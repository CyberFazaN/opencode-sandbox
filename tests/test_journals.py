"""Journals and step order under concurrent changes. A handler re-marks only a journal it still
owns; a restore is journalled from its first save; delete removes metadata.json last; `config
apply` keeps changes made after its plan and starts only a container it stopped.

Docker is mocked. Each interleaving is deterministic: a monkeypatched step that runs between two
steps of the operation changes the metadata the way another process would."""
import json
import os
import subprocess

import pytest
from test_config_plan import FakeContainer

from opencode_sandbox import backup as b
from opencode_sandbox import config_plan as cp
from opencode_sandbox import core as c

RT = {"cpus": "2", "memory": "2g", "pids": 256, "network": "none", "ports": []}


def _on_disk(m):
    return json.loads((c.env_dir(m["id"]) / "metadata.json").read_text())


def _finish(eid, **fields):
    """Another process finishes (or starts) its operation on the environment."""
    with c.lock(eid):
        m = c.resolve(eid)
        c.mark(m, fields.pop("status"), **fields)


@pytest.fixture
def no_docker(monkeypatch):
    calls = []

    def docker(*args, capture=False, check=True):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")
    for name, value in (("ensure_runtime", lambda image=True: None), ("inspect_container", lambda m: None),
                        ("assert_volume_owned", lambda m: None), ("volume_state", lambda m: None),
                        ("docker", docker)):
        monkeypatch.setattr(c, name, value)
    return calls


def _backup(tmp_path):
    root = tmp_path / "x.ocsbackup"
    root.mkdir()
    manifest = {"environment": {"name": "orig", "kind": "scratch", "profile": "default", "runtime": RT,
                                "distro": "debian"},
                "files": {}, "workspace": {"mode": "managed", "included": True}}
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root, manifest


def _interrupted_restore(tmp_path):
    root, manifest = _backup(tmp_path)
    m = c.create("ocs-qa-restored", "scratch")
    c.mark(m, "restoring", operation="restore", restored_from=str(root), restore_stage="initial", restore_system=False)
    return m, root, manifest


# --- handlers ----------------------------------------------------------------------

def test_resume_after_the_restore_finished_leaves_the_environment_alone(no_docker, monkeypatch, tmp_path):
    """`restore-resume` passed its check, then the restore finished: the resume must not mark the
    finished environment as a failed restore (the advice would then be `restore-rollback`)."""
    m, _, manifest = _interrupted_restore(tmp_path)
    (c.env_dir(m["id"]) / "workspace" / "work.txt").write_text("done since\n")

    def verify(path):
        _finish(m["id"], status="ready", operation=None, restore_stage=None)
        return manifest
    monkeypatch.setattr(b, "verify", verify)
    with pytest.raises(c.SandboxError, match="Not an interrupted restore"):
        b.resume_restore(m)
    now = c.resolve(m["id"])
    assert (now["status"], now.get("operation"), now.get("last_error")) == ("ready", None, None)


def test_restore_into_requires_the_restore_journal(no_docker, tmp_path):
    root, manifest = _backup(tmp_path)
    m = c.create("ocs-qa-plain", "scratch")
    with pytest.raises(c.SandboxError, match="Not an interrupted restore"):
        b._restore_into(m, root, manifest, restore_system=False)
    now = c.resolve(m["id"])
    assert (now["status"], now.get("operation")) == ("ready", None)


def test_rollback_does_not_delete_a_restore_that_finished_meanwhile(no_docker, monkeypatch, tmp_path):
    """The check passed; the restore finished while the deletion waited for the lock (delete
    calls ensure_runtime before it takes the lock)."""
    m, _, _ = _interrupted_restore(tmp_path)
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: _finish(
        m["id"], status="ready", operation=None, restore_stage=None))
    with pytest.raises(c.SandboxError, match="Not a failed restore"):
        b.rollback_restore(m)
    assert c.env_dir(m["id"]).is_dir() and c.resolve(m["id"])["status"] == "ready"


def test_restore_failure_handler_keeps_a_journal_it_does_not_own(no_docker, monkeypatch, tmp_path):
    """The restore lost the environment to a concurrent rollback-and-recreate race: another
    operation's journal is never replaced by error/restore."""
    root, _ = _backup(tmp_path)
    monkeypatch.setattr(b, "verify", lambda path: json.loads((path / "manifest.json").read_text()))

    def restore_into(m, *args, **kwargs):
        _finish(m["id"], status="deleting", operation="delete")
        raise c.SandboxError("Restore staging/workspace is not empty; rollback before retry")
    monkeypatch.setattr(b, "_restore_into", restore_into)
    with pytest.raises(c.SandboxError):
        b.restore(root, "ocs-qa-restored")
    now = c.resolve("ocs-qa-restored")
    assert (now["status"], now["operation"]) == ("deleting", "delete")


def test_recreate_recover_handler_keeps_a_concurrent_delete_journal(no_docker, monkeypatch):
    m = c.create("ocs-qa-recreate", "scratch")
    c.mark(m, "recreating", operation="recreate")

    def start(env, **kwargs):
        _finish(env["id"], status="deleting", operation="delete")
        raise c.SandboxError("Environment deletion pending; retry delete --yes")
    monkeypatch.setattr(c, "start", start)
    with pytest.raises(c.SandboxError, match="deletion pending"):
        c.recreate_recover(m)
    now = c.resolve(m["id"])
    assert (now["status"], now["operation"]) == ("deleting", "delete")


def test_recreate_recover_handler_still_records_its_own_failure(no_docker, monkeypatch):
    """Guard: a failure of the recreation itself is recorded for `recreate-recover`."""
    m = c.create("ocs-qa-recreate", "scratch")
    c.mark(m, "recreating", operation="recreate")

    def start(env, **kwargs):
        raise c.SandboxError("docker run failed")
    monkeypatch.setattr(c, "start", start)
    with pytest.raises(c.SandboxError):
        c.recreate_recover(m)
    now = c.resolve(m["id"])
    assert (now["status"], now["operation"]) == ("error", "recreate") and "docker run failed" in now["last_error"]


# --- restore journal from the first save ---------------------------------------------

def test_restore_is_journalled_in_the_first_save(no_docker, monkeypatch, tmp_path):
    """A kill right after the environment is created leaves a recognisable interrupted restore
    with the backup's settings, not an ordinary empty environment with network bridge."""
    root, _ = _backup(tmp_path)
    monkeypatch.setattr(b, "verify", lambda path: json.loads((path / "manifest.json").read_text()))
    first = {}
    create = c.create

    def recording_create(*args, **kwargs):
        m = create(*args, **kwargs)
        first.update(_on_disk(m))
        return m
    monkeypatch.setattr(c, "create", recording_create)
    monkeypatch.setattr(b, "_restore_into", lambda m, *a, **k: c.resolve(m["id"]))
    b.restore(root, "ocs-qa-restored", restore_system=False)
    assert (first["status"], first["operation"], first["restore_stage"]) == ("restoring", "restore", "initial")
    assert first["runtime"]["network"] == "none" and first["restored_from"] == str(root)
    assert first["restore_system"] is False


def test_start_refuses_a_restore_that_has_only_been_created(no_docker, monkeypatch, tmp_path):
    root, _ = _backup(tmp_path)
    monkeypatch.setattr(b, "verify", lambda path: json.loads((path / "manifest.json").read_text()))
    seen = []

    def restore_into(m, *args, **kwargs):
        with pytest.raises(c.SandboxError) as refused:
            c.start(c.resolve(m["id"]))
        seen.append(str(refused.value))
        return c.resolve(m["id"])
    monkeypatch.setattr(b, "_restore_into", restore_into)
    b.restore(root, "ocs-qa-restored", restore_system=False)
    assert seen and not any(a[0] in ("run", "create") for a in no_docker)


# --- delete order -----------------------------------------------------------------------

def test_delete_removes_metadata_last(no_docker, monkeypatch):
    m = c.create("ocs-qa-delete", "scratch")
    d = c.env_dir(m["id"])
    for i in range(20):
        (d / "workspace" / f"file-{i}.txt").write_text("x")
    (d / "agent-context.md").write_text("guidance")
    c.save(m)  # metadata.json is the newest entry
    removed = []
    unlink = os.unlink

    def recording_unlink(path, *args, **kwargs):
        removed.append(os.fsdecode(path).rsplit("/", 1)[-1])
        return unlink(path, *args, **kwargs)
    monkeypatch.setattr(os, "unlink", recording_unlink)
    c.delete(m, force=True)
    assert not d.exists()
    assert removed[-1] == "metadata.json" and removed.count("metadata.json") == 1


def test_delete_killed_during_the_helper_removal_stays_listed(no_docker, monkeypatch):
    """Workspace files the user cannot remove (in the real case: of a subordinate UID) need the
    helper container; a kill while it runs must leave the environment listed with its deletion
    journal, so `delete --yes` can be retried."""
    m = c.create("ocs-qa-delete", "scratch")
    d = c.env_dir(m["id"])
    locked = d / "workspace" / "locked"
    locked.mkdir()
    (locked / "a.txt").write_text("x")
    locked.chmod(0o500)
    c.save(m)

    def docker(*args, capture=False, check=True):
        if args[0] == "run":
            raise KeyboardInterrupt  # stands for the kill: no handler runs
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(c, "docker", docker)
    try:
        with pytest.raises(KeyboardInterrupt):
            c.delete(m, force=True)
        now = c.resolve(m["id"])
        assert (now["status"], now["operation"]) == ("deleting", "delete")
    finally:
        locked.chmod(0o700)


# --- config apply ---------------------------------------------------------------------

@pytest.fixture
def planned(monkeypatch):
    monkeypatch.setattr(c, "host_cpus", lambda: 8)
    m = c.create("ocs-qa-plan", "scratch")
    m["runtime"] = c.validate_runtime_settings({"cpus": "2", "memory": "4g", "pids": 500, "network": "bridge"})
    c.save(m)
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    monkeypatch.setattr(c, "require_docker_space", lambda what: None)
    return c.resolve(m["id"])


def _after_plan(monkeypatch, action):
    """Run `action` once, after apply() has made its plan (apply then calls ensure_runtime)."""
    done = []

    def ensure_runtime(image=True):
        if not done:
            done.append(True)
            action()
    monkeypatch.setattr(c, "ensure_runtime", ensure_runtime)


def _set_memory(eid, value):
    with c.lock(eid):
        m = c.resolve(eid)
        m["runtime"] = {**c.runtime_settings(m), "memory": value}
        c.save(m)


def test_recreate_keeps_a_limit_changed_after_the_plan(monkeypatch, planned):
    FakeContainer(monkeypatch, "stopped")
    _after_plan(monkeypatch, lambda: _set_memory(planned["id"], "3g"))
    assert cp.apply(planned, {"network": "none"})["category"] == "recreate"
    runtime = c.runtime_settings(c.resolve(planned["id"]))
    assert (runtime["network"], runtime["memory"]) == ("none", "3g")


def test_dynamic_update_keeps_a_setting_changed_after_the_plan(monkeypatch, planned):
    FakeContainer(monkeypatch, "stopped")
    _after_plan(monkeypatch, lambda: _set_memory(planned["id"], "3g"))
    assert cp.apply(planned, {"cpus": "3"})["category"] == "dynamic"
    runtime = c.runtime_settings(c.resolve(planned["id"]))
    assert (runtime["cpus"], runtime["memory"]) == (c.validate_runtime_settings({"cpus": "3"})["cpus"], "3g")


def test_recreate_does_not_start_a_container_stopped_by_someone_else(monkeypatch, planned):
    fake = FakeContainer(monkeypatch, "running")
    started = []
    monkeypatch.setattr(c, "start", lambda m: started.append(m["id"]))

    def stopped_elsewhere():
        fake.state = "stopped"
    _after_plan(monkeypatch, stopped_elsewhere)
    assert cp.apply(planned, {"network": "none"})["category"] == "recreate"
    assert started == [] and c.runtime_settings(c.resolve(planned["id"]))["network"] == "none"


def test_recreate_starts_the_container_it_stopped(monkeypatch, planned):
    """Guard."""
    FakeContainer(monkeypatch, "running")
    started = []
    monkeypatch.setattr(c, "start", lambda m: started.append(m["id"]))
    assert cp.apply(planned, {"network": "none"})["category"] == "recreate"
    assert started == [planned["id"]]


def test_restart_does_not_start_a_container_stopped_by_someone_else(monkeypatch, planned):
    """Lowering memory on a running container stops, updates and starts it; if it was stopped
    after the plan, it is updated and stays stopped."""
    fake = FakeContainer(monkeypatch, "running")

    def stopped_elsewhere():
        fake.state = "stopped"
    _after_plan(monkeypatch, stopped_elsewhere)
    assert cp.apply(planned, {"memory": "1g"})["category"] == "restart"
    assert [a[0] for a in fake.calls] == ["update"] and fake.state == "stopped"
    assert c.runtime_settings(c.resolve(planned["id"]))["memory"] == "1g"
