"""Backup completeness: the system layer of a derived image without a container, file names that
verify and restore must accept, and special files that must not abort a backup. Docker is mocked;
the home-volume helper is covered for real by the campaign (CAMPAIGN E01/E04/E09)."""
import io
import json
import os
import socket
import stat
import subprocess
import tarfile
from pathlib import Path

import pytest

from opencode_sandbox import backup as b
from opencode_sandbox import core as c


class FakeDocker:
    """Records docker calls; `image save` writes an archive like Docker's for the saved tag."""

    def __init__(self, present=()):
        self.calls = []
        self.present = set(present)

    def __call__(self, *args, capture=False, check=True):
        self.calls.append(args)
        rc, out = 0, ""
        if args[:2] == ("image", "inspect"):
            rc = 0 if args[-1] in self.present else 1
        elif args[0] == "tag":
            self.present.add(args[2])
        elif args[:2] == ("image", "save"):
            tag = args[-1]
            if tag not in self.present:
                rc = 1
            else:
                _image_archive(Path(args[3]), tag)
        elif args[:2] == ("image", "rm"):
            self.present.discard(args[2])
        elif args[0] == "commit":
            self.present.add(args[2])
        if check and rc:
            raise c.SandboxError(f"Command failed ({rc}): docker {args[0]}")
        return subprocess.CompletedProcess(args, rc, out, "")


def _image_archive(path, tag):
    manifest = json.dumps([{"Config": "blobs/sha256/" + "0" * 64, "RepoTags": [tag], "Layers": []}]).encode()
    with tarfile.open(path, "w:") as tf:
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest)
        tf.addfile(info, io.BytesIO(manifest))


@pytest.fixture
def env(monkeypatch):
    m = c.create("ocs-test-r02", "scratch")
    for name, value in (("ensure_runtime", lambda image=True: None), ("inspect_container", lambda m: None),
                        ("assert_volume_owned", lambda m: None), ("volume_state", lambda m: None)):
        monkeypatch.setattr(c, name, value)
    return m


def _set_image(m, image):
    m["image"] = image
    c.save(m)
    return m


def _manifest(target):
    return json.loads((Path(target) / "manifest.json").read_text())


def _no_partial_backup(root):
    root = Path(root)
    return not root.exists() or not any(p.name.endswith(".ocsbackup") or p.name.startswith(".backup-")
                                        for p in root.iterdir())


# --- derived system image without a container ---------------------------

@pytest.mark.parametrize("kind", ["ocs-runtime", "ocs-checkpoint", "ocs-snapshot", "ocs-backup"])
def test_backup_without_container_keeps_the_derived_system_image(env, monkeypatch, tmp_path, kind):
    derived = f"{kind}:{env['id']}-0123456789ab"
    _set_image(env, derived)
    fake = FakeDocker(present={derived})
    monkeypatch.setattr(c, "docker", fake)
    target = b.backup(env, tmp_path / "bk")
    manifest = _manifest(target)
    assert "system-image.tar" in manifest["files"] and manifest["system_image"] is True
    assert manifest["system_image_source"] == "image"
    saved = [a for a in fake.calls if a[:2] == ("image", "save")]
    assert len(saved) == 1 and b.BACKUP_TAG.fullmatch(saved[0][-1])
    assert ("tag", derived, saved[0][-1]) in fake.calls
    assert ("image", "rm", saved[0][-1]) in fake.calls          # temporary tag removed again
    assert derived in fake.present                             # the environment's image is untouched
    assert not any(a[0] == "commit" for a in fake.calls)
    assert b._image_archive_tag(target / "system-image.tar")[0] == saved[0][-1]  # restorable name
    b.verify(target)


def test_backup_with_missing_derived_image_refuses_and_publishes_nothing(env, monkeypatch, tmp_path):
    _set_image(env, f"ocs-runtime:{env['id']}-0123456789ab")
    monkeypatch.setattr(c, "docker", FakeDocker())
    with pytest.raises(c.SandboxError, match="--no-system"):
        b.backup(env, tmp_path / "bk")
    assert _no_partial_backup(tmp_path / "bk")


def test_backup_without_container_and_without_derived_image_has_no_system_image(env, monkeypatch, tmp_path):
    """Guard: a never-started registry environment has no layer."""
    fake = FakeDocker()
    monkeypatch.setattr(c, "docker", fake)
    manifest = _manifest(b.backup(env, tmp_path / "bk"))
    assert manifest["system_image"] is False and "system-image.tar" not in manifest["files"]
    assert not any(a[:2] == ("image", "save") for a in fake.calls)


def test_no_system_leaves_the_derived_image_out(env, monkeypatch, tmp_path):
    """Guard: --no-system is honoured; the manifest says so."""
    derived = f"ocs-runtime:{env['id']}-0123456789ab"
    _set_image(env, derived)
    fake = FakeDocker(present={derived})
    monkeypatch.setattr(c, "docker", fake)
    manifest = _manifest(b.backup(env, tmp_path / "bk", include_system=False))
    assert manifest["system_image"] is False and manifest["system_image_source"] is None
    assert not any(a[:2] == ("image", "save") for a in fake.calls)


def test_backup_of_a_stopped_container_still_commits_it(env, monkeypatch, tmp_path):
    """Guard: with a container, its layer is committed (also when a derived image is recorded)."""
    _set_image(env, f"ocs-runtime:{env['id']}-0123456789ab")
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False})
    fake = FakeDocker(present={env["image"]})
    monkeypatch.setattr(c, "docker", fake)
    manifest = _manifest(b.backup(env, tmp_path / "bk"))
    assert manifest["system_image_source"] == "container"
    assert any(a[0] == "commit" for a in fake.calls)


# --- backups that verify/restore rejected -------------------------------

def _workspace(m):
    return c.env_dir(m["id"]) / "workspace"


def test_leading_dash_names_round_trip(env, monkeypatch, tmp_path):
    monkeypatch.setattr(c, "docker", FakeDocker())
    w = _workspace(env)
    (w / "-x").write_text("dash\n")
    (w / "--y").mkdir()
    (w / "--y" / "-z").write_text("nested\n")
    target = b.backup(env, tmp_path / "bk")
    b.verify(target)
    out = tmp_path / "out"
    b.unpack(target / "workspace.tar.gz", out)
    assert (out / "-x").read_text() == "dash\n" and (out / "--y" / "-z").read_text() == "nested\n"


def test_backslash_in_a_name_refuses_the_backup_naming_the_file(env, monkeypatch, tmp_path):
    monkeypatch.setattr(c, "docker", FakeDocker())
    (_workspace(env) / "sub").mkdir()
    (_workspace(env) / "sub" / "a\\b").write_text("x")
    with pytest.raises(c.SandboxError, match=r'"sub/a\\b" has a backslash'):
        b.backup(env, tmp_path / "bk")
    assert _no_partial_backup(tmp_path / "bk")


def test_workspace_archive_is_validated_before_publication(env, monkeypatch, tmp_path):
    """Whatever the archiver writes is checked with the restore rules before the backup exists."""
    monkeypatch.setattr(c, "docker", FakeDocker())

    def archive_with_unrestorable_member(source, target):
        with tarfile.open(target, "w:gz") as tf:
            info = tarfile.TarInfo("a/../b")
            info.size = 0
            tf.addfile(info, io.BytesIO(b""))
    monkeypatch.setattr(b, "archive_directory", archive_with_unrestorable_member)
    with pytest.raises(c.SandboxError, match="cannot be restored"):
        b.backup(env, tmp_path / "bk")
    assert _no_partial_backup(tmp_path / "bk")


# --- sockets and FIFOs ---------------------------------------------------

def test_fifos_and_sockets_are_skipped_and_recorded(env, monkeypatch, tmp_path):
    monkeypatch.setattr(c, "docker", FakeDocker())
    w = _workspace(env)
    (w / "keep.txt").write_text("kept\n")
    (w / ".git").mkdir()
    os.mkfifo(w / "pipe")
    sock = socket.socket(socket.AF_UNIX)
    os.chdir(w / ".git")  # short relative path for the socket name
    try:
        sock.bind("fsmonitor--daemon.ipc")
    finally:
        os.chdir(tmp_path)
    try:
        target = b.backup(env, tmp_path / "bk")
    finally:
        sock.close()
    manifest = _manifest(target)
    assert manifest["skipped_special_files"]["workspace"] == [".git/fsmonitor--daemon.ipc", "pipe"]
    b.verify(target)
    out = tmp_path / "out"
    b.unpack(target / "workspace.tar.gz", out)
    assert (out / "keep.txt").read_text() == "kept\n"
    assert not (out / "pipe").exists() and not (out / ".git" / "fsmonitor--daemon.ipc").exists()
    assert "pipe" in "\n".join(b.backup_notes(target))


def test_device_nodes_are_refused_with_a_clear_message(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    (src / "dev0").write_text("")
    real_lstat = Path.lstat

    def lstat(self):
        st = real_lstat(self)
        if self.name == "dev0":
            return os.stat_result((stat.S_IFCHR | 0o600, *st[1:]))
        return st
    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(c.SandboxError, match='"dev0" is a device file'):
        b.archive_directory(src, tmp_path / "a.tar.gz")


def test_home_volume_helper_leaves_out_fifos_and_sockets(env, monkeypatch, tmp_path):
    """The helper runs GNU tar on a list from find without FIFOs and sockets, and reports them."""
    runs = []
    monkeypatch.setattr(c, "volume_state", lambda m: {"Name": c.volume(m)})
    monkeypatch.setattr(b, "helper_image", lambda m: "node:24-bookworm")

    def docker(*args, capture=False, check=True):
        if args[0] == "run":
            runs.append(args)
            staging = Path(next(a for a in args if str(a).startswith("type=bind")).split(",")[1].split("=", 1)[1])
            with tarfile.open(staging / "home.tar.gz", "w:gz") as tf:
                info = tarfile.TarInfo("./.bashrc")
                info.size = 0
                tf.addfile(info, io.BytesIO(b""))
            (staging / b.HOME_SKIPPED).write_bytes(b"./.cache/app.sock\0./run/fifo\0")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(c, "docker", docker)
    target = b.backup(env, tmp_path / "bk")
    script = runs[0][-1]
    assert "! -type p ! -type s" in script and "--verbatim-files-from" in script and "--no-recursion" in script
    manifest = _manifest(target)
    assert manifest["skipped_special_files"]["home"] == [".cache/app.sock", "run/fifo"]
    assert not (target / b.HOME_SKIPPED).exists()
    b.verify(target)


def test_cli_backup_create_names_the_left_out_files(env, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    from opencode_sandbox.cli import app
    monkeypatch.setattr(c, "docker", FakeDocker())
    os.mkfifo(_workspace(env) / "pipe")
    result = CliRunner().invoke(app, ["backup", "create", env["name"], "--destination", str(tmp_path / "bk")])
    assert result.exit_code == 0, result.output
    assert "Note: Not in the backup: 1 socket/FIFO file(s) in the workspace" in result.output
    assert "pipe" in result.output
