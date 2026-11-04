from pathlib import Path

import pytest
from test_opencode_configs import service as service  # noqa: PLC0414 — explicit pytest fixture re-export
from test_tui import run, settle
from textual.widgets import Button, Select, TextArea

from opencode_sandbox import core as c
from opencode_sandbox import opencode_configs as oc
from opencode_sandbox.opencode_configs_tui import ConfigEditorScreen, ReloadConfigScreen
from opencode_sandbox.tui import CreateScreen


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
def test_editor_reopens_export_confirms_delete_and_drift_cancel(service, size):
    m, _, live = service
    async def scenario(app, pilot):
        app.push_screen(ConfigEditorScreen(m))
        await settle(pilot)
        editor = app.screen
        assert not editor.query_one("#oc-apply", Button).display
        editor.query_one("#oc-export", Button).press()
        await settle(pilot, 0.5)
        exported = oc.export_path(m) / "config"
        assert editor.available and exported.is_dir()
        (exported / "opencode.json").write_text("host edit")
        (live / "opencode.json").write_text("container drift")
        editor.query_one("#oc-apply", Button).press()
        await settle(pilot, 0.5)
        assert type(app.screen).__name__ == "DriftScreen"
        labels = [str(b.label) for b in app.screen.query(Button)]
        assert labels == ["Cancel", "Overwrite Anyway"]
        await pilot.press("escape")
        await settle(pilot)
        assert (live / "opencode.json").read_text() == "container drift"
        assert editor.query_one("#oc-editor-text", TextArea).text.startswith("Apply canceled")
        editor.query_one("#oc-apply", Button).press()
        await settle(pilot, 0.5)
        app.screen.query_one("#oc-drift-overwrite", Button).press()
        await settle(pilot, 0.5)
        assert (live / "opencode.json").read_text() == "host edit"
        await pilot.press("escape")
        await settle(pilot)
        assert exported.exists()
        app.push_screen(ConfigEditorScreen(c.resolve(m["id"])))
        await settle(pilot)
        editor = app.screen
        assert editor.available and str(exported) in str(editor.query_one("#oc-editor-status").render())
        editor.query_one("#oc-delete", Button).press()
        await settle(pilot)
        assert type(app.screen).__name__ == "ConfirmScreen"
        await pilot.press("escape")
        await settle(pilot)
        assert exported.exists()
        editor.query_one("#oc-delete", Button).press()
        await settle(pilot)
        app.screen.query_one("#confirm", Button).press()
        await settle(pilot, 0.5)
        assert not exported.exists() and not editor.query_one("#oc-apply", Button).display
    run(scenario, size)


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
def test_main_configs_settings_editor_and_local_reload_empty(service, size):
    _m, _, live = service
    async def scenario(app, pilot):
        app.action_opencode_configs()
        await settle(pilot)
        assert "maintained by you" in str(app.screen.query_one("Static").render())
        await pilot.press("escape")
        await settle(pilot)
        app.action_runtime()
        await settle(pilot)
        assert app.screen.query_one("#rt-agent-context").value is True
        app.screen.query_one("#rt-config-editor", Button).press()
        await settle(pilot)
        assert isinstance(app.screen, ConfigEditorScreen)
        await pilot.press("escape")
        await settle(pilot)
        app.screen.query_one("#rt-config-reload", Button).press()
        await settle(pilot)
        assert isinstance(app.screen, ReloadConfigScreen)
        assert app.screen.query_one("#oc-reload-source", Select).value == ""
        app.screen.query_one("#oc-reload-confirm", Button).press()
        await settle(pilot)
        text = str(app.screen.query_one("Static").render())
        assert "ENTIRE" in text and "Empty completely clears" in text and "Container is running" not in text
        app.screen.query_one("#confirm", Button).press()
        await settle(pilot, 0.5)
        assert list(live.iterdir()) == []
        assert app.screen.query_one("#oc-reload-text", TextArea).text.startswith("Reloaded: Empty.")
    run(scenario, size)


def test_creation_local_copy_requires_selection_and_keeps_default_context():
    async def scenario(app, pilot):
        app.push_screen(CreateScreen())
        await settle(pilot)
        form = app.screen
        form.query_one("#name").value = "ocs-qa-form"
        assert form.values()["opencode_config"] is None and form.values()["agent_context_enabled"] is True
        form.query_one("#more").collapsed = False
        form.query_one("#oc-config-mode", Select).value = "copy"
        await settle(pilot)
        with pytest.raises(c.SandboxError, match="Copy requires"): form.values()
        form.query_one("#oc-config-mode", Select).value = "local"
        await settle(pilot)
        assert not form.query_one("#oc-config-profile", Select).display
    run(scenario)


def test_unreadable_profiles_location_is_reported_not_a_crash(service):
    m, _, _ = service
    root = oc.profiles_directory()
    root.mkdir(parents=True)
    root.chmod(0)
    try:
        async def scenario(app, pilot):
            app.push_screen(ReloadConfigScreen(m))
            await settle(pilot)
            assert "Cannot read OpenCode profiles" in app.screen.query_one("#oc-reload-text", TextArea).text
            await pilot.press("escape")
            app.push_screen(CreateScreen())
            await settle(pilot)
            assert "Cannot read OpenCode profiles" in str(app.screen.query_one("#oc-config-hint").render())
        assert run(scenario).return_code in (None, 0)
    finally:
        root.chmod(0o700)


def test_invalid_export_offers_replacement_and_delete_not_apply(service):
    m, _, _ = service
    exported = Path(oc.export(m))
    (exported.parent / oc.MARKER).write_text("{}")
    async def scenario(app, pilot):
        app.push_screen(ConfigEditorScreen(m))
        await settle(pilot)
        editor = app.screen
        assert "Invalid export" in str(editor.query_one("#oc-editor-status").render())
        assert not editor.query_one("#oc-apply", Button).display and editor.query_one("#oc-delete", Button).display
        editor.query_one("#oc-export", Button).press()
        await settle(pilot)
        assert type(app.screen).__name__ == "ConfirmScreen"
        app.screen.query_one("#confirm", Button).press()
        await settle(pilot, 0.5)
        assert editor.available and editor.query_one("#oc-apply", Button).display
    run(scenario)
