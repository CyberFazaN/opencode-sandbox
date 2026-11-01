"""Staged stdlib-only, NON-MUTATING process-exit fixture; no installer/normal CLI dispatch.

Executed only as the frozen zipapp's __main__ under external Python -I -B -S. Local imports are
bundled source copies, not imports from the replaceable package. Optional fixed read-only runtime
and independent tool/policy/published-source diagnostics never install, dispatch normal CLI or
grant access to another process. No shell, Docker, installer or normal-manager bypass.
"""
import hashlib
import json
import os
import re
import selectors
import socket
import stat
import struct
import sys
import sysconfig
import time
from pathlib import Path

LIMIT = 4096
BUDGET = 30.0  # bounded fixture lifetime, NOT a future installation deadline


class Refused(RuntimeError):
    pass


def _private(info, directory=False):
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600) \
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1):
        raise Refused('Unsafe helper artifact')


def _result(directory, value):
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    if len(raw) > LIMIT: raise Refused('Invalid helper result')
    fd = os.open('result.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600, dir_fd=directory)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.fsync(directory)


def _receive(control, deadline):
    control.settimeout(max(.001, deadline - time.monotonic()))
    raw, _, flags, _ = control.recvmsg(LIMIT)
    if flags & socket.MSG_TRUNC: raise Refused('Oversized helper request')
    return raw


def _wait(control, pidfd, deadline, *, armed):
    with selectors.DefaultSelector() as selector:
        selector.register(control, selectors.EVENT_READ, 'control')
        selector.register(pidfd, selectors.EVENT_READ, 'origin')
        while True:
            left = deadline - time.monotonic()
            if left <= 0: return 'expired'
            events = {key.data for key, _ in selector.select(left)}
            # Cancellation wins over death when both are observed together.
            if 'control' in events:
                message = _receive(control, deadline)
                if message == b'cancel': return 'cancelled'
                if not message:
                    if not armed: return 'abandoned'
                    selector.unregister(control)  # EOF is NOT evidence of process exit
                elif not armed and message == b'arm': return 'armed'
                else: raise Refused('Invalid helper transition')
            if 'origin' in events: return 'quiescent' if armed else 'abandoned'


def main():
    # The only accepted mode is this bounded, non-mutating fixture. No environment flag or CLI
    # argument can grant ordinary manager access while another process owns exclusion.
    if len(sys.argv) != 5 or sys.argv[1] != 'quiescence-fixture': raise Refused('Invalid helper invocation')
    control_fd, pidfd, directory = map(int, sys.argv[2:])
    if min(control_fd, pidfd, directory) < 3 or len({control_fd, pidfd, directory}) != 3:
        raise Refused('Invalid helper descriptors')
    for fd in (control_fd, pidfd, directory): os.set_inheritable(fd, False)
    _private(os.fstat(directory), directory=True)
    with socket.socket(fileno=control_fd) as control:
        if control.type != socket.SOCK_SEQPACKET: raise Refused('Invalid helper control channel')
        origin, uid, _ = struct.unpack('3i', control.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != os.getuid() or origin == os.getpid(): raise Refused('Invalid helper origin')
        fields = Path(f'/proc/self/fdinfo/{pidfd}').read_text().splitlines()
        if f'Pid:\t{origin}' not in fields: raise Refused('Helper origin pidfd does not match control peer')
        started = time.monotonic()
        request = json.loads(_receive(control, started + 8.0))
        required = {'protocol', 'prefix', 'sha256', 'budget'}
        if not isinstance(request, dict) or not required <= set(request) or set(request) - required - {'verify', 'local_review', 'execution_validate'} \
                or ('verify' in request and request['verify'] is not True) \
                or ('execution_validate' in request and (request['execution_validate'] is not True or 'local_review' not in request)) \
                or type(request['protocol']) is not int or request['protocol'] != 1 or isinstance(request['budget'], bool) \
                or not isinstance(request['budget'], (float, int)) \
                or not 0 < request['budget'] <= BUDGET:
            raise Refused('Invalid helper request')
        if 'local_review' in request:
            value = request['local_review']
            if not isinstance(value, dict) or set(value) != {'sha256', 'identity', 'file_identity'} \
                    or any(not isinstance(value[key], str) or not re.fullmatch('[0-9a-f]{64}', value[key]) for key in ('sha256', 'identity')) \
                    or not isinstance(value['file_identity'], list) or len(value['file_identity']) != 2 \
                    or any(type(item) is not int or item < 0 for item in value['file_identity']):
                raise Refused('Invalid local observation request')
        deadline = started + request['budget']
        import installation_locks as locks
        from manager_tool_probe import outside
        target = Path(locks.identity(request['prefix']))
        if target == Path('/') or target.name != 'opencode-sandbox' or target.parent.name != 'venvs':
            raise Refused('Invalid helper installation identity')
        if sys.version_info < (3, 11) or not sys.flags.isolated or not sys.flags.no_site or not sys.flags.dont_write_bytecode:
            raise Refused('Helper requires isolated stdlib-only Python')
        for path in (sys.executable, sys.prefix, sys.base_prefix, sysconfig.get_path('stdlib'), *sys.path):
            outside(path, target)
        artifact = Path(outside(sys.argv[0], target))
        _private(artifact.parent.stat(), directory=True)
        named, opened = artifact.parent.stat(), os.fstat(directory)
        if (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino): raise Refused('Helper directory changed')
        fd = os.open(artifact.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno()); _private(info)
            if info.st_size > 262144: raise Refused('Oversized helper artifact')
            digest = hashlib.sha256(stream.read(262145)).hexdigest()
        if digest != request['sha256']: raise Refused('Helper artifact changed')
        # Never inherit the origin's process-lifetime shared lease or an exclusive guard.
        for item in Path('/proc/self/fd').iterdir():
            try: name = os.readlink(item)
            except OSError: continue
            if '/opencode-sandbox-locks-' in name: raise Refused('Helper inherited an installation guard')
        control.sendall(b'ready')
        outcome = _wait(control, pidfd, deadline, armed=False)
        if outcome == 'armed':
            control.sendall(b'armed')
            outcome = _wait(control, pidfd, deadline, armed=True)
        if outcome == 'quiescent':
            try:
                with locks.exclusive(target):
                    result = {'protocol': 1, 'fixture': True, 'outcome': outcome,
                               'origin': origin, 'helper': os.getpid(), 'sha256': digest}
                    if 'local_review' in request:
                        try:
                            from manager_observations import validate
                            result['review'] = validate(locks, directory, request['local_review'], prefix=str(target),
                                                        origin=origin, deadline=deadline)
                        except (OSError, ValueError, TypeError, KeyError, RuntimeError, RecursionError):
                            result['outcome'] = 'review-failed'
                            result['review'] = {'ok': False, 'identity': request['local_review']['identity'],
                                               'reason': 'Approved local manager observations changed or unavailable; no installation was changed'}
                            _result(directory, result)
                            return
                    if request.get('execution_validate'):
                        try:
                            from manager_execution import validate as execution_validate
                            from manager_observations import load, validate
                            value = load(locks, directory, request['local_review'], prefix=str(target), origin=origin)
                            execution_validate(locks, value, cwd=artifact.parent, deadline=deadline)
                            validate(locks, directory, request['local_review'], prefix=str(target), origin=origin, deadline=deadline)
                            result['execution'] = {'ok': True}
                        except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError, AttributeError, RecursionError):
                            result['outcome'] = 'execution-failed'
                            result['execution'] = {'ok': False, 'reason': 'Independent manager execution validation failed; no installation was changed'}
                            _result(directory, result)
                            return
                    if request.get('verify'):
                        try:
                            from manager_verifier import run
                            result['verifier'] = {'ok': True, 'observed': run(locks, target, deadline=deadline)}
                        except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError):
                            result['outcome'] = 'verification-failed'
                            result['verifier'] = {'ok': False, 'reason': 'Fresh runtime verification unavailable; no installation was changed'}
                    _result(directory, result)
                return
            except locks.Error: outcome = 'busy'
        _result(directory, {'protocol': 1, 'fixture': True, 'outcome': outcome,
                            'origin': origin, 'helper': os.getpid(), 'sha256': digest})


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        # Never echo untrusted requests, paths, imported diagnostics or environment values.
        print('Non-mutating helper fixture refused; no installation was changed.', file=sys.stderr)
        raise SystemExit(2) from None
