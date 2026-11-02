"""One fixed read-only fresh-process runtime query under helper-owned exclusion (UP-16).

This module is also frozen into the external stdlib helper. It is NOT a launcher flag, normal
CLI dispatcher, provenance/authentication result or installation grant. All imports are stdlib;
the client imports only package version/location AFTER validating and closing its UNLOCKED witness.
"""
import ctypes
import json
import os
import re
import selectors
import signal
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

LIMIT = 4096
TIMEOUT = 8.0


class Refused(RuntimeError):
    pass


def _message(control, deadline, expected_pid):
    left = deadline - time.monotonic()
    if left <= 0: raise Refused('Fresh verifier timed out')
    control.settimeout(left)
    raw, ancillary, flags, _ = control.recvmsg(LIMIT, socket.CMSG_SPACE(12) + socket.CMSG_SPACE(32), socket.MSG_CMSG_CLOEXEC)
    credentials = []
    unexpected = False
    for level, kind, data in ancillary:
        if level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(data) == 12:
            credentials.append(struct.unpack('3i', data))
        else:
            unexpected = True
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                for fd, in struct.iter_unpack('i', data[:len(data) // 4 * 4]): os.close(fd)
    if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or not raw or unexpected or len(credentials) != 1 \
            or credentials[0][:2] != (expected_pid, os.getuid()):
        raise Refused('Invalid fresh-verifier message')
    value = json.loads(raw)
    if not isinstance(value, dict): raise Refused('Invalid fresh-verifier message')
    return value


def _peer(control, pidfd):
    if control.type != socket.SOCK_SEQPACKET: raise Refused('Invalid fresh-verifier channel')
    pid, uid, _ = struct.unpack('3i', control.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid != os.getuid() or pid != os.getppid(): raise Refused('Invalid fresh-verifier owner')
    if f'Pid:\t{pid}' not in Path(f'/proc/self/fdinfo/{pidfd}').read_text().splitlines():
        raise Refused('Invalid fresh-verifier owner pidfd')
    with selectors.DefaultSelector() as selector:
        selector.register(pidfd, selectors.EVENT_READ)
        if selector.select(0): raise Refused('Fresh-verifier owner exited')
    return pid


def _runtime():
    # Deliberately no core, CLI, Docker, configuration, discovery, source resolution or callbacks.
    from . import __version__
    package = sys.modules['opencode_sandbox']
    module, prefix = Path(package.__file__).resolve(), Path(sys.prefix).resolve()
    if not module.is_relative_to(prefix) or not isinstance(__version__, str) or not re.fullmatch(r'\d+\.\d+\.\d+', __version__):
        raise Refused('Fresh-verifier runtime identity is unsupported')
    return {'version': __version__, 'prefix': str(prefix), 'module': str(module)}


def exec_client():
    """Frozen external -S bootstrap sets parent-death protection BEFORE target site hooks.

    No preexec_fn or relaxed fork rules. Exec preserves the parent-death signal. Only this fixed
    target/module/argv is accepted; even early site children can inherit no exclusive descriptor.
    """
    if len(sys.argv) != 6 or not sys.flags.isolated or not sys.flags.no_site:
        raise Refused('Invalid fresh-verifier exec bootstrap')
    prefix = Path(sys.argv[1])
    channel, capability, pidfd, owner_fd = map(int, sys.argv[2:])
    if not prefix.is_absolute() or str(prefix.resolve()) != str(prefix) or prefix.name != 'opencode-sandbox' or prefix.parent.name != 'venvs' \
            or min(channel, capability, pidfd) < 3 or len({channel, capability, pidfd}) != 3:
        raise Refused('Invalid fresh-verifier exec identity')
    with socket.socket(fileno=channel) as control:
        owner = _peer(control, pidfd)
        import installation_locks as locks
        locks._verify_descriptor(capability, owner, owner_fd, prefix)
        if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise Refused('Fresh-verifier parent-death protection unavailable')
        _peer(control, pidfd)  # close the prctl/parent-death race before exec
        control.detach()
    for fd in (channel, capability, pidfd): os.set_inheritable(fd, True)
    python = str(prefix / 'bin/python')
    os.execve(python, [python, '-I', '-B', '-m', 'opencode_sandbox.manager_verifier',
                      str(channel), str(capability), str(pidfd)],
              {'HOME': str(Path.home()), 'PATH': os.defpath, 'LANG': 'C.UTF-8'})


def main():
    if len(sys.argv) != 4 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise Refused('Invalid fresh-verifier invocation')
    channel, capability, pidfd = map(int, sys.argv[1:])
    if min(channel, capability, pidfd) < 3 or len({channel, capability, pidfd}) != 3:
        raise Refused('Invalid fresh-verifier descriptors')
    for fd in (channel, capability, pidfd): os.set_inheritable(fd, False)
    try:
        with socket.socket(fileno=channel) as control:
            owner = _peer(control, pidfd)
            deadline = time.monotonic() + TIMEOUT
            value = _message(control, deadline, owner)
            if set(value) != {'protocol', 'prefix', 'nonce', 'owner_fd'} or type(value['protocol']) is not int or value['protocol'] != 1 \
                    or value['prefix'] != str(Path(sys.prefix).resolve()) or not isinstance(value['nonce'], str) \
                    or not re.fullmatch('[0-9a-f]{64}', value['nonce']):
                raise Refused('Invalid fresh-verifier request')
            from . import installation_locks as locks
            try: locks._verify_descriptor(capability, owner, value['owner_fd'])
            finally: os.close(capability); capability = None  # close, NEVER LOCK_UN
            observed = _runtime()
            _peer(control, pidfd)
            raw = json.dumps({'protocol': 1, 'nonce': value['nonce'], 'observed': observed}).encode()
            if len(raw) > LIMIT: raise Refused('Oversized fresh-verifier result')
            control.sendall(raw)
    finally:
        if capability is not None: os.close(capability)
        os.close(pidfd)


def run(locks, prefix, *, deadline=None):
    """Only the exclusive, single-threaded independent helper calls this fixed query.

    Keep the group leader unreaped until group cleanup, so PID reuse cannot redirect signals.
    PDEATHSIG stops the direct verifier even if the helper dies before target client imports;
    the only inherited file witness is independent/read-only and cannot retain exclusion.
    The client never runs normal CLI dispatch; acquire_usage() has no verifier exemption.
    """
    if len(list(Path('/proc/self/task').iterdir())) != 1: raise Refused('Fresh verifier requires a single-threaded owner')
    prefix = Path(locks.identity(prefix))
    if prefix.name != 'opencode-sandbox' or prefix.parent.name != 'venvs': raise Refused('Invalid fresh-verifier prefix')
    # Only an existing controlled venv interpreter, not a user command/PATH Python or installer.
    python = prefix / 'bin/python'
    info = python.stat()
    if info.st_uid not in (0, os.getuid()) or info.st_mode & 0o6022 or not python.is_file():
        raise Refused('Unsafe fresh-verifier interpreter')
    owner = os.getpid()
    artifact = Path(__file__).parent
    if not artifact.is_file(): raise Refused('Fresh verifier must be launched by the frozen helper')
    control, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
    control.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    child.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    pidfd, process = None, None
    limit = time.monotonic() + TIMEOUT
    deadline = limit if deadline is None else min(deadline, limit)
    try:
        pidfd = os.pidfd_open(owner)
        with locks._verification(prefix) as (capability, owner_fd):
            try:
                bootstrap = ('import sys\nsys.path.insert(0,sys.argv.pop(1))\n'
                             'from manager_verifier import exec_client\nexec_client()\n')
                process = subprocess.Popen([sys.executable, '-I', '-B', '-S', '-c', bootstrap, str(artifact), str(prefix),
                                            str(child.fileno()), str(capability), str(pidfd), str(owner_fd)],
                                           pass_fds=(child.fileno(), capability, pidfd), close_fds=True, start_new_session=True,
                                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           cwd=prefix, env={'HOME': str(Path.home()), 'PATH': os.defpath, 'LANG': 'C.UTF-8'})
                child.close()
                nonce = os.urandom(32).hex()
                control.sendall(json.dumps({'protocol': 1, 'prefix': str(prefix), 'nonce': nonce, 'owner_fd': owner_fd}).encode())
                value = _message(control, deadline, process.pid)
                if set(value) != {'protocol', 'nonce', 'observed'} or type(value['protocol']) is not int or value['protocol'] != 1 \
                        or value['nonce'] != nonce or not isinstance(value['observed'], dict) \
                        or set(value['observed']) != {'prefix', 'module', 'version'} or value['observed']['prefix'] != str(prefix) \
                        or not isinstance(value['observed']['module'], str) \
                        or not Path(value['observed']['module']).is_absolute() \
                        or not Path(value['observed']['module']).resolve().is_relative_to(prefix) \
                        or not isinstance(value['observed']['version'], str) or not re.fullmatch(r'\d+\.\d+\.\d+', value['observed']['version']):
                    raise Refused('Invalid fresh-verifier response')
                while os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
                    left = deadline - time.monotonic()
                    if left <= 0: raise Refused('Fresh verifier timed out')
                    time.sleep(min(.01, left))
                status = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)
                if status.si_code != os.CLD_EXITED or status.si_status != 0: raise Refused('Fresh verifier failed')
                if time.monotonic() >= deadline: raise Refused('Fresh verifier timed out')
                return value['observed']
            finally:
                if process is not None:
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    process.wait(timeout=1)
    finally:
        control.close(); child.close()
        if pidfd is not None: os.close(pidfd)


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError):
        print('Fresh runtime verifier refused; no installation was changed.', file=sys.stderr)
        raise SystemExit(2) from None
