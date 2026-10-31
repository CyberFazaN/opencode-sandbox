"""Independent manager evidence, network-free opening and read-only 80x24 progressive disclosure."""
import asyncio
import json
import threading

import pytest
import test_manager_releases
from test_tui import run
from test_updates_tui import until
from textual.widgets import Button, TextArea
from typer.testing import CliRunner

from opencode_sandbox import __version__, cli, preferences, readiness, updates
from opencode_sandbox import core as c
from opencode_sandbox import manager_installation as mi
from opencode_sandbox import manager_releases as mr
from opencode_sandbox import opencode_versions as v

registry = test_manager_releases.registry
github = test_manager_releases.github


@pytest.fixture
def local(monkeypatch):
    monkeypatch.setattr(readiness, 'image_checks', list)
    monkeypatch.setattr(updates, 'base_inventory', lambda *a, **k: {'state': 'not built', 'eligible': False})
    monkeypatch.setattr(mi, 'classify', lambda: {'version': __version__, 'classification': 'manual review',
                                              'reason': 'Editable development installation [literal]', 'verified': False,
                                              'guidance': mi.GUIDANCE})


@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
def test_manager_open_is_network_free_then_check_and_details_never_expose_execution(local, github, size):
    async def test(app, pilot):
        await pilot.press('v')
        screen = app.screen
        await until(pilot, lambda: 'installation' in screen.items['manager']['manager'])
        assert not github['requests'] and not screen.query_one('#updates-check', Button).disabled
        assert 'never checked' in screen.discovery_text()
        screen.action_check()
        await until(pilot, lambda: not screen._active)
        assert 'GitHub: 6.2.0' in screen.discovery_text()
        assert 'Update available' in str(screen.query_one('#updates-selected').render())
        assert screen.query_one('#updates-update', Button).disabled
        for button in screen.query(Button): assert button.region.bottom <= size[1] and button.region.right <= size[0]
        assert screen.query_one('#updates-table').region.height >= 3
        await pilot.press('u')
        assert app.screen is screen and not app._operation_pending
        await pilot.press('d')
        report = app.screen.query_one('#report-text', TextArea)
        assert report.read_only and 'Release [notes]' in report.text and 'Editable' in report.text
        assert 'No replacement is authorized' in report.text
    run(test, size)
    assert len(github['requests']) == 1


@pytest.mark.parametrize('failure', ['github', 'local'])
def test_manager_sources_fail_independently_and_keep_version(local, github, monkeypatch, failure):
    if failure == 'github': github['status'] = 503
    else:
        def broken(): raise RuntimeError('local evidence failed [literal]')
        monkeypatch.setattr(mi, 'classify', broken)
    async def test(app, pilot):
        await pilot.press('v', 'c')
        screen = app.screen
        await until(pilot, lambda: not screen._active)
        assert screen.items['manager']['manager']['version'] == __version__
        if failure == 'github':
            assert 'HTTP 503' in screen.discovery_text()
            assert screen.items['manager']['manager']['installation']['classification'] == 'manual review'
        else:
            assert screen.manager_remote['release']['version'] == '6.2.0'
            assert 'RuntimeError: local evidence failed' in screen.items['manager']['manager']['error']
    run(test, (80, 24))


def test_manager_cancel_close_refuses_late_result_and_keeps_no_mutation(local, monkeypatch):
    started, release = threading.Event(), threading.Event()
    def slow():
        started.set()
        assert release.wait(5)
        return test_manager_releases.release() | {'tag': 'v6.2.0', 'version': '6.2.0'}
    monkeypatch.setattr(mr, 'latest', slow)
    async def test(app, pilot):
        await pilot.press('v', 'c')
        screen = app.screen
        assert await asyncio.to_thread(started.wait, 1)
        screen.action_cancel_checks()
        assert 'canceled' in screen.discovery_text()
        await pilot.press('escape')
        release.set()
        await pilot.pause(.2)
        assert screen.manager_remote['release'] is None and not app._operation_pending
        assert len(app.screen_stack) == 1
    try: run(test, (80, 24))
    finally: release.set()


def test_cli_is_independent_of_docker_npm_and_never_runs_pipx(local, github, monkeypatch):
    monkeypatch.setattr(c, 'docker', lambda *a, **k: pytest.fail('manager inspection must not use Docker'))
    result = CliRunner().invoke(cli.app, ['manager', 'status'])
    assert result.exit_code == 0 and not github['requests']
    assert json.loads(result.output)['installation']['version'] == __version__
    result = CliRunner().invoke(cli.app, ['manager', 'status', '--check'])
    assert result.exit_code == 0 and len(github['requests']) == 1
    assert json.loads(result.output)['release']['version'] == '6.2.0'
    github['status'] = 500
    result = CliRunner().invoke(cli.app, ['manager', 'status', '--check'])
    value = json.loads(result.output)
    assert result.exit_code == 2 and value['release']['version'] == '6.2.0'
    assert value['installation']['version'] == __version__ and 'HTTP 500' in value['check_error']


@pytest.mark.parametrize('failure', [False, True])
def test_optional_manager_source_is_daily_independent_quiet_and_restart_safe(local, github, monkeypatch, failure):
    monkeypatch.setattr(v, 'latest', lambda **kw: None)  # npm is verified separately, no external network
    preferences.write({**preferences.DEFAULTS, 'daily_discovery': True})
    if failure: github['status'] = 500
    async def test(app, pilot):
        await until(pilot, lambda: app._manager_discovery_status is not None)
        assert bool(app._manager_discovery_status['scheduling_error']) == failure
        assert str(app.query_one('#ocversions', Button).label) == ('Updates' if failure else 'Updates (1)')
        notes = list(app._notifications)
        app._set_busy('operation progress remains')
        for _ in range(3): app.refresh_discovery_preferences(); await pilot.pause()
        assert 'operation progress remains' in str(app.query_one('#status').render())
        assert notes == list(app._notifications) and len(github['requests']) == 1
        await pilot.press('v')
        assert ('Check failed' if failure else 'GitHub: 6.2.0') in app.screen.discovery_text()
    run(test, (80, 24))
    run(test, (80, 24))
    assert len(github['requests']) == 1


def test_optional_manager_and_explicit_check_share_real_request(local, github, monkeypatch):
    monkeypatch.setattr(v, 'latest', lambda **kw: None)
    preferences.write({**preferences.DEFAULTS, 'daily_discovery': True})
    github['delay'] = .8
    async def test(app, pilot):
        await until(pilot, lambda: github['requests'])
        await pilot.press('v', 'c')
        screen = app.screen
        await until(pilot, lambda: not screen._active and app._manager_discovery_status is not None)
        assert len(github['requests']) == 1
        assert screen.manager_remote['success'] == mr.discovery()['success']
    run(test, (80, 24))


def test_disabling_owned_manager_http_reaps_child_and_preserves_daily_claim(local, github, monkeypatch):
    monkeypatch.setattr(v, 'latest', lambda **kw: None)
    preferences.write({**preferences.DEFAULTS, 'daily_discovery': True})
    github['delay'] = 1
    children = []
    real_popen = c.subprocess.Popen
    def popen(argv, *a, **k):
        process = real_popen(argv, *a, **k)
        if any('http_probe.py' in str(arg) for arg in argv): children.append(process)
        return process
    monkeypatch.setattr(c.subprocess, 'Popen', popen)
    async def test(app, pilot):
        await until(pilot, lambda: github['requests'])
        preferences.write(preferences.DEFAULTS)
        app.refresh_discovery_preferences()
        await until(pilot, lambda: children and all(p.poll() is not None for p in children))
        assert mr.discovery()['attempt']['error'] == 'check did not complete'
        assert app._manager_discovery_status is None
        preferences.write({**preferences.DEFAULTS, 'daily_discovery': True})
        app.refresh_discovery_preferences()
        await until(pilot, lambda: app._manager_discovery_status is not None)
        assert len(github['requests']) == len(children) == 1
        assert 'check did not complete' in app._manager_discovery_status['scheduling_error']
    run(test)
