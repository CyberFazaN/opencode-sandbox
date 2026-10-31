"""Daily discovery uses real private files/locks; HTTP and process tests use loopback only."""
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from email.utils import formatdate
from pathlib import Path

import pytest
import test_opencode_versions

from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v
from opencode_sandbox import runtime_identity as rid
from opencode_sandbox import update_cache as cache

registry = test_opencode_versions.registry


@pytest.mark.parametrize("failed", [False, True])
def test_automatic_attempt_is_daily_including_failure(registry, failed):
    registry.update(body=json.dumps({"versions": {"2.2.0": {"version": "2.2.0"}}}).encode(), status=503 if failed else 200)
    for _ in range(3):
        if failed:
            with pytest.raises(c.SandboxError, match="HTTP 503"): v.latest(automatic=True)
        else:
            assert v.latest(automatic=True) == "2.2.0"
    assert len(registry["requests"]) == 1


def prepare(registry):
    registry["body"] = b'{"versions":{"2.2.0":{"version":"2.2.0"}}}'


def child(*, automatic=True):
    code = ("from opencode_sandbox import core as c, opencode_versions as v\n"
            f"from pathlib import Path\nc.BASE=Path({str(c.BASE)!r})\nv.REGISTRY={v.REGISTRY!r}\n"
            f"print(v.latest(automatic={automatic!r}), flush=True)\n")
    return subprocess.Popen([sys.executable, "-B", "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src")))


def wait_for(predicate):
    deadline = time.monotonic() + 4
    while not predicate() and time.monotonic() < deadline: time.sleep(.01)
    assert predicate()


def test_attempt_is_persisted_before_http_and_survives_process_restart(registry):
    prepare(registry)
    registry["delay"] = .3
    p = child()
    try:
        wait_for(lambda: len(registry["requests"]) == 1)
        claim = cache.read(v._registry_key())["attempt"]
        assert claim["id"] and not claim["ok"] and claim["error"] == "check did not complete"
        assert p.communicate(timeout=4)[0].strip() == "2.2.0" and p.returncode == 0
        p = child()
        assert p.communicate(timeout=4)[0].strip() == "2.2.0" and p.returncode == 0
        assert len(registry["requests"]) == 1
    finally:
        if p.poll() is None: p.kill()
        p.communicate(timeout=4)


def test_interruption_after_claim_before_http_cannot_retry_on_restart(registry, tmp_path):
    prepare(registry)
    marker = tmp_path / "claimed"
    code = ("import time\nfrom pathlib import Path\nfrom opencode_sandbox import core as c, opencode_versions as v\n"
            f"c.BASE=Path({str(c.BASE)!r})\nv.REGISTRY={v.REGISTRY!r}\n"
            f"def pause(*a, **k):\n Path({str(marker)!r}).write_text('claimed')\n time.sleep(30)\n"
            "c.call=pause\nv.latest(automatic=True)\n")
    p = subprocess.Popen([sys.executable, "-B", "-c", code])
    try:
        wait_for(marker.exists)
        p.kill(); p.wait(timeout=4)
        with pytest.raises(c.SandboxError, match="check did not complete"): v.latest(automatic=True)
        restarted = child()
        try:
            _out, err = restarted.communicate(timeout=4)
            assert restarted.returncode != 0 and "check did not complete" in err
        finally:
            if restarted.poll() is None: restarted.kill()
            restarted.communicate(timeout=4)
        assert registry["requests"] == []
        assert v.latest() == "2.2.0"  # explicit retry, not a cached-success install authorization
    finally:
        if p.poll() is None: p.kill()
        p.wait(timeout=4)


@pytest.mark.parametrize("automatic", [False, True])
def test_threads_coalesce_manual_and_background_success_and_failure(registry, automatic):
    prepare(registry)
    registry["delay"] = .25
    with ThreadPoolExecutor(max_workers=3) as pool:
        owner = pool.submit(v.latest, automatic=automatic)
        wait_for(lambda: len(registry["requests"]) == 1)
        waiters = [pool.submit(v.latest, automatic=flag) for flag in (False, True)]
        assert owner.result() == "2.2.0"
        assert [w.result() for w in waiters] == ["2.2.0", "2.2.0"]
    assert len(registry["requests"]) == 1
    registry["status"] = 500
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(v.latest)
        wait_for(lambda: len(registry["requests"]) == 2)
        waiter = pool.submit(v.latest)
        for future in (owner, waiter):
            with pytest.raises(c.SandboxError, match="HTTP 500"): future.result()
    assert len(registry["requests"]) == 2 and v.discovery()["success"]["value"] == "2.2.0"


def test_processes_coalesce_with_manual_owner(registry):
    prepare(registry)
    registry["delay"] = .5
    processes = [child(automatic=False)]
    try:
        wait_for(lambda: len(registry["requests"]) == 1)
        processes.extend([child(automatic=False), child()])
        for p in processes:
            out, err = p.communicate(timeout=4)
            assert p.returncode == 0, err
            assert out.strip() == "2.2.0"
        assert len(registry["requests"]) == 1
    finally:
        for p in processes:
            if p.poll() is None: p.kill()
            p.communicate(timeout=4)


@pytest.mark.parametrize("elapsed,requests", [(86399, 1), (86401, 2), (-86400, 1)])
def test_clock_changes_do_not_discard_attempt_throttle(registry, elapsed, requests):
    prepare(registry)
    v.latest()
    data = cache.read(v._registry_key())
    data["attempt"]["at"] = time.time() - elapsed
    cache.write(v._registry_key(), data)
    v.latest(automatic=True)
    assert len(registry["requests"]) == requests


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("header", ["numeric", "date", "long"])
def test_retry_after_blocks_background_and_explicit_across_restart(registry, status, header):
    prepare(registry)
    retry = formatdate(time.time() + 10 * 86400, usegmt=True) if header == "date" else str(10 * 86400 if header == "long" else 120)
    registry.update(status=status, headers={"Retry-After": retry})
    with pytest.raises(c.SandboxError, match=f"HTTP {status}"): v.latest()
    for automatic in (False, True):
        with pytest.raises(c.SandboxError, match="rate limited"): v.latest(automatic=automatic)
    p = child(automatic=False)
    try:
        _out, err = p.communicate(timeout=4)
        assert p.returncode != 0 and "rate limited" in err
        assert len(registry["requests"]) == 1
    finally:
        if p.poll() is None: p.kill()
        p.communicate(timeout=4)


@pytest.mark.parametrize("kind", ["directory", "lock", "file", "write"])
def test_unsafe_or_unwritable_storage_disables_automatic_not_explicit(registry, tmp_path, monkeypatch, kind):
    prepare(registry)
    cache.write(v._registry_key(), {})
    directory = c.BASE / cache.DIRECTORY
    if kind == "directory": directory.chmod(0o755)
    if kind == "lock": (directory / (cache._name(v._registry_key()) + ".lock")).symlink_to(tmp_path / "untouched")
    if kind == "file": (directory / cache._name(v._registry_key())).chmod(0o644)
    if kind == "write": monkeypatch.setattr(cache, "write", lambda *a, **k: False)
    with pytest.raises(c.SandboxError, match="Automatic discovery unavailable"): v.latest(automatic=True)
    assert not registry["requests"]
    assert v.latest() == "2.2.0"
    assert len(registry["requests"]) == 1


def test_canceled_waiter_cannot_cancel_owner_or_issue_another_request(registry):
    prepare(registry)
    registry["delay"] = .3
    canceled = threading.Event()
    def waiter():
        with c.runtime_feedback(cancelled=canceled.is_set): return v.latest()
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(v.latest)
        wait_for(lambda: len(registry["requests"]) == 1)
        pending = pool.submit(waiter)
        canceled.set()
        with pytest.raises(rid.Cancelled): pending.result()
        assert owner.result() == "2.2.0"
    assert len(registry["requests"]) == 1


def test_lock_wait_is_bounded_and_no_follow_files_are_not_repaired(registry, tmp_path):
    prepare(registry)
    with cache.source_lock(v._registry_key()), pytest.raises(c.SandboxError, match="source busy"), \
            cache.source_lock(v._registry_key(), timeout=.03):
        pytest.fail("must exclude same-process threads too")
    path = c.BASE / cache.DIRECTORY / (cache._name(v._registry_key()) + ".lock")
    path.unlink()  # this test owns it; product code never removes persistent lock files
    target = tmp_path / "retain-lock"
    target.write_text("untouched")
    os.link(target, path)
    before = path.stat()
    with pytest.raises(cache.Unavailable), cache.source_lock(v._registry_key()):
        pytest.fail("hardlinked lock must be refused")
    assert path.stat() == before and target.read_text() == "untouched"


def test_canceled_owner_leaves_a_daily_failed_claim_and_waiter_does_not_retry(registry, monkeypatch):
    prepare(registry)
    started, release = threading.Event(), threading.Event()
    def canceled(*a, **k):
        started.set()
        assert release.wait(3)
        raise rid.Cancelled()
    monkeypatch.setattr(c, "call", canceled)
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(v.latest)
        assert started.wait(1)
        waiter = pool.submit(v.latest, automatic=True)
        release.set()
        with pytest.raises(rid.Cancelled): owner.result()
        with pytest.raises(c.SandboxError, match="check did not complete"): waiter.result()
    with pytest.raises(c.SandboxError, match="check did not complete"): v.latest(automatic=True)
    assert not registry["requests"] and not v.discovery()["attempt"]["ok"]


def test_manual_may_refresh_early_and_resolved_target_holds_no_discovery_guard(registry):
    prepare(registry)
    assert v.latest(automatic=True) == "2.2.0"
    assert v.resolve_target("latest") == "2.2.0"
    assert len(registry["requests"]) == 2
    with cache.source_lock(v._registry_key(), timeout=.01): pass


def test_failed_claim_fsync_never_launches_automatic_http(registry, monkeypatch):
    prepare(registry)
    def fail_sync(fd): raise OSError("test disk failure")
    monkeypatch.setattr(cache.os, "fsync", fail_sync)
    with pytest.raises(c.SandboxError, match="cannot persist attempt claim"): v.latest(automatic=True)
    assert not registry["requests"]
    assert not list((c.BASE / cache.DIRECTORY).glob(".write-*"))


def test_cached_only_lock_contention_is_not_an_inflight_network_attempt(registry, monkeypatch):
    prepare(registry)
    v.latest()
    data = cache.read(v._registry_key())
    data["success"]["at"] -= 2 * 86400
    cache.write(v._registry_key(), data)
    blocked = threading.Event()
    flock = cache.fcntl.flock
    def observe(fd, operation):
        try: return flock(fd, operation)
        except BlockingIOError:
            blocked.set()
            raise
    monkeypatch.setattr(cache.fcntl, "flock", observe)
    with ThreadPoolExecutor(max_workers=1) as pool:
        # Represents a background consideration reading the daily gate, not a new HTTP owner.
        with cache.source_lock(v._registry_key()):
            pending = pool.submit(v.latest)
            assert blocked.wait(2)
        assert pending.result() == "2.2.0"
    assert len(registry["requests"]) == 2  # explicit fresh Check, never the old cached success
    assert v.discovery()["success"]["at"] > data["success"]["at"]
