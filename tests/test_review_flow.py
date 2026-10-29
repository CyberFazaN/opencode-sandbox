"""Integrity of the change review flow. CLI output derived from workspace content shows
control characters escaped; tracked symlinks that point outside the
repository are refused like untracked ones, and paths that host tools act on are listed for
review; the executable bit of untracked files is kept."""
import os
import subprocess

import pytest
from typer.testing import CliRunner

from opencode_sandbox import core as c
from opencode_sandbox import gitflow
from opencode_sandbox.cli import app

CTRL = "\x07\x1b[0m\rX"  # bell, an escape sequence, a carriage return: never written raw to a terminal


def invoke(*args, **kw):
    """color=True: click strips ANSI sequences only when the output is not a terminal."""
    return CliRunner().invoke(app, list(args), color=True, **kw)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.email=q@x", "-c", "user.name=q", *args],
                          check=True, capture_output=True).stdout.decode().strip()


@pytest.fixture
def sandbox(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    git(src, "init", "-q", "-b", "main")
    (src / "a.txt").write_text("one\n")
    git(src, "add", "-A")
    git(src, "commit", "-qm", "base")
    m = c.create("ocs-test-r06", "project", src)
    return m, src, c.env_dir(m["id"]) / "workspace"


def _no_raw_controls(text):
    return not any(ch in text for ch in ("\x1b", "\r", "\x07", "\u202e"))


# --- Sandbox text is escaped -----------------------------------------------------------

def test_printable_escapes_controls_but_keeps_newlines_and_tabs():
    assert c.printable("a\tb\nc") == "a\tb\nc"
    assert c.printable("x\x1by\rz\u202e") == "x\\x1by\\rz\\u202e"
    assert c.printable("\u00fc-unicode") == "\u00fc-unicode"  # printable non-ASCII is kept


def test_changes_show_and_delete_escape_workspace_text(sandbox):
    m, _src, ws = sandbox
    (ws / "a.txt").write_text("two\n")
    git(ws, "commit", "-qam", f"subject {CTRL}end")
    (ws / f"name{CTRL}.txt").write_text("x\n")
    shown = invoke("changes", "show", m["name"])
    assert shown.exit_code == 0, shown.output
    assert "subject" in shown.output and _no_raw_controls(shown.output) and "\\x1b" in shown.output
    deleted = invoke("delete", m["name"], input="no\n")
    assert "subject" in deleted.output and _no_raw_controls(deleted.output)
    assert c.resolve(m["id"])  # not deleted


def test_changes_inspect_and_branch_diff_escape_patch_text(sandbox, tmp_path):
    m, src, ws = sandbox
    (ws / "a.txt").write_text(f"line {CTRL}\n")
    bundle = gitflow.export_changes(m, tmp_path / "out")
    inspected = invoke("changes", "inspect", str(bundle))
    assert inspected.exit_code == 0, inspected.output
    assert "+line" in inspected.output and _no_raw_controls(inspected.output)
    branch = gitflow.stage_changes(bundle, src)["branch"]
    diff = invoke("changes", "branch-diff", str(src), branch)
    assert "+line" in diff.output and _no_raw_controls(diff.output)


# --- Tracked links leaving the repository; paths to review -----------------------------

@pytest.mark.parametrize("target", ["/etc/hostname", "../../outside"])
def test_tracked_symlink_leaving_the_repository_is_refused(sandbox, tmp_path, target):
    m, src, ws = sandbox
    os.symlink(target, ws / "link")
    git(ws, "add", "link")  # tracked: part of the patch, not of the untracked inventory
    bundle = gitflow.export_changes(m, tmp_path / "out")
    head = git(src, "rev-parse", "HEAD")
    for operation in (lambda: gitflow.review_apply(bundle, src), lambda: gitflow.stage_changes(bundle, src),
                      lambda: gitflow.review_apply(bundle, src, apply=True)):
        with pytest.raises(c.SandboxError, match="Unsafe tracked symlink target: link"):
            operation()
    assert git(src, "rev-parse", "HEAD") == head and git(src, "status", "--porcelain") == ""
    assert git(src, "branch", "--list", "ocs/review-*") == ""


def test_tracked_symlink_inside_the_repository_is_staged(sandbox, tmp_path):
    """Guard: links that stay inside the repository are transferred as before."""
    m, src, ws = sandbox
    os.symlink("a.txt", ws / "link")
    git(ws, "add", "link")
    bundle = gitflow.export_changes(m, tmp_path / "out")
    branch = gitflow.stage_changes(bundle, src)["branch"]
    assert git(src, "ls-tree", branch, "link").startswith("120000 ")


def test_paths_for_attention_are_listed(sandbox, tmp_path):
    m, src, ws = sandbox
    (ws / ".gitattributes").write_text("*.txt text\n")
    (ws / ".vscode").mkdir()
    (ws / ".vscode" / "settings.json").write_text("{}\n")
    (ws / "tool.sh").write_text("#!/bin/sh\n")
    os.chmod(ws / "tool.sh", 0o755)
    os.chmod(ws / "a.txt", 0o755)
    os.symlink("a.txt", ws / "inside-link")
    git(ws, "add", "-A")
    (ws / "untracked-run.sh").write_text("#!/bin/sh\n")
    os.chmod(ws / "untracked-run.sh", 0o755)
    bundle = gitflow.export_changes(m, tmp_path / "out")
    attention = gitflow.inspect_changes(bundle)["attention"]
    joined = "\n".join(attention)
    for expected in (".gitattributes", ".vscode/settings.json", "tool.sh", "a.txt", "inside-link", "untracked-run.sh"):
        assert expected in joined, (expected, attention)
    out = invoke("changes", "inspect", str(bundle)).output
    assert "Review with care" in out and ".gitattributes" in out
    assert gitflow.review_apply(bundle, src)["attention"] == attention


# --- Executable bit of untracked files -------------------------------------------------

def test_untracked_executable_bit_is_kept(sandbox, tmp_path):
    m, src, ws = sandbox
    (ws / "run.sh").write_text("#!/bin/sh\necho ok\n")
    os.chmod(ws / "run.sh", 0o755)
    (ws / "data.txt").write_text("d\n")
    bundle = gitflow.export_changes(m, tmp_path / "out")
    branch = gitflow.stage_changes(bundle, src)["branch"]
    assert git(src, "ls-tree", branch, "run.sh").startswith("100755 ")
    assert git(src, "ls-tree", branch, "data.txt").startswith("100644 ")
    gitflow.review_apply(bundle, src, apply=True)
    assert os.stat(src / "run.sh").st_mode & 0o111 and not os.stat(src / "data.txt").st_mode & 0o111
