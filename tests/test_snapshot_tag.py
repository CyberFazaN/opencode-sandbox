"""`container snapshot --tag` moved existing and manager-owned tags (docker commit
retags), e.g. a base image or another environment's runtime image."""
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import integrations as ig

EXISTING = {"opencode-sandbox:debian", "mine:taken"}


@pytest.fixture
def env(monkeypatch):
    calls = []

    def docker(*a, **k):
        calls.append(a)
        missing = a[:2] == ("image", "inspect") and a[2] not in EXISTING
        return SimpleNamespace(returncode=1 if missing else 0, stdout="", stderr="")
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c, "ensure_runtime", lambda *a, **k: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": True})
    monkeypatch.setattr(c, "require_docker_space", lambda what: None)
    m = c.create("ocs-qa-snaptag", "scratch", provisioning=ig.request([]))
    return m, calls


@pytest.mark.parametrize("tag, message", [
    ("opencode-sandbox:debian", "manager repository"),
    ("opencode-sandbox:new", "manager repository"),
    ("ocs-runtime:0123456789abcdef-1", "manager repository"),
    ("ocs-snapshot:0123456789abcdef-x", "manager repository"),  # another environment's snapshot name
    ("ocs-backup:0123456789abcdef-x", "manager repository"),
    ("mine:taken", "already exists"),
    ("no-tag", "REPOSITORY:TAG"),
    ("mine@sha256:abc", "REPOSITORY:TAG"),
    ("bad tag:1", "Invalid image tag"),
])
def test_refused_tags_commit_nothing(env, tag, message):
    m, calls = env
    with pytest.raises(c.SandboxError, match=message):
        c.snapshot(m, tag)
    assert not any(a[0] == "commit" for a in calls)


@pytest.mark.parametrize("own", [False, True])
def test_new_tags_are_committed(env, own):
    from opencode_sandbox import cleanup
    assert set(c.MANAGER_IMAGE_KINDS) == set(cleanup.OWNED_KINDS)
    m, calls = env
    tag = f"ocs-snapshot:{m['id']}-before-upgrade" if own else "ocs-test-keep:1"
    assert c.snapshot(m, tag) == tag
    assert ("commit", c.cname(m), tag) in calls
    assert c.snapshot(m).startswith(f"ocs-snapshot:{m['id']}-")  # default unchanged
