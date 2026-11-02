"""Identity-bound disposable evidence; Docker is mocked, cache/metadata are real files."""
import json
import math
import time
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v
from opencode_sandbox import update_cache as cache

CID, IID = "a" * 64, "sha256:" + "b" * 64


@pytest.fixture
def runtime(monkeypatch):
    m = c.create("ocs-test-observation", "scratch")
    state = {"Running": True, "cid": CID, "iid": IID, "version": "2.1.4"}
    calls = []
    def docker(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("container", "inspect"):
            return SimpleNamespace(returncode=0, stdout=state["cid"] + "|" + state["iid"] + "|" + state.get("owner", m["id"]), stderr="")
        if state.get("error"): raise c.SandboxError(state["error"])
        return SimpleNamespace(returncode=0, stdout="opencode v" + state["version"] + "\n", stderr="")
    monkeypatch.setattr(c, "inspect_container", lambda _: dict(state))
    monkeypatch.setattr(c, "docker", docker)
    return m, state, calls


def test_stopped_environment_retains_dated_runtime_evidence(runtime):
    m, state, calls = runtime
    assert v.environment_version(m)["version"] == "2.1.4"
    state["Running"] = False
    calls.clear()
    result = v.environment_version(m)
    assert result["version"] == "2.1.4"
    assert result["observation"]["source"] == "container-exec"
    assert result["observation"]["at"]
    assert not any(a[0] in ("start", "run", "exec") for a in calls)


@pytest.mark.parametrize("mode", ["manual", "pinned"])
def test_explicit_comparisons_do_not_bypass_policy(mode):
    item = {"state": "running", "version": "2.1.4", "policy": {"mode": mode, "version": "2.1.4" if mode == "pinned" else None}}
    assert "update available: 2.1.4 -> 2.2.0" in v.environment_line(item, "2.2.0")
    assert item["policy"]["mode"] == mode


def test_latest_selects_supported_stable_when_npm_latest_moves_major(monkeypatch):
    metadata = {"dist-tags": {"latest": "3.0.0"}, "versions": {
        version: {"version": version} for version in ("2.9.0", "2.10.0", "2.11.0-beta.1", "3.0.0")}}
    monkeypatch.setattr(c, "call", lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(metadata), stderr=""))
    assert v.latest() == "2.10.0"


@pytest.mark.parametrize("changed", ["container", "image", "endpoint", "derived", "update", "created", "data"])
def test_replacement_or_lifecycle_change_cannot_reuse_old_evidence(runtime, monkeypatch, changed):
    m, state, calls = runtime
    v.environment_version(m)
    state["Running"] = False
    if changed == "container": state["cid"] = "c" * 64
    if changed == "image": state["iid"] = "sha256:" + "d" * 64
    if changed == "endpoint": monkeypatch.setattr(c, "docker_endpoint", lambda: "unix:///nonexistent/other.sock")
    if changed == "data": monkeypatch.setattr(c, "data_id", lambda: "another-data-directory")
    if changed == "derived": m["image"] = "ocs-runtime:" + m["id"] + "-new"
    if changed == "update": m["opencode_update"] = {"state": "done", "to": "2.2.0"}
    if changed == "created": m["created"] = c.now()
    c.save(m)
    calls.clear()
    result = v.environment_version(m)
    assert result["version"] is None and result["observation"] is None
    assert not any(a[0] in ("start", "exec", "run") for a in calls)


@pytest.mark.parametrize("operation", ["opencode-update", "runtime-recreate", "recreate", "restore", "delete"])
def test_pending_operation_never_publishes_runtime_success(runtime, operation):
    m, _state, calls = runtime
    v.environment_version(m)
    c.mark(m, "error", operation=operation)
    calls.clear()
    result = v.environment_version(m)
    assert result["version"] is None and "pending operation" in result["recovery"]
    assert not any(a[0] in ("start", "exec", "run") for a in calls)


def test_failed_probe_retains_old_time_and_separate_failed_attempt(runtime):
    m, state, _calls = runtime
    good = v.environment_version(m)
    state["error"] = "diagnostic timed out"
    failed = v.environment_version(m)
    assert failed["observation"] == good["observation"]
    assert failed["verification"] == "last-verified" and not failed["attempt"]["ok"]
    assert failed["attempt"]["at"] >= good["observation"]["at"]
    assert "latest probe failed" in v.environment_line({**failed, "policy": v.policy(m)})


def test_cache_absence_and_creation_labels_do_not_verify_a_stopped_binary(runtime):
    m, state, _calls = runtime
    m["opencode_update"] = {"state": "done", "to": "2.99.0"}
    c.save(m)
    state["Running"] = False
    result = v.environment_version(m)
    assert result["version"] is None and result["verification"] == "unknown"
    assert "Unknown" in v.environment_line({**result, "policy": v.policy(m)})


def test_docker_failure_retains_only_explicitly_unverified_history(runtime, monkeypatch):
    m, _state, _calls = runtime
    good = v.environment_version(m)
    def unavailable(_): raise c.SandboxError("Docker unavailable")
    monkeypatch.setattr(c, "inspect_container", unavailable)
    result = v.environment_version(m)
    assert result["observation"] == good["observation"] and result["verification"] == "history-unverified"
    text = v.environment_line({**result, "policy": v.policy(m)}, "2.2.0")
    assert "current container identity unverified" in text and "update available" not in text
    lines, errors = v.versions_report()
    assert m["name"] in lines[0] and "Docker unavailable" in errors[0]


@pytest.mark.parametrize("change", ["container", "journal", "metadata"])
def test_change_during_probe_is_not_published(runtime, monkeypatch, change):
    m, state, _calls = runtime
    real = c.docker
    def docker(*args, **kwargs):
        result = real(*args, **kwargs)
        if args[0] == "exec":
            if change == "container": state["cid"] = "e" * 64
            if change == "journal": c.mark(m, "updating", operation="opencode-update")
            if change == "metadata": m["image"] = "ocs-runtime:new"; c.save(m)
        return result
    monkeypatch.setattr(c, "docker", docker)
    result = v.environment_version(m)
    assert result["version"] is None and result["verification"] == "unknown" and result["error"]
    assert cache.read(v._environment_key(m))["success"] is None


@pytest.mark.parametrize("mode", ["manual", "pinned", "notify"])
def test_unsolicited_and_explicit_comparisons_are_separate(mode):
    item = {"version": "2.1.4", "policy": {"mode": mode, "version": "2.1.4" if mode == "pinned" else None}}
    assert v.comparison(item, "2.2.0").startswith("update available")
    assert (v.comparison(item, "2.2.0", unsolicited=True) is not None) == (mode == "notify")


@pytest.mark.parametrize("field,value", [pytest.param("at", time.time() + 86400, id="future"), ("at", float("nan")), ("value", "2.01.4"),
                                         ("source", "build-label"), ("identity", {})])
def test_invalid_local_observation_is_a_miss(runtime, field, value):
    m, state, _calls = runtime
    v.environment_version(m)
    key = v._environment_key(m)
    data = cache.read(key)
    data["success"][field] = value
    if field == "at" and math.isnan(value):
        path = c.BASE / cache.DIRECTORY / cache._name(key)
        path.write_text(json.dumps(data))
    else: cache.write(key, data)
    state["Running"] = False
    assert v.environment_version(m)["version"] is None


def test_readiness_does_not_pass_a_failed_fresh_probe_with_history(runtime):
    from opencode_sandbox import readiness
    m, state, _calls = runtime
    v.environment_version(m)
    state["error"] = "probe failed"
    check = readiness.opencode_check(m, {"Running": True}, {"Config": {"Env": [v.SELF_UPDATE_ENV]}})
    assert check.status == "failed"


def test_observation_inspection_and_probe_do_not_mutate_metadata(runtime):
    m, state, calls = runtime
    path = c.env_dir(m["id"]) / "metadata.json"
    before = path.read_bytes()
    result = v.environment_version(m)
    assert result["observation"]["identity"]["container"] == CID
    assert next(a for a in calls if a[0] == "exec")[1] == CID
    state["Running"] = False
    v.environment_version(m)
    assert path.read_bytes() == before


def test_missing_container_cannot_report_an_installed_version(runtime, monkeypatch):
    m, _state, _calls = runtime
    v.environment_version(m)
    monkeypatch.setattr(c, "inspect_container", lambda _: None)
    result = v.environment_version(m)
    assert result["state"] == "not-created" and result["version"] is None


def test_ownership_refusal_does_not_probe_a_replacement(runtime):
    m, state, calls = runtime
    state["owner"] = "f" * 16
    with pytest.raises(c.SandboxError, match="ownership mismatch"):
        v.environment_version(m)
    assert not any(a[0] == "exec" for a in calls)


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
@pytest.mark.parametrize("mode", ["manual", "pinned"])
def test_explicit_pilot_report_compares_policies_and_keeps_stopped_time(runtime, monkeypatch, size, mode):
    from test_tui import run, settle

    from opencode_sandbox import readiness, tui
    m, state, _calls = runtime
    v.set_policy(m, mode, "2.1.4" if mode == "pinned" else None)
    v.environment_version(m)
    state["Running"] = False
    monkeypatch.setattr(readiness, "image_checks", list)
    monkeypatch.setattr(v, "latest", lambda: "2.2.0")
    async def test(app, pilot):
        await pilot.press("v", "3", "c")
        await settle(pilot)
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, tui.ReportScreen)
        assert f"{mode}; update available: 2.1.4 -> 2.2.0" in app.screen.report
        assert "last verified" in app.screen.report and "not a fresh check" in app.screen.report
        assert c.resolve(m["id"])["opencode_policy"] == mode
    run(test, size)
