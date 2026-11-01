"""Provider, recovery and UI preferences screens. Never reveal credential values."""
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Input, Static, TextArea

from . import core as c
from . import preferences
from .tui_runtime import admission, publish, work


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
    CSS = "SettingsScreen {align: center middle;} #settings-panel {width: 75; max-width: 100%; height: auto; max-height: 100%; border: round $accent; padding: 0 1;} #settings-panel Horizontal {height: auto;} #settings-panel Button {height: 3;}"
    def compose(self) -> ComposeResult:
        with Vertical(id="settings-panel"):
            yield Static("Preferences of the dashboard (an environment's limits, network and profile: Settings, t)")
            yield Checkbox("Confirm before stopping", id="confirm-stop")
            yield Checkbox("Show quick environments", id="show-quick")
            yield Checkbox("Refresh after terminal session", id="refresh-return")
            yield Checkbox("Daily metadata discovery (dashboard only)", id="daily-discovery")
            yield Static("Default off. GitHub + npm; one automatic attempt/source/24h.\nNo start, version probe or installation.", markup=False)
            with Horizontal():
                yield Button("Save", id="save-settings", variant="primary")
                yield Button("Cancel", id="cancel-settings")
    def on_mount(self):
        try: data = preferences.read()
        except Exception as exc:
            self.notify(c.error_text(exc), severity="error"); data = dict(preferences.DEFAULTS)
        for key, widget in (("confirm_stop", "confirm-stop"), ("show_quick", "show-quick"),
                            ("refresh_on_return", "refresh-return"), ("daily_discovery", "daily-discovery")):
            self.query_one("#" + widget, Checkbox).value = data[key]
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel-settings": self.app.pop_screen(); return
        if event.button.id == "save-settings":
            try:
                preferences.write({"confirm_stop": self.query_one("#confirm-stop", Checkbox).value,
                                   "show_quick": self.query_one("#show-quick", Checkbox).value,
                                   "refresh_on_return": self.query_one("#refresh-return", Checkbox).value,
                                   "daily_discovery": self.query_one("#daily-discovery", Checkbox).value})
                self.app.pop_screen()
                self.app.action_refresh()
                self.app.refresh_discovery_preferences()
            except Exception as exc: self.notify(c.error_text(exc), severity="error")

class RecoveryScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close")]
    CSS = "RecoveryScreen {align: center middle;} RecoveryScreen ToastRack {height: 0; max-height: 0; overflow: hidden;} #recovery-panel {width: 90%; height: 80%; border: round $warning; padding: 0 1;} #recovery-table {height: 1fr; min-height: 3;} #recovery-result {height: 5;} #recovery-panel Horizontal {height: auto;} #recovery-panel Button {min-width: 10; width: 1fr;}"

    def __init__(self, *, environment_id=None):
        super().__init__()
        self.environment_id = environment_id
        self._alive = False
        self._preparing = False
        self._review_worker = None

    def compose(self) -> ComposeResult:
        with Vertical(id="recovery-panel"):
            yield Static("Recovery Center — review interrupted operations before repair")
            yield DataTable(id="recovery-table", cursor_type="row")
            with Horizontal():
                yield Button("Repair selected", id="repair-recovery")
                yield Button("Recover selected", id="runtime-recovery")
                yield Button("Refresh", id="refresh-recovery")
                yield Button("Close", id="close-recovery")
            yield TextArea("Repair does not automatically delete workspace or volumes. Recover selected finishes an "
                          "interrupted settings change or reviews checkpoint recovery for OpenCode; other operations: "
                          "run the command in 'Next step' in a terminal.", id="recovery-result", read_only=True)
    def on_mount(self):
        self._alive = True
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
            if m["id"] == self.environment_id: table.move_cursor(row=table.row_count - 1)

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
                    self.app.push_screen(ConfirmScreen(text), lambda yes: self._begin_runtime_recovery(eid, expected) if yes else None)
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
