"""Restore keeps isolation settings; directory modes; umask."""
import json
import os
from types import SimpleNamespace

import pytest

from opencode_sandbox import backup as b
from opencode_sandbox import core as c

RT = {"cpus": "2", "memory": "2g", "pids": 256, "network": "none", "ports": []}


def fake_restore(monkeypatch):
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    # No Docker root to check space on; the unit suite never runs the real Docker CLI.
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr=""))
    monkeypatch.setattr(b, "verify", lambda root: json.loads((root / "manifest.json").read_text()))
    monkeypatch.setattr(b, "_restore_into", lambda m, root, manifest, restore_system=True: c.resolve(m["id"]))


def write_manifest(tmp_path, env):
    root = tmp_path / "x.ocsbackup"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps({"environment": env, "files": {}, "workspace": {"mode": "managed", "included": True}}))
    return root


def test_restore_applies_runtime_and_policy(tmp_path, monkeypatch):
    fake_restore(monkeypatch)
    root = write_manifest(tmp_path, {"name": "orig", "kind": "scratch", "profile": "default", "runtime": RT, "distro": "debian",
                                     "opencode_policy": "pinned", "opencode_pin": "2.1.4"})
    m = b.restore(root, "ocs-qa-restored")
    assert m["runtime"] == c.validate_runtime_settings(RT)
    assert m["runtime"]["network"] == "none"
    assert (m["opencode_policy"], m["opencode_pin"]) == ("pinned", "2.1.4")
    assert m["restore_warnings"] == []


def test_old_backup_without_runtime_warns(tmp_path, monkeypatch):
    fake_restore(monkeypatch)
    root = write_manifest(tmp_path, {"name": "orig", "kind": "scratch", "profile": "default", "distro": "debian"})
    m = b.restore(root, "ocs-qa-restored")
    assert m["runtime"]["network"] == "bridge"
    assert any("no runtime settings" in w for w in m["restore_warnings"])


@pytest.mark.parametrize("bad", [{**RT, "network": "host"}, {**RT, "privileged": True}, "none"])
def test_hostile_runtime_rejected_before_anything_is_created(tmp_path, monkeypatch, bad):
    fake_restore(monkeypatch)
    root = write_manifest(tmp_path, {"name": "o", "kind": "scratch", "runtime": bad})
    with pytest.raises(c.SandboxError):
        b.restore(root, "ocs-qa-restored")
    assert c.all_envs() == []


def test_conflicting_ports_dropped_with_warning(tmp_path, monkeypatch):
    fake_restore(monkeypatch)
    ports = [{"host": 18080, "container": 8000, "protocol": "tcp"}]
    orig = c.create("orig", "scratch")
    orig["runtime"] = c.validate_runtime_settings({**RT, "network": "bridge", "ports": ports})
    c.save(orig)
    root = write_manifest(tmp_path, {"name": "orig", "kind": "scratch", "distro": "debian", "runtime": {**RT, "network": "bridge", "ports": ports}})
    m = b.restore(root, "ocs-qa-restored")
    assert m["runtime"]["ports"] == [] and m["runtime"]["network"] == "bridge"
    assert any("18080" in w for w in m["restore_warnings"])


def test_unpack_restores_directory_modes(tmp_path):
    src = tmp_path / "src"
    (src / "open" / "deep").mkdir(parents=True)
    (src / "private").mkdir()
    (src / "open" / "deep" / "f").write_text("x")
    os.chmod(src / "open", 0o777); os.chmod(src / "private", 0o700); os.chmod(src / "open" / "deep", 0o2750)
    b.archive_directory(src, tmp_path / "a.tar.gz")
    out = tmp_path / "out"
    b.unpack(tmp_path / "a.tar.gz", out)
    mode = lambda p: (out / p).stat().st_mode & 0o7777
    assert (mode("open"), mode("private"), mode("open/deep")) == (0o777, 0o700, 0o2750)


def test_managed_launcher_sets_umask(monkeypatch):
    m = c.create("ocs-qa-umask", "scratch")
    seen = []
    monkeypatch.setattr(c, "_tty", lambda: True)
    monkeypatch.setattr(c, "start", lambda m: None)
    monkeypatch.setattr(c, "observed_runtime", lambda m: None)
    monkeypatch.setattr(c, "profile_mismatch", lambda m: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: seen.append(a) or type("R", (), {"returncode": 0})())
    c.interactive(m)
    assert "os.umask(0o022)" in seen[0][seen[0].index("-c") + 1]


def _image_tar(tmp_path, repo_tags, ann_name, ref, n=1):
    import io
    import tarfile
    path = tmp_path / "system-image.tar"
    manifest = [{"Config": "blobs/sha256/" + "c" * 64, "RepoTags": repo_tags, "Layers": []}] * n
    index = {"schemaVersion": 2, "manifests": [{"digest": "sha256:" + "d" * 64,
             "annotations": {"io.containerd.image.name": ann_name, "org.opencontainers.image.ref.name": ref}}] * n}
    with tarfile.open(path, "w") as tf:
        for name, obj in (("manifest.json", manifest), ("index.json", index)):
            data = json.dumps(obj).encode(); info = tarfile.TarInfo(name); info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path

GOOD = "ocs-backup:" + "a" * 16 + "-" + "b" * 10


def test_image_archive_with_managed_tag_accepted(tmp_path):
    tag, digests = b._image_archive_tag(_image_tar(tmp_path, [GOOD], "docker.io/library/" + GOOD, "a" * 16 + "-" + "b" * 10))
    assert tag == GOOD and "sha256:" + "d" * 64 in digests


@pytest.mark.parametrize("repo_tags,ann,ref,n", [
    (["opencode-sandbox:debian"], "docker.io/library/opencode-sandbox:debian", "debian", 1),     # base image hijack
    ([GOOD, "opencode-sandbox:debian"], "docker.io/library/" + GOOD, "x", 1),            # extra name
    ([GOOD], "docker.io/library/opencode-sandbox:debian", "debian", 1),                       # index disagrees
    ([GOOD], "docker.io/library/" + GOOD, "a" * 16 + "-" + "b" * 10, 2),          # two images
])
def test_image_archive_cannot_claim_other_tags(tmp_path, repo_tags, ann, ref, n):
    with pytest.raises(c.SandboxError):
        b._image_archive_tag(_image_tar(tmp_path, repo_tags, ann, ref, n))


def test_existing_tag_with_other_content_refused(tmp_path, monkeypatch):
    from types import SimpleNamespace
    path = _image_tar(tmp_path, [GOOD], "docker.io/library/" + GOOD, "a" * 16 + "-" + "b" * 10)
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=0, stdout="sha256:" + "e" * 64 + "\n"))
    with pytest.raises(c.SandboxError, match="different content"):
        b._check_image_tag_free(path)
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=0, stdout="sha256:" + "d" * 64 + "\n"))
    assert b._check_image_tag_free(path) == GOOD  # same image again: restore twice works


def test_archive_entry_limit(tmp_path, monkeypatch):
    src = tmp_path / "many"; src.mkdir()
    for i in range(30):
        (src / f"f{i}").write_text("x")
    b.archive_directory(src, tmp_path / "a.tar.gz")
    monkeypatch.setenv("OPENCODE_SANDBOX_MAX_ARCHIVE_ENTRIES", "10")
    with pytest.raises(c.SandboxError, match="more than 10 entries"):
        b._validate_archive(tmp_path / "a.tar.gz")


def test_restore_refuses_archive_larger_than_free_space(tmp_path, monkeypatch):
    """Decompression bomb: tiny compressed archive, huge declared/extracted size."""
    import hashlib
    import io
    import tarfile
    from collections import namedtuple
    root = tmp_path / "bomb.ocsbackup"; root.mkdir()
    big = 2**30
    class Zeros(io.RawIOBase):
        def __init__(self): self.left = big
        def readable(self): return True
        def readinto(self, b):
            n = min(len(b), self.left); b[:n] = bytes(n); self.left -= n; return n
    with tarfile.open(root / "workspace.tar.gz", "w:gz", compresslevel=1) as tf:
        info = tarfile.TarInfo("zeros"); info.size = big
        tf.addfile(info, io.BufferedReader(Zeros(), 1 << 20))
    data = (root / "workspace.tar.gz").read_bytes()
    assert len(data) < 16 * 2**20
    (root / "manifest.json").write_text(json.dumps({"format": "opencode-sandbox-backup", "schema": b.SCHEMA, "created": "x", "workspace": {"mode": "managed", "included": True},
        "environment": {"name": "b", "kind": "scratch", "distro": "debian"},
        "files": {"workspace.tar.gz": {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}}}))
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})())
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(b.shutil, "disk_usage", lambda p: Usage(10 * 2**30, 9 * 2**30, 256 * 2**20))
    with pytest.raises(c.SandboxError, match="Insufficient disk space"):
        b.restore(root, "ocs-qa-bomb")
    assert c.all_envs() == []
