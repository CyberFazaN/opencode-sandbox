"""Backup, restore and message correctness: malformed manifests, prune grouping and order, restored
modification times, change transfer of a restored project, a failed first start that left a
created container, and default snapshot tags. Docker is mocked; Git is the host's."""
import json
import os
import subprocess
from datetime import datetime

import pytest
from test_backup_completeness import FakeDocker
from test_gitflow_roundtrip import sandbox  # noqa: F401  (fixture)
from typer.testing import CliRunner

from opencode_sandbox import backup as b
from opencode_sandbox import config_plan as cp
from opencode_sandbox import core as c
from opencode_sandbox import gitflow
from opencode_sandbox import opencode_versions as v
from opencode_sandbox.cli import app


@pytest.fixture
def docker(monkeypatch):
    fake = FakeDocker()
    for name, value in (("ensure_runtime", lambda image=True: None), ("inspect_container", lambda m: None),
                        ("assert_volume_owned", lambda m: None), ("volume_state", lambda m: None),
                        ("docker", fake)):
        monkeypatch.setattr(c, name, value)
    return fake


# --- malformed manifests --------------------------------------------------------------

def _manifest_dir(tmp_path, text):
    root = tmp_path / "x.ocsbackup"
    root.mkdir()
    (root / "manifest.json").write_text(text)
    return root


VALID = {"format": "opencode-sandbox-backup", "schema": b.SCHEMA, "created": "2026-10-28T00:00:00+00:00",
         "environment": {"name": "app"}, "files": {}, "workspace": {"mode": "direct", "included": False}}


@pytest.mark.parametrize("text", [
    "{not json", "[]", '"text"', "\xff",
    json.dumps({**VALID, "environment": ["app"]}),
    json.dumps({**VALID, "files": {"home.tar.gz": 5}, "workspace": {"mode": "direct", "included": False}}),
    json.dumps({**VALID, "created": 5}),
])
def test_malformed_manifest_is_a_sandbox_error(tmp_path, text):
    root = _manifest_dir(tmp_path, text)
    if text == "\xff":
        (root / "manifest.json").write_bytes(b"\xff\xfe")
    if "home.tar.gz" in text:
        (root / "home.tar.gz").write_bytes(b"x")
    with pytest.raises(c.SandboxError):
        b.verify(root)
    result = CliRunner().invoke(app, ["backup", "verify", str(root)])
    assert isinstance(result.exception, c.SandboxError), result.exception


def test_valid_minimal_manifest_still_verifies(tmp_path):
    """Guard."""
    assert b.verify(_manifest_dir(tmp_path, json.dumps(VALID)))["environment"]["name"] == "app"


# --- prune ------------------------------------------------------------------------------

def test_prune_keeps_backups_per_environment_not_per_name(docker, tmp_path):
    """Two environments named `app` (the first deleted, the name used again): each keeps its own
    `--keep` newest backups."""
    first = c.create("app", "scratch")
    old = [b.backup(first, tmp_path / "bk") for _ in range(2)]
    c.mark(first, "ready", name="app-gone")
    second = c.create("app", "scratch")
    new = b.backup(second, tmp_path / "bk")
    selected, skipped = b.prune(tmp_path / "bk", keep=1)
    assert skipped == [] and selected == [old[0]]
    assert json.loads((new / "manifest.json").read_text())["environment"]["id"] == second["id"]


def test_prune_orders_by_the_recorded_creation_time(docker, tmp_path):
    """Copied backups lose their directory times; the manifest's `created` decides."""
    m = c.create("app", "scratch")
    older, newer = (b.backup(m, tmp_path / "bk") for _ in range(2))
    os.utime(older, (2_000_000_000, 2_000_000_000))  # the older backup looks newer on disk
    os.utime(newer, (1_000_000_000, 1_000_000_000))
    selected, _ = b.prune(tmp_path / "bk", keep=1)
    assert selected == [older]


def test_prune_never_deletes_a_backup_without_a_valid_creation_time(docker, tmp_path):
    m = c.create("app", "scratch")
    first, second = (b.backup(m, tmp_path / "bk") for _ in range(2))
    manifest = json.loads((first / "manifest.json").read_text())
    (first / "manifest.json").write_text(json.dumps({**manifest, "created": "yesterday"}))
    selected, skipped = b.prune(tmp_path / "bk", keep=0)
    assert selected == [second] and [p for p, _ in skipped] == [first]


# --- modification times -----------------------------------------------------------------

def test_unpack_restores_modification_times(tmp_path):
    src = tmp_path / "src"
    (src / "dir" / "sub").mkdir(parents=True)
    (src / "dir" / "file.txt").write_text("x")
    (src / "dir" / "sub" / "deep.txt").write_text("y")
    (src / "hard.txt").hardlink_to(src / "dir" / "file.txt")
    os.symlink("dir/file.txt", src / "link")
    times = {"dir/file.txt": 1_600_000_000, "dir/sub/deep.txt": 1_600_000_100, "link": 1_600_000_200,
             "dir/sub": 1_600_000_300, "dir": 1_600_000_400}
    for rel, t in times.items():
        os.utime(src / rel, (t, t), follow_symlinks=False)
    b.archive_directory(src, tmp_path / "w.tar.gz")
    out = tmp_path / "out"
    b.unpack(tmp_path / "w.tar.gz", out)
    for rel, t in times.items():
        assert int(os.lstat(out / rel).st_mtime) == t, rel


# --- change transfer of a restored project ------------------------------------------------

def test_restored_project_without_source_can_still_bundle(sandbox, tmp_path):  # noqa: F811
    """Restore records no source (it named a directory of the backed-up machine); the base
    commit is what the transfer needs."""
    m, _, _ = sandbox
    m = c.resolve(m["id"])
    m["source"] = None
    c.save(m)
    bundle = gitflow.export_changes(m, tmp_path / "out")
    assert gitflow.inspect_changes(bundle)["base"] == m["base_commit"]


def test_environment_without_a_base_commit_names_the_reason(docker):
    m = c.create("ocs-qa-empty", "scratch")
    subprocess.run(["git", "-C", str(c.env_dir(m["id"]) / "workspace"), "init", "-q"], check=True)
    with pytest.raises(c.SandboxError, match="no recorded base commit"):
        gitflow.change_summary(m)


# --- failed first start -------------------------------------------------------------------

class CreatedOnFailure:
    """`docker run` creates the container, then fails to start it (e.g. the host port is taken)."""

    def __init__(self, monkeypatch):
        self.state, self.calls = None, []
        monkeypatch.setattr(c, "docker", self)
        monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
        monkeypatch.setattr(c, "inspect_container", lambda m: self.state)
        monkeypatch.setattr(c, "ensure_volume", lambda m: None)
        monkeypatch.setattr(c, "host_cpus", lambda: 8)

    def __call__(self, *args, capture=False, check=True):
        self.calls.append(args)
        if args[0] == "run":
            self.state = {"Running": False, "Status": "created"}
            raise c.SandboxError("Command failed (125): docker run: port is already allocated")
        if args[0] == "rm":
            self.state = None
        return subprocess.CompletedProcess(args, 0, "", "")


def test_failed_first_start_leaves_no_created_container(monkeypatch):
    fake = CreatedOnFailure(monkeypatch)
    m = c.create("ocs-qa-port", "scratch")
    with pytest.raises(c.SandboxError, match="already allocated"):
        c.start(m)
    assert fake.state is None and ("rm", c.cname(m)) in fake.calls
    m = c.resolve(m["id"])
    assert m["status"] == "error" and "already allocated" in m["last_error"]
    p = cp.plan(m, {"ports": []})
    assert p.blockers == () and p.category in ("saved", "none")


def test_pending_start_names_repair_cleanup():
    m = c.create("ocs-qa-port", "scratch")
    c.mark(m, "creating", operation="start")
    assert "repair ocs-qa-port --cleanup" in str(c.pending_operation(c.resolve(m["id"])))


# --- default snapshot tags ----------------------------------------------------------------

class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 28, 12, 0, 0, tzinfo=tz)


def test_two_snapshots_in_one_second_get_different_tags(docker, monkeypatch):
    monkeypatch.setattr(c, "datetime", FixedClock)
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False})
    monkeypatch.setattr(c, "require_docker_space", lambda what: None)
    m = c.create("ocs-qa-snap", "scratch")
    first, second = c.snapshot(m), c.snapshot(m)
    assert first != second and all(t.startswith(f"ocs-snapshot:{m['id']}-20261028120000-") for t in (first, second))


def test_default_snapshot_tag_never_moves_an_existing_tag(docker, monkeypatch):
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False})
    monkeypatch.setattr(c, "require_docker_space", lambda what: None)
    monkeypatch.setattr(c.secrets, "token_hex", lambda n: "0" * (2 * n))
    m = c.create("ocs-qa-snap", "scratch")
    monkeypatch.setattr(c, "datetime", FixedClock)
    docker.present.add(f"ocs-snapshot:{m['id']}-20261028120000-000000")
    with pytest.raises(c.SandboxError, match="already exists"):
        c.snapshot(m)
    assert not any(a[0] == "commit" for a in docker.calls)


def test_opencode_rollback_without_container_never_moves_an_earlier_snapshot_tag(monkeypatch):
    """The rollback tags the derived image as a snapshot; one made in the same second before
    must keep its tag."""
    from test_opencode_lifecycle import FakeDocker as VersionsDocker
    from test_opencode_lifecycle import env
    fake = VersionsDocker(monkeypatch)
    m = env()
    v.update_environment(m, "2.2.0")
    m = c.resolve(m["id"]); m["image"] = runtime = f"ocs-runtime:{m['id']}-0123456789ab"; c.save(m)
    fake.images.add(runtime); fake.exists = False
    monkeypatch.setattr(c, "datetime", FixedClock)
    earlier = f"ocs-snapshot:{m['id']}-20261028120000"
    fake.images.add(earlier)
    result = v.rollback_environment(m)
    assert result["snapshot"] != earlier and result["snapshot"].startswith(f"ocs-snapshot:{m['id']}-20261028120000-")
