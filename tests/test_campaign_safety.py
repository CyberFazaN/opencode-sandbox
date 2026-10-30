"""The real campaign must not race auto-restarts or certify failed inventory probes."""
import importlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parent / "integration"))
    return importlib.import_module("campaign"), importlib.import_module("test_70_privileged")


def test_crash_recovery_waits_for_automatic_restart_before_any_start(harness, monkeypatch):
    _, privileged = harness
    calls = []
    monkeypatch.setattr(privileged, "daemon_up", lambda camp: calls.append("wait for API") or True)
    assert privileged.daemon_after_crash(object(), lambda *args: pytest.fail("must not race an activating service"))
    assert calls == ["wait for API"]


def test_crash_recovery_can_start_only_after_the_automatic_wait_fails(harness, monkeypatch):
    _, privileged = harness
    ready = iter((False, True))
    calls = []

    def wait(camp):
        calls.append("wait for API")
        return next(ready)

    def control(*args):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(privileged, "daemon_up", wait)
    assert privileged.daemon_after_crash(object(), control)
    assert calls == ["wait for API", ("start",), "wait for API"]


def test_crash_recovery_reports_a_failed_start_without_changing_policy(harness, monkeypatch):
    _, privileged = harness
    calls = []
    monkeypatch.setattr(privileged, "daemon_up", lambda camp: False)

    def control(*args):
        calls.append(args)
        return SimpleNamespace(returncode=1)

    assert not privileged.daemon_after_crash(object(), control)
    assert calls == [("start",)]  # no reset-failed, rate-limit/daemon policy edits or repeated mutation


def test_campaign_does_not_report_empty_objects_when_docker_inventory_fails(harness, tmp_path):
    campaign, _ = harness
    camp = campaign.Campaign.__new__(campaign.Campaign)
    camp.data, camp.config = tmp_path / "data", tmp_path / "config"
    camp.manifest_path = tmp_path / "manifest.txt"
    camp.manifest_path.write_text("run-id ocs-test-inventory\n")
    camp.ids, camp.short_dirs, camp.run = {}, [], "ocs-test-inventory"
    notes = []
    camp.log, camp.note = lambda text: None, notes.append
    camp.ocs = lambda *a, **k: SimpleNamespace(returncode=0, stdout="")
    camp.python = lambda *a, **k: SimpleNamespace(returncode=0, stdout="test-data-id")

    def docker(*args, check=True):
        if check:
            raise AssertionError("Docker inventory unavailable")
        return SimpleNamespace(returncode=1, stdout="", stderr="daemon unavailable")

    camp.docker = docker
    with pytest.raises(AssertionError, match="Docker inventory unavailable"):
        camp.finish()
    assert not any("left with this data directory's label" in note for note in notes)


def test_cleanup_guard_refuses_inventory_errors_even_when_no_objects_were_listed(harness, monkeypatch, tmp_path):
    campaign, _ = harness
    monkeypatch.setenv("OPENCODE_SANDBOX_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OPENCODE_SANDBOX_CONFIG", str(tmp_path / "config"))
    code = campaign.GUARD % (str(tmp_path / "data"), str(tmp_path / "config"), [])
    stub = ("from types import SimpleNamespace\nfrom opencode_sandbox import cleanup\n"
            "cleanup.inventory=lambda: SimpleNamespace(errors=['daemon unavailable'], eligible=lambda *a: [])\n")
    result = subprocess.run([sys.executable, "-c", stub + code], capture_output=True, text=True, check=False, timeout=10)
    assert result.returncode != 0 and "inventory unavailable; refusing cleanup" in result.stdout
