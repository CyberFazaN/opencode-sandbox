"""Git change review screen; writes to original repos only through explicit staging."""
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ItemGrid, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static, TextArea

from . import core as c
from .gitflow import (
    change_summary,
    export_changes,
    inspect_changes,
    review_branch_diff,
    stage_changes,
)


class GitScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close")]
    CSS = """
    #git-panel { width: 96%; height: 95%; padding: 0 1; border: round $accent; }
    #git-panel Horizontal, #git-actions { height: auto; }
    #git-actions { grid-gutter: 0 1; margin: 1 0; }
    #git-actions Button { width: 1fr; }
    #git-preview { height: 1fr; min-height: 5; }
    Input { width: 1fr; }
    #git-status { height: auto; }
    """

    def __init__(self, environment: dict):
        super().__init__()
        self.environment = environment
        self.bundle: Path | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="git-panel"):
            yield Static(f"Changes of {self.environment['name']} (same as: changes show, bundle, stage, branch-diff)")
            with Horizontal():
                yield Input(placeholder="Original repository path", id="git-source",
                            value=str(self.environment.get("source") or ""))
                yield Input(placeholder="Review branch (optional)", id="git-branch")
            with ItemGrid(id="git-actions", min_column_width=21):
                yield Button("Summary", id="git-summary", compact=True)
                yield Button("Bundle & inspect", id="git-export", compact=True)
                yield Button("Stage review branch", id="git-stage", variant="primary", compact=True)
                yield Button("Compare branch", id="git-diff", compact=True)
                yield Button("Close", id="git-close", compact=True)
            yield TextArea("Select Summary or Bundle & inspect", read_only=True, id="git-preview")
            yield Static("Staging creates a separate branch; it does not check it out.", id="git-status")

    def _preview(self, content: str) -> None:
        self.query_one("#git-preview", TextArea).load_text(c.printable(content))  # sandbox content

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action == "git-close":
            self.app.pop_screen()
        elif action == "git-summary":
            self.run_summary()
        elif action == "git-export":
            self.run_export()
        elif action == "git-stage":
            if self.bundle is None:
                self.notify("Create a bundle first (Bundle & inspect)", severity="warning")
                return
            self.run_stage(self.bundle, self.query_one("#git-source", Input).value.strip(),
                           self.query_one("#git-branch", Input).value.strip())
        elif action == "git-diff":
            self.run_diff(self.query_one("#git-source", Input).value.strip(),
                          self.query_one("#git-branch", Input).value.strip())

    @work(thread=True, exclusive=True)
    def run_summary(self) -> None:
        try:
            summary = change_summary(self.environment)
            content = "\n".join(f"{k}:\n{v}" for k, v in summary.items())
            self.app.call_from_thread(self._preview, content)
        except Exception as exc:
            self.app.call_from_thread(self.notify, c.error_text(exc), severity="error")

    @work(thread=True, exclusive=True)
    def run_export(self) -> None:
        try:
            path = export_changes(self.environment)
            info = inspect_changes(path)
            content = f"Bundle: {path}\nBase: {info['base']}\nHead: {info['head']}\n"
            content += f"Untracked: {info['untracked']}\nSymlinks: {info['symlinks']}\n"
            content += "".join(f"Review with care: {line}\n" for line in info["attention"]) + f"\n{info['patch']}"
            self.app.call_from_thread(self._set_export, path, content)
        except Exception as exc:
            self.app.call_from_thread(self.notify, c.error_text(exc), severity="error")

    def _set_export(self, path: Path, content: str) -> None:
        self.bundle = path
        self._preview(content)
        self.notify(f"Bundle: {path.name}")

    @work(thread=True, exclusive=True)
    def run_stage(self, path: Path, source: str, branch: str) -> None:
        try:
            result = stage_changes(path, Path(source), branch or None)
            self.app.call_from_thread(self._stage_done, result)
        except Exception as exc:
            self.app.call_from_thread(self.notify, c.error_text(exc), severity="error")

    def _stage_done(self, result: dict) -> None:
        self.query_one("#git-branch", Input).value = result["branch"]
        self.notify(f"Created {result['branch']} at {result['commit'][:12]}", timeout=12)

    @work(thread=True, exclusive=True)
    def run_diff(self, source: str, branch: str) -> None:
        try:
            if not branch:
                raise c.SandboxError("Enter the review branch name")
            content = review_branch_diff(Path(source), branch)
            self.app.call_from_thread(self._preview, content)
        except Exception as exc:
            self.app.call_from_thread(self.notify, c.error_text(exc), severity="error")
