"""Base Images actions use component plans/handlers, not cached inventory as mutation authority."""
import asyncio
import threading

import pytest
import test_base_rollback
from test_opencode_versions import OLD, fake_docker
from test_tui import run
from test_updates_tui import until
from textual.widgets import Button, Checkbox, Select, Static

from opencode_sandbox import build_output, distros, readiness, updates
from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v
from opencode_sandbox.base_updates_tui import (
    BaseConsentScreen,
    BaseRollbackScreen,
    BaseTargetScreen,
)

copies = test_base_rollback.copies


@pytest.fixture
def sources(monkeypatch):
    calls = []
    monkeypatch.setattr(c, 'docker', fake_docker(calls))
    monkeypatch.setattr(c, 'ensure_runtime', lambda *a: None)
    monkeypatch.setattr(c, 'require_docker_space', lambda _: None)
    monkeypatch.setattr(readiness, 'image_checks', list)
    monkeypatch.setattr(v, 'latest', lambda: '2.1.4')
    return calls


async def review(app, pilot, refresh=False):
    await pilot.press('b')
    assert isinstance(app.screen, BaseTargetScreen)
    assert not app.screen.query(Checkbox) and 'always upgrade system packages' in ' '.join(str(w.render()) for w in app.screen.query(Static))
    app.screen.query_one('#base-refresh', Select).value = refresh
    app.screen.query_one('#base-target-review', Button).press()
    await until(pilot, lambda: isinstance(app.screen, BaseConsentScreen))
    await pilot.pause()


@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
@pytest.mark.parametrize('refresh', [False, True])
def test_build_exact_mode_consent_cancel_then_preserving_executor(sources, monkeypatch, size, refresh):
    async def test(app, pilot):
        app._disable_notifications = False
        app._replace_advisory('images', 'test notice', title='test warning', detail='Keep notification [literal]')
        await pilot.press('v', '2')
        screen = app.screen
        for button in screen.query(Button):
            if button.display: assert button.region.bottom <= size[1]
        assert screen.query_one('#updates-table').region.height >= 3
        await review(app, pilot, refresh)
        message = app.screen.message
        assert OLD in message and 'Exact OpenCode target: 2.1.4' in message
        assert ('Refresh & Rebuild' if refresh else 'Cached rebuild') in message
        assert 'System packages: always refreshed and upgraded in both modes (apt-get update, then apt-get upgrade)' in message
        assert 'kept as a rollback copy' in message and 'pins remain enforced' in message
        assert app.focused.id == 'base-cancel'
        for button in app.screen.query(Button): assert button.region.bottom <= size[1]
        assert app.screen.query_one('ToastRack').region.height == 0
        assert not any(a[0] in ('build', 'run', 'tag') for a in sources)
        await pilot.press('escape')
        await review(app, pilot, refresh)
        monkeypatch.setattr(v, 'latest', lambda: pytest.fail('no later target substitution'))
        app.screen.query_one('#base-confirm', Button).press()
        await until(pilot, lambda: screen.operation_result and not app._operation_pending)
        assert 'verified and published' in screen.operation_result
        build = next(a for a in sources if a[0] == 'build')
        assert ('--pull' in build) == refresh and ('--no-cache' in build) == refresh
        assert any(a[0] == 'tag' and a[1] == OLD and 'previous' in a[-1] for a in sources)
        assert not any(a == ('image', 'rm', OLD) for a in sources)
        await pilot.press('d')
        assert 'Base operation (app-owned' in app.screen.report
        assert 'Keep notification [literal]' in app.screen.report
    run(test, size)


def test_missing_build_is_reviewable_but_foreign_base_never_authorized_from_cache(sources, monkeypatch):
    real = c.docker
    def foreign(*a, **kw):
        if a == ('image', 'inspect', distros.get('debian').image):
            import json
            result = real(*a, **kw)
            value = json.loads(result.stdout)
            value[0]['Config']['Labels'] = {}
            result.stdout = json.dumps(value)
            return result
        return real(*a, **kw)
    async def test(app, pilot):
        await pilot.press('v', '2')
        screen = app.screen
        # Deliberately stale/misleading cache row does not authorize replacing the real image.
        screen.items['bases']['debian'].update(state='not built', eligible=True)
        monkeypatch.setattr(c, 'docker', foreign)
        await pilot.press('b')
        app.screen.query_one('#base-target-review', Button).press()
        await until(pilot, lambda: screen.operation_result)
        assert 'unmanaged' in screen.operation_result and app.screen is screen
        assert not any(a[0] in ('build', 'run', 'tag') for a in sources)
    run(test, (80, 24))


def test_base_mutation_survives_close_cancel_and_normal_quit_with_bounded_details(sources, monkeypatch):
    started, release = threading.Event(), threading.Event()
    real_build = c.build_image
    def build(*args, **kwargs):
        build_output.phase('test held build; not canceled')
        build_output.current().write(b'test bounded output [literal]\n')
        started.set()
        assert release.wait(6)
        assert c._RUNTIME_FEEDBACK.get()['cancelled'] is None
        return real_build(*args, **kwargs)
    monkeypatch.setattr(c, 'build_image', build)
    async def test(app, pilot):
        await pilot.press('v', '2')
        await review(app, pilot)
        app.screen.query_one('#base-confirm', Button).press()
        assert await asyncio.to_thread(started.wait, 1)
        await pilot.press('escape', 'q')
        assert app.is_running and app._operation_pending and app._updates_mutation_active
        await pilot.press('v', '2', 'd')
        assert 'test bounded output [literal]' in app.screen.report
        assert 'test held build' in app.screen.report
        await pilot.press('escape')
        release.set()
        await until(pilot, lambda: not app._operation_pending)
        assert 'verified and published' in app._base_operation['result']
        assert app._base_operation['phase'] == 'Complete'
    try: run(test, (80, 24))
    finally: release.set()


@pytest.mark.parametrize('count', [0, 1, 2])
def test_rollback_consolidates_and_requires_explicit_multicopy_choice(copies, monkeypatch, count):
    monkeypatch.setattr(readiness, 'image_checks', list)
    monkeypatch.setattr(updates, 'base_inventory', lambda *a, **k: {'state': 'test managed base', 'eligible': True})
    if count == 0: del copies.tags[copies.first]
    if count == 2: copies.add(copies.second, 'b', '2.1.3', '2020-01-01')
    async def test(app, pilot):
        await pilot.press('v', '2', 'r')
        screen = app.screen_stack[-2] if isinstance(app.screen, (BaseConsentScreen, BaseRollbackScreen)) else app.screen
        if count == 0:
            await until(pilot, lambda: screen.operation_result)
            assert 'No rollback copy' in screen.operation_result
            return
        await until(pilot, lambda: isinstance(app.screen, BaseConsentScreen if count == 1 else BaseRollbackScreen))
        await pilot.pause()
        if count == 2:
            assert app.screen.query_one('#base-copy', Select).value not in {copy.image_id for copy in v.base_rollback_inventory().copies}
            app.screen.query_one('#base-copy-review', Button).press()
            await pilot.pause()
            assert isinstance(app.screen, BaseRollbackScreen) and not copies.verified
            app.screen.query_one('#base-copy', Select).value = test_base_rollback.iid('b')
            app.screen.query_one('#base-copy-review', Button).press()
            await until(pilot, lambda: isinstance(app.screen, BaseConsentScreen))
            await pilot.pause()
        target = test_base_rollback.iid('b' if count == 2 else 'a')
        assert target in app.screen.message and 'current OS/tool/OpenCode checks' in app.screen.message
        assert not copies.verified
        app.screen.query_one('#base-confirm', Button).press()
        await until(pilot, lambda: not app._operation_pending and getattr(app, '_base_operation', {}).get('result'))
        assert copies.tags[copies.d.image] == target and copies.verified[0][1] == target
        assert any('previous' in tag and image == test_base_rollback.iid('c') for tag, image in copies.tags.items())
    run(test, (80, 24))


def test_canceled_late_base_planning_cannot_publish_consent_or_start_a_build(sources, monkeypatch):
    started, release = threading.Event(), threading.Event()
    prepare = v.prepare_base_build
    def slow(*a, **kw):
        started.set()
        assert release.wait(5)
        return prepare(*a, **kw)
    monkeypatch.setattr(v, 'prepare_base_build', slow)
    async def test(app, pilot):
        await pilot.press('v', '2', 'b')
        app.screen.query_one('#base-target-review', Button).press()
        assert await asyncio.to_thread(started.wait, 1)
        await pilot.press('escape')
        release.set()
        await pilot.pause(.2)
        assert len(app.screen_stack) == 1 and not app._operation_pending
        assert not any(a[0] in ('build', 'run', 'tag') for a in sources)
    try: run(test, (80, 24))
    finally: release.set()


def test_changed_rollback_copy_after_consent_is_refused_in_dashboard(copies, monkeypatch):
    monkeypatch.setattr(readiness, 'image_checks', list)
    monkeypatch.setattr(updates, 'base_inventory', lambda *a, **kw: {'state': 'test managed base', 'eligible': True})
    async def test(app, pilot):
        await pilot.press('v', '2', 'r')
        await until(pilot, lambda: isinstance(app.screen, BaseConsentScreen))
        await pilot.pause()
        copies.tags[copies.first] = copies.tags[copies.d.image]
        app.screen.query_one('#base-confirm', Button).press()
        await until(pilot, lambda: getattr(app, '_base_operation', {}).get('result'))
        assert 'changed' in app._base_operation['result'] and not copies.verified
        assert not any(a[0] == 'tag' or a[:2] == ('image', 'rm') for a in copies.calls)
    run(test, (80, 24))


def test_previous_base_result_cannot_hide_a_different_active_operation(sources):
    async def test(app, pilot):
        await pilot.press('v', '2')
        screen = app.screen
        app._base_operation = {'distro': 'debian', 'phase': 'Complete', 'output': '', 'result': 'Previous base build complete'}
        app._operation_pending = True
        screen._render_selected()
        assert 'An operation is running' in str(screen.query_one('#updates-reason').render())
        assert screen.query_one('#updates-update', Button).disabled
        app._operation_pending = False
    run(test, (80, 24))
