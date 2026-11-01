"""Internal exact manager review at both terminal sizes; no public action or execution."""
import asyncio

import pytest
from test_manager_review import installation as local_installation
from test_manager_review import origin as review_origin
from test_manager_review import prepared as prepared_review
from test_manager_review import tools as local_tools
from textual.widgets import Button, Checkbox, TextArea

from opencode_sandbox import core as c
from opencode_sandbox import manager_handoff as handoff
from opencode_sandbox import manager_review as review
from opencode_sandbox import manager_review_tui, tui

origin = review_origin
prepared = prepared_review
installation = local_installation
tools = local_tools


@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
@pytest.mark.parametrize('action', ['escape', 'cancel', 'confirm'])
def test_exact_review_cancel_default_explicit_policy_and_no_helper_or_install(prepared, monkeypatch, size, action):
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    monkeypatch.setattr(handoff, 'prepare', lambda *a, **k: pytest.fail('review staged a helper'))
    results = []
    async def test():
        app = tui.Dashboard()
        async with app.run_test(size=size) as pilot:
            screen = manager_review_tui.ManagerReviewScreen(prepared)
            await app.push_screen(screen, results.append)
            await pilot.pause()
            cancel = screen.query_one('#manager-review-cancel', Button)
            confirm = screen.query_one('#manager-review-confirm', Button)
            policy = screen.query_one('#manager-review-network', Checkbox)
            text = screen.query_one('#manager-review-text', TextArea)
            assert app.focused is cancel and confirm.disabled and not policy.value
            for widget in (cancel, confirm, policy):
                assert widget.region.y >= 0 and widget.region.bottom <= size[1]
                assert widget.region.x >= 0 and widget.region.right <= size[0]
            assert text.read_only and prepared.target.commit in text.text and prepared.prefix in text.text
            assert prepared.identity in text.text and 'Manager Update remains disabled' in text.text
            assert text.virtual_size.height > text.size.height
            if action == 'escape': await pilot.press('escape')
            elif action == 'cancel': cancel.press()
            else:
                confirm.press(); await pilot.pause()
                assert app.screen is screen and not results
                policy.value = True; await pilot.pause()
                assert not confirm.disabled
                confirm.press()
            await pilot.pause()
            assert results and (type(results[0]) is review.Approval if action == 'confirm' else results[0] is None)
            if action == 'confirm': assert results[0].review is prepared
            assert app._manager_fixture is None and app.is_running
    asyncio.run(test())


def test_open_manager_consent_blocks_internal_terminal_handoff_before_artifact_inspection(prepared, monkeypatch):
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    async def test():
        app = tui.Dashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            await app.push_screen(manager_review_tui.ManagerReviewScreen(prepared))
            await pilot.pause()
            with pytest.raises(c.SandboxError, match='screen or consent'): app._request_manager_fixture(None)
            assert app.is_running and app._manager_fixture is None
    asyncio.run(test())


def test_plain_dict_or_boolean_is_not_a_prepared_review():
    for value in (True, {}, None):
        with pytest.raises(c.SandboxError): manager_review_tui.ManagerReviewScreen(value)


@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
def test_keyboard_only_policy_selection_then_confirm_returns_exact_receipt(prepared, monkeypatch, size):
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    results = []
    async def test():
        app = tui.Dashboard()
        async with app.run_test(size=size) as pilot:
            screen = manager_review_tui.ManagerReviewScreen(prepared)
            await app.push_screen(screen, results.append)
            await pilot.pause()
            assert app.focused.id == 'manager-review-cancel'
            await pilot.press('shift+tab', 'space')
            await pilot.pause()
            assert not screen.query_one('#manager-review-confirm', Button).disabled
            await pilot.press('tab', 'tab')
            assert app.focused.id == 'manager-review-confirm'
            await pilot.press('enter')
            await pilot.pause()
            assert len(results) == 1 and results[0].review is prepared
            assert app._manager_fixture is None and app.is_running
    asyncio.run(test())
