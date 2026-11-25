"""Backup browser for the Textual dashboard; operations run off the UI thread."""
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ItemGrid, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Static

from . import core as c
from .backup import backup_info, list_backups, restore, verify
from .tui_runtime import work


class BackupScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close")]
    CSS = """
    BackupScreen { align: center middle; }
    #backup-panel { width: 95%; height: 85%; border: round $accent; padding: 1 2; }
    #backup-table { height: 1fr; }
    #backup-status { height: auto; }
    #restore-name { width: 1fr; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="backup-panel", classes="dialog-fields"):
            yield Static("Backup & Restore", classes="form-title")
            yield DataTable(id="backup-table", cursor_type="row")
            yield Static("New environment name for restore")
            yield Input(id="restore-name", compact=True)
            with ItemGrid(classes="dialog-grid dialog-actions", min_column_width=16):
                yield Button("Verify", id="verify", compact=True)
                yield Button("Restore as new", id="restore", compact=True)
                yield Button("Refresh", id="refresh-backups", compact=True)
                yield Button("Close", id="close-backups", compact=True)
            yield Static("Verification and restore run asynchronously.", id="backup-status")

    def on_mount(self) -> None:
        self.query_one('#backup-table', DataTable).add_columns('Environment', 'Created', 'Size (MiB)', 'Archive')
        self.refresh_entries()

    def refresh_entries(self) -> None:
        table = self.query_one('#backup-table', DataTable)
        table.clear()
        for path in list_backups():
            try:
                info = backup_info(path)
                # Text cells: a str cell is parsed as markup; names come from the manifest.
                table.add_row(*(Text(str(v)) for v in (info['name'], info['created'], f"{info['bytes']/1048576:.1f}", path.name)),
                              key=str(path))
            except (c.SandboxError, OSError):  # what verify reports for an invalid backup, like backup prune
                table.add_row(*(Text(v) for v in ('INVALID', '?', '?', path.name)), key=str(path))

    def selected_path(self) -> Path | None:
        table = self.query_one('#backup-table', DataTable)
        if not table.row_count:
            return None
        return Path(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action == 'close-backups':
            self.app.pop_screen()
        elif action == 'refresh-backups':
            self.refresh_entries()
        elif action in ('verify', 'restore'):
            path = self.selected_path()
            if path is None:
                self.notify('Select a backup first', severity='warning')
                return
            if action == 'verify':
                self.verify_selected(path)
            else:
                name = self.query_one('#restore-name', Input).value.strip()
                if not name:
                    self.notify('Enter a NEW environment name', severity='warning')
                    return
                self.restore_selected(path, name)

    @work(thread=True, exclusive=True)
    def verify_selected(self, path: Path) -> None:
        try:
            manifest = verify(path)
            self.app.call_from_thread(self.notify, f"Verified: {manifest['created']}", timeout=8)
        except Exception as exc:
            self.app.call_from_thread(self.notify, c.error_text(exc), severity='error', timeout=12)

    @work(thread=True, exclusive=True)
    def restore_selected(self, path: Path, name: str) -> None:
        try:
            result = restore(path, name)
            self.app.call_from_thread(self.notify, f"Restored {result['name']} — smoke-test it with: opencode-sandbox backup restore-check {result['name']}", timeout=12)
            self.app.call_from_thread(self.refresh_entries)
        except Exception as exc:
            self.app.call_from_thread(self.notify, c.error_text(exc), severity='error', timeout=12)
