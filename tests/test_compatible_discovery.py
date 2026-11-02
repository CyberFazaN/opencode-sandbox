"""Bounded real loopback HTTP, stable selection, failed-attempt retention and no implicit install."""
import json
import time
from email.utils import formatdate

import pytest
import test_opencode_versions

from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v
from opencode_sandbox import update_cache as cache

registry = test_opencode_versions.registry  # same function-scoped real HTTP fixture


def metadata(*versions, **extra):
    return json.dumps({"name": v.PACKAGE, "dist-tags": {"latest": "3.0.0"},
                       "versions": {version: {"version": version} for version in versions}, **extra}).encode()


@pytest.mark.parametrize("versions,expected", [
    (("2.9.0", "2.10.0", "3.0.0"), "2.10.0"),
    (("2.1.4", "2.2.0-beta.1", "3.0.0"), "2.1.4"),
    (("2.2.0", "2.2.0-beta.9", "2.1.4"), "2.2.0"),
    (("2.2.0+build.1", "2.1.4"), "2.2.0+build.1"),
    (("2.1.4", "2.01.5", "v2.3.0", "2.4.0-01", "2.1.5;id"), "2.1.4"),
])
def test_supported_stable_selection_uses_semver_not_dist_tag(registry, versions, expected):
    registry["body"] = metadata(*versions)
    assert v.latest() == expected
    assert len(registry["requests"]) == 1
    assert registry["requests"][0][1] == "application/vnd.npm.install-v1+json"
    data = v.discovery()
    assert data["success"]["value"] == expected and data["attempt"]["ok"]
    assert data["success"]["identity"] == {"url": v.REGISTRY, "major": v.MAJOR}


@pytest.mark.parametrize("body", [metadata("3.0.0", "2.1.0-beta"), metadata(), b'{"versions":[]}', b'[]',
                                  b'{"versions":{"2.2.0":{"version":"2.2.1"}}}',
                                  b'{"versions":{"2.2.0":{}}}'])
def test_missing_or_invalid_compatible_release_is_an_explicit_error(registry, body):
    registry["body"] = body
    with pytest.raises(c.SandboxError, match="Cannot check"):
        v.latest()
    assert v.discovery()["success"] is None and not v.discovery()["attempt"]["ok"]


def test_metadata_larger_than_old_limit_and_bounded_new_limit(registry, monkeypatch):
    registry["body"] = metadata("2.2.0", padding="x" * 70000)
    assert v.latest() == "2.2.0"
    monkeypatch.setattr(v, "METADATA_LIMIT", 65536)
    with pytest.raises(c.SandboxError, match="response too large"):
        v.latest()
    assert v.discovery()["success"]["value"] == "2.2.0" and not v.discovery()["attempt"]["ok"]


@pytest.mark.parametrize("failure", ["http", "json", "timeout", "shape"])
def test_failure_retains_dated_success_but_cannot_resolve_latest_for_install(registry, failure):
    registry["body"] = metadata("2.2.0")
    v.latest()
    good = v.discovery()["success"]
    if failure == "http": registry["status"] = 500
    if failure == "json": registry["body"] = b"not json"
    if failure == "timeout": registry["delay"] = 1.5
    if failure == "shape": registry["body"] = b'{"version":"2.2.1"}'
    with pytest.raises(c.SandboxError): v.latest(timeout=.3 if failure == "timeout" else 8)
    data = v.discovery()
    assert data["success"] == good and not data["attempt"]["ok"]
    assert data["attempt"]["at"] >= good["at"]
    if failure != "timeout":
        with pytest.raises(c.SandboxError): v.resolve_target("latest")
        lines, errors = v.versions_report(check=True)
        assert "cached; last checked" in lines[0] and errors


@pytest.mark.parametrize("retry", ["120", "date", "long"])
def test_rate_limit_survives_fresh_callers_and_manual_check_respects_it(registry, retry):
    registry["body"] = metadata("2.1.4")
    v.latest()
    header = formatdate(time.time() + 120, usegmt=True) if retry == "date" else str(8 * 86400 if retry == "long" else 120)
    registry.update(status=429, headers={"Retry-After": header})
    with pytest.raises(c.SandboxError, match="HTTP 429.*retry after"): v.latest()
    assert v.discovery()["success"]["value"] == "2.1.4"
    count = len(registry["requests"])
    for _ in range(2):
        with pytest.raises(c.SandboxError, match="rate limited"): v.latest()
    assert len(registry["requests"]) == count
    key = v._registry_key()
    data = cache.read(key)
    data["attempt"]["retry_until"] = time.time() - 1
    cache.write(key, data)
    registry.update(status=200, headers={})
    assert v.latest() == "2.1.4"


def test_cancellation_leaves_an_attempt_not_a_new_success(registry, monkeypatch):
    from opencode_sandbox import runtime_identity
    registry["body"] = metadata("2.1.4")
    v.latest()
    good = v.discovery()["success"]
    def cancelled(*a, **k): raise runtime_identity.Cancelled()
    monkeypatch.setattr(c, "call", cancelled)
    with pytest.raises(runtime_identity.Cancelled): v.latest()
    assert v.discovery()["success"] == good
    assert not v.discovery()["attempt"]["ok"]


def test_cached_only_read_and_report_never_queries_network(registry, monkeypatch):
    registry["body"] = metadata("2.1.4")
    v.latest()
    monkeypatch.setattr(c, "call", lambda *a, **k: pytest.fail("cached read must not query network/Docker"))
    lines, errors = v.versions_report()
    assert "cached; last checked" in lines[0] and not errors


@pytest.mark.parametrize("field,value", [pytest.param("at", time.time() + 86400, id="future"), ("value", "3.0.0"), ("value", "2.1.4-beta.1"),
                                         ("identity", {"url": "foreign", "major": 2}), ("source", "build-label")])
def test_corrupt_remote_success_cannot_look_current(registry, field, value):
    registry["body"] = metadata("2.1.4")
    v.latest()
    data = cache.read(v._registry_key())
    data["success"][field] = value
    cache.write(v._registry_key(), data)
    assert v.discovery()["success"] is None


def test_expired_success_is_retained_but_explicitly_stale(registry):
    registry["body"] = metadata("2.1.4")
    v.latest()
    assert not v.discovery()["stale"]
    data = cache.read(v._registry_key())
    data["success"]["at"] -= 2 * 86400
    cache.write(v._registry_key(), data)
    assert v.discovery()["success"]["value"] == "2.1.4" and v.discovery()["stale"]
