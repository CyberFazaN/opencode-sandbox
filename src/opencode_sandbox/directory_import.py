"""Explicit, literal directory copy. The source is read-only and never passed to Git."""
import os
import shutil
import stat
from contextlib import contextmanager
from pathlib import Path

from . import core as c
from . import workspaces

_ENTRY = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
_DIR = _ENTRY | os.O_DIRECTORY


def check_source(source: Path) -> None:
    """Reject broad/sensitive roots and any overlap with the import destination's data tree."""
    roots = [c.BASE, c.CONFIG, Path.home() / '.local/share/docker']
    if runtime := os.environ.get('XDG_RUNTIME_DIR'):
        roots.append(Path(runtime))
    if data := os.environ.get('XDG_DATA_HOME'):
        roots.append(Path(data) / 'docker')
    for raw in roots:
        root = raw.expanduser().resolve()
        if source == root or source in root.parents or root in source.parents:
            raise c.SandboxError('Refusing full directory import overlapping manager, Docker or runtime data')
    if any(source == root or root in source.parents for root in workspaces.SYSTEM_TREES):
        raise c.SandboxError('Refusing full directory import of a system directory')
    if any(part.startswith('.') for part in source.parts[1:]):
        raise c.SandboxError('Refusing a hidden directory as the full import root; select a project directory')


@contextmanager
def _open(name, flags, *, parent=None):
    fd = os.open(name, flags, dir_fd=parent)
    try:
        yield fd
    finally:
        os.close(fd)


def _mount_id(fd):
    # st_dev alone does not detect a bind mount of another directory on the same filesystem.
    with open(f'/proc/self/fdinfo/{fd}', encoding='ascii') as info:
        for line in info:
            if line.startswith('mnt_id:'):
                return line.split()[1]
    raise c.SandboxError('Cannot verify mount boundaries for the full directory import')


def _metadata(dst, st):
    # Copy ordinary permission bits only. In particular, do not reproduce setuid/setgid or ACLs.
    if not stat.S_ISLNK(st.st_mode):
        dst.chmod(st.st_mode & 0o777)
    os.utime(dst, ns=(st.st_atime_ns, st.st_mtime_ns), follow_symlinks=False)


def _copy_dir(handle, destination, mount):
    with _open('.', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC, parent=handle) as directory:
        for name in os.listdir(directory):
            dst = destination / name
            # Pin the entry before examining its type. Never open a device or FIFO for reading,
            # nor reopen a mutable source path after checking it.
            with _open(name, _ENTRY, parent=directory) as child:
                st = os.fstat(child)
                if _mount_id(child) != mount:
                    raise c.SandboxError('Full directory import refuses nested mounts')
                if stat.S_ISDIR(st.st_mode):
                    dst.mkdir(mode=0o700)
                    _copy_dir(child, dst, mount)
                elif stat.S_ISREG(st.st_mode):
                    with open(f'/proc/self/fd/{child}', 'rb') as src, dst.open('xb') as out:
                        shutil.copyfileobj(src, out)
                elif stat.S_ISLNK(st.st_mode):
                    dst.symlink_to(os.readlink('', dir_fd=child))
                else:
                    raise c.SandboxError('Full directory import refuses special files (such as sockets, FIFOs and devices)')
                _metadata(dst, st)


def copy(source: Path, destination: Path):
    # Resolve at validation, then open each canonical component without following a replacement link.
    fd = os.open(source.anchor, _DIR)
    try:
        for part in source.parts[1:]:
            child = os.open(part, _DIR, dir_fd=fd)
            os.close(fd)
            fd = child
        st = os.fstat(fd)
        destination.mkdir(mode=0o700)
        _copy_dir(fd, destination, _mount_id(fd))
        _metadata(destination, st)
    except (OSError, RecursionError) as exc:
        detail = getattr(exc, 'strerror', None) or 'directory nesting exceeds the supported depth'
        raise c.SandboxError(f'Full directory import failed: {detail}') from None
    finally:
        os.close(fd)


def prepare_cleanup(destination):
    """Make a new, unpublished copy removable even if source directories were read-only."""
    if not destination.is_dir():
        return
    destination.chmod(stat.S_IMODE(destination.stat().st_mode) | 0o700)
    for root, dirs, _ in os.walk(destination, followlinks=False):
        for name in dirs:
            path = Path(root) / name
            if not path.is_symlink():
                path.chmod(stat.S_IMODE(path.stat().st_mode) | 0o700)
