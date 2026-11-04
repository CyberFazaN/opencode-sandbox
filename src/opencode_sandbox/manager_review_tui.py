"""Exact manager consent; an immutable receipt is not a helper or durable execution grant."""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static, TextArea

from . import core as c
from . import manager_review as review


class ManualUpdateScreen(ModalScreen):
    CSS = """ManualUpdateScreen {align: center middle;}
    ManualUpdateScreen ToastRack {height: 0; max-height: 0; overflow: hidden;}
    #manual-update {width: 94%; height: 90%; border: round $warning; background: $surface; padding: 0 1;}
    #manual-update-text {height: 1fr;} #manual-update Horizontal {height: auto;}"""
    BINDINGS = [Binding('escape', 'cancel', 'Cancel')]
    AUTO_FOCUS = '#manual-update-cancel'

    def __init__(self, message, command):
        super().__init__()
        self.message, self.command = c.printable(message), command

    def compose(self):
        with Vertical(id='manual-update'):
            yield Static('Manual update required', markup=False)
            yield TextArea(self.message, read_only=True, id='manual-update-text')
            with Horizontal():
                yield Button('Cancel', id='manual-update-cancel', compact=True)
                yield Button('Confirm' if self.command else 'Close', id='manual-update-confirm', compact=True)

    def action_cancel(self): self.dismiss()

    def on_button_pressed(self, event):
        event.stop()
        copy = event.button.id == 'manual-update-confirm' and self.command
        self.dismiss()
        if copy: self.app.copy_text(self.command)


class ManagerReviewScreen(ModalScreen[review.Approval | None]):
    CSS = """ManagerReviewScreen {align: center middle;}
    ManagerReviewScreen ToastRack {height: 0; max-height: 0; overflow: hidden;}
    #manager-review {width: 94%; height: 94%; border: round $warning; background: $surface; padding: 0 1;}
    #manager-review-text {height: 1fr;} #manager-review Horizontal {height: auto;}
    #manager-review Checkbox {height: auto;}"""
    BINDINGS = [Binding('escape', 'cancel', 'Cancel')]
    AUTO_FOCUS = '#manager-review-cancel'

    def __init__(self, prepared, *, update=False):
        super().__init__()
        if type(prepared) is not review.Review: raise c.SandboxError('An exact prepared manager review is required')
        self.prepared = prepared
        self.update = update
        self.message = c.printable(review.text(prepared, update=update))

    def compose(self) -> ComposeResult:
        with Vertical(id='manager-review'):
            yield Static('Review Sandbox Manager update' if self.update else 'Review Sandbox Manager — internal fixture, no installation', markup=False)
            yield TextArea(self.message, read_only=True, id='manager-review-text')
            yield Checkbox('I accept this exact target and public-default network policy', id='manager-review-network')
            with Horizontal():
                yield Button('Cancel', id='manager-review-cancel', compact=True)
                yield Button('Update & close' if self.update else 'Confirm review', id='manager-review-confirm', variant='warning', compact=True, disabled=True)

    def action_cancel(self): self.dismiss(None)

    def on_checkbox_changed(self, event: Checkbox.Changed):
        event.stop()
        self.query_one('#manager-review-confirm', Button).disabled = not event.value

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        accepted = event.button.id == 'manager-review-confirm' and self.query_one('#manager-review-network', Checkbox).value
        self.dismiss(review.Approval(self.prepared) if accepted else None)
