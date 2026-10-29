"""Commit/build/npm on a nearly full disk failed midway with ENOSPC."""
from collections import namedtuple
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v

Usage = namedtuple("Usage", "total used free")


@pytest.fixture
def low_disk(monkeypatch, tmp_path):
    calls = []
    def docker(*a, **k):
        calls.append(a)
        if a[:2] == ("info", "--format"):
            return SimpleNamespace(returncode=0, stdout=str(tmp_path) + "\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c.shutil, "disk_usage", lambda p: Usage(10 * 2**30, 9 * 2**30, 1 * 2**30))
    return calls


def _no_writes(calls):
    return not any(a[0] in ("commit", "build", "rm", "start", "tag") for a in calls)


def test_snapshot_refused(low_disk):
    m = c.create("ocs-qa-snap", "scratch")
    c_inspect = c.inspect_container
    try:
        c.inspect_container = lambda m: {"Running": False}
        with pytest.raises(c.SandboxError, match="Not enough free disk space"):
            c.snapshot(m)
    finally:
        c.inspect_container = c_inspect
    assert _no_writes(low_disk)


def test_reconfigure_refused_before_commit(low_disk, monkeypatch):
    m = c.create("ocs-qa-rc", "scratch")
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False})
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    with pytest.raises(c.SandboxError, match="Not enough free disk space"):
        c.reconfigure_runtime(m, c.runtime_settings(m))
    assert _no_writes(low_disk) and c.resolve(m["id"]).get("operation") is None


def test_env_update_and_builds_refused(low_disk, monkeypatch):
    m = c.create("ocs-qa-up", "scratch")
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False})
    monkeypatch.setattr(v, "latest", lambda timeout=8: "2.1.4")
    for call in (lambda: v.update_environment(m, "2.1.3"), lambda: v.update_base("2.1.4"), c.build):
        with pytest.raises(c.SandboxError, match="Not enough free disk space"):
            call()
    assert _no_writes(low_disk)


def test_reserve_is_configurable_and_unknown_root_skips(low_disk, monkeypatch):
    monkeypatch.setenv("OPENCODE_SANDBOX_DOCKER_RESERVE_BYTES", str(512 * 2**20))
    assert c.require_docker_space("x") == 2**30
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="down"))
    monkeypatch.delenv("OPENCODE_SANDBOX_DOCKER_RESERVE_BYTES")
    assert c.require_docker_space("x") is None


def test_reconfigure_untags_only_own_superseded_runtime_image(monkeypatch, tmp_path):
    m = c.create("ocs-qa-rc2", "scratch")
    calls = []
    def docker(*a, **k):
        calls.append(a)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c, "require_docker_space", lambda what: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False})
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    for previous, removed in ((f"ocs-runtime:{m['id']}-aaaaaaaaaaaa", True),
                              (f"ocs-snapshot:{m['id']}-20260101000000", False),  # user snapshot kept
                              ("opencode-sandbox:debian", False),
                              (f"ocs-runtime:{'f' * 16}-aaaaaaaaaaaa", False)):     # other env's tag
        m = c.resolve(m["id"]); m["image"] = previous; c.save(m)
        calls.clear()
        new = c.reconfigure_runtime(m, c.runtime_settings(m))["image"]
        rm = [a for a in calls if a[:2] == ("image", "rm")]
        assert rm == ([("image", "rm", previous)] if removed else []), previous
        assert c.resolve(m["id"])["image"] == new


def test_runtime_preview_warning_matches_network(monkeypatch):
    """Network=none previews claimed 'Bridge permits LAN and internet'."""
    from opencode_sandbox import config_plan as cp
    m = c.create("ocs-qa-pv", "scratch")
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "port_conflicts", lambda m, s: [])
    none = " ".join(cp.plan(m, {"network": "none"}).warnings)
    m["runtime"]["network"] = "none"; c.save(m)
    bridge = " ".join(cp.plan(m, {"network": "bridge"}).warnings)
    assert "Bridge" not in none and "no internet or LAN" in none and "provider" in none
    assert "Bridge permits LAN and internet" in bridge and "Port checks" not in bridge


@pytest.mark.parametrize("stderr,missing", [
    ("Error response from daemon: No such container: ocs-x", True),
    ("error: no such object: ocs-x", True),
    (("failed to connect to the docker API at unix:///run/user/1000/docker.sock; check if the path is correct "
      "and if the daemon is running: dial unix /run/user/1000/docker.sock: connect: no such file or directory"), False),
])
def test_daemon_down_is_not_a_missing_container(monkeypatch, stderr, missing):
    """'no such file or directory' of a stopped daemon was read as 'container missing'."""
    m = c.create("ocs-qa-down", "scratch")
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr=stderr))
    if missing:
        assert c.inspect_container(m) is None
    else:
        with pytest.raises(c.SandboxError, match="Cannot inspect"):
            c.inspect_container(m)
