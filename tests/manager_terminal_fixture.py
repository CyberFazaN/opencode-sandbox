"""Test-only real-pty injector for the internal non-mutating handoff; never shipped.

No App.run/driver/terminal/lease/helper response is replaced. Host-only mode disables Docker
diagnostics; the opt-in installed-pipx mode keeps real diagnostics/operations/session clients.
The sole added key is F9 for this fixture. There is no product key/command/environment trigger.
"""
import json
import os
import sys
import termios
import threading
import time
from pathlib import Path
from typing import ClassVar

from opencode_sandbox import installation_locks as locks

evidence, staging, state, options = sys.argv[1:]
evidence, options = json.loads(evidence), json.loads(options)
state = Path(state)
if options.get('host'):
    sys.prefix = evidence['evidence']['venv']  # fresh owned synthetic prefix; no pipx claim
locks.acquire_usage()

from opencode_sandbox import core as c
from opencode_sandbox import manager_handoff as handoff
from opencode_sandbox import tui
from opencode_sandbox.tui_runtime import work

prepared = handoff.prepare(evidence, Path(staging))
assert prepared['supported'], prepared
artifact = prepared['artifact']
data = {'origin': os.getpid(), 'directory': str(artifact.directory)}
release = state.with_suffix('.release')


def report(**values):
    data.update(values)
    partial = state.with_suffix('.partial')
    partial.write_text(json.dumps(data))
    partial.replace(state)


def wait_release():
    deadline = time.monotonic() + 20
    while not release.exists():
        if time.monotonic() >= deadline: raise RuntimeError('Owned test rendezvous expired')
        time.sleep(.01)


if options.get('host'):
    tui.Dashboard._prerequisites_worker = lambda self: None


class FixtureDashboard(tui.Dashboard):
    BINDINGS: ClassVar = [*tui.Dashboard.BINDINGS, ('f9', 'fixture_request', 'Test-only handoff')]

    def run(self, *args, **kwargs):
        result = super().run(*args, **kwargs)
        if options.get('fault') == 'modes':
            attrs = termios.tcgetattr(0)
            attrs[3] ^= termios.ECHO
            termios.tcsetattr(0, termios.TCSANOW, attrs)  # owned real-tty fault AFTER actual teardown
        return result

    def on_mount(self):
        # Textual dispatches inherited on_mount handlers itself; do not mount the base twice.
        self.set_interval(.1, self.fixture_idle)
        if options.get('worker'):
            self._operation_pending = True
            self.fixture_worker = self.owned_work()
        if options.get('session'):
            self.call_after_refresh(self._attach_ready, c.resolve(options['session']), True)

    def fixture_idle(self):
        if not data.get('idle') and not self._operation_pending and not self._session_active \
                and not any(not worker.is_finished for worker in self.workers):
            with self._handoff_activity._mutex:
                if not self._handoff_activity._running: report(idle=True)

    @work(thread=True, group='owned-handoff-test')
    def owned_work(self):
        report(worker_started=True)
        try:
            wait_release()
            if options.get('environment'):
                with c.runtime_feedback(progress=None, cancelled=None): c.start(c.resolve(options['environment']))
            self.call_from_thread(self._work_done)
        except Exception as exc:
            report(worker_error=c.error_text(exc))
            raise

    def _work_done(self):
        self._operation_pending = False
        report(worker_done=True)

    def action_fixture_request(self):
        if options.get('cancel') and not data.get('cancelled'):
            self.fixture_worker.cancel()
            self._operation_pending = False  # prove flags/Worker.is_finished alone are insufficient
            report(cancelled=True)
        try:
            self._request_manager_fixture(artifact, verify=options.get('verify', False))
            report(requested=True)
        except c.SandboxError as exc:
            report(refused=str(exc))
            self.notify('Handoff refused: ' + str(exc), severity='warning')


tui.Dashboard = FixtureDashboard
if options.get('session'):
    attached = c.docker_attached
    def observed_attach(*args, on_start=None):
        def started(pid):
            try: application._request_manager_fixture(artifact)
            except c.SandboxError as exc: report(session_refused=str(exc), client=pid)
            else: raise AssertionError('Actual attached session allowed handoff')
            if on_start is not None: on_start(pid)
        return attached(*args, on_start=started)
    c.docker_attached = observed_attach
    # Preserve the real Dashboard implementation; capture only this exact test app reference.
    original_init = FixtureDashboard.__init__
    def init(self, *args, **kwargs):
        global application
        original_init(self, *args, **kwargs)
        application = self
    FixtureDashboard.__init__ = init

if options.get('drain'):
    threading.Thread(target=wait_release, name='owned-handoff-drain').start()

report(prepared=True)
sys.argv = ['opencode-sandbox', *(['tui'] if options.get('explicit') else [])]
from opencode_sandbox.launcher import main

try:
    try: main()
    except SystemExit as exc:
        if exc.code not in (None, 0): raise
    report(returned=True, helper=artifact.process.pid if artifact.process else None)
except BaseException:
    report(failed=True, helper=artifact.process.pid if artifact.process else None)
    raise
