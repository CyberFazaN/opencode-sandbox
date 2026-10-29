"""The workspace (including .git) is agent-controlled."""
import os
import subprocess
import tarfile
import time
import zipfile

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import gitflow
from opencode_sandbox import workspace_io as wio


def sh_git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=q@x", "-c", "user.name=q", *args],
                   check=True, capture_output=True)


@pytest.fixture
def git_env(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    sh_git(src, "init", "-q")
    (src / "a.txt").write_text("one\n")
    sh_git(src, "add", "-A")
    sh_git(src, "commit", "-qm", "base")
    m = c.create("ocs-qa-git", "project", src)
    return m, c.env_dir(m["id"]) / "workspace", tmp_path


ENTRY_POINTS = {
    "git_changes": lambda m, t: c.git_changes(m),
    "export": lambda m, t: c.export(m, t / "exp"),
    "change_summary": lambda m, t: gitflow.change_summary(m),
    "export_changes": lambda m, t: gitflow.export_changes(m, t / "chg"),
}


@pytest.mark.parametrize("entry", sorted(ENTRY_POINTS))
@pytest.mark.parametrize("key,value", [
    ("core.fsmonitor", "touch {marker}; false"),
    ("filter.evil.clean", "touch {marker}; cat"),
    ("diff.evil.textconv", "touch {marker}; cat"),
    ("core.worktree", "{home}"),
    ("include.path", "{home}/inc"),
])
def test_agent_git_config_is_never_read_on_host(git_env, entry, key, value):
    """The workspace repository config is not read by host Git at all; what
    it configures (filters, drivers, fsmonitor, redirection) cannot execute."""
    m, w, tmp = git_env
    marker = tmp / "PWNED"
    (w / ".gitattributes").write_text("* filter=evil diff=evil\n")
    (w / "a.txt").write_text("changed\n")
    sh_git(w, "config", key, value.format(marker=marker, home=tmp))
    result = ENTRY_POINTS[entry](m, tmp)
    assert "a.txt" in result if isinstance(result, str) else True
    assert not marker.exists()


def test_safe_config_keys_still_work(git_env):
    m, w, tmp = git_env
    sh_git(w, "config", "user.name", "Agent")
    sh_git(w, "remote", "add", "upstream", "https://example.invalid/r.git")
    (w / "a.txt").write_text("two\n")
    assert "a.txt" in c.git_changes(m)
    bundle = gitflow.export_changes(m, tmp / "chg")
    assert b"+two" in zipfile.ZipFile(bundle).read("changes.patch")


@pytest.mark.parametrize("kind", ["symlink", "gitdir-file"])
def test_redirected_git_dir_is_not_trusted(git_env, kind):
    m, w, tmp = git_env
    victim = tmp / "victim"
    victim.mkdir()
    sh_git(victim, "init", "-q")
    sh_git(victim, "config", "core.fsmonitor", f"touch {tmp / 'PWNED'}; false")
    subprocess.run(["rm", "-rf", str(w / ".git")], check=True)
    if kind == "symlink":
        (w / ".git").symlink_to(victim / ".git")
    else:
        (w / ".git").write_text(f"gitdir: {victim / '.git'}\n")
    assert "Not a Git repository" in c.git_changes(m)
    with pytest.raises(c.SandboxError):
        gitflow.export_changes(m, tmp / "chg")
    c.export(m, tmp / "exp")
    assert not (tmp / "PWNED").exists()


def test_alternates_refused(git_env):
    m, w, tmp = git_env
    (w / ".git/objects/info").mkdir(parents=True, exist_ok=True)
    (w / ".git/objects/info/alternates").write_text(str(tmp) + "\n")
    with pytest.raises(c.SandboxError, match="redirects"):
        gitflow.change_summary(m)


def test_non_git_export_archives_symlinks_without_dereferencing(tmp_path):
    secret = tmp_path / "host-secret.txt"
    secret.write_text("HOST-CANARY")
    (tmp_path / "hostdir").mkdir()
    (tmp_path / "hostdir" / "x").write_text("HOST-CANARY")
    m = c.create("ocs-qa-plain", "scratch")
    w = c.env_dir(m["id"]) / "workspace"
    (w / "ok.txt").write_text("fine")
    os.chmod(w / "ok.txt", 0o755)
    (w / "leak.txt").symlink_to(secret)
    (w / "leakdir").symlink_to(tmp_path / "hostdir")
    os.mkfifo(w / "pipe")
    out = c.export(m, tmp_path / "exp")
    assert out.stat().st_mode & 0o777 == 0o600
    with tarfile.open(out) as tf:
        members = {i.name: i for i in tf.getmembers()}
        assert members["workspace/leak.txt"].issym()
        assert members["workspace/leakdir"].issym()
        assert "workspace/leakdir/x" not in members
        assert tf.extractfile("workspace/ok.txt").read() == b"fine"
        assert members["workspace/ok.txt"].mode & 0o777 == 0o755
        for i in tf.getmembers():
            if i.isfile():
                assert b"HOST-CANARY" not in tf.extractfile(i).read()
        assert "pipe" in tf.extractfile("manifest.json").read().decode()


def test_git_export_handles_non_utf8_and_symlinked_untracked(git_env):
    m, w, tmp = git_env
    (w / "a.txt").write_bytes(b"caf\xe9\n")  # Latin-1, invalid UTF-8
    (tmp / "secret").write_text("HOST-CANARY")
    (w / "untracked-link").symlink_to(tmp / "secret")
    (w / "new.txt").write_text("new")
    out = c.export(m, tmp / "exp")
    with tarfile.open(out) as tf:
        names = tf.getnames()
        assert b"caf\xe9" in tf.extractfile("changes.patch").read()
        assert "untracked/new.txt" in names and "untracked/untracked-link" not in names


def test_read_file_refuses_symlink_parent_and_fifo(tmp_path):
    root = tmp_path / "root"
    (root / "real").mkdir(parents=True)
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "f").write_text("x")
    (root / "linkdir").symlink_to(tmp_path / "outside")
    os.mkfifo(root / "real" / "pipe")
    with pytest.raises(c.SandboxError):
        wio.read_file(root, "linkdir/f")
    with pytest.raises(c.SandboxError, match="regular"):
        wio.read_file(root, "real/pipe")  # must not block
    with pytest.raises(c.SandboxError):
        wio.read_file(root, "../outside/f")


@pytest.mark.parametrize("name", ["sub/.git/config", "a/.GIT/hooks/x", ".git/config"])
def test_bundle_paths_cannot_plant_nested_git_dirs(name):
    with pytest.raises(c.SandboxError):
        gitflow._safe_rel(name)


def test_index_snapshot_keeps_the_index_mtime(git_env):
    """Git trusts an index entry's stat data only when the entry is older than the index file;
    a snapshot with a fresh mtime made a same-size change written in the index's timestamp tick
    look unchanged, so `changes export` silently left it out (seen as an intermittent failure)."""
    _, w, _ = git_env
    index = w / ".git" / "index"
    os.utime(index, ns=(1_000_000_000, 1_234_567_890_123_456_789))
    with wio._private_git_dir(w / ".git") as pgd:
        assert (pgd / "index").stat().st_mtime_ns == 1_234_567_890_123_456_789


def test_same_size_change_right_after_an_index_write_is_exported(git_env):
    """Behaviour behind the previous test: before the fix about one attempt in twenty missed the
    change, so 40 attempts catch a regression in most runs."""
    m, w, _ = git_env
    base = m["base_commit"]
    for attempt in range(40):
        (w / "a.txt").write_text("one\n")
        sh_git(w, "add", "a.txt")                         # writes the index
        (w / "a.txt").write_text(f"t{attempt:02}\n")      # same size, same timestamp tick
        time.sleep(0.03)                                  # the snapshot is taken in a later tick
        patch = wio.git(w, "diff", "--no-ext-diff", "--no-textconv", base, "--")
        assert f"+t{attempt:02}".encode() in patch, attempt
