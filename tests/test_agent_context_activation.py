"""Targeted system mutation, saved settings, startup drift repair and secret-profile policy."""
import inspect
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import agent_context as ac
from opencode_sandbox import config_plan as cp
from opencode_sandbox import core as c
from opencode_sandbox import readiness as r
from opencode_sandbox.cli import app


@pytest.mark.parametrize("include", [True, False])
def test_targeted_mutation_preserves_every_other_value_and_order(include):
    original = {"username": "keep", "other": {"nested": [1, 2]},
                "instructions": ["one", ac.CONTAINER_PATH, "two", ac.CONTAINER_PATH, "three"]}
    result = ac.system_document(original, include)
    assert result["username"] == "keep" and result["other"] == original["other"]
    assert result["instructions"] == (["one", ac.CONTAINER_PATH, "two", "three"] if include else ["one", "two", "three"])
    assert ac.system_document(result, include) == result
    assert original["instructions"].count(ac.CONTAINER_PATH) == 2


@pytest.mark.parametrize("document", [[], None, {"instructions": "bad"}, {"instructions": None}])
def test_malformed_structures_are_not_replaced(document):
    with pytest.raises(ValueError): ac.system_document(document, True)


def script(path, include):
    source = "CONTAINER_PATH=" + repr(ac.CONTAINER_PATH) + "\n" + inspect.getsource(ac.system_document) + "\n" + ac.SYSTEM_SCRIPT
    source = source.replace("/etc/opencode", str(path.parent))
    return subprocess.run([sys.executable, "-c", source, str(int(include))], capture_output=True, text=True, check=False)


def test_real_atomic_file_mutation_and_malformed_json_preserved(tmp_path):
    path = tmp_path / "system" / "opencode.json"
    path.parent.mkdir()
    path.write_text('{"instructions":["unrelated"],"username":"keep"}')
    path.chmod(0o640)
    assert script(path, True).returncode == 0
    assert json.loads(path.read_text()) == {"instructions": ["unrelated", ac.CONTAINER_PATH], "username": "keep"}
    assert path.stat().st_mode & 0o777 == 0o640
    assert script(path, False).returncode == 0
    assert json.loads(path.read_text()) == {"instructions": ["unrelated"], "username": "keep"}
    path.write_text("{broken dummy-secret")
    failure = script(path, True)
    assert failure.returncode != 0 and path.read_text() == "{broken dummy-secret"
    assert "dummy-secret" not in failure.stdout + failure.stderr
    path.unlink()
    os.mkfifo(path)
    assert script(path, True).returncode != 0  # no blocking read of special files


@pytest.mark.parametrize("include", [True, False])
def test_every_managed_start_repairs_drift_and_refreshes_file(tmp_path, monkeypatch, include):
    m = c.create("ocs-qa-context", agent_context_enabled=include)
    path = tmp_path / "system" / "opencode.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"instructions": ["unrelated", *([ac.CONTAINER_PATH] if not include else [])], "username": "keep"}))
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": True})
    monkeypatch.setattr(c, "guidance_inputs", lambda m, **k: {"image": "fixture", "runtime": c.runtime_settings(m)})
    calls = []
    def docker(*args, **kwargs):
        if args[0] != "exec": return SimpleNamespace(returncode=0)
        calls.append(args)
        return script(path, args[-1] == "1")
    monkeypatch.setattr(c, "docker", docker)
    c.start(m)
    assert ac.path(m, c.env_dir).is_file()
    assert json.loads(path.read_text())["instructions"].count(ac.CONTAINER_PATH) == int(include)
    assert json.loads(path.read_text())["username"] == "keep"
    c.start(m)
    assert len(calls) == 2 and json.loads(path.read_text())["instructions"].count(ac.CONTAINER_PATH) == int(include)


def test_failed_reconciliation_prevents_success_and_preserves_setting(monkeypatch):
    m = c.create("ocs-qa-context")
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": True})
    monkeypatch.setattr(c, "guidance_inputs", lambda m, **k: {"image": "fixture", "runtime": c.runtime_settings(m)})
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=int(a[0] == "exec")))
    with pytest.raises(c.SandboxError, match="reconcile"): c.start(m)
    assert c.resolve(m["id"])["status"] == "error" and ac.enabled(c.resolve(m["id"]))


def test_saved_toggle_cli_and_failed_live_toggle_is_recoverable(monkeypatch):
    m = c.create("ocs-qa-context")
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "guidance_inputs", lambda m, **k: {"image": "fixture", "runtime": c.runtime_settings(m)})
    result = CliRunner().invoke(app, ["config", "apply", m["name"], "--no-agent-context"])
    assert result.exit_code == 0 and not ac.enabled(c.resolve(m["id"]))
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": True})
    monkeypatch.setattr(c, "guidance_inputs", lambda m, **k: {"image": "fixture", "runtime": c.runtime_settings(m)})
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=1))
    plan = cp.plan(m, {"agent_context_enabled": True})
    assert any("system instruction" in step for step in plan.steps)
    assert all("docker update" not in step for step in plan.steps)
    with pytest.raises(c.SandboxError): cp.apply(m, {"agent_context_enabled": True})
    current = c.resolve(m["id"])
    assert current["operation"] == "config-update" and not ac.enabled(current)
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=0))
    cp.recover(current)
    assert ac.enabled(c.resolve(m["id"])) and not c.resolve(m["id"]).get("operation")


def test_disabled_readiness_does_not_claim_broken_or_reenable(monkeypatch):
    m = c.create("ocs-qa-context", agent_context_enabled=False)
    ac.refresh(m, c.env_dir, image="fixture", runtime=c.runtime_settings(m))
    monkeypatch.setattr(r, "_exec", lambda *a: SimpleNamespace(returncode=0, stdout='{"instructions":["other"]}'
                        if a[-1] == ac.SYSTEM_CONFIG else ac.path(m, c.env_dir).read_text()))
    result = r.delivery_check(m, {"Running": True})
    assert result.status == r.PASSED and "intentionally disabled" in result.detail
    monkeypatch.setattr(r, "_exec", lambda *a: SimpleNamespace(returncode=0 if a[-1] == ac.SYSTEM_CONFIG else 1,
                                                            stdout='{"instructions":[]}'))
    assert r.delivery_check(m, {"Running": True}).status == r.FAILED


@pytest.mark.parametrize("key", ["OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG", "OPENCODE_CONFIG_DIR"])
def test_reserved_profile_keys_fail_set_read_and_cli_without_secret_output(key):
    secret = "dummy-private-never-log"
    with pytest.raises(c.SandboxError, match=key): c.profile_set("reserved", {key: secret})
    path = c.profile_path("reserved")
    path.write_text(json.dumps({key: secret}))
    path.chmod(0o600)
    with pytest.raises(c.SandboxError, match="native OpenCode"): c.profile_read("reserved")
    result = CliRunner().invoke(app, ["create", "ocs-qa-reserved", "--profile", "reserved"])
    assert result.exit_code != 0 and secret not in result.output + str(result.exception)
    assert c.all_envs() == []


def test_provider_specific_and_other_opencode_variables_remain_valid():
    values = {"OPENROUTER_API_KEY": "dummy", "OPENCODE_MODEL": "provider/model", "OPENCODE_CONFIG_EXTRA": "allowed"}
    c.profile_set("legitimate", values)
    assert c.profile_read("legitimate") == values


def test_direct_executable_preserves_arguments_and_loads_data_only(tmp_path, monkeypatch, capsys):
    from opencode_sandbox.assets.images.common import ocs_opencode as launch
    profile = tmp_path / "provider.json"
    profile.write_text(json.dumps({"QA_API_KEY": "dummy $(not-evaluated)"}))
    monkeypatch.setattr(launch, "PROFILE", str(profile))
    monkeypatch.setattr(sys, "argv", ["ocs-opencode", "run", "a prompt with spaces", "--model", "qa/model"])
    monkeypatch.setenv("QA_API_KEY", "previous")
    monkeypatch.setenv("OCS_PROVIDER_LOADED", "0")
    calls = []
    monkeypatch.setattr(launch.os, "execvp", lambda executable, argv: calls.append((executable, argv, os.getenv("QA_API_KEY"))))
    monkeypatch.setattr(launch.os, "umask", lambda value: 0o022)
    launch.main()
    assert os.environ["OCS_PROVIDER_LOADED"] == "1"
    assert calls == [("opencode", ["opencode", "--standalone", "run", "a prompt with spaces", "--model", "qa/model"],
                      "dummy $(not-evaluated)")]
    assert capsys.readouterr() == ("", "")


def test_provider_screen_reports_existing_reserved_profile_without_showing_value():
    from test_tui import run, settle

    from opencode_sandbox.management_tui import ProviderScreen
    c.init_dirs()
    path = c.profile_path("invalid")
    path.write_text('{"OPENCODE_CONFIG":"dummy-secret-hidden"}')
    path.chmod(0o600)
    async def scenario(app, pilot):
        app.push_screen(ProviderScreen())
        await settle(pilot)
        row = app.screen.query_one("#providers-table").get_row("invalid")
        text = " ".join(str(cell) for cell in row)
        assert "OPENCODE_CONFIG is reserved" in text and "dummy-secret-hidden" not in text
    run(scenario)
