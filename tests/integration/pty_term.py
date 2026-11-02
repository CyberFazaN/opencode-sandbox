"""A real pseudo-terminal of a given size whose screen is rendered by pyte."""
import fcntl
import os
import pty
import re
import select
import signal
import struct
import termios
import time

import pyte

TAB, STAB, ENTER, ESC, DOWN, UP = "\t", "\x1b[Z", "\r", "\x1b", "\x1b[B", "\x1b[A"
F5, F6 = "\x1b[15~", "\x1b[17~"


class Term:
    def __init__(self, argv, cols=80, rows=24, env=None, log=None):
        self.cols, self.rows, self.log = cols, rows, log
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.ByteStream(self.screen)
        self.raw = b""
        pid, fd = pty.fork()
        if pid == 0:
            environ = dict(env or os.environ, TERM="xterm-256color")
            environ.pop("COLUMNS", None)
            environ.pop("LINES", None)
            os.execvpe(argv[0], argv, environ)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        self.pid, self.fd, self.alive = pid, fd, True
        self._reaped = False

    def pump(self, seconds):
        end = time.time() + seconds
        while time.time() < end and self.alive:
            r, _, _ = select.select([self.fd], [], [], 0.05)
            if not r:
                continue
            try:
                chunk = os.read(self.fd, 65536)
            except OSError:
                chunk = b""
            if not chunk:
                self.alive = False
                break
            self.raw += chunk
            self.stream.feed(chunk)

    def text(self):
        return "\n".join(line.rstrip() for line in self.screen.display)

    def wait_for(self, pattern, timeout=30):
        end = time.time() + timeout
        while time.time() < end and self.alive:
            if re.search(pattern, self.text()):
                return True
            self.pump(0.2)
        return bool(re.search(pattern, self.text()))

    def send(self, keys, settle=0.6):
        os.write(self.fd, keys.encode())
        self.pump(settle)

    def snap(self, label):
        if self.log:
            self.log(f"----- {label} ({self.cols}x{self.rows}) -----\n{self.text()}")

    def exit_code(self, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            self.pump(0.1)
            try:
                wpid, status = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                self._reaped = True
                return "?"
            if wpid:
                self._reaped = True
                return os.waitstatus_to_exitcode(status)
        self.close()
        return "killed (still running)"

    def restored(self):
        tail = self.raw[-4000:]
        return b"?1049l" in tail and b"?25h" in tail

    def close(self):
        if not self._reaped:
            try:
                # Confirm/reserve actual child ownership before any signal. exit_code() may
                # already have reaped it while a detached updater still writes to this pty.
                pid, _ = os.waitpid(self.pid, os.WNOHANG)
                if not pid:
                    os.kill(self.pid, signal.SIGKILL)
                    os.waitpid(self.pid, 0)
            except (ProcessLookupError, ChildProcessError): pass
            self._reaped = True
        self.alive = False
        if self.fd is not None:
            try: os.close(self.fd)
            except OSError: pass
            self.fd = None
