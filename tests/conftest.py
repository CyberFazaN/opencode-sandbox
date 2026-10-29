import pytest
import typer.rich_utils

from opencode_sandbox import core as c
from opencode_sandbox import runtime_identity as rid

FAKE_ENDPOINT = "unix:///nonexistent/ocs-test-docker.sock"


@pytest.fixture(autouse=True)
def _isolated_manager_paths(tmp_path, monkeypatch):
    """No test may touch the real user's data/config directories."""
    monkeypatch.setattr(c, "BASE", tmp_path / "ocs-data")
    monkeypatch.setattr(c, "CONFIG", tmp_path / "ocs-config")


@pytest.fixture(autouse=True)
def _plain_cli_errors(monkeypatch):
    """Typer forces a colour terminal when GITHUB_ACTIONS, FORCE_COLOR or PY_COLORS is set and then
    wraps error messages in a panel; the tests read them as printed without a terminal."""
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", False)


@pytest.fixture(autouse=True)
def _no_real_daemon_identity(request, monkeypatch):
    """Unit tests never verify the real daemon; tests of the verifier opt out with `real_identity`."""
    monkeypatch.setattr(c, "_ENDPOINT", None)
    if request.node.get_closest_marker("real_identity"):
        return
    monkeypatch.setattr(rid, "verify", lambda context=None, **k: rid.Identity(
        rid.VERIFIED, context or "rootless", k.get("endpoint") or FAKE_ENDPOINT, FAKE_ENDPOINT[7:]))


@pytest.fixture(autouse=True)
def _no_real_session_processes(request, monkeypatch):
    """Interactive sessions go through the mocked `c.docker`; no watchdog process is started.
    Tests of the real processes opt out with `real_session`."""
    if request.node.get_closest_marker("real_session"):
        return
    monkeypatch.setattr(c, "session_watchdog", lambda m, token: None)

    def attached(*args, on_start=None):
        if on_start:
            on_start(0)
        return c.docker(*args, check=False).returncode
    monkeypatch.setattr(c, "docker_attached", attached)


def pytest_configure(config):
    config.addinivalue_line("markers", "real_identity: use the real runtime_identity.verify")
    config.addinivalue_line("markers", "real_session: real docker client and session watchdog processes (fake docker binary)")
