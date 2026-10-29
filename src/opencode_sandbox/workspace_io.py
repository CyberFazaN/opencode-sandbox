"""Host-side access to agent-writable workspaces.

Everything under an environment's ``workspace`` directory, including ``.git``,
can be rewritten by root inside the container. Host Git therefore never reads
the workspace repository's own configuration, hooks or attributes as
configuration: every command runs against a private ``GIT_DIR`` created by the
manager, holding a manager-written config (only the repository storage format
is carried over), snapshots of ``HEAD`` and the index, and symlinks to the
repository's object/ref data (data only). A
repository whose index contains a gitlink (submodule entry) is refused, so
host Git can never start reading a nested repository in the workspace.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import stat
import tempfile
from pathlib import Path, PurePosixPath

from . import core as c

# Paths inside .git that must be real files/directories, and redirections that
# would make Git read another repository on the host.
_NO_SYMLINK = ("config", "HEAD", "index", "packed-refs", "objects", "refs", "reftable", "info", "hooks")
_FORBIDDEN = ("commondir", "objects/info/alternates", "config.worktree", "info/grafts")
# The directories the private GIT_DIR links to: nothing below them may be a symlink either.
_DATA_DIRS = ("objects", "refs", "reftable", "info")
_MAX_HEAD = 1024 * 1024
_MAX_CONFIG = 1024 * 1024
_MAX_SNAPSHOT = 256 * 1024 * 1024
# The only workspace settings carried into the private config: the repository
# storage format, without which Git cannot read the data at all. Values are
# checked against fixed sets; no other setting is ever read.
_FORMAT_KEYS = {"extensions.objectformat": ("sha1", "sha256"),
                "extensions.refstorage": ("files", "reftable")}


def _clean_env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM="1",
               GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1",
               GIT_PAGER="cat", GIT_NO_LAZY_FETCH="1")
    return env


def is_git_workspace(workspace: Path) -> bool:
    """True only for a real ``.git`` directory; a symlink or gitdir file is not trusted."""
    try:
        return stat.S_ISDIR(os.lstat(Path(workspace) / ".git").st_mode)
    except FileNotFoundError:
        return False


def check_repository(workspace: Path) -> Path:
    """Structurally validate an untrusted workspace repository.

    Only metadata that host Git would interpret as redirection is checked here.
    What the repository configures is irrelevant: the Git process never reads
    the workspace repository's own config (see ``git``).
    """
    workspace = Path(workspace)
    gitdir = workspace / ".git"
    try:
        mode = os.lstat(gitdir).st_mode
    except FileNotFoundError:
        raise c.SandboxError("Workspace is not a Git repository") from None
    if not stat.S_ISDIR(mode):
        raise c.SandboxError("Workspace .git is a symlink or gitdir file; refusing host Git access")
    for name in _NO_SYMLINK:
        if (gitdir / name).is_symlink():
            raise c.SandboxError(f"Workspace .git/{name} is a symlink; refusing host Git access")
    for name in _FORBIDDEN:
        if os.path.lexists(gitdir / name):
            raise c.SandboxError(f"Workspace .git/{name} redirects Git; refusing host Git access")
    for name in _DATA_DIRS:
        _refuse_nested_links(gitdir, gitdir / name)
    return gitdir


def _refuse_nested_links(gitdir: Path, top: Path) -> None:
    """A symlink anywhere below the data directories would make host Git read another directory
    of the host (objects, refs of another repository) into exports. Checked when a
    command starts; a change during the command can only change what data is read."""
    stack = [top] if os.path.isdir(top) and not os.path.islink(top) else []
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            raise c.SandboxError(f"Workspace .git cannot be read safely: {exc.strerror}") from exc
        for entry in entries:
            if entry.is_symlink():
                rel = os.path.relpath(entry.path, gitdir)
                raise c.SandboxError(f"Workspace .git/{rel} is a symlink; refusing host Git access")
            if entry.is_dir(follow_symlinks=False):
                stack.append(entry.path)


def _copy_snapshot(src: Path, dst: Path, limit: int, label: str) -> None:
    """Copy one agent-writable file into the private GIT_DIR without following
    symlinks; regular files only, so a planted FIFO cannot block the read.

    The copy keeps the original's timestamps: Git re-reads an index entry's content when the
    entry is not older than the index file, and a fresh mtime would make a same-size change
    written in the index's timestamp tick look unchanged."""
    try:
        fd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise c.SandboxError(f"Workspace .git/{label} cannot be read safely: {exc.strerror}") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise c.SandboxError(f"Workspace .git/{label} is not a regular file; refusing host Git access")
        if st.st_size > limit:
            raise c.SandboxError(f"Workspace .git/{label} is too large; refusing host Git access")
        dfd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            while chunk := os.read(fd, 1024 * 1024):
                written = 0
                while written < len(chunk):
                    written += os.write(dfd, chunk[written:])
            os.utime(dfd, ns=(st.st_atime_ns, st.st_mtime_ns))
        finally:
            os.close(dfd)
    finally:
        os.close(fd)


def _format_config(gitdir: Path, scratch: Path) -> bytes:
    """Private config text carrying only the repository storage format.

    The workspace config is read from a snapshot copy, by `git config --file`,
    which only parses (include directives are off for --file); only the keys
    in ``_FORMAT_KEYS`` are queried and their values must be in the fixed sets.
    """
    if not os.path.lexists(gitdir / "config"):
        return b""
    snapshot = scratch / "workspace-config"
    _copy_snapshot(gitdir / "config", snapshot, _MAX_CONFIG, "config")
    found = {}
    for key, allowed in _FORMAT_KEYS.items():
        p = c.run_program(["git", "config", "--file", str(snapshot), "--get", key],
                           cwd="/", env=_clean_env(), capture_output=True, check=False)
        if p.returncode == 1:
            continue  # not set
        value = p.stdout.decode("utf-8", errors="replace").strip().lower()
        if p.returncode or value not in allowed:
            raise c.SandboxError(f"Workspace .git/config has an unsupported or unreadable {key}; "
                                 "refusing host Git access")
        found[key.split(".", 1)[1]] = value
    if not found:
        return b""
    lines = ["[core]", "\trepositoryformatversion = 1", "[extensions]"]
    lines += [f"\t{name} = {value}" for name, value in sorted(found.items())]
    return ("\n".join(lines) + "\n").encode()


@contextlib.contextmanager
def _private_git_dir(gitdir: Path):
    """A throw-away GIT_DIR for one host Git command on an untrusted workspace.

    ``config`` is manager-written and holds at most the storage format
    (``_format_config``): nothing the agent configured can select a program
    (filters, drivers, hooks, remotes, worktree or include redirection).
    ``HEAD`` and the index are snapshot copies taken without following
    symlinks. Objects and refs are reached through symlinks into the real
    repository (data only); ``check_repository`` refuses
    ``objects/info/alternates`` when it runs, and a later change below these
    directories can only change what data is read.
    """
    tmp = tempfile.mkdtemp(prefix="ocs-gitdir-")
    try:
        pgd = Path(tmp) / "gitdir"
        pgd.mkdir()
        (pgd / "config").write_bytes(_format_config(gitdir, Path(tmp)))
        for name in ("objects", "refs", "reftable", "info", "packed-refs"):
            if os.path.lexists(gitdir / name):
                (pgd / name).symlink_to(gitdir / name)
        _copy_snapshot(gitdir / "HEAD", pgd / "HEAD", _MAX_HEAD, "HEAD")
        if os.path.lexists(gitdir / "index"):
            _copy_snapshot(gitdir / "index", pgd / "index", _MAX_SNAPSHOT, "index")
        yield pgd
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run(pgd: Path, workspace: Path, args, check: bool = True) -> bytes:
    argv = ["git", "--git-dir", str(pgd), "--work-tree", str(workspace),
            "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
            "-c", "core.untrackedCache=false", "-c", "protocol.allow=never", *args]
    p = c.run_program(argv, cwd=workspace, env=_clean_env(), capture_output=True, check=False)
    if check and p.returncode:
        raise c.SandboxError(f"git {' '.join(args[:2])} failed: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout


def git(workspace: Path, *args: str, check: bool = True) -> bytes:
    """Run host Git on an untrusted workspace; returns raw stdout bytes.

    Every call goes through the private GIT_DIR (see the module docstring), and
    a workspace whose index contains a gitlink is refused before any command:
    a populated nested repository makes Git read that repository's own
    configuration, which the manager never validates.
    """
    workspace = Path(workspace)
    gitdir = check_repository(workspace)
    with _private_git_dir(gitdir) as pgd:
        for entry in _run(pgd, workspace, ("ls-files", "--stage", "-z")).split(b"\0"):
            if entry.startswith(b"160000 "):
                path = os.fsdecode(entry.partition(b"\t")[2]) or "?"
                raise c.SandboxError(
                    f"Workspace index contains a Git submodule (gitlink): {path}. Submodule content "
                    "is not supported by host Git access; remove it inside the sandbox "
                    "(git rm --cached) and retry.")
        return _run(pgd, workspace, args, check=check)


def unreadable_entries(root: Path, *, skip_git: bool = False, limit: int = 20) -> list[str]:
    """Paths the host user cannot read (typically created in the container by a
    non-root user, hence owned by a subordinate UID). Symlinks are not followed."""
    root = Path(root)
    found: list[str] = []
    def onerror(exc):
        found.append(os.path.relpath(exc.filename, root) if getattr(exc, "filename", None) else str(exc))
    for current, dirs, files in os.walk(root, onerror=onerror, followlinks=False):
        if skip_git and Path(current) == root:
            dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            p = os.path.join(current, name)
            try:
                if stat.S_ISREG(os.lstat(p).st_mode) and not os.access(p, os.R_OK):
                    found.append(os.path.relpath(p, root))
            except OSError:
                found.append(os.path.relpath(p, root))
        if len(found) >= limit:
            break
    return found[:limit]


def require_readable(root: Path, env_name: str, *, skip_git: bool = False) -> None:
    """Refuse to produce an incomplete archive; silently dropping files is data loss."""
    bad = unreadable_entries(root, skip_git=skip_git)
    if bad:
        shown = ", ".join(bad[:5]) + (" ..." if len(bad) > 5 else "")
        raise c.SandboxError(
            f"{len(bad)}{'+' if len(bad) >= 20 else ''} workspace entries are not readable by the host user "
            f"(usually created inside the container by a non-root user): {shown}. "
            f"Make them readable first, e.g.: opencode-sandbox exec {env_name} -- chmod -R a+rX /workspace")


def _parts(rel: str) -> tuple[str, ...]:
    p = PurePosixPath(rel)
    if not rel or p.is_absolute() or any(part in ("", ".", "..") for part in rel.split("/")):
        raise c.SandboxError(f"Unsafe workspace path: {rel!r}")
    return p.parts


def read_file(root: Path, rel: str, *, limit: int | None = None) -> tuple[bytes, int]:
    """Read a regular file below ``root`` without following any symlink.

    Each component is opened relative to its parent with O_NOFOLLOW, so a
    concurrent swap of a directory for a symlink cannot redirect the read.
    Returns (content, permission bits).
    """
    parts = _parts(rel)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            try:
                nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except OSError as exc:
                raise c.SandboxError(f"Unsafe or missing parent for {rel!r}: {exc.strerror}") from exc
            os.close(fd)
            fd = nfd
        try:
            ffd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        except OSError as exc:
            raise c.SandboxError(f"Cannot read {rel!r} safely: {exc.strerror}") from exc
        try:
            st = os.fstat(ffd)
            if not stat.S_ISREG(st.st_mode):
                raise c.SandboxError(f"Not a regular file: {rel!r}")
            if limit is not None and st.st_size > limit:
                raise c.SandboxError(f"File exceeds size limit: {rel!r}")
            chunks = []
            while chunk := os.read(ffd, 1024 * 1024):
                chunks.append(chunk)
            return b"".join(chunks), stat.S_IMODE(st.st_mode)
        finally:
            os.close(ffd)
    finally:
        os.close(fd)
