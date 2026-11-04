"""One-shot local working-state import; no source writes, hooks, filters or temporary commits.

Reuse workspace_io's isolated Git view. Copy the index (not patches) and its missing blobs,
then materialize only index paths and non-ignored untracked paths without following links.
The source is checked again before publication; concurrent edits invalidate the import.
"""
from __future__ import annotations

import errno
import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import core as c
from . import workspace_io as wio

MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
MAX_PATHS = 100_000
_OPERATIONS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-apply", "rebase-merge", "sequencer")


@dataclass(frozen=True)
class Preview:
    fingerprint: str
    entries: tuple[tuple[str, str], ...]

    def describe(self):
        staged = sum(s[0] not in " ?" for s, _ in self.entries)
        unstaged = sum(s[1] not in " ?" for s, _ in self.entries)
        untracked = sum(s == "??" for s, _ in self.entries)
        lines = ["Include working changes (ignored untracked files excluded)",
                 f"{len(self.entries)} changed paths: {staged} staged, {unstaged} unstaged, {untracked} untracked",
                 "Status: index / working tree; R includes the original path."]
        # repr escapes control characters, newlines and surrogate-escaped filenames; no contents.
        lines += [f"  {s} {p!a}" for s, p in self.entries[:12]]
        if len(self.entries) > 12: lines.append(f"  … {len(self.entries) - 12} more")
        lines.append("Non-ignored hidden files are included too. Review the source for secrets first.")
        return "\n".join(lines)


def _git(pgd, source, *args, input=None, allowed=(0,)):
    p = c.run_program(["git", "--git-dir", str(pgd), "--work-tree", str(source),
                       "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
                       "-c", "core.untrackedCache=false", "-c", "core.attributesFile=" + os.devnull,
                       "-c", "protocol.allow=never", *args],
                      cwd=source, env=wio._clean_env(), input=input, capture_output=True, check=False)
    if p.returncode not in allowed:
        # Git diagnostics can contain source file contents or configuration secrets.
        raise c.SandboxError(f"Working-state import: git {args[0]} failed; source unchanged")
    return p.stdout


def _validate(pgd, source):
    gd = source / ".git"
    if any(os.path.lexists(gd / p) for p in (*_OPERATIONS, "index.lock", "shallow", "info/sparse-checkout")):
        raise c.SandboxError("Working-state import refuses in-progress Git operations, shallow/sparse repositories or an index lock; finish the operation or use committed-only import")
    if any(gd.glob("sharedindex.*")):
        raise c.SandboxError("Working-state import does not support split indexes; disable split index explicitly in the source first")
    if not (pgd / "index").exists():
        raise c.SandboxError("Working-state import requires a committed repository and an existing Git index (repositories with no commits are unsupported)")
    if any((gd / "objects/pack").glob("*.promisor")):
        raise c.SandboxError("Working-state import does not support partial clones; use a complete local repository")
    config = pgd.parent / "workspace-config"
    redirects = c.run_program(["git", "config", "--file", str(config), "--name-only", "--get-regexp",
                               r"^(include\.|includeif\.|core\.worktree$|extensions\.partialclone$)"],
                              cwd="/", env=wio._clean_env(), capture_output=True, check=False)
    if redirects.returncode != 1:
        raise c.SandboxError("Working-state import refuses repository-local Git includes/worktree/partial-clone redirections; use a standalone repository or committed-only import")
    try: head = _git(pgd, source, "rev-parse", "--verify", "HEAD^{commit}").strip()
    except c.SandboxError:
        raise c.SandboxError("Working-state import requires a readable committed HEAD; repositories with no commits or missing objects are unsupported") from None
    entries = _git(pgd, source, "ls-files", "--stage", "-z").split(b"\0")
    blobs = set()
    for entry in filter(None, entries):
        metadata, _, path = entry.partition(b"\t")
        mode, oid, stage = metadata.split()
        _path(os.fsdecode(path))
        if mode == b"160000":
            raise c.SandboxError("Working-state import does not support Git submodules; use committed-only import")
        if stage != b"0":
            raise c.SandboxError("Working-state import does not support unresolved conflicts; resolve them first or use committed-only import")
        if mode not in (b"100644", b"100755", b"120000"):
            raise c.SandboxError("Working-state import does not support this Git index entry type")
        blobs.add(oid)
    if any(e.startswith(b"160000 ") for e in _git(pgd, source, "ls-tree", "-r", "-z", "HEAD").split(b"\0")):
        raise c.SandboxError("Working-state import does not support Git submodules; use committed-only import")
    # Skip-worktree/assume-unchanged hide edits from the preview and can hide missing files.
    if any(e[:1] != b"H" for e in filter(None, _git(pgd, source, "ls-files", "-v", "-z").split(b"\0"))):
        raise c.SandboxError("Working-state import refuses skip-worktree/assume-unchanged entries; clear those flags first")
    return head, blobs


def _path(name):
    parts = wio._parts(name)
    if any(p.lower() == ".git" for p in parts):
        raise c.SandboxError("Working-state import refuses nested repositories or .git paths")
    return parts


def _entry(source, name):
    """Read data or link text via directory FDs; never follow any source path component."""
    parts = _path(name)
    fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            try: nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError: return None
            except OSError as exc:
                if exc.errno not in (errno.ENOTDIR, errno.ELOOP): raise
                # A tracked directory replaced by a regular file is an ordinary deletion.
                if stat.S_ISREG(os.stat(part, dir_fd=fd, follow_symlinks=False).st_mode): return None
                raise c.SandboxError(f"Working-state import refuses symlinked or special parents of tracked paths at {name!a}") from None
            os.close(fd); fd = nfd
        try: st = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError: return None
        if stat.S_ISLNK(st.st_mode):
            return os.fsencode(os.readlink(parts[-1], dir_fd=fd)), 0o120000
        if stat.S_ISDIR(st.st_mode):
            # Only index paths reach here (the scan descends into directories): a tracked file
            # replaced by a directory is a deletion; the directory's own files are scanned separately.
            return None
        if not stat.S_ISREG(st.st_mode):
            raise c.SandboxError(f"Working-state import refuses special files at {name!a}")
        ffd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(ffd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE:
                raise c.SandboxError(f"Working-state import requires regular files of at most 256 MiB: {name!a}")
            data = bytearray()
            while chunk := os.read(ffd, 1024 * 1024):
                data.extend(chunk)
                if len(data) > MAX_FILE: raise c.SandboxError("Working-state import file size limit exceeded")
            after = os.fstat(ffd)
            if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise c.SandboxError("Source changed during import; retry with the repository idle")
            return bytes(data), stat.S_IMODE(after.st_mode) & 0o777
        finally: os.close(ffd)
    finally: os.close(fd)


def _ignores(pgd, source):
    """Honor user-global ignores without loading executable host/repository Git settings."""
    env = wio._clean_env()
    env.pop("GIT_CONFIG_GLOBAL", None)
    p = c.run_program(["git", "config", "--global", "--includes", "--path", "--get", "core.excludesFile"],
                      cwd="/", env=env, capture_output=True, check=False)
    if p.returncode not in (0, 1): raise c.SandboxError("Cannot read global Git ignore configuration safely")
    default = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "git/ignore"
    path = Path(os.fsdecode(p.stdout).strip()) if p.returncode == 0 else default
    if not path.is_absolute(): raise c.SandboxError("Working-state import requires an absolute global Git excludesFile")
    # Repository-local excludesFile is a redirection, not a file in the selected tree.
    config = pgd.parent / "workspace-config"
    local = c.run_program(["git", "config", "--file", str(config), "--get", "core.excludesFile"],
                          cwd="/", env=wio._clean_env(), capture_output=True, check=False)
    if local.returncode != 1:
        raise c.SandboxError("Working-state import does not support repository-local core.excludesFile; use .gitignore or .git/info/exclude")
    # Git opens ignore files normally (a FIFO would block). Only bounded regular-file
    # snapshots are handed to it; no live source info/attributes or info/exclude reads.
    global_copy = pgd.parent / "global-ignore"
    if not global_copy.exists():
        if path.exists(): wio._copy_snapshot(path.resolve(strict=True), global_copy, wio._MAX_CONFIG, "global ignores")
        else: global_copy.write_bytes(b"")
    info = pgd / "info"
    if info.is_symlink(): info.unlink()
    info.mkdir(exist_ok=True)
    exclude = source / ".git/info/exclude"
    if os.path.lexists(exclude) and not (info / "exclude").exists():
        wio._copy_snapshot(exclude, info / "exclude", wio._MAX_CONFIG, "info/exclude")
    return ("-c", "core.excludesFile=" + str(global_copy))


def _paths(pgd, source, ignores):
    """Enumerate no-follow; let Git evaluate ignore rules only in a private rule tree.

    Prune ignored directories before reading their files (dependencies/caches/secrets stay out).
    Git's own source scan would follow pathname races and block on special .gitignore files.
    """
    selected = set(filter(None, _git(pgd, source, "ls-files", "--cached", "-z").split(b"\0")))
    with tempfile.TemporaryDirectory(prefix="ignores-", dir=pgd.parent) as tmp:
        rules = Path(tmp)
        visited = rule_bytes = 0
        def visit(fd, parts):
            nonlocal visited, rule_bytes
            visited += 1
            if visited > MAX_PATHS: raise c.SandboxError("Working-state import exceeds 100,000 directories")
            entries = list(os.scandir(fd))
            if parts and any(e.name.lower() == ".git" for e in entries):
                raise c.SandboxError("Working-state import refuses nested repositories; ignore them or import separately")
            names = {e.name for e in entries}
            rule_dir = rules.joinpath(*parts)
            rule_dir.mkdir(parents=True, exist_ok=True)
            if ".gitignore" in names:
                name = "/".join((*parts, ".gitignore"))
                entry = _entry(source, name)
                if entry is not None and entry[1] != 0o120000:
                    data, _ = entry
                    if len(data) > wio._MAX_CONFIG: raise c.SandboxError("Working-state .gitignore exceeds 1 MiB")
                    rule_bytes += len(data)
                    if rule_bytes > MAX_TOTAL: raise c.SandboxError("Working-state ignore rules exceed 1 GiB")
                    (rule_dir / ".gitignore").write_bytes(data)
            candidates = []
            for entry in entries:
                if not parts and entry.name == ".git": continue
                name = os.fsencode("/".join((*parts, entry.name)))
                is_dir = entry.is_dir(follow_symlinks=False)
                candidates.append((entry.name, name, is_dir))
            payload = b"\0".join(name + (b"/" if directory else b"") for _, name, directory in candidates)
            ignored = set(_git(pgd, rules, *ignores, "check-ignore", "--no-index", "-z", "--stdin",
                               input=payload + b"\0" if payload else b"", allowed=(0, 1)).split(b"\0"))
            for component, name, directory in candidates:
                if name + (b"/" if directory else b"") in ignored: continue
                if directory:
                    child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try: visit(child, (*parts, component))
                    finally: os.close(child)
                else:
                    selected.add(name)
                    if len(selected) > MAX_PATHS: raise c.SandboxError("Working-state import exceeds 100,000 paths")
        fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: visit(fd, ())
        finally: os.close(fd)
    return sorted(selected)


def _capture(pgd, source, destination=None):
    # Git status hashes the private materialized tree, never the host working tree. This
    # closes parent-symlink races between our no-follow reads and Git's pathname-based reads.
    if destination is None:
        with tempfile.TemporaryDirectory(prefix="snapshot-", dir=pgd.parent) as tmp:
            return _capture(pgd, source, Path(tmp))
    head, blobs = _validate(pgd, source)
    index = (pgd / "index").read_bytes()
    # Logical index content, not raw bytes: a read-only host `git status` (IDE, prompt) may
    # rewrite cached stat data between preview and import without changing anything imported.
    digest = hashlib.sha256(head + b"\0" + (pgd / "HEAD").read_bytes() + b"\0")
    digest.update(_git(pgd, source, "ls-files", "--stage", "-z") + b"\0")
    digest.update(_git(pgd, source, "ls-files", "-v", "-z") + b"\0")
    digest.update(_git(pgd, source, "rev-parse", "--symbolic-full-name", "HEAD"))
    ignores = _ignores(pgd, source)
    paths = _paths(pgd, source, ignores)
    if len(paths) > MAX_PATHS: raise c.SandboxError("Working-state import exceeds 100,000 working-tree paths; use committed-only import")
    total = 0
    for raw_name in paths:
        name = os.fsdecode(raw_name)
        entry = _entry(source, name)
        digest.update(raw_name + b"\0")
        if entry is None:
            digest.update(b"missing\0"); continue
        data, mode = entry
        total += len(data)
        if total > MAX_TOTAL: raise c.SandboxError("Working-state import exceeds 1 GiB of working-tree files; use committed-only import")
        digest.update(str(mode).encode() + b"\0" + hashlib.sha256(data).digest())
        target = destination.joinpath(*_path(name))
        # Destination starts empty, and parents must never be links from an earlier entry.
        parent = destination
        for part in _path(name)[:-1]:
            parent = parent / part
            if parent.is_symlink(): raise c.SandboxError("Unsafe destination parent in working-state import")
            parent.mkdir(exist_ok=True)
        if mode == 0o120000: target.symlink_to(os.fsdecode(data))
        else:
            with target.open("xb") as f: f.write(data)
            target.chmod(mode)
    raw = _git(pgd, destination, *ignores, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=all")
    fields = iter(raw.split(b"\0")); statuses = []
    for entry in fields:
        if not entry: continue
        status, name = entry[:2].decode("ascii"), os.fsdecode(entry[3:])
        if "R" in status or "C" in status: name += " <- " + os.fsdecode(next(fields))
        statuses.append((status, name))
    digest.update(raw)
    return Preview(digest.hexdigest(), tuple(statuses)), head, blobs, index


def _copy_index_extensions(pgd, source, dstgd, destination, staged_size):
    """Cache-tree trees and resolve-undo blobs are index references too; without them the
    imported repository fails fsck/gc. Copy only missing trees/blobs, verifying each object ID."""
    for _ in range(1024):  # one round per newly reachable tree level
        listed = _git(dstgd, destination, "rev-list", "--objects", "--indexed-objects", "--missing=print",
                      "--no-object-names")
        missing = [line[1:].decode() for line in listed.splitlines() if line.startswith(b"?")]
        if not missing: return
        for oid in missing:
            kind = _git(pgd, source, "cat-file", "-t", oid).strip().decode()
            if kind not in ("blob", "tree"): raise c.SandboxError("Working-state index references an unsupported object")
            staged_size += int(_git(pgd, source, "cat-file", "-s", oid))
            if staged_size > MAX_TOTAL: raise c.SandboxError("Working-state staged objects exceed 1 GiB")
            data = _git(pgd, source, "cat-file", kind, oid)
            if _git(dstgd, destination, "hash-object", "-t", kind, "-w", "--stdin", input=data).strip().decode() != oid:
                raise c.SandboxError("Working-state staged object verification failed")
    raise c.SandboxError("Working-state index object references are too deeply nested")


def preview(source):
    try:
        source = Path(source).expanduser().resolve(strict=True)
        home = Path.home().resolve()
        if source == Path(source.anchor) or source == home or source in home.parents:
            raise c.SandboxError("Choose a project repository, not the home directory or a parent of it")
        if not os.path.lexists(source / ".git"):
            raise c.SandboxError("Include working changes requires a local Git repository root; import the repository root instead")
        gd = wio.check_repository(source)
        with wio._private_git_dir(gd) as pgd:
            return _capture(pgd, source)[0]
    except OSError as exc:
        raise c.SandboxError(f"Source not accessible safely ({exc.strerror}); source unchanged") from None


def clone(source, destination, *, expected=None):
    """Called only for a fresh managed workspace; caller removes it on any failure."""
    try:
        gd = wio.check_repository(source)
        with wio._private_git_dir(gd) as pgd:
            plan, head, blobs, index = _capture(pgd, source)
            if expected is not None and plan.fingerprint != expected:
                raise c.SandboxError("Source changed since import preview; preview again with the repository idle")
            # Upload-pack reads the private config, not the source config. No hardlinks/alternates,
            # no checkout filters/hooks, no network or recursive submodule operations.
            p = c.run_program(["git", "-c", "protocol.file.allow=always", "-c", "protocol.allow=never",
                               "clone", "--quiet", "--no-local", "--no-checkout", "--template=", "--", str(pgd), str(destination)],
                              cwd="/", env=wio._clean_env(), capture_output=True, check=False)
            if p.returncode: raise c.SandboxError("Working-state repository clone failed; source unchanged")
            dstgd = destination / ".git"
            if _git(dstgd, destination, "rev-parse", "HEAD").strip() != head:
                raise c.SandboxError("Source HEAD changed during import; retry with the repository idle")
            # clone can attach a detached HEAD to a branch at the same commit. Resolve
            # through Git, not raw HEAD bytes (reftable uses a placeholder HEAD file).
            branch = _git(pgd, source, "rev-parse", "--symbolic-full-name", "HEAD").strip()
            if branch == b"HEAD": _git(dstgd, destination, "update-ref", "--no-deref", "HEAD", head.decode())
            else: _git(dstgd, destination, "symbolic-ref", "HEAD", os.fsdecode(branch))
            missing = _git(dstgd, destination, "cat-file", "--batch-check", input=b"\n".join(sorted(blobs)) + b"\n") if blobs else b""
            staged_size = 0
            for line in missing.splitlines():
                if not line.endswith(b" missing"): continue
                oid = line.split()[0]
                size = int(_git(pgd, source, "cat-file", "-s", oid.decode()))
                if size > MAX_FILE: raise c.SandboxError("Working-state staged blob exceeds 256 MiB")
                staged_size += size
                if staged_size > MAX_TOTAL: raise c.SandboxError("Working-state staged blobs exceed 1 GiB")
                data = _git(pgd, source, "cat-file", "blob", oid.decode())
                if _git(dstgd, destination, "hash-object", "-w", "--stdin", input=data).strip() != oid:
                    raise c.SandboxError("Working-state staged blob verification failed")
            (dstgd / "index").write_bytes(index)
            _copy_index_extensions(pgd, source, dstgd, destination, staged_size)
            copied = _capture(pgd, source, destination)[0]
            if copied != plan or preview(source) != plan:
                raise c.SandboxError("Source changed during import; retry with the repository idle")
            _git(dstgd, destination, "config", "remote.origin.url", str(source))
            return head.decode()
    except OSError as exc:
        raise c.SandboxError(f"Cannot import working changes safely ({exc.strerror}); source unchanged") from None
