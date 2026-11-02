"""Read-only Updates inventory: real cache/files, mocked Docker, no helpers on ordinary reads."""
import json
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import distros, updates
from opencode_sandbox import opencode_versions as v
from opencode_sandbox import update_cache as cache

CID, IID = "a" * 64, "sha256:" + "b" * 64


@pytest.fixture
def runtime(monkeypatch):
    m = c.create("ocs-test-updates-history", "scratch")
    calls = []
    state = {"Running": True}
    def docker(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=CID + "|" + IID + "|" + m["id"], stderr="")
    monkeypatch.setattr(c, "inspect_container", lambda _: state)
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(v, "_exec_version", lambda *a, **k: "2.1.4")
    return m, calls, state


def test_history_is_docker_free_and_always_identity_unverified(runtime, monkeypatch):
    m, _calls, _state = runtime
    checked = v.environment_version(m)
    monkeypatch.setattr(c, "docker", lambda *a, **k: pytest.fail("history must be Docker-free"))
    monkeypatch.setattr(c, "inspect_container", lambda *a: pytest.fail("history must not inspect Docker"))
    history = v.environment_history(m)
    assert history["observation"] == checked["observation"]
    assert history["verification"] == "history-unverified" and history["state"] == "unknown"


@pytest.mark.parametrize("observed", [False, True])
def test_ordinary_local_inspection_never_executes_or_refreshes_evidence(runtime, monkeypatch, observed):
    m, calls, state = runtime
    if observed: v.environment_version(m)
    before = cache.read(v._environment_key(m))
    monkeypatch.setattr(v, "_exec_version", lambda *a, **k: pytest.fail("ordinary inventory must not probe"))
    calls.clear()
    item = v.environment_version(m, check=False)
    assert item["state"] == "running" and item["version"] == ("2.1.4" if observed else None)
    assert item["verification"] == ("last-verified" if observed else "unknown")
    assert cache.read(v._environment_key(m)) == before
    assert all(args[:2] == ("container", "inspect") for args in calls)
    state["Running"] = False
    assert v.environment_version(m, check=False)["state"] == "stopped"


@pytest.mark.parametrize("change", ["lifecycle", "data", "journal"])
def test_history_cannot_ignore_lifecycle_identity_or_recovery(runtime, monkeypatch, change):
    m, _calls, _state = runtime
    v.environment_version(m)
    if change == "lifecycle": m["created"] = "new"
    if change == "data": monkeypatch.setattr(c, "data_id", lambda: "other-data")
    if change == "journal": m["operation"] = "opencode-update"
    item = v.environment_history(m)
    assert item["version"] is None
    if change == "journal": assert "pending operation" in item["recovery"]


def test_unavailable_inspection_does_not_create_an_attempt_or_repair_cache(runtime, monkeypatch):
    m, _calls, _state = runtime
    v.environment_version(m)
    before = cache.read(v._environment_key(m))
    def denied(_): raise c.SandboxError("Docker unavailable")
    monkeypatch.setattr(c, "inspect_container", denied)
    item = v.environment_version(m, check=False)
    assert item["verification"] == "history-unverified" and item["error"] == "Docker unavailable"
    assert cache.read(v._environment_key(m)) == before


@pytest.mark.parametrize("check", [False, True])
def test_missing_container_does_not_hide_a_pending_recovery_journal(runtime, monkeypatch, check):
    m, _calls, _state = runtime
    c.mark(m, "error", operation="recreate")
    monkeypatch.setattr(c, "inspect_container", lambda _: None)
    item = v.environment_version(m, check=check)
    assert item["version"] is None and item["state"] == "not-created"
    assert "pending operation" in item["recovery"]


@pytest.mark.parametrize("kind,expected", [("current", "current definition"), ("old", "old definition"),
                                          ("newer", "newer definition"), ("foreign", "ownership/provenance unknown"),
                                          ("unknown", "ownership/provenance unknown"), ("scoped", "ownership/provenance unknown"),
                                          ("different", "different definition")])
def test_base_provenance_is_separate_from_runtime_evidence(monkeypatch, kind, expected):
    d = distros.get(distros.DEFAULT)
    labels = {**d.image_labels(), distros.LABEL + "managed": "true", v.VERSION_LABEL: "2.0.0"}
    if kind == "old": labels[distros.LABEL + "image-revision"] = "1"
    if kind == "newer": labels[distros.LABEL + "image-revision"] = "99"
    if kind == "different": labels[distros.LABEL + "distro-version"] = "99"
    if kind == "foreign": labels[distros.LABEL + "managed"] = "false"
    if kind == "unknown": labels = {}
    if kind == "scoped": labels[c.DATA_LABEL] = "different"
    calls = []
    def docker(*args, **kwargs):
        calls.append(args)
        if args == ("image", "inspect", d.image):
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"Id": IID, "Config": {"Labels": labels}}]), stderr="")
        assert args[:2] == ("image", "inspect") and args[-1] == IID
        return SimpleNamespace(returncode=0, stdout=IID + "|" + json.dumps(labels), stderr="")
    monkeypatch.setattr(c, "docker", docker)
    item = updates.base_inventory(d)
    assert item["state"] == expected and item["version"] is None and item["observation"] is None
    assert item["eligible"] == (kind not in ("foreign", "unknown", "scoped"))
    assert not any(a[0] in ("run", "start", "exec", "build") for a in calls)


@pytest.mark.parametrize("error,missing", [("No such image: test", True), ("daemon unavailable", False)])
def test_only_definite_absence_is_not_built(monkeypatch, error, missing):
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr=error))
    if missing: assert updates.base_inventory(distros.get(distros.DEFAULT))["state"] == "not built"
    else:
        with pytest.raises(c.SandboxError, match="daemon unavailable"): updates.base_inventory(distros.get(distros.DEFAULT))
