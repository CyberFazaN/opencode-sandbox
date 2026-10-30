"""Disposable bounded update evidence, never authoritative metadata or recovery state.

Per-key atomic replacement, no mutation locks or cross-source transactions. A corrupt/unsafe/
unwritable cache is a miss, not permission to repair paths or block normal operations. Scheduling
and in-flight request coordination belong to their callers, not this file store.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import stat
import time
from contextlib import contextmanager
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


def write(key, data):
    try: raw = json.dumps({**data, "format": 1, "key": key}, allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError): return
    if len(raw) > LIMIT: return
    try:
        c.BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
        with _directory(create=True) as directory:
            try:
                existing = os.stat(_name(key), dir_fd=directory, follow_symlinks=False)
                if not stat.S_ISREG(existing.st_mode) or existing.st_uid != os.getuid() \
                        or existing.st_nlink != 1 or existing.st_mode & 0o077:
                    return
            except FileNotFoundError: pass
            name = ".write-" + secrets.token_hex(12)
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=directory)
            try:
                with os.fdopen(fd, "wb") as stream: stream.write(raw)
                os.replace(name, _name(key), src_dir_fd=directory, dst_dir_fd=directory)
            finally:
                try: os.unlink(name, dir_fd=directory)
                except FileNotFoundError: pass
    except OSError:
        return  # disposable evidence, not the result of an install/verification


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
