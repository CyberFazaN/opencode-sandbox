"""Creation refuses unavailable managed images before persisting user data."""
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_tui import run
from test_updates_tui import until
from textual.widgets import Button, Input, Select
from typer.testing import CliRunner

from opencode_sandbox import backends, distros, preferences
from opencode_sandbox import core as c
from opencode_sandbox.cli import app

pytestmark = pytest.mark.creation_base


@pytest.fixture
def inventory(monkeypatch):
    preferences.write({**preferences.read(), "allow_rootful": True})
    monkeypatch.setattr(backends, "host_identity", lambda: {"name": "coder", "uid": 1100, "gid": 1100})
    calls = []
    images = {}
    def docker(*args, **kwargs):
        backend = backends.selected()
        calls.append((backend, args))
        assert args[:2] == ("image", "inspect")
        return images.get((backend, args[-1]), SimpleNamespace(
            returncode=1, stderr=f"Error response from daemon: No such image: {args[-1]}", stdout=""))
    monkeypatch.setattr(c, "docker", docker)
    return images, calls


def present(distro, image_id):
    labels = {distros.LABEL + "managed": "true", **distro.image_labels()}
    return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps([
        {"Id": image_id, "Config": {"Labels": labels}},
    ]))


@pytest.mark.parametrize("available", backends.NAMES)
def test_cli_checks_only_selected_daemon(inventory, available, tmp_path):
    distro = distros.get("kali")
    images, calls = inventory
    images[available, distro.image] = present(distro, "sha256:" + "c" * 64)
    missing = next(name for name in backends.NAMES if name != available)
    source = tmp_path / "input"
    source.mkdir()
    (source / "example").write_text("data")

    runner = CliRunner()
    result = runner.invoke(app, ["create", "ocs-test-missing", "--distro", distro.id,
                                 "--backend", missing, "--source", str(source)])
    assert result.exit_code != 0
    flag = "--docker-backend rootful " if missing == backends.ROOTFUL else ""
    assert f"opencode-sandbox {flag}build --distro kali" in str(result.exception)
    assert c.all_envs() == []
    assert calls == [(missing, ("image", "inspect", distro.image))]

    created = runner.invoke(app, ["create", "ocs-test-present", "--distro", distro.id,
                                  "--backend", available, "--source", str(source)])
    assert created.exit_code == 0, created.exception
    m, = c.all_envs()
    assert backends.get(m) == available and (c.env_dir(m["id"]) / "workspace" / "example").read_text() == "data"


def test_daemon_failure_is_not_a_build_instruction(inventory):
    distro = distros.get("kali")
    images, _ = inventory
    images[backends.ROOTFUL, distro.image] = SimpleNamespace(returncode=1, stderr="permission denied", stdout="")
    with pytest.raises(c.SandboxError, match="rootful Docker: permission denied") as error:
        c.create("ocs-test-unknown", distro=distro.id, backend=backends.ROOTFUL)
    assert "build --distro" not in str(error.value)
    assert c.all_envs() == []


def test_foreign_base_tag_is_neither_used_nor_modified(inventory):
    d = distros.get(distros.DEFAULT)
    images, calls = inventory
    images[backends.ROOTLESS, d.image] = SimpleNamespace(returncode=0, stderr="", stdout=json.dumps([
        {"Id": "sha256:" + "c" * 64, "Config": {"Labels": {}}},
    ]))
    with pytest.raises(c.SandboxError, match="Refusing unmanaged/foreign base image"):
        c.create("ocs-test-foreign")
    assert calls == [(backends.ROOTLESS, ("image", "inspect", d.image))]
    assert not c.all_envs()


def test_cached_base_versions_belong_to_the_inspected_daemon(inventory, monkeypatch):
    from opencode_sandbox import opencode_versions as versions
    from opencode_sandbox import updates

    d = distros.get(distros.DEFAULT)
    image_id = "sha256:" + "c" * 64
    images, calls = inventory
    for backend in backends.NAMES:
        images[backend, d.image] = present(d, image_id)
    monkeypatch.setattr(c, "docker_endpoint", lambda: f"unix:///test-{backends.selected()}.sock")
    probes = []

    def version_probe(ref, *args, **kwargs):
        probes.append((backends.selected(), ref))
        return SimpleNamespace(stdout="2.1.4")

    monkeypatch.setattr(versions.probes, "image", version_probe)
    checked = updates.base_inventory(d, check=True)
    assert checked["version"] == "2.1.4" and checked["verification"] == "verified"
    with backends.use(backends.ROOTFUL):
        rootful = updates.base_inventory(d)
    assert rootful["state"] == checked["state"] and rootful["version"] is None
    cached = updates.base_inventory(d)
    assert cached["version"] == "2.1.4" and cached["verification"] == "last-verified"
    assert probes == [(backends.ROOTLESS, image_id)]
    assert all(args == ("image", "inspect", d.image) for _, args in calls)


def test_rootful_opt_in_is_required_before_inspecting(inventory):
    _, calls = inventory
    preferences.write({**preferences.read(), "allow_rootful": False})
    with pytest.raises(c.SandboxError, match="Rootful Docker is disabled"):
        c.create("ocs-test-disabled", backend=backends.ROOTFUL)
    assert not calls and not c.all_envs()


def test_existing_container_restarts_without_inspecting_base(inventory, monkeypatch):
    distro = distros.get(distros.DEFAULT)
    images, calls = inventory
    images[backends.ROOTFUL, distro.image] = present(distro, "sha256:" + "c" * 64)
    m = c.create("ocs-test-restart", backend=backends.ROOTFUL)
    del images[backends.ROOTFUL, distro.image]
    with pytest.raises(c.MissingBaseImage, match="Rootful Docker is missing"):
        monkeypatch.setattr(c, "inspect_container", lambda m: None)
        c.start(m)
    calls.clear()
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False})
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    monkeypatch.setattr(c, "recheck_mount", lambda m: None)
    monkeypatch.setattr(c, "mounted_profile", lambda m: None)
    monkeypatch.setattr(c, "_prepare_running_environment", lambda m: None)
    monkeypatch.setattr(c, "docker", lambda *a, **kw: calls.append((backends.selected(), a)))
    c.start(m)
    assert calls == [(backends.ROOTFUL, ("start", c.cname(m)))]


def test_system_restore_does_not_require_base_but_files_only_does(inventory, monkeypatch, tmp_path):
    from opencode_sandbox import backup

    _, calls = inventory
    path = tmp_path / "ocs-test-backup"
    path.mkdir()
    manifest = {"environment": {"kind": "scratch", "distro": distros.DEFAULT},
                "files": {"system-image.tar": {}}, "workspace": {"mode": "managed", "included": True}}
    monkeypatch.setattr(backup, "verify", lambda root: manifest)
    monkeypatch.setattr(backup, "_check_restore_space", lambda *a: None)
    monkeypatch.setattr(backup, "_check_image_tag_free", lambda path: None)
    monkeypatch.setattr(backup, "_restore_into", lambda m, *a, **kw: m)
    with pytest.raises(c.MissingBaseImage):
        backup.restore(path, "ocs-test-files-only", restore_system=False)
    assert not c.all_envs()
    calls.clear()
    restored = backup.restore(path, "ocs-test-system")
    assert restored["operation"] == "restore" and restored["restore_system"]
    assert not calls


@pytest.mark.parametrize("size", [(60, 18), (80, 24)])
def test_missing_rootful_form_keeps_values_and_opens_same_backend(inventory, monkeypatch, size):
    import asyncio

    from opencode_sandbox import readiness
    from opencode_sandbox.updates_tui import UpdatesScreen

    mounted = asyncio.Event()
    on_mount = UpdatesScreen.on_mount

    def on_base_mount(screen):
        on_mount(screen)
        screen.call_after_refresh(mounted.set)

    monkeypatch.setattr(UpdatesScreen, "on_mount", on_base_mount)
    distro = distros.get("kali")
    images, _ = inventory
    images[backends.ROOTLESS, distro.image] = present(replace(distro, revision=distro.revision + 1), "sha256:" + "a" * 64)
    assert readiness.image_checks()[-1].image_status is None

    async def test(dashboard, pilot):
        await pilot.press("n")
        form = dashboard.screen
        form.query_one("#name", Input).value = "ocs-test-retry"
        form.query_one("#more").collapsed = False
        form.query_one("#distro", Select).value = "kali"
        form.query_one("#backend", Select).value = backends.ROOTFUL
        await pilot.pause()
        form.query_one("#create", Button).press()
        shortcut = form.query_one("#create-base-images", Button)
        await until(pilot, lambda: shortcut.display and shortcut.region.height > 0)
        assert dashboard.screen is form and not c.all_envs()
        assert shortcut.region.bottom <= size[1]
        assert form.query_one("#name", Input).value == "ocs-test-retry"
        shortcut.press()
        await asyncio.wait_for(mounted.wait(), 5)
        screen = dashboard.screen
        assert screen.view == "bases"
        assert screen.selected_key() == "kali"
        assert screen.query_one("#base-backend", Select).value == backends.ROOTFUL
        assert screen.query_one("#base-backend", Select).region.height == 1
        await pilot.press("escape")
        assert dashboard.screen is form and form.query_one("#distro", Select).value == "kali"
    run(test, size)


@pytest.mark.parametrize("size", [(60, 18), (80, 24)])
def test_base_selector_ignores_delayed_other_backend(monkeypatch, inventory, size):
    import asyncio
    import threading

    from opencode_sandbox import readiness, updates

    monkeypatch.setattr(readiness, "image_checks", list)
    entered, release = threading.Event(), threading.Event()

    def inspect(distro, *, check=False):
        if backends.selected() == backends.ROOTLESS:
            if distro.id == distros.DEFAULT:
                entered.set()
                assert release.wait(5)
            return {"state": "old definition", "version": "2.1.0"}
        return {"state": "current definition", "version": "2.2.0"}

    monkeypatch.setattr(updates, "base_inventory", inspect)

    async def test(app, pilot):
        await pilot.press("v", "2")
        screen = app.screen
        selector = screen.query_one("#base-backend", Select)
        assert selector.value == backends.ROOTLESS and selector.region.height == 1
        assert await asyncio.to_thread(entered.wait, 2)
        selector.focus()
        await pilot.press("enter", "down", "enter")
        await until(pilot, lambda: all(row.get("version") == "2.2.0" for row in screen.items["bases"].values()))
        assert selector.value == backends.ROOTFUL
        release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert all(row["version"] == "2.2.0" for row in screen.items["bases"].values())
        assert screen.query_one("#updates-table").region.height >= 3
        assert all(button.region.bottom <= size[1] for button in screen.query(Button) if button.display)
    try:
        run(test, size)
    finally:
        release.set()


def test_updates_defaults_to_selected_backends_images_without_an_advisory(inventory):
    images, _ = inventory
    distro = distros.get(distros.DEFAULT)
    images[backends.ROOTFUL, distro.image] = present(distro, "sha256:" + "c" * 64)
    c.create("ocs-test-rootful-updates", backend=backends.ROOTFUL)

    async def test(app, pilot):
        await app.workers.wait_for_complete()
        assert not app._image_advisory
        await pilot.press("v", "2")
        assert app.screen.query_one("#base-backend", Select).value == backends.ROOTFUL

    run(test, (80, 24))


def test_covered_create_form_is_reenabled_after_base_check(monkeypatch):
    import asyncio
    import threading

    from opencode_sandbox.tui import ConfirmScreen

    entered, release = threading.Event(), threading.Event()

    def check(*args):
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr(c, "check_creation_base", check)

    async def test(app, pilot):
        await pilot.press("n")
        form = app.screen
        form.query_one("#name", Input).value = "ocs-test-covered"
        button = form.query_one("#create", Button)
        button.press()
        assert await asyncio.to_thread(entered.wait, 2)
        assert button.disabled
        await app.push_screen(ConfirmScreen("Cover the create form"))
        release.set()
        await app.workers.wait_for_complete()
        await pilot.press("escape")
        assert app.screen is form and not button.disabled
        assert not c.all_envs()

    try:
        run(test, (80, 24))
    finally:
        release.set()
