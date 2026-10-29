"""Reviewable, opt-in transfer of sandbox Git changes to the original repository.

This is a change export, not a trusted backup or a transactional Git merge.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from . import core as c
from . import workspace_io as wio

FORMAT = "ocs-git-changes-v1"
HISTORY_MEMBER = "history.bundle"
MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024


def _git(repo: Path, *args: str, check=True) -> bytes:
    p = c.run_program(["git", "-C", str(repo), *args], capture_output=True, check=False)
    if check and p.returncode:
        raise c.SandboxError(f"git {' '.join(args[:2])} failed: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_rel(name: str) -> Path:
    if not name or "\\" in name or "\x00" in name or re.match(r"^[A-Za-z]:", name):
        raise c.SandboxError("Unsafe file name in change bundle")
    p = PurePosixPath(name)
    if p.is_absolute() or any(part in ("", ".", "..") for part in name.split("/")):
        raise c.SandboxError("Unsafe relative path in change bundle")
    if any(part.lower() == ".git" for part in p.parts):
        raise c.SandboxError("Git control directory cannot be exported as untracked content")
    return Path(*p.parts)


def _clean(repo: Path) -> bool:
    return not _git(repo, "status", "--porcelain", "--untracked-files=all")


def _workspace(m: dict) -> Path:
    from . import workspaces
    if workspaces.is_direct(m):
        raise c.SandboxError(c.DIRECT_CHANGES)
    repo = workspaces.managed_path(m)
    if not wio.is_git_workspace(repo):
        raise c.SandboxError("Stage 03 requires a Git sandbox workspace")
    # The base commit is what a transfer needs; the source is only a hint (a restored project
    # records none: it named a directory of the backed-up machine).
    if not m.get("base_commit"):
        raise c.SandboxError("Environment has no recorded base commit: change transfer needs a project imported "
                             "from a Git repository (or restored from a backup of one)")
    wio.git(repo, "cat-file", "-e", m["base_commit"] + "^{commit}")
    return repo


def change_summary(m: dict) -> dict:
    repo = _workspace(m)
    base = m["base_commit"]
    committed = wio.git(repo, "log", "--format=%h %s", f"{base}..HEAD", "--").decode(errors="replace")
    status = wio.git(repo, "status", "--short").decode(errors="replace")
    stat_text = wio.git(repo, "diff", "--no-ext-diff", "--no-textconv", "--stat", base, "--").decode(errors="replace")
    return {"base": base, "head": wio.git(repo, "rev-parse", "HEAD").decode().strip(),
            "commits": committed, "status": status, "diffstat": stat_text}


def _submodules(repo: Path) -> list[str]:
    output = wio.git(repo, "ls-files", "--stage", "-z")
    return [os.fsdecode(entry.split(b"\t", 1)[1]) for entry in output.split(b"\0")
            if entry.startswith(b"160000 ") and b"\t" in entry]


def _validate_link_target(name: str, target: str) -> None:
    if not target or target.startswith("/") or "\\" in target or "\x00" in target:
        raise c.SandboxError(f"Unsafe symlink target: {name}")
    parts = list(PurePosixPath(name).parts[:-1])
    for part in target.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise c.SandboxError(f"Symlink escapes workspace: {name}")
            parts.pop()
        else:
            parts.append(part)


# Paths that host tools read and act on (Git attributes and submodules, CI, editors, hooks
# managers, direnv): listed for review, not refused.
ATTENTION_NAMES = {".gitattributes", ".gitmodules", ".envrc", ".gitlab-ci.yml", ".pre-commit-config.yaml"}
ATTENTION_DIRS = {".github", ".githooks", ".husky", ".vscode", ".idea", ".devcontainer"}


def _patch_facts(patch: bytes) -> tuple[list[str], dict[str, str]]:
    """Paths a patch touches and the new mode of created or mode-changed paths, parsed by
    `git apply` (no repository is read; outside any repository)."""
    if not patch:
        return [], {}
    with tempfile.TemporaryDirectory(prefix="ocs-patch-") as temp:
        patch_file = Path(temp) / "changes.patch"
        patch_file.write_bytes(patch)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        def run(*args):
            p = c.run_program(["git", "apply", *args, str(patch_file)], cwd=temp, env=env,
                               capture_output=True, check=False)
            if p.returncode:
                raise c.SandboxError(f"Cannot read the patch: {p.stderr.decode(errors='replace').strip()}")
            return p.stdout
        fields = run("--numstat", "-z").split(b"\0")
        summary = run("--summary").decode("utf-8", errors="replace")
    paths, i = [], 0
    while i < len(fields):
        entry = fields[i]
        if entry.count(b"\t") >= 2:
            name = entry.split(b"\t", 2)[2]
            if name:
                paths.append(os.fsdecode(name))
            else:  # rename or copy: "added\tdeleted\t\0old\0new"
                paths.append(os.fsdecode(fields[i + 2]))
                i += 2
        i += 1
    modes = {}
    for line in summary.splitlines():
        found = re.fullmatch(r" (?:create mode (\d{6})|mode change \d{6} => (\d{6})) (.*)", line)
        if found:
            modes[found.group(3)] = found.group(1) or found.group(2)
    return paths, modes


def attention(manifest: dict, patch: bytes) -> list[str]:
    """What a reviewer should look at closely: paths host tools act on, symbolic links, and
    files that become executable (tracked from the patch, untracked from the manifest)."""
    paths, modes = _patch_facts(patch)
    untracked = manifest.get("untracked", {})
    out = []
    for name in sorted(set(paths) | set(untracked) | set(manifest.get("symlinks", {}))):
        parts = PurePosixPath(name).parts
        reasons = []
        if parts and (parts[-1] in ATTENTION_NAMES or any(p in ATTENTION_DIRS for p in parts[:-1])):
            reasons.append("host tools act on it")
        if modes.get(name) == "120000" or name in manifest.get("symlinks", {}):
            reasons.append("symbolic link")
        if modes.get(name) == "100755" or (untracked.get(name) or {}).get("executable"):
            reasons.append("executable")
        if reasons:
            out.append(f"{name} ({', '.join(reasons)})")
    return out


def _check_tracked_links(tree: Path, source: Path, base: str) -> None:
    """Refuse symbolic links in the result that point outside the repository, unless the source
    already has the same link at the base commit (the rule for untracked links, applied to
    tracked ones)."""
    for root, dirs, files in os.walk(tree):
        if Path(root) == tree and ".git" in dirs:
            dirs.remove(".git")
        for entry in dirs + files:
            path = Path(root) / entry
            if not path.is_symlink():
                continue
            name = path.relative_to(tree).as_posix()
            target = os.readlink(path)
            try:
                _validate_link_target(name, target)
            except c.SandboxError:
                listed = _git(source, "ls-tree", "-z", base, "--", name).split(b"\0")[0]
                if listed.startswith(b"120000 ") and _git(source, "cat-file", "blob", listed.split()[2].decode()) == os.fsencode(target):
                    continue
                raise c.SandboxError(f"Unsafe tracked symlink target: {name} -> {target!r} (links are transferred "
                                     "only when they stay inside the repository; copy it by hand if you need it)") from None


def export_changes(m: dict, destination: Path | None = None) -> Path:
    """Package the entire base-to-worktree binary patch and non-ignored untracked regular files."""
    if destination is not None:
        from . import workspaces
        workspaces.refuse_output_inside(destination, "a change bundle")
    with c.lock(m["id"]):
        repo = _workspace(m)
        base = m["base_commit"]
        wio.require_readable(repo, m["name"], skip_git=True)
        submodules = _submodules(repo)
        if submodules:
            raise c.SandboxError("Submodules are not yet supported by change export: " + ", ".join(submodules))
        patch = wio.git(repo, "-c", "core.quotePath=false", "diff", "--binary", "--no-ext-diff", "--no-textconv", base, "--")
        names = wio.git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
        contents = {}
        executable = set()
        link_targets = {}
        total = len(patch)
        for raw in names:
            if not raw:
                continue
            try:
                name = os.fsdecode(raw)
                if name.endswith("/"):  # git lists an embedded repository as "dir/"
                    raise c.SandboxError(f"Embedded Git repository is not supported by change export: {name}")
                rel = _safe_rel(name)
                src = repo / rel
                # Parent symlinks could redirect file reads outside workspace.
                for parent in list(src.parents):
                    if parent == repo:
                        break
                    if parent.is_symlink():
                        raise c.SandboxError(f"Symlink in untracked path: {name}")
                if src.is_symlink():
                    target = os.readlink(src)
                    _validate_link_target(name, target)
                    link_targets[name] = target
                    continue
                if not stat.S_ISREG(src.lstat().st_mode):
                    raise c.SandboxError(f"Unsupported untracked file type: {name}")
                # O_NOFOLLOW walk: a concurrent symlink swap cannot redirect the read.
                data, mode = wio.read_file(repo, name, limit=MAX_FILE)
                total += len(data)
                if total > MAX_TOTAL:
                    raise c.SandboxError("Change export exceeds size limit")
                contents[name] = data
                if mode & 0o100:
                    executable.add(name)
            except (OSError, UnicodeError) as exc:
                raise c.SandboxError(f"Cannot export untracked path: {raw!r}: {exc}") from exc
        # Preserve original commits separately from the flattened working-tree patch.
        # Git bundle is optional for older exports and may be empty when HEAD == base.
        head = wio.git(repo, "rev-parse", "HEAD").decode().strip()
        history = b""
        if head != base:
            with tempfile.TemporaryDirectory(prefix="ocs-history-") as tmpdir:
                bundle_file = Path(tmpdir) / HISTORY_MEMBER
                wio.git(repo, "bundle", "create", str(bundle_file), "HEAD", "^" + base)
                history = bundle_file.read_bytes()
        manifest = {
            "format": FORMAT, "created": datetime.now(UTC).isoformat(),
            "environment_id": m["id"], "environment_name": m["name"],
            "source_hint": m["source"], "base": base,
            "head": head,
            "patch_sha256": _sha(patch), "patch_size": len(patch),
            "history_sha256": _sha(history) if history else None,
            "history_size": len(history),
            "symlinks": link_targets,
            "untracked": {name: {"sha256": _sha(data), "size": len(data), "executable": name in executable}
                          for name, data in sorted(contents.items())},
        }
        out_dir = Path(destination).expanduser() if destination else c.BASE / "changes"
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{m['name']}-{m['id']}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.ocschanges"
        target = out_dir / filename
        if target.exists():
            raise c.SandboxError("Change bundle exists; refusing overwrite")
        fd, tmp = tempfile.mkstemp(prefix=".ocs-changes-", dir=out_dir)
        try:
            with os.fdopen(fd, "wb") as stream:
                with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED,
                                     allowZip64=True) as z:
                    z.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode())
                    z.writestr("changes.patch", patch)
                    if history:
                        z.writestr(HISTORY_MEMBER, history)
                    for name, data in sorted(contents.items()):
                        z.writestr("untracked/" + name, data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(tmp, 0o600)
            os.link(tmp, target)  # no-clobber publication
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return target


def read_bundle(path: Path) -> tuple[dict, bytes, dict[str, bytes]]:
    """Validate members and hashes before returning any content to the apply workflow."""
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or len(names) > 100000:
                raise c.SandboxError("Duplicate or excessive bundle entries")
            if "manifest.json" not in names or "changes.patch" not in names:
                raise c.SandboxError("Missing change bundle components")
            total = 0
            for i in infos:
                if i.is_dir() or (i.external_attr >> 16) & 0o170000 not in (0, stat.S_IFREG):
                    raise c.SandboxError("Unsupported archive entry type")
                if i.file_size > MAX_FILE or i.compress_size > MAX_TOTAL:
                    raise c.SandboxError("Oversized bundle member")
                total += i.file_size
                if total > MAX_TOTAL:
                    raise c.SandboxError("Bundle exceeds uncompressed size limit")
                # history.bundle is written whenever the sandbox has commits.
                if i.filename not in ("manifest.json", "changes.patch", HISTORY_MEMBER):
                    if not i.filename.startswith("untracked/"):
                        raise c.SandboxError("Unexpected archive member")
                    _safe_rel(i.filename[len("untracked/"):])
            manifest = json.loads(z.read("manifest.json"))
            if manifest.get("format") != FORMAT:
                raise c.SandboxError("Unsupported change bundle format")
            if not re.fullmatch(r"[a-f0-9]{40,64}", manifest.get("base", "")):
                raise c.SandboxError("Invalid base commit")
            patch = z.read("changes.patch")
            if len(patch) != manifest.get("patch_size") or _sha(patch) != manifest.get("patch_sha256"):
                raise c.SandboxError("Patch checksum mismatch")
            files = {}
            entries = manifest.get("untracked")
            if not isinstance(entries, dict):
                raise c.SandboxError("Invalid untracked manifest")
            expected = {"manifest.json", "changes.patch"}
            if manifest.get("history_size", 0):
                expected.add(HISTORY_MEMBER)
                history = z.read(HISTORY_MEMBER)
                if len(history) != manifest["history_size"] or _sha(history) != manifest.get("history_sha256"):
                    raise c.SandboxError("Git history bundle checksum mismatch")
            for name, info in entries.items():
                _safe_rel(name)
                key = "untracked/" + name
                expected.add(key)
                data = z.read(key)
                if len(data) != info.get("size") or _sha(data) != info.get("sha256"):
                    raise c.SandboxError(f"Checksum mismatch: {name}")
                if not isinstance(info.get("executable", False), bool):
                    raise c.SandboxError(f"Invalid executable flag: {name}")
                files[name] = data
            links = manifest.get("symlinks", {})
            if not isinstance(links, dict):
                raise c.SandboxError("Invalid symlinks manifest")
            for name, target in links.items():
                _safe_rel(name)
                if not isinstance(target, str):
                    raise c.SandboxError("Invalid symlink target")
                _validate_link_target(name, target)
                if name in files:
                    raise c.SandboxError("Duplicate regular file and symlink")
            if expected != set(names):
                raise c.SandboxError("Bundle members differ from manifest")
            return manifest, patch, files
    except (zipfile.BadZipFile, KeyError, ValueError, TypeError, OSError) as exc:
        raise c.SandboxError(f"Invalid change bundle: {exc}") from exc


def _mark_executable(dst: Path, executable: bool) -> None:
    if executable:  # read bits become execute bits, as Git does on checkout
        mode = dst.stat().st_mode & 0o777
        dst.chmod(mode | (mode & 0o444) >> 2)


def _executable(manifest: dict, name: str) -> bool:
    return bool((manifest.get("untracked", {}).get(name) or {}).get("executable"))


def review_apply(path: Path, source: Path, *, apply: bool = False) -> dict:
    """Refuse changed sources, unexpected untracked collisions and patch conflicts.

    An explicit apply is NOT atomic against concurrent edits; stop other writers first.
    """
    manifest, patch, files = read_bundle(path)
    source = Path(source).expanduser().resolve(strict=True)
    if not (source / ".git").exists():
        raise c.SandboxError("Target must be a Git repository root")
    root = Path(os.fsdecode(_git(source, "rev-parse", "--show-toplevel").strip())).resolve()
    if root != source:
        raise c.SandboxError("Target must be the Git repository root")
    current = _git(source, "rev-parse", "HEAD").decode().strip()
    if current != manifest["base"]:
        raise c.SandboxError("Source HEAD diverged from exported base; manual merge required")
    if not _clean(source):
        raise c.SandboxError("Source contains modifications or untracked files; refusing apply")
    for name in list(files) + list(manifest.get("symlinks", {})):
        rel = _safe_rel(name)
        dst = source / rel
        if dst.exists() or dst.is_symlink():
            raise c.SandboxError(f"Untracked destination already exists: {name}")
        for ancestor in dst.parents:
            if ancestor == source:
                break
            if ancestor.is_symlink():
                raise c.SandboxError(f"Symlink parent in target: {name}")
    with tempfile.TemporaryDirectory(prefix="ocs-git-apply-") as temp:
        patch_file = Path(temp) / "changes.patch"
        patch_file.write_bytes(patch)
        if patch:
            _git(source, "apply", "--check", "--binary", str(patch_file))
        # Verify the complete result in an isolated clone before touching the source.
        # A patch can itself introduce paths colliding with exported untracked files.
        preview = Path(temp) / "preview"
        p = c.run_program(["git", "clone", "--quiet", "--no-hardlinks", "--", str(source), str(preview)],
                           capture_output=True, check=False)
        if p.returncode:
            raise c.SandboxError(f"Cannot create preflight clone: {p.stderr.decode(errors='replace')}")
        if patch:
            _git(preview, "apply", "--binary", str(patch_file))
        _check_tracked_links(preview, source, current)
        for name in list(files) + list(manifest.get("symlinks", {})):
            dst = preview / _safe_rel(name)
            if dst.exists() or dst.is_symlink():
                raise c.SandboxError(f"Patch conflicts with untracked file: {name}")
            for ancestor in dst.parents:
                if ancestor == preview:
                    break
                if ancestor.is_symlink() or (ancestor.exists() and not ancestor.is_dir()):
                    raise c.SandboxError(f"Unsafe untracked parent after patch: {name}")
        if apply and manifest.get("symlinks"):
            raise c.SandboxError("Direct apply does not support untracked symlinks; use 'changes stage'")
        if apply:
            # Recheck immediately before mutation; not a concurrency lock on external Git tools.
            if current != _git(source, "rev-parse", "HEAD").decode().strip() or not _clean(source):
                raise c.SandboxError("Source changed during review")
            _apply_or_restore(source, patch, patch_file, files, manifest)
    return {"source": str(source), "base": current, "patch_bytes": len(patch),
            "untracked_count": len(files), "attention": attention(manifest, patch), "applied": apply}


def _apply_or_restore(source: Path, patch: bytes, patch_file: Path, files: dict, manifest: dict) -> None:
    """Apply, or undo exactly what this call wrote, so that a failure never leaves a half-applied
    source.

    The source was verified clean at the base commit just before, so reversing the patch
    and removing only the files/directories created here restores that state.
    """
    created_files, created_dirs, patched = [], [], False
    try:
        if patch:
            _git(source, "apply", "--binary", str(patch_file))
            patched = True
        for name, data in files.items():
            dst = source / _safe_rel(name)
            missing = [d for d in reversed(dst.parents) if d != source and source in d.parents and not d.exists()]
            for d in missing:
                d.mkdir()
                created_dirs.append(d)
            with dst.open("xb") as f:
                created_files.append(dst)
                f.write(data)
            _mark_executable(dst, _executable(manifest, name))
    except (OSError, c.SandboxError) as exc:
        problems = []
        for f in reversed(created_files):
            try: f.unlink()
            except OSError as err: problems.append(f"{f}: {err}")
        for d in reversed(created_dirs):
            try: d.rmdir()
            except OSError as err: problems.append(f"{d}: {err}")
        if patched:
            try: _git(source, "apply", "-R", "--binary", str(patch_file))
            except c.SandboxError as err: problems.append(str(err))
        if not problems and not _clean(source):
            problems.append("source not clean after rollback")
        state = ("source restored to its previous clean state" if not problems else
                 "ROLLBACK INCOMPLETE, inspect with 'git status': " + "; ".join(problems))
        raise c.SandboxError(f"Apply failed: {exc}; {state}") from exc


def inspect_changes(path: Path) -> dict:
    """Return an exact patch preview and inventory, without writing to a repository."""
    manifest, patch, files = read_bundle(path)
    return {"base": manifest["base"], "head": manifest["head"],
            "patch": patch.decode("utf-8", errors="replace"),
            "untracked": sorted(files), "symlinks": manifest.get("symlinks", {}), "has_history": bool(manifest.get("history_size")),
            "attention": attention(manifest, patch)}


def stage_changes(path: Path, source: Path, branch: str | None = None) -> dict:
    """Create a review branch without changing HEAD, index, or source working tree.

    This is the recommended safe application workflow. The resulting commit
    contains the final sandbox files; original commit history remains in the
    attached history.bundle for explicit inspection/import.
    """
    manifest, patch, files = read_bundle(path)
    source = Path(source).expanduser().resolve(strict=True)
    if not (source / ".git").exists():
        raise c.SandboxError("Target must be a Git repository root")
    root = Path(os.fsdecode(_git(source, "rev-parse", "--show-toplevel").strip())).resolve()
    if root != source or not _clean(source):
        raise c.SandboxError("Target must be a clean Git repository root")
    current = _git(source, "rev-parse", "HEAD").decode().strip()
    if current != manifest["base"]:
        raise c.SandboxError("Source HEAD differs from the exported base")
    branch = branch or "ocs/review-" + manifest["environment_id"][:12]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,120}", branch) or ".." in branch or "//" in branch or branch.endswith(("/", ".lock")):
        raise c.SandboxError("Invalid review branch name")
    ref = "refs/heads/" + branch
    if _git(source, "show-ref", "--verify", ref, check=False):
        raise c.SandboxError("Review branch already exists")
    with tempfile.TemporaryDirectory(prefix="ocs-stage-") as temp:
        preview = Path(temp) / "preview"
        p = c.run_program(["git", "clone", "--quiet", "--no-hardlinks", "--", str(source), str(preview)],
                           capture_output=True, check=False)
        if p.returncode:
            raise c.SandboxError(p.stderr.decode(errors="replace"))
        if patch:
            patchfile = Path(temp) / "changes.patch"
            patchfile.write_bytes(patch)
            _git(preview, "apply", "--binary", str(patchfile))
        for name, target in manifest.get("symlinks", {}).items():
            dst = preview / _safe_rel(name)
            if dst.exists() or dst.is_symlink():
                raise c.SandboxError(f"Symlink collision in review: {name}")
            for parent in dst.parents:
                if parent == preview:
                    break
                if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                    raise c.SandboxError(f"Unsafe symlink parent: {name}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.symlink_to(target)
        for name, data in files.items():
            dst = preview / _safe_rel(name)
            if dst.exists() or dst.is_symlink():
                raise c.SandboxError(f"File collision in review: {name}")
            for parent in dst.parents:
                if parent == preview:
                    break
                if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                    raise c.SandboxError(f"Unsafe path in review: {name}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            with dst.open("xb") as f:
                f.write(data)
            _mark_executable(dst, _executable(manifest, name))
        _check_tracked_links(preview, source, current)
        _git(preview, "add", "--all")
        tree = _git(preview, "write-tree").decode().strip()
        message = f"Review OpenCode sandbox changes ({manifest['environment_name']})"
        commit = _git(preview, "-c", "user.name=OpenCode Sandbox", "-c", "user.email=opencode-sandbox@localhost",
                      "commit-tree", tree, "-p", current, "-m", message).decode().strip()
        # Commit object lives in the clone; transfer it to source before updating the ref.
        _git(preview, "update-ref", "refs/heads/ocs-export", commit)
        _git(source, "fetch", "--no-tags", str(preview), "refs/heads/ocs-export")
        if current != _git(source, "rev-parse", "HEAD").decode().strip() or not _clean(source):
            raise c.SandboxError("Source changed during staging")
        _git(source, "update-ref", ref, commit, "0" * len(current))
    return {"branch": branch, "commit": commit, "source": str(source), "source_unchanged": True,
            "attention": attention(manifest, patch)}


def drop_review_branch(source: Path, branch: str, *, expected_commit: str) -> None:
    """Remove only the exact branch created by staging, using compare-and-swap."""
    if not re.fullmatch(r"[0-9a-f]{40,64}", expected_commit):
        raise c.SandboxError("Invalid expected commit")
    if not branch.startswith("ocs/review-"):
        raise c.SandboxError("Only managed review branches may be removed")
    if not expected_commit.strip("0"):
        # git update-ref -d treats an all-zero old value as "do not verify".
        raise c.SandboxError("Invalid expected commit")
    source = Path(source).expanduser().resolve(strict=True)
    current = _git(source, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch, check=False).decode().strip()
    if not current:
        raise c.SandboxError(f"Review branch not found: {branch}")  # update-ref -d succeeded silently
    if current != expected_commit:
        raise c.SandboxError(f"Review branch {branch} now points to {current}, not {expected_commit}; not removed")
    _git(source, "update-ref", "-d", "refs/heads/" + branch, expected_commit)


def review_branch_diff(source: Path, branch: str) -> str:
    """Compare a review branch to its parent without checkout or worktree changes."""
    source = Path(source).expanduser().resolve(strict=True)
    root = Path(os.fsdecode(_git(source, "rev-parse", "--show-toplevel").strip())).resolve()
    if root != source or not branch.startswith("ocs/review-"):
        raise c.SandboxError("Expected Git repository root and managed review branch")
    _git(source, "check-ref-format", "--branch", branch)
    ref = "refs/heads/" + branch
    commit = _git(source, "rev-parse", "--verify", ref).decode().strip()
    parent = _git(source, "rev-parse", "--verify", commit + "^1").decode().strip()
    return _git(source, "-c", "core.quotePath=false", "diff", "--no-ext-diff", "--stat", parent, commit).decode(errors="replace") + "\n" + _git(source, "-c", "core.quotePath=false", "diff", "--no-ext-diff", "--binary", parent, commit).decode(errors="replace")
