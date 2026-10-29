"""Docker mounts a direct workspace again at every container start,
following the path as it is then. Every start of a direct-workspace container re-checks the
recorded directory first; a refusal leaves the container stopped. Docker is mocked; real row L02."""
import os
import subprocess

import pytest
from test_direct_workspace import direct_env, project  # noqa: F401  (fixture)

from opencode_sandbox import config_plan as cp
from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v


class Recorder:
    def __init__(self, monkeypatch, running=False):
        self.calls, self.running = [], running
        monkeypatch.setattr(c, "docker", self)
        monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": self.running})
        monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
        monkeypatch.setattr(c, "mounted_profile", lambda m: None)
        monkeypatch.setattr(c, "require_docker_space", lambda what: None)
        monkeypatch.setattr("opencode_sandbox.integrations.provision", lambda m: None)

    def __call__(self, *args, capture=False, check=True):
        self.calls.append(args)
        if args[0] == "start":
            self.running = True
        elif args[0] == "stop":
            self.running = False
        out = ""
        if args[:2] == ("container", "inspect"):
            out = "opencode-sandbox:debian\n"
        return subprocess.CompletedProcess(args, 0, out, "")

    def started(self):
        return any(a[0] == "start" for a in self.calls)


def _swap_for_symlink(folder, tmp_path):
    """The recorded directory is replaced by a symlink to another directory of the user."""
    other = tmp_path / "other"
    other.mkdir()
    folder.rename(tmp_path / "moved")
    folder.symlink_to(other, target_is_directory=True)


@pytest.fixture
def stopped(monkeypatch, project):  # noqa: F811
    m = direct_env(monkeypatch, project)
    c.mark(m, "stopped")
    return m


def test_start_of_a_stopped_container_rechecks_the_directory(stopped, monkeypatch, project, tmp_path):  # noqa: F811
    rec = Recorder(monkeypatch)
    _swap_for_symlink(project, tmp_path)
    with pytest.raises(c.SandboxError, match="now resolves to"):
        c.start(stopped)
    assert not rec.started() and c.resolve(stopped["id"])["status"] == "stopped"


def test_start_refuses_a_parent_writable_by_others(stopped, monkeypatch, project):  # noqa: F811
    rec = Recorder(monkeypatch)
    os.chmod(project.parent, 0o777)
    try:
        with pytest.raises(c.SandboxError):
            c.start(stopped)
    finally:
        os.chmod(project.parent, 0o755)
    assert not rec.started()


def test_start_of_an_unchanged_directory_works(stopped, monkeypatch):
    """Guard."""
    rec = Recorder(monkeypatch)
    c.start(stopped)
    assert rec.started()


def test_recreate_recover_rechecks_before_starting_the_replacement(stopped, monkeypatch, project, tmp_path):  # noqa: F811
    stopped["image"] = "opencode-sandbox:debian"
    c.mark(stopped, "error", operation="recreate")
    rec = Recorder(monkeypatch)
    _swap_for_symlink(project, tmp_path)
    with pytest.raises(c.SandboxError, match="now resolves to"):
        c.recreate_recover(stopped)
    assert not rec.started() and c.resolve(stopped["id"])["operation"] == "recreate"


def test_config_restart_rechecks_before_stopping(stopped, monkeypatch, project, tmp_path):  # noqa: F811
    """Lowering memory on a running container stops, updates and starts it."""
    rec = Recorder(monkeypatch, running=True)
    _swap_for_symlink(project, tmp_path)
    m = c.resolve(stopped["id"])
    m["pending_config"] = {"runtime": c.runtime_settings(m), "restart": True, "start": True}
    with pytest.raises(c.SandboxError, match="now resolves to"):
        cp._update_container(m)
    assert not any(a[0] in ("stop", "start") for a in rec.calls)


def test_opencode_update_rechecks_before_anything_changes(stopped, monkeypatch, project, tmp_path):  # noqa: F811
    rec = Recorder(monkeypatch)
    monkeypatch.setattr(v, "supported", lambda version: version)
    m = c.resolve(stopped["id"])
    m["runtime"] = {**c.runtime_settings(m), "network": "bridge"}
    c.save(m)
    _swap_for_symlink(project, tmp_path)
    with pytest.raises(c.SandboxError, match="now resolves to"):
        v.update_environment(m, "2.2.0")
    assert not any(a[0] in ("commit", "start") for a in rec.calls)
    assert c.resolve(stopped["id"]).get("operation") is None


def test_config_update_of_a_running_container_without_restart_is_not_blocked(stopped, monkeypatch, project, tmp_path):  # noqa: F811
    """Guard: `docker update` of limits does not mount anything again."""
    rec = Recorder(monkeypatch, running=True)
    _swap_for_symlink(project, tmp_path)
    m = c.resolve(stopped["id"])
    m["pending_config"] = {"runtime": c.runtime_settings(m), "restart": False, "start": True}
    cp._update_container(m)
    assert any(a[0] == "update" for a in rec.calls) and not any(a[0] in ("stop", "start") for a in rec.calls)
