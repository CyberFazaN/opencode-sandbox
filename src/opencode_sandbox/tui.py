"""Textual environment manager. Destructive actions always require confirmation."""
import contextlib
from pathlib import Path

from rich.markup import escape
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ItemGrid, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TextArea,
)
from textual.widgets.data_table import CellDoesNotExist, RowDoesNotExist

from . import core as c
from .tui_runtime import work


class ConfirmScreen(ModalScreen[bool]):
    CSS = "ConfirmScreen {align: center middle;} #confirm-panel {width: 72; max-width: 100%; height: auto; max-height: 100%; border: round $error; background: $surface; padding: 1 2;} #confirm-panel Horizontal {height: auto;}"
    BINDINGS = [Binding("escape", "cancel", "Cancel")]
    AUTO_FOCUS = "#cancel"
    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-panel"):
            yield Static(self.message, markup=False)
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button("Confirm", id="confirm", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def action_cancel(self) -> None:
        self.dismiss(False)


class CreateScreen(ModalScreen[dict | None]):
    """New environment. Name, kind and folder first; distribution, workspace mode, provider profile
    and integrations under "More options" with the defaults of `create` (progressive disclosure).
    The checks are core.creation_options, the same as the CLI's."""
    CSS = """CreateScreen {align: center middle;}
    #create-panel {width: 84; max-width: 100%; height: auto; max-height: 100%; border: round $accent; background: $surface; padding: 0 1;}
    #create-panel Horizontal {height: auto;}
    #create-panel Collapsible {padding: 0; border: none;}
    #create-panel Collapsible Contents {padding: 0 0 0 2;}
    #create-error {color: $error; height: auto;}
    .hint {color: $text-muted;}"""
    BINDINGS = [Binding("escape", "cancel", "Cancel")]
    AUTO_FOCUS = "#name"

    def action_cancel(self) -> None:
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        from . import distros, integrations
        profiles = sorted({"default", *c.profile_list()})
        with Vertical(id="create-panel"):
            yield Static("[b]New environment[/b]  (Tab: next field, Esc: cancel)")
            yield Input(placeholder="Name (letters, digits, . _ -)", id="name", compact=True)
            yield Select([("Scratch: empty workspace", "scratch"), ("Project: a copy of a folder", "project"),
                          ("Quick: disposable session", "quick")], value="scratch", allow_blank=False, id="kind", compact=True)
            yield Input(placeholder="Folder to copy (Git repository: committed files only); empty = none", id="source", compact=True)
            with Collapsible(title="More options: distribution, workspace, provider profile, integrations", id="more"):
                yield Select([(f"Base definition: {d.name} {d.version}" + (" (default)" if d.id == distros.DEFAULT else ""), d.id)
                              for d in distros.REGISTRY.values()], value=distros.DEFAULT, allow_blank=False, id="distro", compact=True)
                yield Select([("Workspace: managed (empty, or a copy of the folder; default)", "managed"),
                              ("Workspace: direct host folder (not recommended)", "direct")],
                             value="managed", allow_blank=False, id="workspace-mode", compact=True)
                yield Select([(f"Provider profile: {name}", name) for name in profiles], value="default",
                             allow_blank=False, id="profile", compact=True)
                yield Static("Integrations, set up once at the first start:", classes="hint")
                for item in integrations.CATALOG.values():
                    yield Checkbox(item.name, value=item.name in integrations.DEFAULT, id=f"integration-{item.name}", compact=True)
                    yield Static(f"  {item.description}", classes="hint")
            yield Static("", id="create-error")
            with Horizontal():
                yield Button("Cancel", id="cancel", compact=True)
                yield Button("Create", id="create", variant="primary", compact=True)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "workspace-mode":
            self.query_one("#source", Input).placeholder = (
                "Host folder the agent works in directly (required)" if event.value == "direct"
                else "Folder to copy (Git repository: committed files only); empty = none")

    def on_input_changed(self, event: Input.Changed) -> None:
        # A folder to copy makes a project, as in `create --source` without --kind.
        kind = self.query_one("#kind", Select)
        if event.input.id == "source" and event.value.strip() and kind.value == "scratch":
            kind.value = "project"

    def values(self) -> dict:
        """The form as `create` arguments, checked with core.creation_options (raises SandboxError)."""
        from . import integrations
        name = self.query_one("#name", Input).value.strip()
        folder = self.query_one("#source", Input).value.strip()
        mode = self.query_one("#workspace-mode", Select).value
        kind = self.query_one("#kind", Select).value
        distro = self.query_one("#distro", Select).value
        direct = mode == "direct"
        path = Path(folder).expanduser() if folder else None
        c.creation_options(name, kind, None if direct else path, distro=distro, workspace_mode=mode,
                           workspace=path if direct else None)
        if direct:
            # The host checks without the directory scan, so a refused folder is reported here,
            # with the form still open; creation repeats all of them.
            from . import workspaces
            workspaces.check_direct(path, scan=False)
        chosen = [n for n in integrations.CATALOG if self.query_one(f"#integration-{n}", Checkbox).value]
        return {"name": name, "kind": kind, "source": folder or None, "profile": self.query_one("#profile", Select).value,
                "mode": mode, "distro": distro, "integrations": chosen}

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#create", Button).press()  # Enter in a text field creates, as the Create button

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        try:
            values = self.values()
        except c.SandboxError as exc:
            self.query_one("#create-error", Static).update(escape(str(exc)))
            return
        self.dismiss(values)


class Dashboard(App):
    TITLE = "OpenCode Sandbox"
    # Compact, wrapping button rows: at 80x24 the old layout left one table row and
    # hid 11 of 20 buttons off-screen.
    CSS = """
    Screen {layout: vertical;}
    #search {width: 1fr;}
    .bar {height: auto; grid-gutter: 0 1;}
    .bar Button {width: 1fr;}
    #envs {height: 1fr; min-height: 3;}
    #details {height: 9; border: round $accent; padding: 0 1; text-wrap: nowrap; text-overflow: ellipsis;}
    #status, #metrics {height: 1; padding: 0 1; text-wrap: nowrap; text-overflow: ellipsis;}
    """
    # Labels match the CLI's terms: Settings = `config`, Changes = `changes`, Usage =
    # `container usage`, Disk = `disk`, Backups = `backup list`/`restore`, Promote = `promote`.
    BINDINGS = [Binding("q", "quit", "Quit"), Binding("question_mark", "show_help_panel", "Keys"),
                Binding("slash", "focus_search", "Filter"),
                Binding("o", "open_selected", "OpenCode"), Binding("s", "shell_selected", "Shell"),
                Binding("f5", "start_selected", "Start"), Binding("f6", "stop_selected", "Stop"),
                Binding("n", "create_environment", "New"), Binding("x", "delete_selected", "Delete"),
                Binding("r", "refresh_readiness", "Refresh", show=False), Binding("c", "current_folder", "This folder", show=False),
                Binding("p", "providers", "Provider profiles", show=False), Binding("g", "settings", "Preferences", show=False),
                Binding("t", "runtime", "Settings", show=False), Binding("u", "usage", "Usage", show=False),
                Binding("v", "opencode_versions", "OpenCode versions", show=False), Binding("a", "agent_context", "Agent context", show=False),
                Binding("f8", "recovery", "Recovery", show=False), Binding("R", "repair_selected", "Repair", show=False),
                Binding("e", "export_selected", "Export changes", show=False), Binding("b", "backup_selected", "Backup", show=False),
                Binding("B", "backups", "Backups", show=False), Binding("d", "git_review", "Changes", show=False),
                Binding("k", "keep_quick", "Promote quick", show=False),
                Binding("i", "check_selected", "Check", show=False),
                Binding("D", "disk", "Disk", show=False)]
    AUTO_REFRESH_SECONDS = 2.0
    _GLOBAL_ACTIONS = frozenset({"quit", "show_help_panel"})
    _DASHBOARD_ACTIONS = frozenset(b.action for b in BINDINGS) - _GLOBAL_ACTIONS

    def notify(self, message, *, title="", severity="information", timeout=None, markup=False) -> None:
        """Always plain text: messages carry exception text, file and environment names, in which
        square brackets are content. Screens' notify() passes markup=True explicitly."""
        super().notify(message, title=title, severity=severity, timeout=timeout, markup=False)

    def check_action(self, action: str, parameters) -> bool | None:
        # Dashboard keys must not act on a hidden selection behind sub-screens.
        return not (action in self._DASHBOARD_ACTIONS and len(self.screen_stack) > 1)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Filter name / source / ID  ( / )", id="search", compact=True)
        # Top bar: not about the selected environment. Bottom bar: the selected environment.
        with ItemGrid(id="toolbar", classes="bar", min_column_width=16):
            for label, bid in (("New", "new"), ("This folder", "current"), ("Backups", "backups"),
                               ("Providers", "providers"), ("Preferences", "settings"), ("Versions", "ocversions"),
                               ("Recovery", "recovery"), ("Disk", "disk")):
                yield Button(label, id=bid, compact=True)
        yield DataTable(id="envs", cursor_type="row")
        yield Static("Select an environment to see details", id="details")
        with ItemGrid(id="actions", classes="bar", min_column_width=15):
            for label, bid in (("OpenCode", "open"), ("Shell", "shell"), ("Start", "start"), ("Stop", "stop"),
                               ("Check", "check"), ("Settings", "runtime"), ("Usage", "usage"),
                               ("Agent context", "agentcontext"), ("Changes", "changes"), ("Export", "export"),
                               ("Backup", "backup"), ("Repair", "repair"), ("Promote", "keep")):
                yield Button(label, id=bid, compact=True)
            yield Button("Delete", id="delete", variant="error", compact=True)
        yield Static("Resource metrics: select an environment and press Usage", id="metrics", markup=False)
        yield Static("Ready", id="status", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self._operation_pending = False
        self._runtime_waiters = set()
        self.query_one("#envs", DataTable).add_columns("Name", "Kind", "State", "Profile", "Source", "ID")
        self.action_refresh()
        # CLI changes made while the dashboard is open (H08); only metadata file stats are read.
        self.set_interval(self.AUTO_REFRESH_SECONDS, self._refresh_if_changed)
        # Focus the table, not the filter: otherwise every letter key typed into the filter.
        self.query_one("#envs", DataTable).focus()
        try:
            pending = c.pending_repairs()
            if pending:
                self.notify(f"{len(pending)} environment(s) need repair", severity="warning", timeout=12)
            invalid = c.invalid_metadata()
            if invalid:
                self.notify(f"{len(invalid)} invalid metadata file(s) ignored; run 'opencode-sandbox list' for paths",
                            severity="warning", timeout=12)
        except Exception as exc:
            self.notify(c.error_text(exc), severity="error")
        self._prerequisites_worker()

    @work(thread=True, exclusive=True, group="prerequisites")
    def _prerequisites_worker(self) -> None:
        """Shared daemon/base-image checks at startup/explicit Refresh, off the UI thread.

        Image warnings are advisory; they never block or change an existing environment.
        """
        from . import readiness
        try:
            check = readiness.daemon_check()
            if check.status != readiness.PASSED:
                self.call_from_thread(self._show_prerequisites, check.detail)
                return
            self.call_from_thread(self._prerequisites_ready)
            support = readiness.resource_support_check()
            self.call_from_thread(self._show_resource_support, support)
            images = [item for item in readiness.image_checks() if item.status != readiness.PASSED]
            if images:
                self.call_from_thread(self._show_image_checks, images)
        except Exception as exc:
            self.call_from_thread(self._show_prerequisites, c.error_text(exc))
            return

    def _show_resource_support(self, check) -> None:
        from . import readiness
        for note in list(self._notifications):
            if note.title == "Resource-limit support": self._unnotify(note)
        status = self.query_one("#status", Static)
        if check.status != readiness.PASSED:
            if not self._operation_pending:
                status.update("Resource-limit support needs attention. Details: opencode-sandbox doctor")
            text = "\n".join(readiness.format_report({"checks": [vars(check)]}))
            self.notify(text, title="Resource-limit support", severity="warning", timeout=30)
        elif not self._operation_pending and str(status.render()).startswith("Resource-limit support needs attention"):
            status.update("Ready")

    def _show_image_checks(self, checks) -> None:
        from . import readiness
        if not self._operation_pending:
            self.query_one("#status", Static).update("Base image checks need attention. Details: opencode-sandbox doctor")
        self.notify("\n".join(readiness.format_report({"checks": [vars(item) for item in checks]})),
                    title="Base images need attention", severity="warning", timeout=30)

    def _show_prerequisites(self, detail: str) -> None:
        if not self._operation_pending:
            self.query_one("#status", Static).update(
                "Docker is not ready: environments cannot start. Details: opencode-sandbox doctor")
        self.notify(f"{detail}\nDetails: opencode-sandbox doctor", title="Docker is not ready",
                    severity="warning", timeout=30)

    def _prerequisites_ready(self) -> None:
        for note in list(self._notifications):
            if note.title == "Docker is not ready":
                self._unnotify(note)
        status = self.query_one("#status", Static)
        if not self._operation_pending and str(status.render()).startswith("Docker is not ready"):
            status.update("Ready")

    def _runtime_notice(self, message, worker) -> None:
        if not self.is_running or (message and worker.is_cancelled):
            return
        if message:
            first = not self._runtime_waiters
            self._runtime_waiters.add(worker)
            if not self._operation_pending:
                self.query_one("#status", Static).update(message)
            if first: self.notify(message, title="Docker readiness", timeout=10)
        else:
            self._runtime_waiters.discard(worker)
            if not self._runtime_waiters:
                for note in list(self._notifications):
                    if note.title == "Docker readiness": self._unnotify(note)
            status = self.query_one("#status", Static)
            if not self._runtime_waiters and str(status.render()).startswith("Waiting for Docker readiness"):
                status.update("Ready")

    @staticmethod
    def _metadata_state():
        state = []
        for p in (c.BASE / "environments").glob("*/metadata.json"):
            try: s = p.stat()
            except OSError: continue
            state.append((p.parent.name, s.st_ino, s.st_mtime_ns, s.st_size))
        return sorted(state)

    def _refresh_if_changed(self) -> None:
        if len(self.screen_stack) > 1:
            return  # the table lives on the dashboard screen; picked up after the sub-screen closes
        if self._metadata_state() != self._metadata_seen:
            self.action_refresh()

    def action_refresh(self) -> None:
        self._metadata_seen = self._metadata_state()
        table = self.query_one("#envs", DataTable)
        previous = None
        if table.row_count:
            with contextlib.suppress(CellDoesNotExist):
                previous = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        table.clear()
        needle = self.query_one("#search", Input).value.casefold()
        from .preferences import read as read_preferences
        try: show_quick = read_preferences()["show_quick"]
        except (c.SandboxError, OSError, ValueError): show_quick = True  # unreadable ui.json: the default
        for m in c.all_envs():
            if not show_quick and m.get("kind") == "quick": continue
            if needle not in " ".join(str(m.get(k) or "") for k in ("name", "source", "id")).casefold():
                continue
            # Text cells: a str cell is parsed as markup.
            table.add_row(*(Text(str(v)) for v in (m["name"], m["kind"], m.get("status", "?"), m.get("profile", "default"),
                                                   m.get("source") or "—", m["id"])), key=m["id"])
        if previous is not None:
            with contextlib.suppress(RowDoesNotExist):  # the selected environment is gone or filtered out
                table.move_cursor(row=table.get_row_index(previous))
        self.update_details()

    def action_refresh_readiness(self) -> None:
        """Explicit Refresh retries prerequisites; metadata auto-refresh stays Docker-free."""
        self.action_refresh()
        self._prerequisites_worker()

    def selected(self):
        table = self.query_one("#envs", DataTable)
        if not table.row_count:
            return None
        try:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            return c.resolve(key)
        except (CellDoesNotExist, c.SandboxError):  # no row under the cursor, or removed meanwhile
            return None

    def update_details(self) -> None:
        m = self.selected()
        if not m:
            empty = not self.query_one("#envs", DataTable).row_count
            self.query_one("#details", Static).update(
                "No environment selected" + ("\n\nNo environments shown. Press n for a new environment, c to import "
                                             "this folder, / to change the filter." if empty else ""))
            return
        self.query_one("#details", Static).update(self._details(m))
        self.query_one("#metrics", Static).update("Resource metrics: press Usage to fetch Docker stats")

    @staticmethod
    def _details(m) -> str:
        """Seven lines, the pane's height at 80x24 (not wrapped: long values end in an ellipsis; the
        full values: `status NAME`), in the CLI's wording (`status`, `config show`)."""
        from . import workspaces
        from .config_plan import current
        try:
            cfg = current(m)
            ports = ", ".join(f"{p['host']}:{p['container']}/{p['protocol']}" for p in cfg["ports"]) or "none"
            settings = f"{cfg['cpus']} CPU, {cfg['memory']} memory, {cfg['pids']} processes, network {cfg['network']}, ports {ports}"
            profile = cfg["profile"]
        except c.SandboxError as exc:
            settings, profile = f"invalid ({exc})", m.get("profile", "default")
        try: workspace = workspaces.describe(m)
        except c.SandboxError as exc: workspace = f"invalid ({exc})"
        image = c.distribution_description(m)
        created = str(m.get("created") or "—")[:16].replace("T", " ")
        return (f"[b]{escape(m['name'])}[/b]  {m['kind']}  ID {m['id']}\n"
                f"State: {m.get('status', '?')}  Operation: {m.get('operation') or '—'}  Created: {created}\n"
                f"Workspace: {escape(workspace)}\n"
                f"Distribution: {escape(image)}  Provider profile: {escape(profile)}\n"
                f"Settings: {escape(settings)}\n"
                f"Readiness: {Dashboard._readiness_line(m)}\n"
                f"Error: {escape(str(m.get('last_error') or '—'))}")

    @staticmethod
    def _readiness_line(m) -> str:
        from . import readiness
        return escape(readiness.cached_line(m)) + "  (i: check)"

    def action_check_selected(self) -> None:
        """Comprehensive read-only check (same implementation as `check NAME`), off the UI thread."""
        m = self.selected()
        if m is None:
            self.notify("Select an environment", severity="warning"); return
        self.notify(f"Checking {m['name']}…")
        self._check_worker(m)

    @work(thread=True, exclusive=True, group="readiness-check")
    def _check_worker(self, m):
        from . import readiness
        try:
            report = readiness.run(m)
            text = (f"Readiness of {m['name']} [{m['id']}]\nSummary: {readiness.summary(report)}\n\n"
                    + "\n".join(readiness.format_report(report)))
            self.call_from_thread(self._show_check, text, readiness.failed(report))
        except Exception as exc:
            self.call_from_thread(self._show_check, f"Check failed: {c.error_text(exc)}", True)

    def _show_check(self, text: str, failed: bool) -> None:
        self.push_screen(OpenCodeVersionsScreen(text, title="Readiness check (read-only; nothing was started or changed)"))
        self.update_details()
        if failed:
            self.notify("Some checks failed", severity="error")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self.update_details()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # Enter (or a click on the highlighted row); the table consumes Enter itself.
        if event.data_table.id == "envs":
            self.action_open_selected()

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_repair_selected(self) -> None: self._perform("repair")
    def action_backup_selected(self) -> None: self._perform("backup")

    def action_backups(self) -> None:
        from .backup_tui import BackupScreen
        self.push_screen(BackupScreen())

    def action_git_review(self) -> None:
        from .git_tui import GitScreen
        m = self.selected()
        if m: self.push_screen(GitScreen(m))
        else: self.notify("Select an environment", severity="warning")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.action_refresh()

    def action_providers(self) -> None:
        from .management_tui import ProviderScreen
        self.push_screen(ProviderScreen())

    def action_settings(self) -> None:
        from .management_tui import SettingsScreen
        self.push_screen(SettingsScreen())

    def action_runtime(self) -> None:
        m=self.selected()
        if m:
            self.push_screen(RuntimeScreen(m), lambda settings: self._save_runtime(m, settings))

    def _save_runtime(self, m, changes) -> None:
        if changes is None: return
        if self._operation_pending:
            self.notify("Another operation is running", severity="warning"); return
        from . import config_plan as cp
        try:
            plan=cp.plan(m, changes)
            if not plan.changes:
                self.notify("No configuration changes", severity="information"); return
            if plan.blockers:
                raise c.SandboxError("; ".join(plan.blockers))
            self.push_screen(ConfirmScreen(cp.describe(plan)),
                lambda yes: self._apply_runtime(m,changes,plan) if yes else None)
        except Exception as exc:
            self.notify(f"Configuration plan failed: {c.error_text(exc)}", severity="error")

    def _apply_runtime(self, m, changes, plan):
        if self._operation_pending: return
        self._operation_pending=True
        self._set_busy("Applying settings…")
        self._runtime_worker(m, changes, plan)

    @work(thread=True, exclusive=True, group="environment-operation")
    def _runtime_worker(self, m, changes, plan):
        from . import config_plan as cp
        try:
            result=cp.apply(m, changes, confirmed=plan)
            self.app.call_from_thread(self._finished, f"Settings applied ({result['category']})")
        except Exception as exc:
            self.app.call_from_thread(self._finished,c.error_text(exc),True)

    @work(thread=True, exclusive=True, group="runtime-usage")
    def _usage_worker(self,m):
        try:
            result=c.runtime_usage(m)
            self.app.call_from_thread(self._show_usage, m["name"], result)
        except Exception as exc:
            self.app.call_from_thread(self._show_usage_error, c.error_text(exc))

    def _show_usage(self, name, data):
        if data.get("state") == "running":
            msg = (f"{name}: CPU {data.get('cpu') or '?'} | RAM {data.get('memory') or '?'} "
                   f"({data.get('memory_percent') or '?'}) | PIDs {data.get('processes') or '?'} | Net {data.get('network_io') or '?'}")
        else: msg = f"{name}: {data.get('state', 'unknown')}"
        self.query_one("#metrics", Static).update(msg)

    def _show_usage_error(self, message):
        self.query_one("#metrics", Static).update(f"Usage unavailable: {message}")
        self.notify(message, severity="error")

    def action_usage(self):
        m=self.selected()
        if m:
            self.query_one("#metrics", Static).update(f"{m['name']}: loading Docker stats…")
            self._usage_worker(m)

    def action_disk(self) -> None:
        """Disk usage and cleanup preview (same implementation as `disk` / `cleanup`)."""
        self.notify("Collecting disk usage…")
        self._disk_worker()

    @work(thread=True, exclusive=True, group="disk-usage")
    def _disk_worker(self):
        from . import cleanup
        try:
            inv = cleanup.inventory()
            self.call_from_thread(self._show_disk, inv)
        except Exception as exc:
            self.call_from_thread(self.notify, f"Disk usage failed: {c.error_text(exc)}", severity="error")

    def _show_disk(self, inv) -> None:
        self.push_screen(DiskScreen(inv), lambda superseded: self._confirm_cleanup(inv, superseded))

    def _confirm_cleanup(self, inv, superseded) -> None:
        from . import cleanup
        if superseded is None:
            return
        items = inv.eligible(superseded)
        text = (f"Remove {len(items)} object(s), freeing {cleanup.human(cleanup.reclaimable(items))}?\n"
                + "\n".join(cleanup.format_preview(items)[:12]) + ("\n  …" if len(items) > 12 else "")
                + "\nEach object is checked again first; objects in use are skipped.")
        self.push_screen(ConfirmScreen(text), lambda yes: self._cleanup_worker([i.key for i in items], superseded) if yes else None)

    @work(thread=True, exclusive=True, group="disk-cleanup")
    def _cleanup_worker(self, keys, superseded):
        from . import cleanup
        try:
            results = cleanup.apply(keys, superseded=superseded)
            def line(item, error):
                label = item if isinstance(item, str) else f"{item.kind} {item.name}"
                if error is None:
                    return f"Removed: {label}"
                if error.startswith("skipped: "):  # left alone on purpose, as in the CLI
                    return f"Skipped: {label} ({error.removeprefix('skipped: ')})"
                return f"Not removed: {label} ({error})"
            lines = [line(item, error) for item, error in results]
            failed = any(error and not error.startswith("skipped: ") for _, error in results)
            self.call_from_thread(self._show_cleanup, "\n".join(lines) or "Nothing removed", failed)
        except Exception as exc:
            self.call_from_thread(self._show_cleanup, f"Cleanup failed: {c.error_text(exc)}", True)

    def _show_cleanup(self, text: str, failed: bool) -> None:
        self.push_screen(OpenCodeVersionsScreen(text, title="Cleanup result"))
        if failed:
            self.notify("Some objects were not removed", severity="warning")

    def action_opencode_versions(self) -> None:
        """Check registry and running environments without starting stopped ones."""
        self.notify("Checking OpenCode versions…")
        self._opencode_versions_worker()

    @work(thread=True, exclusive=True, group="opencode-version-check")
    def _opencode_versions_worker(self):
        from . import opencode_versions as v
        try:
            latest = v.latest()
            rows = []
            for item in v.versions():
                try:
                    rows.append(f"{item['name']}: {v.environment_line(item, latest)}")
                except Exception as exc:
                    rows.append(f"{item['name']}: check failed ({c.error_text(exc)})")
            message = f"Latest OpenCode: {latest}\n" + "\n".join(rows)
            self.call_from_thread(self._show_opencode_versions, message, False)
        except Exception as exc:
            self.call_from_thread(self._show_opencode_versions, c.error_text(exc), True)

    def _show_opencode_versions(self, message: str, error: bool) -> None:
        self.push_screen(OpenCodeVersionsScreen(message))
        if error:
            self.notify("Version check failed", severity="error")

    def action_agent_context(self) -> None:
        m = self.selected()
        if m is None:
            self.notify("Select an environment", severity="warning")
            return
        self._agent_context_worker(m)

    @work(thread=True, exclusive=True, group="agent-context")
    def _agent_context_worker(self, m) -> None:
        from . import agent_context as ac
        try:
            try:
                inputs = c.guidance_inputs(m)
            except c.SandboxError:
                inputs = c.guidance_inputs(m, observe=False)
            content = ac.render(m, **inputs)
            current = ac.verify(m, c.env_dir, **inputs)
            self.call_from_thread(self.push_screen, OpenCodeVersionsScreen(
                f"Agent context: {m['name']}\nOn-disk: {'current' if current else 'missing/outdated'}\n"
                "Guidance is regenerated before every OpenCode launch.\n\n" + content))
        except Exception as exc:
            self.call_from_thread(self.notify, c.error_text(exc), severity="error")

    def action_recovery(self) -> None:
        from .management_tui import RecoveryScreen
        self.push_screen(RecoveryScreen())

    def _set_busy(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _finished(self, message: str, error: bool = False) -> None:
        self._operation_pending = False
        self._set_busy(message)
        self.notify(message, severity="error" if error else "information", timeout=10)
        self.action_refresh()

    @work(thread=True, exclusive=True, group="environment-operation")
    def _run_operation(self, action: str, environment: dict) -> None:
        try:
            if action == "start":
                c.start(environment)
                result = "Started"
            elif action == "stop":
                c.stop(environment)
                result = "Stopped"
            elif action == "repair":
                result = c.repair(environment)
            elif action == "export":
                result = f"Export: {c.export(environment)}"
            elif action == "backup":
                from .backup import backup, backup_notes
                state = c.inspect_container(environment)
                if state and state.get("Running"):
                    raise c.SandboxError(f"{environment['name']} is running; a backup is taken from a stopped container. "
                                         "Stop it first (F6), then back it up (b).")
                target = Path(backup(environment, stop_running=False))
                result = " ".join([f"Backup saved: {target.name} in {target.parent}", *backup_notes(target)])
            elif action == "delete":
                c.delete(environment, force=True)
                result = "Deleted"
            else:
                raise ValueError(action)
            self.app.call_from_thread(self._finished, result)
        except Exception as exc:
            self.app.call_from_thread(self._finished, c.error_text(exc), True)

    def _perform(self, action: str, m=None) -> None:
        """m: the environment named in a confirmation; never re-read the cursor after it."""
        if self._operation_pending:
            self.notify("Another operation is running", severity="warning")
            return
        m = m or self.selected()
        if m is None:
            self.notify("Select an environment", severity="warning")
            return
        self._operation_pending = True
        self._set_busy(f"{action.capitalize()} {m['name']}…")
        self._run_operation(action, m)

    def action_start_selected(self) -> None: self._perform("start")
    def action_stop_selected(self) -> None:
        from .preferences import read
        try: confirm = read()["confirm_stop"]
        except Exception as exc:
            self.notify(c.error_text(exc), severity="error"); return
        m = self.selected()
        if not m: return
        if confirm:
            self.push_screen(ConfirmScreen(f"Stop environment {m['name']}?\nWorkspace and home volume are retained."),
                             lambda yes: self._perform("stop", m) if yes else None)
        else:
            self._perform("stop", m)
    def action_export_selected(self) -> None: self._perform("export")

    def action_keep_quick(self) -> None:
        """Same result as 'promote' at the end of a CLI quick session (D08)."""
        m = self.selected()
        if not m:
            self.notify("Select an environment", severity="warning"); return
        if m.get("kind") != "quick":
            self.notify("Only quick sessions can be promoted; this environment is already persistent", severity="warning"); return
        if self._operation_pending:
            self.notify("Another operation is running", severity="warning"); return
        new_name = f"scratch-{m['id'][:6]}"
        self.push_screen(ConfirmScreen(f"Promote quick session '{m['name']}' to scratch environment '{new_name}'?\n"
                                       "Workspace, home volume and container stay unchanged; it is no longer "
                                       "treated as disposable."),
                         lambda yes: self._keep_quick(m, new_name) if yes else None)

    def _keep_quick(self, m, new_name) -> None:
        try:
            c.promote(m, "scratch", new_name)
            self._finished(f"Promoted to {new_name}")
        except Exception as exc:
            self._finished(c.error_text(exc), True)

    def action_delete_selected(self) -> None:
        m = self.selected()
        if not m:
            return
        if self._operation_pending:
            self.notify("Another operation is running", severity="warning"); return
        direct = (m.get("workspace") or {}).get("mode") == "direct"
        removed = (f"Container and home volume will be removed. The direct workspace {m['workspace']['path']} is not touched.\n"
                   if direct else "Container, home volume, and workspace will be removed.\n")
        self.push_screen(ConfirmScreen(f"Permanently DELETE '{m['name']}' ({m['id']})?\n" + removed +
                                       "Export or back up any important data first."),
                         lambda confirmed: self._perform("delete", m) if confirmed else None)

    def action_create_environment(self) -> None:
        self.push_screen(CreateScreen(), self._create_from_form)

    def _create_from_form(self, values) -> None:
        if values is not None:
            if self._operation_pending:
                self.notify("Another operation is running", severity="warning"); return
            if values["mode"] == "direct":
                self._confirm_direct(values)
                return
            self._operation_pending = True
            self._create_environment(values)

    def _confirm_direct(self, values) -> None:
        """Consent for a direct workspace: same text as the CLI; checks first, so refusals come before it."""
        from . import workspaces
        from .cli import DIRECT_CONSENT
        try:
            target = workspaces.check_direct(Path(values["source"]).expanduser())
        except c.SandboxError as exc:
            self.notify(str(exc), severity="error"); return
        self.push_screen(ConfirmScreen(f"{workspaces.LABEL}.\n\n" + DIRECT_CONSENT.format(path=target)),
                         lambda yes: self._create_direct({**values, "source": str(target)}) if yes else None)

    def _create_direct(self, values) -> None:
        if self._operation_pending:
            self.notify("Another operation is running", severity="warning"); return
        self._operation_pending = True
        self._set_busy(f"Preflight and creation of {values['name']}…")
        self._create_environment(values)

    @work(thread=True, exclusive=True, group="environment-operation")
    def _create_environment(self, values: dict) -> None:
        from . import integrations
        try:
            provisioning = integrations.request(values.get("integrations"))  # None = the defaults
            source = Path(values["source"]).expanduser() if values.get("source") else None
            if values.get("mode") == "direct":
                m = c.create(values["name"], values["kind"], None, profile=values["profile"], distro=values.get("distro"),
                             workspace_mode="direct", workspace=source, consent=True, provisioning=provisioning)
            else:
                m = c.create(values["name"], values["kind"], source, profile=values["profile"], distro=values.get("distro"),
                             provisioning=provisioning)
            self.app.call_from_thread(self._created, m)
        except Exception as exc:
            self.app.call_from_thread(self._finished, c.error_text(exc), True)

    def _created(self, m) -> None:
        """Select the new environment: the next o, s or F5 must act on it, not on the row that was
        selected before (found in a real terminal)."""
        self._finished(f"Created {m['name']} ({m['id']})")
        table = self.query_one("#envs", DataTable)
        try:
            table.move_cursor(row=table.get_row_index(m["id"]))
        except RowDoesNotExist:  # filtered out (e.g. quick sessions hidden): keep the cursor
            return
        self.update_details()

    def action_open_selected(self) -> None: self._attach(False)
    def action_shell_selected(self) -> None: self._attach(True)

    def _attach(self, shell: bool) -> None:
        m = self.selected()
        if not m:
            return
        if self._operation_pending:
            self.notify("Another operation is running", severity="warning"); return
        self._operation_pending = True
        self._set_busy("Checking Docker before opening the session…")
        self._prepare_attach(m, shell)

    @work(thread=True, exclusive=True, group="environment-operation")
    def _prepare_attach(self, m, shell) -> None:
        try:
            c.verify_runtime()
            self.call_from_thread(self._attach_ready, m, shell)
        except Exception as exc:
            self.call_from_thread(self._finished, c.error_text(exc), True)

    def _attach_ready(self, m, shell) -> None:
        self._operation_pending = False
        try:
            with self.suspend(), c.runtime_feedback():
                c.interactive(m, shell=shell)
            from .preferences import read
            if read()["refresh_on_return"]:
                self._finished("Session exited")
            else:
                self._set_busy("Session exited")
        except Exception as exc:
            self._finished(c.error_text(exc), True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action == "new": self.action_create_environment()
        elif action == "current": self.action_current_folder()
        elif action == "refresh": self.action_refresh()
        elif action == "providers": self.action_providers()
        elif action == "settings": self.action_settings()
        elif action == "runtime": self.action_runtime()
        elif action == "usage": self.action_usage()
        elif action == "ocversions": self.action_opencode_versions()
        elif action == "agentcontext": self.action_agent_context()
        elif action == "recovery": self.action_recovery()
        elif action == "open": self.action_open_selected()
        elif action == "shell": self.action_shell_selected()
        elif action == "delete": self.action_delete_selected()
        elif action in {"start", "stop", "repair", "export", "backup"}: self._perform(action)
        elif action == "backups": self.action_backups()
        elif action == "changes": self.action_git_review()
        elif action == "keep": self.action_keep_quick()
        elif action == "check": self.action_check_selected()
        elif action == "disk": self.action_disk()

    def action_current_folder(self) -> None:
        """Importing copies host files into the agent's workspace: always confirm."""
        current = c.current_env()
        if current:
            self.notify(f"Already managed: {current['name']}"); return
        if self._operation_pending:
            self.notify("Another operation is running", severity="warning"); return
        p = Path.cwd()
        git = c.call(["git", "-C", str(p), "rev-parse", "--show-toplevel"], capture=True, check=False)
        if git.returncode == 0:
            what = ("Git repository: a clone of COMMITTED files only; uncommitted and ignored files are not copied."
                    if Path(git.stdout.strip()) == p.resolve() else
                    f"This folder is inside Git repository {git.stdout.strip()}; import the repository root instead.")
        else:
            what = ("Not a Git repository: ALL files are COPIED except hidden files, symlinks and "
                    "node_modules/target/dist/build/__pycache__. The agent can read everything copied.")
        self.push_screen(ConfirmScreen(f"Create project environment '{p.name}' from the current folder?\n{p}\n\n{what}"),
                         lambda yes: self._create_current(p) if yes else None)

    def _create_current(self, p: Path) -> None:
        if self._operation_pending:
            self.notify("Another operation is running", severity="warning"); return
        self._operation_pending = True
        self._set_busy(f"Creating {p.name}…")
        self._create_environment({"name": p.name, "kind": "project", "source": str(p), "profile": "default", "mode": "managed"})

class RuntimeScreen(ModalScreen[dict | None]):
    """Edit manager-owned settings; the dashboard shows the change plan before applying."""
    # Labelled one-line fields: the placeholders were the only labels and vanished once filled.
    CSS = ("RuntimeScreen {align: center middle;} #runtime-panel {width: 78; max-width: 100%; height: auto; max-height: 100%; "
           "border: round $accent; background: $surface; padding: 0 1;} #runtime-panel Horizontal {height: auto;} "
           "#runtime-panel .field {height: 1; margin-bottom: 1;} #runtime-panel .field > Static {width: 19;} "
           "#runtime-panel .field Input, #runtime-panel .field Select {width: 1fr;}")
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def action_cancel(self) -> None:
        self.dismiss(None)

    def __init__(self, environment: dict):
        super().__init__()
        self.environment = environment

    def compose(self) -> ComposeResult:
        from .config_plan import current
        cfg = current(self.environment)
        ports = ",".join(f"{p['host']}:{p['container']}/{p['protocol']}" for p in cfg["ports"])
        profiles = sorted({"default", cfg["profile"], *c.profile_list()})
        with Vertical(id="runtime-panel"):
            yield Static(f"[b]Settings of {escape(self.environment['name'])}[/b] (same as: config apply)\n"
                         "The next step shows the change plan. Ports bind to 127.0.0.1.\n")
            fields = (("CPUs (--cpus)", Input(value=cfg["cpus"], placeholder="e.g. 4", id="rt-cpus", compact=True)),
                      ("Memory (--memory)", Input(value=cfg["memory"], placeholder="e.g. 8g", id="rt-memory", compact=True)),
                      ("Processes (--pids)", Input(value=str(cfg["pids"]), placeholder="e.g. 2048", id="rt-pids", compact=True)),
                      ("Network", Select([("bridge: internet + LAN", "bridge"), ("none: offline", "none")], value=cfg["network"],
                                         allow_blank=False, id="rt-network", compact=True)),
                      ("Ports (--publish)", Input(value=ports, placeholder="none, e.g. 8080:8000/tcp,5353:5353/udp", id="rt-ports", compact=True)),
                      ("Provider profile", Select([(name, name) for name in profiles], value=cfg["profile"], allow_blank=False,
                                                  id="rt-profile", compact=True)))
            for label, widget in fields:
                with Horizontal(classes="field"):
                    yield Static(label)
                    yield widget
            with Horizontal():
                yield Button("Cancel", id="rt-cancel", compact=True)
                yield Button("Preview", id="rt-save", variant="primary", compact=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rt-cancel":
            self.dismiss(None); return
        from .config_plan import parse_ports
        try:
            ports=parse_ports(filter(None, (p.strip() for p in self.query_one("#rt-ports", Input).value.split(","))))
            changes=c.validate_runtime_settings({
                "cpus":self.query_one("#rt-cpus", Input).value,
                "memory":self.query_one("#rt-memory", Input).value,
                "pids":self.query_one("#rt-pids", Input).value,
                "network":self.query_one("#rt-network", Select).value,
                "ports":ports})
            changes["profile"]=self.query_one("#rt-profile", Select).value
        except (ValueError, c.SandboxError) as exc:
            self.notify(str(exc), severity="error"); return
        self.dismiss(changes)


class DiskScreen(ModalScreen[bool | None]):
    """Disk usage report; dismisses with False (cleanup), True (cleanup incl. superseded) or None."""
    CSS = "DiskScreen {align: center middle;} #disk-panel {width: 95%; height: 90%; border: round $accent; padding: 0 1; background: $surface;} #disk-report {height: 1fr;} #disk-panel Horizontal {height: auto;}"
    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, inv):
        super().__init__()
        from . import cleanup
        self.inv = inv
        self.report = "\n".join(cleanup.format_inventory(inv))

    def action_close(self) -> None:
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        default, extra = len(self.inv.eligible()), len(self.inv.eligible(True))
        with Vertical(id="disk-panel"):
            yield Static("Disk usage (read-only; sizes approximate; same as: disk usage, disk cleanup)")
            yield TextArea(self.report, read_only=True, id="disk-report")
            with Horizontal():
                yield Button("Close", id="disk-close")
                yield Button(f"Clean up ({default})", id="disk-cleanup", variant="warning", disabled=not default)
                yield Button(f"Clean up incl. superseded ({extra})", id="disk-cleanup-all", variant="error", disabled=not extra)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss({"disk-cleanup": False, "disk-cleanup-all": True}.get(event.button.id))


class OpenCodeVersionsScreen(ModalScreen[None]):
    """Read-only version report. No automatic container updates."""
    CSS = "OpenCodeVersionsScreen {align: center middle;} #versions-panel {width: 90%; height: 85%; border: round $accent; padding: 0 1; background: $surface;} #versions-report {height: 1fr;}"
    BINDINGS = [Binding("escape", "close", "Close")]

    def action_close(self) -> None:
        self.dismiss(None)

    def __init__(self, report: str, title: str = "OpenCode versions (no automatic updates)"):
        super().__init__()
        self.report = report
        self.title_text = title

    def compose(self) -> ComposeResult:
        with Vertical(id="versions-panel"):
            yield Static(self.title_text)
            yield TextArea(self.report, read_only=True, id="versions-report")
            yield Button("Close", id="close-versions")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-versions":
            self.dismiss(None)
