"""Compact Updates views: owned read-only checks, explicit environment consent and existing handlers."""
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
from . import manager_installation as mi
from . import manager_releases as mr
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
    #updates-environment-buttons {height: auto;}
    #updates-environment-buttons Button {min-width: 10; width: 1fr;}
    #updates-base-buttons {height: auto;} #updates-base-buttons Button {min-width: 10;}
    """
    BINDINGS = [Binding("escape", "close", "Close"), Binding("c", "check", "Check"),
                Binding("d", "details", "Details"), Binding("1", "view('manager')", "Manager"),
                Binding("2", "view('bases')", "Bases"), Binding("3", "view('environments')", "Environments"),
                Binding("u", "environment('update')", "Update"), Binding("s", "environment('start')", "Start"),
                Binding("p", "environment('policy')", "Policy"), Binding("r", "environment('rollback')", "Rollback"),
                Binding("e", "environment('recover')", "Recover"), Binding("b", "base('build')", "Build/Rebuild")]
    AUTO_FOCUS = "#updates-table"

    def __init__(self, *, environment_id=None):
        super().__init__()
        self.view = "manager"
        self.items = {key: {} for key in VIEWS}
        self.selection = {"environments": environment_id}
        self.remote = v.discovery()
        self._cached_remote = dict(self.remote)
        self.manager_remote = mr.discovery()
        self._cached_manager_remote = dict(self.manager_remote)
        self._manager_notice = None
        self.inventory_error = None
        self._discovery_notice = None
        self._alive = False
        self._generation = {}
        self._active = {}
        self._owned = []
        self._preparing = None
        self._prepare_token = None
        self.operation_result = None

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
            with Horizontal(id="updates-environment-buttons"):
                for label, action in (("Start", "start"), ("Policy", "policy"), ("Rollback", "rollback"), ("Recover", "recover")):
                    yield Button(label, id="updates-" + action, compact=True)
            with Horizontal(id="updates-base-buttons"):
                yield Button('Rollback', id='updates-base-rollback', compact=True)
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
        for section in ("manager", "bases", "environments"):
            entries = [(key, self._next(section, key)) for key in self.items[section]]
            self._track(self._inventory_worker(section, entries))
        self.set_interval(1, self._refresh_discovery)

    def _refresh_discovery(self):
        self._render_notices()
        current = v.discovery()
        if current != self._cached_remote and ("npm",) not in self._active:
            self._cached_remote = current
            self.remote = current
            self._discovery_notice = None
            self._render_selected()
        current_manager = mr.discovery()
        if current_manager != self._cached_manager_remote and ('github',) not in self._active:
            self._cached_manager_remote = current_manager
            self.manager_remote = current_manager
            self._manager_notice = None
            self._render_selected()
        self.query_one("#updates-discovery", Static).update(plain_lines(self.discovery_text()))
        if self.view == 'bases': self._render_selected()

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
            if section == 'manager':
                installation = mi.classify()
                return {'installation': installation, 'state': installation['classification']}
            if section == "bases": return updates.base_inventory(distros.get(key), check=check)
            m = c.resolve(key)
            return {"name": m["name"], "metadata": m, "policy": v.policy(m), **v.environment_version(m, check=check)}
        except Exception as exc:
            return {"error": c.error_text(exc)}

    def _receive(self, section, key, token, item, checked):
        if not self._alive or self._generation.get((section, key)) is not token: return
        previous = self.items[section][key]
        if section != 'manager' and item.get("error") and "verification" not in item:
            item["verification"] = "history-unverified" if previous.get("verification") == "history-unverified" else "last-verified"
            if previous.get("state") == "inspecting local image…": item["state"] = "unknown"
        if not item.get("error"): previous.pop("error", None)
        if "state" in item and not item.get("recovery"): previous.pop("recovery", None)
        self.items[section][key].update(item)
        if section == "environments": self._adopt_current_metadata(key)
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
        if self._alive and self.app.screen is self: self.action_view(event.tab.id)

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
        if self.view == 'manager':
            state = self.manager_remote
            success, attempt = state.get('success'), state.get('attempt')
            text = (f"GitHub: {success['value']} — cached; checked {cache.when(success['at'])}"
                    + ('; stale' if state.get('stale') else '')) if success else 'GitHub: never checked; availability unknown'
            if ('github',) in self._active: return text + '\nChecking published manager releases… local installation evidence remains available.'
            worker = self.app._manager_discovery_worker_ref
            if self.app._discovery_enabled and worker is not None and not worker.is_finished:
                return text + '\nDashboard checking GitHub… local installation evidence remains available.'
            if self._manager_notice: return text + '\n' + self._manager_notice
            if attempt and not attempt['ok']: return text + '\nCheck failed: ' + attempt['error']
            return text + '\nCheck reads official published full releases; no installation or downgrade.'
        success, attempt = self.remote.get("success"), self.remote.get("attempt")
        stale = self.remote.get("stale") or bool(success and time.time() - success["at"] >= 86400)
        text = (f"npm: {success['value']} — cached; checked {cache.when(success['at'])}"
                + ("; stale" if stale else "")) if success else "npm: never checked; availability unknown"
        if ("npm",) in self._active: return text + "\nChecking npm… local evidence remains available."
        worker = self.app._discovery_worker_ref
        if self.app._discovery_enabled and worker is not None and not worker.is_finished:
            return text + "\nDashboard checking npm… local evidence remains available."
        if self._discovery_notice: return text + "\n" + self._discovery_notice
        if attempt and not attempt["ok"] and attempt.get("error") == "check did not complete":
            return text + "\nLast npm attempt did not complete; explicit Check can retry."
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
            installation = (item or {}).get('installation')
            text = '\n'.join([f'Sandbox Manager {__version__}', mr.comparison(__version__, self.manager_remote.get('release')),
                              'Installation: ' + (installation['classification'] if installation else 'inspecting local evidence…'),
                              installation['reason'] if installation else 'Local inspection does not run pipx or contact the network.',
                              'Full evidence, release notes and manual guidance: Details.'])
            if item and item.get('notice'): text = '\n'.join(text.splitlines()[:4] + [item['notice']])
            if item and item.get('error'): text = '\n'.join(text.splitlines()[:4] + ['Local check failed: ' + item['error']])
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
                elif item.get("state") == "stopped": lines.append("For fresh evidence: explicit Start, then Check. It stays running.")
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
                            "bases": "Build/Rebuild selects cached or full refresh; existing environments do not change.",
                            "environments": "Actions review live eligibility before consent; Check never starts a container."}[self.view]
        if self.operation_result: reason = "Operation result — Details for full text\n" + plain(self.operation_result)
        if self._preparing: reason = "Preparing read-only operation plan… Cancel check cancels preparation, not an approved mutation."
        base_operation = getattr(self.app, '_base_operation', None)
        if self.view == 'bases' and base_operation and base_operation['distro'] == key:
            reason = (base_operation.get('result') or base_operation['phase']) + '\nBuild output / full result: Details. Close never cancels approved work.'
        if self.app._operation_pending:
            active_base = self.view == 'bases' and base_operation and base_operation['distro'] == key and not base_operation.get('result')
            reason = (base_operation['phase'] if active_base else 'An operation is running.') + '\nClose/Cancel check does not cancel it; wait for its result (Details).'
        self.query_one("#updates-reason", Static).update(reason.strip())
        button = self.query_one("#updates-check", Button)
        button.disabled = False
        button.tooltip = ('Read published GitHub releases and independently inspect local installation; no pipx execution'
                          if self.view == 'manager' else check_reason or "Query npm and check the selected object's OpenCode version")
        self.query_one("#updates-cancel", Button).disabled = not (self._active or self._preparing)
        controls = self.query_one("#updates-environment-buttons")
        controls.display = self.view == "environments"
        self.query_one('#updates-base-buttons').display = self.view == 'bases'
        self.query_one("#updates-keys", Static).update(
            "c Check d Details | s Start u Update p Policy r Rollback e Recover | Esc Close"
            if self.view == "environments" else 'c Check d Details | b/u Build/Rebuild r Rollback | Esc Close'
            if self.view == 'bases' else "1/2/3: views   ↑/↓: select   c: Check   d/Enter: Details   Esc: Close")
        blocked = self.view != "environments" or item is None or bool(self._preparing) or self.app._operation_pending
        for action in ("update", "start", "policy", "rollback", "recover"):
            button = self.query_one("#updates-" + action, Button)
            button.disabled = blocked or bool(item and item.get("metadata", {}).get("operation") and action != "recover")
            button.tooltip = reason.strip() if button.disabled else f"Review {action} for the selected environment; no mutation before confirmation"
        update = self.query_one('#updates-update', Button)
        update.label = ('Build' if item and item.get('state') == 'not built' else 'Rebuild') if self.view == 'bases' else 'Update'
        if self.view == 'bases':
            update.disabled = item is None or bool(self._preparing) or self.app._operation_pending
            update.tooltip = 'Review live base identity, exact target and cached/full-refresh mode before building'
        self.query_one('#updates-base-rollback', Button).disabled = self.view != 'bases' or bool(self._preparing) or self.app._operation_pending

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        event.stop()
        if self._alive: self._render_selected()

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        event.stop()
        if self.app.screen is self: self.action_details()

    def action_check(self):
        if self.view == 'manager':
            if ('github',) not in self._active:
                self._active[('github',)] = self._manager_release_worker()
                self._track(self._active[('github',)])
            if ('manager', 'manager') not in self._active:
                token = self._next('manager', 'manager')
                self.items['manager']['manager']['checking'] = True
                self._active['manager', 'manager'] = self._check_worker('manager', 'manager', token)
                self._track(self._active['manager', 'manager'])
            self._render_view()
            return
        # One UI waiter per screen; the provider also coalesces other screens/CLI/background.
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
            result = v.discovery()
            if not result["success"] or result["success"]["value"] != value or not (result["attempt"] or {}).get("ok"):
                # Explicit discovery still works without writable cache storage.
                result = {"success": cache.evidence(value, "npm-metadata", {"url": v.REGISTRY, "major": v.MAJOR}),
                          "attempt": {"at": time.time(), "ok": True}, "stale": False}
        except Exception as exc:
            attempt = v.discovery()["attempt"]
            if not attempt or attempt["ok"]: attempt = {"at": time.time(), "ok": False}
            result = {"attempt": {**attempt, "error": c.error_text(exc)}, "stale": True}
        publish(self.app, self._registry_received, result)

    def _registry_received(self, result):
        if not self._alive: return
        self._active.pop(("npm",), None)
        self._cached_remote = v.discovery()
        self._discovery_notice = None
        self.remote.update(result)
        self._render_selected()

    @work(thread=True, group='updates-manager-discovery')
    def _manager_release_worker(self):
        try:
            release = mr.latest()
            result = mr.discovery()
            if result.get('release') != release or not (result.get('attempt') or {}).get('ok'):
                result = {'success': cache.evidence(release['version'], mr.SOURCE, {'url': mr.API}), 'release': release,
                          'attempt': {'at': time.time(), 'ok': True}, 'stale': False}
        except Exception as exc:
            attempt = mr.discovery()['attempt']
            if not attempt or attempt['ok']: attempt = {'at': time.time(), 'ok': False}
            result = {'attempt': {**attempt, 'error': c.error_text(exc)}, 'stale': True}
        publish(self.app, self._manager_release_received, result)

    def _manager_release_received(self, result):
        if not self._alive: return
        self._active.pop(('github',), None)
        self._cached_manager_remote = mr.discovery()
        self._manager_notice = None
        self.manager_remote.update(result)
        self._render_selected()

    def action_cancel_checks(self):
        if self._preparing:
            self._preparing.cancel()
            self._preparing = self._prepare_token = None
        if ("npm",) in self._active: self._discovery_notice = "npm check canceled; previous discovery retained."
        if ('github',) in self._active: self._manager_notice = 'GitHub check canceled; previous discovery retained.'
        for request, worker in self._active.items():
            worker.cancel()
            if len(request) == 2:
                section, key = request
                self._next(section, key)
                self.items[section][key].pop("checking", None)
                self.items[section][key]["notice"] = "Check canceled; previous evidence retained."
        self._active.clear()
        self._render_view()

    def action_environment(self, action):
        if self.view == 'bases' and action in ('update', 'rollback'):
            self.action_base('build' if action == 'update' else 'rollback'); return
        from .environment_updates_tui import PolicyScreen, TargetScreen
        if self.view != "environments" or self.app._operation_pending or self._preparing: return
        key = self.selected_key()
        if key is None: return
        try:
            m = c.resolve(key)
            if m.get("operation") and action != "recover": raise c.pending_operation(m)
            if action == "recover" and m.get("operation") != v.UPDATE_OP:
                from .management_tui import RecoveryScreen
                self.app.push_screen(RecoveryScreen(environment_id=key))
            elif action == "update":
                self.app.push_screen(TargetScreen(m), lambda value: self._prepare_action(key, action, value) if value is not None else None)
            elif action == "policy":
                self.app.push_screen(PolicyScreen(m), lambda value: self._prepare_action(key, action, value) if value is not None else None)
            else:
                self._prepare_action(key, action)
        except Exception as exc:
            self.operation_result = c.error_text(exc)
            self._render_selected()

    def action_base(self, action):
        from .base_updates_tui import BaseTargetScreen
        if self.view != 'bases' or self.app._operation_pending or self._preparing: return
        key = self.selected_key()
        if key is None: return
        if action == 'build':
            self.app.push_screen(BaseTargetScreen(distros.get(key)),
                                 lambda value: self._prepare_base(key, action, value) if value is not None else None)
        else: self._prepare_base(key, action)

    def _prepare_base(self, key, action, value=None):
        if not self._alive or self.app._operation_pending or self._preparing: return
        self._prepare_token = token = object()
        self._preparing = self._prepare_base_worker(key, action, value, token)
        self._track(self._preparing)
        self._render_selected()

    @work(thread=True, group='updates-prepare')
    def _prepare_base_worker(self, key, action, value, token):
        try:
            if action == 'build': plan = v.prepare_base_build(value[0], key, refresh=value[1])
            else: plan = v.base_rollback_inventory(key)
            publish(self.app, self._base_prepared, token, key, action, plan, None)
        except Exception as exc:
            publish(self.app, self._base_prepared, token, key, action, None, c.error_text(exc))

    def _base_prepared(self, token, key, action, plan, error):
        from .base_updates_tui import BaseRollbackScreen
        if not self._alive or self._prepare_token is not token: return
        self._preparing = self._prepare_token = None
        if self.app.screen is not self: return
        if error:
            self.operation_result = error
            self._render_selected(); return
        if action == 'rollback':
            if len(plan.copies) > 1:
                self.app.push_screen(BaseRollbackScreen(plan),
                                     lambda choice: self._confirm_base(key, action, v.select_base_rollback(plan, choice)) if choice is not None else None)
                return
            try: plan = v.select_base_rollback(plan)
            except c.SandboxError as exc:
                self.operation_result = str(exc)
                self._render_selected(); return
        self._confirm_base(key, action, plan)

    def _confirm_base(self, key, action, plan):
        from .base_updates_tui import BaseConsentScreen, rollback_consent
        if not self._alive or self.app._operation_pending: return
        text = v.describe_base_build(plan) if action == 'build' else rollback_consent(plan)
        self.app.push_screen(BaseConsentScreen(text), lambda yes: self._approved_base(key, action, plan) if yes else None)

    def _approved_base(self, key, action, plan):
        if not self._alive or self.app._operation_pending: return
        self.action_cancel_checks()
        self._next('bases', key)
        self.operation_result = None
        self.app.run_base_update_action(key, action, plan, self._base_finished)
        self._render_selected()

    def _base_finished(self, key, result, failed):
        if not self._alive: return
        self.operation_result = result
        self._track(self._inventory_worker('bases', [(key, self._next('bases', key))]))
        self._render_selected()

    def _prepare_action(self, key, action, value=None):
        if not self._alive or self.app._operation_pending or self._preparing: return
        self._prepare_token = token = object()
        self._preparing = self._prepare_action_worker(key, action, value, token)
        self._track(self._preparing)
        self._render_selected()

    @work(thread=True, group="updates-prepare")
    def _prepare_action_worker(self, key, action, value, token):
        from .environment_updates_tui import consent
        try:
            m = c.resolve(key)
            if action == "update": plan = v.prepare_environment_update(m, value)
            elif action == "policy": plan = v.prepare_environment_policy(m, *value)
            elif action == "start": plan = v.prepare_environment_start(m)
            else: plan = v.prepare_checkpoint_action(m, action)
            m = c.resolve(key)
            if v._consent_metadata(m) != plan.metadata:
                raise c.SandboxError("Environment changed while preparing consent; review again")
            publish(self.app, self._action_prepared, token, m, action, plan, consent(m, action, plan), None)
        except Exception as exc:
            publish(self.app, self._action_prepared, token, None, action, None, None, c.error_text(exc))

    def _action_prepared(self, token, m, action, plan, message, error):
        from .environment_updates_tui import EnvironmentConsentScreen
        if not self._alive or self._prepare_token is not token: return
        self._preparing = self._prepare_token = None
        if self.app.screen is not self:
            self.operation_result = "Operation review ended while another screen was open; request the action again."
            self._render_selected()
            return
        if error:
            self.operation_result = error
            self._render_selected()
            return
        self._render_selected()
        self.app.push_screen(EnvironmentConsentScreen(message),
                             lambda yes: self._approved_action(m, action, plan) if yes else None)

    def _approved_action(self, m, action, plan):
        if not self._alive or self.app._operation_pending: return
        self.action_cancel_checks()
        self._next("environments", m["id"])  # old inventory cannot publish across the mutation
        self.operation_result = None
        self.app.run_environment_update_action(m, action, plan, self._environment_action_finished)
        self._render_selected()

    def _environment_action_finished(self, key, result, failed):
        if not self._alive: return
        self.operation_result = result
        self._adopt_current_metadata(key)
        token = self._next("environments", key)
        self._track(self._inventory_worker("environments", [(key, token)]))
        self._render_selected()

    def _adopt_current_metadata(self, key):
        item = self.items["environments"].get(key)
        if item is None: return
        try:
            m = c.resolve(key)
            # Journals/recovery routing are local authoritative metadata, not delayed inventory.
            changed = v._lifecycle(m) != v._lifecycle(item.get("metadata", {})) or m.get("operation") != item.get("metadata", {}).get("operation")
            item.update(metadata=m, name=m["name"], policy=v.policy(m))
            if changed or m.get("operation"): item.update(v.environment_history(m))
            if not m.get("operation"): item.pop("recovery", None)
        except Exception as exc:
            item["error"] = c.error_text(exc)

    def action_details(self):
        from .tui import ReportScreen
        key = self.selected_key()
        if self.view == "environments": self._adopt_current_metadata(key)
        item = self.items[self.view].get(key)
        lines = [VIEWS[self.view]]
        if self.operation_result: lines += ["Last operation result:", self.operation_result, ""]
        base_operation = getattr(self.app, '_base_operation', None)
        if self.view == 'bases' and base_operation and base_operation['distro'] == key:
            lines += ['Base operation (app-owned; Cancel check/Close do not cancel it):',
                      base_operation['phase'], base_operation.get('result') or '',
                      'Bounded build output tail:', base_operation.get('output') or '(no build output)', '']
        if item and self.view == "environments" and item.get("metadata", {}).get("operation"):
            m = item["metadata"]
            lines += [str(c.pending_operation(m)), f"Last operation error: {m.get('last_error') or 'none'}", ""]
        lines += [self.discovery_text(), ""]
        if self.view != "manager": lines += ["Discovery evidence:", json.dumps(self.remote, indent=2), ""]
        else: lines += ['Manager discovery evidence:', json.dumps(self.manager_remote, indent=2), '']
        lines += ["Optional dashboard discovery: " + ("enabled (GitHub + npm, independent sources)" if self.app._discovery_enabled else "off"),
                  "Automatic attempts are daily, failures included. Explicit Check may refresh sooner; Retry-After still applies.",
                  "Automatic discovery never starts containers or runs binary/image probes."]
        if self.app._discovery_status:
            lines += ["Last dashboard scheduling result:", json.dumps(self.app._discovery_status, indent=2)]
        if self.app._manager_discovery_status:
            lines += ['Last manager scheduling result:', json.dumps(self.app._manager_discovery_status, indent=2)]
        notes = self._notices()
        if notes:
            lines += ["Dashboard notices (retained; compact here so controls remain visible):",
                      *[f"{note.title}: {note.message}" for note in notes], ""]
        if item:
            lines.append(json.dumps({k: value for k, value in item.items() if k != "metadata"}, indent=2))
            if self.view == "environments": lines.append(self.item_summary(item))
        if self.inventory_error: lines.append("Local inventory failed: " + self.inventory_error)
        if self.view == "manager":
            lines += [mi.GUIDANCE, 'CLI: opencode-sandbox manager status --check',
                      'Discovery is not target consent or tag-to-commit verification. No replacement is authorized.',
                      'Manager Update stays unavailable until independent exclusion/handoff/replacement/recovery gates pass.']
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
        report = ReportScreen(c.printable("\n".join(lines)), title=f"Updates — {VIEWS[self.view]} — Details")
        report.add_class("updates-details")
        self.app.push_screen(report)

    def action_close(self):
        self._stop_workers()
        self.app.pop_screen()

    def _stop_workers(self):
        self._alive = False
        self._prepare_token = None
        for worker in self._owned: worker.cancel()

    def on_unmount(self):
        self._stop_workers()

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        {"updates-check": self.action_check, "updates-details": self.action_details,
         "updates-cancel": self.action_cancel_checks, "updates-close": self.action_close,
         **{"updates-" + action: lambda action=action: self.action_environment(action)
            for action in ("update", "start", "policy", "rollback", "recover")},
         'updates-base-rollback': lambda: self.action_base('rollback')}.get(event.button.id, lambda: None)()


def plain_lines(text):
    return "\n".join(plain(line) for line in text.splitlines())
