"""Cache files are disposable, bounded, private and outside authoritative environment data."""
import json
import os
import time

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import update_cache as cache


def test_missing_cache_does_not_create_data():
    assert cache.read("test") == {}
    assert not c.BASE.exists()


def test_atomic_private_roundtrip_and_key_separation():
    cache.write("one", {"success": {"value": "2.2.0"}})
    cache.write("two", {"success": None})
    assert cache.read("one")["success"]["value"] == "2.2.0"
    assert cache.read("two")["success"] is None
    directory = c.BASE / cache.DIRECTORY
    assert directory.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in directory.iterdir())
    assert not (c.BASE / "environments").exists()
    assert not list(directory.glob(".write-*"))


@pytest.mark.parametrize("body", [b"not JSON", b"[]", b'{"format":2}', b'{"format":1,"key":"other"}',
                                  b"\xff", b" " * (cache.LIMIT + 1), b"[" * 2000 + b"]" * 2000,
                                  b'{"format":1,"key":"test","extra":NaN}'])
def test_invalid_cache_is_only_a_miss(body):
    cache.write("test", {})
    path = c.BASE / cache.DIRECTORY / cache._name("test")
    path.write_bytes(body)
    assert cache.read("test") == {}


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "public"])
def test_unsafe_cache_file_is_neither_followed_nor_repaired(tmp_path, kind):
    cache.write("test", {})
    path = c.BASE / cache.DIRECTORY / cache._name("test")
    path.unlink()
    target = tmp_path / "untouched"
    target.write_text("retain me")
    if kind == "symlink": path.symlink_to(target)
    if kind == "hardlink": os.link(target, path)
    if kind == "fifo": os.mkfifo(path)
    if kind == "public": path.write_text("retain me"); path.chmod(0o644)
    before = path.lstat()
    assert cache.read("test") == {}
    cache.write("test", {"new": True})
    assert path.lstat() == before
    assert target.read_text() == "retain me"


@pytest.mark.parametrize("kind", ["symlink", "public", "file"])
def test_unsafe_directory_is_ignored_without_repair(tmp_path, kind):
    c.BASE.mkdir(parents=True)
    directory = c.BASE / cache.DIRECTORY
    target = tmp_path / "other"
    target.mkdir()
    if kind == "symlink": directory.symlink_to(target, target_is_directory=True)
    if kind == "public": directory.mkdir(mode=0o755)
    if kind == "file": directory.write_text("keep")
    before = directory.lstat()
    cache.write("test", {"new": True})
    assert cache.read("test") == {}
    assert directory.lstat() == before and not list(target.iterdir())


def test_unwritable_cache_does_not_mask_a_result(monkeypatch):
    def denied(*args, **kwargs): raise PermissionError("read-only")
    monkeypatch.setattr(cache.os, "open", denied)
    assert cache.read("test") == {}
    cache.write("test", {"new": True})


@pytest.mark.parametrize("at", [0, -1, True, None, "today", float("nan"), float("inf"),
                              pytest.param(time.time() + 86400, id="future")])
def test_bad_or_future_times_are_not_fresh_evidence(at):
    data = {"success": {"at": at, "source": "test", "value": "2.2.0", "identity": {}},
            "attempt": {"at": at, "ok": False, "error": "failed"}}
    assert cache.observation(data, "test") is None and cache.attempt(data) is None


def test_failed_attempt_does_not_overwrite_success_evidence():
    observation = cache.evidence("2.2.0", "test", {"object": "one"})
    data = {"success": observation, "attempt": {"at": time.time(), "ok": False, "error": "TLS failure"}}
    cache.write("test", data)
    loaded = cache.read("test")
    assert cache.observation(loaded, "test", {"object": "one"}) == observation
    assert not cache.attempt(loaded)["ok"]
    assert cache.observation(loaded, "test", {"object": "two"}) is None
    assert json.loads((c.BASE / cache.DIRECTORY / cache._name("test")).read_text())["format"] == 1


@pytest.mark.parametrize("bad", [{"extra": float("nan")}, {"extra": {1, 2}}])
def test_nonserializable_cache_evidence_cannot_block_the_callers_operation(bad):
    cache.write("test", bad)
    assert cache.read("test") == {}
