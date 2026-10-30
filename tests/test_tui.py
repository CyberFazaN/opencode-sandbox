"""H01-H07: Textual pilot tests (fake Docker, isolated data)."""
import asyncio
from types import SimpleNamespace

import pytest
from textual.widgets import Button

from opencode_sandbox import core as c
from opencode_sandbox import tui
from opencode_sandbox.management_tui import ProviderScreen


@pytest.fixture(autouse=True)
def fake_runtime(monkeypatch):
    calls = []
    monkeypatch.setattr(c, "docker", lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "ensure_volume", lambda m: None)
    return calls


def run(test, size=(100, 30)):
    async def main():
        app = tui.Dashboard()
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await test(app, pilot)
        return app
    return asyncio.run(main())


async def settle(pilot, seconds=0.2):
    await pilot.pause(); await asyncio.sleep(seconds); await pilot.pause()


def stack(app):
    return [type(s).__name__ for s in app.screen_stack]


def test_empty_state_and_invalid_metadata():
    bad = c.BASE / "environments" / "0000000000000000"
    bad.mkdir(parents=True)
    (bad / "metadata.json").write_text("{broken")
    async def t(app, pilot):
        assert "No environment selected" in str(app.query_one("#details").render())
        assert "Press n for a new environment" in str(app.query_one("#details").render())
        assert any("invalid metadata" in n.message for n in app._notifications)
    run(t)


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
def test_every_button_visible_and_table_usable(size):
    """At 80x24 11 of 20 buttons were off-screen and the table had one row."""
    for i in range(6):
        c.create(f"ocs-qa-{i}", "scratch")
    async def t(app, pilot):
        w, h = size
        for b in app.query(Button):
            r = b.region
            assert r.width > 0 and r.right <= w and r.bottom <= h, (b.id, r)
            assert str(b.label).strip() and len(str(b.label)) <= r.width, (b.id, r)
            assert r.height == 1, (b.id, r)  # a wrapped label pushed a bar onto another row
        assert app.query_one("#envs").region.height >= 5
        details = app.query_one("#details")
        assert details.content_region.height >= 7  # incl. 'Error:' line, previously clipped
    run(t, size)


def test_initial_focus_lets_letter_keys_work():
    async def t(app, pilot):
        assert app.focused.id == "envs"
        await pilot.press("slash")
        assert app.focused.id == "search"
        await pilot.press("q")  # typed into the filter, not quit
        assert app.query_one("#search").value == "q"
        app.query_one("#envs").focus()
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running
    run(t)


def test_enter_on_row_opens_opencode(monkeypatch):
    c.create("ocs-qa-open", "scratch")
    opened = []
    monkeypatch.setattr(tui.Dashboard, "_attach", lambda self, shell: opened.append((self.selected()["name"], shell)))
    async def t(app, pilot):
        await pilot.press("enter")
        await pilot.press("s")
        assert opened == [("ocs-qa-open", False), ("ocs-qa-open", True)]
    run(t)


def test_current_folder_requires_confirmation(tmp_path, monkeypatch):
    """One click copied the working directory into the agent workspace."""
    src = tmp_path / "proj"
    src.mkdir()
    (src / "a.txt").write_text("x")
    monkeypatch.chdir(src)
    async def t(app, pilot):
        await pilot.press("c")
        assert stack(app) == ["Screen", "ConfirmScreen"]
        assert "ALL files are COPIED" in str(app.screen.query_one("Static").render())
        await pilot.press("escape")
        await settle(pilot)
        assert c.all_envs() == []
        await pilot.press("c")
        await pilot.press("tab", "enter")  # Cancel is focused first; Tab -> Confirm
        await settle(pilot, 0.5)
        assert [m["name"] for m in c.all_envs()] == ["proj"]
    run(t)


@pytest.mark.parametrize("which", ["home", "parent", "root"])
def test_core_refuses_home_parents_and_root(tmp_path, monkeypatch, which):
    home = tmp_path / "u" / "me"
    (home / "Documents").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    source = {"home": home, "parent": home.parent, "root": "/"}[which]
    with pytest.raises(c.SandboxError, match="Refusing to import"):
        c.create("ocs-qa-home", "project", source)
    assert c.all_envs() == []
    c.create("ocs-qa-docs", "project", home / "Documents")  # a project directory below home is fine


def test_dashboard_keys_inactive_behind_subscreens(monkeypatch):
    """'x' on the Providers screen opened a delete prompt for a hidden selection."""
    c.create("ocs-qa-hidden", "scratch")
    performed = []
    monkeypatch.setattr(tui.Dashboard, "_run_operation", lambda self, a, m: performed.append(a))
    async def t(app, pilot):
        app.push_screen(ProviderScreen())
        await pilot.pause()
        app.screen.query_one("#providers-table").focus()
        for key in ("x", "f5", "f6", "n", "R", "b"):
            await pilot.press(key)
        await settle(pilot)
        assert stack(app) == ["Screen", "ProviderScreen"] and performed == []
        await pilot.press("tab")  # focus traversal still works on sub-screens
        assert app.focused is not None and app.focused.id != "providers-table"
        await pilot.press("escape")
        assert stack(app) == ["Screen"]
        await pilot.press("f5")
        await settle(pilot)
        assert performed == ["start"]
    run(t)


def test_delete_acts_on_environment_shown_in_confirmation(monkeypatch):
    c.create("ocs-qa-a", "scratch")
    c.create("ocs-qa-b", "scratch")
    deleted = []
    monkeypatch.setattr(c, "delete", lambda m, force=False: deleted.append(m["name"]))
    async def t(app, pilot):
        table = app.query_one("#envs")
        shown = app.selected()["name"]
        await pilot.press("x")
        assert shown in str(app.screen.query_one("Static").render())
        table.move_cursor(row=1 - table.cursor_row)  # e.g. a refresh moved the cursor
        assert app.selected()["name"] != shown
        await pilot.press("tab", "enter")
        await settle(pilot, 0.4)
        assert deleted == [shown]
    run(t)


def test_escape_closes_dialogs_without_action(monkeypatch):
    c.create("ocs-qa-esc", "scratch")
    performed = []
    monkeypatch.setattr(tui.Dashboard, "_run_operation", lambda self, a, m: performed.append(a))
    async def t(app, pilot):
        for key in ("x", "n", "t", "p", "g", "f8", "B"):
            await pilot.press(key)
            await pilot.pause()
            assert len(app.screen_stack) == 2, key
            await pilot.press("escape")
            await pilot.pause()
            assert stack(app) == ["Screen"], key
        assert performed == []
    run(t)


def test_docker_unavailable_reports_and_releases_busy_flag(monkeypatch):
    c.create("ocs-qa-down", "scratch")
    def down(*a, **k):
        raise c.SandboxError("Docker unavailable (test)")
    monkeypatch.setattr(c, "ensure_runtime", down)
    async def t(app, pilot):
        await pilot.press("f5")
        await settle(pilot, 0.4)
        assert "Docker unavailable" in str(app.query_one("#status").render())
        assert app._operation_pending is False
    run(t)


def test_busy_flag_blocks_duplicate_and_attach(monkeypatch):
    c.create("ocs-qa-busy", "scratch")
    performed, attached = [], []
    monkeypatch.setattr(tui.Dashboard, "_run_operation", lambda self, a, m: performed.append(a))
    monkeypatch.setattr(c, "interactive", lambda m, shell=False: attached.append(m))
    async def t(app, pilot):
        await pilot.press("f5")        # worker never finishes (fake): stays busy
        await pilot.press("f5", "s", "o", "x")
        await pilot.pause()
        assert performed == ["start"] and attached == []
        assert stack(app) == ["Screen"]
        assert any("Another operation" in n.message for n in app._notifications)
    run(t)


def test_confirm_dialog_buttons_are_normal_size():
    """The panel and the Confirm button shared id 'confirm': the panel CSS made the button 72 wide."""
    c.create("ocs-qa-dlg", "scratch")
    async def t(app, pilot):
        await pilot.press("x")
        await pilot.pause()
        cancel, confirm = app.screen.query_one("#cancel"), app.screen.query_one("#confirm")
        assert confirm.region.height == cancel.region.height and confirm.region.width < 40
        assert len(app.screen.query("#confirm")) == 1
        assert app.screen.query_one("#confirm-panel").region.height <= 12
    run(t, (80, 24))


def test_no_registry_call_until_requested(monkeypatch, fake_runtime):
    """G09: no background network call or update at startup; only on explicit request."""
    from opencode_sandbox import opencode_versions as v
    c.create("ocs-qa-g09", "scratch")
    looked_up = []
    monkeypatch.setattr(v, "latest", lambda timeout=8: looked_up.append(1) or "2.1.4")
    async def t(app, pilot):
        await settle(pilot, 0.5)
        assert looked_up == [] and not any(a[0] in ("exec", "run", "build") for a in fake_runtime)
        await pilot.press("v")
        await settle(pilot, 0.5)
        assert looked_up == [1] and type(app.screen).__name__ == "OpenCodeVersionsScreen"
        assert not any(a[0] in ("build", "commit") for a in fake_runtime)
    run(t)


def test_status_line_shows_backup_name_on_one_line(monkeypatch, tmp_path):
    """The status line is one row; a wrapped path showed only 'Backup:'."""
    import opencode_sandbox.backup as b
    c.create("ocs-qa-bk", "scratch")
    target = tmp_path / ("very-long-directory-name-" * 4) / "ocs-qa-bk-0123-20261022.ocsbackup"
    monkeypatch.setattr(b, "backup", lambda m, stop_running=False: target)
    async def t(app, pilot):
        await pilot.press("b")
        await settle(pilot, 0.4)
        line = str(app.query_one("#status").render())
        assert line.startswith("Backup saved: ocs-qa-bk-0123-20261022.ocsbackup")
        assert app.query_one("#status").region.height == 1
    run(t, (80, 24))


@pytest.mark.parametrize("key", ["p", "g", "f8", "B", "d", "n", "t"])
def test_subscreens_fit_80x24(key):
    """Providers clipped its buttons and Git review its Close button at 80x24."""
    c.create("ocs-qa-fit", "scratch")
    async def t(app, pilot):
        await pilot.press(key)
        await pilot.pause()
        assert len(app.screen_stack) == 2
        for b in app.screen.query(Button):
            r = b.region
            assert r.width > 0 and r.height > 0 and r.right <= 80 and r.bottom <= 24, (key, b.id, r)
            for parent in b.ancestors:
                if parent is app.screen or parent is app: break
                assert parent.region.contains_region(r), (key, b.id, r, parent)  # not clipped
    run(t, (80, 24))


def test_keep_quick_session_promotes_like_cli():
    """D08: quick sessions could be kept (promoted) only from the CLI."""
    q = c.create("quick-0a1b2c", "quick")
    c.create("ocs-qa-plain", "scratch")
    async def t(app, pilot):
        table = app.query_one("#envs")
        table.move_cursor(row=table.get_row_index(q["id"]))
        await pilot.press("k")
        await pilot.pause()
        assert stack(app) == ["Screen", "ConfirmScreen"]
        assert "quick-0a1b2c" in str(app.screen.query_one("Static").render())
        await pilot.press("escape")
        await settle(pilot)
        assert c.resolve(q["id"])["kind"] == "quick"
        await pilot.press("k")
        await pilot.press("tab", "enter")
        await settle(pilot, 0.4)
        kept = c.resolve(q["id"])
        assert (kept["kind"], kept["name"]) == ("scratch", f"scratch-{q['id'][:6]}")  # same as the CLI quick prompt
        assert "scratch-" in str(app.query_one("#envs").get_row(q["id"])[0])
        table.move_cursor(row=table.get_row_index(c.resolve("ocs-qa-plain")["id"]))
        await pilot.press("k")
        await pilot.pause()
        assert stack(app) == ["Screen"]
        assert any("Only quick" in n.message for n in app._notifications)
    run(t)


def test_dashboard_refreshes_after_external_cli_change(monkeypatch):
    """H08: changes made with the CLI while the dashboard is open appeared only after 'r'."""
    monkeypatch.setattr(tui.Dashboard, "AUTO_REFRESH_SECONDS", 0.1, raising=False)
    first = c.create("ocs-qa-ext1", "scratch")
    async def t(app, pilot):
        table = app.query_one("#envs")
        assert table.row_count == 1
        c.create("ocs-qa-ext2", "scratch")          # another process
        await settle(pilot, 0.5)
        assert table.row_count == 2
        table.move_cursor(row=table.get_row_index(first["id"]))
        rebuilds = []
        monkeypatch.setattr(table, "clear", lambda *a, **k: rebuilds.append(1) or type(table).clear(table, *a, **k))
        await settle(pilot, 0.5)
        assert rebuilds == []                        # unchanged metadata: no rebuild, cursor stays
        c.promote(c.resolve("ocs-qa-ext1"), "scratch", "ocs-qa-renamed")
        await settle(pilot, 0.5)
        assert rebuilds and app.selected()["name"] == "ocs-qa-renamed"
        app.push_screen(ProviderScreen())
        await pilot.pause()
        c.create("ocs-qa-ext3", "scratch")
        await settle(pilot, 0.5)                     # no crash while a sub-screen is open
        await pilot.press("escape")
        await settle(pilot, 0.5)
        assert table.row_count == 3
    run(t)


@pytest.mark.parametrize("observed", ["missing", "unreachable"])
def test_agent_context_preview(monkeypatch, observed):
    """The preview renders through guidance_inputs; Docker failures fall back to the configuration."""
    c.create("ocs-qa-acprev", "scratch")
    if observed == "unreachable":
        def fail(m):
            raise c.SandboxError("Docker is not reachable")
        monkeypatch.setattr(c, "observed_runtime", fail)

    async def t(app, pilot):
        await pilot.press("a")
        await settle(pilot)
        assert stack(app)[-1] == "OpenCodeVersionsScreen"
        report = app.screen.report
        assert "Agent context: ocs-qa-acprev" in report and "## Network and resources" in report
        assert "Networking mode: bridge" in report and "On-disk: missing/outdated" in report
    run(t)


def test_container_settings_show_the_plan_and_apply_it(monkeypatch):
    """The TUI uses the same planner/executor as `config apply`, including the provider."""
    from opencode_sandbox import config_plan as cp
    c.create("ocs-qa-cfg", "scratch")
    c.profile_set("work", {"QA_KEY": "dummy"})
    applied = []
    monkeypatch.setattr(cp, "apply", lambda m, changes, confirmed=None: applied.append((changes, confirmed))
                        or {"category": confirmed.category})

    async def t(app, pilot):
        await pilot.press("t")
        await pilot.pause()
        assert stack(app)[-1] == "RuntimeScreen"
        app.screen.query_one("#rt-pids").value = "700"
        app.screen.query_one("#rt-profile").value = "work"
        app.screen.query_one("#rt-save").press()
        await settle(pilot)
        assert stack(app)[-1] == "ConfirmScreen"
        text = str(app.screen.query_one("#confirm-panel Static").render())
        assert "process limit: 2048 -> 700  [saved" in text and "provider profile: default -> work" in text
        app.screen.query_one("#confirm").press()
        await settle(pilot, 0.5)
        changes, plan = applied[0]
        assert changes["pids"] == 700 and changes["profile"] == "work" and plan.category == "saved"
    run(t)


# Creation flow, bars and terms ---------------------------------------------------------

def _visible(app, selector, size):
    w, h = size
    r = app.screen.query_one(selector).region
    return r.width > 0 and r.height > 0 and r.right <= w and r.bottom <= h


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
def test_create_form_discloses_options_progressively(size):
    from opencode_sandbox import distros, integrations
    async def t(app, pilot):
        await pilot.press("n")
        await settle(pilot)
        assert stack(app)[-1] == "CreateScreen" and app.focused.id == "name"
        for sel in ("#name", "#kind", "#source", "#more", "#create", "#cancel"):
            assert _visible(app, sel, size), sel
        assert app.screen.query_one("#more").collapsed and not _visible(app, "#distro", size)
        app.screen.query_one("#more").collapsed = False
        await settle(pilot)
        for sel in ("#distro", "#workspace-mode", "#profile", *(f"#integration-{n}" for n in integrations.CATALOG), "#create"):
            assert _visible(app, sel, size), sel
        assert app.screen.query_one("#distro").value == distros.DEFAULT
        assert app.screen.query_one("#integration-context7").value is True
    run(t, size)


def test_create_form_uses_the_shared_rules_and_choices(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    (folder / "a.txt").write_text("x")
    c.profile_set("work", {"OPENROUTER_API_KEY": "test-only"})
    c.create("ocs-qa-older", "scratch")  # selected before the creation
    async def t(app, pilot):
        assert app.selected()["name"] == "ocs-qa-older"
        await pilot.press("n")
        await settle(pilot)
        form = app.screen
        form.query_one("#name").value = "ocs-qa-form"
        form.query_one("#source").value = str(folder)
        await settle(pilot)
        assert form.query_one("#kind").value == "project"  # a folder to copy makes a project, as in the CLI
        form.query_one("#kind").value = "scratch"
        form.query_one("#create").press()
        await settle(pilot)
        assert stack(app)[-1] == "CreateScreen" and "starts empty" in str(form.query_one("#create-error").render())
        form.query_one("#name").value = "bad name!"
        form.query_one("#kind").value = "project"
        form.query_one("#create").press()
        await settle(pilot)
        assert stack(app)[-1] == "CreateScreen" and "name" in str(form.query_one("#create-error").render()).lower()
        form.query_one("#name").value = "ocs-qa-form"
        form.query_one("#more").collapsed = False
        form.query_one("#distro").value = "arch"
        form.query_one("#profile").value = "work"
        form.query_one("#integration-context7").value = False
        await settle(pilot)
        form.query_one("#create").press()
        await settle(pilot, 1.0)
        m = c.resolve("ocs-qa-form")
        assert app.selected()["id"] == m["id"]  # The new environment is selected
        assert (m["kind"], m["distro"], m["profile"], m["provisioning"]["requested"]) == ("project", "arch", "work", [])
        assert m["source"] == str(folder.resolve())
        details = str(app.query_one("#details").render())
        for text in ("Distribution: Arch Linux (OS version not inspected)", "Provider profile: work", f"managed copy of {folder.resolve()}",
                     "Settings: ", "network bridge", "Readiness: "):
            assert text in details, text
    run(t, (120, 40))


def test_bars_separate_global_and_environment_actions_with_cli_terms():
    async def t(app, pilot):
        top = [str(b.label) for b in app.query_one("#toolbar").query(Button)]
        bottom = [str(b.label) for b in app.query_one("#actions").query(Button)]
        assert top == ["New", "This folder", "Backups", "Providers", "Preferences", "Versions", "Recovery", "Disk"]
        assert bottom == ["OpenCode", "Shell", "Start", "Stop", "Check", "Settings", "Usage", "Agent context",
                          "Changes", "Export", "Backup", "Repair", "Promote", "Delete"]
        descriptions = {b.key: b.description for b in app.BINDINGS}
        assert descriptions["t"] == "Settings" and descriptions["d"] == "Changes" and descriptions["g"] == "Preferences"
    run(t, (80, 24))


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
def test_details_fit_the_pane(size, tmp_path):
    source = tmp_path / ("long-folder-name-" * 4) / "project"
    source.mkdir(parents=True)
    (source / "a.txt").write_text("x")
    m = c.create("ocs-qa-" + "n" * 56, "project", source)  # longest name, long path
    m["last_error"] = "Start failed: " + "x" * 200
    c.save(m)
    async def t(app, pilot):
        details = app.query_one("#details")
        lines = str(details.render()).splitlines()
        assert len(lines) <= details.content_region.height, lines
        assert lines[-1].startswith("Error: Start failed")
        # Long values end in an ellipsis instead of wrapping the error line out of the pane (real
        # 80x24 terminal): rendered rows == lines.
        rendered = [details.render_line(y).text for y in range(details.region.height)]
        assert any("Error: Start failed" in row for row in rendered), rendered
    run(t, size)


def test_recovery_center_names_the_finishing_command():
    from opencode_sandbox.management_tui import RecoveryScreen
    m = c.create("ocs-qa-rec", "scratch")
    c.mark(m, "error", operation="recreate")
    async def t(app, pilot):
        app.push_screen(RecoveryScreen())
        await settle(pilot)
        table = app.screen.query_one("#recovery-table")
        row = [str(cell) for cell in table.get_row_at(0)]  # Text cells
        assert "opencode-sandbox container recreate-recover ocs-qa-rec" in row
    run(t, (120, 40))


def test_settings_fields_are_labelled_at_80x24():
    """The placeholders were the only labels and disappeared once a value was filled in."""
    c.create("ocs-qa-settings", "scratch")
    async def t(app, pilot):
        await pilot.press("t")
        await settle(pilot)
        assert stack(app)[-1] == "RuntimeScreen"
        labels = [str(s.render()) for s in app.screen.query(".field > Static")]
        assert labels == ["CPUs (--cpus)", "Memory (--memory)", "Processes (--pids)", "Network", "Ports (--publish)",
                          "Provider profile"]
        for sel in ("#rt-cpus", "#rt-memory", "#rt-pids", "#rt-network", "#rt-ports", "#rt-profile", "#rt-save", "#rt-cancel"):
            assert _visible(app, sel, (80, 24)), sel
        network = app.screen.query_one("#rt-network")
        label = network.query("SelectCurrent > Static").first()
        assert network.region.height == 1 and label.region.width >= len("bridge: internet + LAN")  # not cut by the label style
    run(t, (80, 24))
