"""Compact manual/cached Updates views, with screen-owned cancellable read-only workers."""
import json
import time

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static, Tab, Tabs
from textual.widgets.data_table import CellDoesNotExist

from . import __version__, distros, updates
from . import core as c
from . import opencode_versions as v
from . import update_cache as cache
from .tui_runtime import publish, work

VIEWS = {"manager": "Sandbox Manager", "bases": "Base Images", "environments": "Environment OpenCode"}


def plain(value):
    return c.printable(str(value)).replace("\n", " ").replace("\t", " ")


class UpdatesScreen(Screen):
    # Toasts normally dock over the lower controls. Keep notification ownership intact, but
    # disclose them through the compact heading/Details instead of covering this read-only UI.
    CSS = """UpdatesScreen {align: center middle;}
    UpdatesScreen ToastRack {height: 0; max-height: 0; margin: 0; overflow: hidden;}
    #updates-panel {width: 100%; max-width: 120; height: 100%; border: round $accent; padding: 0 1;}
    #updates-title, #updates-keys {height: 1;}
    #updates-discovery {height: 2; text-wrap: nowrap; text-overflow: ellipsis;}
    #updates-table {height: 1fr; min-height: 3;}
    #updates-selected {height: 5; text-wrap: nowrap; text-overflow: ellipsis;}
    #updates-reason {height: 2; color: $text-muted; text-wrap: nowrap; text-overflow: ellipsis;}
    #updates-buttons {height: auto;}
    #updates-buttons Button {min-width: 10; width: 1fr;}
    """
    BINDINGS = [Binding("escape", "close", "Close"), Binding("c", "check", "Check"),
                Binding("d", "details", "Details"), Binding("1", "view('manager')", "Manager"),
                Binding("2", "view('bases')", "Bases"), Binding("3", "view('environments')", "Environments")]
    AUTO_FOCUS = "#updates-table"

    def __init__(self, *, environment_id=None):
        super().__init__()
        self.view = "manager"
        self.items = {key: {} for key in VIEWS}
        self.selection = {"environments": environment_id}
        self.remote = v.discovery()
        self.inventory_error = None
        self._discovery_notice = None
        self._alive = False
        self._generation = {}
        self._active = {}
        self._owned = []

    def compose(self) -> ComposeResult:
        with Vertical(id="updates-panel"):
            yield Static("Updates — independent components; no automatic installation", id="updates-title", markup=False)
            yield Tabs(Tab("1 Manager", id="manager"), Tab("2 Base Images", id="bases"),
                       Tab("3 Environments", id="environments"), id="updates-tabs")
            yield Static("", id="updates-discovery", markup=False)
            yield DataTable(id="updates-table", cursor_type="row")
            yield Static("", id="updates-selected", markup=False)
            yield Static("", id="updates-reason", markup=False)
            with Horizontal(id="updates-buttons"):
                yield Button("Check", id="updates-check", compact=True)
                yield Button("Details", id="updates-details", compact=True)
                yield Button("Cancel check", id="updates-cancel", compact=True, disabled=True)
                yield Button("Update", id="updates-update", compact=True, disabled=True)
                yield Button("Close", id="updates-close", compact=True)
            yield Static("1/2/3: views   ↑/↓: select   c: Check   d/Enter: Details   Esc: Close", id="updates-keys", markup=False)

    def on_mount(self):
        self._alive = True
        self.items["manager"]["manager"] = {"name": "Sandbox Manager", "state": "installed",
                                             "version": __version__, "observation": None}
        for d in distros.REGISTRY.values():
            self.items["bases"][d.id] = {"name": d.name, "state": "inspecting local image…", "version": None}
        try:
            for m in c.all_envs():
                try:
                    item = {"name": m["name"], "id": m["id"], "metadata": m,
                            "policy": v.policy(m), **v.environment_history(m)}
                except Exception as exc:
                    item = {"name": m["name"], "id": m["id"], "metadata": m, "policy": None,
                            "state": "unknown", "version": None, "error": c.error_text(exc)}
                self.items["environments"][m["id"]] = item
        except Exception as exc:
            self.inventory_error = c.error_text(exc)
        self._render_view()
        for section in ("bases", "environments"):
            entries = [(key, self._next(section, key)) for key in self.items[section]]
            self._track(self._inventory_worker(section, entries))
        self.set_interval(1, self._render_notices)

    def _notices(self):
        notes = list(self.app._notifications)
        for _summary, note in self.app._advisories.values():
            if note not in notes: notes.append(note)
        return notes

    def _render_notices(self):
        count = len(self._notices())
        self.query_one("#updates-title", Static).update(
            "Updates — no automatic installation" + (f" | {count} dashboard notice(s): Details" if count else ""))

    def _track(self, worker):
        self._owned = [w for w in self._owned if not w.is_finished]
        self._owned.append(worker)

    def _next(self, section, key):
        token = object()
        self._generation[section, key] = token
        return token

    @work(thread=True, group="updates-inventory")
    def _inventory_worker(self, section, entries):
        for key, token in entries:
            item = self._inspect(section, key, check=False)
            publish(self.app, self._receive, section, key, token, item, False)

    def _inspect(self, section, key, *, check):
        try:
            if section == "bases": return updates.base_inventory(distros.get(key), check=check)
            m = c.resolve(key)
            return {"name": m["name"], "metadata": m, "policy": v.policy(m), **v.environment_version(m, check=check)}
        except Exception as exc:
            return {"error": c.error_text(exc)}

    def _receive(self, section, key, token, item, checked):
        if not self._alive or self._generation.get((section, key)) is not token: return
        previous = self.items[section][key]
        if item.get("error") and "verification" not in item:
            item["verification"] = "history-unverified" if previous.get("verification") == "history-unverified" else "last-verified"
            if previous.get("state") == "inspecting local image…": item["state"] = "unknown"
        if not item.get("error"): previous.pop("error", None)
        if "state" in item and not item.get("recovery"): previous.pop("recovery", None)
        self.items[section][key].update(item)
        if checked:
            self._active.pop((section, key), None)
            self.items[section][key].pop("checking", None)
            self.items[section][key].pop("notice", None)
            if not item.get("error"): self.items[section][key].pop("error", None)
        self._render_view()

    def selected_key(self):
        table = self.query_one("#updates-table", DataTable)
        if table.row_count:
            try: return table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            except CellDoesNotExist: return None
        return None

    def on_tabs_tab_activated(self, event: Tabs.TabActivated):
        if self._alive: self.action_view(event.tab.id)

    def on_resize(self):
        if self._alive: self._render_view()

    def action_view(self, view):
        if view != self.view:
            self.selection[self.view] = self.selected_key()
            self.view = view
            self.query_one("#updates-tabs", Tabs).active = view
            self.query_one("#updates-table", DataTable).clear()
            self._render_view()
        self.query_one("#updates-table", DataTable).focus()

    def _render_view(self):
        table = self.query_one("#updates-table", DataTable)
        previous = self.selected_key() or self.selection.get(self.view)
        table.clear(columns=True)
        width = max(50, min(self.size.width, 120) - 10)
        table.add_column(VIEWS[self.view], width=width * 27 // 100)
        table.add_column("State / definition", width=width * 33 // 100)
        table.add_column("Version evidence", width=width - width * 27 // 100 - width * 33 // 100)
        for key, item in self.items[self.view].items():
            evidence = item.get("version") or "Unknown"
            if item.get("observation"): evidence += " (last verified)"
            state = "checking…" if item.get("checking") else item.get("state", "unknown")
            if item.get("error"): state += "; check failed"
            table.add_row(*(Text(plain(x)) for x in (item["name"], state, evidence)), key=key)
            if key == previous: table.move_cursor(row=table.row_count - 1)
        self._render_selected()

    def discovery_text(self):
        if self.view == "manager": return "Published releases: not checked\nRelease discovery and installation verification are not available here yet."
        success, attempt = self.remote.get("success"), self.remote.get("attempt")
        stale = self.remote.get("stale") or bool(success and time.time() - success["at"] >= 86400)
        text = (f"npm: {success['value']} — cached; checked {cache.when(success['at'])}"
                + ("; stale" if stale else "")) if success else "npm: never checked; availability unknown"
        if ("npm",) in self._active: return text + "\nChecking npm… local evidence remains available."
        if self._discovery_notice: return text + "\n" + self._discovery_notice
        if attempt and not attempt["ok"]: return text + "\nCheck failed: " + attempt["error"]
        return text + "\nCheck queries npm and verifies only the selected object; never starts an environment."

    def item_summary(self, item):
        try:
            return v.environment_line(item, (self.remote.get("success") or {}).get("value"))
        except Exception as exc:
            return f"check failed ({c.error_text(exc)})"

    def _render_selected(self):
        self._render_notices()
        key = self.selected_key()
        item = self.items[self.view].get(key)
        self.query_one("#updates-discovery", Static).update(plain_lines(self.discovery_text()))
        check_reason = None
        if self.view == "manager":
            text = f"Sandbox Manager {__version__}\nInstallation classification: not assessed\nManager release checking/update is not available here yet.\nDetails: existing installation and manual upgrade guidance."
            check_reason = "Manager release discovery is not available here yet."
        elif item is None:
            text = "No environments listed." + (f"\nLocal inventory failed: {self.inventory_error}" if self.inventory_error else "")
            check_reason = "No selected object; Check still queries npm."
        else:
            lines = [item["name"], item.get("state", "unknown")]
            if self.view == "environments":
                lines[1] = self.item_summary(item)
                observation = item.get("observation")
                lines.append("Actual state: " + item.get("state", "unknown")
                             + (f"; last verified {cache.when(observation['at'])}" if observation else "; version Unknown"))
                if item.get("recovery"): lines.append(item["recovery"])
                elif item.get("verification") == "history-unverified": lines.append("Current container identity unverified; see Details.")
                elif item.get("state") == "stopped": lines.append("For fresh evidence, explicitly Start from the dashboard; it stays running.")
                elif item.get("state") == "not-created": lines.append("No runtime binary verified; creation-image labels are not installed evidence.")
            else:
                observation = item.get("observation")
                lines.append(f"OpenCode: {item.get('version') or 'Unknown'}" + (f"; last verified {cache.when(observation['at'])}" if observation else ""))
                if item.get("version") and self.remote.get("success"):
                    lines.append(v.describe(item["version"], self.remote["success"]["value"]))
                lines.append("Upstream OS/package freshness not assessed; build label: " + str(item.get("build_version") or "Unknown"))
                if not item.get("eligible"): check_reason = "Image probe unavailable: managed ownership/provenance not verified."
            if item.get("error"): lines = [*lines[:4], "Check failed: " + item["error"]]
            if item.get("notice"): lines = [*lines[:4], item["notice"]]
            text = "\n".join(lines[:5])
        self.query_one("#updates-selected", Static).update(plain_lines(text))
        reason = check_reason or ""
        reason += "\n" + {"manager": "Update unavailable: verified manager handoff is not implemented yet.",
                           "bases": "Build/Rollback unavailable here yet; CLI guidance in Details. Existing environments do not change.",
                           "environments": "Start/Update/Policy/Rollback/Recover unavailable here yet; use existing dashboard/CLI (Details)."}[self.view]
        self.query_one("#updates-reason", Static).update(reason.strip())
        button = self.query_one("#updates-check", Button)
        button.disabled = self.view == "manager"
        button.tooltip = check_reason or "Query npm and check the selected object's OpenCode version"
        self.query_one("#updates-cancel", Button).disabled = not self._active
        self.query_one("#updates-update", Button).tooltip = reason.strip()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        if self._alive: self._render_selected()

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        self.action_details()

    def action_check(self):
        if self.view == "manager": return
        # One in-flight npm request per screen, shared by both OpenCode views.
        if ("npm",) not in self._active:
            self._active[("npm",)] = self._registry_worker()
            self._track(self._active[("npm",)])
        key = self.selected_key()
        item = self.items[self.view].get(key)
        eligible = item is not None and (self.view == "environments" or item.get("eligible"))
        if eligible and (self.view, key) not in self._active:
            token = self._next(self.view, key)
            item["checking"] = True
            self._active[self.view, key] = self._check_worker(self.view, key, token)
            self._track(self._active[self.view, key])
        self._render_view()

    @work(thread=True, group="updates-check")
    def _check_worker(self, section, key, token):
        item = self._inspect(section, key, check=True)
        publish(self.app, self._receive, section, key, token, item, True)

    @work(thread=True, group="updates-discovery")
    def _registry_worker(self):
        try:
            value = v.latest()
            result = {"success": cache.evidence(value, "npm-metadata", {"url": v.REGISTRY, "major": v.MAJOR}),
                      "attempt": {"at": time.time(), "ok": True}, "stale": False}
        except Exception as exc:
            result = {"attempt": {"at": time.time(), "ok": False, "error": c.error_text(exc)}, "stale": True}
        publish(self.app, self._registry_received, result)

    def _registry_received(self, result):
        if not self._alive: return
        self._active.pop(("npm",), None)
        self._discovery_notice = None
        self.remote.update(result)
        self._render_selected()

    def action_cancel_checks(self):
        if ("npm",) in self._active: self._discovery_notice = "npm check canceled; previous discovery retained."
        for request, worker in self._active.items():
            worker.cancel()
            if request != ("npm",):
                section, key = request
                self._next(section, key)
                self.items[section][key].pop("checking", None)
                self.items[section][key]["notice"] = "Check canceled; previous evidence retained."
        self._active.clear()
        self._render_view()

    def action_details(self):
        from .tui import ReportScreen
        key = self.selected_key()
        item = self.items[self.view].get(key)
        lines = [VIEWS[self.view], self.discovery_text(), ""]
        if self.view != "manager": lines += ["Discovery evidence:", json.dumps(self.remote, indent=2), ""]
        notes = self._notices()
        if notes:
            lines += ["Dashboard notices (retained; compact here so controls remain visible):",
                      *[f"{note.title}: {note.message}" for note in notes], ""]
        if item:
            lines.append(json.dumps({k: value for k, value in item.items() if k != "metadata"}, indent=2))
            if self.view == "environments": lines.append(self.item_summary(item))
        if self.inventory_error: lines.append("Local inventory failed: " + self.inventory_error)
        if self.view == "manager":
            lines += ["Installation not classified. Do not infer pipx ownership from PATH or this screen.",
                      "Manual installation/upgrade: follow docs/install.md for your existing installation.",
                      "No release has been checked, no target selected, and no replacement is authorized."]
        elif self.view == "bases" and key:
            d = distros.get(key)
            lines += [f"Tag: {d.image}; manager definition: {d.name} {d.version}, revision {d.revision}",
                      "Build provenance is not a runtime check or an upstream package-freshness assessment.",
                      (v.describe(item["version"], self.remote["success"]["value"])
                       if item.get("version") and self.remote.get("success") else "Version availability: Unknown without verified binary and discovery evidence."),
                      f"CLI: opencode-sandbox opencode check --distro {key}",
                      f"CLI: opencode-sandbox opencode update-base --distro {key}",
                      f"CLI: opencode-sandbox opencode rollback-base --distro {key}",
                      "Base replacement does not migrate existing environments or their system layers."]
        elif item:
            m = item["metadata"]
            lines += [f"Saved state (not live evidence): {m.get('status')}; operation: {m.get('operation') or 'none'}",
                      f"Last operation error: {m.get('last_error') or 'none'}",
                      "History is not proof that the current binary is unchanged. No stopped container is started by Check.",
                      *[f"CLI: opencode-sandbox {cmd} {m['id']}" for cmd in
                        ("start", "opencode status", "opencode update", "opencode policy", "opencode rollback", "opencode update-recover")],
                      "Start explicitly leaves it running. Update requires an existing stopped, network-enabled container.",
                      "Pins, ownership and pending journals still govern all operations; availability is not consent."]
        self.app.push_screen(ReportScreen(c.printable("\n".join(lines)), title=f"Updates — {VIEWS[self.view]} — Details"))

    def action_close(self):
        self._stop_workers()
        self.app.pop_screen()

    def _stop_workers(self):
        self._alive = False
        for worker in self._owned: worker.cancel()

    def on_unmount(self):
        self._stop_workers()

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        {"updates-check": self.action_check, "updates-details": self.action_details,
         "updates-cancel": self.action_cancel_checks, "updates-close": self.action_close}.get(event.button.id, lambda: None)()


def plain_lines(text):
    return "\n".join(plain(line) for line in text.splitlines())
