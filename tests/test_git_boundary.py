"""Host Git must not execute anything configured in the
agent-writable workspace, including through nested repositories (gitlinks) and
through replacing `.git/config` between validation and use.

Marker-only: the "attack" programs only touch a file, never anything else.
"""
import os
import shlex
import subprocess

import pytest
from test_untrusted_workspace import ENTRY_POINTS, sh_git
from test_untrusted_workspace import git_env as _git_env

from opencode_sandbox import core as c
from opencode_sandbox import gitflow
from opencode_sandbox import workspace_io as wio

git_env = _git_env  # registers the shared fixture (pytest discovers it as a module attribute)


def _racy_repo(repo, marker):
    """A repository whose next status must re-hash a.txt (racy index), with a
    clean filter configured in its own config that only creates a marker.

    The setup's own `git add` runs that filter once (the nested repo's Git, not
    the host's outer command), so the marker is cleared afterwards: from here
    on, only the host command under test can create it.
    """
    (repo / ".gitattributes").write_text("a.txt filter=marker\n")
    sh_git(repo, "config", "filter.marker.clean", f"touch {shlex.quote(str(marker))}; cat")
    (repo / "a.txt").write_text("changed content and size\n")
    sh_git(repo, "add", "a.txt")
    sh_git(repo, "reset", "-q")  # forces a content re-hash on the next status
    marker.unlink(missing_ok=True)


def _nested_gitlink(m, repo, tmp, marker, *, gitdir_file=False):
    """Register an attacker-controlled populated repository as a gitlink."""
    nested = repo / "nested"
    nested.mkdir()
    sh_git(nested, "init", "-q")
    (nested / "a.txt").write_text("base\n")
    sh_git(nested, "add", "a.txt")
    sh_git(nested, "commit", "-qm", "nested base")
    head = subprocess.check_output(
        ["git", "-C", str(nested), "rev-parse", "HEAD"]).strip().decode()
    sh_git(repo, "update-index", "--add", "--cacheinfo", f"160000,{head},nested")
    _racy_repo(nested, marker)
    if gitdir_file:
        saved = tmp / "nested-git"
        (nested / ".git").rename(saved)
        (nested / ".git").write_text(f"gitdir: {saved}\n")


@pytest.mark.parametrize("entry", sorted(ENTRY_POINTS))
@pytest.mark.parametrize("gitdir_file", [False, True])
def test_nested_git_config_cannot_execute(git_env, entry, gitdir_file):
    m, repo, tmp = git_env
    marker = tmp / "nested-marker"
    _nested_gitlink(m, repo, tmp, marker, gitdir_file=gitdir_file)
    try:
        ENTRY_POINTS[entry](m, tmp)
    except c.SandboxError:
        pass  # a refusal is safe and expected for unsupported content
    assert not marker.exists(), "host Git executed a program from the nested repository"


def test_gitlink_is_refused_before_any_host_git_run(git_env):
    _m, repo, tmp = git_env
    _nested_gitlink(None, repo, tmp, tmp / "m")
    with pytest.raises(c.SandboxError, match="[Ss]ubmodule"):
        wio.git(repo, "status", "--short")


@pytest.mark.parametrize("entry", sorted(ENTRY_POINTS))
def test_config_replacement_after_validation_cannot_execute(git_env, monkeypatch, entry):
    m, repo, tmp = git_env
    marker = tmp / "race-marker"
    original = wio.check_repository

    def replace_after_check(workspace):
        gitdir = original(workspace)
        _racy_repo(repo, marker)  # agent swaps .git/config after validation
        return gitdir

    monkeypatch.setattr(wio, "check_repository", replace_after_check)
    try:
        ENTRY_POINTS[entry](m, tmp)
    except c.SandboxError:
        pass  # a later refusal is fine; execution is what must not happen
    assert not marker.exists(), "host Git reread agent config after validation"


def test_untracked_embedded_repo_is_inert(git_env):
    m, repo, tmp = git_env
    embedded = repo / "emb"
    embedded.mkdir()
    sh_git(embedded, "init", "-q")
    (embedded / "a.txt").write_text("base\n")
    sh_git(embedded, "add", "a.txt")
    sh_git(embedded, "commit", "-qm", "embedded base")
    _racy_repo(embedded, tmp / "embedded-marker")
    summary = gitflow.change_summary(m)
    assert "emb" in summary["status"]  # named, not executed
    assert not (tmp / "embedded-marker").exists()


def test_private_git_dir_isolation(git_env, monkeypatch):
    _m, repo, _tmp = git_env
    original = subprocess.run
    calls = []

    def record(argv, **kwargs):
        calls.append((argv, kwargs.get("env", {})))
        return original(argv, **kwargs)

    monkeypatch.setattr(subprocess, "run", record)
    assert wio.git(repo, "status", "--short") == b""  # clean
    for argv, env in calls:
        assert "--git-dir" not in argv or not argv[argv.index("--git-dir") + 1].startswith(str(repo)), \
            "host Git used the agent .git directory"
        assert env.get("GIT_NO_LAZY_FETCH") == "1"
        assert env.get("GIT_CONFIG_GLOBAL") == os.devnull


@pytest.mark.parametrize("fmt", ["--ref-format=reftable", "--object-format=sha256"])
def test_repository_storage_formats_still_work(tmp_path, fmt):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", fmt, str(repo)], check=True, capture_output=True)
    (repo / "a.txt").write_text("one\n")
    sh_git(repo, "add", "a.txt")
    sh_git(repo, "commit", "-qm", "base")
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).strip()
    (repo / "a.txt").write_text("two\n")
    assert wio.git(repo, "rev-parse", "HEAD").strip() == head
    assert wio.git(repo, "status", "--short") == b" M a.txt\n"


def test_unknown_storage_format_value_is_refused(tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    sh_git(repo, "config", "extensions.refstorage", "unknown")
    with pytest.raises(c.SandboxError, match="unsupported or unreadable extensions.refstorage"):
        wio.git(repo, "status", "--short")
