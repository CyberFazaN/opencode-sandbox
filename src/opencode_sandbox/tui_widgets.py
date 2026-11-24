"""Shared dialog layout and control styles."""
from textual.containers import VerticalScroll
from textual.content import Content
from textual.widgets import Checkbox


class FormBody(VerticalScroll, can_focus=False):
    """Scroll to fields as they receive focus without adding a Tab stop."""

    DEFAULT_CSS = """
    FormBody { height: auto; max-height: 78vh; scrollbar-size-vertical: 1; }
    """


class FormCheckbox(Checkbox):
    """Keep the checked state legible when a terminal flattens colors."""

    def render(self) -> Content:
        mark = "[x]" if self.value else "[ ]"
        return Content.assemble(
            (mark, self.get_visual_style("toggle--button")),
            " ",
            self.label.stylize_before(self.get_visual_style("toggle--label")),
        )


DIALOG_CSS = """
ModalScreen { background: $background 82%; }
.form-title { text-style: bold; }
.form-hint { color: $text-muted; }
.dialog-actions { height: auto; margin-top: 1; }
.dialog-actions Button:focus { text-style: bold underline; }
.dialog-grid { height: auto; grid-gutter: 0 1; }
.dialog-grid Button { width: 1fr; }
.dialog-fields Input { background: $panel; padding: 0 1; }
.dialog-fields Select > SelectCurrent { background: $panel; padding: 0 1; }
.dialog-fields Select.-expanded > SelectCurrent,
.dialog-fields Select:focus > SelectCurrent,
.dialog-fields Input:focus,
.dialog-fields Checkbox:focus {
    background: $primary;
    color: $text;
    text-style: bold underline;
}
.dialog-fields Select:focus > SelectCurrent Static,
.dialog-fields Select.-expanded > SelectCurrent Static { color: $text; }
.dialog-fields SelectOverlay {
    max-height: 7;
    constrain: inside inside;
    border: round $accent;
    background: $panel;
    scrollbar-size-vertical: 1;
}
.dialog-fields SelectOverlay > .option-list--option-highlighted {
    background: $primary;
    color: $text;
    text-style: bold underline;
}
.dialog-fields Checkbox { height: auto; padding: 0 1; background: $panel; }
.dialog-fields Checkbox > .toggle--button { color: $foreground; background: $panel; }
.dialog-fields Checkbox.-on > .toggle--button { color: $text-success; }
.dialog-fields Checkbox:focus > .toggle--label {
    color: $text;
    background: $primary;
    text-style: bold underline;
}
"""
