"""UP-06: category-owned notices/status, mocked checks with deterministic Textual pilots."""
import asyncio
import threading

import pytest
from test_tui import run

from opencode_sandbox import core as c
from opencode_sandbox import readiness as r

TITLES = {"daemon": "Docker is not ready", "resources": "Resource-limit support", "images": "Base images need attention"}


@pytest.fixture(autouse=True)
def checks(monkeypatch):
    state = {"daemon": r.Check("daemon", "Daemon identity", r.PASSED, "verified"),
             "resources": r.Check("resource-support", "Resource-limit support", r.PASSED, "supported"),
             "images": [r.Check("image-debian", "Base image Debian", r.PASSED, "current")]}
    calls = []
    def get(category):
        calls.append(category)
        value = state[category]
        if isinstance(value, Exception): raise value
        return value
    monkeypatch.setattr(r, "daemon_check", lambda: get("daemon"))
    monkeypatch.setattr(r, "resource_support_check", lambda: get("resources"))
    monkeypatch.setattr(r, "image_checks", lambda: get("images"))
    return state, calls


def notes(app, category):
    return [note for note in app._notifications if note.title == TITLES[category]]


def status(app):
    return str(app.query_one("#status").render())


def show(app, category, result=r.WARNING, detail="old warning"):
    if category == "daemon":
        app._prerequisites_ready() if result == r.PASSED else app._show_prerequisites(detail)
    else:
        check = r.Check(category, TITLES[category], result, detail)
        app._show_resource_support(check) if category == "resources" else app._show_image_checks([check])


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
@pytest.mark.parametrize("category", TITLES)
def test_repeated_warning_unknown_and_success_replace_only_owned_notice(size, category):
    async def test(app, pilot):
        await app.workers.wait_for_complete()
        # Even the same title is not ownership proof; preserve an unrelated notification object.
        app.notify("Keep unrelated [literal] notice", title=TITLES[category])
        await pilot.pause()
        unrelated, = notes(app, category)
        for detail in ("old warning", "old warning", "new warning [literal]"):
            show(app, category, detail=detail)
        # No event-loop yield between replacements: a queued old toast must not reappear later.
        await pilot.pause()
        owned = [note for note in notes(app, category) if note is not unrelated]
        assert len(owned) == 1 and "new warning [literal]" in owned[0].message and not owned[0].markup
        show(app, category, r.NOT_CHECKED, "inspection unavailable [timeout]")
        await pilot.pause()
        owned = [note for note in notes(app, category) if note is not unrelated]
        assert len(owned) == 1 and "old warning" not in owned[0].message and "new warning" not in owned[0].message
        assert "inspection unavailable [timeout]" in owned[0].message
        if category != "daemon":
            assert "[not checked]" in owned[0].message and "could not" in status(app)
        show(app, category, r.PASSED)
        await pilot.pause()
        assert notes(app, category) == [unrelated] and status(app) == "Ready"
        show(app, category)
        show(app, category, r.PASSED)
        await pilot.pause()
        assert notes(app, category) == [unrelated] and status(app) == "Ready"
        pane = app.query_one("#status")
        assert pane.region.height == 1 and pane.region.right <= size[0] and pane.region.bottom <= size[1]
    run(test, size)


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
def test_overlapping_categories_reveal_the_remaining_advisory(size):
    async def test(app, pilot):
        await app.workers.wait_for_complete()
        for category in TITLES: show(app, category)
        original = {category: notes(app, category)[0] for category in TITLES}
        assert status(app).startswith("Docker is not ready")
        show(app, "images", r.PASSED)
        assert not notes(app, "images") and status(app).startswith("Docker is not ready")
        assert all(notes(app, category) == [original[category]] for category in ("daemon", "resources"))
        show(app, "images", detail="new image warning")
        show(app, "daemon", r.PASSED)
        assert status(app).startswith("Resource-limit support") and notes(app, "resources") == [original["resources"]]
        show(app, "resources", r.PASSED)
        assert status(app).startswith("Base image checks") and "new image warning" in notes(app, "images")[0].message
        # An expired/dismissed toast still leaves its category's status until fresh evidence.
        app._unnotify(notes(app, "images")[0])
        assert status(app).startswith("Base image checks")
        show(app, "images", r.PASSED)
        assert status(app) == "Ready"
    run(test, size)


class Waiter:
    is_cancelled = False


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
@pytest.mark.parametrize("category", TITLES)
def test_advisory_transitions_and_wait_cleanup_preserve_mutation_progress_and_result(size, category):
    async def test(app, pilot):
        await app.workers.wait_for_complete()
        waiter = Waiter()
        app._runtime_notice("Waiting for Docker readiness…", waiter)
        app._operation_pending = True
        # This prefix previously allowed a runtime cleanup to erase a mutation's status.
        progress = "Waiting for Docker readiness during active mutation [literal]"
        app._set_busy(progress)
        for result in (r.WARNING, r.NOT_CHECKED, r.PASSED, r.WARNING):
            show(app, category, result)
            assert status(app) == progress and app._operation_pending
        app._runtime_notice(None, waiter)
        assert status(app) == progress and app._operation_pending
        app._finished("Mutation failed; recovery required", error=True)
        show(app, category, r.PASSED)
        app._runtime_notice(None, waiter)
        assert status(app) == "Mutation failed; recovery required" and not app._operation_pending
    run(test, size)


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
def test_readiness_wait_owns_status_until_last_waiter_then_reveals_current_advisory(size):
    async def test(app, pilot):
        await app.workers.wait_for_complete()
        first, second = Waiter(), Waiter()
        app._runtime_notice("Waiting for Docker readiness: first", first)
        app._runtime_notice("Waiting for Docker readiness: second", second)
        show(app, "images")
        show(app, "resources", r.NOT_CHECKED, "unavailable")
        show(app, "images", r.PASSED)
        assert status(app).endswith("second")
        app._runtime_notice(None, second)
        assert status(app).endswith("first")
        first.is_cancelled = True
        app._runtime_notice("obsolete wait", first)
        assert status(app).endswith("first")
        app._runtime_notice(None, first)
        assert status(app).startswith("Resource-limit support could not be verified")
        show(app, "resources", r.PASSED)
        assert status(app) == "Ready"
        await pilot.pause()
        assert not any(note.title == "Docker readiness" for note in app._notifications)
    run(test, size)


@pytest.mark.parametrize("category", ["resources", "images"])
@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
def test_worker_check_exception_is_unknown_in_its_own_category_and_other_checks_continue(checks, category, size):
    state, calls = checks
    async def test(app, pilot):
        await app.workers.wait_for_complete()
        show(app, category, detail="old warning")
        state[category] = c.SandboxError("probe unavailable [test]")
        calls.clear()
        await app._prerequisites_worker().wait()
        assert calls == ["daemon", "resources", "images"]
        note, = notes(app, category)
        assert "[not checked]" in note.message and "probe unavailable [test]" in note.message
        assert "old warning" not in note.message and "could not" in status(app)
        assert not notes(app, "daemon")
        state[category] = r.Check("resource-support", "Resource-limit support", r.PASSED, "supported") if category == "resources" else []
        await app._prerequisites_worker().wait()
        assert not notes(app, category) and status(app) == "Ready"
    run(test, size)


def test_failed_daemon_refresh_does_not_claim_skipped_categories_passed(checks):
    state, calls = checks
    async def test(app, pilot):
        await app.workers.wait_for_complete()
        show(app, "images")
        show(app, "resources")
        previous = [notes(app, category)[0] for category in ("images", "resources")]
        state["daemon"] = c.SandboxError("daemon unavailable")
        calls.clear()
        await app._prerequisites_worker().wait()
        assert calls == ["daemon"] and status(app).startswith("Docker is not ready")
        assert [notes(app, category)[0] for category in ("images", "resources")] == previous
    run(test, (80, 24))


def test_metadata_only_refresh_neither_rechecks_nor_clears_advisories(checks):
    _, calls = checks
    async def test(app, pilot):
        await app.workers.wait_for_complete()
        show(app, "images")
        note, = notes(app, "images")
        calls.clear()
        m = c.create("ocs-test-up06-metadata", "scratch")
        app._refresh_if_changed()
        assert not calls and notes(app, "images") == [note] and app.query_one("#envs").row_count == 1
        assert c.resolve(m["id"]).get("operation") is None
    run(test, (80, 24))


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
def test_replaced_prerequisite_worker_cannot_publish_obsolete_image_warning(checks, monkeypatch, size):
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    block = {"old": False}
    def images():
        if block["old"]:
            started.set()
            try:
                assert release.wait(3)
                return [r.Check("image-debian", "Base image Debian", r.WARNING, "obsolete image warning")]
            finally: finished.set()
        return []
    monkeypatch.setattr(r, "image_checks", images)
    async def test(app, pilot):
        await app.workers.wait_for_complete()
        block["old"] = True
        old = app._prerequisites_worker()
        assert await asyncio.to_thread(started.wait, 1)
        block["old"] = False
        await app._prerequisites_worker().wait()
        assert old.is_cancelled
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
        await pilot.pause()
        assert not notes(app, "images") and status(app) == "Ready"
    try:
        run(test, size)
    finally:
        release.set()
