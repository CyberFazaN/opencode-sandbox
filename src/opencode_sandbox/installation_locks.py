"""Early stdlib-only installation leases, before data/environment/base guards (D-056).

One persistent inode per canonical Python prefix, independent of all product/XDG overrides.
Normal entry points retain a shared lease until process exit, including worker shutdown. The
exclusive guard is an internal prerequisite, NOT an updater or permission to mutate. No upgrade,
verification bypass, timeout/retry loop, lock-file repair, unlink or override-dependent fallback.
Older managers, library callers and arbitrary external pipx/Docker do not honor this protocol.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
import stat
import sys
import threading
from contextlib import ExitStack, contextmanager
from pathlib import Path

_TMP = Path('/tmp')  # not tempfile, HOME, XDG_RUNTIME_DIR or an environment setting
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_MUTEX = threading.Lock()
_LEASE = None
_OPEN = set()


class Error(RuntimeError):
    """Safe static bootstrap errors; no core/Typer import required to refuse startup."""


def identity(prefix=None):
    """Stable across replacement, not keyed by the interpreter binary or a disposable inode."""
    path = Path(sys.prefix if prefix is None else prefix)
    if not path.is_absolute(): raise Error('Installation prefix must be absolute')
    return str(path.resolve())


def _same(fd, parent, name):
    opened, named = os.fstat(fd), os.stat(name, dir_fd=parent, follow_symlinks=False)
    if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
        raise Error('Installation lock path changed; refusing a split lock namespace')


def _ordered():
    # Check loaded modules only: importing the application here would defeat early exclusion.
    for name, check in (('core', 'locks_held'), ('base_locks', 'held')):
        module = sys.modules.get('opencode_sandbox.' + name)
        if module is not None and getattr(module, check)():
            raise Error('Lock order violation: installation access must precede data/environment/base guards')


class _Guard:
    def __init__(self, prefix, mode):
        self.prefix = identity(prefix)
        self.stack = ExitStack()
        try:
            parent = os.open(_TMP, _DIRECTORY)
            self.stack.callback(os.close, parent)
            info = os.fstat(parent)
            if info.st_uid not in (0, os.getuid()) or (info.st_mode & 0o022 and
                    not (info.st_uid == 0 and info.st_mode & stat.S_ISVTX)):
                raise Error('Unsafe installation lock parent directory')
            directory_name = f'opencode-sandbox-locks-{os.getuid()}'
            try: os.mkdir(directory_name, 0o700, dir_fd=parent)
            except FileExistsError: pass
            directory = os.open(directory_name, _DIRECTORY, dir_fd=parent)
            self.stack.callback(os.close, directory)
            info = os.fstat(directory)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise Error('Unsafe installation lock directory: expected own UID and mode 0700')
            key = hashlib.sha256(os.fsencode(self.prefix)).hexdigest()
            name = f'installation-{key}.lock'
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                         0o600, dir_fd=directory)
            self.stack.callback(os.close, fd)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() \
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
                raise Error('Unsafe installation lock file: expected private own-user regular file with one link')
            try: fcntl.flock(fd, mode | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Error('Manager installation busy: another supported manager or exclusive operation is using it; '
                            'close other instances and retry. Never delete the lock file.') from None
            self.paths = ((directory, parent, directory_name), (fd, directory, name))
            self.check()
        except BaseException:
            self.stack.close()
            raise
        _OPEN.add(self)

    def check(self):
        for fd, parent, name in self.paths: _same(fd, parent, name)

    def close(self):
        # Close, never LOCK_UN: a fork copy must not unlock the parent's open file description.
        self.stack.close()
        _OPEN.discard(self)


def acquire_usage():
    """Idempotent process-lifetime lease; deliberately no release-on-main-return window.

    Descriptor closure at process exit comes after non-daemon worker/thread-pool shutdown.
    There is no in-process shared-to-exclusive conversion or public early-release function.
    """
    global _LEASE
    with _MUTEX:
        try:
            if _LEASE is not None:
                if _LEASE.prefix != identity(): raise Error('Running installation identity changed')
                _LEASE.check()
                return
            _ordered()
            _LEASE = _Guard(None, fcntl.LOCK_SH)
        except OSError as exc:
            raise Error('Cannot safely open installation lock namespace; no paths were repaired') from exc


@contextmanager
def exclusive(prefix=None):
    """Non-waiting external exclusion. Any live shared lease, including our own, refuses it.

    Caller must separately prove consent, identity, independence, terminal restoration and
    verification/recovery before any future replacement; none is established by this guard.
    """
    with _MUTEX:
        try:
            _ordered()
            guard = _Guard(prefix, fcntl.LOCK_EX)
        except OSError as exc:
            raise Error('Cannot safely open installation lock namespace; no paths were repaired') from exc
    try: yield
    finally:
        with _MUTEX: guard.close()


def _after_fork():
    global _LEASE, _MUTEX
    for guard in tuple(_OPEN): guard.close()
    _LEASE = None
    _MUTEX = threading.Lock()


# No exec'd helper/client inherits a lease (CLOEXEC). A fork-only child also drops its copies,
# without unlocking the still-running parent; entry into the manager must acquire its own lease.
os.register_at_fork(before=lambda: _MUTEX.acquire(), after_in_parent=lambda: _MUTEX.release(), after_in_child=_after_fork)
