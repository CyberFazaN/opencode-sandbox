"""Readiness feedback/cancellation and actual worker-body admission, not a UI retry loop."""
import threading
from contextlib import contextmanager, nullcontext
from functools import wraps

from textual import work as textual_work
from textual.worker import get_current_worker

from . import core as c
from . import runtime_identity as rid


class Activity:
    """Count actual bodies, not canceled Textual tasks; sealing never cancels live work.

    The internal handoff refuses live/queued workers. A canceled queued thread may still enter
    later; this same mutex prevents it starting application work after the handoff is sealed.
    This is an app-local admission barrier, never installation quiescence or a usage-lease release.
    """
    def __init__(self):
        self._mutex = threading.Lock()
        self._running = 0
        self._sealed = False

    @contextmanager
    def enter(self):
        with self._mutex:
            admitted = not self._sealed
            if admitted: self._running += 1
        try: yield admitted
        finally:
            if admitted:
                with self._mutex: self._running -= 1

    def seal(self, workers):
        with self._mutex:
            if self._sealed: raise c.SandboxError('Manager handoff is already pending')
            if self._running or any(not worker.is_finished for worker in workers):
                raise c.SandboxError('Dashboard work is still running; wait before manager handoff')
            self._sealed = True


def admission(app):
    activity = getattr(app, '_handoff_activity', None)
    return activity.enter() if activity is not None else nullcontext(True)


def publish(app, callback, *args, **kwargs):
    """Read-only worker results cannot outlive cancellation, replacement or app shutdown."""
    worker = get_current_worker()
    def show():
        if app.is_running and not worker.is_cancelled:
            callback(*args, **kwargs)
    if app.is_running and not worker.is_cancelled:
        try: app.call_from_thread(show)
        except RuntimeError:
            if app.is_running and not worker.is_cancelled: raise


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

            with admission(app) as admitted:
                if not admitted: return None
                with c.runtime_feedback(progress=progress, cancelled=lambda: worker.is_cancelled):
                    try:
                        return fn(self, *a, **k)
                    except rid.Cancelled:
                        return None
        return textual_work(*args, **kwargs)(run)
    return decorate
