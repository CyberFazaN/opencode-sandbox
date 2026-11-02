"""Compact keyboard, selection-copy and update consent regressions."""
import json
import shlex
from types import SimpleNamespace

import pytest
import test_environment_updates_tui
import test_updates_tui
from test_tui import run, settle
from test_updates_tui import until
from textual.widgets import Button, Checkbox, Input, TextArea

from opencode_sandbox import clipboard, preferences, tui
from opencode_sandbox import core as c
from opencode_sandbox import environment_checks as checks
from opencode_sandbox import manager_installation as mi
from opencode_sandbox.environment_updates_tui import (
    EnvironmentConsentScreen,
    TargetScreen,
)
from opencode_sandbox.manager_review_tui import ManualUpdateScreen

sources = test_updates_tui.sources
runtime = test_environment_updates_tui.runtime
environment_sources = test_environment_updates_tui.sources


@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
def test_keys_toggle_escape_and_close_restore_focus(size):
    async def test(app, pilot):
        table = app.focused
        for close in ('question_mark', 'escape', 'button'):
            await pilot.press('question_mark')
            assert isinstance(app.screen, tui.KeysScreen)
            assert 'Start' in app.screen.query_one('#keys-text', TextArea).text
            button = app.screen.query_one('#keys-close', Button)
            assert button.region.bottom <= size[1] and button.region.right <= size[0]
            if close == 'button': button.press(); await pilot.pause()
            else: await pilot.press(close)
            assert len(app.screen_stack) == 1 and app.focused is table
        await pilot.press('slash', 'question_mark')
        assert len(app.screen_stack) == 1 and app.query_one('#search', Input).value == '?'
    run(test, size)


def test_preference_is_opt_in_backward_compatible_and_saved():
    c.init_dirs()
    (c.CONFIG / 'ui.json').write_text(json.dumps({'confirm_stop': False}))
    assert not preferences.read()['copy_selected_text']
    async def test(app, pilot):
        await pilot.press('g')
        box = app.screen.query_one('#copy-selected-text', Checkbox)
        assert not box.value
        box.value = True
        app.screen.query_one('#save-settings', Button).press()
        await pilot.pause()
        assert preferences.read()['copy_selected_text'] and app._copy_selected
        assert not preferences.read()['confirm_stop']
    run(test, (80, 24))


def test_advisories_do_not_obscure_confirmation_controls():
    async def test(app, pilot):
        app._disable_notifications = False
        app._replace_advisory('images', 'Old base definition', title='Base images need attention', detail='Retained image needs review')
        note = app._advisories['images'][1]
        await app.push_screen(tui.ConfirmScreen('Recover interrupted container recreation for ocs-test-environment?'))
        await pilot.pause()
        assert app.screen.query_one('ToastRack').region.height == 0
        assert note in list(app._notifications) and app._advisories['images'][1] is note
        for button in app.screen.query(Button): assert button.region.bottom <= 24
        await pilot.press('escape')
        assert len(app.screen_stack) == 1
    run(test, (80, 24))


@pytest.mark.parametrize('native', [True, None])
def test_copy_feedback_distinguishes_native_acceptance_and_osc52(monkeypatch, native):
    calls = []
    monkeypatch.setattr(clipboard, 'native_copy', lambda text: calls.append(text) or native)
    async def test(app, pilot):
        monkeypatch.setattr(type(app._driver), 'is_headless', property(lambda self: False))
        writes = []
        monkeypatch.setattr(app._driver, 'write', writes.append)
        app.copy_text('selected \u03b1 text')
        await until(pilot, lambda: any(n.title == 'Clipboard' for n in app._notifications))
        message = next(n.message for n in app._notifications if n.title == 'Clipboard')
        assert calls == ['selected \u03b1 text'] and app.clipboard == 'selected \u03b1 text'
        osc = [s for s in writes if '\x1b]52;' in s]
        if native:
            assert message == 'Copied to clipboard' and not osc
        else:
            assert 'acceptance unverified' in message and len(osc) == 1
    run(test)


def test_selection_copy_deduplicates_ignores_inputs_and_disabled_preference(monkeypatch):
    async def test(app, pilot):
        copies = []
        monkeypatch.setattr(app, 'copy_text', copies.append)
        await app.push_screen(tui.ReportScreen('select this text', title='Report'))
        await pilot.pause()
        area = app.screen.query_one('#report-text', TextArea)
        area.focus()
        await pilot.press('f7')
        await settle(pilot, .3)
        assert copies == []
        app._copy_selected = True
        await pilot.press('left', 'f7')
        await settle(pilot, .3)
        assert copies == ['select this text']
        await pilot.press('left', 'f7')
        await settle(pilot, .3)
        assert copies == ['select this text']
        await pilot.press('escape', 'g')
        # An editable field's selection must not replace the user's clipboard.
        await pilot.press('escape', 'slash')
        app.query_one('#search', Input).value = 'private input'
        await pilot.press('ctrl+a')
        await settle(pilot, .3)
        assert copies == ['select this text']
    run(test)


def test_mouse_selection_copies_on_release_not_while_dragging(monkeypatch):
    async def test(app, pilot):
        await settle(pilot)
        copies = []
        monkeypatch.setattr(app, 'copy_text', copies.append)
        app._copy_selected = True
        app.query_one('#status').update('selection example')
        await pilot.pause()
        await pilot.mouse_down('#status', offset=(1, 0))
        await pilot.hover('#status', offset=(10, 0))
        assert not copies
        selected = app.screen.get_selected_text()
        assert selected.strip() == 'selection'  # Textual 4 includes a widget-separator newline.
        await pilot.mouse_up('#status', offset=(10, 0))
        await settle(pilot, .3)
        assert copies == [selected]
        await pilot.click('#status', offset=(12, 0))
        assert copies == [selected]  # preserve Textual's selection, and never write on empty clicks
    run(test, (80, 24))


def test_manual_command_is_exact_and_only_for_fresh_verified_ownership(monkeypatch):
    release = {'tag': 'v99.1.0', 'version': '99.1.0'}
    local = {'verified': True, 'reason': 'verified', 'evidence': {
        'pipx_home': '/test/custom pipx', 'pipx_bin_dir': '/test/bin', 'source_python': '/test/python',
        'locations': {'man_dir': '/test/man', 'completion_dir': '/test/complete', 'shared_libs': '/test/shared'}}}
    monkeypatch.setattr(mi, 'classify', lambda: local)
    message, command = mi.manual_update(release, 'Independent updater unavailable')
    args = shlex.split(command)
    assert 'PIPX_HOME=/test/custom pipx' in args and args[-1] == 'git+' + mi.URL + '@v99.1.0'
    assert args[-3:-1] == ['--python', '/test/python'] and '--force' in args
    async def test(app, pilot):
        copied = []
        monkeypatch.setattr(app, 'copy_text', copied.append)
        await app.push_screen(ManualUpdateScreen(message, command))
        await pilot.pause()
        assert app.focused.id == 'manual-update-cancel'
        app.screen.query_one('#manual-update-confirm', Button).press()
        await pilot.pause()
        assert copied == [command] and len(app.screen_stack) == 1 and not app._operation_pending
    run(test, (80, 24))
    local['verified'] = False
    assert mi.manual_update(release, 'unsupported')[1] is None


@pytest.mark.parametrize('stopped', [False, True])
def test_check_all_consent_fixed_targets_and_no_overlapping_requests(sources, monkeypatch, stopped):
    m, calls = sources
    snapshot = {m['id']: ('identity', not stopped, 'metadata')}
    monkeypatch.setattr(checks, 'review', lambda keys: (snapshot, [m['name']] if stopped else []))
    async def test(app, pilot):
        await pilot.press('v', '3', 'C')
        screen = app.screen_stack[-2] if isinstance(app.screen, EnvironmentConsentScreen) else app.screen
        if stopped:
            await until(pilot, lambda: isinstance(app.screen, EnvironmentConsentScreen))
            assert 'temporarily started' in app.screen.message and 'stay running' in app.screen.message
            assert not any(call[-1] is True for call in calls)
            await pilot.press('escape')
            await pilot.press('C')
            await until(pilot, lambda: isinstance(app.screen, EnvironmentConsentScreen))
            app.screen.query_one('#environment-confirm', Button).press()
            await pilot.pause()
        await until(pilot, lambda: not screen._active and not screen._preparing)
        assert calls.count(('npm',)) == 1
        assert calls.count(('environment', m['id'], True)) == 1
        assert not screen.query('#updates-start') and not screen.query('#updates-cancel')
    run(test, (80, 24))


def test_running_update_caution_cancel_then_confirm_finishes_stopped(environment_sources, runtime):
    runtime.running = True
    async def test(app, pilot):
        await pilot.press('v', '3', 'u')
        screen = app.screen_stack[-2]
        assert isinstance(app.screen, TargetScreen)
        app.screen.query_one('#update-target', Input).value = '2.2.0'
        await pilot.press('enter')
        await until(pilot, lambda: isinstance(app.screen, EnvironmentConsentScreen))
        assert app.screen.caution and 'will NOT restart' in app.screen.message
        assert runtime.running and not any(a[0] == 'stop' for a in runtime.calls)
        await pilot.press('escape', 'u')
        app.screen.query_one('#update-target', Input).value = '2.2.0'
        await pilot.press('enter')
        await until(pilot, lambda: isinstance(app.screen, EnvironmentConsentScreen))
        app.screen.query_one('#environment-confirm', Button).press()
        await until(pilot, lambda: screen.operation_result and not app._operation_pending)
        assert not runtime.running and 'update complete; stopped' in screen.operation_result
        ops = [a[0] for a in runtime.calls]
        assert ops.index('stop') < ops.index('commit') < ops.index('start')
    run(test, (80, 24))


def test_native_clipboard_is_not_used_for_remote_shells(monkeypatch):
    monkeypatch.setenv('SSH_CONNECTION', 'test')
    monkeypatch.setenv('WAYLAND_DISPLAY', 'test')
    monkeypatch.setattr(clipboard.shutil, 'which', lambda name: pytest.fail('remote desktop must not be targeted'))
    assert clipboard.native_copy('text') is None


def test_native_clipboard_failure_never_claims_success(monkeypatch):
    monkeypatch.delenv('SSH_CONNECTION', raising=False)
    monkeypatch.delenv('SSH_TTY', raising=False)
    monkeypatch.setenv('WAYLAND_DISPLAY', 'test')
    monkeypatch.setattr(clipboard.shutil, 'which', lambda name: '/test/' + name)
    monkeypatch.setattr(clipboard.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=1))
    assert clipboard.native_copy('text') is None
