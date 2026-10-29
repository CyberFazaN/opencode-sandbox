"""E06/E07: real Git round trip sandbox -> bundle -> review branch / apply."""
import os
import shutil
import subprocess
import zipfile

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import gitflow


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.email=q@x", "-c", "user.name=q", *args],
                          check=True, capture_output=True).stdout.decode().strip()


def worktree_tree(repo, tmp_path, name):
    """Tree id of the full working tree (tracked + non-ignored untracked), without touching repo."""
    copy = tmp_path / name
    shutil.copytree(repo, copy, symlinks=True)
    git(copy, "add", "-A")
    return git(copy, "write-tree")


@pytest.fixture
def sandbox(tmp_path):
    src = tmp_path / "src"
    (src / "d").mkdir(parents=True)
    git(src, "init", "-q", "-b", "main")
    for name, data in {"modify.txt": "1\n", "keep.txt": "k\n", "del-staged.txt": "x\n", "del-unstaged.txt": "y\n",
                       "old.txt": "r\n", "run.sh": "#!/bin/sh\n", "d/n.txt": "n\n", "ü file.txt": "u\n"}.items():
        (src / name).write_text(data)
    (src / "blob.bin").write_bytes(os.urandom(512))
    os.chmod(src / "run.sh", 0o755)
    os.symlink("keep.txt", src / "link")
    git(src, "add", "-A")
    git(src, "commit", "-qm", "base")
    m = c.create("ocs-qa-rt", "project", src)
    ws = c.env_dir(m["id"]) / "workspace"
    (ws / "modify.txt").write_text("1 committed\n")
    (ws / "committed-new.txt").write_text("c\n")
    git(ws, "add", "-A")
    git(ws, "commit", "-qm", "agent commit")          # -> history.bundle in the export
    (ws / "keep.txt").write_text("k staged\n")
    git(ws, "add", "keep.txt")
    git(ws, "rm", "-q", "del-staged.txt")
    (ws / "del-unstaged.txt").unlink()
    git(ws, "mv", "old.txt", "new.txt")
    os.chmod(ws / "modify.txt", 0o755)
    os.chmod(ws / "run.sh", 0o644)
    (ws / "modify.txt").write_text("1 committed\n2 unstaged\n")
    (ws / "blob.bin").write_bytes(os.urandom(700))
    (ws / "u" / "v").mkdir(parents=True)
    (ws / "u" / "v" / "new.txt").write_text("untracked\n")
    (ws / "spaced name.bin").write_bytes(os.urandom(64))
    (ws / ".gitignore").write_text("*.log\n")
    (ws / "x.log").write_text("ignored\n")
    return m, src, ws


def test_bundle_with_commits_stages_exact_worktree(sandbox, tmp_path):
    """Any bundle containing history.bundle was rejected as 'Unexpected archive member'."""
    m, src, ws = sandbox
    os.symlink("../keep.txt", ws / "u" / "link-up")
    bundle = gitflow.export_changes(m, tmp_path / "out")
    assert "history.bundle" in zipfile.ZipFile(bundle).namelist()
    info = gitflow.inspect_changes(bundle)
    assert info["has_history"] and "u/v/new.txt" in info["untracked"] and "x.log" not in info["untracked"]
    head_before, status_before = git(src, "rev-parse", "HEAD"), git(src, "status", "--porcelain")
    assert gitflow.review_apply(bundle, src)["applied"] is False
    result = gitflow.stage_changes(bundle, src)
    assert git(src, "rev-parse", "HEAD") == head_before and git(src, "status", "--porcelain") == status_before
    assert git(src, "rev-parse", result["branch"] + "^{tree}") == worktree_tree(ws, tmp_path, "expected")
    assert git(src, "rev-parse", result["branch"] + "^1") == head_before
    # the attached history is a valid Git bundle with the agent's commit
    hist = tmp_path / "h.bundle"
    hist.write_bytes(zipfile.ZipFile(bundle).read("history.bundle"))
    git(src, "bundle", "verify", str(hist))
    diff = gitflow.review_branch_diff(src, result["branch"])
    assert "committed-new.txt" in diff and "u/v/new.txt" in diff and "old.txt => new.txt" in diff
    with pytest.raises(c.SandboxError, match="already exists"):
        gitflow.stage_changes(bundle, src)
    gitflow.drop_review_branch(src, result["branch"], expected_commit=result["commit"])
    with pytest.raises(c.SandboxError, match="not found"):  # Claimed success before
        gitflow.drop_review_branch(src, result["branch"], expected_commit=result["commit"])


def test_direct_apply_reproduces_worktree_and_modes(sandbox, tmp_path):
    m, src, ws = sandbox
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(src), str(clone)], check=True)
    bundle = gitflow.export_changes(m, tmp_path / "out")
    assert gitflow.review_apply(bundle, clone, apply=True)["applied"]
    assert worktree_tree(clone, tmp_path, "got") == worktree_tree(ws, tmp_path, "expected")
    assert os.stat(clone / "modify.txt").st_mode & 0o111 and not os.stat(clone / "run.sh").st_mode & 0o111
    assert not (clone / "x.log").exists() and not (clone / "del-staged.txt").exists()


@pytest.mark.parametrize("dirt", ["modified", "untracked", "diverged", "staged"])
def test_dirty_or_diverged_source_is_never_changed(sandbox, tmp_path, dirt):
    m, src, _ws = sandbox
    bundle = gitflow.export_changes(m, tmp_path / "out")
    if dirt == "modified":
        (src / "keep.txt").write_text("user edit\n")
    elif dirt == "untracked":
        (src / "user-new.txt").write_text("mine\n")
    elif dirt == "staged":
        (src / "keep.txt").write_text("user staged\n")
        git(src, "add", "keep.txt")
    else:
        (src / "keep.txt").write_text("user commit\n")
        git(src, "commit", "-qam", "user")
    state = (git(src, "rev-parse", "HEAD"), git(src, "status", "--porcelain"), git(src, "for-each-ref"),
             (src / "keep.txt").read_text())
    for call in (lambda: gitflow.review_apply(bundle, src), lambda: gitflow.review_apply(bundle, src, apply=True),
                 lambda: gitflow.stage_changes(bundle, src)):
        with pytest.raises(c.SandboxError, match="diverged|differs|modifications|clean Git"):
            call()
    assert state == (git(src, "rev-parse", "HEAD"), git(src, "status", "--porcelain"), git(src, "for-each-ref"),
                     (src / "keep.txt").read_text())


def test_unstage_is_compare_and_swap(sandbox, tmp_path):
    """An all-zero expected commit deleted the branch unconditionally."""
    m, src, _ws = sandbox
    result = gitflow.stage_changes(gitflow.export_changes(m, tmp_path / "out"), src)
    branch, commit = result["branch"], result["commit"]
    for wrong in ("0" * 40, git(src, "rev-parse", "HEAD")):
        with pytest.raises(c.SandboxError):
            gitflow.drop_review_branch(src, branch, expected_commit=wrong)
        assert git(src, "rev-parse", branch) == commit
    # the user built on the review branch: never removed
    tree = git(src, "rev-parse", branch + "^{tree}")
    newer = git(src, "commit-tree", tree, "-p", commit, "-m", "user review work")
    git(src, "update-ref", "refs/heads/" + branch, newer, commit)
    with pytest.raises(c.SandboxError, match="now points to"):
        gitflow.drop_review_branch(src, branch, expected_commit=commit)
    assert git(src, "rev-parse", branch) == newer


def test_failed_apply_restores_source(sandbox, tmp_path):
    """A write failure after the patch left a half-applied source and a traceback."""
    m, src, ws = sandbox
    (ws / "d" / "untracked-in-d.txt").write_text("x\n")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(src), str(clone)], check=True)
    before = (git(clone, "rev-parse", "HEAD"), git(clone, "status", "--porcelain", "--untracked-files=all"),
              (clone / "modify.txt").read_text())
    bundle = gitflow.export_changes(m, tmp_path / "out")
    os.chmod(clone / "d", 0o555)
    try:
        with pytest.raises(c.SandboxError, match="Apply failed: .*restored to its previous clean state"):
            gitflow.review_apply(bundle, clone, apply=True)
    finally:
        os.chmod(clone / "d", 0o755)
    assert before == (git(clone, "rev-parse", "HEAD"), git(clone, "status", "--porcelain", "--untracked-files=all"),
                      (clone / "modify.txt").read_text())
    assert not (clone / "u").exists()  # directories created by the failed apply are removed


def test_cli_reports_os_errors_without_traceback(monkeypatch, capsys):
    import sys

    from opencode_sandbox import cli
    monkeypatch.setattr(sys, "argv", ["opencode-sandbox", "changes", "inspect", "/nonexistent/x.ocschanges"])
    def boom(path):
        raise PermissionError(13, "Permission denied", str(path))
    monkeypatch.setattr(gitflow, "inspect_changes", boom)
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "Error:" in err and "Permission denied" in err and "Traceback" not in err


def test_inspect_listing_escapes_control_characters(sandbox, tmp_path):
    """A newline in a file name split the review listing."""
    from typer.testing import CliRunner

    from opencode_sandbox.cli import app
    m, _src, ws = sandbox
    (ws / "a.txt\nUntracked files: (none)").write_text("hidden\n")
    bundle = gitflow.export_changes(m, tmp_path / "out")
    out = CliRunner().invoke(app, ["changes", "inspect", str(bundle)]).output
    listing = [line for line in out.splitlines() if line.startswith("Untracked files:")]
    assert len(listing) == 1 and "a.txt\\nUntracked files: (none)" in listing[0]


def test_embedded_repository_has_clear_message(sandbox, tmp_path):
    m, _src, ws = sandbox
    (ws / "emb").mkdir()
    git(ws / "emb", "init", "-q")
    (ws / "emb" / "f").write_text("x\n")
    with pytest.raises(c.SandboxError, match="Embedded Git repository"):
        gitflow.export_changes(m, tmp_path / "out")
