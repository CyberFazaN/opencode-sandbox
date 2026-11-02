"""Private immutable updater/recovery inputs, independent of the replaceable application.

The operation identity hashes these inputs (including a fresh nonce); authoritative state binds
that identity and path. Neither a discovery cache nor an origin consent receipt is recovery data.
"""
import hashlib
import math
import os
import re
import shlex
import stat
import time
from pathlib import Path

if __package__:
    from . import installation_state as state
    from . import manager_network as policy
    from . import manager_observations as observations
else:
    import installation_state as state
    import manager_network as policy
    import manager_observations as observations

LIMIT = 16384
FORMAT = 1
RECORD = 'operation.json'


class Refused(RuntimeError):
    pass


def directory(path):
    observations.route(path)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        state._private(os.fstat(fd), directory=True)
        return fd
    except BaseException:
        os.close(fd)
        raise


def write(path, value):
    """Create one known private file, never overwrite, repair, clean or dump an environment."""
    raw = (observations.canonical(value) + '\n').encode()
    if len(raw) > LIMIT: raise Refused('Private manager operation record exceeds its bound')
    parent = directory(path.parent)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.fsync(parent)
    finally: os.close(parent)


def _read(path):
    path = observations._path(str(path))
    parent = directory(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno()); state._private(info)
            if info.st_size > LIMIT: raise Refused('Private manager operation record exceeds its bound')
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT: raise Refused('Private manager operation record exceeds its bound')
        value = observations.parse(raw)
    finally: os.close(parent)
    return value


def read(path):
    path = observations._path(str(path))
    value = _read(path)
    required = {'format', 'operation', 'nonce', 'prefix', 'previous', 'target', 'settings', 'python_version',
                'pipx', 'helper_python', 'helper_sha256', 'created', 'home', 'installer_path', 'ceiling'}
    if not isinstance(value, dict) or set(value) != required or type(value['format']) is not int or value['format'] != FORMAT \
            or value['operation'] != observations.digest({key: item for key, item in value.items() if key != 'operation'}) \
            or not isinstance(value['nonce'], str) or not re.fullmatch('[0-9a-f]{64}', value['nonce']) \
            or not isinstance(value['helper_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', value['helper_sha256']) \
            or not isinstance(value['settings'], dict) or set(value['settings']) != policy.KNOWN \
            or type(value['created']) not in (int, float) or not math.isfinite(value['created']) or value['created'] <= 0 \
            or not isinstance(value['python_version'], str) \
            or not re.fullmatch(r'Python [0-9]+\.[0-9]+\.[0-9]+', value['python_version']):
        raise Refused('Unknown or changed manager recovery inputs; preserved')
    prefix = observations._path(value['prefix'])
    for item in (*value['settings'].values(), value['pipx'], value['helper_python'], value['home'], value['ceiling']): observations._path(item)
    if not isinstance(value['installer_path'], str) or not value['installer_path'] or any(not ch.isprintable() for ch in value['installer_path']):
        raise Refused('Manager recovery installer search path is invalid')
    if path.resolve() != path or prefix.resolve() != prefix or Path(value['settings']['PIPX_HOME']) / 'venvs/opencode-sandbox' != prefix \
            or path.is_relative_to(prefix): raise Refused('Manager recovery installation boundary disagrees')
    state._shape(status(value, path), prefix)
    return value


def status(record, path):
    return {'format': state.FORMAT, 'prefix': record['prefix'], 'operation': record['operation'], 'phase': 'prepared',
            'record': str(path), 'owner': state.owner(), 'installer': None, 'previous': record['previous'],
            'target': record['target'], 'result': None, 'at': time.time()}


def prepare(value, *, path, helper_sha256, python_version, environment):
    binding = observations.parse(value['binding'])
    old, tools = binding['installation']['evidence'], binding['tools']
    previous = {'version': value['version'], 'tag': old['tag'], 'commit': old['commit'], 'source': state.SOURCE}
    target = {'version': value['target']['version'], 'tag': value['target']['tag'],
              'commit': value['target']['objects'][-1], 'source': state.SOURCE}
    record = {'format': FORMAT, 'nonce': os.urandom(32).hex(), 'prefix': value['prefix'], 'previous': previous, 'target': target,
              'settings': tools['settings'], 'python_version': python_version, 'pipx': tools['pipx'],
              'helper_python': tools['python'], 'helper_sha256': helper_sha256, 'created': time.time(),
              'home': environment['HOME'], 'installer_path': environment['PATH'], 'ceiling': environment['GIT_CEILING_DIRECTORIES']}
    record['operation'] = observations.digest(record)
    write(path, record)
    return read(path)


def check_archive(record, path):
    archive = Path(__file__).parent
    if not archive.is_file() or archive.parent != path.parent: raise Refused('Recovery requires the original external frozen helper')
    fd = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno()); state._private(info)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 262144: raise Refused('Recovery helper exceeds its bound')
        raw = stream.read(262145)
    if len(raw) > 262144 or hashlib.sha256(raw).hexdigest() != record['helper_sha256']:
        raise Refused('Original recovery helper changed; preserved')


def instructions(record, path):
    archive = path.parent / 'helper.pyz'
    verify = [record['helper_python'], '-I', '-B', '-S', str(archive), 'recover', str(path)]
    reinstall = ['env', *(key + '=' + value for key, value in sorted(record['settings'].items())), record['pipx'],
                 'install', '--force', '--python', record['settings']['PIPX_DEFAULT_PYTHON'],
                 'git+' + state.SOURCE + '@' + record['previous']['tag']]
    return ('Private manager operation record: ' + str(path) + '\n'
            'Independent verification/recovery (never installs): ' + shlex.join(verify) + '\n'
            'If unavailable, inspect all installer processes before a MANUAL previous-tag reinstall:\n' + shlex.join(reinstall) + '\n'
            'Preserve any custom network/credential settings manually. External pipx does not honor manager locks.\n'
            'Force is not a backup; previous-tag reinstall does not restore identical dependencies or guarantee offline recovery.\n'
            'After a hard-killed installer owner, same-boot descendant quiescence is unknown: startup stays blocked.\n'
            'A reboot supplies independent process quiescence before the explicit verification command; never delete state or locks.\n'
            'No dashboard restart is automatic. Wait for the final result before starting the manager.')


def result(path, value):
    # Retain each attempt, including failed recovery; never overwrite unfamiliar prior evidence.
    write(path.parent / ('result-' + os.urandom(16).hex() + '.json'), {'format': FORMAT, 'at': time.time(), **value})


def _quiescence_path(path, owner):
    return path.parent / ('quiescent-' + observations.digest(owner) + '.json')


def record_quiescence(record, path):
    # The owner must start no further child after this durable final phase. Recovery still
    # requires fresh installed verification; this is process-phase evidence, not a health cache.
    write(_quiescence_path(path, state.owner()), {'format': FORMAT, 'operation': record['operation'], 'owner': state.owner()})


def quiescence(record, path, owner):
    try: value = _read(_quiescence_path(path, owner))
    except FileNotFoundError: return False
    if value != {'format': FORMAT, 'operation': record['operation'], 'owner': owner}:
        raise Refused('Manager process-quiescence evidence changed; preserved')
    return True
