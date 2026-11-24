import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import backends, preferences
from opencode_sandbox import core as c
from opencode_sandbox import runtime_identity as rid
from opencode_sandbox.cli import app

HOST = {"name": "ocs-test-host", "uid": 1000, "gid": 1000}


@pytest.fixture
def host(monkeypatch):
    monkeypatch.setattr(backends, "host_identity", lambda: HOST.copy())


def allow(value=True):
    preferences.write({**preferences.read(), "allow_rootful": value})


def test_opt_in_and_metadata_visibility_when_disabled(host):
    runner = CliRunner()
    assert not preferences.read()["allow_rootful"]
    rejected = runner.invoke(app, ["create", "ocs-test-rootful", "--backend", "rootful"])
    assert rejected.exit_code != 0
    assert "Rootful Docker is disabled" in str(rejected.exception)
    enabled = runner.invoke(app, ["config", "global", "--allow-rootful"])
    assert enabled.exit_code == 0
    created = runner.invoke(app, ["create", "ocs-test-rootful", "--backend", "rootful"])
    assert created.exit_code == 0, created.output
    m = c.resolve("ocs-test-rootful")
    assert m["identity"] == HOST and m["backend"] == backends.ROOTFUL

    allow(False)
    assert c.resolve(m["id"]) == m
    listed = runner.invoke(app, ["list"])
    assert "rootful" in listed.output and "1000:1000" in listed.output
    with pytest.raises(c.SandboxError, match="disabled"):
        c.start(m)
    with pytest.raises(c.SandboxError, match="immutable"):
        c.save({**m, "backend": "rootless", "schema": c.METADATA_SCHEMA})


def test_distinct_daemon_routing_and_failed_rootful_never_falls_back(host, monkeypatch):
    allow()
    rootless = c.create("ocs-test-rootless")
    rootful = c.create("ocs-test-rootful", backend="rootful")
    launched = []
    verified = []

    def verify(context=None, *, rootful=False, **kwargs):
        verified.append(rootful)
        return rid.Identity(rid.VERIFIED, context, "unix:///rootful" if rootful else "unix:///rootless")

    def call(argv, **kwargs):
        launched.append(argv[2])
        return SimpleNamespace(returncode=1, stderr="no such container")

    monkeypatch.setattr(rid, "verify", verify)
    monkeypatch.setattr(c, "call", call)
    assert c.inspect_container(rootful) is None
    assert c.inspect_container(rootless) is None
    assert c.inspect_container(rootful) is None
    assert verified == [True, False, True]
    assert launched == ["unix:///rootful", "unix:///rootless", "unix:///rootful"]

    monkeypatch.setattr(rid, "verify", lambda **k: rid.Identity(rid.MISMATCH, "rootful", None))
    with pytest.raises(c.PrerequisiteError):
        c.inspect_container(rootful)
    assert len(launched) == 3


def test_rootful_peer_requires_root_unmapped_dockerd(tmp_path):
    proc = tmp_path / "12"
    proc.mkdir()
    (proc / "comm").write_text("dockerd\n")
    for kind in ("uid", "gid"):
        (proc / (kind + "_map")).write_text("          0          0 4294967295\n")
    assert rid.inspect_rootful_peer(12, 0, 0, proc=tmp_path)[0] is None
    assert rid.inspect_rootful_peer(12, 1000, 0, proc=tmp_path)[0] == rid.MISMATCH
    (proc / "uid_map").write_text("0 100000 65536\n")
    assert rid.inspect_rootful_peer(12, 0, 0, proc=tmp_path)[0] == rid.UNVERIFIED_PROXY


def test_launch_uses_non_root_user_and_rootful_home(host, monkeypatch):
    allow()
    m = c.create("ocs-test-runtime", backend="rootful")
    calls = []
    monkeypatch.setattr(c, "ensure_runtime", lambda *a: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "ensure_volume", lambda m: None)
    monkeypatch.setattr(c, "guidance_inputs", lambda m, **k: {"image": c.env_image(m), "runtime": c.runtime_settings(m)})
    monkeypatch.setattr(c, "image_definition", lambda *a, **k: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout=""))
    c.start(m)
    run = next(argv for argv in calls if argv[0] == "run")
    assert run[run.index("--user") + 1] == "1000:1000"
    assert f"type=volume,src={c.volume(m)},dst=/home/ocs" in run
    assert "HOME=/home/ocs" in run
    for flag in ("no-new-privileges:true", "--privileged", "--group-add", "--cap-add"):
        assert flag not in run
    assert run[run.index("--network") + 1] != "host"
    assert all("docker.sock" not in arg for arg in run)


def test_global_maintenance_switch_selects_daemon(host, monkeypatch):
    from opencode_sandbox import cleanup

    allow()

    def inventory():
        assert backends.selected() == backends.ROOTFUL
        return cleanup.Inventory("/test", "test", backend=backends.ROOTFUL)

    monkeypatch.setattr(cleanup, "inventory", inventory)
    result = CliRunner().invoke(app, ["--docker-backend", "rootful", "disk", "usage"])
    assert result.exit_code == 0, result.output
    assert "Docker backend: rootful" in result.output
    assert backends.selected() == backends.ROOTLESS


def test_metadata_rejects_missing_identity(host):
    allow()
    m = c.create("ocs-test-runtime", backend="rootful")
    path = Path(c.env_dir(m["id"])) / "metadata.json"
    path.write_text(json.dumps({**m, "identity": None}))
    assert "invalid Docker backend or runtime identity" in c.metadata_error(path)


def test_compact_dashboard_rootful_creation(host, monkeypatch):
    import asyncio

    from textual.widgets import Button, Checkbox, Input, Select

    from opencode_sandbox import tui

    monkeypatch.setattr(tui.Dashboard, "_prerequisites_worker", lambda *a: None)

    async def check():
        dashboard = tui.Dashboard()
        dashboard._disable_notifications = True
        async with dashboard.run_test(size=(80, 24)) as pilot:
            await pilot.press("g")
            toggle = dashboard.screen.query_one("#allow-rootful", Checkbox)
            assert not toggle.value
            toggle.value = True
            dashboard.screen.query_one("#save-settings", Button).press()
            await pilot.pause()
            await pilot.press("n")
            form = dashboard.screen
            form.query_one("#name", Input).value = "ocs-test-rootful"
            form.query_one("#more").collapsed = False
            await pilot.pause()
            backend = form.query_one("#backend", Select)
            backend.focus()
            await pilot.press("enter", "down", "enter")
            assert backend.value == "rootful"
            form.query_one("#create", Button).press()
            await pilot.pause()
            assert isinstance(dashboard.screen, tui.ConfirmScreen)
            assert "host root authority" in dashboard.screen.message
            # Escape cancels the warning and no metadata has been written.
            await pilot.press("escape")
            assert not c.all_envs()

    asyncio.run(check())


def test_recovery_prepares_identity_before_publishing_running(host, monkeypatch):
    from opencode_sandbox import agent_context

    allow()
    m = c.create("ocs-test-recover", backend="rootful")
    snapshot = f"ocs-snapshot:{m['id']}-test"
    c.mark(m, "recreating", operation="recreate", image=snapshot, last_snapshot=snapshot)
    monkeypatch.setattr(c, "ensure_runtime", lambda *a: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": True})
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(stdout=snapshot))
    monkeypatch.setattr(c, "guidance_inputs", lambda m: {"image": snapshot, "runtime": c.runtime_settings(m)})
    work = []
    monkeypatch.setattr(c, "_initialize_rootful", lambda m: work.append("identity"))
    monkeypatch.setattr(agent_context, "reconcile", lambda m: work.append("context"))
    assert c.recreate_recover(m) == "replacement already running"
    assert work == ["identity", "context"]
    assert c.resolve(m["id"])["operation"] is None
