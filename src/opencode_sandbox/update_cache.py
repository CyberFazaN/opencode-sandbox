"""Disposable bounded update evidence, never authoritative metadata or recovery state.

Per-key atomic replacement and optional private source exclusion, no mutation locks or cross-
source transactions. A corrupt/unsafe/unwritable cache is a miss, not permission to repair paths
or block normal operations. Scheduling decisions belong to callers, not this file store.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import secrets
import stat
import time
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime

from . import core as c

LIMIT = 131072
DIRECTORY = "update-cache"


def timestamp(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 < value <= time.time()


def when(value):
    return datetime.fromtimestamp(value, UTC).isoformat(timespec="seconds")


def _name(key):
    return hashlib.sha256(key.encode()).hexdigest() + ".json"


def _invalid_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")


@contextmanager
def _directory(*, create=False):
    # Descriptor-relative access: no following a substituted cache directory/file, no chmod,
    # unlink/repair of someone else's paths. BASE itself is the user's configured data root.
    base = os.open(c.BASE, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        if create:
            try: os.mkdir(DIRECTORY, 0o700, dir_fd=base)
            except FileExistsError: pass
        fd = os.open(DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=base)
        try:
            info = os.fstat(fd)
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise OSError("unsafe cache directory")
            yield fd
        finally: os.close(fd)
    finally: os.close(base)


def read(key):
    try:
        with _directory() as directory:
            fd = os.open(_name(key), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 \
                        or info.st_mode & 0o077 or info.st_size > LIMIT:
                    return {}
                raw = stream.read(LIMIT + 1)
                if len(raw) > LIMIT: return {}
        data = json.loads(raw, parse_constant=_invalid_constant)
        if not isinstance(data, dict) or data.get("format") != 1 or data.get("key") != key:
            return {}
        return data
    except (OSError, ValueError, UnicodeError, RecursionError):
        return {}


def write(key, data, *, durable=False):
    try: raw = json.dumps({**data, "format": 1, "key": key}, allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError): return False
    if len(raw) > LIMIT: return False
    try:
        c.BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
        with _directory(create=True) as directory:
            try:
                existing = os.stat(_name(key), dir_fd=directory, follow_symlinks=False)
                if not stat.S_ISREG(existing.st_mode) or existing.st_uid != os.getuid() \
                        or existing.st_nlink != 1 or existing.st_mode & 0o077:
                    return False
            except FileNotFoundError: pass
            name = ".write-" + secrets.token_hex(12)
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=directory)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
                    if durable:
                        stream.flush()
                        os.fsync(stream.fileno())
                os.replace(name, _name(key), src_dir_fd=directory, dst_dir_fd=directory)
                if durable: os.fsync(directory)
            finally:
                try: os.unlink(name, dir_fd=directory)
                except FileNotFoundError: pass
    except OSError:
        return False  # disposable evidence, not the result of an install/verification
    return True


class Unavailable(OSError):
    """No safe persistent source coordination; automatic requests must fail closed."""


@contextmanager
def source_lock(key, *, timeout=10):
    """Only metadata requests belong inside this guard, never Docker or mutation locks.

    Persistent lock inodes are never removed/repaired. Each thread/process opens its own file
    description; no-follow/ownership/link/mode and namespace identity checks prevent split locks.
    """
    from . import runtime_identity as rid
    with ExitStack() as stack:
        try:
            c.BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
            directory = stack.enter_context(_directory(create=True))
            name = _name(key) + ".lock"
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         0o600, dir_fd=directory)
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 \
                    or stat.S_IMODE(info.st_mode) != 0o600:
                raise OSError("unsafe source lock")
        except OSError as exc:
            raise Unavailable("Discovery scheduling storage unavailable") from exc
        deadline, waited = time.monotonic() + timeout, False
        while True:
            cancelled = (c._RUNTIME_FEEDBACK.get() or {}).get("cancelled")
            if cancelled and cancelled(): raise rid.Cancelled()
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                waited = True
                if time.monotonic() >= deadline: raise c.SandboxError("Discovery source busy; try Check later") from None
                time.sleep(.02)
            except OSError as exc:
                raise Unavailable("Discovery source exclusion unavailable") from exc
        try:
            with _directory() as current:
                opened, named = os.fstat(directory), os.fstat(current)
                if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino): raise OSError("source directory changed")
            named = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if (info.st_dev, info.st_ino) != (named.st_dev, named.st_ino): raise OSError("source lock changed")
        except OSError as exc:
            raise Unavailable("Discovery scheduling storage changed") from exc
        yield waited


def evidence(value, source, identity):
    return {"value": value, "source": source, "at": time.time(), "identity": identity}


def observation(data, source, identity=None):
    item = data.get("success")
    if not isinstance(item, dict) or item.get("source") != source or not timestamp(item.get("at")) \
            or not isinstance(item.get("value"), str) or not isinstance(item.get("identity"), dict):
        return None
    if identity is not None and item["identity"] != identity: return None
    return item


def attempt(data):
    item = data.get("attempt")
    if not isinstance(item, dict) or not timestamp(item.get("at")) or type(item.get("ok")) is not bool:
        return None
    if not item["ok"] and not isinstance(item.get("error"), str): return None
    return item
