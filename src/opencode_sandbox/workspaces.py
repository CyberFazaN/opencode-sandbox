"""Where an environment's /workspace lives (D-012).

`managed`: `<environment dir>/workspace`, created, copied into and deleted by the manager.
`direct` (opt-in, not recommended): an existing host directory of the user, bind-mounted as it is.
A direct directory is externally owned: no manager code deletes, chowns, chmods, restores into
or walks-and-modifies it. Deletion code only ever computes the managed path (`managed_path`) and
never asks this module for a direct one. The only writes are the preflight's own marker file.
"""
from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

from . import core as c

MANAGED, DIRECT = "managed", "direct"
LABEL = "Not recommended — direct access to host files"
# Equal to or inside one of these: system trees are never a project directory.
SYSTEM_TREES = tuple(Path(p) for p in ("/bin", "/boot", "/dev", "/etc", "/lib", "/lib32", "/lib64", "/opt", "/proc",
                                        "/root", "/run", "/sbin", "/srv", "/sys", "/usr", "/var"))
PREFLIGHT_PREFIX = ".ocs-preflight-"
_SPECIAL = {stat.S_IFSOCK: "socket", stat.S_IFCHR: "device", stat.S_IFBLK: "device"}


def info(m: dict) -> dict:
    """The validated `workspace` record ({mode, path}); malformed records never default to managed."""
    w = m.get("workspace")
    if not isinstance(w, dict) or set(w) != {"mode", "path"}:
        raise c.SandboxError("Invalid workspace record in metadata")
    if w["mode"] == MANAGED and w["path"] is None:
        return w
    if w["mode"] == DIRECT and isinstance(w["path"], str) and os.path.isabs(w["path"]) \
            and os.path.normpath(w["path"]) == w["path"]:
        return w
    raise c.SandboxError("Invalid workspace record in metadata")


def is_direct(m: dict) -> bool:
    return info(m)["mode"] == DIRECT


def managed_path(m: dict) -> Path:
    """The manager-owned workspace directory (also for deletion; never a direct path)."""
    return c.env_dir(m["id"]) / "workspace"


def path(m: dict) -> Path:
    """The host directory mounted at /workspace."""
    w = info(m)
    return Path(w["path"]) if w["mode"] == DIRECT else managed_path(m)



def refuse_output_inside(destination, what: str) -> None:
    """Exports, change bundles and backups are host data: a destination inside any environment's
    workspace would make them agent-writable, and a backup would archive itself."""
    target = Path(destination).expanduser().resolve()
    for other in c.all_envs():
        try:
            ws = path(other).resolve()
        except (c.SandboxError, OSError):
            continue
        if target == ws or ws in target.parents:
            raise c.SandboxError(f"Refusing to write {what} into {target}: it is inside the workspace of "
                                 f"{other['name']}, where the agent can change it. Choose a directory outside "
                                 "every workspace")

def describe(m: dict) -> str:
    """One line for the CLI and the dashboard."""
    w = info(m)
    if w["mode"] == DIRECT:
        return f"DIRECT host folder {w['path']} ({LABEL})"
    return f"managed copy of {m['source']} (the original is not mounted)" if m.get("source") else "managed, started empty"


def _inside(p: Path, root: Path) -> bool:
    return p == root or root in p.parents


def _protected_roots() -> list[Path]:
    """Directories a direct workspace may not be, contain, or lie inside."""
    roots = [c.BASE, c.CONFIG]
    if os.environ.get("XDG_RUNTIME_DIR"):
        roots.append(Path(os.environ["XDG_RUNTIME_DIR"]))
    root = c.docker_root() if c._ENDPOINT else None
    if root is not None:
        roots.append(root)
    out = []
    for r in roots:
        try:
            out.append(Path(r).expanduser().resolve())
        except OSError:
            continue
    return out


def check_direct(requested, *, scan=True) -> Path:
    """Host-side checks; return the resolved directory or raise with every reason found."""
    try:
        target = Path(requested).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise c.SandboxError(f"Direct workspace not accessible: {requested} ({getattr(exc, 'strerror', None) or exc})") from None
    st = os.lstat(target)
    if not stat.S_ISDIR(st.st_mode):
        raise c.SandboxError(f"Direct workspace must be a directory: {target}")
    uid, problems = os.getuid(), []
    home = Path.home().resolve()
    if target == Path(target.anchor):
        problems.append("it is the root directory")
    if any(_inside(target, t) for t in SYSTEM_TREES):
        problems.append("it is a system directory")
    if _inside(home, target):
        problems.append("it is your home directory or contains it")
    for root in _protected_roots():
        if _inside(target, root) or _inside(root, target):
            problems.append(f"it is, contains or lies inside {root} (manager data, configuration or runtime files)")
    if any(part.startswith(".") for part in target.parts[1:]):
        problems.append("a path component is hidden (dot directories hold configuration and credentials)")
    if st.st_uid != uid:
        problems.append(f"it is owned by uid {st.st_uid}, not by you (uid {uid})")
    seen_own = False
    for parent in reversed(target.parents):
        pst = os.lstat(parent)
        if pst.st_uid == uid:
            seen_own = True
        elif pst.st_uid != 0:
            problems.append(f"{parent} is owned by another user (uid {pst.st_uid})")
        elif seen_own:
            problems.append(f"{parent} is owned by root inside your own directories")
        others = pst.st_mode & stat.S_IWOTH or (pst.st_mode & stat.S_IWGRP and pst.st_gid != os.getgid())
        if others and not pst.st_mode & stat.S_ISVTX:
            problems.append(f"{parent} is writable by other users (they could replace the directory)")
    if problems:
        raise c.SandboxError(f"Refusing direct workspace {target}: " + "; ".join(dict.fromkeys(problems)))
    if scan:
        _scan(target, st.st_dev)
    return target


def recheck(m: dict) -> Path:
    """Before Docker creates a mount again: the recorded directory must still pass the checks and
    must not have become a symlink to somewhere else (Docker would follow it)."""
    recorded = Path(info(m)["path"])
    target = check_direct(recorded)
    if target != recorded:
        raise c.SandboxError(f"Direct workspace {recorded} now resolves to {target}; refusing to mount a different "
                             "directory. Restore the original directory or create a new environment")
    return target


def _scan(target: Path, device: int, limit: int = 5) -> None:
    """Sockets and device nodes would give the container access to host services; a nested
    mount would bring another filesystem along (Docker bind mounts are recursive)."""
    found = []
    stack = [target]
    while stack and len(found) < limit:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            raise c.SandboxError(f"Cannot read {directory} while checking the direct workspace: {exc.strerror}") from None
        for entry in entries:
            st = entry.stat(follow_symlinks=False)
            kind = _SPECIAL.get(stat.S_IFMT(st.st_mode))
            rel = Path(entry.path).relative_to(target)
            if kind:
                found.append(f"{rel} ({kind})")
            elif stat.S_ISDIR(st.st_mode):
                if st.st_dev != device:
                    found.append(f"{rel} (another mounted filesystem)")
                else:
                    stack.append(Path(entry.path))
    if found:
        raise c.SandboxError(f"Refusing direct workspace {target}: it contains " + ", ".join(found[:limit])
                             + ("; …" if len(found) >= limit else ""))


def overlapping(target: Path, envs, own_id=None) -> list[str]:
    """Names of other environments whose direct workspace is, contains or lies inside `target`."""
    out = []
    for other in envs:
        if other["id"] == own_id:
            continue
        try:
            w = info(other)
        except c.SandboxError:
            continue
        if w["mode"] == DIRECT and (_inside(target, Path(w["path"])) or _inside(Path(w["path"]), target)):
            out.append(other["name"])
    return out


def _ours(p: Path, token: str | None = None) -> bool:
    """A preflight marker written by this manager: regular file, ours, exact content."""
    try:
        st = os.lstat(p)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_size > 64:
            return False
        content = p.read_text()
    except (OSError, UnicodeError):
        return False
    name_token = p.name[len(PREFLIGHT_PREFIX):]
    return content == f"ocs-preflight {name_token}\n" and (token is None or name_token == token)


def remove_stale_markers(target: Path) -> list[str]:
    """Remove markers left by an interrupted preflight; return markers that are not provably ours."""
    foreign = []
    for p in target.glob(PREFLIGHT_PREFIX + "*"):
        if len(p.name) == len(PREFLIGHT_PREFIX) + 16 and _ours(p):
            p.unlink()
        else:
            foreign.append(p.name)
    return foreign


def preflight(target: Path, image: str, *, user: str | None = None) -> dict:
    """Write, check and remove one marker file through a throw-away container of the real image
    with the execution identity the environment's container will have (no `--user`; `user` exists
    for tests of a mismatching identity). Refuses unless the file appears on the host as yours."""
    c.verify_runtime()  # D-003: the daemon must be verified, so container root maps to this user
    stale = remove_stale_markers(target)
    if stale:
        raise c.SandboxError(f"{target} contains files named like preflight markers that are not the manager's: "
                             + ", ".join(stale) + "; remove or rename them first")
    token = secrets.token_hex(8)
    marker = target / (PREFLIGHT_PREFIX + token)

    def container(script):
        args = ["run", "--rm", "--network", "none", "--security-opt", "no-new-privileges:true",
                *c.helper_labels("preflight"), "--label", "org.opencode-sandbox.preflight=true",
                "--mount", f"type=bind,src={target},dst=/workspace", "--workdir", "/workspace"]
        if user is not None:
            args += ["--user", user]
        return c.docker(*args, "--entrypoint", "sh", image, "-c", script, "ocs-preflight", token,
                        capture=True, check=False)

    REMOVE = 'rm -f -- "/workspace/.ocs-preflight-$1"'
    write = container('umask 022 && printf "ocs-preflight %s\\n" "$1" > "/workspace/.ocs-preflight-$1"')
    try:
        if write.returncode:
            raise c.SandboxError(f"Preflight: the container could not write to the directory: {(write.stderr or '').strip()[:300]}")
        try:
            st = os.lstat(marker)
        except FileNotFoundError:
            raise c.SandboxError("Preflight: the file written in the container is not visible on the host") from None
        if (st.st_uid, st.st_gid) != (os.getuid(), os.getgid()):
            raise c.SandboxError(f"Preflight: files written in the container belong to host uid:gid {st.st_uid}:{st.st_gid}, "
                                 f"not to you ({os.getuid()}:{os.getgid()}); this identity mapping is not supported")
        if not _ours(marker, token):
            raise c.SandboxError("Preflight: the file written in the container has unexpected content")
        remove = container(REMOVE)
        if remove.returncode or os.path.lexists(marker):
            raise c.SandboxError(f"Preflight: the container could not delete its file: {(remove.stderr or '').strip()[:300]}")
    finally:
        if os.path.lexists(marker):
            if _ours(marker, token):
                marker.unlink()
            else:  # e.g. written under another identity: the same identity removes it
                container(REMOVE)
                if os.path.lexists(marker):
                    raise c.SandboxError(f"Preflight left {marker}; remove it manually")
    return {"path": str(target), "image": image, "uid": os.getuid(), "gid": os.getgid()}
