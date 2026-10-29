"""D-003: Docker endpoint and daemon identity classification (mocked /proc and Docker CLI;
the SO_PEERCRED path uses real UNIX sockets served by this test process)."""
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import runtime_identity as rid

ROOT = Path(__file__).resolve().parents[1]
UID, GID = os.getuid(), os.getgid()
pytestmark = pytest.mark.real_identity


def fake_proc(tmp_path, *, pid=4242, exe="/usr/bin/dockerd", peer_ns="user:[2]", own_ns="user:[1]",
              uid_map=None, gid_map=None):
    proc = tmp_path / "proc"
    base = proc / str(pid)
    (base / "ns").mkdir(parents=True)
    (proc / "self" / "ns").mkdir(parents=True)
    if exe is not None:
        (base / "exe").symlink_to(exe)
    (base / "ns" / "user").symlink_to(peer_ns)
    (proc / "self" / "ns" / "user").symlink_to(own_ns)
    (base / "uid_map").write_text(uid_map if uid_map is not None else f"         0       {UID}          1\n         1     100000      65536\n")
    (base / "gid_map").write_text(gid_map if gid_map is not None else f"         0       {GID}          1\n         1     100000      65536\n")
    return proc


def context_json(host, tls=None):
    return json.dumps({"Name": "x", "Endpoints": {"docker": {"Host": host, "SkipTLSVerify": False}},
                       "TLSMaterial": tls or {}})


# --- context resolution ---------------------------------------------------------------------

@pytest.mark.parametrize("host", ["tcp://127.0.0.1:2375", "ssh://user@host", "npipe:////./pipe/docker_engine", ""])
def test_non_unix_endpoints_are_unsupported(monkeypatch, host):
    monkeypatch.setattr(rid, "_docker", lambda argv, docker="docker": (context_json(host), None))
    ident = rid.verify("ocs-test")
    assert ident.classification == rid.UNSUPPORTED and not ident.verified
    assert "not a local unix://" in ident.message()


def test_tls_context_is_unsupported(monkeypatch):
    monkeypatch.setattr(rid, "_docker", lambda argv, docker="docker": (
        context_json("unix:///run/user/1/docker.sock", {"docker": ["ca.pem"]}), None))
    assert rid.verify("ocs-test").classification == rid.UNSUPPORTED


@pytest.mark.parametrize("answer", ['context "nope": context not found: open /x/meta.json: no such file or directory',
                                    'context "nope" does not exist'])
def test_missing_context_is_not_configured(monkeypatch, answer):
    """A configuration error, not a stopped daemon: the hint says how to create the context."""
    monkeypatch.setattr(rid, "_docker", lambda argv, docker="docker": (None, answer))
    ident = rid.verify("nope")
    assert ident.classification == rid.NOT_CONFIGURED and ident.reasons == ("Docker context 'nope' does not exist",)
    assert "dockerd-rootless-setuptool.sh install" in ident.message() and "systemctl" not in ident.message()


def test_missing_docker_cli_is_missing():
    assert rid._docker(["version"], docker="/nonexistent/ocs-test-docker") == (None, rid.CLI_NOT_FOUND)
    ident = rid.verify("x", docker="/nonexistent/ocs-test-docker")
    assert ident.classification == rid.MISSING and "not installed" in ident.reasons[0]
    assert "pacman -S docker" in ident.message()


def test_other_context_errors_stay_unavailable(monkeypatch):
    monkeypatch.setattr(rid, "_docker", lambda argv, docker="docker": (None, "permission denied"))
    ident = rid.verify("x")
    assert ident.classification == rid.UNAVAILABLE and "permission denied" in ident.reasons[0]


def test_unreadable_context_json_is_not_configured(monkeypatch):
    monkeypatch.setattr(rid, "_docker", lambda argv, docker="docker": ("not json", None))
    assert rid.verify("x").classification == rid.NOT_CONFIGURED


def test_every_classification_has_a_distinct_exit_code_and_a_hint():
    codes = list(rid.EXIT_CODES.values())
    assert len(set(codes)) == len(codes) and rid.EXIT_CODES[rid.VERIFIED] == 0
    assert not {1, 2} & set(codes)  # 1: a check failed or declined, 2: usage or operation error
    assert set(rid.HINTS) == set(rid.EXIT_CODES) - {rid.VERIFIED}


def test_relative_socket_path_is_unsupported():
    assert rid.verify("x", endpoint="unix://docker.sock").classification == rid.UNSUPPORTED


def test_context_name_comes_from_environment(monkeypatch):
    seen = []
    monkeypatch.setenv("OPENCODE_SANDBOX_DOCKER_CONTEXT", "ocs-test-ctx")
    monkeypatch.setattr(rid, "_docker", lambda argv, docker="docker": seen.append(argv) or (None, "nope"))
    assert rid.verify().context == "ocs-test-ctx" and seen[0][-1] == "ocs-test-ctx"


def test_docker_host_and_context_variables_are_noted_and_dropped(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://evil:2375")
    monkeypatch.setenv("DOCKER_CONTEXT", "other")
    monkeypatch.setenv("DOCKER_TLS_VERIFY", "1")
    monkeypatch.setattr(rid, "_docker", lambda argv, docker="docker": (None, "nope"))
    ident = rid.verify("rootless")
    assert any("DOCKER_HOST is set but ignored" in n for n in ident.notes)
    env = rid.docker_env()
    assert not {"DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY"} & env.keys()


# --- socket and peer --------------------------------------------------------------------------

def test_missing_socket_is_unavailable(tmp_path):
    ident = rid.verify("x", endpoint=f"unix://{tmp_path}/absent.sock")
    assert ident.classification == rid.UNAVAILABLE and "does not exist" in ident.reasons[0]


def test_regular_file_is_unsupported(tmp_path):
    (tmp_path / "file.sock").write_text("")
    assert rid.verify("x", endpoint=f"unix://{tmp_path}/file.sock").classification == rid.UNSUPPORTED


def test_stale_socket_without_listener_is_unavailable(tmp_path):
    path = str(tmp_path / "stale.sock")
    s = socket.socket(socket.AF_UNIX)
    s.bind(path)
    s.close()  # bound but nobody listens: connection refused, like a crashed daemon
    ident = rid.verify("x", endpoint=f"unix://{path}")
    assert ident.classification == rid.UNAVAILABLE and "cannot connect" in ident.reasons[0]


def test_same_user_proxy_socket_is_not_verified(tmp_path):
    """A socket served by a process of our own UID that is not dockerd (here: python)."""
    path = str(tmp_path / "proxy.sock")
    server = socket.socket(socket.AF_UNIX)
    server.bind(path)
    server.listen(1)
    try:
        pid, uid, gid, conn = rid.peer_credentials(path)
        conn.close()
        assert (pid, uid, gid) == (os.getpid(), UID, GID)
        ident = rid.verify("x", endpoint=f"unix://{path}")
    finally:
        server.close()
    assert ident.classification == rid.UNVERIFIED_PROXY
    assert ident.pid == os.getpid() and "not dockerd" in ident.reasons[0]
    assert "proxy" in ident.message()


def test_symlinked_socket_path_is_resolved(tmp_path):
    path = tmp_path / "real.sock"
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(path))
    server.listen(1)
    (tmp_path / "link.sock").symlink_to(path)
    try:
        ident = rid.verify("x", endpoint=f"unix://{tmp_path}/link.sock")
    finally:
        server.close()
    assert ident.socket == str(path) and ident.endpoint == f"unix://{path}"
    assert any("resolves to" in n for n in ident.notes)


def test_dockerd_in_own_userns_mapping_root_to_us_passes_peer_check(tmp_path):
    proc = fake_proc(tmp_path)
    cls, reasons, exe, _ = rid.inspect_peer(4242, UID, GID, proc=proc)
    assert cls is None and reasons == [] and exe == "/usr/bin/dockerd"


@pytest.mark.parametrize("uid,text", [(0, "rootful"), (UID + 1, "another user")])
def test_foreign_uid_is_mismatch(tmp_path, uid, text):
    cls, reasons, _, _ = rid.inspect_peer(4242, uid, GID, proc=fake_proc(tmp_path))
    assert cls == rid.MISMATCH and text in reasons[0]


def test_invisible_peer_pid_is_unverified(tmp_path):
    assert rid.inspect_peer(0, UID, GID, proc=fake_proc(tmp_path))[0] == rid.UNVERIFIED_PROXY


@pytest.mark.parametrize("exe", ["/usr/bin/socat", "/usr/bin/python3", "/home/u/dockerd-proxy"])
def test_non_dockerd_peer_is_unverified_proxy(tmp_path, exe):
    cls, reasons, got, _ = rid.inspect_peer(4242, UID, GID, proc=fake_proc(tmp_path, exe=exe))
    assert cls == rid.UNVERIFIED_PROXY and got == exe and "cannot be identified" in reasons[0]


def test_unreadable_peer_executable_is_unverified(tmp_path):
    cls, reasons, _, _ = rid.inspect_peer(4242, UID, GID, proc=fake_proc(tmp_path, exe=None))
    assert cls == rid.UNVERIFIED_PROXY and "cannot read the peer executable" in reasons[0]


def test_replaced_dockerd_binary_is_accepted_with_note(tmp_path):
    cls, _, exe, notes = rid.inspect_peer(4242, UID, GID, proc=fake_proc(tmp_path, exe="/usr/bin/dockerd (deleted)"))
    assert cls is None and exe == "/usr/bin/dockerd" and "replaced" in notes[0]


def test_dockerd_in_our_user_namespace_is_mismatch(tmp_path):
    cls, reasons, _, _ = rid.inspect_peer(4242, UID, GID, proc=fake_proc(tmp_path, peer_ns="user:[1]"))
    assert cls == rid.MISMATCH and "not a rootless daemon" in reasons[0]


@pytest.mark.parametrize("which", ["uid_map", "gid_map"])
def test_namespace_mapping_root_elsewhere_is_mismatch(tmp_path, which):
    kwargs = {which: "         0     200000          1\n"}
    cls, reasons, _, _ = rid.inspect_peer(4242, UID, GID, proc=fake_proc(tmp_path, **kwargs))
    assert cls == rid.MISMATCH and "maps" in reasons[0]


def test_unreadable_namespace_is_unverified(tmp_path):
    proc = fake_proc(tmp_path)
    (proc / "4242" / "uid_map").unlink()
    assert rid.inspect_peer(4242, UID, GID, proc=proc)[0] == rid.UNVERIFIED_PROXY


# --- engine check and full classification -----------------------------------------------------

@pytest.fixture
def peer_ok(tmp_path, monkeypatch):
    path = tmp_path / "d.sock"
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(path))
    server.listen(4)
    monkeypatch.setattr(rid, "inspect_peer", lambda pid, uid, gid, proc=None: (None, [], "/usr/bin/dockerd", []))
    yield f"unix://{path}"
    server.close()


@pytest.mark.parametrize("answer,expected", [((True, "[\"name=rootless\"]"), rid.VERIFIED),
                                             ((False, "[\"name=seccomp\"]"), rid.MISMATCH),
                                             ((None, "Cannot connect"), rid.UNAVAILABLE)])
def test_engine_answer_decides_final_class(monkeypatch, peer_ok, answer, expected):
    monkeypatch.setattr(rid, "engine_reports_rootless", lambda endpoint, docker="docker": answer)
    ident = rid.verify("x", endpoint=peer_ok)
    assert ident.classification == expected
    assert ident.verified is (expected == rid.VERIFIED)


def test_engine_check_uses_the_verified_endpoint(monkeypatch):
    seen = []
    monkeypatch.setattr(rid, "_docker", lambda argv, docker="docker": seen.append(argv) or ('["name=rootless"]', None))
    assert rid.engine_reports_rootless("unix:///x.sock")[0] is True
    assert seen[0][:2] == ["-H", "unix:///x.sock"]


def test_exit_codes_and_json(monkeypatch, capsys):
    for cls, code in rid.EXIT_CODES.items():
        monkeypatch.setattr(rid, "verify", lambda context=None, cls=cls: rid.Identity(cls, "x"))
        assert rid.main([]) == code
    capsys.readouterr()
    monkeypatch.setattr(rid, "verify", lambda context=None: rid.Identity(rid.UNSUPPORTED, "x"))
    assert rid.main(["--json"]) == rid.EXIT_CODES[rid.UNSUPPORTED]
    assert json.loads(capsys.readouterr().out)["classification"] == rid.UNSUPPORTED


def test_runs_as_a_script_without_the_package(tmp_path):
    """install.sh runs the file directly with -I -B before any venv exists."""
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    p = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "src/opencode_sandbox/runtime_identity.py"),
                        "--context", "ocs-test-missing"], check=False, env=env, capture_output=True, text=True, timeout=60)
    # not-configured with a Docker CLI in /usr/bin, missing without one
    assert p.returncode in (rid.EXIT_CODES[rid.NOT_CONFIGURED], rid.EXIT_CODES[rid.MISSING]), p.stderr
    assert "Daemon identity: not-configured" in p.stdout or "Daemon identity: missing" in p.stdout
    assert not list((ROOT / "src/opencode_sandbox").glob("__pycache__/runtime_identity.*-test-*"))


# --- manager integration ----------------------------------------------------------------------

def test_docker_calls_use_the_endpoint_fixed_at_first_verification(monkeypatch):
    seen, runs = [], []
    endpoints = iter(["unix:///first.sock", "unix:///second.sock"])

    def verify(context=None, endpoint=None, **k):
        seen.append(endpoint)
        return rid.Identity(rid.VERIFIED, context, endpoint or next(endpoints), "/first.sock")

    monkeypatch.setattr(rid, "verify", verify)
    monkeypatch.setenv("DOCKER_HOST", "tcp://evil:2375")
    monkeypatch.setattr(c.subprocess, "run", lambda argv, **k: runs.append((argv, k["env"])) or
                        SimpleNamespace(returncode=0, stdout="", stderr=""))
    c.docker("ps")
    c.ensure_runtime(False)
    c.docker("ps")
    assert seen == [None, "unix:///first.sock"]  # re-verified, never re-resolved
    assert [argv[:3] for argv, _ in runs] == [["docker", "-H", "unix:///first.sock"]] * 2
    assert all("DOCKER_HOST" not in env for _, env in runs)
    assert c.docker_cli() == "docker -H unix:///first.sock"


@pytest.mark.parametrize("cls", [rid.UNVERIFIED_PROXY, rid.MISMATCH, rid.UNAVAILABLE, rid.UNSUPPORTED])
def test_manager_refuses_anything_but_verified(monkeypatch, cls):
    monkeypatch.setattr(rid, "verify", lambda context=None, endpoint=None, **k: rid.Identity(cls, "rootless", "unix:///x", reasons=("why",)))
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **k: pytest.fail("docker must not run"))
    with pytest.raises(c.SandboxError, match=f"Docker daemon identity: {cls} .*why"):
        c.ensure_runtime(False)
    with pytest.raises(c.SandboxError, match=cls):
        c.docker("ps")
    assert c._ENDPOINT is None


def test_cli_doctor_prints_report_and_fails_unless_verified(monkeypatch):
    from typer.testing import CliRunner

    from opencode_sandbox.cli import app
    monkeypatch.setattr(rid, "verify", lambda context=None, endpoint=None, **k: rid.Identity(
        rid.UNVERIFIED_PROXY, "rootless", "unix:///tmp/p.sock", reasons=("served by /usr/bin/socat",)))
    from opencode_sandbox import readiness
    monkeypatch.setattr(readiness, "host_checks", list)
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == rid.EXIT_CODES[rid.UNVERIFIED_PROXY]
    assert "Daemon identity: unverified-proxy" in result.output and "socat" in result.output


def test_scripts_use_the_shared_verifier():
    for name in ("install.sh", "setup-rootless.sh"):
        text = (ROOT / name).read_text()
        assert "SecurityOptions" not in text and "--context rootless" not in text, name
        assert "runtime_identity.py" in text and "-I -B" in text, name
    assert "--context" not in (ROOT / "src/opencode_sandbox/core.py").read_text().split("def docker_cli")[0]
