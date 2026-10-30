"""Keep client creation signal-safe without masking signals inherited by the client."""
import os
import signal
import subprocess
import threading
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
def test_launch_defers_then_restores_the_original_handler(sig):
    saved = signal.getsignal(sig)
    calls = []

    def handler(signum, frame):
        calls.append(signum)
        assert signal.getsignal(sig) is handler
        raise SystemExit(128 + signum)

    signal.signal(sig, handler)
    try:
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, [])
        with pytest.raises(SystemExit) as caught, c._session_launch_signals():
            os.kill(os.getpid(), sig)
            assert calls == []  # no exception until the client PID/callback are owned
            assert signal.pthread_sigmask(signal.SIG_BLOCK, []) == mask
        assert caught.value.code == 128 + sig and calls == [sig]
        assert signal.getsignal(sig) is handler
    finally:
        signal.signal(sig, saved)


def test_launch_preserves_ignored_and_default_handlers():
    saved = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGHUP)}
    try:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        with c._session_launch_signals():
            assert signal.getsignal(signal.SIGTERM) == signal.SIG_DFL
            assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN
            os.kill(os.getpid(), signal.SIGHUP)
        assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN
    finally:
        for sig, handler in saved.items():
            signal.signal(sig, handler)


def test_launch_restores_handlers_on_an_exception_and_delivers_only_first_signal():
    saved = signal.getsignal(signal.SIGTERM)
    calls = []

    def handler(signum, frame):
        calls.append(signum)

    signal.signal(signal.SIGTERM, handler)
    try:
        with pytest.raises(RuntimeError, match="creation failed"), c._session_launch_signals():
            os.kill(os.getpid(), signal.SIGTERM)
            os.kill(os.getpid(), signal.SIGTERM)
            raise RuntimeError("creation failed")
        assert calls == [signal.SIGTERM]
        assert signal.getsignal(signal.SIGTERM) is handler
    finally:
        signal.signal(signal.SIGTERM, saved)


@pytest.mark.real_session
def test_pending_exit_runs_only_after_pid_registration(monkeypatch):
    saved = signal.getsignal(signal.SIGTERM)
    registered, events = [], []

    def handler(signum, frame):
        assert registered == [123]
        raise SystemExit(128 + signum)

    class Client:
        pid = 123

        def poll(self):
            return None

        def send_signal(self, sig):
            events.append(sig)

        def wait(self, timeout=None):
            events.append(timeout)
            return 129

    def create(*args, **kwargs):
        os.kill(os.getpid(), signal.SIGTERM)
        return Client()

    monkeypatch.setattr(subprocess, "Popen", create)
    signal.signal(signal.SIGTERM, handler)
    try:
        with pytest.raises(SystemExit) as caught:
            c.docker_attached("exec", on_start=registered.append)
        assert caught.value.code == 143 and events == [signal.SIGHUP, 5]
    finally:
        signal.signal(signal.SIGTERM, saved)


def test_launch_in_worker_does_not_install_process_wide_handlers(monkeypatch):
    monkeypatch.setattr(signal, "signal", lambda *a: pytest.fail("worker changed signal handler"))
    results = []

    def worker():
        with c._session_launch_signals():
            results.append("created")

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive() and results == ["created"]


@pytest.mark.real_session
def test_forced_client_cleanup_waits_after_kill(monkeypatch):
    events = []

    class Client:
        pid = 123

        def poll(self):
            return None

        def wait(self, timeout=None):
            events.append(("wait", timeout))
            if len(events) == 1:
                raise SystemExit(143)
            if timeout:
                raise subprocess.TimeoutExpired("docker", timeout)
            return -signal.SIGKILL

        def send_signal(self, sig):
            events.append(("signal", sig))

        def kill(self):
            events.append(("kill",))

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: Client())
    with pytest.raises(SystemExit) as caught:
        c.docker_attached("exec")
    assert caught.value.code == 143
    assert events == [("wait", None), ("signal", signal.SIGHUP), ("wait", 5), ("kill",), ("wait", None)]


@pytest.mark.real_session
def test_creation_failure_restores_handlers_and_keeps_error(monkeypatch):
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}

    def failed(*args, **kwargs):
        raise FileNotFoundError("no docker")

    monkeypatch.setattr(subprocess, "Popen", failed)
    with pytest.raises(c.SandboxError, match="Cannot execute docker"):
        c.docker_attached("exec")
    assert {sig: signal.getsignal(sig) for sig in before} == before


@pytest.mark.real_session
def test_closed_terminal_restoration_does_not_replace_the_client_error(monkeypatch):
    attrs, restored = [1, 2, 3], []
    monkeypatch.setattr(c.sys, "stdin", SimpleNamespace(fileno=lambda: 91))
    monkeypatch.setattr(c.termios, "tcgetattr", lambda fd: attrs if fd == 91 else pytest.fail("wrong terminal"))

    def restore(fd, when, state):
        restored.append((fd, when, state))
        raise c.termios.error("terminal closed")

    def failed(*a, **k):
        raise FileNotFoundError("no docker")

    monkeypatch.setattr(c.termios, "tcsetattr", restore)
    monkeypatch.setattr(subprocess, "Popen", failed)
    with pytest.raises(c.SandboxError, match="Cannot execute docker"):
        c.docker_attached("exec")
    assert restored == [(91, c.termios.TCSANOW, attrs)]
