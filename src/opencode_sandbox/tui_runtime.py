"""Readiness feedback/cancellation for existing Textual thread workers, not a UI retry loop."""
from functools import wraps

from textual import work as textual_work
from textual.worker import get_current_worker

from . import core as c
from . import runtime_identity as rid


def work(*args, **kwargs):
    def decorate(fn):
        @wraps(fn)
        def run(self, *a, **k):
            worker = get_current_worker()
            app = self.app

            def progress(message):
                if (message is None or not worker.is_cancelled) and app.is_running:
                    # Shutdown can race the is_running observation; never post a late callback.
                    try:
                        app.call_from_thread(app._runtime_notice, message, worker)
                    except RuntimeError:
                        if app.is_running: raise

            with c.runtime_feedback(progress=progress, cancelled=lambda: worker.is_cancelled):
                try:
                    return fn(self, *a, **k)
                except rid.Cancelled:
                    return None
        return textual_work(*args, **kwargs)(run)
    return decorate
