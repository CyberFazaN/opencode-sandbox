"""Compact Updates views, independent results, cancellation and keyboard-only navigation."""
import asyncio
import threading
import time

import pytest
from test_tui import run, settle
from textual.widgets import Button, TextArea

from opencode_sandbox import core as c
from opencode_sandbox import distros, environment_checks, readiness, tui, updates
from opencode_sandbox import opencode_versions as v
from opencode_sandbox import update_cache as cache
from opencode_sandbox.updates_tui import UpdatesScreen


@pytest.fixture
def sources(monkeypatch):
    m = c.create("ocs-test-updates-pilot", "scratch")
    calls = []
    def environment(m, *, check=True):
        calls.append(("environment", m["id"], check))
        return {"state": "stopped", "version": None, "verification": "unknown", "observation": None}
    def base(d, *, check=False):
        calls.append(("base", d.id, check))
        return {"state": "current definition", "version": None, "observation": None, "eligible": True,
                "build_version": "2.0.0", "image": "sha256:" + "b" * 64}
    monkeypatch.setattr(v, "environment_version", environment)
    monkeypatch.setattr(environment_checks, 'check', lambda m, **kw: v.environment_version(m, check=True))
    monkeypatch.setattr(updates, "base_inventory", base)
    monkeypatch.setattr(v, "latest", lambda: calls.append(("npm",)) or "2.2.0")
    monkeypatch.setattr(readiness, "image_checks", list)
    return m, calls


async def until(pilot, predicate):
    deadline = time.monotonic() + 3
    while not predicate() and time.monotonic() < deadline: await pilot.pause(.02)
    assert predicate()


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
@pytest.mark.parametrize("entry", ["key", "button"])
def test_local_first_compact_views_focus_and_details(sources, size, entry):
    m, calls = sources
    async def test(app, pilot):
        if entry == "key": await pilot.press("v")
        else: app.query_one("#ocversions", Button).press(); await pilot.pause()
        await settle(pilot)
        screen = app.screen
        assert isinstance(screen, UpdatesScreen)
        assert not any(call[-1] is True or call == ("npm",) for call in calls)
        assert screen.view == "manager" and not screen.query_one("#updates-check", Button).disabled
        assert screen.query_one('#updates-update', Button).disabled
        for view, key in (("bases", "2"), ("environments", "3"), ("manager", "1")):
            await pilot.press(key)
            focus = '#updates-check' if view == 'manager' else '#updates-table'
            assert screen.view == view and app.focused is screen.query_one(focus)
            for selector in ("#updates-title", "#updates-tabs", '#updates-manager' if view == 'manager' else '#updates-table', "#updates-buttons", 'Footer'):
                widget = screen.query_one(selector)
                assert widget.region.height > 0 and widget.region.right <= size[0] and widget.region.bottom <= size[1]
            if view != 'manager': assert screen.query_one("#updates-table").region.height >= 3
            for button in screen.query(Button): assert button.region.bottom <= size[1] and button.region.right <= size[0]
            for shortcut in screen.query('FooterKey'):
                assert shortcut.region.right <= size[0] and shortcut.region.height == 1
            await pilot.press("d")
            assert isinstance(app.screen, tui.ReportScreen)
            assert app.screen.query_one("#report-text", TextArea).read_only
            await pilot.press("escape")
            assert app.screen is screen and app.focused is screen.query_one(focus)
        await pilot.press("3", "tab")
        assert app.focused is screen.query_one("#updates-check")
        await pilot.press("shift+tab")
        assert app.focused is screen.query_one("#updates-table")
        await pilot.press("escape")
        assert len(app.screen_stack) == 1
        assert c.resolve(m["id"]).get("operation") is None
    run(test, size)


def test_explicit_check_uses_selected_object_and_shares_npm_across_views(sources):
    m, calls = sources
    async def test(app, pilot):
        await pilot.press("v", "3", "c")
        await until(pilot, lambda: not app.screen._active)
        assert ("environment", m["id"], True) in calls and calls.count(("npm",)) == 1
        assert not any(call[0] == "base" and call[-1] is True for call in calls)
        assert "Available OpenCode: 2.2.0" in app.screen.discovery_text()
        await pilot.press("2")
        assert "Available OpenCode: 2.2.0" in app.screen.discovery_text()
        assert all(i["version"] is None for i in app.screen.items["bases"].values())
        await pilot.press('d')
        assert '"build_version": "2.0.0"' in app.screen.report
        await pilot.press('escape')
        await pilot.press("c")
        await until(pilot, lambda: not app.screen._active)
        assert sum(call[0] == "base" and call[-1] is True for call in calls) == 1
    run(test, (80, 24))


@pytest.mark.parametrize('key', ['c', 'C'])
def test_base_checks_refresh_eligibility_instead_of_trusting_cached_rows(sources, key):
    _m, calls = sources
    async def test(app, pilot):
        await pilot.press('v', '2')
        screen = app.screen
        for item in screen.items['bases'].values(): item.update(eligible=False, state='not built')
        await pilot.press(key)
        await until(pilot, lambda: not screen._active)
        checked = [entry for entry in calls if entry[0] == 'base' and entry[-1] is True]
        assert len(checked) == (1 if key == 'c' else len(distros.REGISTRY))
        assert calls.count(('npm',)) == 1
        for _, distro, _ in checked: assert screen.items['bases'][distro]['eligible'] is True
    run(test, (80, 24))


@pytest.mark.parametrize("source", ["npm", "environment", "base"])
def test_independent_check_failures_keep_inventory_and_other_results(sources, monkeypatch, source):
    m, _calls = sources
    def broken(*a, **k): raise RuntimeError("failure [literal] " + source)
    if source == "npm": monkeypatch.setattr(v, "latest", broken)
    if source == "environment": monkeypatch.setattr(v, "environment_version", broken)
    if source == "base": monkeypatch.setattr(updates, "base_inventory", broken)
    async def test(app, pilot):
        await pilot.press("v", "2" if source == "base" else "3", "c")
        screen = app.screen
        await until(pilot, lambda: not screen._active)
        assert screen.items["environments"][m["id"]]["name"] == m["name"]
        assert len(screen.items["bases"]) == len(distros.REGISTRY)
        if source == "npm": assert "RuntimeError: failure [literal] npm" in screen.discovery_text()
        else:
            section = "bases" if source == "base" else "environments"
            assert "RuntimeError:" in next(iter(screen.items[section].values()))["error"]
            assert "Available OpenCode: 2.2.0" in screen.discovery_text()
        await pilot.press("d")
        assert "failure [literal]" in app.screen.report
        assert "[literal]" in app.screen.query_one("#report-text", TextArea).text
    run(test, (80, 24))


def test_cached_remote_failure_and_stopped_history_remain_dated(sources):
    _m, calls = sources
    success = cache.evidence("2.2.0", "npm-metadata", {"url": v.REGISTRY, "major": v.MAJOR})
    success["at"] -= 2 * 86400
    cache.write(v._registry_key(), {"success": success, "attempt": {"at": time.time(), "ok": False, "error": "HTTP 429; retry later"}})
    async def test(app, pilot):
        await pilot.press("v", "3")
        screen = app.screen
        assert "checked" in screen.discovery_text() and "stale" in screen.discovery_text()
        assert "HTTP 429" in screen.discovery_text()
        assert ("npm",) not in calls
    run(test)


def test_slow_sources_publish_independently_and_coalesce_inflight_checks(sources, monkeypatch):
    m, calls = sources
    release, started = threading.Event(), threading.Event()
    def latest():
        calls.append(("npm",)); started.set()
        assert release.wait(4)
        return "2.2.0"
    monkeypatch.setattr(v, "latest", latest)
    async def test(app, pilot):
        await pilot.press("v", "3", "c")
        screen = app.screen
        assert await asyncio.to_thread(started.wait, 1)
        await until(pilot, lambda: ("environments", m["id"]) not in screen._active)
        assert "Checking available version on npm" in screen.discovery_text()
        await pilot.press("2")
        assert calls.count(("npm",)) == 1
        assert screen.items["environments"][m["id"]]["state"] == "stopped"
        release.set()
        await until(pilot, lambda: not screen._active)
        assert "Available OpenCode: 2.2.0" in screen.discovery_text()
    try: run(test, (80, 24))
    finally: release.set()


def test_pending_journal_and_operation_error_are_persistent_details(sources):
    m, _calls = sources
    c.mark(m, "error", operation="opencode-update", last_error="rollback failed [test]")
    async def test(app, pilot):
        await pilot.press("v", "3", "d")
        assert "opencode-update" in app.screen.report and "rollback failed [test]" in app.screen.report
        assert "opencode update-recover" in app.screen.report
        assert c.resolve(m["id"])["operation"] == "opencode-update"
    run(test)


def test_late_inventory_cannot_replace_a_newer_explicit_check(sources, monkeypatch):
    m, _calls = sources
    release, started, finished = threading.Event(), threading.Event(), threading.Event()
    def environment(m, *, check=True):
        if check: return {"state": "running", "version": "2.2.0", "verification": "verified"}
        started.set()
        try:
            assert release.wait(4)
            return {"state": "stopped", "version": "2.1.4", "verification": "last-verified"}
        finally: finished.set()
    monkeypatch.setattr(v, "environment_version", environment)
    async def test(app, pilot):
        await pilot.press("v", "3")
        assert await asyncio.to_thread(started.wait, 1)
        screen = app.screen
        await pilot.press("c")
        await until(pilot, lambda: not screen._active)
        assert screen.items["environments"][m["id"]]["version"] == "2.2.0"
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
        await settle(pilot)
        assert screen.items["environments"][m["id"]]["version"] == "2.2.0"
    try: run(test, (80, 24))
    finally: release.set()


def test_close_preserves_prior_evidence_and_refuses_late_results(sources, monkeypatch):
    m, _calls = sources
    release, started = threading.Event(), threading.Event()
    observation = cache.evidence("2.1.4", "container-exec", {})
    def environment(m, *, check=True):
        if check:
            started.set()
            assert release.wait(4)
            return {"state": "running", "version": "2.99.0"}
        return {"state": "stopped", "version": "2.1.4", "observation": observation, "verification": "last-verified"}
    monkeypatch.setattr(v, "environment_version", environment)
    async def test(app, pilot):
        await pilot.press("v", "3")
        screen = app.screen
        await until(pilot, lambda: screen.items["environments"][m["id"]].get("version") == "2.1.4")
        await pilot.press("c")
        assert await asyncio.to_thread(started.wait, 1)
        assert not screen.query('#updates-cancel')
        await pilot.press('escape')
        assert not screen._active
        assert screen.items["environments"][m["id"]]["observation"] == observation
        release.set()
        await settle(pilot)
        assert screen.items["environments"][m["id"]]["version"] == "2.1.4"
    try: run(test, (80, 24))
    finally: release.set()


def test_selection_survives_view_changes_and_resize_without_hidden_dashboard_actions(sources, monkeypatch):
    m, _calls = sources
    second = c.create("ocs-test-second-long-" + "a" * 40, "scratch")
    mutations = []
    monkeypatch.setattr(c, "start", lambda *a: mutations.append("start"))
    async def test(app, pilot):
        await pilot.press("v", "3")
        screen = app.screen
        assert screen.selected_key() == m["id"] or screen.selected_key() == second["id"]
        table = screen.query_one("#updates-table")
        table.move_cursor(row=table.get_row_index(m["id"]))
        await pilot.press("2", "3")
        assert screen.selected_key() == m["id"]
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert table.virtual_size.width <= table.size.width
        await pilot.press("x", "o")
        assert app.screen is screen and mutations == []
        await pilot.press("d", "c", "3", "f5")
        assert isinstance(app.screen, tui.ReportScreen) and mutations == []
    run(test, (120, 40))


@pytest.mark.parametrize("state", ["stopped", "not-created", "running"])
def test_check_and_details_never_authorize_mutations_or_infer_installed_labels(sources, monkeypatch, state):
    m, calls = sources
    mutations = []
    monkeypatch.setattr(v, "update_environment", lambda *a, **k: mutations.append(a))
    def environment(*a, **k): return {"state": state, "version": None, "observation": None, "verification": "unknown"}
    monkeypatch.setattr(v, "environment_version", environment)
    async def test(app, pilot):
        await pilot.press("v", "3", "c")
        screen = app.screen
        await until(pilot, lambda: not screen._active)
        assert screen.items["environments"][m["id"]]["version"] is None
        # UP-11 enables a read-only review request, not installation based on this cached row.
        assert not screen.query_one("#updates-update", Button).disabled
        assert 'Check complete' in str(screen.query_one("#updates-reason").render())
        assert mutations == []
        await pilot.press("d")
        assert "Explicit Check may temporarily start stopped containers" in app.screen.report
        assert "Pins, ownership and pending journals" in app.screen.report
        assert calls.count(("npm",)) == 1
        await pilot.press("escape", "u")
        assert app.focused is app.screen.query_one("#update-target")
        assert app.screen.query_one("#update-target").value == "latest" and mutations == []
        await pilot.press("escape")
        assert app.screen is screen and mutations == [] and c.resolve(m["id"]).get("operation") is None
    run(test, (80, 24))


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
def test_dashboard_advisories_are_retained_and_disclosed_without_covering_controls(sources, size):
    async def test(app, pilot):
        await settle(pilot)
        app._disable_notifications = False  # run_test normally omits the production toast rack
        app._replace_advisory("images", "Old definition", title="Base images need attention", detail="Retained image [literal] needs review")
        owned = app._advisories["images"][1]
        await pilot.press("v")
        screen = app.screen
        await pilot.pause()
        assert "dashboard notice(s): Details" in str(screen.query_one("#updates-title").render())
        assert screen.query_one("ToastRack").region.height == 0
        assert app._advisories["images"][1] is owned
        assert owned in list(app._notifications)
        await pilot.press("d")
        assert "Retained image [literal] needs review" in app.screen.report
        await pilot.press("escape", "escape")
        assert app._advisories["images"][1] is owned
        assert len(app.screen_stack) == 1
    run(test, size)


def test_empty_inventory_still_checks_and_discloses_full_source_failure(monkeypatch):
    monkeypatch.setattr(readiness, "image_checks", list)
    message = "HTTP failure " + "long detail " * 100
    def latest(): raise c.SandboxError(message)
    monkeypatch.setattr(v, "latest", latest)
    async def test(app, pilot):
        await pilot.press("v", "3", "c")
        screen = app.screen
        await until(pilot, lambda: not screen._active)
        assert not screen.items["environments"]
        assert not screen.query_one("#updates-details", Button).disabled
        await pilot.press("d")
        assert message in app.screen.report and "Discovery evidence:" in app.screen.report
    run(test, (80, 24))
