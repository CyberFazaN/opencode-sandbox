"""A separate fixed fresh CLI-help construction query, not normal CLI dispatch or a lease bypass.

Frozen source runs before target site hooks, proves the live helper's exclusion using an
unlocked witness, closes it, then initializes site and constructs/renders only the CLI command
graph. No command name, arguments, callback or environment may be supplied by the caller. The
existing three-field manager_verifier runtime query remains unchanged.
"""
import ctypes
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

if __package__:
    from . import manager_verifier as protocol
else:
    import manager_verifier as protocol


class Refused(RuntimeError):
    pass


def _identity():
    if len(sys.argv) != 6 or not sys.flags.isolated or not sys.flags.no_site or not sys.flags.dont_write_bytecode:
        raise Refused('Invalid fixed CLI-health bootstrap')
    prefix = Path(sys.argv[1])
    channel, witness, pidfd, owner_fd = map(int, sys.argv[2:])
    if not prefix.is_absolute() or prefix.resolve() != prefix or prefix.name != 'opencode-sandbox' or prefix.parent.name != 'venvs' \
            or min(channel, witness, pidfd) < 3 or len({channel, witness, pidfd}) != 3:
        raise Refused('Invalid fixed CLI-health identity')
    return prefix, channel, witness, pidfd, owner_fd


def exec_client():
    prefix, channel, witness, pidfd, owner_fd = _identity()
    import installation_locks as locks
    with socket.socket(fileno=channel) as control:
        owner = protocol._peer(control, pidfd)
        locks._verify_descriptor(witness, owner, owner_fd, prefix)
        if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise Refused('CLI-health parent-death protection unavailable')
        protocol._peer(control, pidfd)
        control.detach()
    for fd in (channel, witness, pidfd): os.set_inheritable(fd, True)
    bootstrap = 'import sys\nsys.path.insert(0,sys.argv.pop(1))\nfrom manager_health import client\nclient()\n'
    python = str(prefix / 'bin/python')
    os.execve(python, [python, '-I', '-B', '-S', '-c', bootstrap, str(Path(__file__).parent), str(prefix),
                       str(channel), str(witness), str(pidfd), str(owner_fd)],
              {'HOME': str(Path.home()), 'PATH': os.defpath, 'LANG': 'C.UTF-8'})


def client():
    prefix, channel, witness, pidfd, owner_fd = _identity()
    for fd in (channel, witness, pidfd): os.set_inheritable(fd, False)
    import installation_locks as locks
    try:
        with socket.socket(fileno=channel) as control:
            owner = protocol._peer(control, pidfd)
            value = protocol._message(control, time.monotonic() + 8, owner)
            if set(value) != {'protocol', 'prefix', 'nonce', 'owner_fd'} or type(value['protocol']) is not int or value['protocol'] != 1 \
                    or value['prefix'] != str(prefix) or value['owner_fd'] != owner_fd \
                    or not isinstance(value['nonce'], str) or len(value['nonce']) != 64 or any(ch not in '0123456789abcdef' for ch in value['nonce']):
                raise Refused('Invalid fixed CLI-health request')
            locks._verify_descriptor(witness, owner, owner_fd, prefix)
            os.close(witness); witness = None  # never LOCK_UN; no capability enters target site hooks
            import site
            site.main()
            if Path(sys.prefix).resolve() != prefix: raise Refused('Fixed CLI-health runtime prefix disagrees')
            from typer.main import get_command

            from opencode_sandbox import __version__
            from opencode_sandbox.cli import app
            command = get_command(app)
            if not {'manager', 'opencode', 'tui', 'doctor'} <= set(command.commands) \
                    or not any('--version' in parameter.opts for parameter in command.params):
                raise Refused('Fixed CLI-health command graph is incomplete')
            # Construct help directly. Do not call Command.main/invoke, the application's main,
            # root/version callbacks, Docker, discovery or any user-selected command.
            with command.context_class(command, info_name='opencode-sandbox') as context: command.get_help(context)
            protocol._peer(control, pidfd)
            control.sendall(json.dumps({'protocol': 1, 'nonce': value['nonce'],
                                        'observed': {'prefix': str(prefix), 'version': __version__, 'cli_help': True}}).encode())
    finally:
        if witness is not None: os.close(witness)
        os.close(pidfd)


def run(locks, prefix, *, deadline=None):
    if len(list(Path('/proc/self/task').iterdir())) != 1: raise Refused('Fixed CLI-health query requires a single-threaded owner')
    prefix = Path(locks.identity(prefix))
    artifact = Path(__file__).parent
    if not artifact.is_file(): raise Refused('Fixed CLI-health query requires a frozen helper')
    python = prefix / 'bin/python'
    info = python.stat()
    if not python.is_file() or info.st_uid not in (0, os.getuid()) or info.st_mode & 0o6022:
        raise Refused('Unsafe fixed CLI-health interpreter')
    deadline = min(deadline, time.monotonic() + 8) if deadline is not None else time.monotonic() + 8
    control, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
    for peer in (control, child): peer.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    pidfd, process = None, None
    try:
        pidfd = os.pidfd_open(os.getpid())
        with locks._verification(prefix) as (witness, owner_fd):
            bootstrap = 'import sys\nsys.path.insert(0,sys.argv.pop(1))\nfrom manager_health import exec_client\nexec_client()\n'
            process = subprocess.Popen([sys.executable, '-I', '-B', '-S', '-c', bootstrap, str(artifact), str(prefix),
                                        str(child.fileno()), str(witness), str(pidfd), str(owner_fd)],
                                       pass_fds=(child.fileno(), witness, pidfd), close_fds=True, start_new_session=True,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       cwd=prefix, env={'HOME': str(Path.home()), 'PATH': os.defpath, 'LANG': 'C.UTF-8'})
            child.close()
            nonce = os.urandom(32).hex()
            control.sendall(json.dumps({'protocol': 1, 'prefix': str(prefix), 'nonce': nonce, 'owner_fd': owner_fd}).encode())
            value = protocol._message(control, deadline, process.pid)
            if set(value) != {'protocol', 'nonce', 'observed'} or type(value['protocol']) is not int or value['protocol'] != 1 or value['nonce'] != nonce \
                    or not isinstance(value['observed'], dict) or set(value['observed']) != {'prefix', 'version', 'cli_help'} \
                    or value['observed']['prefix'] != str(prefix) or value['observed']['cli_help'] is not True \
                    or not isinstance(value['observed']['version'], str):
                raise Refused('Invalid fixed CLI-health response')
            while os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
                if time.monotonic() >= deadline: raise Refused('Fixed CLI-health query timed out')
                time.sleep(.01)
            status = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)
            if status.si_code != os.CLD_EXITED or status.si_status or time.monotonic() >= deadline:
                raise Refused('Fixed CLI-health query failed')
            return value['observed']
    finally:
        if process is not None:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait(timeout=1)
        control.close(); child.close()
        if pidfd is not None: os.close(pidfd)
