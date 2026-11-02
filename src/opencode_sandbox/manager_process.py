"""Frozen stdlib bounded diagnostic children; no application imports or mutation deadlines."""
import os
import selectors
import signal
import subprocess
import time
import zipfile
from pathlib import Path


class Refused(RuntimeError):
    pass


def source(name):
    if name not in ('manager_tool_probe.py', 'manager_pip_probe.py', 'http_probe.py'):
        raise Refused('Unrecognized frozen diagnostic source')
    parent = Path(__file__).parent
    if parent.is_file():
        with zipfile.ZipFile(parent) as archive:
            if archive.getinfo(name).file_size > 65536: raise Refused('Oversized frozen diagnostic source')
            raw = archive.read(name)
    else: raw = (parent / name).read_bytes()
    if len(raw) > 65536: raise Refused('Oversized frozen diagnostic source')
    return raw.decode('utf-8')


def run(argv, *, environment, cwd, deadline, limit=131072):
    """Capture bounded bytes, kill/reap our group with its leader still reserved on every exit.

    Only short read-only probes use this budget. Never expose child diagnostics to a terminal or
    include arbitrary output in an exception. No inherited usage/exclusive descriptors.
    """
    if time.monotonic() >= deadline: raise Refused('Independent diagnostic timed out')
    process = subprocess.Popen(argv, env=environment, cwd=cwd, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, start_new_session=True)
    output = [bytearray(), bytearray()]
    try:
        with selectors.DefaultSelector() as selector:
            for index, stream in enumerate((process.stdout, process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, index)
            status = None
            while selector.get_map() or status is None:
                left = deadline - time.monotonic()
                if left <= 0: raise Refused('Independent diagnostic timed out')
                for key, _ in selector.select(min(left, .02)):
                    chunk = os.read(key.fileobj.fileno(), 16384)
                    if not chunk: selector.unregister(key.fileobj)
                    else:
                        output[key.data].extend(chunk)
                        if sum(map(len, output)) > limit: raise Refused('Independent diagnostic output exceeds its bound')
                status = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            code = status.si_status if status.si_code == os.CLD_EXITED else -status.si_status
            return code, bytes(output[0]), bytes(output[1])
    finally:
        # Popen.poll()/wait()/communicate() must not free this PID before killpg.
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait(timeout=1)
        process.stdout.close(); process.stderr.close()
