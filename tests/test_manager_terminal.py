"""Internal handoff requests are not manager update/installation consent."""
import asyncio
import json
import os
import pty
import select
import signal
import subprocess
import sys
import termios
import threading
import time
from pathlib import Path

import pytest
from test_manager_helper import artifact as staged_artifact
from test_manager_helper import origin, result_at, subreaper, wait_helper
from test_manager_tools import tools as external_tools
from test_updates_tui import until
from textual.screen import Screen

from opencode_sandbox import cli, tui
from opencode_sandbox import core as c
from opencode_sandbox import manager_handoff as h
from opencode_sandbox.tui_runtime import Activity, work

tools = external_tools
artifact = staged_artifact


def test_attached_session_refuses_handoff_before_artifact_inspection(monkeypatch):
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    async def test():
        app = tui.Dashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app._session_active = True
            with pytest.raises(c.SandboxError, match='session'):
                app._request_manager_fixture(None)
            assert app.is_running and app.return_value is None
    asyncio.run(test())


@pytest.mark.parametrize('flag', ['_operation_pending', '_updates_mutation_active'])
def test_operations_refuse_handoff_before_inspection(monkeypatch, flag):
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    async def test():
        app = tui.Dashboard()
        async with app.run_test() as pilot:
            await pilot.pause()
            setattr(app, flag, True)
            with pytest.raises(c.SandboxError, match='operation'): app._request_manager_fixture(None)
            assert app.is_running and app._manager_fixture is None
    asyncio.run(test())


def test_open_screen_or_consent_refuses_handoff(monkeypatch):
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    async def test():
        app = tui.Dashboard()
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.push_screen(Screen())
            with pytest.raises(c.SandboxError, match='screen or consent'): app._request_manager_fixture(None)
    asyncio.run(test())


@pytest.mark.parametrize('cancel', [False, True])
def test_live_thread_body_refuses_handoff_even_after_textual_cancellation(artifact, monkeypatch, cancel):
    origin(monkeypatch, artifact)
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    entered, release = threading.Event(), threading.Event()
    class App(tui.Dashboard):
        @work(thread=True)
        def owned(self):
            entered.set()
            assert release.wait(8)
    async def test():
        app = App()
        async with app.run_test() as pilot:
            await pilot.pause()
            worker = app.owned()
            await until(pilot, entered.is_set)
            if cancel:
                worker.cancel()
                await until(pilot, lambda: worker.is_finished)
            try:
                with pytest.raises(c.SandboxError, match='work is still running'): app._request_manager_fixture(artifact)
                assert app.is_running and not artifact.used
            finally: release.set()
    asyncio.run(test())
    artifact.discard()


def test_sealed_activity_prevents_late_cancelled_queued_body_entry():
    activity = Activity()
    activity.seal([])
    with activity.enter() as admitted: assert not admitted
    with pytest.raises(c.SandboxError, match='already pending'): activity.seal([])


def test_activity_exception_retains_admission_and_never_cancels_the_live_body():
    activity = Activity()
    with pytest.raises(ValueError), activity.enter() as admitted:
        assert admitted
        with pytest.raises(c.SandboxError, match='work is still running'): activity.seal([])
        raise ValueError('owned failure')
    activity.seal([])


def test_queued_worker_also_refuses_sealing():
    from types import SimpleNamespace
    activity = Activity()
    with pytest.raises(c.SandboxError, match='work is still running'):
        activity.seal([SimpleNamespace(is_finished=False)])
    activity.seal([SimpleNamespace(is_finished=True)])


def test_configuration_recovery_retains_app_ownership_and_actual_body_tracking(monkeypatch):
    from opencode_sandbox.management_tui import RecoveryScreen
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    def recover(*args):
        entered.set()
        assert release.wait(8)
    monkeypatch.setattr(RecoveryScreen, '_recover_runtime', recover)
    async def test():
        app = tui.Dashboard()
        async with app.run_test() as pilot:
            screen = RecoveryScreen()
            await app.push_screen(screen)
            screen._begin_runtime_recovery('0' * 16, None)
            await until(pilot, entered.is_set)
            worker, = [worker for worker in app.workers if worker.group == 'environment-operation']
            app.pop_screen()
            await pilot.pause()
            try:
                assert not worker.is_cancelled
                with pytest.raises(c.SandboxError, match='work is still running'): app._handoff_activity.seal([])
            finally: release.set()
    asyncio.run(test())


def test_successful_internal_request_exits_but_never_starts_or_arms_fixture(artifact, monkeypatch):
    origin(monkeypatch, artifact)
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    async def test():
        app = tui.Dashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app._request_manager_fixture(artifact)
            assert app.return_value is app._manager_fixture
            assert not app.check_action('quit', ())
            assert not artifact.used and artifact.process is None
        assert app.return_value == h.TerminalRequest(artifact, False)
    asyncio.run(test())
    artifact.discard()


@pytest.mark.parametrize('bad', ['missing', 'verify', 'used', 'prefix'])
def test_invalid_or_stale_requests_do_not_seal_or_exit_the_dashboard(artifact, monkeypatch, bad):
    origin(monkeypatch, artifact)
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    async def test():
        app = tui.Dashboard()
        async with app.run_test() as pilot:
            await pilot.pause()
            if bad == 'used': artifact.used = True
            if bad == 'prefix': monkeypatch.setattr(sys, 'prefix', str(Path(artifact.prefix).parent / 'foreign'))
            with pytest.raises(c.SandboxError):
                app._request_manager_fixture(None if bad == 'missing' else artifact, verify=1 if bad == 'verify' else False)
            assert app.is_running and app._manager_fixture is None and not app._handoff_activity._sealed
            assert artifact.process is None
    asyncio.run(test())
    artifact.discard()


def test_off_ui_thread_cannot_request_handoff_or_consume_the_artifact(artifact, monkeypatch):
    origin(monkeypatch, artifact)
    monkeypatch.setattr(tui.Dashboard, '_prerequisites_worker', lambda self: None)
    async def test():
        app = tui.Dashboard()
        async with app.run_test() as pilot:
            await pilot.pause()
            def attempt():
                with pytest.raises(c.SandboxError, match='UI thread'): app._request_manager_fixture(artifact)
            await asyncio.to_thread(attempt)
            assert app.is_running and not artifact.used and app._manager_fixture is None
    asyncio.run(test())
    artifact.discard()


@pytest.mark.parametrize('failure', ['exception', 'nonzero', 'foreign-result'])
def test_cli_never_hands_off_an_abnormal_dashboard_return(monkeypatch, failure):
    class App:
        is_running = False
        return_code = 1 if failure == 'nonzero' else 0
        _manager_fixture = h.TerminalRequest(None)
        def run(self):
            if failure == 'exception': raise RuntimeError('owned app failure')
            return h.TerminalRequest(None) if failure == 'foreign-result' else self._manager_fixture
    monkeypatch.setattr(tui, 'Dashboard', App)
    monkeypatch.setattr(h, 'complete_terminal_fixture', lambda *a: pytest.fail('abnormal handoff'))
    with pytest.raises((RuntimeError, c.SandboxError)): cli._dashboard()


@pytest.mark.parametrize('failure', ['first-check', 'second-check', 'arm', 'none'])
def test_terminal_completion_failure_cancels_exact_started_fixture_and_never_claims_a_transfer(artifact, monkeypatch, failure):
    from types import SimpleNamespace
    calls = []
    terminal = object.__new__(h.Terminal)
    def check(self):
        calls.append('check')
        if failure == 'first-check' or failure == 'second-check' and calls.count('check') == 2:
            raise c.SandboxError('owned terminal fault')
    def arm():
        calls.append('arm')
        if failure == 'arm': raise c.SandboxError('owned arming fault')
    def start(*args, **kwargs):
        calls.append('start')
        return SimpleNamespace(arm=arm, close=lambda: calls.append('cancel/reap'),
                               control=SimpleNamespace(close=lambda: calls.append('transfer')))
    monkeypatch.setattr(h.Terminal, 'check', check)
    monkeypatch.setattr(h, 'start_fixture', start)
    if failure == 'none': h.complete_terminal_fixture(h.TerminalRequest(artifact), terminal)
    else:
        with pytest.raises(c.SandboxError): h.complete_terminal_fixture(h.TerminalRequest(artifact), terminal)
    assert ('transfer' in calls) is (failure == 'none')
    assert ('start' in calls) is (failure != 'first-check')
    assert ('cancel/reap' in calls) is (failure in ('second-check', 'arm'))
    artifact.discard()


@pytest.mark.parametrize('shell', [False, True])
@pytest.mark.parametrize('failure', [False, True])
def test_session_lifetime_is_explicit_and_cleared_on_success_and_failure(monkeypatch, shell, failure):
    from contextlib import nullcontext
    app = tui.Dashboard()
    app._operation_pending = True
    monkeypatch.setattr(app, 'suspend', nullcontext)
    monkeypatch.setattr(app, '_finished', lambda *args: None)
    def interactive(*args, **kwargs):
        assert app._session_active and not app._operation_pending and kwargs['shell'] is shell
        if failure: raise ValueError('owned attached failure')
    monkeypatch.setattr(c, 'interactive', interactive)
    app._attach_ready({}, shell)
    assert not app._session_active


@pytest.mark.parametrize('fault', ['modes', 'foreground', 'closed', 'stream', 'reused', 'thread'])
def test_terminal_snapshot_refuses_changed_state_without_repair(monkeypatch, fault):
    master, slave = pty.openpty()
    streams = [os.fdopen(os.dup(slave), mode) for mode in ('r', 'w', 'w')]
    for name, stream in zip(('__stdin__', '__stdout__', '__stderr__'), streams, strict=True): monkeypatch.setattr(sys, name, stream)
    # This primitive test uses a real tty/modes but supplies foreground identity; the full pty
    # subprocess tests independently prove real foreground/session ownership with no patch.
    monkeypatch.setattr(h.os, 'tcgetpgrp', lambda fd: os.getpgrp())
    try:
        terminal = h.Terminal()
        if fault == 'modes':
            attrs = termios.tcgetattr(slave); attrs[3] ^= termios.ECHO
            termios.tcsetattr(slave, termios.TCSANOW, attrs)
        if fault == 'foreground': monkeypatch.setattr(h.os, 'tcgetpgrp', lambda fd: os.getpgrp() + 1)
        if fault == 'closed': streams[0].close()
        if fault == 'stream': monkeypatch.setattr(sys, '__stdout__', streams[2])
        if fault == 'reused': terminal.used = True
        if fault == 'thread': terminal.thread = -1
        before = termios.tcgetattr(slave)
        with pytest.raises((c.SandboxError, OSError, ValueError)): terminal.check()
        assert termios.tcgetattr(slave) == before
    finally:
        for stream in streams: stream.close()
        os.close(slave); os.close(master)


def read_state(path, predicate=lambda value: True, timeout=10, pump=None):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if path.exists():
            value = json.loads(path.read_text())
            if predicate(value): return value
            assert not value.get('worker_error'), value['worker_error']
        if pump: pump(.05)
        else: time.sleep(.01)
    pytest.fail('Owned terminal fixture did not reach rendezvous')


@pytest.mark.parametrize('size,explicit', [((80, 24), False), ((120, 40), True)])
def test_real_terminal_restoration_precedes_arming_and_actual_death_precedes_exclusion(tools, tmp_path, monkeypatch, size, explicit):
    # Shared opt-in pty helper renders the real terminal; no Docker/pipx provenance claim here.
    pytest.importorskip('pyte')  # optional host-terminal renderer; real campaign requires it
    monkeypatch.syspath_prepend(str(Path(__file__).parent / 'integration'))
    from pty_term import Term
    evidence, *_ = tools
    staging = tmp_path / 'staging'; staging.mkdir()
    state = tmp_path / 'state.json'
    env = dict(os.environ, OPENCODE_SANDBOX_HOME=str(tmp_path / 'data'), OPENCODE_SANDBOX_CONFIG=str(tmp_path / 'config'))
    with subreaper():
        term = Term([sys.executable, '-B', str(Path(__file__).with_name('manager_terminal_fixture.py')), json.dumps(evidence),
                     str(staging), str(state), json.dumps({'host': True, 'drain': True, 'explicit': explicit})], *size, env=env)
        helper = None
        try:
            assert term.wait_for('OpenCode Sandbox', 10)
            raw_modes = termios.tcgetattr(term.fd)
            assert not raw_modes[3] & termios.ICANON
            term.send('\x1b[20~', .2)  # F9, fixture-only key
            data = read_state(state, lambda value: value.get('returned') or value.get('failed'))
            assert data.get('returned'), (data, term.raw[-4000:])
            helper = data['helper']; assert helper is not None
            assert termios.tcgetattr(term.fd)[3] & termios.ICANON
            assert termios.tcgetattr(term.fd)[3] & termios.ECHO
            term.pump(.1)
            marker = term.raw.index(b'Non-mutating manager handoff fixture:')
            assert term.raw.rfind(b'\x1b[?1049l', 0, marker) >= 0
            assert term.raw.rfind(b'\x1b[?25h', 0, marker) >= 0
            assert term.raw.rfind(b'\x1b[?1000l', 0, marker) >= 0
            assert b'\x1b[?1049h' not in term.raw[marker:]
            assert not (Path(data['directory']) / 'result.json').exists()
            pidfd = os.pidfd_open(data['origin'])
            try: assert not select.select([pidfd], [], [], .2)[0]
            finally: os.close(pidfd)
            code = f'from opencode_sandbox.installation_locks import exclusive\nwith exclusive({evidence["evidence"]["venv"]!r}): pass'
            checked = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, timeout=5, check=False)
            assert checked.returncode != 0 and b'installation busy' in checked.stderr.lower()
            state.with_suffix('.release').touch()
            assert term.exit_code(10) == 0
            assert wait_helper(helper) == 0; helper = None
            assert result_at(data['directory'])['outcome'] == 'quiescent'
            assert subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, timeout=5, check=False).returncode == 0
        finally:
            state.with_suffix('.release').touch()
            try:
                if os.waitpid(term.pid, os.WNOHANG)[0] == 0:
                    os.kill(term.pid, signal.SIGKILL); os.waitpid(term.pid, 0)
            except ChildProcessError: pass
            os.close(term.fd)
            if state.exists(): helper = helper or json.loads(state.read_text()).get('helper')
            if helper is not None:
                try:
                    if os.waitpid(helper, os.WNOHANG)[0] == 0:
                        os.kill(helper, signal.SIGKILL); os.waitpid(helper, 0)
                except ChildProcessError: pass


@pytest.mark.parametrize('mode', ['worker', 'cancelled-worker', 'modes', 'quit'])
def test_real_terminal_refusal_or_ordinary_quit_never_arms_a_helper(tools, tmp_path, monkeypatch, mode):
    pytest.importorskip('pyte')  # do not make the renderer a new product/test-extra dependency
    monkeypatch.syspath_prepend(str(Path(__file__).parent / 'integration'))
    from pty_term import Term
    evidence, *_ = tools
    staging = tmp_path / 'staging'; staging.mkdir()
    state = tmp_path / 'state.json'
    options = {'host': True, 'worker': mode in ('worker', 'cancelled-worker'), 'cancel': mode == 'cancelled-worker',
               'fault': mode if mode == 'modes' else None}
    env = dict(os.environ, OPENCODE_SANDBOX_HOME=str(tmp_path / 'data'), OPENCODE_SANDBOX_CONFIG=str(tmp_path / 'config'))
    with subreaper():
        term = Term([sys.executable, '-B', str(Path(__file__).with_name('manager_terminal_fixture.py')), json.dumps(evidence),
                     str(staging), str(state), json.dumps(options)], env=env)
        try:
            assert term.wait_for('OpenCode Sandbox', 10)
            if options['worker']: read_state(state, lambda value: value.get('worker_started'))
            term.send('q' if mode == 'quit' else '\x1b[20~', .2)
            if options['worker']:
                value = read_state(state, lambda value: value.get('refused'))
                assert 'operation' in value['refused'] or 'work is still running' in value['refused']
                assert not value.get('helper') and not value.get('requested')
                assert not (Path(value['directory']) / 'result.json').exists()
                state.with_suffix('.release').touch()
                read_state(state, lambda value: value.get('worker_done'))
                term.send('q', .2)  # normal quit after completion must not reuse the refused request
            elif mode == 'modes':
                value = read_state(state, lambda value: value.get('failed'))
                assert value['helper'] is None
                assert not (Path(value['directory']) / 'result.json').exists()
            status = term.exit_code(10)
            assert status == (2 if mode == 'modes' else 0), (status, term.raw[-4000:])
            value = json.loads(state.read_text())
            assert not value.get('helper') and not (Path(value['directory']) / 'result.json').exists()
            if mode != 'modes': assert term.restored()
        finally:
            state.with_suffix('.release').touch()
            try:
                if os.waitpid(term.pid, os.WNOHANG)[0] == 0:
                    os.kill(term.pid, signal.SIGKILL); os.waitpid(term.pid, 0)
            except ChildProcessError: pass
            os.close(term.fd)
