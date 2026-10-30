"""Local version inventory survives independent registry and per-environment failures.

Docker and npm are mocked; metadata and the Textual pilot use isolated real files.
"""
from types import SimpleNamespace

import pytest
from test_tui import run, settle
from typer.testing import CliRunner

from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v
from opencode_sandbox.cli import app
from opencode_sandbox.updates_tui import UpdatesScreen


@pytest.fixture
def inventory(monkeypatch):
    running = c.create("ocs-test-up02-running", "scratch")
    stopped = c.create("ocs-test-up02-stopped", "scratch")
    created = c.create("ocs-test-up02-created", "scratch")
    states = {running["id"]: {"Running": True}, stopped["id"]: {"Running": False}, created["id"]: None}
    events = []
    discovery = {"version": "2.2.0", "error": c.SandboxError("Registry unavailable [test]")}

    def inspect(m):
        events.append(("inspect", m["id"]))
        return states[m["id"]]

    def docker(*args, **kwargs):
        if args[:2] == ("container", "inspect"):
            return SimpleNamespace(returncode=0, stdout="a" * 64 + "|sha256:" + "b" * 64 + "|" + args[-1].removeprefix("ocs-"), stderr="")
        if args[:2] == ("image", "inspect"):  # dashboard's independent startup advisory
            return SimpleNamespace(returncode=1, stdout="", stderr="No such image")
        assert args == ("exec", "a" * 64, "timeout", "--signal=KILL", "5s", "opencode", "--version"), args
        events.append(args)
        return SimpleNamespace(returncode=0, stdout="opencode v2.1.4\n", stderr="")

    def latest():
        events.append(("registry",))
        if discovery["error"] is not None:
            raise discovery["error"]
        return discovery["version"]

    monkeypatch.setattr(c, "inspect_container", inspect)
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(v, "latest", latest)
    paths = [c.env_dir(m["id"]) / "metadata.json" for m in (running, stopped, created)]
    return SimpleNamespace(events=events, states=states, discovery=discovery, files={p: p.read_bytes() for p in paths})


def assert_local_rows(text):
    assert "ocs-test-up02-running: 2.1.4; notify" in text
    assert "ocs-test-up02-stopped: notify; not checked (stopped)" in text
    assert "ocs-test-up02-created: notify; not-created" in text
    assert "current" not in text and "update available" not in text


def assert_read_only_checks(inventory, *, check=True, ordered=True):
    assert {p: p.read_bytes() for p in inventory.files} == inventory.files
    assert inventory.events.count(("registry",)) == int(check)
    if check and ordered:
        # Local collection must not depend on a successful registry check.
        assert inventory.events[-1] == ("registry",)
    assert {a[1] for a in inventory.events if a[0] == "inspect"} == set(inventory.states)
    assert len([a for a in inventory.events if a[0] == "exec"]) == 1  # running only


async def check_updates(app, pilot):
    await pilot.press("v", "3")
    await settle(pilot)
    screen = app.screen
    assert isinstance(screen, UpdatesScreen)
    table = screen.query_one("#updates-table")
    running = next(m for m in c.all_envs() if m["name"] == "ocs-test-up02-running")
    table.move_cursor(row=table.get_row_index(running["id"]))
    await pilot.press("c")
    await settle(pilot)
    return screen


REGISTRY_ERRORS = [
    c.SandboxError("Registry unavailable [test]"),
    TimeoutError("registry timed out"),
    c.SandboxError("Cannot check OpenCode npm registry: HTTP Error 429: Too Many Requests"),
    c.SandboxError("Cannot check OpenCode npm registry: invalid JSON"),
    RuntimeError("Unexpected registry failure [test]"),
]


@pytest.mark.parametrize("error", REGISTRY_ERRORS)
def test_cli_inventory_survives_registry_failure(inventory, error):
    inventory.discovery["error"] = error
    result = CliRunner().invoke(app, ["opencode", "versions", "--check"])
    assert_local_rows(result.stdout)
    assert f"npm registry check failed: {c.error_text(error)}" in result.stderr
    assert "npm registry:" not in result.stdout
    assert result.exit_code == 2
    assert_read_only_checks(inventory)


@pytest.mark.parametrize("error", REGISTRY_ERRORS)
def test_tui_inventory_survives_registry_failure(inventory, error):
    inventory.discovery["error"] = error
    async def t(app, pilot):
        screen = await check_updates(app, pilot)
        rows = {i["name"]: i for i in screen.items["environments"].values()}
        assert rows["ocs-test-up02-running"]["version"] == "2.1.4"
        assert rows["ocs-test-up02-stopped"]["state"] == "stopped"
        assert rows["ocs-test-up02-created"]["state"] == "not-created"
        assert f"Check failed: {c.error_text(error)}" in screen.discovery_text()
        assert_read_only_checks(inventory, ordered=False)
        await pilot.press("escape")
        assert len(app.screen_stack) == 1
    run(t, (80, 24))


def test_cli_inventory_without_check_never_queries_registry(inventory):
    result = CliRunner().invoke(app, ["opencode", "versions"])
    assert result.exit_code == 0 and not result.stderr
    assert_local_rows(result.stdout)
    assert_read_only_checks(inventory, check=False)


@pytest.mark.parametrize("frontend", ["cli", "tui"])
@pytest.mark.parametrize("registry_ok", [False, True])
@pytest.mark.parametrize("error", [OSError("Cannot read local metadata [test]"), RuntimeError("Local inventory defect [test]")])
def test_local_source_failure_does_not_hide_registry_result(monkeypatch, inventory, frontend, registry_ok, error):
    inventory.discovery["error"] = None if registry_ok else c.SandboxError("Registry unavailable [test]")
    def fail():
        raise error
    monkeypatch.setattr(v, "versions", fail)

    def check(text):
        assert f"Local version inventory failed: {c.error_text(error)}" in text
        if registry_ok:
            assert "npm registry: 2.2.0" in text and "npm registry check failed" not in text
        else:
            assert "npm registry check failed: Registry unavailable [test]" in text
        assert inventory.events == [("registry",)]

    if frontend == "cli":
        result = CliRunner().invoke(app, ["opencode", "versions", "--check"])
        assert result.exit_code == 2
        check(result.output)
    else:
        async def t(app, pilot):
            # The new UI enumerates local metadata independently of the CLI's active report.
            await pilot.press("v", "3")
            await settle(pilot)
            screen = app.screen
            def fail_metadata(): raise error
            monkeypatch.setattr(c, "all_envs", fail_metadata)
            await pilot.press("escape", "v", "3", "c")
            await settle(pilot)
            screen = app.screen
            assert screen.inventory_error == c.error_text(error)
            assert not screen.items["environments"]
            if registry_ok:
                assert "npm: 2.2.0" in screen.discovery_text() and "Check failed" not in screen.discovery_text()
            else:
                assert "Check failed: Registry unavailable [test]" in screen.discovery_text()
            assert inventory.events.count(("registry",)) == 1
        run(t, (80, 24))


@pytest.mark.parametrize("frontend", ["cli", "tui"])
@pytest.mark.parametrize("registry_ok", [False, True])
@pytest.mark.parametrize("row_error", [ValueError("Cannot format row [test]"), KeyError("version")])
def test_bad_rows_do_not_hide_other_environments(monkeypatch, inventory, frontend, registry_ok, row_error):
    inventory.discovery["error"] = None if registry_ok else c.SandboxError("Registry unavailable [test]")
    bad_policy = c.create("ocs-test-up02-policy", "scratch")
    bad_policy["opencode_policy"] = []  # unhashable policy: even malformed values stay per-row
    c.save(bad_policy)
    bad_docker = c.create("ocs-test-up02-docker", "scratch")
    bad_format = c.create("ocs-test-up02-format", "scratch")
    for m in (bad_policy, bad_docker, bad_format):
        path = c.env_dir(m["id"]) / "metadata.json"
        inventory.files[path] = path.read_bytes()
    real_inspect, real_line = c.inspect_container, v.environment_line
    def inspect(m):
        if m["id"] == bad_docker["id"]:
            raise c.SandboxError("Container ownership refused [test]")
        if m["id"] == bad_format["id"]:
            return None
        return real_inspect(m)
    def line(item, newest=None):
        if item["id"] == bad_format["id"]:
            raise row_error
        return real_line(item, newest)
    monkeypatch.setattr(c, "inspect_container", inspect)
    monkeypatch.setattr(v, "environment_line", line)

    def check(text):
        assert "ocs-test-up02-policy: error: TypeError:" in text
        assert "ocs-test-up02-docker: error: Container ownership refused [test]" in text
        assert f"ocs-test-up02-format: check failed ({c.error_text(row_error)})" in text
        assert "ocs-test-up02-stopped: notify; not checked (stopped)" in text
        assert "ocs-test-up02-created: notify; not-created" in text
        if registry_ok:
            assert "ocs-test-up02-running: 2.1.4; update available: 2.1.4 -> 2.2.0" in text
        else:
            assert_local_rows(text)
            assert "npm registry check failed" in text
        assert_read_only_checks(inventory)

    if frontend == "cli":
        result = CliRunner().invoke(app, ["opencode", "versions", "--check"])
        assert result.exit_code == 2
        check(result.output)
        assert "check failed" in result.stderr and "ownership refused" in result.stderr
    else:
        async def t(app, pilot):
            screen = await check_updates(app, pilot)
            rows = {i["name"]: i for i in screen.items["environments"].values()}
            assert rows[bad_policy["name"]]["error"].startswith("TypeError:")
            assert rows[bad_docker["name"]]["error"] == "Container ownership refused [test]"
            assert screen.item_summary(rows[bad_format["name"]]) == f"check failed ({c.error_text(row_error)})"
            assert rows["ocs-test-up02-stopped"]["state"] == "stopped"
            assert rows["ocs-test-up02-created"]["state"] == "not-created"
            text = screen.item_summary(rows["ocs-test-up02-running"])
            if registry_ok: assert "update available: 2.1.4 -> 2.2.0" in text
            else: assert "Check failed: Registry unavailable [test]" in screen.discovery_text()
            assert_read_only_checks(inventory, ordered=False)
        run(t, (80, 24))


@pytest.mark.parametrize("mode", ["notify", "manual", "pinned"])
def test_shared_inventory_compares_every_policy_without_changing_it(inventory, mode):
    inventory.discovery["error"] = None
    running = next(m for m in c.all_envs() if m["name"] == "ocs-test-up02-running")
    v.set_policy(running, mode, "2.1.4" if mode == "pinned" else None)
    lines, errors = v.versions_report(check=True)
    assert errors == [] and lines[0] == "npm registry: 2.2.0"
    expected = ("" if mode == "notify" else mode + "; ") + "update available: 2.1.4 -> 2.2.0"
    assert f"{running['name']}: 2.1.4; {expected}" in lines
    assert c.resolve(running["id"])["opencode_policy"] == mode


@pytest.mark.parametrize("check", [False, True])
def test_empty_inventory_can_still_report_discovery(monkeypatch, check):
    looked_up = []
    monkeypatch.setattr(v, "latest", lambda: looked_up.append(1) or "2.2.0")
    lines, errors = v.versions_report(check=check)
    assert lines == (["npm registry: 2.2.0"] if check else []) and errors == []
    assert looked_up == ([1] if check else [])
