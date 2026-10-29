"""Container-owned (host-unreadable) workspace entries.

On rootless Docker, files created by a non-root container user are owned by a
subordinate UID; the host user cannot read or remove them. chmod 000 simulates
that here (tests run as an ordinary user).
"""
import os
import subprocess
from types import SimpleNamespace

import pytest

from opencode_sandbox import backup as b
from opencode_sandbox import core as c
from opencode_sandbox import gitflow


@pytest.fixture
def unreadable_env(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root can read everything")
    m = c.create("ocs-qa-unread", "scratch")
    w = c.env_dir(m["id"]) / "workspace"
    (w / "ok.txt").write_text("ok")
    (w / "userdir").mkdir()
    (w / "userdir" / "p.txt").write_text("private")
    (w / "secret.txt").write_text("s")
    os.chmod(w / "secret.txt", 0)
    os.chmod(w / "userdir", 0)
    yield m, w
    for name in ("userdir", "secret.txt"):
        if os.path.lexists(w / name):
            os.chmod(w / name, 0o755)


def test_export_refuses_instead_of_silently_dropping(unreadable_env, tmp_path):
    m, _w = unreadable_env
    with pytest.raises(c.SandboxError, match=r"not readable.*chmod -R a\+rX"):
        c.export(m, tmp_path / "exp")
    assert not list((tmp_path / "exp").glob("*.tar.gz"))  # no partial artifact


def test_archive_directory_never_skips_unreadable(unreadable_env, tmp_path):
    _m, w = unreadable_env
    with pytest.raises(c.SandboxError, match="Cannot read"):
        b.archive_directory(w, tmp_path / "ws.tar.gz")


def test_backup_refuses_before_writing(unreadable_env, tmp_path, monkeypatch):
    m, _w = unreadable_env
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    with pytest.raises(c.SandboxError, match="not readable"):
        b.backup(m, tmp_path / "bk")
    assert not list((tmp_path / "bk").glob("*.ocsbackup"))


def test_changes_export_refuses(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    subprocess.run(["git", "-C", str(src), "init", "-q"], check=True)
    (src / "a").write_text("a")
    subprocess.run(["git", "-C", str(src), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(src), "-c", "user.email=q@x", "-c", "user.name=q", "commit", "-qm", "i"], check=True)
    m = c.create("ocs-qa-unread-git", "project", src)
    w = c.env_dir(m["id"]) / "workspace"
    (w / "d").mkdir()
    (w / "d" / "new").write_text("n")
    os.chmod(w / "d", 0)
    try:
        with pytest.raises(c.SandboxError, match="not readable"):
            gitflow.export_changes(m, tmp_path / "chg")
    finally:
        os.chmod(w / "d", 0o755)


def test_delete_falls_back_to_userns_cleanup(unreadable_env, monkeypatch):
    m, w = unreadable_env
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    calls = []
    def docker(*a, **k):
        calls.append(a)
        if a[0] == "run":  # what the helper container does inside the user namespace
            for p in ("userdir", "secret.txt"):
                if os.path.lexists(w / p):
                    os.chmod(w / p, 0o755)
            subprocess.run(["find", str(w), "-mindepth", "1", "-delete"], check=True)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(c, "docker", docker)
    c.delete(m, force=True)
    assert not c.env_dir(m["id"]).exists()
    run = next(a for a in calls if a[0] == "run")
    assert "--network" in run and run[run.index("--network") + 1] == "none"
    assert f"type=bind,src={w},dst=/w" in run  # only the workspace is mounted
