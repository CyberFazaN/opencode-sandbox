"""Default-off dashboard scheduling: real files/HTTP, Textual pilots and no runtime work."""
import json
import threading

import pytest
import test_opencode_versions
from test_tui import run
from test_updates_tui import until
from textual.widgets import Button, Checkbox

from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v
from opencode_sandbox import preferences, readiness, update_discovery
from opencode_sandbox import update_cache as cache

registry = test_opencode_versions.registry


def history(m, version="2.1.4"):
    identity = {"data": c.data_id(), "environment": m["id"], "lifecycle": v._lifecycle(m)}
    cache.write(v._environment_key(m), {"success": cache.evidence(version, "container-exec", identity)})


@pytest.fixture
def metadata_sources(monkeypatch, registry):
    from opencode_sandbox import manager_releases
    # This pre-existing suite isolates npm scheduling; manager scheduling has its own real-HTTP
    # pilots/provider tests. Never let the newly added independent source contact public GitHub.
    monkeypatch.setattr(manager_releases, 'latest', lambda **kwargs: None)
    registry["body"] = b'{"versions":{"2.2.0":{"version":"2.2.0"}}}'
    monkeypatch.setattr(readiness, "image_checks", list)
    monkeypatch.setattr(readiness, "daemon_check", lambda: readiness.Check("daemon", "Docker", readiness.PASSED, "test"))
    calls = []
    monkeypatch.setattr(c, "docker", lambda *a, **k: calls.append(a) or pytest.fail("discovery must not call Docker"))
    return calls


def test_preferences_are_backward_compatible_boolean_default_off(tmp_path):
    assert preferences.read() == preferences.DEFAULTS and not preferences.read()["daily_discovery"]
    c.CONFIG.mkdir(parents=True)
    path = c.CONFIG / "ui.json"
    for value in (None, "true", 1, [], {}):
        path.write_text(json.dumps({"confirm_stop": False, "daily_discovery": value}))
        assert not preferences.read()["daily_discovery"] and not preferences.read()["confirm_stop"]
    preferences.write({**preferences.DEFAULTS, "daily_discovery": True})
    assert preferences.read()["daily_discovery"] and path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(c.SandboxError): preferences.write({**preferences.DEFAULTS, "daily_discovery": "yes"})


@pytest.mark.parametrize("invalid", [False, True])
def test_default_or_invalid_preferences_never_schedule(metadata_sources, registry, invalid):
    if invalid:
        c.CONFIG.mkdir(parents=True)
        (c.CONFIG / "ui.json").write_text("broken JSON")
    async def test(app, pilot):
        for _ in range(3): app.refresh_discovery_preferences()
        await pilot.pause()
        assert not app._discovery_enabled and not registry["requests"] and not metadata_sources
        assert app._discovery_worker_ref is None
    run(test, (80, 24))


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
def test_preferences_save_cancel_enable_disable_and_compact_controls(metadata_sources, registry, size):
    async def test(app, pilot):
        await pilot.press("g")
        screen = app.screen
        assert not screen.query_one("#daily-discovery", Checkbox).value
        for widget in screen.query("Checkbox, Button"):
            assert widget.region.height > 0 and widget.region.bottom <= size[1] and widget.region.right <= size[0]
        screen.query_one("#daily-discovery", Checkbox).value = True
        screen.query_one("#cancel-settings", Button).press()
        await pilot.pause()
        assert not preferences.read()["daily_discovery"] and not registry["requests"]
        await pilot.press("g")
        app.screen.query_one("#daily-discovery", Checkbox).value = True
        app.screen.query_one("#save-settings", Button).press()
        await until(pilot, lambda: app._discovery_status is not None)
        assert preferences.read()["daily_discovery"] and len(registry["requests"]) == 1
        for _ in range(3):
            app.refresh_discovery_preferences()
            await pilot.pause()
        assert len(registry["requests"]) == 1
        await pilot.press("g")
        app.screen.query_one("#daily-discovery", Checkbox).value = False
        app.screen.query_one("#save-settings", Button).press()
        await pilot.pause()
        assert not app._discovery_enabled and str(app.query_one("#ocversions", Button).label) == "Updates"
        assert not metadata_sources
    run(test, size)


def test_indicator_is_single_quiet_policy_filtered_and_never_operation_status(metadata_sources, registry):
    preferences.write({**preferences.DEFAULTS, "daily_discovery": True})
    for mode in ("notify", "manual", "pinned"):
        m = c.create("ocs-test-notice-" + mode, "scratch")
        v.set_policy(m, mode, "2.1.4" if mode == "pinned" else None)
        history(c.resolve(m["id"]))
    for state in ("unknown", "current", "newer", "pending"):
        m = c.create("ocs-test-notice-" + state, "scratch")
        if state != "unknown": history(m, "2.2.0" if state == "current" else "2.3.0" if state == "newer" else "2.1.4")
        if state == "pending": c.mark(m, "error", operation="recreate")
    async def test(app, pilot):
        await until(pilot, lambda: str(app.query_one("#ocversions", Button).label) == "Updates (1)")
        app.query_one("#status").update("operation stays visible")
        app._operation_pending = True
        notes = list(app._notifications)
        for _ in range(3):
            app.refresh_discovery_preferences()
            app.action_refresh()
            await pilot.pause()
        assert str(app.query_one("#status").render()) == "operation stays visible"
        assert list(app._notifications) == notes  # no per-environment or repeated availability toasts
        assert len(registry["requests"]) == 1 and not metadata_sources
    app = run(test, (80, 24))
    # A fresh dashboard also reuses the claim; its indicator is state, not another notice event.
    run(test, (80, 24))
    assert app._discovery_status["success"]["value"] == "2.2.0"


def test_background_and_explicit_updates_check_share_one_real_request(metadata_sources, registry, monkeypatch):
    preferences.write({**preferences.DEFAULTS, "daily_discovery": True})
    registry["delay"] = .8
    # Empty environment view ensures the explicit Check has no runtime object to probe.
    from opencode_sandbox import updates
    monkeypatch.setattr(updates, "base_inventory", lambda *a, **k: {"state": "not built", "eligible": False})
    async def test(app, pilot):
        await until(pilot, lambda: len(registry["requests"]) == 1)
        await pilot.press("v", "3", "c")
        screen = app.screen
        await until(pilot, lambda: not screen._active and app._discovery_status is not None)
        assert "npm: 2.2.0" in screen.discovery_text()
        assert screen.remote["success"] == v.discovery()["success"]  # never retimestamp shared evidence
        assert len(registry["requests"]) == 1 and not metadata_sources
        await pilot.press("d")
        assert "enabled (GitHub + npm, independent sources)" in app.screen.report
    run(test, (80, 24))


def test_background_results_reach_an_already_open_updates_view(metadata_sources, registry, monkeypatch):
    from opencode_sandbox import updates
    monkeypatch.setattr(updates, "base_inventory", lambda *a, **k: {"state": "not built", "eligible": False})
    async def test(app, pilot):
        await pilot.press("v", "3")
        screen = app.screen
        assert not registry["requests"]
        preferences.write({**preferences.DEFAULTS, "daily_discovery": True})
        app.refresh_discovery_preferences()
        await until(pilot, lambda: "npm: 2.2.0" in screen.discovery_text())
        assert not screen._active and len(registry["requests"]) == 1
    run(test, (80, 24))


def test_disabling_cancels_owned_attempt_and_late_publication(metadata_sources, monkeypatch):
    from opencode_sandbox import runtime_identity as rid
    started, canceled = threading.Event(), threading.Event()
    def slow(**kwargs):
        started.set()
        callback = (c._RUNTIME_FEEDBACK.get() or {})["cancelled"]
        while not callback(): canceled.wait(.01)
        canceled.set()
        raise rid.Cancelled()
    monkeypatch.setattr(v, "latest", slow)
    preferences.write({**preferences.DEFAULTS, "daily_discovery": True})
    async def test(app, pilot):
        await until(pilot, started.is_set)
        preferences.write(preferences.DEFAULTS)
        app.refresh_discovery_preferences()
        await until(pilot, canceled.is_set)
        assert app._discovery_status is None and not app._discovery_enabled
    run(test)


def test_short_cli_commands_ignore_enabled_dashboard_preference(metadata_sources, registry):
    from typer.testing import CliRunner

    from opencode_sandbox.cli import app
    preferences.write({**preferences.DEFAULTS, "daily_discovery": True})
    for args in (["list"], ["--version"], ["opencode", "versions"]):
        result = CliRunner().invoke(app, args)
        assert result.exit_code == 0, result.output
    assert not registry["requests"] and not metadata_sources


def test_failure_is_local_details_not_an_availability_toast(metadata_sources, registry):
    preferences.write({**preferences.DEFAULTS, "daily_discovery": True})
    registry["status"] = 500
    async def test(app, pilot):
        await until(pilot, lambda: app._discovery_status is not None)
        assert "HTTP 500" in app._discovery_status["scheduling_error"]
        assert str(app.query_one("#ocversions", Button).label) == "Updates"
        assert not any("npm" in n.message for n in app._notifications)
    run(test)
    assert not metadata_sources


def test_availability_never_uses_base_build_labels_or_unknown_runtime(metadata_sources):
    c.create("ocs-test-unknown-version", "scratch")
    assert update_discovery.available() == 0


def test_invalid_policy_and_unknown_history_do_not_break_quiet_indicator(metadata_sources, registry):
    v.latest()
    bad = c.create("ocs-test-bad-notice-policy", "scratch")
    bad["opencode_policy"] = []
    c.save(bad)
    history(bad)
    assert update_discovery.available() == 0


def test_unavailable_scheduling_is_disclosed_without_disabling_manual_ui(metadata_sources, registry, monkeypatch):
    from opencode_sandbox import updates
    monkeypatch.setattr(updates, "base_inventory", lambda *a, **k: {"state": "not built", "eligible": False})
    preferences.write({**preferences.DEFAULTS, "daily_discovery": True})
    monkeypatch.setattr(cache, "write", lambda *a, **k: False)
    async def test(app, pilot):
        await until(pilot, lambda: app._discovery_status is not None)
        assert "Automatic discovery unavailable" in app._discovery_status["scheduling_error"]
        assert not registry["requests"]
        await pilot.press("v", "3", "c")
        screen = app.screen
        await until(pilot, lambda: not screen._active)
        assert "npm: 2.2.0" in screen.discovery_text() and len(registry["requests"]) == 1
        await pilot.press("d")
        assert "Automatic discovery unavailable" in app.screen.report
    run(test, (80, 24))


def test_disabling_real_http_attempt_reaps_child_and_keeps_daily_claim(metadata_sources, registry, monkeypatch):
    preferences.write({**preferences.DEFAULTS, "daily_discovery": True})
    registry["delay"] = 1
    children = []
    real_popen = c.subprocess.Popen
    def popen(argv, *a, **k):
        process = real_popen(argv, *a, **k)
        if any("http_probe.py" in str(arg) for arg in argv): children.append(process)
        return process
    monkeypatch.setattr(c.subprocess, "Popen", popen)
    async def test(app, pilot):
        await until(pilot, lambda: len(registry["requests"]) == 1)
        preferences.write(preferences.DEFAULTS)
        app.refresh_discovery_preferences()
        await until(pilot, lambda: children and all(p.poll() is not None for p in children))
        assert v.discovery()["success"] is None
        assert v.discovery()["attempt"]["error"] == "check did not complete"
        preferences.write({**preferences.DEFAULTS, "daily_discovery": True})
        app.refresh_discovery_preferences()
        await until(pilot, lambda: app._discovery_status is not None)
        assert "check did not complete" in app._discovery_status["scheduling_error"]
        assert len(registry["requests"]) == 1 and len(children) == 1
    run(test)


def test_rate_limited_ui_preserves_attempt_time_and_retry_fields(metadata_sources, registry, monkeypatch):
    from opencode_sandbox import updates
    monkeypatch.setattr(updates, "base_inventory", lambda *a, **k: {"state": "not built", "eligible": False})
    registry.update(status=429, headers={"Retry-After": "900000"})
    async def test(app, pilot):
        await pilot.press("v", "3", "c")
        screen = app.screen
        await until(pilot, lambda: not screen._active)
        first = v.discovery()["attempt"]
        assert screen.remote["attempt"]["at"] == first["at"] and first["retry_until"]
        await pilot.press("c")
        await until(pilot, lambda: not screen._active)
        assert screen.remote["attempt"]["at"] == first["at"]
        assert screen.remote["attempt"]["retry_until"] == first["retry_until"]
        assert "rate limited" in screen.discovery_text() and len(registry["requests"]) == 1
        await pilot.press("d")
        assert "retry_until" in app.screen.report
    run(test, (80, 24))
