"""Test-only installed-console review injector; never shipped or a product action/flag.

The owned .pth installs only this dashboard subclass. Actual CLI bootstrap/invocation, source,
classification, tool diagnostics, file/routes, UI and revalidation remain real. No helper/executor.
"""
import json
import threading
import time
from pathlib import Path

from opencode_sandbox import core as c
from opencode_sandbox import (
    manager_releases,
    manager_review,
    manager_review_tui,
    manager_targets,
    tui,
)
from opencode_sandbox.tui_runtime import work


def install(options):
    import sys
    from typing import ClassVar
    assert Path(manager_review.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    manager_targets.ENDPOINT = options['endpoint']
    manager_releases.API = options['endpoint'] + '/releases?per_page=100'
    state = Path(options['state'])
    values = {}
    def report(**changes):
        values.update(changes)
        partial = state.with_suffix('.partial')
        partial.write_text(json.dumps(values))
        partial.replace(state)
    if options.get('local_validate'):
        from opencode_sandbox import manager_handoff
        complete = manager_handoff.complete_terminal_fixture
        def completed(request, terminal):
            complete(request, terminal)  # observe ONLY after the real checks/start/arm completed
            report(helper=request.artifact.process.pid, armed=True)
        manager_handoff.complete_terminal_fixture = completed
    class Dashboard(tui.Dashboard):
        BINDINGS: ClassVar = tui.Dashboard.BINDINGS

        def on_mount(self):
            # Textual dispatches inherited mount handlers itself; actual diagnostics still run.
            self.requested = False
            self.set_interval(.1, self.when_idle)

        def when_idle(self):
            if hasattr(self, 'pending_artifact') and not any(not worker.is_finished for worker in self.workers):
                with self._handoff_activity._mutex:
                    idle = not self._handoff_activity._running
                if idle:
                    artifact = self.pending_artifact
                    del self.pending_artifact
                    self._request_manager_fixture(artifact)
                return
            if not self.requested and not any(not worker.is_finished for worker in self.workers):
                self.requested = True
                self.prepare_review()

        @work(thread=True, group='owned-manager-review')
        def prepare_review(self):
            try:
                prepared = manager_review.prepare('v6.2.0')
                report(prepared=True, identity=prepared.identity, prefix=prepared.prefix,
                       tag=prepared.target.tag, commit=prepared.target.commit)
                self.call_from_thread(self.show_review, prepared)
            except c.SandboxError as exc:
                report(refused=str(exc))
                self.call_from_thread(self.exit)

        def show_review(self, prepared):
            self.push_screen(manager_review_tui.ManagerReviewScreen(prepared), self.reviewed)

        def reviewed(self, receipt):
            if receipt is None:
                report(cancelled=True)
                self.exit()
                return
            assert type(receipt) is manager_review.Approval
            report(approved=receipt.review.identity)
            self.check_review(receipt)

        @work(thread=True, group='owned-manager-review')
        def check_review(self, receipt):
            prepared = receipt.review
            try:
                assert manager_review.revalidate(prepared) is prepared
                report(revalidated=True)
                if options.get('local_validate'):
                    from opencode_sandbox import manager_handoff
                    staged = manager_handoff.prepare_review_fixture(receipt, Path(options['staging']))
                    assert staged['supported'], staged
                    artifact = staged['artifact']
                    report(staged=True, directory=str(artifact.directory), local_identity=artifact.review_identity)
                    self.call_from_thread(self.queue_handoff, artifact)
                    return
            except c.SandboxError as exc: report(refused=str(exc))
            self.call_from_thread(self.exit)

        def queue_handoff(self, artifact):
            def drain():
                deadline = time.monotonic() + 20
                while not state.with_suffix('.release').exists():
                    if time.monotonic() >= deadline: raise RuntimeError('Owned local replay drain expired')
                    time.sleep(.01)
            threading.Thread(target=drain, name='owned-local-review-drain').start()
            self.pending_artifact = artifact
    tui.Dashboard = Dashboard
