"""D-052: bounded acquisition and kernel-authenticated response-sender identity.

Host UNIX sockets are real; dockerd executable/namespace evidence is explicitly mocked.
Real activated dockerd coverage belongs to the opt-in campaign, not these tests.
"""
import asyncio
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from contextlib import contextmanager

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import runtime_identity as rid

pytestmark = pytest.mark.real_identity


def response(options=None):
    body = json.dumps({"SecurityOptions": options if options is not None else ["name=rootless"]}).encode()
    return b"HTTP/1.0 200 OK\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body


@contextmanager
def server(tmp_path, payload=None, delay=0, count=1):
    path = tmp_path / "d.sock"
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(path))
    listener.listen(8)
    listener.settimeout(2)
    done = threading.Event()
    errors = []

    def serve():
        try:
            for i in range(count):
                conn, _ = listener.accept()
                with conn:
                    conn.settimeout(2)
                    if conn.recv(4096):
                        if done.wait(delay): return
                        conn.sendall(response() if payload is None else payload(i) if callable(payload) else payload)
        except (BrokenPipeError, ConnectionResetError):
            pass  # cancellation closes only the manager's connection
        except OSError as exc:
            if not done.is_set(): errors.append(exc)

    thread = threading.Thread(target=serve)
    thread.start()
    try:
        yield f"unix://{path}"
    finally:
        done.set()
        listener.close()
        thread.join(3)
        assert not thread.is_alive() and not errors


def valid_sender(monkeypatch):
    seen = []

    def inspect(pid, uid, gid, **kwargs):
        seen.append((pid, uid, gid))
        return None, [], "/usr/bin/dockerd", []

    monkeypatch.setattr(rid, "inspect_peer", inspect)
    return seen


def test_delayed_authenticated_response_succeeds_without_cli_engine_probe(tmp_path, monkeypatch):
    seen = valid_sender(monkeypatch)
    notices = []
    with server(tmp_path, delay=0.35) as endpoint:
        ident = rid.verify(endpoint=endpoint, timeout=1, progress=notices.append)
    assert ident.verified and ident.pid == os.getpid()
    assert (os.getpid(), os.getuid(), os.getgid()) in seen
    assert len(notices) == 1 and "Waiting for Docker readiness" in notices[0]


def test_ready_first_attempt_has_no_wait_notice(tmp_path, monkeypatch):
    valid_sender(monkeypatch)
    with server(tmp_path) as endpoint:
        ident = rid.verify(endpoint=endpoint, progress=lambda _: pytest.fail("ready fast path"))
    assert ident.verified


def test_response_timeout_is_one_total_budget(tmp_path, monkeypatch):
    valid_sender(monkeypatch)
    start = time.monotonic()
    with server(tmp_path, delay=1) as endpoint:
        ident = rid.verify(endpoint=endpoint, timeout=0.2)
    assert ident.classification == rid.UNAVAILABLE
    assert "0.2" in ident.message() and "deadline" in ident.message()
    assert time.monotonic() - start < 0.7


def test_cancellation_during_response_does_not_become_identity_failure(tmp_path, monkeypatch):
    valid_sender(monkeypatch)
    start = time.monotonic()
    with server(tmp_path, delay=1) as endpoint, pytest.raises(rid.Cancelled):
        rid.verify(endpoint=endpoint, cancelled=lambda: time.monotonic() - start > 0.15)
    assert time.monotonic() - start < 0.7


def test_rootless_looking_response_from_python_is_not_identity(tmp_path):
    with server(tmp_path) as endpoint:
        ident = rid.verify(endpoint=endpoint, timeout=1)
    assert ident.classification == rid.UNVERIFIED_PROXY and not ident.verified


@pytest.mark.parametrize("options", [[], ["name=not-rootless"], "name=rootless", None])
def test_rootless_option_is_structured_and_exact(tmp_path, monkeypatch, options):
    valid_sender(monkeypatch)
    payload = response(options) if options is not None else b'HTTP/1.0 200 OK\r\n\r\n{}'
    with server(tmp_path, payload) as endpoint:
        ident = rid.verify(endpoint=endpoint, timeout=1)
    assert ident.classification == rid.MISMATCH


@pytest.mark.parametrize("payload", [
    b"HTTP/1.0 500 Error\r\n\r\n{}", b"nonsense", b"HTTP/1.0 200 OK\r\n\r\nnot-json",
    b"HTTP/1.0 200 OK\r\nContent-Length: 0\r\n\r\n{}",
    b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}",
    b"HTTP/1.0 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
    b"HTTP/1.0 200 OK\r\nContent-Encoding: gzip\r\n\r\n{}",
    b"HTTP/1.0 200 OK\r\nbroken\r\n\r\n{}", b"x" * 17000,
    b"HTTP/1.0 200 OK\r\nContent-Length: " + b"9" * 5000 + b"\r\n\r\n{}",
])
def test_malformed_or_error_response_is_not_retried(tmp_path, monkeypatch, payload):
    valid_sender(monkeypatch)
    with server(tmp_path, payload) as endpoint:
        ident = rid.verify(endpoint=endpoint, timeout=1)
    assert ident.classification == rid.UNAVAILABLE


def test_interrupted_transport_retries_full_identity(tmp_path, monkeypatch):
    valid_sender(monkeypatch)
    with server(tmp_path, lambda i: b"" if i == 0 else response(), count=2) as endpoint:
        ident = rid.verify(endpoint=endpoint, timeout=1)
    assert ident.verified


def test_transient_then_wrong_sender_is_a_prompt_permanent_failure(tmp_path):
    start = time.monotonic()
    with server(tmp_path, lambda i: b"" if i == 0 else response(), count=2) as endpoint:
        ident = rid.verify(endpoint=endpoint, timeout=1)
    assert ident.classification == rid.UNVERIFIED_PROXY and time.monotonic() - start < 0.7


@pytest.mark.parametrize("error", [PermissionError(13, "denied"), ConnectionRefusedError(111, "refused"),
                                  FileNotFoundError(2, "gone")])
def test_permanent_transport_errors_do_not_retry(tmp_path, monkeypatch, error):
    path = tmp_path / "s"
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(path))
        calls = []

        def fail(*a, **k):
            calls.append(a)
            raise error

        monkeypatch.setattr(rid, "peer_credentials", fail)
        monkeypatch.setattr(rid.Budget, "pause", lambda *a: pytest.fail("permanent error retried"))
        ident = rid.verify(endpoint=f"unix://{path}")
    assert ident.classification == rid.UNAVAILABLE and len(calls) == 1


def test_endpoint_is_canonicalized_and_context_resolved_only_once(tmp_path, monkeypatch):
    valid_sender(monkeypatch)
    calls = []
    with server(tmp_path, lambda i: b"" if i == 0 else response(), count=2) as endpoint:
        link = tmp_path / "link.sock"
        link.symlink_to(endpoint.removeprefix("unix://"))

        def resolve(*a, **k):
            calls.append(a)
            return f"unix://{link}", None, ""

        monkeypatch.setattr(rid, "resolve_context", resolve)
        original = rid.peer_credentials

        def connect(path, **k):
            link.unlink(missing_ok=True)
            link.symlink_to(tmp_path / "evil.sock")
            return original(path, **k)

        monkeypatch.setattr(rid, "peer_credentials", connect)
        ident = rid.verify("ocs-test", timeout=1)
    assert ident.verified and ident.endpoint == endpoint and len(calls) == 1


def test_inherited_listener_checks_actual_child_not_creator(tmp_path, monkeypatch):
    path = tmp_path / "i.sock"
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(path)); listener.listen(4)
        code = """import socket,sys,time
s=socket.socket(fileno=int(sys.argv[1]))
c,_=s.accept()
with c:
 c.recv(4096)
 c.sendall(bytes.fromhex(sys.argv[2]))
 time.sleep(.2)
"""
        child = subprocess.Popen([sys.executable, "-I", "-c", code, str(listener.fileno()), response().hex()],
                                 pass_fds=(listener.fileno(),))
        try:
            def inspect(pid, uid, gid, **k):
                if pid == child.pid: return None, [], "/usr/bin/dockerd", []
                return rid.UNVERIFIED_PROXY, ["listener creator is not dockerd"], "/usr/lib/systemd", []

            monkeypatch.setattr(rid, "inspect_peer", inspect)
            ident = rid.verify(endpoint=f"unix://{path}", timeout=1)
            assert ident.verified and ident.pid == child.pid != os.getpid()
        finally:
            child.wait(timeout=2)


@pytest.mark.parametrize("creds,flags", [([], 0), ([(0, 1, b"bad")], 0),
                                      ([(socket.SOL_SOCKET, socket.SCM_CREDENTIALS, struct.pack("3i", os.getpid(), os.getuid(), os.getgid()))], socket.MSG_CTRUNC)])
def test_missing_or_truncated_sender_credentials_are_refused(monkeypatch, creds, flags):
    class Connection:
        def settimeout(self, n): pass
        def send(self, data): return len(data)
        def recvmsg(self, *a): return response(), creds, flags, None

    valid_sender(monkeypatch)
    with pytest.raises(rid.SenderError):
        rid._response(Connection(), rid.Budget(1), None)


def test_exiting_sender_cannot_verify_after_response(tmp_path, monkeypatch):
    calls = []

    def inspect(*a, **k):
        calls.append(a)
        if len(calls) < 3: return None, [], "/usr/bin/dockerd", []
        return rid.UNVERIFIED_PROXY, ["cannot read the peer executable"], None, []

    monkeypatch.setattr(rid, "inspect_peer", inspect)
    with server(tmp_path) as endpoint:
        ident = rid.verify(endpoint=endpoint)
    assert ident.classification == rid.UNVERIFIED_PROXY


def test_context_lookup_consumes_the_same_budget_and_reaps_child(tmp_path):
    script = tmp_path / "docker"
    script.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
    script.chmod(0o700)
    started = time.monotonic()
    ident = rid.verify("ocs-test", docker=str(script), timeout=0.2)
    assert ident.classification == rid.UNAVAILABLE and "deadline" in ident.message()
    assert time.monotonic() - started < 0.7


def test_concurrent_acquisitions_share_only_the_inflight_result(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    results, calls = [], []

    def verify(context, endpoint=None, **k):
        calls.append(endpoint)
        entered.set()
        assert release.wait(2)
        return rid.Identity(rid.VERIFIED, context, "unix:///ocs-test.sock")

    monkeypatch.setattr(rid, "verify", verify)
    one = threading.Thread(target=lambda: results.append(c.verify_runtime()))
    two = threading.Thread(target=lambda: results.append(c.verify_runtime()))
    one.start(); assert entered.wait(1)
    two.start()
    time.sleep(.1)
    release.set()
    one.join(2); two.join(2)
    assert len(results) == 2 and calls == [None]
    assert c.verify_runtime().verified and calls == [None, "unix:///ocs-test.sock"]


def test_repeated_transient_uses_one_monotonic_budget(tmp_path, monkeypatch):
    clock = [0.0]
    sleeps, attempts, notices = [], [], []
    monkeypatch.setattr(rid.time, "monotonic", lambda: clock[0])

    def sleep(n):
        assert 0 < n <= .1
        sleeps.append(n); clock[0] += n

    def connect(*a, **k):
        attempts.append(clock[0])
        raise ConnectionResetError("initializing")

    monkeypatch.setattr(rid.time, "sleep", sleep)
    monkeypatch.setattr(rid, "peer_credentials", connect)
    with socket.socket(socket.AF_UNIX) as listener:
        path = tmp_path / "s"
        listener.bind(str(path))
        ident = rid.verify(endpoint=f"unix://{path}", timeout=1, progress=notices.append)
    assert ident.classification == rid.UNAVAILABLE and "initializing" in ident.message()
    assert clock[0] == pytest.approx(1) and len(notices) == 1 and len(attempts) >= 3


def test_response_size_is_bounded(tmp_path, monkeypatch):
    valid_sender(monkeypatch)
    with server(tmp_path, b"HTTP/1.0 200 OK\r\n\r\n" + b"x" * rid.MAX_RESPONSE) as endpoint:
        ident = rid.verify(endpoint=endpoint)
    assert ident.classification == rid.UNAVAILABLE and "512 KiB" in ident.message()


def test_response_sender_cannot_change_between_chunks(monkeypatch):
    valid_sender(monkeypatch)
    packets = iter([(b"HTTP/1.0 200 OK\r\n", os.getpid()), (b"\r\n{}", os.getpid() + 1)])

    class Connection:
        def settimeout(self, n): pass
        def send(self, data): return len(data)
        def recvmsg(self, *a):
            data, pid = next(packets)
            return data, [(socket.SOL_SOCKET, socket.SCM_CREDENTIALS,
                           struct.pack("3i", pid, os.getuid(), os.getgid()))], 0, None

    with pytest.raises(rid.SenderError, match="sender changed"):
        rid._response(Connection(), rid.Budget(1), None)


def test_unexpected_rights_are_closed_and_refused(tmp_path):
    original = os.open(tmp_path / "dummy", os.O_CREAT | os.O_RDONLY, 0o600)
    received = os.dup(original)

    class Connection:
        def settimeout(self, n): pass
        def send(self, data): return len(data)
        def recvmsg(self, *a):
            return response(), [(socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack("i", received))], 0, None

    try:
        with pytest.raises(rid.SenderError, match="file descriptors"):
            rid._response(Connection(), rid.Budget(1), None)
        with pytest.raises(OSError): os.fstat(received)
    finally:
        os.close(original)


def test_pid_reuse_during_response_is_refused(tmp_path, monkeypatch):
    valid_sender(monkeypatch)
    tokens = iter(["old-process", "different-process"])
    monkeypatch.setattr(rid, "_process_token", lambda *a: next(tokens))
    with server(tmp_path) as endpoint:
        ident = rid.verify(endpoint=endpoint)
    assert ident.classification == rid.UNVERIFIED_PROXY and "process changed" in ident.message()


def test_canceled_connect_closes_the_newly_created_socket(tmp_path):
    before = len(os.listdir("/proc/self/fd"))
    with pytest.raises(rid.Cancelled):
        rid.peer_credentials(str(tmp_path / "unused.sock"), budget=rid.Budget(cancelled=lambda: True))
    assert len(os.listdir("/proc/self/fd")) == before


def test_dashboard_success_clears_only_its_own_warning(monkeypatch):
    from opencode_sandbox import readiness, tui

    calls = []
    monkeypatch.setattr(readiness, "image_checks", list)

    def verify(context, endpoint=None, budget=None):
        calls.append(endpoint)
        if len(calls) == 1: return rid.Identity(rid.UNAVAILABLE, context, reasons=("offline",))
        budget.pause(.35)
        return rid.Identity(rid.VERIFIED, context, "unix:///ocs-test.sock")

    monkeypatch.setattr(rid, "verify", verify)

    async def scenario():
        app = tui.Dashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(); await asyncio.sleep(.15)
            app.notify("Keep this unrelated notice", title="Other")
            await pilot.press("r")
            await asyncio.sleep(.5); await pilot.pause()
            assert not [n for n in app._notifications if n.title in ("Docker is not ready", "Docker readiness")]
            assert any(n.title == "Other" for n in app._notifications)
            assert "Ready" in str(app.query_one("#status").render())

    asyncio.run(scenario())


def test_cli_wait_feedback_is_stderr_and_final_report_is_stdout(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from opencode_sandbox import cli, readiness

    valid_sender(monkeypatch)
    monkeypatch.setattr(readiness, "host_checks", list)
    monkeypatch.setattr(readiness, "image_checks", list)
    monkeypatch.setattr(readiness, "storage_check", lambda: readiness.Check("storage", "storage", readiness.NOT_CHECKED, "test"))
    monkeypatch.setattr(c, "docker", lambda *a, **k: type("Result", (), {"returncode": 1})())
    with server(tmp_path, delay=.35) as endpoint:
        monkeypatch.setattr(c, "_ENDPOINT", endpoint)
        result = CliRunner().invoke(cli.app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "Daemon identity: verified" in result.stdout and "Waiting" not in result.stdout
    assert result.stderr.count("Waiting for Docker readiness") == 1


def test_dashboard_wait_navigation_refresh_and_quit_are_responsive(monkeypatch):
    from opencode_sandbox import readiness, tui

    calls, canceled = [], threading.Event()
    monkeypatch.setattr(readiness, "image_checks", list)

    def verify(context, endpoint=None, budget=None):
        calls.append(endpoint)
        if len(calls) == 1:
            return rid.Identity(rid.UNAVAILABLE, context, reasons=("offline",))
        try:
            budget.pause(30)
        except rid.Cancelled:
            canceled.set()
            raise

    monkeypatch.setattr(rid, "verify", verify)

    async def scenario():
        app = tui.Dashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(); await asyncio.sleep(.15)
            assert "Docker is not ready" in str(app.query_one("#status").render())
            await pilot.press("r")
            await asyncio.sleep(.4); await pilot.pause()
            assert "Waiting for Docker readiness" in str(app.query_one("#status").render())
            await pilot.press("/")
            assert app.focused.id == "search"
            app.exit()
        assert canceled.wait(1)
        assert len(calls) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
def test_cli_signal_during_context_probe_reaps_child_and_keeps_data(tmp_path, sig):
    tools = tmp_path / "bin"
    tools.mkdir()
    pidfile = tmp_path / "child.pid"
    docker = tools / "docker"
    docker.write_text(f'''#!{sys.executable}
import os,sys,time
from pathlib import Path
if '--version' in sys.argv:
 print('Docker test')
else:
 Path({str(pidfile)!r}).write_text(str(os.getpid()))
 time.sleep(30)
''')
    docker.chmod(0o700)
    root = os.path.dirname(os.path.dirname(__file__))
    env = {**os.environ, "PATH": f"{tools}:{os.environ['PATH']}", "PYTHONPATH": f"{root}/src",
           "OPENCODE_SANDBOX_HOME": str(tmp_path / "data"), "OPENCODE_SANDBOX_CONFIG": str(tmp_path / "config")}
    proc = subprocess.Popen([sys.executable, "-m", "opencode_sandbox.cli", "doctor"], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        end = time.monotonic() + 5
        while (not pidfile.exists() or not pidfile.stat().st_size) and time.monotonic() < end:
            time.sleep(.01)
        assert pidfile.exists(), proc.poll()
        child_pid = int(pidfile.read_text())
        proc.send_signal(sig)
        out, err = proc.communicate(timeout=2)
        assert proc.returncode != 0 and "Traceback" not in out + err
        with pytest.raises(ProcessLookupError): os.kill(child_pid, 0)
        assert not (tmp_path / "data" / "environments").exists()
    finally:
        if proc.poll() is None: proc.kill()
        proc.communicate(timeout=2)
