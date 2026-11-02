"""Bounded, captured host diagnostics; never use this runner for long mutations or sessions."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from contextlib import nullcontext

POLL = 0.05
TIMEOUT = 8.0
MAX_OUTPUT = 1024 * 1024  # combined stdout/stderr, not one unbounded buffer per poll


class Cancelled(BaseException):
    pass


class Failure(Exception):
    pass


def run(argv, *, timeout=TIMEOUT, cancelled=None, max_output=MAX_OUTPUT, cwd=None, env=None, launch_guard=nullcontext):
    """One monotonic total budget, including pipe draining; terminate/reap only our process group.

    Pipes are read incrementally so a noisy client or a descendant retaining a pipe cannot evade
    the deadline/output bound. No background reader thread is abandoned after cancellation.
    """
    deadline = time.monotonic() + timeout
    def remaining():
        if cancelled and cancelled(): raise Cancelled()
        left = deadline - time.monotonic()
        if left <= 0: raise Failure(f"Diagnostic timed out after {timeout:g}s")
        return left
    remaining()
    p = None
    output = [bytearray(), bytearray()]
    size = 0
    try:
        with launch_guard():
            p = subprocess.Popen([str(x) for x in argv], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        with selectors.DefaultSelector() as selector:
            for index, pipe in enumerate((p.stdout, p.stderr)):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ, index)
            # Observe exit without reaping: the unreaped leader reserves the PGID until cleanup,
            # so a reused PID cannot redirect the final group signal at an unrelated process.
            while selector.get_map() or os.waitid(os.P_PID, p.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
                for key, _ in selector.select(min(POLL, remaining())):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    size += len(chunk)
                    if size > max_output: raise Failure(f"Diagnostic output exceeds {max_output} bytes")
                    output[key.data].extend(chunk)
            remaining()  # a canceled/expired client cannot publish a late success
    finally:
        # Even if the direct client exited, its children may still own pipes or keep running.
        if p is not None:
            try: os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            p.stdout.close()
            p.stderr.close()
            try: p.wait(timeout=1)
            except subprocess.TimeoutExpired as exc:
                raise Failure("Diagnostic client could not be reaped after termination") from exc
    return subprocess.CompletedProcess(argv, p.returncode,
                                       *(bytes(data).decode(errors="replace") for data in output))
