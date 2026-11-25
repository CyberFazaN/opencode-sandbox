import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from opencode_sandbox import agent_context as ac
from opencode_sandbox import core as c
from opencode_sandbox import opencode_availability as availability
from opencode_sandbox.cli import app


@pytest.mark.parametrize(("exit_code", "status"), [
    (None, availability.Status.MISSING),
    (0, availability.Status.AVAILABLE),
    (1, availability.Status.BROKEN),
])
def test_availability_uses_live_path_and_version(monkeypatch, tmp_path, exit_code, status):
    m = c.create("ocs-test-availability", image="example.org/custom:1")
    (tmp_path / "timeout").symlink_to(shutil.which("timeout"))
    (tmp_path / "tail").symlink_to(shutil.which("tail"))
    (tmp_path / "sh").symlink_to("/bin/sh")
    if exit_code is not None:
        binary = tmp_path / "opencode"
        binary.write_text(f"#!/bin/sh\necho custom-version-string\nexit {exit_code}\n")
        binary.chmod(0o700)
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": True})

    def docker(*args, **kwargs):
        assert args[:2] == ("exec", c.cname(m))
        return subprocess.run(args[2:], env={"PATH": str(tmp_path)}, capture_output=True, text=True, check=False)

    monkeypatch.setattr(c, "docker", docker)
    result = CliRunner().invoke(app, ["opencode", "availability", m["name"]])
    assert result.exit_code == (0 if status == availability.Status.AVAILABLE else 1), result.output
    assert result.output.strip() == status.value


@pytest.mark.parametrize("state", [None, {"Running": False}])
def test_availability_leaves_inactive_containers_alone(monkeypatch, state):
    monkeypatch.setattr(c, "inspect_container", lambda m: state)
    monkeypatch.setattr(c, "docker", lambda *a, **k: pytest.fail("inactive container must not be started or probed"))
    assert availability.check({}) is availability.Status.UNKNOWN


def test_missing_opencode_allows_shell_launch(monkeypatch):
    m = c.create("ocs-test-shell")
    calls = []
    monkeypatch.setattr(c, "start", lambda m: None)
    monkeypatch.setattr(c, "guidance_inputs", lambda m: {"image": "example", "runtime": c.runtime_settings(m)})
    monkeypatch.setattr(c, "_tty", lambda: True)
    monkeypatch.setattr(c, "profile_mismatch", lambda m: None)
    monkeypatch.setattr(availability, "check", lambda m: availability.Status.MISSING)
    monkeypatch.setattr(c, "docker_attached", lambda *a, **k: calls.append(a) or 0)
    with pytest.raises(c.SandboxError, match="OpenCode is missing.*shell"):
        c.interactive(m)
    assert not calls
    assert c.interactive(m, shell=True) == 0
    assert "OCS_SHELL=1" in calls[0]


def test_failed_docker_exec_does_not_mean_missing(monkeypatch):
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": True})
    monkeypatch.setattr(
        c, "docker", lambda *a, **k: subprocess.CompletedProcess(a, 125, "", "Cannot connect to the Docker daemon")
    )
    assert availability.check({"id": "1234"}) is availability.Status.UNKNOWN


def test_hanging_version_is_unknown_not_broken(monkeypatch, tmp_path):
    binary = tmp_path / "opencode"
    binary.write_text('#!/bin/sh\n: > "$0.started"\nexec /bin/sleep 30\n')
    binary.chmod(0o700)
    monkeypatch.setattr(availability.probes, "EXEC_TIMEOUT", 0.1)
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": True})
    m = c.create("ocs-test-hanging", image="example.org/custom:1")

    def docker(*args, capture, check):
        assert args[:6] == ("exec", c.cname(m), "timeout", "--signal=KILL", "0.1s", "sh")
        return c.call(args[2:], capture=capture, check=check,
                      env={"PATH": f"{tmp_path}:/usr/bin:/bin"}, timeout=c._DIAGNOSTIC_TIMEOUT.get())

    monkeypatch.setattr(c, "docker", docker)
    result = CliRunner().invoke(app, ["opencode", "availability", m["name"]], catch_exceptions=False)
    assert (result.exit_code, result.output.strip()) == (2, "Unknown")
    assert binary.with_suffix(".started").is_file()


def test_unexpected_probe_response_is_unknown(monkeypatch):
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": True})
    monkeypatch.setattr(c, "docker", lambda *a, **k: subprocess.CompletedProcess(a, 0, "Unexpected", ""))
    assert availability.check({"id": "1234"}) is availability.Status.UNKNOWN


def test_probe_limits_version_output():
    result = subprocess.run(
        ["sh", "-c", "opencode() { head -c 65536 /dev/zero; printf '\\n2.2.0\\n'; }; " + availability._PROBE],
        capture_output=True, check=True,
    )
    assert len(result.stdout) < 4200 and result.stdout.endswith(b"2.2.0\n\nocs-exit:0\n")


def test_start_reports_failed_agent_context_while_opencode_is_missing(monkeypatch):
    m = c.create("ocs-test-context-repair")
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": True})
    monkeypatch.setattr(c, "guidance_inputs", lambda m: {"image": "example", "runtime": c.runtime_settings(m)})
    monkeypatch.setattr(availability, "check", lambda m: availability.Status.MISSING)

    def failed(m):
        raise c.SandboxError("Cannot reconcile system Agent Context activation")

    monkeypatch.setattr(ac, "reconcile", failed)
    result = CliRunner().invoke(app, ["start", m["name"]])
    assert result.exit_code == 0 and "WARNING: Cannot reconcile" in result.output
    saved = c.resolve(m["name"])
    assert saved["status"] == "running" and "Cannot reconcile" in saved["last_error"]
    monkeypatch.setattr(ac, "reconcile", lambda m: None)
    c.start(m)
    assert c.resolve(m["name"])["last_error"] is None
