"""Test-only installed-console review injector; never shipped or a product action/flag.

The owned .pth installs only this dashboard subclass. Actual CLI bootstrap/invocation, source,
classification, tool diagnostics, file/routes, UI and revalidation remain real. No helper/executor.
"""
import json
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
    class Dashboard(tui.Dashboard):
        BINDINGS: ClassVar = tui.Dashboard.BINDINGS

        def on_mount(self):
            # Textual dispatches inherited mount handlers itself; actual diagnostics still run.
            self.requested = False
            self.set_interval(.1, self.when_idle)

        def when_idle(self):
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
            self.check_review(receipt.review)

        @work(thread=True, group='owned-manager-review')
        def check_review(self, prepared):
            try:
                assert manager_review.revalidate(prepared) is prepared
                report(revalidated=True)
            except c.SandboxError as exc: report(refused=str(exc))
            self.call_from_thread(self.exit)
    tui.Dashboard = Dashboard
