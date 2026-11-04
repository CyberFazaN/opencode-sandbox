"""Real Git and host files: import fidelity, source immutability and fail-closed boundaries."""
import os
import stat
import subprocess

import pytest
from typer.testing import CliRunner

from opencode_sandbox import core as c
from opencode_sandbox import git_import as gi
from opencode_sandbox.cli import app


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    # Deterministic global-ignore tests; never read a maintainer's Git configuration.
    home = tmp_path / "home"; home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    root = tmp_path / "source"; root.mkdir()
    git(root, "init", "-q", "-b", "feature/in-progress")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")
    for name in ("modified", "removed", "renamed", "binary", "executable", "link"):
        (root / name).write_bytes(b"base\n")
    (root / "link").unlink(); (root / "link").symlink_to("modified")
    (root / ".gitignore").write_text("*.ignored\n.env\ncache/\n")
    git(root, "add", "."); git(root, "commit", "-qm", "base")
    return root


def source_snapshot(repo):
    # Includes exact index/config/refs/objects bytes and modes, not access timestamps.
    return {str(p.relative_to(repo)): ("link", os.readlink(p)) if p.is_symlink() else
            (stat.S_IMODE(p.stat().st_mode), p.read_bytes())
            for p in repo.rglob("*") if not p.is_dir()}


def imported(repo, **kwargs):
    m = c.create("working", source=repo, include_working_changes=True, **kwargs)
    return c.env_dir(m["id"]) / "workspace"


def test_complete_working_state_and_source_immutability(repo):
    (repo / "modified").write_bytes(b"staged\n"); git(repo, "add", "modified")
    (repo / "modified").write_bytes(b"staged\nunstaged\n")
    git(repo, "rm", "-q", "removed")
    git(repo, "mv", "renamed", "new-name")
    (repo / "new-name").write_bytes(b"base\nmore\n")
    (repo / "binary").write_bytes(bytes(range(256))); git(repo, "add", "binary")
    (repo / "binary").write_bytes(b"\0unstaged\xff")
    (repo / "executable").chmod(0o751)
    (repo / "link").unlink(); (repo / "link").symlink_to("../../outside-secret")
    (repo / "untracked").mkdir(); (repo / "untracked/file").write_bytes(b"\0new\xff")
    (repo / "untracked/file").chmod(0o640)
    (repo / ".visible-hidden").write_text("included")
    (repo / "secret.ignored").write_text("dummy secret must not be copied")
    (repo / ".env").write_text("DUMMY_KEY=do-not-copy")
    (repo / "cache").mkdir(); (repo / "cache/data").write_text("ignored")
    before = source_snapshot(repo)
    plan = gi.preview(repo)
    assert "staged" in plan.describe() and "untracked" in plan.describe()
    assert "DUMMY_KEY" not in plan.describe() and ".env" not in plan.describe()
    dest = imported(repo, import_fingerprint=plan.fingerprint)
    assert source_snapshot(repo) == before
    assert git(dest, "rev-parse", "HEAD") == git(repo, "rev-parse", "HEAD")
    assert git(dest, "branch", "--show-current") == b"feature/in-progress\n"
    assert git(dest, "status", "--porcelain=v1", "-z", "--untracked-files=all") == git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    assert git(dest, "diff", "--cached", "--binary") == git(repo, "diff", "--cached", "--binary")
    assert git(dest, "diff", "--binary") == git(repo, "diff", "--binary")
    assert (dest / "binary").read_bytes() == b"\0unstaged\xff"
    assert os.readlink(dest / "link") == "../../outside-secret"
    assert stat.S_IMODE((dest / "executable").stat().st_mode) == 0o751
    assert stat.S_IMODE((dest / "untracked/file").stat().st_mode) == 0o640
    assert not (dest / "removed").exists() and not (dest / ".env").exists()
    assert not (dest / "cache").exists() and not (dest / "secret.ignored").exists()
    assert not (dest / ".git/objects/info/alternates").exists()


def test_default_clone_stays_clean(repo):
    (repo / "modified").write_text("not imported"); git(repo, "add", "modified")
    (repo / "new").write_text("not imported")
    before = source_snapshot(repo)
    m = c.create("clean", source=repo)
    dest = c.env_dir(m["id"]) / "workspace"
    assert (dest / "modified").read_bytes() == b"base\n"
    assert not (dest / "new").exists() and git(dest, "status", "--porcelain") == b""
    assert source_snapshot(repo) == before


def test_added_deleted_intent_to_add_and_detached_head(repo):
    git(repo, "checkout", "--detach", "-q")
    (repo / "added").write_text("staged addition"); git(repo, "add", "added")
    (repo / "added").unlink()  # staged addition, unstaged deletion
    (repo / "removed").unlink()  # ordinary unstaged deletion
    (repo / "intent").write_text("not staged"); git(repo, "add", "-N", "intent")
    dest = imported(repo)
    assert git(dest, "branch", "--show-current") == b""
    assert git(dest, "status", "--porcelain=v1") == git(repo, "status", "--porcelain=v1")
    assert git(dest, "diff", "--cached") == git(repo, "diff", "--cached")


def test_global_and_repository_info_ignores(repo, tmp_path):
    ignore = tmp_path / "global-ignore"; ignore.write_text("global-secret\n")
    git(repo, "config", "--global", "core.excludesFile", str(ignore))
    (repo / ".git/info/exclude").write_text("local-secret\n")
    for name in ("global-secret", "local-secret"): (repo / name).write_text("dummy")
    dest = imported(repo)
    assert not (dest / "global-secret").exists() and not (dest / "local-secret").exists()


def test_hooks_filters_global_and_environment_config_are_inert(repo, tmp_path, monkeypatch):
    marker = tmp_path / "executed"
    git(repo, "config", "core.fsmonitor", f"touch {marker}")
    git(repo, "config", "filter.attack.clean", f"touch {marker}; cat")
    git(repo, "config", "filter.attack.smudge", f"touch {marker}; cat")
    (repo / ".gitattributes").write_text("* filter=attack\n")
    hook = repo / ".git/hooks/post-checkout"; hook.write_text(f"#!/bin/sh\ntouch {marker}\n"); hook.chmod(0o755)
    git(repo, "config", "--global", "core.fsmonitor", f"touch {marker}")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.fsmonitor")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", f"touch {marker}")
    before = source_snapshot(repo)
    dest = imported(repo)
    assert not marker.exists() and (dest / ".gitattributes").exists()
    assert source_snapshot(repo) == before
    assert "filter.attack" not in (dest / ".git/config").read_text()


def test_nested_ignore_rules_and_force_added_files(repo):
    (repo / "sub").mkdir()
    (repo / "sub/.gitignore").write_text("*.log\n!keep.log\nnested/\n")
    (repo / "sub/omit.log").write_text("ignored")
    (repo / "sub/keep.log").write_text("keep")
    (repo / "sub/nested").mkdir(); git(repo / "sub/nested", "init", "-q")
    (repo / "sub/nested/private").write_text("ignored nested repository")
    (repo / "forced.ignored").write_text("explicitly staged")
    git(repo, "add", "-f", "forced.ignored")
    dest = imported(repo)
    assert (dest / "sub/keep.log").read_text() == "keep"
    assert not (dest / "sub/omit.log").exists() and not (dest / "sub/nested").exists()
    assert git(dest, "show", ":forced.ignored") == b"explicitly staged"
    assert git(dest, "status", "--porcelain", "--untracked-files=all") == git(repo, "status", "--porcelain", "--untracked-files=all")


@pytest.mark.parametrize("state", ["conflict", "gitlink", "operation", "split", "skip", "local-excludes", "include", "gitdir", "symlink-gitdir", "nested", "fifo", "fifo-ignore", "fifo-exclude", "parent-link"])
def test_unsupported_states_leave_no_environment_or_source_changes(repo, tmp_path, state):
    if state == "conflict":
        oid = git(repo, "rev-parse", "HEAD:modified").strip().decode()
        git(repo, "update-index", "--force-remove", "modified")
        subprocess.run(["git", "-C", str(repo), "update-index", "--index-info"],
                       input=f"100644 {oid} 1\tmodified\n100644 {oid} 2\tmodified\n".encode(), check=True)
    elif state == "gitlink":
        oid = git(repo, "rev-parse", "HEAD").strip().decode()
        git(repo, "update-index", "--add", "--cacheinfo", f"160000,{oid},submodule")
    elif state == "operation": (repo / ".git/MERGE_HEAD").write_text("dummy")
    elif state == "split": git(repo, "update-index", "--split-index")
    elif state == "skip": git(repo, "update-index", "--assume-unchanged", "modified")
    elif state == "local-excludes": git(repo, "config", "core.excludesFile", str(tmp_path / "secret"))
    elif state == "include": git(repo, "config", "include.path", str(tmp_path / "external-config"))
    elif state in ("gitdir", "symlink-gitdir"):
        saved = tmp_path / "external-git"; (repo / ".git").rename(saved)
        if state == "gitdir": (repo / ".git").write_text(f"gitdir: {saved}\n")
        else: (repo / ".git").symlink_to(saved, target_is_directory=True)
    elif state == "nested":
        nested = repo / "nested"; nested.mkdir(); git(nested, "init", "-q")
        (nested / "private").write_text("do not silently omit nested files")
    elif state == "fifo":
        (repo / "modified").unlink(); os.mkfifo(repo / "modified")
    elif state == "fifo-ignore":
        (repo / ".gitignore").unlink(); os.mkfifo(repo / ".gitignore")
    elif state == "fifo-exclude":
        (repo / ".git/info/exclude").unlink(); os.mkfifo(repo / ".git/info/exclude")
    elif state == "parent-link":
        (repo / "directory").mkdir(); (repo / "directory/file").write_text("base")
        git(repo, "add", "directory"); git(repo, "commit", "-qm", "directory")
        (repo / "directory/file").unlink(); (repo / "directory").rmdir()
        (repo / "directory").symlink_to(tmp_path)
    # Avoid reading a FIFO in the snapshot itself.
    before = (repo / ".git/index").read_bytes() if (repo / ".git/index").exists() else None
    with pytest.raises(c.SandboxError): imported(repo)
    assert c.all_envs() == []
    assert not list((c.BASE / "environments").glob("*/workspace"))
    if before is not None: assert (repo / ".git/index").read_bytes() == before


def test_preview_drift_and_mid_import_failure_cleanup(repo, monkeypatch):
    plan = gi.preview(repo)
    (repo / "modified").write_text("changed after preview")
    with pytest.raises(c.SandboxError, match="changed since"): imported(repo, import_fingerprint=plan.fingerprint)
    original = gi._capture
    def change_while_copying(pgd, source, destination=None):
        result = original(pgd, source, destination)
        if destination is not None: (source / "new-concurrent-file").write_text("new")
        return result
    monkeypatch.setattr(gi, "_capture", change_while_copying)
    with pytest.raises(c.SandboxError, match="changed during"): imported(repo)
    assert c.all_envs() == []


@pytest.mark.parametrize("fmt", ["--ref-format=reftable", "--object-format=sha256"])
def test_storage_formats(repo, tmp_path, fmt):
    other = tmp_path / "other"
    git(tmp_path, "init", "-q", fmt, str(other))
    (other / "file").write_text("base")
    git(other, "add", ".")
    git(other, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base")
    (other / "file").write_text("staged"); git(other, "add", "file")
    (other / "file").write_text("working")
    dest = imported(other)
    assert git(dest, "show", ":file") == b"staged" and (dest / "file").read_text() == "working"
    assert git(dest, "rev-parse", "HEAD") == git(other, "rev-parse", "HEAD")


def test_all_staged_deletions_and_independent_history(repo):
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "rm", "-qr", ".")
    dest = imported(repo)
    assert git(dest, "status", "--porcelain") == git(repo, "status", "--porcelain")
    assert git(dest, "rev-parse", "HEAD") == head
    # No object is hardlinked to source and the clone survives removing source objects.
    for file in (repo / ".git/objects").rglob("*"):
        if file.is_file(): file.unlink()
    assert git(dest, "show", "HEAD:modified") == b"base\n"


def test_failure_after_clone_leaves_no_partial_environment(repo, monkeypatch):
    original = gi._git
    def fail(pgd, source, *args, **kwargs):
        if args[0] == "hash-object": raise c.SandboxError("injected write failure")
        return original(pgd, source, *args, **kwargs)
    (repo / "modified").write_text("new staged data"); git(repo, "add", "modified")
    before = source_snapshot(repo)
    monkeypatch.setattr(gi, "_git", fail)
    with pytest.raises(c.SandboxError, match="injected write"): imported(repo)
    assert source_snapshot(repo) == before and c.all_envs() == []


def test_status_only_hashes_private_no_follow_snapshot(repo, monkeypatch):
    original = gi._git
    checked = []
    def record(pgd, source, *args, **kwargs):
        if "status" in args:
            assert source != repo
            checked.append(source)
        return original(pgd, source, *args, **kwargs)
    monkeypatch.setattr(gi, "_git", record)
    imported(repo)
    assert checked


def test_size_limit_failure_is_explicit_and_non_destructive(repo, monkeypatch):
    before = source_snapshot(repo)
    monkeypatch.setattr(gi, "MAX_TOTAL", len((repo / ".gitignore").read_bytes()) + 1)
    with pytest.raises(c.SandboxError, match="exceeds 1 GiB"): imported(repo)
    assert source_snapshot(repo) == before and c.all_envs() == []


def test_paths_control_characters_and_symlinks_are_not_followed(repo, tmp_path):
    outside = tmp_path / "outside-secret"; outside.write_text("never read")
    (repo / "untracked-link").symlink_to(outside)
    name = "-strange\n\x1b[31m[red]"
    (repo / name).write_text("new")
    plan = gi.preview(repo)
    assert "\x1b" not in plan.describe() and "\\x1b" in plan.describe()
    dest = imported(repo)
    assert (dest / name).read_text() == "new"
    assert (dest / "untracked-link").is_symlink() and os.readlink(dest / "untracked-link") == str(outside)


def test_cli_preview_and_default(repo):
    help_result = CliRunner().invoke(app, ["create", "--help"], terminal_width=80)
    assert help_result.exit_code == 0 and "--include-working-changes" in help_result.output
    (repo / "modified").write_text("working")
    result = CliRunner().invoke(app, ["create", "cli-working", "--source", str(repo), "--include-working-changes"])
    assert result.exit_code == 0, result.output
    assert "1 changed paths: 0 staged, 1 unstaged, 0 untracked" in result.output
    assert " M 'modified'" in result.output
    result = CliRunner().invoke(app, ["create", "cli-clean", "--source", str(repo)])
    assert result.exit_code == 0 and "changed paths" not in result.output


@pytest.mark.parametrize("options", [{}, {"source": "somewhere", "kind": "quick"},
                                     {"workspace_mode": "direct", "workspace": "somewhere"}])
def test_mode_requires_managed_project(options):
    with pytest.raises(c.SandboxError, match="managed Project"):
        c.create("invalid", include_working_changes=True, **options)
