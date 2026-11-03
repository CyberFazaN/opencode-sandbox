"""Base-only target/mode selection, explicit copy choice and immutable consent."""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static, TextArea

from . import core as c
from . import distros
from . import opencode_versions as v


class BaseTargetScreen(ModalScreen[tuple | None]):
    CSS = """BaseTargetScreen {align: center middle;}
    BaseTargetScreen ToastRack {height: 0; max-height: 0; overflow: hidden;}
    #base-target-panel {width: 76; max-width: 100%; height: auto; border: round $accent; background: $surface; padding: 0 1;}
    #base-target-panel Horizontal {height: auto;}"""
    BINDINGS = [Binding('escape', 'cancel', 'Cancel')]
    AUTO_FOCUS = '#base-target'

    def __init__(self, distro):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        with Vertical(id='base-target-panel'):
            yield Static(f'Build / Rebuild — {self.distro.name}', markup=False)
            yield Static('OpenCode version (exact 2.x version or latest):', markup=False)
            yield Input(value='latest', id='base-target', compact=True)
            yield Static('Build mode:', markup=False)
            yield Select([('Cached rebuild (reuse eligible layers)', False),
                          ('Refresh & Rebuild (pull + no-cache)', True)],
                         value=False, allow_blank=False, compact=True, id='base-refresh')
            yield Static('Cached: no upstream pull. Refresh: pull and bypass the build cache.\n'
                         f'Both modes always upgrade system packages:\n  {self.distro.build_upgrade}.\n'
                         'Existing environments are unchanged.', markup=False)
            with Horizontal():
                yield Button('Cancel', id='base-target-cancel', compact=True)
                yield Button('Review', id='base-target-review', compact=True)

    def action_cancel(self): self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        self.dismiss((self.query_one('#base-target', Input).value, self.query_one('#base-refresh', Select).value)
                     if event.button.id == 'base-target-review' else None)


class BaseRollbackScreen(ModalScreen[str | None]):
    CSS = """BaseRollbackScreen {align: center middle;}
    BaseRollbackScreen ToastRack {height: 0; max-height: 0; overflow: hidden;}
    #base-copies {width: 94%; height: 92%; border: round $accent; background: $surface; padding: 0 1;}
    #base-copy-text {height: 1fr;} #base-copies Horizontal {height: auto;} #base-copy-error {height: 1;}"""
    BINDINGS = [Binding('escape', 'cancel', 'Cancel')]
    AUTO_FOCUS = '#base-copy'

    def __init__(self, inventory):
        super().__init__()
        self.inventory = inventory

    def compose(self) -> ComposeResult:
        with Vertical(id='base-copies'):
            yield Static(f'Choose rollback copy — {self.inventory.distro}', markup=False)
            yield Static('Several distinct images: explicitly choose a copy; no newest-by-date default.\n'
                         'Aliases of one immutable image are one choice.', markup=False)
            yield Select([(f'{copy.image_id} | OpenCode {copy.version or "Unknown"}', copy.image_id)
                          for copy in self.inventory.copies], prompt='Choose an immutable image', compact=True, id='base-copy')
            yield TextArea('\n'.join(v.format_base_rollback_copies(self.inventory)), read_only=True, id='base-copy-text')
            yield Static('', markup=False, id='base-copy-error')
            with Horizontal():
                yield Button('Cancel', id='base-copy-cancel', compact=True)
                yield Button('Review', id='base-copy-review', compact=True)

    def action_cancel(self): self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.id == 'base-copy-cancel': self.dismiss(None); return
        selected = self.query_one('#base-copy', Select).value
        if selected not in {copy.image_id for copy in self.inventory.copies}:
            self.query_one('#base-copy-error', Static).update('Select an explicit copy before Review.'); return
        self.dismiss(selected)


class BaseConsentScreen(ModalScreen[bool]):
    CSS = """BaseConsentScreen {align: center middle;}
    BaseConsentScreen ToastRack {height: 0; max-height: 0; overflow: hidden;}
    #base-consent {width: 94%; height: 92%; border: round $warning; background: $surface; padding: 0 1;}
    #base-consent-text {height: 1fr;} #base-consent Horizontal {height: auto;}"""
    BINDINGS = [Binding('escape', 'cancel', 'Cancel')]
    AUTO_FOCUS = '#base-cancel'

    def __init__(self, message):
        super().__init__()
        self.message = c.printable(message)

    def compose(self) -> ComposeResult:
        with Vertical(id='base-consent'):
            yield Static('Review Base Images operation — existing environments do not migrate', markup=False)
            yield TextArea(self.message, read_only=True, id='base-consent-text')
            with Horizontal():
                yield Button('Cancel', id='base-cancel', compact=True)
                yield Button('Confirm', id='base-confirm', variant='warning', compact=True)

    def action_cancel(self): self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        self.dismiss(event.button.id == 'base-confirm')


def rollback_consent(plan):
    d = distros.get(plan.distro)
    copy = plan.selected
    definition = copy.definition
    return '\n'.join([
        f'Rollback base image {d.image}', f'Daemon: {plan.endpoint}', f'Current image: {plan.current_id or "missing"}',
        f'Exact selected image: {copy.image_id}', *copy.aliases,
        f'Copy build: {definition.distro} {definition.version}, revision {definition.revision}; OpenCode {copy.version or "Unknown"} (build label).',
        f'Required definition: {d.name} {d.version}, revision {d.revision}.',
        'The copy must pass current OS/tool/OpenCode checks before publication; a legacy copy may be refused.',
        'The replaced current image is kept as a rollback copy. Selected aliases are consumed after the swap.',
        'Existing containers, writable layers, home/workspace/configuration and integrations are unchanged.',
        'Future base-based creation and file-only restores use this base; not-yet-created pins remain enforced.',
        'This is not an upstream package-freshness or security assessment.',
        'Consent is revalidated under shared base guards. Closing the screen never cancels an approved operation.',
    ])
