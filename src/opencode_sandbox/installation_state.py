"""Stdlib incomplete-update barrier, outside the replaceable pipx venv and discovery caches.

Only lock-owning helpers write it. Normal bootstrap reads it before application dispatch; pending,
unknown or unsafe state fails closed without repair. This is not a migration, installer, process
killer or automatic recovery. Completed operation details remain in their private external record.
"""
import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path

DIRECTORY = '.opencode-sandbox-updates'
FORMAT = 1
LIMIT = 16384
PHASES = {'prepared', 'installing', 'verifying', 'manual-recovery', 'complete'}
RESULTS = {'target-verified', 'previous-verified', 'target-unverified', 'unavailable', 'interrupted'}
SOURCE = 'https://github.com/CyberFazaN/opencode-sandbox.git'
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class Error(RuntimeError):
    pass


def location(prefix):
    prefix = Path(prefix)
    if not prefix.is_absolute() or prefix.name != 'opencode-sandbox' or prefix.parent.name != 'venvs': return None
    key = hashlib.sha256(os.fsencode(str(prefix))).hexdigest()
    return prefix.parent.parent / DIRECTORY / (key + '.json')


def _private(info, *, directory=False):
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600) \
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1):
        raise Error('Unsafe manager installation operation state; no paths were repaired')


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value: raise Error('Ambiguous manager installation operation state')
        value[key] = item
    return value


def _invalid(value): raise Error('Invalid manager installation operation state')


def owner():
    fields = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': os.getpid(), 'uid': os.getuid(), 'start': fields[19],
            'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def alive(identity):
    try:
        if identity['boot'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip(): return False
        path = Path('/proc') / str(identity['pid'])
        return path.stat().st_uid == identity['uid'] and path.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19] == identity['start']
    except FileNotFoundError: return False


def _shape(value, prefix):
    required = {'format', 'prefix', 'operation', 'phase', 'record', 'owner', 'installer', 'target', 'previous', 'result', 'at'}
    if not isinstance(value, dict) or set(value) != required or type(value['format']) is not int or value['format'] != FORMAT \
            or value['prefix'] != str(prefix) or not isinstance(value['operation'], str) \
            or not re.fullmatch('[0-9a-f]{64}', value['operation']) or not isinstance(value['phase'], str) or value['phase'] not in PHASES \
            or value['result'] is not None and (not isinstance(value['result'], str) or value['result'] not in RESULTS) \
            or type(value['at']) not in (int, float) or not math.isfinite(value['at']) or value['at'] <= 0 \
            or not isinstance(value['record'], str) or not Path(value['record']).is_absolute() \
            or Path(value['record']).is_relative_to(prefix) or any(not char.isprintable() for char in value['record']):
        raise Error('Unknown or invalid manager installation operation state; preserved')
    identity = value['owner']
    if not isinstance(identity, dict) or set(identity) != {'pid', 'uid', 'start', 'boot'} \
            or type(identity['pid']) is not int or identity['pid'] <= 0 or type(identity['uid']) is not int or identity['uid'] != os.getuid() \
            or not isinstance(identity['start'], str) or not identity['start'].isdigit() or len(identity['start']) > 24 \
            or not isinstance(identity['boot'], str) or not re.fullmatch('[0-9a-f-]{36}', identity['boot']):
        raise Error('Invalid manager installation operation owner; preserved')
    child = value['installer']
    if child is not None and (not isinstance(child, dict) or set(child) != {'pid', 'start', 'pgid'}
            or type(child['pid']) is not int or child['pid'] <= 0 or type(child['pgid']) is not int or child['pgid'] != child['pid']
            or not isinstance(child['start'], str) or not child['start'].isdigit() or len(child['start']) > 24):
        raise Error('Invalid manager installation child identity; preserved')
    for name in ('target', 'previous'):
        source = value[name]
        if not isinstance(source, dict) or set(source) != {'version', 'tag', 'commit', 'source'} \
                or not isinstance(source['version'], str) or len(source['version']) > 80 \
                or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', source['version']) \
                or source['tag'] != 'v' + source['version'] or source['source'] != SOURCE \
                or not isinstance(source['commit'], str) or not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', source['commit']):
            raise Error('Invalid manager installation source identity; preserved')
    if value['phase'] == 'complete' and (value['installer'] is not None or value['result'] not in ('target-verified', 'previous-verified')):
        raise Error('Unverified manager installation operation cannot be marked complete')
    return value


def read(prefix):
    path = location(prefix)
    if path is None: return None
    directory = None
    try:
        try: directory = os.open(path.parent, _DIRECTORY)
        except FileNotFoundError: return None
        _private(os.fstat(directory), directory=True)
        try: fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
        except FileNotFoundError: return None
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno()); _private(info)
            if info.st_size > LIMIT: raise Error('Manager installation operation state exceeds its bound')
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT: raise Error('Manager installation operation state exceeds its bound')
        return _shape(json.loads(raw, object_pairs_hook=_unique, parse_constant=_invalid), prefix)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise Error('Cannot safely read manager installation operation state; preserved without repair') from None
    finally:
        if directory is not None: os.close(directory)


def check(prefix):
    value = read(prefix)
    if value is not None and value['phase'] != 'complete':
        raise Error('Manager installation update incomplete; normal startup is blocked. '
                    'Inspect the private operation record for independent recovery instructions. '
                    'Do not delete lock or operation-state files.')


def write(prefix, value):
    """Internal: caller must already prove own kernel exclusion; no state reset/repair shortcut."""
    path = location(prefix)
    if path is None: raise Error('Manager operation state requires the recognized pipx installation prefix')
    value = _shape(value, prefix)
    if value['owner'] != owner(): raise Error('Manager operation state writer does not own this process identity')
    previous = read(prefix)
    if previous is None:
        if value['phase'] != 'prepared': raise Error('Manager operation must be prepared before installation')
    elif previous['phase'] != 'complete':
        if previous['operation'] != value['operation']: raise Error('An incomplete manager operation must be recovered first')
        if previous['owner'] != value['owner'] and alive(previous['owner']):
            raise Error('The existing manager operation owner is still alive; no takeover permitted')
        transitions = {'prepared': {'installing', 'manual-recovery', 'complete'},
                       'installing': {'verifying', 'manual-recovery'},
                       'verifying': {'complete', 'manual-recovery'},
                       'manual-recovery': {'verifying', 'manual-recovery', 'installing'}}
        if value['phase'] not in transitions[previous['phase']]: raise Error('Invalid manager installation operation transition')
        if any(value[key] != previous[key] for key in ('record', 'target', 'previous')):
            raise Error('Manager installation operation identities changed; preserved')
    elif value['phase'] != 'prepared' or value['operation'] == previous['operation']:
        raise Error('Completed manager operation is immutable; prepare a new operation')
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    if len(raw) > LIMIT: raise Error('Manager installation operation state exceeds its bound')
    root = os.open(path.parent.parent, _DIRECTORY)
    directory = None
    temporary = '.write-' + os.urandom(16).hex()
    created = False
    try:
        info = os.fstat(root)
        if info.st_uid != os.getuid() or info.st_mode & 0o022: raise Error('Manager pipx home is not controlled by this user')
        try: os.mkdir(DIRECTORY, 0o700, dir_fd=root)
        except FileExistsError: pass
        directory = os.open(DIRECTORY, _DIRECTORY, dir_fd=root); _private(os.fstat(directory), directory=True)
        named = os.stat(DIRECTORY, dir_fd=root, follow_symlinks=False)
        opened = os.fstat(directory)
        if (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino): raise Error('Manager operation directory changed')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
        created = True
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory); os.fsync(root)
    except OSError:
        raise Error('Cannot safely persist manager installation operation state; no repair attempted') from None
    finally:
        if directory is not None:
            if created:
                try: os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError: pass
            os.close(directory)
        os.close(root)
