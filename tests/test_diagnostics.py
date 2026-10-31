"""Short diagnostics own their host clients; no real Docker or network is required."""
import json
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import diagnostics as d
from opencode_sandbox import opencode_versions as v
from opencode_sandbox import probes
from opencode_sandbox import runtime_identity as rid


@pytest.mark.real_session
def test_cancelled_diagnostic_does_not_wait_for_a_sleeping_host_client(tmp_path, monkeypatch):
    binary = tmp_path / "docker"
    binary.write_text("#!/bin/sh\nsleep 1\n")
    binary.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    started = time.monotonic()
    with c.runtime_feedback(cancelled=lambda: time.monotonic() - started > 0.1), pytest.raises(rid.Cancelled):
        c.docker("image", "inspect", "ocs-test-not-real", capture=True)
    assert time.monotonic() - started < 0.7


def python(code, *args):
    return [sys.executable, "-I", "-B", "-c", code, *map(str, args)]


def dead(pid):
    try:
        from pathlib import Path
        return Path(f"/proc/{pid}/stat").read_text().split(")", 1)[1].split()[0] == "Z"
    except (FileNotFoundError, ProcessLookupError):
        # procfs can lose the task between open and read: ENOENT and ESRCH both mean gone.
        return True


@pytest.mark.parametrize('error', [FileNotFoundError, ProcessLookupError, PermissionError])
def test_process_death_observation_distinguishes_disappearance_from_inaccessible_procfs(monkeypatch, error):
    from pathlib import Path
    def vanished(*args, **kwargs): raise error('owned procfs observation fixture')
    monkeypatch.setattr(Path, 'read_text', vanished)
    if error is PermissionError:
        with pytest.raises(PermissionError): dead(os.getpid())
    else: assert dead(os.getpid())


def test_running_process_is_not_a_dead_descendant():
    assert not dead(os.getpid())


@pytest.mark.parametrize("failure", ["timeout", "cancel", "overflow", "interrupt"])
def test_owned_host_process_and_its_descendants_are_terminated_and_reaped(tmp_path, monkeypatch, failure):
    marker = tmp_path / "child-pid"
    code = """
import subprocess,sys,time
from pathlib import Path
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
Path(sys.argv[1]).write_text(str(child.pid))
time.sleep(.1)
if sys.argv[2]=='overflow': print('x'*10000,flush=True)
time.sleep(30)
"""
    clients = []
    real_popen = d.subprocess.Popen
    def popen(*a, **k):
        p = real_popen(*a, **k)
        clients.append(p)
        return p
    monkeypatch.setattr(d.subprocess, "Popen", popen)
    start = time.monotonic()
    def cancelled():
        if failure == "interrupt" and marker.exists(): raise KeyboardInterrupt()
        return failure == "cancel" and marker.exists()
    error = d.Cancelled if failure == "cancel" else KeyboardInterrupt if failure == "interrupt" else d.Failure
    with pytest.raises(error):
        d.run(python(code, marker, failure), timeout=.35, max_output=1000, cancelled=cancelled)
    assert time.monotonic() - start < 1.5
    assert len(clients) == 1 and clients[0].returncode is not None
    assert marker.exists()
    pid = int(marker.read_text())
    until = time.monotonic() + 1
    while not dead(pid) and time.monotonic() < until: time.sleep(.01)
    assert dead(pid)


def test_inherited_pipe_after_direct_child_exit_cannot_evade_deadline(tmp_path):
    marker = tmp_path / "descendant"
    code = """
import subprocess,sys
from pathlib import Path
p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
Path(sys.argv[1]).write_text(str(p.pid))
"""
    with pytest.raises(d.Failure, match="timed out"):
        d.run(python(code, marker), timeout=.3)
    pid = int(marker.read_text())
    until = time.monotonic() + 1
    while not dead(pid) and time.monotonic() < until: time.sleep(.01)
    assert dead(pid)


def test_diagnostic_preserves_completed_process_output_exit_and_closed_stdin():
    p = d.run(python("import sys; print(repr(sys.stdin.read())); print('err',file=sys.stderr); sys.exit(7)"))
    assert p.returncode == 7 and p.stdout == "''\n" and p.stderr == "err\n"
    assert c.call(python("print('ok')"), capture=True, timeout=1).stdout == "ok\n"
    with pytest.raises(c.SandboxError, match=r"Command failed \(7\)"):
        c.call(python("raise SystemExit(7)"), capture=True, timeout=1)


def test_group_identity_is_reserved_until_after_cleanup_signal(monkeypatch):
    signalled = []
    real = os.killpg
    def killpg(pid, sig):
        # WNOWAIT observes without consuming the exited leader; it still reserves this PID/PGID.
        status = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        assert status is not None and status.si_pid == pid
        signalled.append(pid)
        real(pid, sig)
    monkeypatch.setattr(d.os, "killpg", killpg)
    assert d.run(python("print('ok')")).stdout == "ok\n"
    assert len(signalled) == 1
    with pytest.raises(ChildProcessError):
        os.waitid(os.P_PID, signalled[0], os.WEXITED | os.WNOHANG)


def test_pre_cancelled_and_expired_requests_launch_nothing(monkeypatch):
    monkeypatch.setattr(d.subprocess, "Popen", lambda *a, **k: pytest.fail("must not launch"))
    with pytest.raises(d.Cancelled): d.run(["unused"], cancelled=lambda: True)
    with pytest.raises(d.Failure, match="timed out"): d.run(["unused"], timeout=0)


def test_signal_during_client_creation_waits_until_ownership_is_registered(monkeypatch):
    clients = []
    real = d.subprocess.Popen
    def popen(*a, **k):
        p = real(*a, **k)
        clients.append(p)
        signal.raise_signal(signal.SIGINT)
        return p
    monkeypatch.setattr(d.subprocess, "Popen", popen)
    with pytest.raises(KeyboardInterrupt):
        c.call(python("import time; time.sleep(30)"), capture=True, timeout=1)
    assert len(clients) == 1 and clients[0].returncode is not None


def test_dns_block_in_http_child_is_bounded_by_the_parent():
    from pathlib import Path
    script = Path(v.__file__).with_name("http_probe.py")
    code = """
import runpy,socket,sys,time
socket.getaddrinfo=lambda *a,**k: time.sleep(30)
sys.argv=[sys.argv[1],'https://example.invalid/latest','1']
runpy.run_path(sys.argv[0],run_name='__main__')
"""
    started = time.monotonic()
    with pytest.raises(c.SandboxError, match="timed out"):
        c.call(python(code, script), capture=True, timeout=.3)
    assert time.monotonic() - started < 1


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_output_is_bounded_without_echoing_arguments_or_output(stream):
    with pytest.raises(c.SandboxError, match="output exceeds") as error:
        c.call(python(f"import sys; sys.{stream}.write('dummy-secret'*10000)", "dummy-argv"),
               capture=True, timeout=1, max_output=512)
    assert "dummy" not in str(error.value)


@pytest.mark.parametrize("args,bounded", [
    (("image", "inspect", "test"), True), (("container", "inspect", "test"), True),
    (("volume", "inspect", "test"), True), (("image", "ls"), True), (("ps",), True),
    (("stats", "--no-stream"), True), (("info",), True), (("system", "df"), True),
    (("build", "."), False), (("commit", "test", "test-copy"), False),
    (("exec", "test", "install"), False), (("run", "test"), False), (("stats",), False),
    (("start", "test"), False), (("stop", "test"), False),
])
def test_only_finite_read_only_docker_operations_get_automatic_bounds(monkeypatch, args, bounded):
    calls = []
    monkeypatch.setattr(c, "call", lambda argv, **k: calls.append((argv, k)) or SimpleNamespace(returncode=0))
    c.docker(*args, capture=True)
    assert (calls[0][1]["timeout"] is not None) == bounded
    assert calls[0][0][:3] == ["docker", "-H", c.docker_endpoint()]


def test_unbounded_mutations_keep_existing_subprocess_path(monkeypatch):
    calls = []
    monkeypatch.setattr(c.subprocess, "run", lambda argv, **k: calls.append(k) or SimpleNamespace(returncode=0))
    monkeypatch.setattr(d, "run", lambda *a, **k: pytest.fail("a long mutation must not use diagnostic runner"))
    c.docker_endpoint()  # successful acquisition before the ongoing mutation loses its UI worker
    with c.runtime_feedback(cancelled=lambda: True):
        c.docker("build", ".")
        c.docker("exec", "ocs-test", "npm", "install")
        c.docker("commit", "ocs-test", "ocs-test-image")
    assert len(calls) == 3 and all("timeout" not in k for k in calls)


@pytest.mark.parametrize("interruption", [c.SandboxError("Diagnostic timed out"), rid.Cancelled(), KeyboardInterrupt()])
@pytest.mark.parametrize("ownership", ["own", "missing", "foreign", "bad-json", "unavailable"])
def test_interrupted_helper_cleanup_is_bounded_and_immutable_label_checked(monkeypatch, interruption, ownership):
    removed, inspected = [], []
    full_id = "a" * 64
    def docker(*args, **kwargs):
        if args[0] == "run":
            assert "--pull" in args and args[args.index("--pull")+1] == "never"
            name = args[args.index("--name")+1]
            inspected.append(name)
            raise interruption
        assert c._RUNTIME_FEEDBACK.get()["cancelled"] is None
        assert c._DIAGNOSTIC_TIMEOUT.get() == probes.CLEANUP_TIMEOUT
        if args[:2] == ("container", "inspect"):
            assert args[-1] == inspected[0]
            token = inspected[0].removeprefix(probes.PREFIX)
            labels = {probes.LABEL: token, c.DATA_LABEL: c.data_id(), c.HELPER_LABEL: "diagnostic",
                      "org.opencode-sandbox.managed": "true"}
            if ownership == "foreign": labels[probes.LABEL] = "other"
            if ownership in ("missing", "unavailable"):
                return SimpleNamespace(returncode=1, stdout="", stderr="No such container: test" if ownership == "missing" else "daemon unavailable")
            return SimpleNamespace(returncode=0, stdout="bad" if ownership == "bad-json" else json.dumps([
                {"Id": full_id, "Config": {"Labels": labels}}]), stderr="")
        assert args == ("rm", "-f", full_id)
        removed.append(full_id)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(c, "docker", docker)
    expected = type(interruption) if ownership in ("own", "missing") else c.SandboxError
    with c.runtime_feedback(cancelled=lambda: True), pytest.raises(expected) as error:
        probes.image("ocs-test-image", "opencode", "--version")
    assert removed == ([full_id] if ownership == "own" else [])
    if ownership not in ("own", "missing"):
        assert "cleanup not confirmed" in str(error.value) and inspected[0] in str(error.value)


@pytest.mark.parametrize("code,stream", [(124, "stderr"), (137, "stderr"), (127, "stderr"), (127, "stdout")])
def test_container_probe_timeout_or_missing_tool_is_not_verified(monkeypatch, code, stream):
    m = c.create("ocs-test-probe", "scratch")
    calls = []
    def docker(*args, **kwargs):
        calls.append(args)
        data = {"stdout": "opencode v2.2.0", "stderr": ""}
        if code == 127: data[stream] = 'OCI runtime exec failed: exec: "timeout": executable file not found'
        return SimpleNamespace(returncode=code, **data)
    monkeypatch.setattr(c, "docker", docker)
    with pytest.raises(c.SandboxError, match="timed out|unavailable"):
        probes.exec(m, "opencode", "--version")
    assert calls == [("exec", c.cname(m), "timeout", "--signal=KILL", "5s", "opencode", "--version")]


def test_total_http_budget_includes_slow_drip_body(monkeypatch):
    done = threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            try:
                for _ in range(100):
                    self.wfile.write(b" "); self.wfile.flush()
                    if done.wait(.04): break
            except (BrokenPipeError, ConnectionResetError): pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    monkeypatch.setattr(v, "REGISTRY", f"http://127.0.0.1:{server.server_port}/latest")
    started = time.monotonic()
    try:
        with pytest.raises(c.SandboxError, match="Cannot check.*timed out"):
            v.latest(timeout=.3)
        assert time.monotonic() - started < 1
    finally:
        done.set(); server.shutdown(); server.server_close(); thread.join(2)
