"""Scoped base-build feedback: bounded output tail, not a timeout or mutation cancel runner."""
import subprocess
import time
from contextlib import contextmanager
from contextvars import ContextVar

LIMIT = 32768
_FEEDBACK = ContextVar('base_build_feedback', default=None)


class Feedback:
    def __init__(self, callback):
        self.callback, self.phase, self.tail, self.truncated = callback, '', b'', False
        self.last = 0.0

    def publish(self):
        prefix = '[Earlier build output omitted; showing the bounded tail]\n' if self.truncated else ''
        self.callback(self.phase, prefix + self.tail.decode('utf-8', errors='replace'))
        self.last = time.monotonic()

    def write(self, chunk):
        first = not self.tail
        self.truncated |= len(self.tail) + len(chunk) > LIMIT
        self.tail = (self.tail + chunk)[-LIMIT:]
        if first or time.monotonic() - self.last >= .2: self.publish()


@contextmanager
def listen(callback):
    token = _FEEDBACK.set(Feedback(callback))
    try: yield
    finally: _FEEDBACK.reset(token)


def phase(message):
    feedback = _FEEDBACK.get()
    if feedback:
        feedback.phase = message
        feedback.publish()


def current():
    return _FEEDBACK.get()


def run(argv, *, env, launch_guard):
    """Drain continuously with bounded memory. No build deadline/output-limit termination.

    Only the base-build worker opts in. CLI output otherwise keeps its normal streaming path.
    The direct client is always waited/reaped; interrupting it is not proof a daemon build ended.
    """
    feedback = current()
    proc = None
    try:
        with launch_guard():
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, env=env)
        while chunk := proc.stdout.read1(65536): feedback.write(chunk)
        proc.wait()
        feedback.publish()
        text = feedback.tail.decode('utf-8', errors='replace')
        return subprocess.CompletedProcess(argv, proc.returncode, text, text)
    finally:
        if proc is not None:
            if proc.poll() is None: proc.terminate()
            proc.wait()
            proc.stdout.close()
