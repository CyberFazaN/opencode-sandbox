"""File-transfer UX for the shared global OpenCode config service; never an embedded editor."""
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Select, Static, TextArea

from . import core as c
from . import opencode_configs as oc
from .tui_runtime import admission, publish, work


class ConfigProfilesScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close")]
    CSS = "ConfigProfilesScreen {align: center middle;} #oc-profiles {width: 90%; height: 85%; border: round $accent; padding: 0 1;} #oc-profiles-text {height: 1fr;} #oc-profiles Horizontal {height: auto;}"

    def compose(self):
        with Vertical(id="oc-profiles"):
            yield Static("OpenCode Configs — maintained by you, outside this application", markup=False)
            yield TextArea("", id="oc-profiles-text", read_only=True)
            with Horizontal():
                yield Button("Refresh", id="oc-profiles-refresh", compact=True)
                yield Button("Close", id="oc-profiles-close", compact=True)

    def on_mount(self): self.refresh_profiles()

    def refresh_profiles(self):
        try:
            names = oc.profiles()
            text = (f"Directory: {oc.profiles_directory()}\n\n"
                    "Place named configuration directories here, or a root symlink, for example:\n"
                    f"  mkdir -p {oc.profiles_directory()}\n"
                    f"  ln -s ~/my-opencode-config {oc.profiles_directory()}/work\n\n"
                    "The manager only reads sources. Copy/Reload imports the entire directory once; "
                    "no live links or synchronization. Internal symlinks retain their link text. "
                    "Profiles may contain secrets and executable plugins.\n\n"
                    + ("Available profiles:\n" + "\n".join(names) if names else "No profiles yet. Local creation remains available."))
        except Exception as exc: text = c.error_text(exc)
        self.query_one("#oc-profiles-text", TextArea).load_text(c.printable(text))

    def on_button_pressed(self, event):
        event.stop()
        if event.button.id == "oc-profiles-close": self.app.pop_screen()
        else: self.refresh_profiles()


class DriftScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]
    AUTO_FOCUS = "#oc-drift-cancel"
    CSS = "DriftScreen {align: center middle;} #oc-drift {width: 70; max-width: 100%; height: auto; border: round $warning; background: $surface; padding: 1;} #oc-drift Horizontal {height: auto;}"

    def compose(self):
        with Vertical(id="oc-drift"):
            yield Static("Container config changed since the last Export/Apply. Cancel preserves both trees and the baseline. "
                         "Overwrite Anyway replaces the newer container tree with your export; it never merges.", markup=False)
            with Horizontal():
                yield Button("Cancel", id="oc-drift-cancel")
                yield Button("Overwrite Anyway", id="oc-drift-overwrite", variant="error")

    def action_cancel(self): self.dismiss(False)
    def on_button_pressed(self, event):
        event.stop()
        self.dismiss(event.button.id == "oc-drift-overwrite")


def run_transfer(screen, action, *, source=None, overwrite=None, replace=False):
    """App-owned mutation survives screen closure, retaining normal operation admission."""
    app = screen.app
    if app._operation_pending:
        screen.notify("Another operation is running", severity="warning")
        return
    app._operation_pending = app._updates_mutation_active = True
    app._set_busy(f"OpenCode config: {action} — copying/validating the whole tree…")
    screen.result_text("Working — whole-directory operations may take time for plugins/dependencies…")

    def execute():
        with admission(app) as admitted:
            if not admitted: return
            result, error, conflict = None, None, None
            try:
                m = c.resolve(screen.environment["id"])
                with c.runtime_feedback(progress=None, cancelled=None):
                    if action == "export": result = oc.export(m, replace=replace)
                    elif action == "apply": result = oc.apply(m, overwrite=overwrite)
                    elif action == "delete": oc.delete_export(m, confirmed=True)
                    elif action == "reload": result = oc.reload(m, source, confirmed=True)
                    elif action == "recover": result = oc.recover(m)
            except oc.Conflict as exc: conflict = exc.fingerprint
            except Exception as exc: error = c.error_text(exc)
            if app.is_running:
                app.call_from_thread(finish, result, error, conflict)

    def finish(result, error, conflict):
        app._operation_pending = app._updates_mutation_active = False
        app._set_busy(error or ("Container config changed — review overwrite" if conflict else "OpenCode config operation complete"))
        if screen.is_mounted:
            if conflict:
                app.push_screen(DriftScreen(), lambda yes: run_transfer(screen, "apply", overwrite=conflict) if yes and screen.is_mounted else None)
            elif error: screen.result_text(error)
            else:
                screen.result_text(f"{action.capitalize()} complete" + (f": {result}" if result else ""))
                if isinstance(screen, ConfigEditorScreen): screen.refresh_status()
        elif error: app.notify(error, severity="error")

    app.run_worker(execute, thread=True, group="environment-operation")


class ConfigEditorScreen(Screen):
    BINDINGS = [Binding("escape", "close", "Close")]
    CSS = "ConfigEditorScreen {align: center middle;} #oc-editor {width: 94%; height: 90%; border: round $accent; padding: 0 1;} #oc-editor-text {height: 1fr;} #oc-editor Horizontal {height: auto;} #oc-editor Button {min-width: 12; width: 1fr;} #oc-editor-status {height: auto;}"

    def __init__(self, environment):
        super().__init__()
        self.environment, self.available = environment, False

    def compose(self):
        with Vertical(id="oc-editor"):
            yield Static(f"OpenCode Config Editor — {self.environment['name']} (host file transfers)", markup=False)
            yield Static("Checking export…", id="oc-editor-status", markup=False)
            yield TextArea(oc.SCOPE + "\n\n" + oc.EXPORT_WARNING, id="oc-editor-text", read_only=True)
            with Horizontal():
                yield Button("Export Config", id="oc-export", compact=True)
                yield Button("Apply Export", id="oc-apply", compact=True)
                yield Button("Delete Export", id="oc-delete", variant="error", compact=True)
            with Horizontal():
                yield Button("Refresh", id="oc-refresh", compact=True)
                yield Button("Recover transfer", id="oc-recover", compact=True)
                yield Button("Close", id="oc-close", compact=True)

    def on_mount(self):
        for bid in ("oc-apply", "oc-delete", "oc-recover"):
            self.query_one("#" + bid, Button).display = False
        self.refresh_status()

    def result_text(self, message):
        self.query_one("#oc-editor-text", TextArea).load_text(c.printable(str(message)))

    @work(thread=True, group="oc-export-status", exclusive=True)
    def refresh_status(self):
        try: result = oc.status(self.environment)
        except Exception as exc: result = {"state": c.error_text(exc), "path": None}
        publish(self.app, self._status, result)

    def _status(self, result):
        if not self.is_mounted: return
        self.available = result["state"] == "Export available"
        self.query_one("#oc-editor-status", Static).update(result["state"] + ("\n" + result["path"] if result["path"] else ""))
        for bid in ("oc-apply", "oc-delete"):
            self.query_one("#" + bid, Button).display = self.available
        self.query_one("#oc-recover", Button).display = c.resolve(self.environment["id"]).get("operation") == "opencode-config"

    def action_close(self):
        if self.available:
            self.app.notify("Export remains at " + str(oc.export_path(self.environment) / "config") + "; /tmp cleanup or reboot may remove it.")
        self.app.pop_screen()

    def on_button_pressed(self, event):
        from .tui import ConfirmScreen
        event.stop()
        action = event.button.id
        if action == "oc-close": self.action_close()
        elif action == "oc-refresh": self.refresh_status()
        elif action == "oc-recover": run_transfer(self, "recover")
        elif action == "oc-export":
            if self.available:
                self.app.push_screen(ConfirmScreen("Replace this export? Existing host-side edits will be lost. Cancel keeps it intact."),
                                     lambda yes: run_transfer(self, "export", replace=True) if yes else None)
            else: run_transfer(self, "export")
        elif action == "oc-delete":
            self.app.push_screen(ConfirmScreen("Delete Export? Unapplied host edits will be lost. Container config is not touched."),
                                 lambda yes: run_transfer(self, "delete") if yes else None)
        elif action == "oc-apply": self.review_apply()

    @work(thread=True, group="oc-apply-review", exclusive=True)
    def review_apply(self):
        try:
            running = c.running(c.resolve(self.environment["id"]))
            publish(self.app, self._apply_reviewed, running, None)
        except Exception as exc: publish(self.app, self._apply_reviewed, False, c.error_text(exc))

    def _apply_reviewed(self, running, error):
        from .tui import ConfirmScreen
        if not self.is_mounted or self.app.screen is not self: return
        if error: self.result_text(error)
        elif running:
            self.app.push_screen(ConfirmScreen(oc.RUNNING_WARNING + "\nApply Export now?"),
                                 lambda yes: run_transfer(self, "apply") if yes else None)
        else: run_transfer(self, "apply")


class ReloadConfigScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close")]
    CSS = "ReloadConfigScreen {align: center middle;} #oc-reload {width: 90%; height: 90%; border: round $accent; padding: 0 1;} #oc-reload-text {height: 1fr;} #oc-reload Horizontal {height: auto;}"

    def __init__(self, environment):
        super().__init__()
        self.environment = environment

    def compose(self):
        names = oc.profiles()
        original = self.environment.get("opencode_config_source")
        with Vertical(id="oc-reload"):
            yield Static(f"Reload OpenCode Config — {self.environment['name']}", markup=False)
            yield Select([("Empty — clear the whole global config directory", ""), *((name, name) for name in names)],
                         value=original if original in names else "", allow_blank=False, id="oc-reload-source", compact=True)
            yield TextArea(oc.REPLACE_WARNING + "\nEmpty completely clears this directory's local configuration.\n\n" + oc.SCOPE,
                           read_only=True, id="oc-reload-text")
            with Horizontal():
                yield Button("Reload Config", id="oc-reload-confirm", variant="error", compact=True)
                yield Button("Close", id="oc-reload-close", compact=True)

    def result_text(self, message): self.query_one("#oc-reload-text", TextArea).load_text(c.printable(str(message)))

    def on_button_pressed(self, event):
        event.stop()
        if event.button.id == "oc-reload-close": self.app.pop_screen()
        elif event.button.id == "oc-reload-confirm":
            self.review(self.query_one("#oc-reload-source", Select).value or None)

    @work(thread=True, group="oc-reload-review", exclusive=True)
    def review(self, source):
        try:
            if source is not None: oc.profile_path(source)
            running = c.running(c.resolve(self.environment["id"]))
            publish(self.app, self._reviewed, source, running, None)
        except Exception as exc: publish(self.app, self._reviewed, source, False, c.error_text(exc))

    def _reviewed(self, source, running, error):
        from .tui import ConfirmScreen
        if not self.is_mounted or self.app.screen is not self: return
        if error: self.result_text(error); return
        text = oc.REPLACE_WARNING + "\n" + ("Empty completely clears local config." if source is None else f"Copy profile {source} once.")
        if running: text += "\n" + oc.RUNNING_WARNING
        self.app.push_screen(ConfirmScreen(text), lambda yes: run_transfer(self, "reload", source=source) if yes else None)
