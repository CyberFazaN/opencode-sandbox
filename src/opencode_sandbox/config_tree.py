"""Stdlib, no-follow whole-tree codec. Also sent verbatim to the isolated volume helper.

Only directories, regular files and symbolic links are supported. Hard-linked regular files
are copied independently. Fingerprints encode length-delimited names/types/modes/data/targets,
not timestamps or host/container ownership. No user code is imported or executed.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import stat
import tarfile

MAX_ENTRIES = 2_000_000
MAX_BYTES = 64 * 1024**3
CHUNK = 1024**2
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class TreeError(RuntimeError):
    pass


class ArchiveSink:
    """Bound archive metadata as well as file bytes, retaining temporary-filesystem headroom."""
    def __init__(self, stream, maximum):
        self.stream, self.maximum, self.written, self.next_check = stream, maximum, 0, 0
        self.fd = None
        try:
            fd = stream.fileno()
            if stat.S_ISREG(os.fstat(fd).st_mode): self.fd = fd
        except (AttributeError, OSError, ValueError):
            pass  # BytesIO and container stdout pipes have no backing filesystem allocation.
        if self.fd is not None:
            space = os.fstatvfs(self.fd)
            self.maximum = min(maximum, max(0, space.f_bavail * space.f_frsize - 128 * 1024**2))

    def write(self, data):
        if self.written + len(data) > self.maximum:
            raise TreeError("Config archive exceeds the transfer byte limit")
        if self.fd is not None and self.written >= self.next_check:
            space = os.fstatvfs(self.fd)
            if space.f_bavail * space.f_frsize - 128 * 1024**2 < len(data):
                raise TreeError("Insufficient temporary archive space; copies preserved")
            self.next_check = self.written + CHUNK
        result = self.stream.write(data)
        self.written += len(data)
        return result


class ConfigTarInfo(tarfile.TarInfo):
    """Bound metadata before stdlib parsing; this is an internal whole-tree wire format."""
    def _proc_pax(self, archive):
        if self.size > 1024**2 or self.type == tarfile.XGLTYPE:
            raise TreeError("Unsupported or oversized config archive metadata")
        return super()._proc_pax(archive)

    def _proc_gnulong(self, archive):
        if self.size > 1024**2:
            raise TreeError("Oversized config archive name metadata")
        return super()._proc_gnulong(archive)

    def _proc_sparse(self, *args):
        raise TreeError("Sparse config archive entries are unsupported")

    _proc_gnusparse_00 = _proc_sparse
    _proc_gnusparse_01 = _proc_sparse
    _proc_gnusparse_10 = _proc_sparse


def identity(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def field(digest, data):
    digest.update(len(data).to_bytes(8, "big"))
    digest.update(data)


def sample(root, archive=None, *, max_bytes=MAX_BYTES, max_entries=MAX_ENTRIES, allow_missing=True):
    """Stable sample and optional tar, using only opened directories and no-follow leaf opens.

    Per-entry checks plus a second complete digest detect ordinary concurrent writers. They
    cannot exclude a malicious same-UID writer or freeze OpenCode; no such claim is made.
    """
    if max_entries < 1:
        raise TreeError("Config tree exceeds the entry limit")
    if archive is not None:
        sink = ArchiveSink(archive, max_bytes + max_entries * 2048 + CHUNK)
        with tarfile.open(fileobj=sink, mode="w|", format=tarfile.PAX_FORMAT) as tf:
            return _sample(root, tf, max_bytes=max_bytes, max_entries=max_entries, allow_missing=allow_missing)
    return _sample(root, None, max_bytes=max_bytes, max_entries=max_entries, allow_missing=allow_missing)


def _sample(root, tf, *, max_bytes, max_entries, allow_missing):
    count, total = 1, 0  # Include the root, matching the archive reader's entry count.
    digest = hashlib.sha256()

    def add(info, source=None):
        tf.addfile(info, source)
        tf.members.clear()  # streaming output must not retain all path/TarInfo objects

    def walk(fd, relative, depth=0):
        nonlocal count, total
        if depth > 512:
            raise TreeError("Config tree is too deeply nested")
        before = os.fstat(fd)
        record(relative, b"d", stat.S_IMODE(before.st_mode))
        if tf:
            info = tarfile.TarInfo(relative or ".")
            info.type, info.mode = tarfile.DIRTYPE, stat.S_IMODE(before.st_mode)
            add(info)
        names = []
        with os.scandir(fd) as entries:
            for entry in entries:
                count += 1  # Reserve pending siblings before descending into child directories.
                if count > max_entries:
                    raise TreeError("Config tree exceeds the entry limit")
                names.append(entry.name)
        for name in sorted(names, key=os.fsencode):
            path = (relative + "/" if relative else "") + name
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            mode = stat.S_IMODE(st.st_mode)
            if stat.S_ISDIR(st.st_mode):
                child = os.open(name, DIR_FLAGS, dir_fd=fd)
                try:
                    if identity(os.fstat(child)) != identity(st):
                        raise TreeError("Config source changed while sampling")
                    walk(child, path, depth + 1)
                finally:
                    os.close(child)
            elif stat.S_ISLNK(st.st_mode):
                target = os.readlink(name, dir_fd=fd)
                record(path, b"l", mode)
                field(digest, os.fsencode(target))
                if tf:
                    info = tarfile.TarInfo(path)
                    info.type, info.mode, info.linkname = tarfile.SYMTYPE, mode, target
                    add(info)
            elif stat.S_ISREG(st.st_mode):
                total += st.st_size
                if total > max_bytes:
                    raise TreeError("Config tree exceeds the transfer byte limit")
                leaf = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                with os.fdopen(leaf, "rb") as source:
                    if identity(os.fstat(source.fileno())) != identity(st):
                        raise TreeError("Config source changed while sampling")
                    record(path, b"f", mode)
                    field(digest, str(st.st_size).encode())
                    remaining = st.st_size
                    # TarFile.addfile reads this bounded reader while hashing the identical bytes.
                    class Reader:
                        def read(self, size):
                            nonlocal remaining
                            data = source.read(min(size, remaining))
                            remaining -= len(data)
                            digest.update(data)
                            return data
                    if tf:
                        info = tarfile.TarInfo(path)
                        info.mode, info.size = mode, st.st_size
                        add(info, Reader())
                    else:
                        reader = Reader()
                        while remaining:
                            if not reader.read(min(CHUNK, remaining)):
                                raise TreeError("Config source changed while sampling")
                    if remaining or source.read(1) or identity(os.fstat(source.fileno())) != identity(st):
                        raise TreeError("Config source changed while sampling")
            else:
                raise TreeError("Unsupported config entry: only directories, regular files and symlinks can be copied")
            if identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) != identity(st):
                raise TreeError("Config source changed while sampling")
        if identity(os.fstat(fd)) != identity(before):
            raise TreeError("Config source changed while sampling")

    def record(path, kind, mode):
        field(digest, os.fsencode(path))
        field(digest, kind)
        field(digest, str(mode).encode())

    try:
        fd = os.open(root, DIR_FLAGS)
    except FileNotFoundError:
        if not allow_missing:
            raise TreeError("Config source is missing; nothing was copied") from None
        record("", b"d", 0o700)
        if tf:
            info = tarfile.TarInfo(".")
            info.type, info.mode = tarfile.DIRTYPE, 0o700
            add(info)
    else:
        try:
            walk(fd, "")
            if identity(os.stat(root, follow_symlinks=False)) != identity(os.fstat(fd)):
                raise TreeError("Config source changed while sampling")
        finally:
            os.close(fd)
    return digest.hexdigest()


def snapshot(root, archive, **limits):
    first = sample(root, archive, **limits)
    if sample(root, **limits) != first:
        raise TreeError("Config source changed while copying; neither side was replaced")
    return first


def unpack(archive, destination, *, max_bytes=MAX_BYTES, max_entries=MAX_ENTRIES):
    """Extract exclusively, never through links. Ownership is the extracting user (container root)."""
    root = os.open(destination, DIR_FLAGS)
    seen, directories, links = set(), [], []
    total = 0

    def parent(parts):
        fd = os.dup(root)
        try:
            for part in parts:
                try: os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError: pass
                child = os.open(part, DIR_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = child
            return fd
        except BaseException:
            os.close(fd)
            raise

    try:
        if os.listdir(root):
            raise TreeError("Config staging directory is not empty")
        with tarfile.open(fileobj=archive, mode="r|*", tarinfo=ConfigTarInfo) as tf:
            for member in tf:
                tf.members.clear()  # streaming transport needs no unbounded historical member list
                name = member.name
                if len(seen) >= max_entries or name in seen:
                    raise TreeError("Config archive has duplicate paths or too many entries")
                seen.add(name)
                parts = name.split("/")
                if name == "." and member.isdir():
                    directories.append(([], member.mode & 0o7777))
                    continue
                if name.startswith("/") or any(p in ("", ".", "..") for p in parts) or "\0" in name \
                        or len(parts) > 512:
                    raise TreeError("Unsafe config archive path")
                if not (member.isdir() or member.isfile() or member.issym()):
                    raise TreeError("Unsupported config archive entry")
                fd = parent(parts[:-1])
                try:
                    if member.isdir():
                        try: os.mkdir(parts[-1], 0o700, dir_fd=fd)
                        except FileExistsError:
                            check = os.open(parts[-1], DIR_FLAGS, dir_fd=fd)
                            os.close(check)
                        directories.append((parts, member.mode & 0o7777))
                    elif member.issym():
                        if not member.linkname or "\0" in member.linkname:
                            raise TreeError("Invalid config symlink")
                        links.append((parts, member.linkname))
                    else:
                        total += member.size
                        if member.size < 0 or total > max_bytes:
                            raise TreeError("Config archive exceeds the transfer byte limit")
                        space = os.fstatvfs(root)
                        if member.size > max(0, space.f_bavail * space.f_frsize - 64 * 1024**2):
                            raise TreeError("Insufficient free space for config staging; original tree preserved")
                        leaf = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                       0o600, dir_fd=fd)
                        with os.fdopen(leaf, "wb") as out, tf.extractfile(member) as source:
                            while data := source.read(CHUNK):
                                out.write(data)
                            out.flush()
                            os.fchmod(out.fileno(), member.mode & 0o7777)
                            os.fsync(out.fileno())
                finally:
                    os.close(fd)
        for parts, target in links:
            fd = parent(parts[:-1])
            try: os.symlink(target, parts[-1], dir_fd=fd)
            finally: os.close(fd)
        for parts, mode in sorted(directories, key=lambda item: len(item[0]), reverse=True):
            fd = parent(parts)
            try:
                os.fchmod(fd, mode)
                os.fsync(fd)
            finally:
                os.close(fd)
        os.fsync(root)
    finally:
        os.close(root)


def exchange(first, second):
    """Atomic Linux same-filesystem directory exchange; unsupported filesystems fail closed."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise TreeError("Atomic config directory exchange is unavailable")
    if rename(-100, os.fsencode(first), -100, os.fsencode(second), 2):
        raise OSError(ctypes.get_errno(), "Atomic config directory exchange failed")


def write_json(path, value):
    """Private durable metadata, outside all user-editable config trees."""
    import tempfile
    parent = os.path.dirname(path)
    fd, temporary = tempfile.mkstemp(prefix=".ocs-", dir=parent)
    try:
        with os.fdopen(fd, "w") as out:
            os.fchmod(out.fileno(), 0o600)
            json.dump(value, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        sync_directory(parent)
    finally:
        if os.path.lexists(temporary): os.unlink(temporary)


def sync_directory(path):
    fd = os.open(path, DIR_FLAGS)
    try: os.fsync(fd)
    finally: os.close(fd)
