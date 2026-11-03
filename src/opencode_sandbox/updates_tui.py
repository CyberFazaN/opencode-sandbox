"""Updates: compact component views, owned checks and exact lifecycle consent."""
import json
import time

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    LoadingIndicator,
    Static,
    Tab,
    Tabs,
)
from textual.widgets.data_table import CellDoesNotExist

from . import __version__, distros, updates
from . import core as c
from . import manager_installation as mi
from . import manager_releases as mr
from . import opencode_versions as v
from . import update_cache as cache
from .tui_runtime import publish, work

VIEWS = {"manager": "Manager", "bases": "Base Images", "environments": "Environments"}


def plain(value):
    return c.printable(str(value)).replace("\n", " ").replace("\t", " ")


class UpdatesScreen(Screen):
    # Reserve inline feedback instead of letting toasts cover compact-terminal controls.
    CSS = """UpdatesScreen {align: center middle;}
    UpdatesScreen ToastRack {height: 0; max-height: 0; margin: 0; overflow: hidden;}
    #updates-panel {width: 100%; max-width: 120; height: 1fr; border: round $accent; padding: 0 1;}
    #updates-title {height: 1; text-style: bold;}
    #updates-tabs Tab.-active {color: $accent; text-style: bold;}
    #updates-discovery {height: 2; text-wrap: nowrap; text-overflow: ellipsis;}
    #updates-table {height: 1fr; min-height: 3;}
    #updates-manager {height: 1fr; min-height: 3; padding: 1 2; border: round $foreground 20%;}
    #updates-selected {height: 3; text-wrap: nowrap; text-overflow: ellipsis;}
    #updates-list-tools {height: 1;} #updates-hint {width: 1fr; color: $text-muted; background: $background;}
    #updates-check-all {width: 13; min-width: 13;}
    #updates-progress {height: 2;} #updates-spinner {width: 4; height: 1;}
    #updates-reason {width: 1fr; height: 2; text-wrap: nowrap; text-overflow: ellipsis;}
    #updates-reason.running {color: $warning;} #updates-reason.failed {color: $error;}
    #updates-reason.succeeded {color: $success;}
    #updates-buttons, #updates-environment-buttons, #updates-base-buttons {height: auto;}
    #updates-buttons Button, #updates-environment-buttons Button, #updates-base-buttons Button {width: 16; min-width: 10;}
    #updates-close {dock: right;}
    """
    BINDINGS = [Binding("escape", "close", "Close"), Binding("c", "check", "Check"),
                Binding('C', 'check_all', 'Check all'), Binding("d", "details", "Details"),
                Binding("1", "view('manager')", "Manager", show=False),
                Binding("2", "view('bases')", "Bases", show=False), Binding("3", "view('environments')", "Environments", show=False),
                Binding("u", "environment('update')", "Update"), Binding('f5', "environment('start')", 'Start', key_display='F5'),
                Binding('f6', "environment('stop')", 'Stop', key_display='F6'),
                Binding("p", "environment('policy')", "Policy", show=False), Binding("r", "environment('rollback')", "Rollback", show=False),
                Binding("e", "environment('recover')", "Recover", show=False), Binding("b", "base('build')", "Build/Rebuild", show=False)]
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
        self.operation_failed = False
        self._check_result = None
        self._batch_remaining = set()
        self._batch_errors = []
        self._batch_verified = 0
        self._batch_unavailable = []
        self._clipboard_message = None

    def compose(self) -> ComposeResult:
        with Vertical(id="updates-panel"):
            yield Static("Updates", id="updates-title", markup=False)
            yield Tabs(Tab("1 Manager", id="manager"), Tab("2 Base Images", id="bases"),
                       Tab("3 Environments", id="environments"), id="updates-tabs")
            yield Static("", id="updates-discovery", markup=False)
            with Horizontal(id='updates-list-tools', classes='bar'):
                yield Static('', id='updates-hint', markup=False)
                yield Button('Check All', id='updates-check-all', compact=True)
            yield Static('', id='updates-manager', markup=False)
            yield DataTable(id="updates-table", cursor_type="row")
            yield Static("", id="updates-selected", markup=False)
            with Horizontal(id='updates-progress'):
                yield LoadingIndicator(id='updates-spinner')
                yield Static("", id="updates-reason", markup=False)
            with Horizontal(id="updates-buttons", classes="bar"):
                yield Button("Check", id="updates-check", compact=True)
                yield Button("Details", id="updates-details", compact=True)
                yield Button("Update", id="updates-update", compact=True, disabled=True)
                yield Button("Close", id="updates-close", compact=True)
            with Horizontal(id="updates-environment-buttons", classes="bar"):
                for label, action in (("Policy", "policy"), ("Rollback", "rollback"), ("Recover", "recover")):
                    yield Button(label, id="updates-" + action, compact=True)
            with Horizontal(id="updates-base-buttons", classes="bar"):
                yield Button('Rollback', id='updates-base-rollback', compact=True)
        footer = Footer(show_command_palette=False)
        footer.compact = True
        yield footer

    def on_mount(self):
        self._alive = True
        self.items["manager"]["manager"] = {"name": "opencode-sandbox", "state": "installed",
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
        self.query_one('#updates-check').focus()
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
        self._render_selected()

    def _notices(self):
        notes = list(self.app._notifications)
        for _summary, note in self.app._advisories.values():
            if note not in notes: notes.append(note)
        return notes

    def _render_notices(self):
        count = len(self._notices())
        self.query_one("#updates-title", Static).update(
            "Updates" + (f" | {count} dashboard notice(s): Details" if count else ""))

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

    def _inspect(self, section, key, *, check, expected=None):
        try:
            if section == 'manager':
                installation = mi.classify()
                return {'installation': installation, 'state': installation['classification']}
            if section == "bases": return updates.base_inventory(distros.get(key), check=check)
            from . import environment_checks
            m = c.resolve(key)
            policy = v.policy(m)
            result = environment_checks.check(m, expected=expected) if check else v.environment_version(m, check=False)
            notice = environment_checks.cleanup_notice(m)
            return {"name": m["name"], "metadata": m, "policy": policy, **result,
                    **({'cleanup': notice} if notice else {})}
        except Exception as exc:
            if section == 'environments' and check:
                try:
                    m = c.resolve(key)
                    return {**v.environment_version(m, check=False), 'error': c.error_text(exc)}
                except Exception:
                    return {'state': 'unknown', 'error': c.error_text(exc)}
            return {"error": c.error_text(exc)}

    def _receive(self, section, key, token, item, checked):
        if not self._alive or self._generation.get((section, key)) is not token: return
        previous = self.items[section][key]
        if section != 'manager' and item.get("error") and "verification" not in item:
            item["verification"] = "history-unverified" if previous.get("verification") == "history-unverified" else "last-verified"
            if previous.get("state") == "inspecting local image…": item["state"] = "unknown"
        if not item.get("error"): previous.pop("error", None)
        if not item.get('cleanup'): previous.pop('cleanup', None)
        if "state" in item and not item.get("recovery"): previous.pop("recovery", None)
        self.items[section][key].update(item)
        if section == "environments": self._adopt_current_metadata(key)
        if checked:
            self._active.pop((section, key), None)
            self.items[section][key].pop("checking", None)
            self.items[section][key].pop("notice", None)
            if not item.get("error"): self.items[section][key].pop("error", None)
            self._batch_remaining.discard((section, key))
            if item.get('error'): self._batch_errors.append(self.items[section][key]['name'])
            elif section == 'manager' or item.get('verification') == 'verified': self._batch_verified += 1
            else: self._batch_unavailable.append(self.items[section][key]['name'])
            if not self._batch_remaining:
                self._check_result = ('Installation check failed — Details' if self._batch_errors else 'Installation check complete — Details') \
                    if section == 'manager' else self._check_summary()
        self._render_view()

    def _check_summary(self):
        return (f'Check complete — {self._batch_verified} verified, {len(self._batch_errors)} failed, '
                f'{len(self._batch_unavailable)} unavailable. Details for evidence/errors.')

    def selected_key(self):
        if self.view == 'manager': return 'manager'
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
            if self._preparing:
                self._preparing.cancel()
                self._preparing = self._prepare_token = None
            self.selection[self.view] = self.selected_key()
            self.view = view
            self.query_one("#updates-tabs", Tabs).active = view
            self.query_one("#updates-table", DataTable).clear()
            self._render_view()
        self.query_one('#updates-check' if view == 'manager' else '#updates-table').focus()

    def _render_view(self):
        table = self.query_one("#updates-table", DataTable)
        table.display = self.view != 'manager'
        self.query_one('#updates-manager').display = self.view == 'manager'
        self.query_one('#updates-selected').display = self.view != 'manager'
        self.query_one('#updates-list-tools').display = self.view != 'manager'
        previous = self.selected_key() or self.selection.get(self.view)
        table.clear(columns=True)
        width = max(50, min(self.size.width, 120) - 10)
        table.add_column({'manager': 'Manager', 'bases': 'Base Image', 'environments': 'Environment'}[self.view], width=width * 35 // 100)
        table.add_column('State', width=width * 30 // 100)
        table.add_column('Version' if self.view == 'manager' else 'OpenCode Version', width=width - width * 35 // 100 - width * 30 // 100)
        for key, item in self.items[self.view].items():
            evidence = item.get("version") or "Unknown"
            if item.get('verification') in ('last-verified', 'history-unverified') and item.get('version'): evidence += ' (cached)'
            state = "checking…" if item.get("checking") else item.get("state", "unknown")
            if item.get("error"): state += "; check failed"
            table.add_row(*(Text(plain(x)) for x in (item["name"], state, evidence)), key=key)
            if key == previous: table.move_cursor(row=table.row_count - 1)
        self._render_selected()

    def discovery_text(self):
        if self.view == 'manager':
            state = self.manager_remote
            success, attempt = state.get('success'), state.get('attempt')
            text = (f"Available manager: {success['value']} (GitHub; checked {cache.when(success['at'])}"
                    + ')'
                    + ('; stale' if state.get('stale') else '')) if success else 'GitHub: never checked; availability unknown'
            if ('github',) in self._active: return text + '\nChecking published manager releases…'
            worker = self.app._manager_discovery_worker_ref
            if self.app._discovery_enabled and worker is not None and not worker.is_finished:
                return text + '\nDashboard checking GitHub…'
            if self._manager_notice: return text + '\n' + self._manager_notice
            if attempt and not attempt['ok']: return text + '\nCheck failed: ' + attempt['error']
            return text
        success, attempt = self.remote.get("success"), self.remote.get("attempt")
        stale = self.remote.get("stale") or bool(success and time.time() - success["at"] >= 86400)
        text = (f"Available OpenCode: {success['value']} (npm; checked {cache.when(success['at'])})"
                + ("; stale" if stale else "")) if success else "npm: never checked; availability unknown"
        if ("npm",) in self._active: return text + "\nChecking available version on npm…"
        worker = self.app._discovery_worker_ref
        if self.app._discovery_enabled and worker is not None and not worker.is_finished:
            return text + "\nDashboard checking npm…"
        if self._discovery_notice: return text + "\n" + self._discovery_notice
        if attempt and not attempt["ok"] and attempt.get("error") == "check did not complete":
            return text + "\nLast npm attempt did not complete; explicit Check can retry."
        if attempt and not attempt["ok"]: return text + "\nCheck failed: " + attempt["error"]
        return text

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
            text = '\n\n'.join([f'opencode-sandbox   {__version__}', mr.comparison(__version__, self.manager_remote.get('release')),
                              'Installation: ' + (installation['classification'] if installation else 'inspecting local evidence…'),
                               'Release notes and installation evidence: Details.'])
            if item and item.get('error'): text += '\nLocal check failed: ' + item['error']
            self.query_one('#updates-manager', Static).update(plain_lines(text))
        elif item is None:
            text = "No environments listed." + (f"\nLocal inventory failed: {self.inventory_error}" if self.inventory_error else "")
            check_reason = "No selected object; Check can refresh availability."
        else:
            lines = [item['name']]
            if self.view == "environments":
                policy = item.get('policy') or {}
                lines.append('Policy: ' + policy.get('mode', 'unknown') + (' ' + policy['version'] if policy.get('version') else ''))
                if item.get('version') and self.remote.get('success'):
                    lines.append(v.describe(item['version'], self.remote['success']['value']))
                if item.get("recovery"): lines.append(item["recovery"])
                if item.get('cleanup'): lines.append(item['cleanup'])
                elif item.get('verification') == 'history-unverified': lines.append('Container identity unverified — Details')
            else:
                if item.get("version") and self.remote.get("success"):
                    lines.append(v.describe(item["version"], self.remote["success"]["value"]))
                if not item.get("eligible"): check_reason = "Image probe unavailable: managed ownership/provenance not verified."
            if item.get("error"): lines = [*lines[:2], "Check failed: " + item["error"]]
            elif item.get('notice'): lines = [*lines[:2], item['notice']]
            text = "\n".join(lines[-3:])
        self.query_one("#updates-selected", Static).update(plain_lines(text))
        reason = check_reason or ""
        reason += "\n" + {"manager": 'Check releases, then Update for automatic review or manual guidance.',
                            "bases": "Rebuild changes the base for future containers, not existing environments.",
                            "environments": "F5 Start / F6 Stop. Update finishes stopped; no automatic restart."}[self.view]
        if self._check_result: reason = self._check_result
        failed = bool(self._batch_errors and self._check_result)
        source = self.manager_remote if self.view == 'manager' else self.remote
        request = ('github',) if self.view == 'manager' else ('npm',)
        if self._check_result and request not in self._active and (source.get('attempt') or {}).get('ok') is False:
            reason = 'Availability check failed. ' + reason
            failed = True
        if self.operation_result:
            reason = ('Failed — ' if self.operation_failed else 'Complete — ') + plain(self.operation_result)
            failed = self.operation_failed
        if self._clipboard_message: reason = self._clipboard_message
        if self._preparing: reason = "Preparing review…"
        elif self._batch_remaining: reason = f'Inspecting installed versions… {len(self._batch_remaining)} remaining'
        base_operation = getattr(self.app, '_base_operation', None)
        if self.view == 'bases' and base_operation and base_operation['distro'] == key:
            reason = (base_operation.get('result') or base_operation['phase']) + '\nBuild output / full result: Details.'
            failed = base_operation.get('failed', False)
        if self.app._operation_pending:
            active_base = self.view == 'bases' and base_operation and base_operation['distro'] == key and not base_operation.get('result')
            reason = (base_operation['phase'] if active_base else 'An operation is running.') + '\nClose returns to the dashboard; approved work continues.'
        busy = bool(self._active or self._preparing or self.app._operation_pending)
        status = self.query_one('#updates-reason', Static)
        status.update(reason.strip())
        status.set_class(busy, 'running')
        status.set_class(not busy and failed, 'failed')
        status.set_class(not busy and not failed and bool(self.operation_result or self._check_result)
                         and not (self._batch_unavailable and not self.operation_result), 'succeeded')
        self.query_one('#updates-spinner').display = busy
        button = self.query_one("#updates-check", Button)
        button.disabled = bool(self._preparing or self.app._operation_pending or (self.view, key) in self._active or self._batch_remaining)
        button.tooltip = ('Read published GitHub releases and independently inspect local installation; no pipx execution'
                          if self.view == 'manager' else check_reason or "Check npm availability and inspect the selected installed binary")
        all_button = self.query_one('#updates-check-all', Button)
        all_button.disabled = bool(self._active or self._preparing or self.app._operation_pending) or not self.items[self.view]
        all_button.tooltip = 'Check available OpenCode on npm once and inspect all listed installed versions'
        self.query_one('#updates-hint', Static).update('Checking may temporarily start stopped environments.' if self.view == 'environments'
                                                       else 'Check inspects installed OpenCode; availability comes from npm.')
        controls = self.query_one("#updates-environment-buttons")
        controls.display = self.view == "environments"
        self.query_one('#updates-base-buttons').display = self.view == 'bases'
        blocked = self.view != "environments" or item is None or bool(self._preparing or self._batch_remaining) or self.app._operation_pending
        for action in ("update", "policy", "rollback", "recover"):
            button = self.query_one("#updates-" + action, Button)
            button.disabled = blocked or bool(item and item.get("metadata", {}).get("operation") and action != "recover")
            button.tooltip = reason.strip() if button.disabled else f"Review {action} for the selected environment; no mutation before confirmation"
        update = self.query_one('#updates-update', Button)
        update.label = ('Build' if item and item.get('state') == 'not built' else 'Rebuild') if self.view == 'bases' else 'Update'
        if self.view == 'bases':
            update.disabled = item is None or bool(self._preparing or self._batch_remaining) or self.app._operation_pending
            update.tooltip = 'Review live base identity, exact target and cached/full-refresh mode before building'
        elif self.view == 'manager':
            manager_reason = mi.update_reason((item or {}).get('installation'), self.manager_remote.get('release'))
            update.disabled = not mi.newer_release(self.manager_remote.get('release')) or bool(self._preparing or self._batch_remaining) or self.app._operation_pending
            update.tooltip = manager_reason or 'Prepare a fresh exact source/tool/installation review; no installation before explicit consent and clean exit'
        self.query_one('#updates-base-rollback', Button).disabled = self.view != 'bases' or bool(self._preparing or self._batch_remaining) or self.app._operation_pending
        self.refresh_bindings()

    def clipboard_feedback(self, message):
        self._clipboard_message = message
        self._render_selected()
        self.set_timer(3, self._clear_clipboard_feedback)

    def _clear_clipboard_feedback(self):
        self._clipboard_message = None
        if self._alive: self._render_selected()

    def check_action(self, action, parameters):
        if action == 'check_all': return self.view != 'manager'
        if action == 'environment' and parameters and parameters[0] in ('start', 'stop', 'policy', 'recover'):
            return self.view == 'environments'
        return True

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        event.stop()
        if self._alive: self._render_selected()

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        event.stop()
        if self.app.screen is self: self.action_details()

    def action_check(self):
        if self.app.screen is not self or self._preparing or self.app._operation_pending or self._batch_remaining: return
        self.operation_result = None
        self._check_result = None
        self._batch_errors = []
        self._batch_verified = 0
        self._batch_unavailable = []
        if self.view == 'manager':
            if ('github',) not in self._active:
                self._active[('github',)] = self._manager_release_worker()
                self._track(self._active[('github',)])
            if ('manager', 'manager') not in self._active:
                token = self._next('manager', 'manager')
                self.items['manager']['manager']['checking'] = True
                self._batch_remaining.add(('manager', 'manager'))
                self._active['manager', 'manager'] = self._check_worker('manager', 'manager', token)
                self._track(self._active['manager', 'manager'])
            self._render_view()
            return
        key = self.selected_key()
        self._begin_checks(self.view, [key] if key else [])

    def _begin_checks(self, section, keys, expected=None):
        if not self._alive or self.app._operation_pending or self._batch_remaining: return
        self.operation_result = self._check_result = None
        self._batch_errors = []
        self._batch_verified = 0
        self._batch_unavailable = []
        # One npm waiter per screen; the provider also coalesces CLI/background callers.
        if ("npm",) not in self._active:
            self._active[("npm",)] = self._registry_worker()
            self._track(self._active[("npm",)])
        for key in keys:
            item = self.items[section].get(key)
            if item is None: continue
            # Cached eligibility may predate a build/removal (or initial inventory). The fresh
            # base inventory verifies provenance before it decides whether to run a helper.
            token = self._next(section, key)
            item['checking'] = True
            self._batch_remaining.add((section, key))
            self._active[section, key] = self._check_worker(section, key, token, (expected or {}).get(key))
            self._track(self._active[section, key])
        if not self._batch_remaining: self._check_result = self._check_summary()
        self._render_view()

    def action_check_all(self):
        if self.view == 'manager' or self.app.screen is not self or self._active or self._preparing or self.app._operation_pending: return
        keys = list(self.items[self.view])
        if self.view == 'bases':
            self._begin_checks('bases', keys)
            return
        self._prepare_token = token = object()
        self._preparing = self._batch_review_worker(keys, token)
        self._track(self._preparing)
        self._render_selected()

    @work(thread=True, group='updates-batch-review')
    def _batch_review_worker(self, keys, token):
        from . import environment_checks
        try: publish(self.app, self._batch_reviewed, token, *environment_checks.review(keys), None)
        except Exception as exc: publish(self.app, self._batch_reviewed, token, None, None, c.error_text(exc))

    def _batch_reviewed(self, token, targets, stopped, error):
        from .environment_updates_tui import EnvironmentConsentScreen
        if not self._alive or self._prepare_token is not token: return
        self._preparing = self._prepare_token = None
        if self.app.screen is not self: return
        if error:
            self.operation_result, self.operation_failed = error, True
            self._render_selected()
            return
        if stopped:
            message = ('Check All installed OpenCode versions?\n\n'
                       f'{len(stopped)} stopped environment(s) will be temporarily started, inspected and stopped again:\n'
                       + '\n'.join(stopped) + '\n\nAlready-running environments stay running. No new containers or integrations are created. '
                       'If state or identity changes after this review, that check is refused.')
            self.app.push_screen(EnvironmentConsentScreen(message),
                                 lambda yes: self._begin_checks('environments', list(targets), targets) if yes else None)
        else: self._begin_checks('environments', list(targets), targets)
        self._render_selected()

    @work(thread=True, group="updates-check")
    def _check_worker(self, section, key, token, expected=None):
        item = self._inspect(section, key, check=True, expected=expected)
        if section == 'environments' and self.app.is_running:
            from . import environment_checks
            notice = environment_checks.cleanup_notice({'id': key, 'name': self.items[section][key]['name']})
            # Cleanup failures must survive screen closure/cancellation, unlike ordinary results.
            try:
                self.app.call_from_thread(self.app._replace_advisory, 'version-check-' + key,
                                          'Temporary check needs attention' if notice else None,
                                          title='Temporary-check cleanup', detail=notice or '')
            except RuntimeError:
                if self.app.is_running: raise
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

    def _cancel_readonly(self):
        """Internal invalidation only; there is deliberately no user-facing Cancel Check action."""
        if self._preparing:
            self._preparing.cancel()
            self._preparing = self._prepare_token = None
        for request, worker in self._active.items():
            worker.cancel()
            if len(request) == 2:
                section, key = request
                self._next(section, key)
                self.items[section][key].pop("checking", None)
        self._active.clear()
        self._batch_remaining.clear()

    def action_environment(self, action):
        if self.view == 'manager' and action == 'update':
            self.action_manager_update(); return
        if self.view == 'bases' and action in ('update', 'rollback'):
            self.action_base('build' if action == 'update' else 'rollback'); return
        from .environment_updates_tui import PolicyScreen, TargetScreen
        if self.view != "environments" or self.app.screen is not self or self.app._operation_pending or self._preparing or self._batch_remaining: return
        key = self.selected_key()
        if key is None: return
        try:
            m = c.resolve(key)
            if m.get("operation") and action not in ('recover', 'stop'): raise c.pending_operation(m)
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
            self.operation_failed = True
            self._render_selected()

    def action_manager_update(self):
        if not self._alive or self.app.screen is not self or self.app._operation_pending or self._preparing or self._batch_remaining: return
        release = self.manager_remote.get('release')
        if not mi.newer_release(release): return
        self._prepare_token = token = object()
        self._preparing = self._prepare_manager_worker(release, token)
        self._track(self._preparing)
        self._render_selected()

    @work(thread=True, group='updates-manager-review')
    def _prepare_manager_worker(self, release, token):
        from . import manager_review
        try:
            reason = mi.update_reason(mi.classify(), release)
            if reason:
                publish(self.app, self._manual_prepared, token, *mi.manual_update(release, reason))
            else:
                try: prepared = manager_review.prepare(release['tag'])
                except Exception as exc:
                    publish(self.app, self._manual_prepared, token, *mi.manual_update(release, 'Automatic update review unavailable: ' + c.error_text(exc)))
                else: publish(self.app, self._manager_prepared, token, prepared, None)
        except Exception as exc: publish(self.app, self._manager_prepared, token, None, c.error_text(exc))

    def _manual_prepared(self, token, message, command):
        from .manager_review_tui import ManualUpdateScreen
        if not self._alive or self._prepare_token is not token: return
        self._preparing = self._prepare_token = None
        self._render_selected()
        if self.app.screen is self: self.app.push_screen(ManualUpdateScreen(message, command))

    def _manager_prepared(self, token, prepared, error):
        from .manager_review_tui import ManagerReviewScreen
        if not self._alive or self._prepare_token is not token: return
        self._preparing = self._prepare_token = None
        if self.app.screen is not self: return
        if error:
            self.operation_result = error
            self.operation_failed = True
            self._render_selected(); return
        self._render_selected()
        self.app.push_screen(ManagerReviewScreen(prepared, update=True), self._manager_approved)

    def _manager_approved(self, approval):
        if approval is None or not self._alive or self.app.screen is not self or self.app._operation_pending: return
        self._cancel_readonly()
        self.app.pop_screen()
        self.app.run_manager_update(approval)

    def action_base(self, action):
        from .base_updates_tui import BaseTargetScreen
        if self.view != 'bases' or self.app.screen is not self or self.app._operation_pending or self._preparing or self._batch_remaining: return
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
            self.operation_failed = True
            self._render_selected(); return
        if action == 'rollback':
            if len(plan.copies) > 1:
                self.app.push_screen(BaseRollbackScreen(plan),
                                     lambda choice: self._confirm_base(key, action, v.select_base_rollback(plan, choice)) if choice is not None else None)
                return
            try: plan = v.select_base_rollback(plan)
            except c.SandboxError as exc:
                self.operation_result = str(exc)
                self.operation_failed = True
                self._render_selected(); return
        self._confirm_base(key, action, plan)

    def _confirm_base(self, key, action, plan):
        from .base_updates_tui import BaseConsentScreen, rollback_consent
        if not self._alive or self.app._operation_pending: return
        text = v.describe_base_build(plan) if action == 'build' else rollback_consent(plan)
        self.app.push_screen(BaseConsentScreen(text), lambda yes: self._approved_base(key, action, plan) if yes else None)

    def _approved_base(self, key, action, plan):
        if not self._alive or self.app._operation_pending: return
        self._cancel_readonly()
        self._next('bases', key)
        self.operation_result = None
        self.app.run_base_update_action(key, action, plan, self._base_finished)
        self._render_selected()

    def _base_finished(self, key, result, failed):
        if not self._alive: return
        self.operation_result = result
        self.operation_failed = failed
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
            if action == "update": plan = v.prepare_environment_update(m, value[0], stop_running=True, system_packages=value[1])
            elif action == "policy": plan = v.prepare_environment_policy(m, *value)
            elif action == "start": plan = v.prepare_environment_start(m)
            elif action == 'stop': plan = v.prepare_environment_stop(m)
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
            self.operation_failed = True
            self._render_selected()
            return
        self._render_selected()
        from . import preferences
        if action == 'stop' and not preferences.read()['confirm_stop']:
            self._approved_action(m, action, plan)
        else:
            self.app.push_screen(EnvironmentConsentScreen(message, caution=action == 'update' and plan.running),
                                 lambda yes: self._approved_action(m, action, plan) if yes else None)

    def _approved_action(self, m, action, plan):
        if not self._alive or self.app._operation_pending: return
        self._cancel_readonly()
        self._next("environments", m["id"])  # old inventory cannot publish across the mutation
        self.operation_result = None
        self.app.run_environment_update_action(m, action, plan, self._environment_action_finished)
        self._render_selected()

    def _environment_action_finished(self, key, result, failed):
        if not self._alive: return
        self.operation_result = result
        self.operation_failed = failed
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
            lines += ['Base operation (app-owned; closing this screen does not cancel it):',
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
                       'Update performs a fresh exact review, then exits for an independent frozen helper after terminal restoration.',
                       'Only verified official-tag pipx/default settings are supported; custom installer/network settings require manual preservation.',
                       'No automatic restart/rollback; private verify-only recovery instructions are printed before mutation.']
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
                      "History is not proof that the current binary is unchanged. Explicit Check may temporarily start stopped containers.",
                      *[f"CLI: opencode-sandbox {cmd} {m['id']}" for cmd in
                        ("start", "opencode status", "opencode update", "opencode policy", "opencode rollback", "opencode update-recover")],
                      "F5 Start leaves it running; F6 Stop stops it. Update requires an existing network-enabled container, and finishes stopped.",
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
        self._cancel_readonly()
        for worker in self._owned: worker.cancel()

    def on_unmount(self):
        self._stop_workers()

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        {"updates-check": self.action_check, "updates-details": self.action_details,
         'updates-check-all': self.action_check_all, "updates-close": self.action_close,
         **{"updates-" + action: lambda action=action: self.action_environment(action)
            for action in ("update", "start", "policy", "rollback", "recover")},
         'updates-base-rollback': lambda: self.action_base('rollback')}.get(event.button.id, lambda: None)()


def plain_lines(text):
    return "\n".join(plain(line) for line in text.splitlines())
