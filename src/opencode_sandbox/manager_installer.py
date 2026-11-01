"""Frozen exact-tag pipx child and reserved-PID cleanup; no discovery or automatic rollback.

An isolated external Python child parks before exec. Its pid/start/group is durable before GO.
Only that child gets parent-death SIGKILL; descendants never inherit a manager lock. The helper
uses subreaper ownership/pidfds to terminate adopted descendants, never stale PID guesses.
"""
import ctypes
import hashlib
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

if __package__:
    from . import installation_state as state
    from . import manager_network as policy
    from . import manager_observations as observations
    from . import manager_source as source
    from . import manager_verifier as protocol
else:
    import installation_state as state
    import manager_network as policy
    import manager_observations as observations
    import manager_source as source
    import manager_verifier as protocol


class Refused(RuntimeError):
    pass


def _children():
    return [int(pid) for pid in Path(f'/proc/self/task/{os.getpid()}/children').read_text().split()]


def begin():
    if _children() or len(list(Path('/proc/self/task').iterdir())) != 1:
        raise Refused('Installer requires an independent single-threaded owner without existing children')
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0: raise Refused('Installer subreaper protection unavailable')


def drain():
    """Terminate only actual own adopted children with pidfd proof; reap all owned exits."""
    live = False
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        children = _children()
        if not children: return True, live
        for pid in children:
            descriptor = None
            try:
                descriptor = os.pidfd_open(pid)
                fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
                if int(fields[1]) != os.getpid(): raise Refused('Installer descendant ownership could not be proved')
                if fields[0] != 'Z':
                    live = True
                    signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                os.waitpid(pid, os.WNOHANG)
            except (ProcessLookupError, FileNotFoundError, ChildProcessError): pass
            finally:
                if descriptor is not None: os.close(descriptor)
        time.sleep(.01)
    return False, live


def _cleanup(process):
    # The direct leader has not been reaped, even on normal completion, so killpg cannot target
    # a recycled group. A subreaper child must have our actual PPID before pidfd signaling.
    try: os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError: pass
    process.wait(timeout=3)
    return drain()[0]


def child():
    if len(sys.argv) != 4 or not sys.flags.isolated or not sys.flags.no_site or not sys.flags.dont_write_bytecode:
        raise Refused('Invalid installer bootstrap')
    channel, pidfd = map(int, sys.argv[2:])
    if min(channel, pidfd) < 3 or channel == pidfd: raise Refused('Invalid installer descriptors')
    for fd in (channel, pidfd): os.set_inheritable(fd, False)
    with socket.socket(fileno=channel) as control:
        owner = protocol._peer(control, pidfd)
        if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise Refused('Installer parent-death protection unavailable')
        protocol._peer(control, pidfd)
        identity = state.owner()
        control.sendall(json.dumps({'pid': identity['pid'], 'start': identity['start'], 'pgid': os.getpgrp()}).encode())
        control.settimeout(8)
        raw, ancillary, flags, _ = control.recvmsg(16384, socket.CMSG_SPACE(12), socket.MSG_CMSG_CLOEXEC)
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or ancillary != [(socket.SOL_SOCKET, socket.SCM_CREDENTIALS,
                struct.pack('3i', owner, os.getuid(), os.getgid()))]:
            raise Refused('Invalid or oversized installer request')
        value = observations.parse(raw)
        required = {'protocol', 'pipx', 'tag', 'settings', 'home', 'path', 'ceiling', 'owner_fd'}
        if not isinstance(value, dict) or set(value) != required or type(value['protocol']) is not int or value['protocol'] != 1:
            raise Refused('Invalid installer request')
        source.version(value['tag'])
        for path in (value['pipx'], value['home'], value['ceiling']): observations._path(path)
        import installation_locks as locks
        import manager_operation as operation
        prefix = Path(value['settings']['PIPX_HOME']) / 'venvs/opencode-sandbox'
        # Open an independent read-only witness ourselves; inherit/export NO lock descriptor.
        # Verify the authenticated live parent really owns exclusion for this exact prefix.
        key = hashlib.sha256(os.fsencode(str(prefix))).hexdigest()
        fd = os.open(locks._TMP / f'opencode-sandbox-locks-{os.getuid()}' / f'installation-{key}.lock',
                     os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        try: locks._verify_descriptor(fd, owner, value['owner_fd'], prefix)
        finally: os.close(fd)
        pending = state.read(prefix)
        parent = Path(f'/proc/{owner}/stat').read_text().rsplit(')', 1)[1].split()
        if pending is None or pending['phase'] != 'installing' or pending['owner'] != {
                'pid': owner, 'uid': os.getuid(), 'start': parent[19], 'boot': identity['boot']} \
                or pending['installer'] != {'pid': os.getpid(), 'start': identity['start'], 'pgid': os.getpgrp()}:
            raise Refused('Installer admission is not durably owned by the live exclusive parent')
        record = operation.read(Path(pending['record']))
        operation.check_archive(record, Path(pending['record']))
        if record['operation'] != pending['operation'] or record['target'] != pending['target'] or record['previous'] != pending['previous'] \
                or record['pipx'] != value['pipx'] or record['settings'] != value['settings'] or record['target']['tag'] != value['tag'] \
                or record['home'] != value['home'] or record['installer_path'] != value['path'] or record['ceiling'] != value['ceiling']:
            raise Refused('Installer admission changed immutable operation inputs')
        environment = policy.environment(value['settings'], {'HOME': value['home']}, path=value['path'])
        environment['GIT_CEILING_DIRECTORIES'] = value['ceiling']
        protocol._peer(control, pidfd)
    os.close(pidfd)
    # No inherited exclusive/shared descriptor, shell command, next-tag lookup or Python switch.
    os.execve(value['pipx'], [value['pipx'], 'install', '--force', '--python', value['settings']['PIPX_DEFAULT_PYTHON'],
                             'git+' + state.SOURCE + '@' + value['tag']], environment)


def replace(locks, record, path, effective):
    prefix = record['prefix']
    with locks._verification(prefix) as (witness, owner_fd): locks._verify_descriptor(witness, os.getpid(), owner_fd, prefix)
    current = locks.operation_state(prefix)
    if current != state_value(record, path) or _children() or len(list(Path('/proc/self/task').iterdir())) != 1:
        raise Refused('Installer requires its prepared operation and an independent idle owner')
    begin()
    archive = Path(__file__).parent
    if not archive.is_file(): raise Refused('Installer requires the external frozen helper')
    control, child_socket = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
    for peer in (control, child_socket): peer.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    process = pidfd = None
    quiescent = False
    try:
        pidfd = os.pidfd_open(os.getpid())
        process = subprocess.Popen([sys.executable, '-I', '-B', '-S', str(archive), 'installer-child', str(child_socket.fileno()), str(pidfd)],
                                   pass_fds=(child_socket.fileno(), pidfd), close_fds=True, start_new_session=True,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   cwd=path.parent, env={'HOME': effective['environment']['HOME'], 'PATH': os.defpath, 'LANG': 'C.UTF-8'})
        child_socket.close()
        identity = protocol._message(control, time.monotonic() + 8, process.pid)
        if set(identity) != {'pid', 'start', 'pgid'} or identity['pid'] != process.pid or identity['pgid'] != process.pid:
            raise Refused('Installer did not park in its owned process group')
        fields = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()
        if identity['start'] != fields[19] or int(fields[1]) != os.getpid() or int(fields[2]) != process.pid:
            raise Refused('Installer process identity changed before admission')
        current.update(phase='installing', installer=identity, at=time.time())
        locks.record_operation(current, prefix)  # durable BEFORE allowing exec
        control.sendall(json.dumps({'protocol': 1, 'pipx': record['pipx'], 'tag': record['target']['tag'],
                                    'settings': record['settings'], 'home': effective['environment']['HOME'],
                                    'path': effective['environment']['PATH'], 'ceiling': effective['environment']['GIT_CEILING_DIRECTORIES'],
                                    'owner_fd': owner_fd}).encode())
        # Deliberately no installation/build deadline. No poll/wait/communicate until group cleanup.
        while os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None: time.sleep(.05)
        status = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)
        code = status.si_status if status.si_code == os.CLD_EXITED else -status.si_status
        return code
    finally:
        try:
            if process is not None: quiescent = _cleanup(process)
        finally:
            control.close(); child_socket.close()
            if pidfd is not None: os.close(pidfd)
            current = locks.operation_state(prefix)
            if current and current['operation'] == record['operation']:
                current.update(phase='verifying' if quiescent else 'manual-recovery',
                               installer=None if quiescent else current['installer'], result=None if quiescent else 'interrupted', at=time.time())
                # A launch failure while still prepared cannot transition straight to verifying.
                if current['phase'] == 'verifying' and locks.operation_state(prefix)['phase'] == 'prepared':
                    current.update(phase='manual-recovery', result='interrupted')
                locks.record_operation(current, prefix)


def state_value(record, path):
    # Compare invariant fields, not a guessed timestamp or cache result.
    value = state.read(record['prefix'])
    if value is None or value['phase'] != 'prepared' or value['owner'] != state.owner() \
            or value['operation'] != record['operation'] or value['record'] != str(path) \
            or value['target'] != record['target'] or value['previous'] != record['previous'] or value['installer'] is not None:
        raise Refused('Installer prepared state changed or is not owned')
    return value
