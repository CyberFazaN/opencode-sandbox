"""A managed session whose host client goes away (terminal closed) is hung up
inside the container instead of running on unattended."""
import os
import pty
import signal
import subprocess
import termios
import time
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c


@pytest.fixture
def env(monkeypatch):
    m = c.create("ocs-qa-hup", "scratch")
    monkeypatch.setattr(c, "start", lambda m: None)
    monkeypatch.setattr(c, "observed_runtime", lambda m: None)
    monkeypatch.setattr(c, "image_definition", lambda m, **k: None)  # session fixture: provenance uninspected
    monkeypatch.setattr(c, "_tty", lambda: True)
    monkeypatch.setattr(c, "profile_mismatch", lambda m: None)
    return m


def recorder(calls, launch):
    def docker(*a, **k):
        calls.append(a)
        if a[0] == "exec" and "-it" in a:
            return launch()
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return docker


def hangups(calls):
    return [a for a in calls if a[0] == "exec" and "ocs-hangup" in a]


def test_signal_while_running_hangs_up_exactly_this_session(env, monkeypatch):
    calls = []
    def interrupted():
        raise SystemExit(128 + signal.SIGHUP)  # what cli._exit_on_signal raises on SIGHUP
    monkeypatch.setattr(c, "docker", recorder(calls, interrupted))
    with pytest.raises(SystemExit):
        c.interactive(env)
    token = calls[0][-1]
    assert len(token) == 16 and hangups(calls) == [("exec", c.cname(env), "sh", "-c", c.HANGUP, "ocs-hangup", token)]


def test_killed_docker_client_hangs_up(env, monkeypatch):
    calls = []
    monkeypatch.setattr(c, "docker", recorder(calls, lambda: SimpleNamespace(returncode=-9)))
    assert c.interactive(env) == -9 and len(hangups(calls)) == 1


@pytest.mark.parametrize("rc", [0, 1, 130])
def test_normal_exit_sends_nothing(env, monkeypatch, rc):
    calls = []
    monkeypatch.setattr(c, "docker", recorder(calls, lambda: SimpleNamespace(returncode=rc)))
    assert c.interactive(env) == rc and hangups(calls) == []


def test_hangup_failure_does_not_mask_the_exit(env, monkeypatch):
    def docker(*a, **k):
        if "ocs-hangup" in a:
            raise c.SandboxError("daemon gone")
        raise KeyboardInterrupt
    monkeypatch.setattr(c, "docker", docker)
    with pytest.raises(KeyboardInterrupt):
        c.interactive(env)


def test_hangup_script_signals_only_processes_with_the_token():
    """Runs the real script against this host's /proc with uniquely tagged children."""
    token = os.urandom(8).hex()
    tagged = subprocess.Popen(["sleep", "60"], env={"PATH": "/usr/bin:/bin", "OCS_RUN_TOKEN": token})
    other = subprocess.Popen(["sleep", "60"], env={"PATH": "/usr/bin:/bin", "OCS_RUN_TOKEN": token + "0"})
    immune = subprocess.Popen(["nohup", "sleep", "60"], env={"PATH": "/usr/bin:/bin", "OCS_RUN_TOKEN": token},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.3)
        assert subprocess.run(["sh", "-c", c.HANGUP, "ocs-hangup", token], check=False).returncode == 0
        assert tagged.wait(timeout=5) == -signal.SIGHUP
        time.sleep(0.3)
        assert other.poll() is None and immune.poll() is None  # other sessions and nohup jobs survive
    finally:
        for p in (tagged, other, immune):
            p.kill()
            p.wait()


# The manager process itself is SIGKILLed (no cleanup runs). Real processes: this
# test's manager is a child Python process, the docker client a fake `docker` script on PATH.
FAKE_DOCKER = """#!/bin/sh
echo "$*" >> "$OCS_FAKE_LOG"
case "$*" in *ocs-hangup*) exit 0;; esac
case "$*" in *" exec -it "*)
  [ -n "$OCS_FAKE_RAW" ] && stty raw -echo
  [ -n "$OCS_FAKE_QUICK" ] && exit 0
  sleep 60 & child=$!
  trap 'echo client-hangup >> "$OCS_FAKE_LOG"; kill $child; exit 129' HUP
  echo client-started >> "$OCS_FAKE_LOG"; wait $child; exit 0;;
esac
exit 0
"""

MANAGER = """import sys
from pathlib import Path
from opencode_sandbox import core as c, integrations as ig
c.BASE = Path(sys.argv[1]) / "data"; c.CONFIG = Path(sys.argv[1]) / "config"
c._ENDPOINT = "unix:///nonexistent/ocs-test.sock"
for name in ("start", "observed_runtime", "profile_mismatch"):
    setattr(c, name, lambda m: None)
c._tty = lambda: True
from opencode_sandbox import agent_context
agent_context.refresh = lambda *a, **k: None
c.guidance_inputs = lambda m, **k: {}
import signal
from opencode_sandbox.cli import _exit_on_signal
signal.signal(signal.SIGTERM, _exit_on_signal)
signal.signal(signal.SIGHUP, _exit_on_signal)
m = c.create("ocs-qa-wd", "scratch", provisioning=ig.request([]))
sys.exit(c.interactive(m))
"""


LAUNCH_SIGNAL = '''
# Interrupt _fork_exec before Popen stores its returned PID. The child is already running,
# just as in the captured failure; waiting for its trap makes the ordering deterministic.
import os, time, subprocess
original_fork = subprocess._fork_exec
def interrupted_fork(*args, **kwargs):
    pid = original_fork(*args, **kwargs)
    if "-it" in args[0]:
        log = Path(os.environ["OCS_FAKE_LOG"])
        deadline = time.monotonic() + 10
        while not (log.exists() and "client-started" in log.read_text()):
            if time.monotonic() >= deadline:
                raise RuntimeError("fake client startup timed out")
            time.sleep(.01)
        Path(sys.argv[1], "launch-pid").write_text(str(pid))
        os.kill(os.getpid(), int(os.environ["OCS_FAKE_LAUNCH_SIGNAL"]))
    return pid
subprocess._fork_exec = interrupted_fork
'''


def _manager(tmp_path, monkeypatch, quick=False, launch_signal=None, raw_terminal=False, stdin=subprocess.DEVNULL):
    import sys
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "docker").write_text(FAKE_DOCKER)
    (bin_dir / "docker").chmod(0o755)
    log = tmp_path / "docker.log"
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "OCS_FAKE_LOG": str(log),
           **({"OCS_FAKE_QUICK": "1"} if quick else {}),
           **({"OCS_FAKE_RAW": "1"} if raw_terminal else {}),
           **({"OCS_FAKE_LAUNCH_SIGNAL": str(launch_signal)} if launch_signal else {})}
    code = MANAGER.replace('m = c.create', LAUNCH_SIGNAL + '\nm = c.create') if launch_signal else MANAGER
    proc = subprocess.Popen([sys.executable, "-c", code, str(tmp_path)], env=env, stdin=stdin)
    return proc, log


def _wait_for(log, text, seconds=10):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if log.exists() and text in log.read_text():
            return True
        time.sleep(0.05)
    return False


@pytest.mark.real_session
def test_sigkilled_manager_hangs_up_client_and_session(tmp_path, monkeypatch):
    proc, log = _manager(tmp_path, monkeypatch)
    try:
        assert _wait_for(log, "client-started")
        proc.kill()  # SIGKILL: no Python cleanup in the manager
        proc.wait()
        assert _wait_for(log, "ocs-hangup") and _wait_for(log, "client-hangup")
        text = log.read_text()
        hangup = next(x for x in text.splitlines() if "ocs-hangup" in x)
        token = hangup.split()[-1]
        assert len(token) == 16 and text.count(token) == 2  # the token of exactly this session
        assert next(x for x in text.splitlines() if " exec -it " in x).startswith("-H unix:///nonexistent/ocs-test.sock exec -it")
        assert "-H unix:///nonexistent/ocs-test.sock exec ocs-" in text
        time.sleep(0.5)
        assert _watchdogs() == []
    finally:
        if proc.poll() is None:
            proc.kill()


@pytest.mark.real_session
def test_normal_end_leaves_no_watchdog_and_sends_no_hangup(tmp_path, monkeypatch):
    proc, log = _manager(tmp_path, monkeypatch, quick=True)
    assert proc.wait(timeout=20) == 0
    time.sleep(0.5)
    text = log.read_text()
    assert " exec -it " in text and "ocs-hangup" not in text
    assert _watchdogs() == []


def _watchdogs():
    from pathlib import Path
    found = []
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            argv = cmdline.read_bytes().split(b"\0")
        except OSError:
            continue
        if argv[1:4] == [b"-I", b"-c", c.WATCHDOG.encode()]:
            found.append(cmdline.parent.name)
    return found


@pytest.mark.real_session
def test_sigterm_ends_the_client_and_hangs_up_once(tmp_path, monkeypatch):
    proc, log = _manager(tmp_path, monkeypatch)
    try:
        assert _wait_for(log, "client-started")
        proc.terminate()
        assert proc.wait(timeout=20) == 128 + signal.SIGTERM
        assert _wait_for(log, "client-hangup") and _wait_for(log, "ocs-hangup")
        time.sleep(0.5)
        assert log.read_text().count("ocs-hangup") == 1 and _watchdogs() == []  # the watchdog was told "done"
    finally:
        if proc.poll() is None:
            proc.kill()


@pytest.mark.real_session
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGHUP, signal.SIGINT])
def test_signal_during_client_creation_reaps_client_and_hangs_up_once(tmp_path, monkeypatch, sig):
    proc, log = _manager(tmp_path, monkeypatch, launch_signal=sig)
    try:
        rc = proc.wait(timeout=20)
        assert rc == (-signal.SIGINT if sig == signal.SIGINT else 128 + sig)
        assert _wait_for(log, "client-hangup") and _wait_for(log, "ocs-hangup")
        assert log.read_text().count("ocs-hangup") == 1
        pid = int((tmp_path / "launch-pid").read_text())
        assert not os.path.exists(f"/proc/{pid}")  # reaped, not just signaled
        assert _watchdogs() == []
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        # A failing pre-fix regression must not leave the intentionally orphaned fake client.
        path = tmp_path / "launch-pid"
        if path.exists():
            pid = int(path.read_text())
            try:
                from pathlib import Path
                environ = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
                if os.fsencode(f"OCS_FAKE_LOG={log}") in environ:
                    os.kill(pid, signal.SIGHUP)
            except OSError:
                pass


@pytest.mark.real_session
@pytest.mark.parametrize("sig", [None, signal.SIGTERM, signal.SIGHUP])
def test_client_terminal_modes_are_restored(tmp_path, monkeypatch, sig):
    """A client may exit without undoing raw mode; the manager owns terminal restoration."""
    master, slave = pty.openpty()
    before = termios.tcgetattr(slave)
    proc = None
    try:
        proc, log = _manager(tmp_path, monkeypatch, quick=sig is None, raw_terminal=True, stdin=slave)
        if sig is not None:
            assert _wait_for(log, "client-started")
            assert termios.tcgetattr(slave) != before
            proc.send_signal(sig)
        assert proc.wait(timeout=20) == (128 + sig if sig is not None else 0)
        assert termios.tcgetattr(slave) == before
    finally:
        if proc is not None:
            if proc.poll() is None: proc.kill()
            proc.wait()
        os.close(slave)
        os.close(master)
