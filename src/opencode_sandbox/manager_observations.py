"""Shared stdlib local observations, also frozen into the NON-MUTATING helper.

Replay approved file hashes/routes under existing exclusion without importing the application.
NOT fresh classification, external dependency/tool execution, published-source/network policy
validation, replacement authority or recovery. The separate manager_execution gate does fresh
diagnostics. There is no command/callback/environment executor here.
"""
import hashlib
import json
import os
import re
import stat
import time
from pathlib import Path

LIMIT = 1048576
RECORD_LIMIT = 131072
NAME = 'opencode-sandbox'
CONTEXT = ('HOME', 'PATH', 'XDG_CONFIG_HOME', 'XDG_CONFIG_DIRS', 'XDG_DATA_HOME', 'PIPX_BIN_DIR',
           'PIPX_COMPLETION_DIR', 'PIPX_DEFAULT_PYTHON', 'PIPX_HOME', 'PIPX_MAN_DIR', 'PIPX_SHARED_LIBS')
FAILURE = 'Approved local manager observations changed or unavailable; no installation was changed'


class Refused(RuntimeError):
    pass


def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value: raise Refused('Ambiguous local observation data')
        value[key] = item
    return value


def _invalid(value): raise Refused('Non-finite local observation data')


def parse(raw): return json.loads(raw, object_pairs_hook=_unique, parse_constant=_invalid)


def _path(value):
    if not isinstance(value, str) or not value or not Path(value).is_absolute() or any(not ch.isprintable() for ch in value):
        raise Refused('Invalid local observation path')
    return Path(value)


def route(value, *, deadline=None):
    """Exact shared route semantics; directory timestamps are not replacement identity."""
    path = _path(str(value))
    pending, current, rows, links = list(path.parts[1:]), Path('/'), [], 0
    while True:
        if deadline is not None and time.monotonic() >= deadline: raise Refused('Local observations timed out')
        try: info = current.lstat()
        except FileNotFoundError:
            rows.append((str(current), 'missing', tuple(pending)))
            return rows
        kind = stat.S_IFMT(info.st_mode)
        if kind not in (stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK):
            raise Refused('Manager review encountered a special path; manual review required')
        if info.st_uid not in (0, os.getuid()) or (not stat.S_ISLNK(info.st_mode) and info.st_mode & 0o022
                and not (stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and info.st_mode & stat.S_ISVTX)):
            raise Refused('Manager review paths are not controlled; manual review required')
        extra = () if stat.S_ISDIR(info.st_mode) else (info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)
        link = os.readlink(current) if stat.S_ISLNK(info.st_mode) else None
        rows.append((str(current), kind, info.st_dev, info.st_ino, info.st_uid, info.st_mode, extra, link))
        if link is not None:
            links += 1
            if links > 40: raise Refused('Manager review has a cyclic or excessive symlink route')
            target = Path(link)
            pending = list(target.parts[1:] if target.is_absolute() else target.parts) + pending
            current = Path('/') if target.is_absolute() else current.parent
            continue
        if not pending: return rows
        part = pending.pop(0)
        current = current.parent if part == '..' else current / part


def read_record(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022 or info.st_size > RECORD_LIMIT:
            raise Refused('Local observation record is unsafe or too large')
        raw = stream.read(RECORD_LIMIT + 1)
    if len(raw) > RECORD_LIMIT: raise Refused('Local observation record exceeds its bound')
    return raw


def critical(evidence):
    prefix, dist = _path(evidence['venv']), _path(evidence['distribution'])
    module = _path(evidence['module'])
    if str(prefix.resolve()) != str(prefix) or prefix.name != NAME or prefix.parent.name != 'venvs' \
            or not dist.is_relative_to(prefix) or dist.resolve() != dist or not dist.name.endswith('.dist-info') \
            or module != dist.parent / 'opencode_sandbox/__init__.py' or module.resolve() != module:
        raise Refused('Local observation installation boundary is invalid')
    return [prefix / 'pipx_metadata.json', prefix / 'pyvenv.cfg', module, prefix / 'bin/opencode-sandbox',
            *(dist / name for name in ('direct_url.json', 'METADATA', 'entry_points.txt', 'RECORD'))]


def _shape(value, prefix, origin):
    required = {'format', 'fixture', 'origin', 'prefix', 'version', 'identity', 'binding', 'target', 'context'}
    if not isinstance(value, dict) or set(value) != required or type(value['format']) is not int or value['format'] != 1 \
            or value['fixture'] is not True or type(value['origin']) is not int or value['origin'] != origin \
            or value['prefix'] != prefix or not isinstance(value['version'], str) or len(value['version']) > 80 \
            or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value['version']) \
            or not isinstance(value['binding'], str) or len(value['binding'].encode()) > 524288 \
            or not isinstance(value['target'], dict) or 'at' not in value['target'] \
            or not isinstance(value['context'], dict) or set(value['context']) != set(CONTEXT) \
            or any(item is not None and not isinstance(item, str) for item in value['context'].values()):
        raise Refused('Invalid approved local observation input')
    target = {key: item for key, item in value['target'].items() if key != 'at'}
    if value['identity'] != digest({'source': target, 'binding': value['binding'], 'owner': origin}):
        raise Refused('Approved local observation identity changed')
    binding = parse(value['binding'])
    if not isinstance(binding, dict) or set(binding) != {'installation', 'tools', 'records', 'routes', 'context', 'network'} \
            or binding['network'] != 'public-defaults' or binding['context'] != digest(value['context']) \
            or binding['installation']['version'] != value['version'] or binding['installation']['evidence']['venv'] != prefix:
        raise Refused('Approved local observation binding changed')
    records = critical(binding['installation']['evidence'])
    if not isinstance(binding['records'], dict) or set(binding['records']) != {str(path) for path in records} \
            or any(not isinstance(item, str) or not re.fullmatch('[0-9a-f]{64}', item) for item in binding['records'].values()) \
            or not isinstance(binding['routes'], dict) or not 0 < len(binding['routes']) <= 2048 \
            or not set(binding['records']) <= set(binding['routes']):
        raise Refused('Invalid approved local observation inventory')
    for path in binding['routes']: _path(path)
    return binding, records


def capsule(*, origin, prefix, version, identity, binding, target, context):
    """Private bounded validation input only, not authoritative consent/recovery or installer env."""
    value = {'format': 1, 'fixture': True, 'origin': origin, 'prefix': prefix, 'version': version,
             'identity': identity, 'binding': binding, 'target': target, 'context': context}
    raw = (canonical(value) + '\n').encode()
    if len(raw) > LIMIT: raise Refused('Approved local observation input exceeds its bound')
    _shape(value, prefix, origin)
    return raw


def load(locks, directory, expected, *, prefix, origin):
    """Read the identity-bound private capsule under independently proved own exclusion."""
    with locks._verification(prefix) as (witness, owner_fd):
        locks._verify_descriptor(witness, os.getpid(), owner_fd, prefix)
        fd = os.open('review.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 \
                    or info.st_nlink != 1 or info.st_size > LIMIT or [info.st_dev, info.st_ino] != expected['file_identity']:
                raise Refused('Approved local observation input is not private or unchanged')
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT or hashlib.sha256(raw).hexdigest() != expected['sha256']:
            raise Refused('Approved local observation input changed')
        value = parse(raw)
        _shape(value, prefix, origin)
        if value['identity'] != expected['identity']: raise Refused('Approved local observation identity disagrees')
        return value


def validate(locks, directory, expected, *, prefix, origin, deadline):
    """Replay only local observations after origin death; not fresh execution validation.

    Context is bound data, never applied as an execution environment. File I/O is bounded in
    size; deadline checks do not promise preemption of an unresponsive filesystem.
    """
    value = load(locks, directory, expected, prefix=prefix, origin=origin)
    binding, records = _shape(value, prefix, origin)
    for path, observed in binding['routes'].items():
        if canonical(route(path, deadline=deadline)) != canonical(observed): raise Refused(FAILURE)
    for path in records:
        if time.monotonic() >= deadline: raise Refused('Local observations timed out')
        if hashlib.sha256(read_record(path)).hexdigest() != binding['records'][str(path)]: raise Refused(FAILURE)
    for path, observed in binding['routes'].items():
        if canonical(route(path, deadline=deadline)) != canonical(observed): raise Refused(FAILURE)
    return {'ok': True, 'identity': value['identity']}
