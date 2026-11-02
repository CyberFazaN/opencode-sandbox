"""Small environment-only forms and scrollable exact consent; not an update executor."""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static, TextArea

from . import core as c
from . import opencode_versions as v


class TargetScreen(ModalScreen[str | None]):
    CSS = "TargetScreen {align: center middle;} TargetScreen ToastRack {height: 0; max-height: 0; overflow: hidden;} #target-panel {width: 74; max-width: 100%; height: auto; border: round $accent; padding: 0 1;} #target-panel Horizontal {height: auto;}"
    BINDINGS = [Binding("escape", "cancel", "Cancel")]
    AUTO_FOCUS = "#update-target"

    def __init__(self, m):
        super().__init__()
        self.environment = m

    def compose(self) -> ComposeResult:
        p = v.policy(self.environment)
        with Vertical(id="target-panel"):
            yield Static(f"Update OpenCode — {self.environment['name']}", markup=False)
            yield Static("Exact 2.x version, or latest supported stable.\nNext: resolve, check eligibility, then review exact consent.", markup=False)
            yield Input(value=p["version"] or "latest", id="update-target", compact=True)
            with Horizontal():
                yield Button("Cancel", id="target-cancel", compact=True)
                yield Button("Review", id="target-review", compact=True)

    def action_cancel(self): self.dismiss(None)

    def on_input_submitted(self): self.dismiss(self.query_one("#update-target", Input).value)

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        self.dismiss(self.query_one("#update-target", Input).value if event.button.id == "target-review" else None)


class PolicyScreen(ModalScreen[tuple | None]):
    CSS = "PolicyScreen {align: center middle;} PolicyScreen ToastRack {height: 0; max-height: 0; overflow: hidden;} #policy-panel {width: 74; max-width: 100%; height: auto; border: round $accent; padding: 0 1;} #policy-panel Horizontal {height: auto;} #policy-error {height: auto; color: $error;}"
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, m):
        super().__init__()
        self.environment = m

    def compose(self) -> ComposeResult:
        p = v.policy(self.environment)
        with Vertical(id="policy-panel"):
            yield Static(f"OpenCode policy — {self.environment['name']}", markup=False)
            yield Select([("Notify", "notify"), ("Manual", "manual"), ("Pinned", "pinned")],
                         value=p["mode"], allow_blank=False, compact=True, id="opencode-policy")
            yield Static("Exact pin (used only for Pinned):", markup=False)
            yield Input(value=p["version"] or "", id="opencode-pin", compact=True)
            yield Static("No installation. Manual/Pinned suppress general newer-version notices,\nnot explicit comparisons. Pins still restrict update/rollback/start.", markup=False)
            yield Static("", id="policy-error", markup=False)
            with Horizontal():
                yield Button("Cancel", id="policy-cancel", compact=True)
                yield Button("Review", id="policy-review", compact=True)

    def action_cancel(self): self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.id == "policy-cancel": self.dismiss(None); return
        mode = self.query_one("#opencode-policy", Select).value
        try:
            pin = v.supported(self.query_one("#opencode-pin", Input).value) if mode == "pinned" else None
        except c.SandboxError as exc:
            self.query_one("#policy-error", Static).update(str(exc)); return
        self.dismiss((mode, pin))


class EnvironmentConsentScreen(ModalScreen[bool]):
    """Full immutable identities stay available at 80x24 without clipping consent buttons."""
    CSS = "EnvironmentConsentScreen {align: center middle;} EnvironmentConsentScreen ToastRack {height: 0; max-height: 0; overflow: hidden;} #environment-consent {width: 92%; height: 92%; border: round $warning; background: $surface; padding: 0 1;} #environment-consent-text {height: 1fr;} #environment-consent Horizontal {height: auto;}"
    BINDINGS = [Binding("escape", "cancel", "Cancel")]
    AUTO_FOCUS = "#environment-cancel"

    def __init__(self, message):
        super().__init__()
        self.message = c.printable(message)

    def compose(self) -> ComposeResult:
        with Vertical(id="environment-consent"):
            yield Static("Review environment operation — no automatic installation", markup=False)
            yield TextArea(self.message, read_only=True, id="environment-consent-text")
            with Horizontal():
                yield Button("Cancel", id="environment-cancel", compact=True)
                yield Button("Confirm", id="environment-confirm", variant="warning", compact=True)

    def action_cancel(self): self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        self.dismiss(event.button.id == "environment-confirm")


def consent(m, action, plan):
    lines = [f"{action.capitalize()} — {m['name']} [{m['id']}]", ""]
    if action == "update":
        lines += [f"Install exact OpenCode {plan.target} (not a moving latest target).",
                  "Requires an existing stopped, owned, network-enabled container; pins still apply.",
                  "Download from npm. Temporarily start for the update, verify the binary, then stop.",
                  "First commit the complete system layer as a checkpoint. Failure rolls back to it.",
                  "Successful update keeps that checkpoint for explicit rollback."]
        lines += [f"{key}: {value}" for key, value in plan.identity]
    elif action in ("rollback", "recover"):
        lines += [f"Exact checkpoint: {plan.checkpoint}", f"Immutable image: {plan.checkpoint_id}",
                  f"Recorded binary: {plan.previous_version or 'Unknown'} -> {plan.target or 'Unknown'} (not a runtime check).",
                  "Restore the ENTIRE checkpointed system layer, not only the OpenCode binary."]
        if action == "rollback": lines += ["Keep the present system layer as a snapshot first (including later changes)."]
        else: lines += ["Interrupted update: roll back, never guess whether npm completed.",
                        "Stop/remove any owned current container; unfinished update-layer changes are discarded."]
        lines += ["Final state: no running container; explicit Start recreates it from the checkpoint.",
                  f"Daemon: {plan.endpoint}", f"Container identity: {plan.identity}"]
    elif action == "policy":
        old = v.policy(m)
        lines += [f"Policy: {old['mode']} {old['version'] or ''} -> {plan.mode} {plan.version or ''}",
                  "Change policy/pin only; no install, start, network-setting change or journal clearing.",
                  "Notify permits general newer-version notices; Manual/Pinned suppress them.",
                  "Explicit comparisons remain available. A pin still restricts execution/creation."]
    elif action == "start":
        lines += ["Explicitly Start this environment. It remains running afterward.",
                  "May create its container and apply pending first-start integrations once.",
                  "Existing ownership, direct-workspace, profile, pin and journal checks still apply.",
                  "Fresh version verification is a separate explicit Check; no automatic stop."]
    lines += ["", "Persistent home, workspace and user OpenCode configuration are not rolled back or replaced.",
              "Binary rollback cannot undo application-data changes or guarantee backward compatibility.",
              "Confirmation is revalidated before mutation. Close/Cancel check never cancels an approved mutation.",
              "If the manager is killed, inspect its journal and use the indicated recovery command."]
    return "\n".join(lines)
