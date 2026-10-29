"""The original custom image is kept, and restored system images belong to the restoring
environment and data directory. Docker is mocked; the real campaign covers the same paths
(CAMPAIGN E01, E10)."""
import io
import json
import subprocess
import tarfile

import pytest

from opencode_sandbox import backup as b
from opencode_sandbox import core as c

CUSTOM = "example.org/team/tool:1"


class FakeDocker:
    def __init__(self, present=(), loads=None):
        self.calls = []
        self.present = set(present)
        self.loads = loads

    def __call__(self, *args, capture=False, check=True):
        self.calls.append(args)
        rc, out = 0, ""
        if args[:2] == ("image", "inspect"):
            rc = 0 if args[-1] in self.present else 1
            out = "sha256:" + "0" * 64 if not rc else ""
        elif args[:2] == ("image", "load"):
            self.present.add(self.loads)
            out = f"Loaded image: {self.loads}\n"
        elif args[0] == "commit":
            self.present.add(args[-1])
        elif args[:2] == ("image", "rm"):
            self.present.discard(args[2])
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
def no_container(monkeypatch):
    for name, value in (("ensure_runtime", lambda image=True: None), ("inspect_container", lambda m: None),
                        ("assert_volume_owned", lambda m: None), ("volume_state", lambda m: None)):
        monkeypatch.setattr(c, name, value)


# --- custom-image provenance ---------------------------------------------

def test_custom_image_is_recorded_at_creation():
    m = c.create("ocs-test-custom", "scratch", image=CUSTOM)
    assert m["custom_image"] == CUSTOM and c.custom_image(m) == CUSTOM
    assert c.custom_image(c.create("ocs-test-registry", "scratch")) is None


def test_backup_records_the_original_custom_image_after_a_reconfiguration(no_container, monkeypatch, tmp_path):
    m = c.create("ocs-test-custom", "scratch", image=CUSTOM)
    m["image"] = f"ocs-runtime:{m['id']}-0123456789ab"  # what reconfigure_runtime leaves
    c.save(m)
    monkeypatch.setattr(c, "docker", FakeDocker())
    target = b.backup(m, tmp_path / "bk", include_system=False)
    env = json.loads((target / "manifest.json").read_text())["environment"]
    assert env["custom_image"] == CUSTOM


def test_restore_without_system_image_uses_the_original_custom_image(no_container, monkeypatch, tmp_path):
    m = c.create("ocs-test-custom", "scratch", image=CUSTOM)
    m["image"] = f"ocs-runtime:{m['id']}-0123456789ab"
    c.save(m)
    monkeypatch.setattr(c, "docker", FakeDocker(present={CUSTOM}))
    target = b.backup(m, tmp_path / "bk", include_system=False)
    monkeypatch.setattr(b, "_check_restore_space", lambda *a: None)
    restored = b.restore(target, "ocs-test-restored", restore_system=False)
    assert restored["image"] == CUSTOM and restored["custom_image"] == CUSTOM
    assert restored["restore_warnings"] == []


def test_restore_warns_when_the_custom_image_is_not_local(no_container, monkeypatch, tmp_path):
    m = c.create("ocs-test-custom", "scratch", image=CUSTOM)
    monkeypatch.setattr(c, "docker", FakeDocker())
    target = b.backup(m, tmp_path / "bk", include_system=False)
    monkeypatch.setattr(b, "_check_restore_space", lambda *a: None)
    restored = b.restore(target, "ocs-test-restored", restore_system=False)
    assert restored["image"] == CUSTOM
    assert any(CUSTOM in w and "not present locally" in w for w in restored["restore_warnings"])


def test_superseded_runtime_image_is_kept_while_another_environment_uses_it(monkeypatch):
    a = c.create("ocs-test-a", "scratch")
    shared = f"ocs-runtime:{a['id']}-0123456789ab"
    other = c.create("ocs-test-b", "scratch", image=shared)  # another environment references the same image
    assert other["image"] == shared
    a.update(image=f"ocs-runtime:{a['id']}-ba9876543210", superseded_image=shared, operation="runtime-recreate")
    c.save(a)
    fake = FakeDocker()
    monkeypatch.setattr(c, "docker", fake)
    c._finish_reconfigure(a)
    assert ("image", "rm", shared) not in fake.calls


def test_superseded_runtime_image_is_untagged_when_unused(monkeypatch):
    """Guard: the normal case still untags."""
    a = c.create("ocs-test-a", "scratch")
    old = f"ocs-runtime:{a['id']}-0123456789ab"
    a.update(image=f"ocs-runtime:{a['id']}-ba9876543210", superseded_image=old, operation="runtime-recreate")
    c.save(a)
    fake = FakeDocker()
    monkeypatch.setattr(c, "docker", fake)
    c._finish_reconfigure(a)
    assert ("image", "rm", old) in fake.calls


# --- restored system images are relabelled -------------------------------

def _system_backup(tmp_path, loaded):
    root = tmp_path / "x.ocsbackup"
    root.mkdir()
    _image_archive(root / "system-image.tar", loaded)
    return root, {"files": {"system-image.tar": {}}, "environment": {"kind": "scratch"}}


def _restoring_env():
    m = c.create("ocs-test-restored", "scratch")
    c.mark(m, "restoring", operation="restore", restore_stage="initial")
    return m


@pytest.mark.parametrize("loaded_before", [False, True])
def test_restored_system_image_is_relabelled_for_the_new_environment(no_container, monkeypatch, tmp_path, loaded_before):
    loaded = "ocs-backup:0123456789abcdef-0123456789"  # the old environment's id
    root, manifest = _system_backup(tmp_path, loaded)
    m = _restoring_env()
    fake = FakeDocker(present={loaded} if loaded_before else (), loads=loaded)
    monkeypatch.setattr(c, "docker", fake)
    restored = b._restore_into(m, root, manifest)
    new = restored["image"]
    assert b.BACKUP_TAG.fullmatch(new) and new.startswith(f"ocs-backup:{m['id']}-")
    create = next(a for a in fake.calls if a[0] == "create")
    assert create[create.index("--name") + 1] == c.cname(m) and create[-1] == loaded
    assert "--pull" in create and create[create.index("--pull") + 1] == "never"
    labels = {create[i + 1] for i, a in enumerate(create) if a == "--label"}
    assert f"org.opencode-sandbox.id={m['id']}" in labels and f"{c.DATA_LABEL}={c.data_id()}" in labels
    assert not any(label.startswith(c.HELPER_LABEL) for label in labels)  # images pass labels on to containers
    assert ("commit", c.cname(m), new) in fake.calls
    assert ("rm", "-v", c.cname(m)) in fake.calls
    assert (("image", "rm", loaded) in fake.calls) is (not loaded_before)  # a pre-existing tag is never removed
    assert c.resolve(m["id"])["image"] == new and restored["status"] == "ready"
