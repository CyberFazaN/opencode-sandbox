"""Text from environments, backups and errors is shown as plain
text in the dashboard (square brackets are content, not Textual markup), and the dashboard's own
messages name dashboard keys, not CLI options."""
import json

from test_tui import run, settle, stack

from opencode_sandbox import backup as b
from opencode_sandbox import core as c
from opencode_sandbox.backup_tui import BackupScreen
from opencode_sandbox.management_tui import RecoveryScreen

BRACKETS = "file [/b] and [b]x[/b] and [@click=app.quit]here[/]"


def _cells(table, row=0):
    return [str(cell) for cell in table.get_row_at(row)]


def test_recovery_center_shows_an_error_with_brackets_as_text():
    m = c.create("ocs-qa-rec", "scratch")
    c.mark(m, "error", operation="recreate", last_error=f"Recreation start failed: {BRACKETS}")

    async def t(app, pilot):
        app.push_screen(RecoveryScreen())
        await settle(pilot)
        assert stack(app)[-1] == "RecoveryScreen"
        assert any(BRACKETS[:40] in cell for cell in _cells(app.screen.query_one("#recovery-table")))
    run(t, (120, 40))


def test_recovery_center_names_the_terminal_for_other_operations():
    async def t(app, pilot):
        app.push_screen(RecoveryScreen())
        await settle(pilot)
        texts = " ".join(str(s.render()) for s in app.screen.query("Static"))
        assert "in a terminal" in texts
    run(t, (120, 40))


def test_backups_screen_lists_a_backup_whose_recorded_name_has_brackets():
    """The name comes from the backup's manifest (a backup may come from another machine)."""
    root = c.BASE / "backups" / "x.ocsbackup"
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({
        "format": "opencode-sandbox-backup", "schema": b.SCHEMA, "created": "2026-10-28T00:00:00+00:00",
        "environment": {"name": BRACKETS}, "files": {}, "workspace": {"mode": "direct", "included": False}}))

    async def t(app, pilot):
        app.push_screen(BackupScreen())
        await settle(pilot)
        assert stack(app)[-1] == "BackupScreen"
        assert _cells(app.screen.query_one("#backup-table"))[0] == BRACKETS
    run(t, (120, 40))


def test_dashboard_status_line_and_notifications_are_plain_text():
    async def t(app, pilot):
        app._set_busy(BRACKETS)
        app.notify(BRACKETS, severity="error")
        await settle(pilot)
        assert str(app.query_one("#status").render()) == BRACKETS
        assert app._notifications and all(not n.markup for n in app._notifications)
    run(t)


def test_dashboard_backup_of_a_running_environment_names_the_dashboard_key(monkeypatch):
    m = c.create("ocs-qa-bk", "scratch")
    monkeypatch.setattr(c, "inspect_container", lambda env: {"Running": True})

    async def t(app, pilot):
        app._perform("backup", c.resolve(m["id"]))
        await settle(pilot, 0.5)
        messages = [n.message for n in app._notifications]
        assert any("Stop it first (F6)" in text for text in messages), messages
        assert not any("--stop" in text for text in messages), messages
    run(t)
