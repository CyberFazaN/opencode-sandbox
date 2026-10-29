"""Recreation is consistent. A running container is stopped before its system layer is
committed, and recovery never takes the old, still running container
for the replacement. Docker is mocked; real rows D04/D05."""
import subprocess

import pytest

from opencode_sandbox import core as c


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "require_docker_space", lambda what: None)
    return c.create("ocs-test-r05", "scratch")


class FakeDocker:
    """One container `ocs-<id>`; records calls."""

    def __init__(self, m, *, running=True, image="opencode-sandbox:debian"):
        self.m, self.calls = m, []
        self.container = {"Running": running, "Image": image}

    def inspect(self, m):
        return None if self.container is None else {"Running": self.container["Running"]}

    def __call__(self, *args, capture=False, check=True):
        self.calls.append(args)
        out, rc = "", 0
        if args[0] == "stop":
            self.container["Running"] = False
        elif args[0] == "rm":
            if self.container["Running"] and "-f" not in args:
                rc = 1
            else:
                self.container = None
        elif args[:2] == ("container", "inspect"):
            out = self.container["Image"] + "\n"
        elif args[:2] == ("image", "inspect"):
            rc = 1
        if check and rc:
            raise c.SandboxError(f"Command failed ({rc}): docker {args[0]}")
        return subprocess.CompletedProcess(args, rc, out, "")


def _fake_start(m, *, _resume_recreate=False):
    current = c.resolve(m["id"])
    c.mark(current, "running", operation=None)


def test_running_container_is_stopped_before_the_commit(env, monkeypatch):
    fake = FakeDocker(env)
    monkeypatch.setattr(c, "docker", fake)
    monkeypatch.setattr(c, "inspect_container", fake.inspect)
    monkeypatch.setattr(c, "start", _fake_start)
    assert c.recreate(env, confirm=True) == "recreated"
    names = [a[0] for a in fake.calls if a[0] in ("stop", "commit", "rm")]
    assert names == ["stop", "commit", "rm"]
    assert ("rm", c.cname(env)) in fake.calls and not any(a[:2] == ("rm", "-f") for a in fake.calls)


def test_removal_never_kills_a_container_that_runs_again(env, monkeypatch):
    """If the container runs again after the commit, it is not removed; the journal stays."""
    fake = FakeDocker(env)
    monkeypatch.setattr(c, "docker", fake)
    monkeypatch.setattr(c, "inspect_container", fake.inspect)
    real_snapshot = c.snapshot

    def snapshot_then_restarted(m, tag=None):
        out = real_snapshot(m, tag)
        fake.container["Running"] = True  # started again from outside the manager
        return out
    monkeypatch.setattr(c, "snapshot", snapshot_then_restarted)
    with pytest.raises(c.SandboxError):
        c.recreate(env, confirm=True)
    assert fake.container is not None
    assert c.resolve(env["id"])["operation"] == "recreate"


def test_recover_refuses_while_the_old_container_still_runs(env, monkeypatch):
    snap = f"ocs-snapshot:{env['id']}-20261028000000"
    env["image"] = snap
    c.mark(env, "error", operation="recreate", last_snapshot=snap)
    fake = FakeDocker(env, running=True, image="opencode-sandbox:debian")  # the old container
    monkeypatch.setattr(c, "docker", fake)
    monkeypatch.setattr(c, "inspect_container", fake.inspect)
    with pytest.raises(c.SandboxError, match=r"old container.*opencode-sandbox stop ocs-test-r05"):
        c.recreate_recover(env)
    saved = c.resolve(env["id"])
    assert saved["operation"] == "recreate" and saved["status"] == "error"
    assert not any(a[0] in ("stop", "rm") for a in fake.calls)


def test_recover_accepts_the_running_replacement(env, monkeypatch):
    """Guard: the replacement (created from the snapshot) is running: the journal closes."""
    snap = f"ocs-snapshot:{env['id']}-20261028000000"
    env["image"] = snap
    c.mark(env, "error", operation="recreate", last_snapshot=snap)
    fake = FakeDocker(env, running=True, image=snap)
    monkeypatch.setattr(c, "docker", fake)
    monkeypatch.setattr(c, "inspect_container", fake.inspect)
    assert c.recreate_recover(env) == "replacement already running"
    assert c.resolve(env["id"])["operation"] is None


def test_recover_without_snapshot_compares_with_the_environment_image(env, monkeypatch):
    """Recreation of an environment without a container: the replacement uses its base image."""
    c.mark(env, "error", operation="recreate")
    fake = FakeDocker(env, running=True, image=c.env_image(env))
    monkeypatch.setattr(c, "docker", fake)
    monkeypatch.setattr(c, "inspect_container", fake.inspect)
    assert c.recreate_recover(env) == "replacement already running"
