"""Public manager consent/eligibility/admission; pilots do not replace a real installation."""
import asyncio
import json
import runpy
from pathlib import Path

import pytest
from test_manager_review import installation as local_installation
from test_manager_review import origin as review_origin
from test_manager_review import prepared as prepared_review
from test_manager_review import tools as external_tools
from test_updates_tui import until
from textual.widgets import Button, Checkbox
from typer.testing import CliRunner

from opencode_sandbox import cli, readiness, tui, updates
from opencode_sandbox import manager_handoff as handoff
from opencode_sandbox import manager_installation as installation_module
from opencode_sandbox import manager_review as review
from opencode_sandbox.manager_review_tui import ManagerReviewScreen

installation = local_installation
origin = review_origin
prepared = prepared_review
tools = external_tools


@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
@pytest.mark.parametrize('approve', [False, True])
def test_public_exact_review_cancel_first_and_approved_staging_exit_never_arms_inside_textual(prepared, size, approve, monkeypatch):
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    monkeypatch.setattr(readiness, 'image_checks', list)
    monkeypatch.setattr(updates, 'base_inventory', lambda *args, **kwargs: {'state': 'not built', 'eligible': False})
    monkeypatch.setattr(review, 'prepare', lambda tag: prepared)
    monkeypatch.setattr(handoff, 'start_update', lambda *args, **kwargs: pytest.fail('Textual must not start or arm a helper'))
    staged = []
    actual = handoff.prepare_update
    def prepare(approval):
        result = actual(approval); staged.append(result)
        return result
    monkeypatch.setattr(handoff, 'prepare_update', prepare)
    async def test():
        app = tui.Dashboard()
        async with app.run_test(size=size) as pilot:
            await pilot.press('v')
            screen = app.screen
            await until(pilot, lambda: 'installation' in screen.items['manager']['manager'])
            screen.manager_remote['release'] = {'version': '6.2.0', 'tag': 'v6.2.0'}
            screen._render_selected()
            assert not screen.query_one('#updates-update', Button).disabled
            await pilot.press('u')
            await until(pilot, lambda: isinstance(app.screen, ManagerReviewScreen))
            consent = app.screen
            assert consent.update and app.focused.id == 'manager-review-cancel'
            assert consent.query_one('#manager-review-confirm', Button).disabled
            for control in consent.query(Button): assert control.region.bottom <= size[1] and control.region.right <= size[0]
            assert 'No mutation Cancel' in consent.message and 'reboot' in consent.message
            if approve:
                consent.query_one('#manager-review-network', Checkbox).value = True
                await pilot.pause()
                consent.query_one('#manager-review-confirm', Button).press()
                await until(pilot, lambda: app._manager_fixture is not None)
                artifact = app._manager_fixture.artifact
                assert artifact.update and not artifact.used and artifact.process is None
                assert len(staged) == 1 and staged[0]['artifact'] is artifact
                assert app._handoff_activity._sealed and not app.check_action('quit', ())
            else:
                await pilot.press('enter')
                assert app.screen is screen and not staged and not app._operation_pending
                assert app._manager_fixture is None
    asyncio.run(test())


@pytest.mark.parametrize('release', [None, {'tag': 'v6.1.0', 'version': '6.1.0'}, {'tag': 'v6.0.0', 'version': '6.0.0'},
                                    {'tag': 'main', 'version': 'main'}, {'tag': 'v6.2.0', 'version': '6.3.0'}])
def test_ui_availability_cannot_select_unknown_same_older_or_inconsistent_target(release):
    assert installation_module.update_reason({'verified': True, 'version': '6.1.0'}, release)


def test_cli_update_refuses_nonterminal_before_any_review_network_or_staging(monkeypatch):
    monkeypatch.setattr(review, 'prepare', lambda *args: pytest.fail('nonterminal update must not inspect or contact source'))
    result = CliRunner().invoke(cli.app, ['manager', 'update', '--tag', 'v6.2.0'])
    assert result.exit_code != 0
    assert 'confirm' not in result.output.lower()


def test_changed_approved_staging_fails_without_sealing_or_handoff(prepared, monkeypatch):
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    def unavailable(*args): raise RuntimeError('changed origin review')
    monkeypatch.setattr(handoff, 'prepare_update', unavailable)
    async def test():
        app = tui.Dashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.run_manager_update(review.Approval(prepared))
            await until(pilot, lambda: app._manager_update_intent is None)
            assert app.is_running and not app._operation_pending and not app._handoff_activity._sealed
            assert app._manager_fixture is None
    asyncio.run(test())


def test_public_review_does_not_serialize_provider_credentials_or_an_executable_environment(prepared):
    value = review.text(prepared, update=True)
    assert 'host as this user' in value and 'public defaults' in value
    assert prepared.target.commit in value and prepared.identity in value
    assert 'independently verified' in value and 'No mutation Cancel' in value
    assert json.loads(prepared.binding)['network'] == 'public-defaults'


def test_reaped_terminal_origin_is_never_signaled_while_detached_helper_finishes(monkeypatch):
    term_class = runpy.run_path(str(Path(__file__).parent / 'integration/pty_term.py'))['Term']
    terminal = term_class.__new__(term_class)
    terminal.pid, terminal.fd, terminal.alive, terminal._reaped = 12345, None, True, False
    terminal.pump = lambda seconds: None
    monkeypatch.setattr('os.waitpid', lambda pid, flags: (pid, 0))
    monkeypatch.setattr('os.kill', lambda *args: pytest.fail('reaped terminal PID may have been reused'))
    assert terminal.exit_code() == 0 and terminal._reaped
    terminal.close(); terminal.close()
    assert terminal.fd is None and not terminal.alive
