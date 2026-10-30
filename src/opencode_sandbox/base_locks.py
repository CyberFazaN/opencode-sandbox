"""Daemon-wide base guards (D-056), independent of product and XDG path overrides.

One fixed Linux temporary root avoids runtime-directory/fallback split locks. Never repair,
unlink or replace these files: another process may still hold the inode. Older managers and
manual Docker commands do not participate in this advisory protocol.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import time
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from pathlib import Path

from . import core as c
from . import distros

_TMP = Path("/tmp")  # deliberately not tempfile, HOME, TMPDIR or XDG_RUNTIME_DIR
_HELD = ContextVar("base_guards", default=())
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def held():
    return bool(_HELD.get())


def _same(fd, parent, name):
    opened, named = os.fstat(fd), os.stat(name, dir_fd=parent, follow_symlinks=False)
    if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
        raise c.SandboxError("Base lock path changed; refusing a split lock namespace")


@contextmanager
def _directory():
    with ExitStack() as stack:
        parent = os.open(_TMP, _DIRECTORY)
        stack.callback(os.close, parent)
        info = os.fstat(parent)
        # The host /tmp must be root-owned and sticky if writable by others. A private own-user
        # root is also safe (used by isolated tests); no permission or symlink takeover.
        if info.st_uid not in (0, os.getuid()) or (info.st_mode & 0o022 and
                not (info.st_uid == 0 and info.st_mode & stat.S_ISVTX)):
            raise c.SandboxError("Unsafe base lock parent directory")
        name = f"opencode-sandbox-locks-{os.getuid()}"
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
        except FileExistsError:
            pass
        directory = os.open(name, _DIRECTORY, dir_fd=parent)
        stack.callback(os.close, directory)
        info = os.fstat(directory)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise c.SandboxError("Unsafe base lock directory: expected own UID and mode 0700")
        _same(directory, parent, name)
        yield parent, name, directory


@contextmanager
def lock(distro, phase, *, timeout=30.0):
    """Build before publication; no data/environment locks may be acquired inside either.

    The endpoint is the pinned canonical endpoint from successful daemon verification, never a
    context alias or daemon PID. Descriptors are non-inheritable and each acquisition opens its
    own file description, so threads also exclude one another.
    """
    d = distros.get(distro)
    if phase not in ("build", "publication"):
        raise c.SandboxError("Invalid base lock phase")
    level = (0 if phase == "build" else 1, d.id)
    previous = _HELD.get()
    if previous and level <= previous[-1]:
        raise c.SandboxError("Base lock order violation: build then publication, distributions in stable order")
    endpoint = c.docker_endpoint()
    key = hashlib.sha256(json.dumps([os.getuid(), endpoint, d.id]).encode()).hexdigest()
    name = f"{key}-{phase}.lock"
    with ExitStack() as stack:
        try:
            parent, directory_name, directory = stack.enter_context(_directory())
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                         0o600, dir_fd=directory)
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() \
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
                raise c.SandboxError("Unsafe base lock file: expected private own-user regular file with one link")
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise c.SandboxError(f"Base image busy: {d.id} ({phase} lock timeout)") from None
                    time.sleep(0.05)
            _same(directory, parent, directory_name)
            _same(fd, directory, name)
        except OSError as exc:
            raise c.SandboxError(f"Cannot safely open base lock namespace: {exc.strerror}") from exc
        token = _HELD.set((*previous, level))
        try:
            yield
        finally:
            _HELD.reset(token)
            fcntl.flock(fd, fcntl.LOCK_UN)
