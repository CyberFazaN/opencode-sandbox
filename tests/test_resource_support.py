"""D-053: do not confuse accepted Docker limit settings with enforcement support."""
import json
from types import SimpleNamespace

import pytest
from test_tui import run, settle
from typer.testing import CliRunner

from opencode_sandbox import core as c
from opencode_sandbox import readiness as r

GOOD = {"CgroupVersion": "2", "CgroupDriver": "systemd", "MemoryLimit": True,
        "CpuCfsQuota": True, "CpuCfsPeriod": True, "PidsLimit": True}
DOCKER_INFO = getattr(c, "docker_info", None)


def evidence(monkeypatch, info):
    monkeypatch.setattr(c, "docker_info", lambda: info)


def test_reported_support_is_not_a_claim_of_measured_enforcement(monkeypatch):
    evidence(monkeypatch, GOOD)
    check = r.resource_support_check()
    assert check.id == "resource-support" and check.status == r.PASSED
    assert "Docker reports" in check.detail and "enforcement not measured" in check.detail


@pytest.mark.parametrize("field,word", [("MemoryLimit", "memory"), ("CpuCfsQuota", "CPU"),
                                      ("CpuCfsPeriod", "CPU"), ("PidsLimit", "pids")])
def test_missing_controller_support_warns_with_upstream_guidance(monkeypatch, field, word):
    evidence(monkeypatch, {**GOOD, field: False})
    check = r.resource_support_check()
    assert check.status == r.WARNING and word in check.detail
    assert "https://docs.docker.com/engine/security/rootless/tips/#limiting-resources" in check.hint
    assert not any(word in check.hint for word in ("sudo", "systemctl", "pacman", "apt install"))


@pytest.mark.parametrize("field", ["MemoryLimit", "CpuCfsQuota", "CpuCfsPeriod", "PidsLimit"])
@pytest.mark.parametrize("value", [None, "true", 1])
def test_missing_or_wrong_typed_capability_is_unknown_not_supported(monkeypatch, field, value):
    evidence(monkeypatch, {**GOOD, field: value})
    check = r.resource_support_check()
    assert check.status == r.NOT_CHECKED and "not established" in check.detail


@pytest.mark.parametrize("fields,status", [({"CgroupVersion": "1"}, r.WARNING),
                                          ({"CgroupDriver": "none"}, r.WARNING),
                                          ({"CgroupDriver": "cgroupfs"}, r.NOT_CHECKED),
                                          ({"CgroupVersion": "future"}, r.NOT_CHECKED)])
def test_unsupported_and_unestablished_configs_are_distinct(monkeypatch, fields, status):
    evidence(monkeypatch, {**GOOD, **fields})
    assert r.resource_support_check().status == status


@pytest.mark.parametrize("info", [None, [], "garbage", {}, {"CgroupVersion": "2"}])
def test_missing_information_cannot_pass(monkeypatch, info):
    evidence(monkeypatch, info)
    check = r.resource_support_check()
    assert check.status == r.NOT_CHECKED


def test_probe_failure_does_not_leak_raw_output_or_claim_missing_controllers(monkeypatch):
    def unavailable():
        raise c.SandboxError("Docker info query failed")

    monkeypatch.setattr(c, "docker_info", unavailable)
    check = r.resource_support_check()
    assert check.status == r.NOT_CHECKED and "query failed" in check.detail


def test_capability_probe_uses_verified_endpoint_and_is_bounded(monkeypatch):
    from opencode_sandbox import runtime_identity as rid

    calls = []

    def query(argv, **kwargs):
        calls.append((argv, kwargs))
        assert kwargs["budget"].timeout == 5
        return json.dumps(GOOD), None

    monkeypatch.setattr(rid, "_docker", query)
    assert DOCKER_INFO() == GOOD
    assert calls[0][0][:3] == ["-H", c.docker_endpoint(), "info"]


def test_matching_container_settings_are_labeled_configuration_not_enforcement(monkeypatch):
    m = c.create("ocs-test-support", "scratch")
    monkeypatch.setattr(c, "observed_runtime", lambda m: c.runtime_settings(m))
    check = r.runtime_check(m, {"Running": True})
    assert check.status == r.PASSED
    assert "configuration matches" in check.detail and "enforcement not measured" in check.detail


@pytest.mark.parametrize("out,error", [("not-json", None), ("[]", None), ("null", None),
                                     ("", "proxy https://user:secret@example.invalid failed")])
def test_info_failures_do_not_expose_raw_responses(monkeypatch, out, error):
    from opencode_sandbox import runtime_identity as rid

    monkeypatch.setattr(rid, "_docker", lambda *a, **k: (out, error))
    with pytest.raises(c.SandboxError) as caught:
        DOCKER_INFO()
    assert "secret" not in str(caught.value)
    if out: assert out not in str(caught.value)


def test_info_deadline_and_cancellation_use_existing_probe_cleanup(monkeypatch):
    from opencode_sandbox import runtime_identity as rid

    def expired(*a, **k):
        raise rid.Deadline("expired")

    monkeypatch.setattr(rid, "_docker", expired)
    with pytest.raises(c.SandboxError, match="5-second diagnostic budget"):
        DOCKER_INFO()
    monkeypatch.setattr(c, "_ENDPOINT", "unix:///ocs-test.sock")
    monkeypatch.setattr(rid, "_docker", lambda *a, **k: k["budget"].remaining())
    with c.runtime_feedback(cancelled=lambda: True), pytest.raises(rid.Cancelled):
        DOCKER_INFO()


def test_no_info_query_before_daemon_verification(monkeypatch):
    from opencode_sandbox import runtime_identity as rid

    monkeypatch.setattr(rid, "verify", lambda *a, **k: rid.Identity(rid.MISMATCH, "rootless"))
    monkeypatch.setattr(rid, "_docker", lambda *a, **k: pytest.fail("unverified query"))
    with pytest.raises(c.PrerequisiteError):
        DOCKER_INFO()


def test_unknown_and_known_missing_capabilities_are_both_disclosed(monkeypatch):
    evidence(monkeypatch, {**GOOD, "MemoryLimit": False, "PidsLimit": None})
    check = r.resource_support_check()
    assert check.status == r.WARNING and "memory" in check.detail and "not established for pids" in check.detail


def test_unrelated_controller_warnings_do_not_make_required_support_fail(monkeypatch):
    evidence(monkeypatch, {**GOOD, "CPUSet": False, "SwapLimit": False, "Warnings": ["No cpuset support", "No io.weight support"]})
    assert r.resource_support_check().status == r.PASSED


def test_doctor_preserves_exit_semantics_and_uses_shared_report(monkeypatch):
    from opencode_sandbox import cli

    evidence(monkeypatch, {**GOOD, "PidsLimit": False})
    check = r.resource_support_check()
    monkeypatch.setattr(r, "host_checks", list)
    monkeypatch.setattr(r, "image_checks", list)
    monkeypatch.setattr(r, "storage_check", lambda: r.Check("storage", "Storage", r.NOT_CHECKED, "test"))
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=1))
    result = CliRunner().invoke(cli.app, ["doctor"])
    assert result.exit_code == 0 and "Daemon identity: verified" in result.output
    assert all(line in result.output for line in r.format_report({"checks": [vars(check)]}))


def test_dashboard_advisory_is_nonblocking_and_refresh_clears_its_notice(monkeypatch):
    evidence(monkeypatch, {**GOOD, "MemoryLimit": False})
    monkeypatch.setattr(r, "image_checks", list)
    shared = "\n".join(r.format_report({"checks": [vars(r.resource_support_check())]}))

    async def scenario(app, pilot):
        await settle(pilot)
        notes = [n for n in app._notifications if n.title == "Resource-limit support"]
        assert notes and notes[0].message == shared
        await pilot.press("/")
        assert app.focused.id == "search"
        app._operation_pending = True
        app.query_one("#status").update("Operation in progress")
        app._show_resource_support(r.resource_support_check())
        assert str(app.query_one("#status").render()) == "Operation in progress"
        app._operation_pending = False
        evidence(monkeypatch, GOOD)
        app.action_refresh_readiness()
        await settle(pilot)
        assert not [n for n in app._notifications if n.title == "Resource-limit support"]
    run(scenario, size=(80, 24))


def test_check_skips_support_when_docker_is_unverified(monkeypatch):
    from opencode_sandbox import runtime_identity as rid

    m = c.create("ocs-test-unavailable", "scratch")
    monkeypatch.setattr(rid, "verify", lambda *a, **k: rid.Identity(rid.UNAVAILABLE, "rootless"))
    monkeypatch.setattr(c, "docker_info", lambda: pytest.fail("cannot inspect unverified daemon"))
    report = {item.id: item for item in r.environment_checks(m)}
    assert report["resource-support"].status == r.NOT_CHECKED
