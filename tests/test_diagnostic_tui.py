"""Canceled read-only workers reap owned clients and cannot publish late reports (80x24)."""
import asyncio
import os
import sys
import threading
import time

import pytest
from test_tui import run, settle

from opencode_sandbox import core as c
from opencode_sandbox import diagnostics, environment_checks, readiness
from opencode_sandbox import opencode_versions as v


@pytest.mark.real_session
def test_pilot_cancellation_reaps_a_real_sleeping_diagnostic_client(tmp_path, monkeypatch):
    m = c.create("ocs-test-up05-pilot", "scratch")
    marker = tmp_path / "client-pid"
    binary = tmp_path / "docker"
    binary.write_text(f"#!{sys.executable}\nimport os,sys,time\nfrom pathlib import Path\n"
                      f"if 'exec' in sys.argv:\n Path({str(marker)!r}).write_text(str(os.getpid()))\n time.sleep(30)\n"
                      f"else: print({'a' * 64 + '|sha256:' + 'b' * 64 + '|' + m['id']!r})\n")
    binary.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setattr(c, "inspect_container", lambda _: {"Running": True})
    monkeypatch.setattr(readiness, "image_checks", list)
    monkeypatch.setattr(v, "latest", lambda: "2.2.0")
    finished = threading.Event()
    real = diagnostics.run
    def diagnostic(*a, **k):
        try: return real(*a, **k)
        finally: finished.set()
    monkeypatch.setattr(diagnostics, "run", diagnostic)
    async def test(app, pilot):
        await settle(pilot)
        await pilot.press("v", "3", "c")
        screen = app.screen
        deadline = time.monotonic() + 2
        while not marker.exists() and time.monotonic() < deadline:
            await pilot.pause(.02)
        assert marker.exists()
        # The UI remains responsive while the child is blocked.
        await pilot.press("tab")
        await pilot.press('escape')
        assert await asyncio.to_thread(finished.wait, 1)
        await settle(pilot)
        pid = int(marker.read_text())
        assert not os.path.exists(f"/proc/{pid}")
        assert len(app.screen_stack) == 1
        assert screen.items["environments"][m["id"]]["version"] is None
        assert c.resolve(m["id"]).get("operation") is None
    run(test, (80, 24))


def test_cancelled_uncooperative_report_cannot_publish_after_replacement(monkeypatch):
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    m = c.create("ocs-test-uncooperative", "scratch")
    monkeypatch.setattr(readiness, "image_checks", list)
    def report(m, *, check=True):
        if not check: return {"state": "stopped", "version": None}
        started.set()
        try:
            assert release.wait(3)
            return {"state": "stopped", "version": "2.99.0"}
        finally: finished.set()
    monkeypatch.setattr(v, "environment_version", report)
    monkeypatch.setattr(environment_checks, 'check', lambda m, **kw: report(m, check=True))
    monkeypatch.setattr(v, "latest", lambda: "2.2.0")
    async def test(app, pilot):
        await settle(pilot)
        await pilot.press("v", "3", "c")
        previous = app.screen
        assert await asyncio.to_thread(started.wait, 1)
        await pilot.press("escape", "v", "3")
        replacement = app.screen
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
        await settle(pilot)
        assert previous is not replacement
        assert replacement.items["environments"][m["id"]]["version"] is None
        assert previous.items["environments"][m["id"]]["version"] is None
    try:
        run(test, (80, 24))
    finally:
        release.set()
