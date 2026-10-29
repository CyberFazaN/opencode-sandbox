"""Provider, recovery and UI preferences screens. Never reveal credential values."""
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Input, Static

from . import core as c
from . import preferences


class ProviderScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close")]
    # Compact inputs/buttons: at 80x24 the table had no rows and the buttons were clipped.
    CSS = "ProviderScreen {align: center middle;} #providers-panel {width: 90%; height: 90%; border: round $accent; padding: 0 1;} #providers-table {height: 1fr; min-height: 3;} #providers-panel Input {margin-bottom: 1;} #providers-panel Horizontal {height: auto;} #providers-panel Button {margin-right: 1;}"
    def compose(self) -> ComposeResult:
        with Vertical(id="providers-panel"):
            yield Static("Provider profiles — credential values are never displayed")
            yield DataTable(id="providers-table", cursor_type="row")
            yield Input(placeholder="Profile name for a new credential", id="profile-name", compact=True)
            yield Input(placeholder="Credential variable (e.g. ANTHROPIC_API_KEY)", id="profile-key", compact=True)
            yield Input(placeholder="Credential value", password=True, id="profile-value", compact=True)
            with Horizontal():
                yield Button("Save credential", id="save-profile", compact=True)
                yield Button("Refresh", id="refresh-profiles", compact=True)
                yield Button("Close", id="close-profiles", compact=True)
            yield Static("Choose an environment's profile in its Settings (t). Key changes reach a container after a restart.", id="profile-status")
    def on_mount(self):
        self.query_one("#providers-table", DataTable).add_columns("Profile", "Variable names (not values)")
        self.refresh_profiles()
    def refresh_profiles(self):
        table = self.query_one("#providers-table", DataTable)
        table.clear()
        for name in sorted(c.profile_list()):
            table.add_row(name, ", ".join(c.profile_keys(name)), key=name)
    def on_button_pressed(self, event: Button.Pressed):
        action = event.button.id
        if action == "close-profiles": self.app.pop_screen(); return
        if action == "refresh-profiles": self.refresh_profiles(); return
        name = self.query_one("#profile-name", Input).value.strip()
        if not name:
            table = self.query_one("#providers-table", DataTable)
            if table.row_count:
                name = str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        if not name:
            self.notify("Select or enter a profile", severity="warning"); return
        if action == "save-profile":
            key = self.query_one("#profile-key", Input).value.strip()
            value = self.query_one("#profile-value", Input).value
            self.save_profile(name, key, value)
    @work(thread=True, exclusive=True, group="provider-work")
    def save_profile(self, name, key, value):
        try:
            # Preserve existing keys, never read/display existing secret values in the UI.
            if c.profile_path(name).exists():
                raise c.SandboxError("Existing profile: use CLI providers set to update without dropping other keys")
            c.profile_set(name, {key: value})
            self.app.call_from_thread(self._saved)
        except Exception as exc: self.app.call_from_thread(self.notify, c.error_text(exc), severity="error")
    def _saved(self):
        self.query_one("#profile-value", Input).value = ""
        self.refresh_profiles()
        self.notify("Profile saved")

class SettingsScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close")]
    CSS = "SettingsScreen {align: center middle;} #settings-panel {width: 75; height: auto; border: round $accent; padding: 2;}"
    def compose(self) -> ComposeResult:
        with Vertical(id="settings-panel"):
            yield Static("Preferences of the dashboard (an environment's limits, network and profile: Settings, t)")
            yield Checkbox("Confirm before stopping", id="confirm-stop")
            yield Checkbox("Show quick environments", id="show-quick")
            yield Checkbox("Refresh after terminal session", id="refresh-return")
            with Horizontal():
                yield Button("Save", id="save-settings", variant="primary")
                yield Button("Cancel", id="cancel-settings")
    def on_mount(self):
        try: data = preferences.read()
        except Exception as exc:
            self.notify(c.error_text(exc), severity="error"); data = dict(preferences.DEFAULTS)
        for key, widget in (("confirm_stop", "confirm-stop"), ("show_quick", "show-quick"), ("refresh_on_return", "refresh-return")):
            self.query_one("#" + widget, Checkbox).value = data[key]
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel-settings": self.app.pop_screen(); return
        if event.button.id == "save-settings":
            try:
                preferences.write({"confirm_stop": self.query_one("#confirm-stop", Checkbox).value,
                                   "show_quick": self.query_one("#show-quick", Checkbox).value,
                                   "refresh_on_return": self.query_one("#refresh-return", Checkbox).value})
                self.app.pop_screen()
                self.app.action_refresh()
            except Exception as exc: self.notify(c.error_text(exc), severity="error")

class RecoveryScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close")]
    CSS = "RecoveryScreen {align: center middle;} #recovery-panel {width: 90%; height: 80%; border: round $warning; padding: 1 2;} #recovery-table {height: 1fr;}"
    def compose(self) -> ComposeResult:
        with Vertical(id="recovery-panel"):
            yield Static("Recovery Center — review interrupted operations before repair")
            yield DataTable(id="recovery-table", cursor_type="row")
            with Horizontal():
                yield Button("Repair selected", id="repair-recovery")
                yield Button("Recover change", id="runtime-recovery")
                yield Button("Refresh", id="refresh-recovery")
                yield Button("Close", id="close-recovery")
            yield Static("Repair does not automatically delete workspace or volumes. Recover change finishes an "
                         "interrupted settings change; other operations: run the command in 'Next step' in a terminal.")
    def on_mount(self):
        self.query_one("#recovery-table", DataTable).add_columns("Name", "State", "Operation", "Next step", "Last error", "ID")
        self.refresh_entries()
    def refresh_entries(self):
        table = self.query_one("#recovery-table", DataTable); table.clear()
        from .readiness import RECOVERY
        for m in c.pending_repairs():
            step = RECOVERY.get(m.get("operation") or "", "opencode-sandbox repair {name}").format(name=m["name"])
            # Text cells: a str cell is parsed as markup, and errors carry file names.
            table.add_row(*(Text(str(v)) for v in (m["name"], m.get("status", "?"), m.get("operation") or "—", step,
                                                   str(m.get("last_error") or "—")[:90], m["id"])), key=m["id"])
    def on_button_pressed(self, event: Button.Pressed):
        action = event.button.id
        if action == "close-recovery": self.app.pop_screen()
        elif action == "refresh-recovery": self.refresh_entries()
        elif action == "runtime-recovery":
            table = self.query_one("#recovery-table", DataTable)
            if table.row_count:
                eid = str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
                try:
                    m = c.resolve(eid)
                    if m.get("operation") not in ("runtime-recreate", "config-update"):
                        self.notify("Selected environment has no interrupted configuration change", severity="warning"); return
                    from .tui import ConfirmScreen
                    text = (f"Recover interrupted container recreation for {m['name']}?\nA stopped old container may be removed after checking its ownership. Workspace and home volume remain."
                            if m["operation"] == "runtime-recreate" else
                            f"Finish the interrupted limit change for {m['name']}?\nThe saved limits are applied again with docker update.")
                    self.app.push_screen(ConfirmScreen(text), lambda yes: self.recover_runtime(eid) if yes else None)
                except Exception as exc: self.notify(c.error_text(exc), severity="error")
        elif action == "repair-recovery":
            table = self.query_one("#recovery-table", DataTable)
            if table.row_count:
                self.repair_selected(str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value))
    @work(thread=True, exclusive=True, group="recovery-work")
    def repair_selected(self, eid):
        try:
            result = c.repair(c.resolve(eid))
            self.app.call_from_thread(self.notify, str(result))
            self.app.call_from_thread(self.refresh_entries)
        except Exception as exc: self.app.call_from_thread(self.notify, c.error_text(exc), severity="error")

    @work(thread=True, exclusive=True, group="recovery-work")
    def recover_runtime(self, eid):
        try:
            from .config_plan import recover
            result = recover(c.resolve(eid))
            self.app.call_from_thread(self.notify, f"Recovered: {result}")
            self.app.call_from_thread(self.refresh_entries)
            self.app.call_from_thread(self.app.action_refresh)
        except Exception as exc:
            self.app.call_from_thread(self.notify, c.error_text(exc), severity="error")
