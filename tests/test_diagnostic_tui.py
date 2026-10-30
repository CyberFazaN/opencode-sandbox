"""Canceled read-only workers reap owned clients and cannot publish late reports (80x24)."""
import asyncio
import os
import sys
import threading
import time

import pytest
from test_tui import run, settle

from opencode_sandbox import core as c
from opencode_sandbox import diagnostics, readiness, tui
from opencode_sandbox import opencode_versions as v


@pytest.mark.real_session
def test_pilot_cancellation_reaps_a_real_sleeping_diagnostic_client(tmp_path, monkeypatch):
    m = c.create("ocs-test-up05-pilot", "scratch")
    marker = tmp_path / "client-pid"
    binary = tmp_path / "docker"
    binary.write_text(f"#!{sys.executable}\nimport os,time\nfrom pathlib import Path\nPath({str(marker)!r}).write_text(str(os.getpid()))\ntime.sleep(30)\n")
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
        worker = app._opencode_versions_worker()
        deadline = time.monotonic() + 2
        while not marker.exists() and time.monotonic() < deadline:
            await pilot.pause(.02)
        assert marker.exists()
        # The UI remains responsive while the child is blocked.
        await pilot.press("tab")
        worker.cancel()
        assert await asyncio.to_thread(finished.wait, 1)
        await settle(pilot)
        pid = int(marker.read_text())
        assert not os.path.exists(f"/proc/{pid}")
        assert not isinstance(app.screen, tui.ReportScreen)
        assert c.resolve(m["id"]).get("operation") is None
    run(test, (80, 24))


def test_cancelled_uncooperative_report_cannot_publish_after_replacement(monkeypatch):
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    monkeypatch.setattr(readiness, "image_checks", list)
    def report(**kwargs):
        started.set()
        try:
            assert release.wait(3)
            return ["obsolete result"], []
        finally: finished.set()
    monkeypatch.setattr(v, "versions_report", report)
    async def test(app, pilot):
        await settle(pilot)
        worker = app._opencode_versions_worker()
        assert await asyncio.to_thread(started.wait, 1)
        worker.cancel()
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
        await settle(pilot)
        assert not isinstance(app.screen, tui.ReportScreen)
    try:
        run(test, (80, 24))
    finally:
        release.set()
