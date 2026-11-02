"""Environment Updates: exact consent, real handlers with fake Docker, owned mutation workers."""
import asyncio
import hashlib
import threading
from types import SimpleNamespace

import pytest
import test_environment_actions
from test_opencode_lifecycle import Crash, env
from test_tui import run
from test_updates_tui import until
from textual.widgets import Button, Input, Select, TextArea

from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v
from opencode_sandbox import readiness, updates
from opencode_sandbox.environment_updates_tui import (
    EnvironmentConsentScreen,
    PolicyScreen,
    TargetScreen,
)
from opencode_sandbox.management_tui import RecoveryScreen

runtime = test_environment_actions.runtime


@pytest.fixture
def sources(runtime, monkeypatch):
    monkeypatch.setattr(readiness, 'image_checks', list)
    monkeypatch.setattr(updates, 'base_inventory', lambda *a, **k: {'state': 'test image', 'eligible': False})
    monkeypatch.setattr(v, 'latest', lambda: '2.2.0')
    return env()


async def review_update(app, pilot, target='2.2.0'):
    await pilot.press('u')
    assert isinstance(app.screen, TargetScreen)
    app.screen.query_one('#update-target', Input).value = target
    await pilot.press('enter')
    await until(pilot, lambda: isinstance(app.screen, EnvironmentConsentScreen))
    await pilot.pause()


def test_keyboard_target_edit_and_enter_cannot_reach_hidden_dashboard(sources):
    async def test(app, pilot):
        await pilot.press('v', '3', 'u')
        assert isinstance(app.screen, TargetScreen)
        assert app.focused is app.screen.query_one('#update-target', Input)
        await pilot.press('ctrl+a', 'ctrl+k', '2', '.', '1', '.', '4')
        assert app.screen.query_one('#update-target', Input).value == '2.1.4'
        await pilot.press('enter')
        await until(pilot, lambda: isinstance(app.screen, EnvironmentConsentScreen))
        assert 'exact OpenCode 2.1.4' in app.screen.message
    run(test, (80, 24))


def test_subscreen_and_unmounted_table_events_do_not_reach_dashboard_selection(sources, monkeypatch):
    calls = []
    async def test(app, pilot):
        await pilot.press('v', '3')
        table = app.screen.query_one('#updates-table')
        monkeypatch.setattr(app, 'update_details', lambda: calls.append('dashboard details'))
        app.on_data_table_row_highlighted(SimpleNamespace(data_table=table))
        app.on_data_table_row_selected(SimpleNamespace(data_table=table))
        assert calls == []
        unmounted = SimpleNamespace(id='envs', is_mounted=False)
        app.on_data_table_row_highlighted(SimpleNamespace(data_table=unmounted))
        app.on_data_table_row_selected(SimpleNamespace(data_table=unmounted))
        assert calls == []
    run(test, (80, 24))


@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
def test_exact_update_consent_cancel_then_existing_executor_stops(sources, runtime, size, monkeypatch):
    m = sources
    async def test(app, pilot):
        await pilot.press('v', '3')
        screen = app.screen
        for button in screen.query(Button):
            if button.display: assert button.region.bottom <= size[1] and button.region.right <= size[0]
        assert screen.query_one('#updates-table').region.height >= 3
        await review_update(app, pilot, 'latest')
        assert 'exact OpenCode 2.2.0' in app.screen.message
        assert all(word in app.screen.message for word in ('checkpoint', 'Temporarily start', 'then stop', 'network', 'container:', runtime.cid))
        assert not any(a[0] in ('commit', 'start', 'exec', 'stop') for a in runtime.calls)
        for button in app.screen.query(Button): assert button.region.bottom <= size[1]
        await pilot.press('escape')
        assert app.screen is screen and not app._operation_pending
        await review_update(app, pilot)
        monkeypatch.setattr(v, 'latest', lambda: pytest.fail('must not substitute a later target'))
        app.screen.query_one('#environment-confirm', Button).press()
        await until(pilot, lambda: not app._operation_pending and screen.operation_result)
        assert 'update complete; stopped' in screen.operation_result and not runtime.running
        assert next(a for a in runtime.calls if 'ocs-install-opencode' in a)[-1] == '2.2.0'
        assert c.resolve(m['id'])['operation'] is None
        await pilot.press('d')
        assert 'Last operation result:' in app.screen.report
    run(test, size)


@pytest.mark.parametrize('reason', ['running', 'network', 'pin', 'journal', 'absent'])
def test_live_refusals_never_start_stop_install_or_change_policy(sources, runtime, reason):
    m = sources
    if reason == 'running': runtime.running = True
    if reason == 'network': m['runtime']['network'] = 'none'; c.save(m)
    if reason == 'pin': v.set_policy(m, 'pinned', '2.1.4')
    if reason == 'journal': c.mark(m, 'updating', operation=v.UPDATE_OP)
    if reason == 'absent': runtime.exists = False
    before = (c.env_dir(m['id']) / 'metadata.json').read_bytes()
    async def test(app, pilot):
        await pilot.press('v', '3')
        screen = app.screen
        runtime.calls.clear()
        if reason == 'journal':
            screen.action_environment('update')
            assert 'update-recover' in screen.operation_result
        else:
            await pilot.press('u')
            app.screen.query_one('#update-target', Input).value = '2.2.0'
            await pilot.press('enter')
            await until(pilot, lambda: screen.operation_result is not None)
        assert app.screen is screen and not app._operation_pending
        assert not any(a[0] in ('commit', 'start', 'stop', 'exec', 'rm') for a in runtime.calls)
        assert (c.env_dir(m['id']) / 'metadata.json').read_bytes() == before
    run(test, (80, 24))


def test_changed_selection_and_container_do_not_redirect_or_execute_confirmed_update(sources, runtime):
    second = env('ocs-test-second-consent')
    async def test(app, pilot):
        await pilot.press('v', '3')
        screen = app.screen
        table = screen.query_one('#updates-table')
        table.move_cursor(row=table.get_row_index(sources['id']))
        await review_update(app, pilot)
        table.move_cursor(row=table.get_row_index(second['id']))
        runtime.cid = 'f' * 64
        runtime.calls.clear()
        app.screen.query_one('#environment-confirm', Button).press()
        await until(pilot, lambda: screen.operation_result and not app._operation_pending)
        assert 'changed since confirmation' in screen.operation_result
        assert not any(a[0] in ('commit', 'start', 'stop', 'exec') for a in runtime.calls)
        assert c.resolve(second['id']).get('opencode_update') is None
    run(test)


def test_explicit_start_stays_running_and_check_remains_separate(sources, runtime):
    async def test(app, pilot):
        await pilot.press('v', '3', 's')
        screen = app.screen_stack[-2] if isinstance(app.screen, EnvironmentConsentScreen) else app.screen
        await until(pilot, lambda: isinstance(app.screen, EnvironmentConsentScreen))
        await pilot.pause()
        assert 'remains running' in app.screen.message
        app.screen.query_one('#environment-confirm', Button).press()
        await until(pilot, lambda: screen.operation_result and not app._operation_pending)
        assert runtime.running and not any(a[0] == 'exec' for a in runtime.calls)
        await pilot.press('c')
        screen = app.screen
        await until(pilot, lambda: not screen._active)
        assert runtime.running and screen.items['environments'][sources['id']]['version'] == '2.1.4'
        assert not any(a[0] == 'stop' for a in runtime.calls)
    run(test, (80, 24))


@pytest.mark.parametrize('mode,pin', [('manual', None), ('notify', None), ('pinned', '2.1.4')])
def test_policy_and_pin_require_separate_consent_without_installation(sources, runtime, mode, pin):
    async def test(app, pilot):
        await pilot.press('v', '3', 'p')
        screen = app.screen_stack[-2]
        assert isinstance(app.screen, PolicyScreen)
        app.screen.query_one('#opencode-policy', Select).value = mode
        app.screen.query_one('#opencode-pin', Input).value = pin or ''
        app.screen.query_one('#policy-review', Button).press()
        await until(pilot, lambda: isinstance(app.screen, EnvironmentConsentScreen))
        await pilot.pause()
        assert 'no install' in app.screen.message
        assert v.policy(c.resolve(sources['id']))['mode'] == 'notify'
        runtime.calls.clear()
        app.screen.query_one('#environment-confirm', Button).press()
        await until(pilot, lambda: screen.operation_result and not app._operation_pending)
        assert v.policy(c.resolve(sources['id'])) == {'mode': mode, 'version': pin}
        assert not any(a[0] in ('start', 'exec', 'commit', 'stop') for a in runtime.calls)
    run(test, (80, 24))


def test_approved_mutation_survives_cancel_close_and_quit_is_not_cancellation(sources, runtime, monkeypatch):
    started, release = threading.Event(), threading.Event()
    update = v.update_environment
    def slow(*a, **k):
        started.set()
        assert release.wait(5)
        feedback = c._RUNTIME_FEEDBACK.get()
        assert feedback['cancelled'] is None
        return update(*a, **k)
    monkeypatch.setattr(v, 'update_environment', slow)
    async def test(app, pilot):
        await pilot.press('v', '3')
        screen = app.screen
        await review_update(app, pilot)
        app.screen.query_one('#environment-confirm', Button).press()
        assert await asyncio.to_thread(started.wait, 1)
        await pilot.pause()
        screen.action_cancel_checks()
        await pilot.press('escape', 'q')
        assert app.is_running and app._operation_pending and app._updates_mutation_active
        app.action_start_selected()
        assert not runtime.running
        release.set()
        await until(pilot, lambda: not app._operation_pending)
        assert not runtime.running and c.resolve(sources['id'])['opencode_update']['state'] == 'done'
    try: run(test, (80, 24))
    finally: release.set()


def test_cancel_or_close_during_read_only_planning_refuses_late_consent(sources, monkeypatch):
    started, release = threading.Event(), threading.Event()
    prepare = v.prepare_environment_update
    def slow(*a):
        started.set()
        assert release.wait(4)
        return prepare(*a)
    monkeypatch.setattr(v, 'prepare_environment_update', slow)
    async def test(app, pilot):
        await pilot.press('v', '3', 'u', 'enter')
        screen = app.screen
        assert await asyncio.to_thread(started.wait, 1)
        screen.action_cancel_checks()
        assert screen._preparing is None
        await pilot.press('escape')
        release.set()
        await pilot.pause(.2)
        assert len(app.screen_stack) == 1 and not app._operation_pending
        assert c.resolve(sources['id']).get('opencode_update') is None
    try: run(test, (80, 24))
    finally: release.set()


@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
def test_operation_forms_keep_advisory_ownership_without_toast_overlays(sources, size):
    async def test(app, pilot):
        app._disable_notifications = False
        app._replace_advisory('images', 'Older input', title='Review retained image', detail='Keep this notice [literal]')
        note = app._advisories['images'][1]
        await pilot.press('v', '3', 'p')
        assert isinstance(app.screen, PolicyScreen)
        assert app.screen.query_one('ToastRack').region.height == 0
        await pilot.press('escape')
        await review_update(app, pilot)
        assert app.screen.query_one('ToastRack').region.height == 0
        assert note in list(app._notifications) and app._advisories['images'][1] is note
        for button in app.screen.query(Button): assert button.region.bottom <= size[1]
        await pilot.press('escape', 'd')
        assert app.screen.query_one('ToastRack').region.height == 0
        assert 'Keep this notice [literal]' in app.screen.report
    run(test, size)


def test_changed_metadata_during_preparation_cannot_misdescribe_policy_consent(sources, monkeypatch):
    prepare = v.prepare_environment_policy
    def changed(m, *args):
        plan = prepare(m, *args)
        current = c.resolve(m['id'])
        current['profile'] = 'changed-while-planning'
        c.save(current)
        return plan
    monkeypatch.setattr(v, 'prepare_environment_policy', changed)
    async def test(app, pilot):
        await pilot.press('v', '3', 'p')
        screen = app.screen_stack[-2]
        app.screen.query_one('#policy-review', Button).press()
        await until(pilot, lambda: screen.operation_result is not None)
        assert 'changed while preparing' in screen.operation_result
        assert app.screen is screen and not app._operation_pending
    run(test, (80, 24))


@pytest.mark.parametrize('kind', ['repair-error', 'unsupported-journal'])
def test_recovery_center_errors_are_persistent_scrollable_and_do_not_clip_controls(sources, monkeypatch, kind):
    error = 'test recovery failure [literal] ' + 'long detail ' * 300
    c.mark(sources, 'error', operation='delete' if kind == 'unsupported-journal' else None, last_error='test error')
    def fail(m): raise c.SandboxError(error)
    monkeypatch.setattr(c, 'repair', fail)
    async def test(app, pilot):
        app._disable_notifications = False
        app.push_screen(RecoveryScreen(environment_id=sources['id']))
        await pilot.pause()
        screen = app.screen
        screen.query_one('#repair-recovery' if kind == 'repair-error' else '#runtime-recovery', Button).press()
        expected = error if kind == 'repair-error' else str(c.pending_operation(c.resolve(sources['id'])))
        await until(pilot, lambda: screen.query_one('#recovery-result', TextArea).text == expected)
        assert screen.query_one('#recovery-result', TextArea).read_only
        assert screen.query_one('ToastRack').region.height == 0
        for button in screen.query(Button):
            assert button.region.bottom <= 24 and button.parent.region.contains_region(button.region)
        assert c.resolve(sources['id']).get('operation') == ('delete' if kind == 'unsupported-journal' else None)
    run(test, (80, 24))


def test_rollback_reviews_and_preserves_present_system_layer(sources, runtime):
    result = v.update_environment(sources, '2.2.0')
    runtime.images.add('sha256:' + hashlib.sha256(result['checkpoint'].encode()).hexdigest())
    runtime.calls.clear()
    async def test(app, pilot):
        await pilot.press('v', '3')
        screen = app.screen
        await pilot.press('r')
        await until(pilot, lambda: isinstance(app.screen, EnvironmentConsentScreen))
        await pilot.pause()
        assert 'ENTIRE checkpointed system layer' in app.screen.message
        assert 'present system layer as a snapshot' in app.screen.message
        assert not any(a[0] == 'commit' for a in runtime.calls)
        app.screen.query_one('#environment-confirm', Button).press()
        await until(pilot, lambda: screen.operation_result and not app._operation_pending)
        assert any(a[0] == 'commit' and a[2].startswith('ocs-snapshot:') for a in runtime.calls)
        assert not runtime.exists and c.resolve(sources['id'])['operation'] is None
    run(test, (80, 24))


@pytest.mark.parametrize('entry', ['updates', 'recovery'])
def test_interrupted_update_recovery_uses_same_confirmed_handler(sources, runtime, entry):
    runtime.install = 'crash'
    with pytest.raises(Crash): v.update_environment(sources, '2.2.0')
    runtime.images.add('sha256:' + hashlib.sha256(c.resolve(sources['id'])['opencode_update']['checkpoint'].encode()).hexdigest())
    async def test(app, pilot):
        if entry == 'updates': await pilot.press('v', '3', 'e')
        else:
            app.push_screen(RecoveryScreen(environment_id=sources['id']))
            await pilot.pause()
            app.screen.query_one('#runtime-recovery', Button).press()
        await until(pilot, lambda: isinstance(app.screen, EnvironmentConsentScreen))
        await pilot.pause()
        assert 'never guess whether npm completed' in app.screen.message
        assert 'unfinished update-layer changes are discarded' in app.screen.message
        app.screen.query_one('#environment-confirm', Button).press()
        await until(pilot, lambda: c.resolve(sources['id']).get('operation') is None and not app._operation_pending)
        current = c.resolve(sources['id'])
        assert current['operation'] is None and not runtime.running and not runtime.exists
        assert current['opencode_update']['state'] == 'rolled-back'
    run(test, (80, 24))


def test_failed_recovery_keeps_journal_reason_and_routes_existing_config_recovery(sources, runtime, monkeypatch):
    runtime.install = 'crash'
    with pytest.raises(Crash): v.update_environment(sources, '2.2.0')
    checkpoint = c.resolve(sources['id'])['opencode_update']['checkpoint']
    runtime.images.add('sha256:' + hashlib.sha256(checkpoint.encode()).hexdigest())
    docker = c.docker
    def fail(*a, **k):
        if a[0] == 'rm': raise c.SandboxError('test recovery remove failed')
        return docker(*a, **k)
    monkeypatch.setattr(c, 'docker', fail)
    async def test(app, pilot):
        await pilot.press('v', '3')
        screen = app.screen
        await pilot.press('e')
        await until(pilot, lambda: isinstance(app.screen, EnvironmentConsentScreen))
        await pilot.pause()
        app.screen.query_one('#environment-confirm', Button).press()
        await until(pilot, lambda: screen.operation_result and not app._operation_pending)
        assert 'test recovery remove failed' in screen.operation_result
        await until(pilot, lambda: screen.items['environments'][sources['id']]['metadata'].get('operation') == 'runtime-recreate')
        await pilot.press('d')
        assert 'config recover' in app.screen.report and 'test recovery remove failed' in app.screen.report
        await pilot.press('escape', 'e')
        assert isinstance(app.screen, RecoveryScreen)
        assert app.screen.environment_id == sources['id']
    run(test, (80, 24))
