"""Project creation: both modes, shared preview, cancellation and error handling."""
import pytest
from test_git_import import git
from test_git_import import repo as _repo
from test_tui import fake_runtime as _fake_runtime
from test_tui import run, settle, stack
from textual.widgets import Button, Select, TextArea

from opencode_sandbox import core as c
from opencode_sandbox import git_import as gi

repo, fake_runtime = _repo, _fake_runtime  # register shared fixtures


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
def test_working_import_preview_cancel_and_create(repo, size):
    (repo / "modified").write_text("staged"); git(repo, "add", "modified")
    (repo / "modified").write_text("working")
    plan = gi.preview(repo)
    async def t(app, pilot):
        await pilot.press("n")
        form = app.screen
        assert form.query_one("#git-working-changes", Select).value is False
        form.query_one("#name").value = "ocs-qa-working"
        form.query_one("#source").value = str(repo)
        form.query_one("#git-working-changes", Select).value = True
        await settle(pilot)
        form.query_one("#create", Button).press()
        await settle(pilot, .5)
        assert stack(app)[-1] == "GitImportPreviewScreen"
        assert app.screen.query_one(TextArea).text == plan.describe()
        for bid in ("#import-cancel", "#import-confirm"):
            region = app.screen.query_one(bid).region
            assert region.width > 0 and region.bottom <= size[1] and region.right <= size[0]
        await pilot.press("escape")
        assert c.all_envs() == []
        app._create_from_form({"name": "ocs-qa-working", "kind": "project", "mode": "managed",
                               "source": str(repo), "profile": "default", "include_working_changes": True})
        await settle(pilot, .5)
        app.screen.query_one("#import-confirm", Button).press()
        await settle(pilot, .5)
        m = c.resolve("ocs-qa-working")
        dest = c.env_dir(m["id"]) / "workspace"
        assert (dest / "modified").read_text() == "working"
        assert git(dest, "show", ":modified") == b"staged"
    run(t, size)


def test_preview_drift_and_unsupported_errors_are_visible(repo):
    async def t(app, pilot):
        values = {"name": "ocs-qa-working", "kind": "project", "mode": "managed",
                  "source": str(repo), "profile": "default", "include_working_changes": True}
        app._create_from_form(values)
        await settle(pilot, .5)
        (repo / "modified").write_text("after preview")
        app.screen.query_one("#import-confirm", Button).press()
        await settle(pilot, .5)
        assert c.all_envs() == []
        assert any("changed since" in n.message for n in app._notifications)
        (repo / ".git/MERGE_HEAD").write_text("dummy")
        app._create_from_form(values)
        await settle(pilot, .5)
        assert stack(app) == ["Screen"]
        assert any("in-progress Git" in n.message for n in app._notifications)
        assert not app._operation_pending
    run(t)
