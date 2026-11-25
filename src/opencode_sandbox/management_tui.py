"""Provider, recovery and UI preferences screens. Never reveal credential values."""
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ItemGrid, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Input, Static, TextArea

from . import core as c
from . import preferences
from .tui_runtime import admission, publish, work
from .tui_widgets import FormBody, FormCheckbox


class ProviderScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close")]
    # Compact inputs/buttons: at 80x24 the table had no rows and the buttons were clipped.
    CSS = """
    ProviderScreen {align: center middle;}
    #providers-panel {width: 90%; height: 90%; border: round $accent; padding: 0 1;}
    #providers-table {height: 1fr; min-height: 3;}
    """
    def compose(self) -> ComposeResult:
        with Vertical(id="providers-panel", classes="dialog-fields"):
            yield Static("Provider profiles", classes="form-title")
            yield DataTable(id="providers-table", cursor_type="row")
            yield Static("New profile name")
            yield Input(id="profile-name", compact=True)
            yield Static("Credential variable")
            yield Input(placeholder="e.g. ANTHROPIC_API_KEY", id="profile-key", compact=True)
            yield Static("Credential value")
            yield Input(password=True, id="profile-value", compact=True)
            with ItemGrid(classes="dialog-grid dialog-actions", min_column_width=16):
                yield Button("Save profile", id="save-profile", variant="primary", compact=True)
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
            try: detail = ", ".join(c.profile_keys(name))
            except (c.SandboxError, OSError) as exc: detail = "Invalid profile: " + c.error_text(exc)
            table.add_row(Text(c.printable(name)), Text(c.printable(detail)), key=name)
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
    CSS = "SettingsScreen {align: center middle;} #settings-panel {width: 75; max-width: 100%; height: auto; max-height: 100%; border: round $accent; padding: 0 1;} #settings-panel Horizontal {height: auto;} #settings-panel FormBody {max-height: 65vh;}"
    def compose(self) -> ComposeResult:
        with Vertical(id="settings-panel", classes="dialog-fields"):
            yield Static("Preferences", classes="form-title", markup=False)
            yield Static("Tab: next option · Space: toggle · Esc: cancel", classes="form-hint", markup=False)
            with FormBody():
                yield FormCheckbox("Confirm before stopping", id="confirm-stop", compact=True)
                yield FormCheckbox("Show quick environments", id="show-quick", compact=True)
                yield FormCheckbox("Refresh after terminal session", id="refresh-return", compact=True)
                yield FormCheckbox("Daily metadata discovery (dashboard only)", id="daily-discovery", compact=True)
                yield FormCheckbox("Copy selected text", id="copy-selected-text", compact=True)
                yield FormCheckbox("Allow rootful Docker environments", id="allow-rootful", compact=True)
            with Horizontal(classes="dialog-actions"):
                yield Button("Save", id="save-settings", variant="primary", compact=True)
                yield Button("Cancel", id="cancel-settings", compact=True)
    def on_mount(self):
        try: data = preferences.read()
        except Exception as exc:
            self.notify(c.error_text(exc), severity="error"); data = dict(preferences.DEFAULTS)
        for key, widget in (("confirm_stop", "confirm-stop"), ("show_quick", "show-quick"),
                            ("refresh_on_return", "refresh-return"), ("daily_discovery", "daily-discovery"),
                            ("copy_selected_text", "copy-selected-text"), ("allow_rootful", "allow-rootful")):
            self.query_one("#" + widget, Checkbox).value = data[key]
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel-settings": self.app.pop_screen(); return
        if event.button.id == "save-settings":
            try:
                preferences.write({"confirm_stop": self.query_one("#confirm-stop", Checkbox).value,
                                   "show_quick": self.query_one("#show-quick", Checkbox).value,
                                   "refresh_on_return": self.query_one("#refresh-return", Checkbox).value,
                                   "daily_discovery": self.query_one("#daily-discovery", Checkbox).value,
                                   "copy_selected_text": self.query_one("#copy-selected-text", Checkbox).value,
                                   "allow_rootful": self.query_one("#allow-rootful", Checkbox).value})
                self.app.pop_screen()
                self.app.refresh_docker_preferences()
                self.app.refresh_discovery_preferences()
                self.app.refresh_clipboard_preferences()
            except Exception as exc: self.notify(c.error_text(exc), severity="error")

class RecoveryScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close")]
    CSS = """
    RecoveryScreen {align: center middle;}
    RecoveryScreen ToastRack {height: 0; max-height: 0; overflow: hidden;}
    #recovery-panel {width: 90%; height: 95%; border: round $warning; padding: 0 1;}
    #recovery-table {height: 1fr; min-height: 3;}
    #recovery-detail {height: 4; display: none;}
    #recovery-result {height: 4;}
    #recovery-panel Button {min-width: 10;}
    """

    def __init__(self, *, environment_id=None):
        super().__init__()
        self.environment_id = environment_id
        self._alive = False
        self._preparing = False
        self._review_worker = None
        self._entries = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="recovery-panel"):
            yield Static("Recovery Center", classes="form-title")
            yield DataTable(id="recovery-table", cursor_type="row")
            with ItemGrid(classes="dialog-grid", min_column_width=15):
                yield Button("Repair", id="repair-recovery", compact=True)
                yield Button("Recover", id="runtime-recovery", compact=True)
                yield Button("Refresh", id="refresh-recovery", compact=True)
                yield Button("Close", id="close-recovery", compact=True)
            yield TextArea("", id="recovery-detail", read_only=True)
            yield TextArea("Repair does not automatically delete workspace or volumes. Recover finishes an "
                          "interrupted settings change or reviews checkpoint recovery for OpenCode; other operations: "
                          "run the command in 'Next step' in a terminal.", id="recovery-result", read_only=True)
    def on_mount(self):
        self._alive = True
        self.query_one("#recovery-table", DataTable).add_columns("Name", "State", "Operation")
        self.refresh_entries()
    def refresh_entries(self):
        table = self.query_one("#recovery-table", DataTable)
        if table.row_count:
            selected = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        else:
            selected = self.environment_id
        table.clear()
        self._entries = {m["id"]: m for m in c.pending_repairs()}
        for eid, m in self._entries.items():
            table.add_row(*(Text(c.printable(str(value))) for value in
                            (m["name"], m.get("status", "?"), m.get("operation") or "—")), key=eid)
            if eid == selected:
                table.move_cursor(row=table.row_count - 1)
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value if table.row_count else None
        self._show_entry(key)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        event.stop()
        self._show_entry(event.row_key.value)

    def _show_entry(self, key):
        from .readiness import RECOVERY
        detail = self.query_one("#recovery-detail", TextArea)
        entry = self._entries.get(key)
        detail.display = entry is not None
        if entry is None:
            return
        command = RECOVERY.get(entry.get("operation") or "", "opencode-sandbox repair {name}")
        detail.load_text(c.printable(
            f"Next step: {command.format(name=entry['name'])}\n"
            f"Last error: {entry.get('last_error') or '—'}\n"
            f"Environment ID: {entry['id']}"
        ))

    def on_unmount(self):
        self._alive = False
        if self._review_worker: self._review_worker.cancel()

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
                    if self.app._operation_pending or self._preparing:
                        self._recovery_notice("Another operation or recovery review is running", severity="warning"); return
                    if m.get("operation") == "opencode-update":
                        self._preparing = True
                        self._review_worker = self.prepare_opencode_recovery(eid)
                        return
                    if m.get("operation") not in ("runtime-recreate", "config-update"):
                        self._recovery_notice(str(c.pending_operation(m)) if m.get("operation") else "Selected environment has no interrupted configuration change", severity="warning"); return
                    from . import opencode_versions as v
                    from .tui import ConfirmScreen
                    expected = (v._consent_metadata(m), c.data_id())
                    text = (f"Recover interrupted container recreation for {m['name']}?\nA stopped old container may be removed after checking its ownership. Workspace and home volume remain."
                            if m["operation"] == "runtime-recreate" else
                            f"Finish the interrupted limit change for {m['name']}?\nThe saved limits are applied again with docker update.")
                    self.app.push_screen(
                        ConfirmScreen(text, title="Review recovery", action_label="Recover", destructive=False),
                        lambda yes: self._begin_runtime_recovery(eid, expected) if yes else None,
                    )
                except Exception as exc: self._recovery_notice(c.error_text(exc), severity="error")
        elif action == "repair-recovery":
            if self.app._operation_pending: return
            table = self.query_one("#recovery-table", DataTable)
            if table.row_count:
                self.repair_selected(str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value))

    @work(thread=True, group="recovery-review")
    def prepare_opencode_recovery(self, eid):
        from . import opencode_versions as v
        try:
            m = c.resolve(eid)
            plan = v.prepare_checkpoint_action(m, "recover")
            m = c.resolve(eid)
            if v._consent_metadata(m) != plan.metadata:
                raise c.SandboxError("Environment changed while preparing consent; review again")
            publish(self.app, self._opencode_recovery_prepared, m, plan, None)
        except Exception as exc:
            publish(self.app, self._opencode_recovery_prepared, None, None, c.error_text(exc))

    def _opencode_recovery_prepared(self, m, plan, error):
        from .environment_updates_tui import EnvironmentConsentScreen, consent
        if not self._alive: return
        self._preparing = False
        if self.app.screen is not self:
            self.query_one("#recovery-result", TextArea).load_text("Recovery review ended while another screen was open; request it again.")
            return
        if error:
            self.query_one("#recovery-result", TextArea).load_text(error)
            return
        self.app.push_screen(EnvironmentConsentScreen(consent(m, "recover", plan)),
                             lambda yes: self.app.run_environment_update_action(m, "recover", plan, self._opencode_recovered) if yes and self._alive else None)

    def _opencode_recovered(self, key, result, failed):
        if not self._alive: return
        self.query_one("#recovery-result", TextArea).load_text(result)
        self.refresh_entries()

    def _recovery_notice(self, message, *, severity="information"):
        if not self._alive: return
        self.query_one("#recovery-result", TextArea).load_text(c.printable(message))
        self.notify(message, severity=severity)

    def _begin_runtime_recovery(self, eid, expected):
        if self.app._operation_pending or not self._alive: return
        self.app._operation_pending = self.app._updates_mutation_active = True
        self.app._set_busy("Recovering configuration change…")
        # App-owned worker, not canceled/replaced when this screen is closed.
        def recover():
            with admission(self.app) as admitted:
                if admitted: self._recover_runtime(eid, expected)
        self.app.run_worker(recover, thread=True, group="environment-operation")

    def _recover_runtime(self, eid, expected):
        with c.runtime_feedback(progress=None, cancelled=None):
            try:
                from . import opencode_versions as v
                from .config_plan import recover
                def recheck(m):
                    if (v._consent_metadata(m), c.data_id()) != expected:
                        raise c.SandboxError("Recovery journal changed since confirmation; review again")
                result = recover(c.resolve(eid), precondition=recheck)
                message, failed = f"Recovered: {result}", False
            except Exception as exc:
                message, failed = c.error_text(exc), True
        if self.app.is_running:
            self.app.call_from_thread(self.app._environment_update_finished, eid, message, failed, self._opencode_recovered)

    @work(thread=True, exclusive=True, group="recovery-work")
    def repair_selected(self, eid):
        try:
            result = c.repair(c.resolve(eid))
            self.app.call_from_thread(self._recovery_notice, str(result))
            self.app.call_from_thread(self.refresh_entries)
        except Exception as exc: self.app.call_from_thread(self._recovery_notice, c.error_text(exc), severity="error")
