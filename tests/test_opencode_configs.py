"""Whole-tree semantics and recovery with real host files; Docker transport is tested separately."""
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import config_tree as tree
from opencode_sandbox import config_volume as volume
from opencode_sandbox import core as c
from opencode_sandbox import opencode_configs as oc
from opencode_sandbox.cli import app


def config(path, value="original"):
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    (path / "opencode.json").write_text(json.dumps({"username": value}))
    (path / "tool").write_text("#!/bin/sh\nexit 0\n")
    (path / "tool").chmod(0o751)
    (path / "absolute").symlink_to("/outside/never-read")
    (path / "relative").symlink_to("../other")
    return path


def archive(path):
    out = io.BytesIO()
    digest = tree.snapshot(path, out)
    out.seek(0)
    return out, digest


def test_roundtrip_whole_tree_links_modes_and_deterministic_fingerprint(tmp_path):
    source = config(tmp_path / "source")
    (source / "empty").mkdir(mode=0o711)
    (source / "private").write_bytes(b"dummy-secret\0bytes")
    packed, digest = archive(source)
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    tree.unpack(packed, target)
    assert tree.sample(target) == digest == tree.sample(source)
    assert stat.S_IMODE((target / "tool").stat().st_mode) == 0o751
    assert stat.S_IMODE((target / "empty").stat().st_mode) == 0o711
    assert os.readlink(target / "absolute") == "/outside/never-read"
    assert os.readlink(target / "relative") == "../other"
    assert (target / "private").read_bytes() == b"dummy-secret\0bytes"


@pytest.mark.parametrize("change", ["bytes", "mode", "rename", "add", "delete", "link"])
def test_fingerprint_detects_every_relevant_change(tmp_path, change):
    source = config(tmp_path / "source")
    before = tree.sample(source)
    if change == "bytes": (source / "tool").write_bytes(b"different")
    elif change == "mode": (source / "tool").chmod(0o750)
    elif change == "rename": (source / "tool").rename(source / "renamed")
    elif change == "add": (source / "added").mkdir()
    elif change == "delete": (source / "tool").unlink()
    else:
        (source / "absolute").unlink()
        (source / "absolute").symlink_to("/different-target")
    assert tree.sample(source) != before


def test_missing_and_empty_are_consistent(tmp_path):
    path = tmp_path / "empty"
    absent = tree.sample(path)
    path.mkdir(mode=0o700)
    assert tree.sample(path) == absent


def test_special_file_and_limits_fail_without_following_links(tmp_path):
    source = config(tmp_path / "source")
    os.mkfifo(source / "fifo")
    with pytest.raises(tree.TreeError, match="Unsupported"):
        archive(source)
    (source / "fifo").unlink()
    with pytest.raises(tree.TreeError, match="entry limit"):
        tree.sample(source, max_entries=1)
    with pytest.raises(tree.TreeError, match="byte limit"):
        tree.sample(source, max_bytes=1)


def test_snapshot_rejects_concurrent_edit(tmp_path, monkeypatch):
    source = config(tmp_path / "source")
    original = tree.sample
    def sample(path, out=None, **options):
        result = original(path, out, **options)
        if out: (source / "opencode.json").write_text("changed")
        return result
    monkeypatch.setattr(tree, "sample", sample)
    with pytest.raises(tree.TreeError, match="changed while copying"):
        archive(source)


@pytest.mark.parametrize("names", [["../escape"], ["/absolute"], ["link", "link/child"], ["same", "same"]])
def test_archive_refuses_traversal_duplicate_and_link_parents(tmp_path, names):
    packed = io.BytesIO()
    with tarfile.open(fileobj=packed, mode="w") as tf:
        for name in names:
            info = tarfile.TarInfo(name)
            if name == "link": info.type, info.linkname = tarfile.SYMTYPE, str(tmp_path / "outside")
            else: info.size = 1
            tf.addfile(info, None if info.issym() else io.BytesIO(b"x"))
    packed.seek(0)
    target = tmp_path / "stage"
    target.mkdir()
    with pytest.raises((tree.TreeError, OSError)):
        tree.unpack(packed, target)
    assert not (tmp_path / "outside").exists()


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(oc, "TMP", tmp_path / "tmp")
    oc.TMP.mkdir(mode=0o1777)
    m = c.create("ocs-qa-config")
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    live = config(home / ".config" / "opencode")
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False})
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: {"Labels": {
        "org.opencode-sandbox.id": m["id"], c.DATA_LABEL: c.data_id(), "org.opencode-sandbox.managed": "true"}})
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=0,
                        stdout="sha256:" + "1" * 64 if a[:2] == ("container", "inspect") else "null", stderr=""))
    def operation(m, action, *, incoming=None, outgoing=None, **options):
        return volume.operation(str(home), {"action": action, "binding": oc.binding(m), **oc.limits(), **options},
                                incoming, outgoing)
    monkeypatch.setattr(oc, "volume_operation", operation)
    return m, home, live


def test_export_apply_reopen_and_baseline_is_not_edited_host_tree(service):
    m, _, live = service
    original = tree.sample(live)
    exported = Path(oc.export(m))
    marker = exported.parent / oc.MARKER
    assert json.loads(marker.read_text())["fingerprint"] == original
    assert oc.status(c.resolve(m["id"])) == {"state": "Export available", "path": str(exported)}
    (exported / "opencode.json").write_text('{"username":"host edit"}')
    assert json.loads(marker.read_text())["fingerprint"] == original
    oc.apply(m)
    assert (live / "opencode.json").read_text() == '{"username":"host edit"}'
    assert json.loads(marker.read_text())["fingerprint"] == tree.sample(live)
    oc.apply(m)  # no false conflict on repeated Apply
    assert stat.S_IMODE(exported.parent.stat().st_mode) == 0o700


def test_drift_cancel_override_and_new_drift_requires_new_consent(service):
    m, _, live = service
    exported = Path(oc.export(m))
    baseline = (exported.parent / oc.MARKER).read_bytes()
    (exported / "opencode.json").write_text("edited host bytes")
    (live / "opencode.json").write_text("new container bytes")
    metadata = c.resolve(m["id"])
    with pytest.raises(oc.Conflict) as conflict: oc.apply(m)
    assert (live / "opencode.json").read_text() == "new container bytes"
    assert (exported.parent / oc.MARKER).read_bytes() == baseline
    assert c.resolve(m["id"]) == metadata
    accepted = conflict.value.fingerprint
    (live / "opencode.json").write_text("changed again")
    with pytest.raises(oc.Conflict): oc.apply(m, overwrite=accepted)
    oc.apply(m, overwrite=tree.sample(live))
    assert (live / "opencode.json").read_text() == "edited host bytes"


def test_export_replacement_failure_cancel_and_delete_preserve_live(service, monkeypatch):
    m, _, live = service
    exported = Path(oc.export(m))
    (exported / "edit").write_text("unapplied")
    with pytest.raises(c.SandboxError, match="confirm replacement"): oc.export(m)
    real = oc.volume_operation
    def failed(*a, **k): raise c.SandboxError("injected export failure")
    monkeypatch.setattr(oc, "volume_operation", failed)
    with pytest.raises(c.SandboxError): oc.export(m, replace=True)
    assert (exported / "edit").read_text() == "unapplied"
    monkeypatch.setattr(oc, "volume_operation", real)
    before = tree.sample(live)
    with pytest.raises(c.SandboxError, match="Confirm Delete"): oc.delete_export(m)
    oc.delete_export(m, confirmed=True)
    assert oc.status(m)["state"] == "No export" and tree.sample(live) == before
    with pytest.raises(c.SandboxError, match="No export"): oc.apply(m)


def test_reload_empty_profile_symlink_and_source_independence(service, tmp_path):
    m, home, live = service
    source = config(tmp_path / "user-source", "profile")
    oc.profiles_directory().mkdir(parents=True)
    (oc.profiles_directory() / "work").symlink_to(source, target_is_directory=True)
    adjacent = home / ".local" / "share"
    adjacent.mkdir(parents=True)
    (adjacent / "auth.json").write_text("dummy-auth")
    assert oc.profiles() == ["work"]
    oc.reload(m, "work", confirmed=True)
    assert tree.sample(live) == tree.sample(source)
    (source / "opencode.json").write_text("later source edit")
    assert "profile" in (live / "opencode.json").read_text()
    oc.reload(m, None, confirmed=True)
    assert live.is_dir() and list(live.iterdir()) == []
    assert (adjacent / "auth.json").read_text() == "dummy-auth"


def test_invalid_reload_source_and_failing_stage_keep_original(service, tmp_path, monkeypatch):
    m, _, live = service
    before = tree.sample(live)
    with pytest.raises(c.SandboxError): oc.reload(m, "missing", confirmed=True)
    assert tree.sample(live) == before and not c.resolve(m["id"]).get("operation")
    def fail(*a, **k): raise tree.TreeError("injected stage failure")
    monkeypatch.setattr(volume, "unpack", fail)
    with pytest.raises(tree.TreeError): oc.reload(m, None, confirmed=True)
    assert tree.sample(live) == before
    assert c.resolve(m["id"])["operation"] == "opencode-config"
    oc.recover(m)
    assert not c.resolve(m["id"]).get("operation")


@pytest.mark.parametrize("kind", ["symlink", "mode", "marker", "identity", "config-link", "baseline-type", "binding-type"])
def test_untrusted_predictable_export_path_refused_and_preserved(service, tmp_path, kind):
    m, _, live = service
    exported = Path(oc.export(m))
    root = exported.parent
    if kind == "symlink":
        root.rename(root.with_name("retained"))
        root.symlink_to(tmp_path)
    elif kind == "mode": root.chmod(0o755)
    elif kind == "marker": (root / oc.MARKER).chmod(0o644)
    elif kind == "identity":
        record = json.loads((root / oc.MARKER).read_text())
        record["binding"]["created"] = "another environment"
        tree.write_json(root / oc.MARKER, record)
    elif kind in ("baseline-type", "binding-type"):
        record = json.loads((root / oc.MARKER).read_text())
        if kind == "baseline-type": record["fingerprint"] = int("1" * 64)
        else: record["binding"]["schema"] = True
        tree.write_json(root / oc.MARKER, record)
    else:
        exported.rename(root / "retained")
        exported.symlink_to(tmp_path)
    before = tree.sample(live)
    for operation in (lambda: oc.status(m), lambda: oc.export(m, replace=True),
                      lambda: oc.delete_export(m, confirmed=True), lambda: oc.apply(m)):
        with pytest.raises(c.SandboxError): operation()
    assert root.exists() and tree.sample(live) == before


def test_export_namespaces_stable_across_container_recreation_and_names_not_reused(service, monkeypatch):
    m, _, _ = service
    path = oc.export(m)
    changed = {**m, "image": "different", "name": "renamed"}
    assert str(oc.export_path(changed) / "config") == path
    another = c.create("another")
    assert oc.export_path(another) != oc.export_path(m)
    monkeypatch.setattr(c, "BASE", c.BASE / "different-root")
    assert str(oc.export_path(m) / "config") != path


@pytest.mark.parametrize("phase", ["exchange", "commit", "cleanup"])
def test_actual_process_death_recovery_before_and_after_commit(tmp_path, phase):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    live = config(home / ".config" / "opencode", "old")
    new = config(tmp_path / "new", "new")
    packed, _ = archive(new)
    request = {"binding": {"id": "fixture"}, "action": "replace", "max_bytes": tree.MAX_BYTES, "max_entries": tree.MAX_ENTRIES}
    hooks = {
        "exchange": "original=exchange\ndef exchange(a,b):\n original(a,b)\n os._exit(77)\n",
        "commit": "original=write_json\ndef write_json(p,v):\n original(p,v)\n if v.get('phase')=='committed': os._exit(77)\n",
        "cleanup": "original=shutil.rmtree\ndef remove(p):\n original(p)\n os._exit(77)\nshutil.rmtree=remove\n",
    }
    hook = hooks[phase]
    source = oc._helper_source().rsplit("helper_main()", 1)[0]
    code = source + "\n" + hook + f"\noperation({str(home)!r},json.loads(sys.argv[1]),sys.stdin.buffer,sys.stdout.buffer)"
    p = subprocess.run([sys.executable, "-c", code, json.dumps(request)], input=packed.read(), capture_output=True, check=False)
    assert p.returncode == 77, p.stderr
    assert "new" in (live / "opencode.json").read_text()
    volume.operation(str(home), {**request, "action": "recover"}, None, None)
    assert ("old" if phase == "exchange" else "new") in (live / "opencode.json").read_text()
    assert not (home / ".config" / ".ocs-occonfig-transaction").exists()


def test_cli_editor_actions_and_reload_default(service):
    m, _, live = service
    runner = CliRunner()
    assert "No export" in runner.invoke(app, ["opencode-configs", "status", m["name"]]).output
    assert runner.invoke(app, ["opencode-configs", "export", m["name"]]).exit_code == 0
    assert runner.invoke(app, ["opencode-configs", "reload", m["name"], "--yes"]).exit_code == 0
    assert list(live.iterdir()) == []  # Local defaults to Empty
    conflict = runner.invoke(app, ["opencode-configs", "apply", m["name"]])
    assert conflict.exit_code != 0 and "preserved" in str(conflict.exception)
    assert runner.invoke(app, ["opencode-configs", "apply", m["name"], "--overwrite"]).exit_code == 0
    assert runner.invoke(app, ["opencode-configs", "delete-export", m["name"], "--yes"]).exit_code == 0


@pytest.mark.parametrize("channel", ["stdout", "stderr"])
def test_host_transport_bounds_untrusted_helper_output(channel):
    code = f"import sys; sys.{channel}.buffer.write(b'x'*200000); sys.{channel}.flush()"
    with pytest.raises(c.SandboxError, match="exceeded"):
        oc._transfer([sys.executable, "-c", code], None, io.BytesIO(), max_output=100)


def test_reject_oversized_pax_metadata_before_reading_payload(tmp_path):
    info = tarfile.TarInfo("././@PaxHeader")
    info.type, info.size = tarfile.XHDTYPE, 2 * 1024**2
    packed = io.BytesIO(info.tobuf())
    target = tmp_path / "stage"
    target.mkdir()
    with pytest.raises(tree.TreeError, match="oversized"):
        tree.unpack(packed, target)


def test_change_at_directory_switch_is_detected_and_preserved(service, monkeypatch):
    m, _, live = service
    exported = Path(oc.export(m))
    (exported / "opencode.json").write_text("new host copy")
    original = volume.exchange
    calls = []
    def exchange(first, second):
        original(first, second)
        if not calls:
            (Path(second) / "opencode.json").write_text("container write at switch")
        calls.append(1)
    monkeypatch.setattr(volume, "exchange", exchange)
    with pytest.raises(tree.TreeError, match="changed during the switch"): oc.apply(m)
    assert (live / "opencode.json").read_text() == "container write at switch"
    assert (exported / "opencode.json").read_text() == "new host copy"
    oc.recover(m)
    assert not c.resolve(m["id"]).get("operation")


def test_predictable_namespace_collision_is_never_adopted(service):
    m, _, _ = service
    namespace = oc.export_path(m).parent
    namespace.mkdir(mode=0o700)
    (namespace / "unrelated").write_text("keep")
    with pytest.raises(c.SandboxError): oc.export(m)
    assert list(namespace.iterdir()) == [namespace / "unrelated"]


def test_invalid_copy_source_fails_before_environment_or_runtime_changes(tmp_path, monkeypatch):
    root = oc.profiles_directory()
    root.mkdir(parents=True)
    source = config(root / "invalid")
    os.mkfifo(source / "unsupported")
    def unexpected(*a, **k): raise AssertionError("persistent/runtime work preceded source validation")
    monkeypatch.setattr(c, "ensure_runtime", unexpected)
    with pytest.raises(c.SandboxError, match="Unsupported config entry"):
        c.create("ocs-qa-invalid-copy", opencode_config="invalid")
    assert c.all_envs() == []


def test_copy_intent_blocks_start_before_publication_and_retains_completed_volume(tmp_path, monkeypatch):
    root = oc.profiles_directory()
    root.mkdir(parents=True)
    config(root / "work")
    monkeypatch.setattr(c, "ensure_runtime", lambda *a: None)
    observed = []
    def initialize(m, archive):
        observed.append(c.resolve(m["id"])["operation"])
        assert observed == ["opencode-config"]
    monkeypatch.setattr(oc, "initialize", initialize)
    real_mark = c.mark
    def fail_publication(m, status, **fields):
        if status == "ready": raise OSError("injected metadata publication failure")
        return real_mark(m, status, **fields)
    monkeypatch.setattr(c, "mark", fail_publication)
    with pytest.raises(OSError): c.create("ocs-qa-copy", opencode_config="work")
    m = c.resolve("ocs-qa-copy")
    assert m["operation"] == "opencode-config" and m["status"] == "error"


def test_initial_copy_unknown_cleanup_preserves_environment_identity(service, monkeypatch):
    m, _, _ = service
    monkeypatch.setattr(c, "volume_state", lambda m: None)
    monkeypatch.setattr(c, "ensure_volume", lambda m: None)
    def unavailable(*a, **k): raise c.SandboxError("daemon unavailable")
    monkeypatch.setattr(oc, "volume_operation", unavailable)
    monkeypatch.setattr(c, "assert_volume_owned", unavailable)
    with pytest.raises(c.SandboxError) as error: oc.initialize(m, io.BytesIO())
    assert error.value.preserve_environment is True


def test_export_publication_sync_failure_restores_existing_host_edits(service, monkeypatch):
    m, _, live = service
    exported = Path(oc.export(m))
    (exported / "unapplied").write_text("keep my edits")
    marker = (exported.parent / oc.MARKER).read_bytes()
    original = tree.sync_directory
    failed = []
    def sync(path):
        if Path(path) == exported.parent.parent and not failed:
            failed.append(True)
            raise OSError("injected export publication failure")
        return original(path)
    monkeypatch.setattr(tree, "sync_directory", sync)
    with pytest.raises(OSError, match="publication failure"): oc.export(m, replace=True)
    assert (exported / "unapplied").read_text() == "keep my edits"
    assert (exported.parent / oc.MARKER).read_bytes() == marker
    assert "original" in (live / "opencode.json").read_text()


def test_failed_apply_baseline_write_never_claims_container_was_unchanged(service, monkeypatch):
    m, _, live = service
    exported = Path(oc.export(m))
    (exported / "opencode.json").write_text("successfully installed bytes")
    original = tree.write_json
    def write(path, value):
        if Path(path) == exported.parent / oc.MARKER:
            raise OSError("injected baseline persistence failure")
        return original(path, value)
    monkeypatch.setattr(tree, "write_json", write)
    with pytest.raises(OSError, match="baseline persistence failure"):
        oc.apply(m)
    assert (live / "opencode.json").read_text() == "successfully installed bytes"
    assert c.resolve(m["id"])["operation"] == "opencode-config"
    oc.recover(m)


def test_unavailable_volume_refuses_apply_reload_without_stranding_a_journal(service, monkeypatch):
    m, _, live = service
    exported = Path(oc.export(m))
    marker = (exported.parent / oc.MARKER).read_bytes()
    metadata = c.resolve(m["id"])
    before = tree.sample(live)
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    for operation in (lambda: oc.apply(m), lambda: oc.reload(m, None, confirmed=True)):
        with pytest.raises(c.SandboxError, match="volume is unavailable"): operation()
        assert c.resolve(m["id"]) == metadata
        assert tree.sample(live) == before and (exported.parent / oc.MARKER).read_bytes() == marker


def test_profile_disappearing_after_discovery_never_means_empty_reload(service, monkeypatch):
    m, _, live = service
    oc.profiles_directory().mkdir(parents=True)
    source = config(oc.profiles_directory() / "gone")
    metadata, before = c.resolve(m["id"]), tree.sample(live)
    real = oc.profile_path
    def discovered(name):
        path = real(name)
        shutil.rmtree(source)  # another host tool removed it after discovery
        return path
    monkeypatch.setattr(oc, "profile_path", discovered)
    with pytest.raises(c.SandboxError, match="source is missing"):
        oc.reload(m, "gone", confirmed=True)
    assert tree.sample(live) == before and c.resolve(m["id"]) == metadata


def test_export_root_disappearing_during_apply_never_installs_empty(service, monkeypatch):
    m, _, live = service
    exported = Path(oc.export(m))
    metadata, before = c.resolve(m["id"]), tree.sample(live)
    real = tree.snapshot
    def snapshot(path, out, **options):
        if Path(path) == exported: shutil.rmtree(exported)
        return real(path, out, **options)
    monkeypatch.setattr(tree, "snapshot", snapshot)
    with pytest.raises(c.SandboxError, match="source is missing"):
        oc.apply(m)
    assert tree.sample(live) == before and c.resolve(m["id"]) == metadata


def test_host_codec_error_is_a_safe_cli_error_not_a_traceback_with_byte_locals(service):
    m, _, live = service
    exported = Path(oc.export(m))
    (exported / "private").write_text("dummy-password-must-not-appear")
    os.mkfifo(exported / "zz-fifo")
    before = tree.sample(live)
    with pytest.raises(c.SandboxError, match="Unsupported config entry") as error:
        oc.apply(m)
    assert "dummy-password-must-not-appear" not in str(error.value)
    assert tree.sample(live) == before and not c.resolve(m["id"]).get("operation")


def test_signal_obscuring_export_exchange_retains_previous_host_copy(service, monkeypatch):
    m, _, _ = service
    exported = Path(oc.export(m))
    (exported / "unapplied").write_text("preserve these host edits")
    original = tree.exchange
    def interrupted(first, second):
        original(first, second)
        raise KeyboardInterrupt()
    monkeypatch.setattr(tree, "exchange", interrupted)
    with pytest.raises(KeyboardInterrupt): oc.export(m, replace=True)
    stages = list(exported.parent.parent.glob(".export-*"))
    assert len(stages) == 1
    assert (stages[0] / "config" / "unapplied").read_text() == "preserve these host edits"


def test_archive_budget_bounds_metadata_too():
    output = io.BytesIO()
    writer = tree.ArchiveSink(output, 100)
    writer.write(b"x" * 60)
    with pytest.raises(tree.TreeError, match="archive exceeds"):
        writer.write(b"y" * 60)
    assert output.getvalue() == b"x" * 60


def test_archive_writer_rechecks_temporary_filesystem_headroom(tmp_path, monkeypatch):
    with (tmp_path / "archive").open("wb") as output:
        writer = tree.ArchiveSink(output, 1024**2)
        monkeypatch.setattr(tree.os, "fstatvfs", lambda fd: SimpleNamespace(f_bavail=0, f_frsize=4096))
        with pytest.raises(tree.TreeError, match="temporary archive space"):
            writer.write(b"x")
        assert output.tell() == 0


def test_entry_budget_stops_directory_enumeration_before_materializing_every_name(tmp_path, monkeypatch):
    observed = []
    @contextmanager
    def entries(fd):
        def iterator():
            for index in range(1000):
                observed.append(index)
                yield SimpleNamespace(name=f"entry-{index}")
        yield iterator()
    monkeypatch.setattr(tree.os, "scandir", entries)
    with pytest.raises(tree.TreeError, match="entry limit"):
        tree.sample(tmp_path, max_entries=3)
    assert len(observed) == 3  # root + two entries fill the budget; stop at the next one


@pytest.mark.parametrize("path", ["/", "/root/.config", "/root/.config/opencode", "/root/.config/opencode/plugins"])
def test_overlapping_image_volume_is_rejected_before_journalling_or_copying(service, monkeypatch, path):
    m, _, live = service
    before, metadata = tree.sample(live), c.resolve(m["id"])
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=0,
                        stdout="sha256:" + "1" * 64 if a[:2] == ("container", "inspect") else json.dumps({path: {}}), stderr=""))
    with pytest.raises(c.SandboxError, match="overlapping image volume"):
        oc.reload(m, None, confirmed=True)
    assert tree.sample(live) == before and c.resolve(m["id"]) == metadata
