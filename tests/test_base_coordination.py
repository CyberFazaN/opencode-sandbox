"""Base lock participants and mutation revalidation; real locks, mocked Docker."""
import contextvars
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
import test_cleanup
from test_opencode_versions import NEW, OLD, fake_docker

from opencode_sandbox import cleanup as cl
from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v

world = test_cleanup.world  # reuse the isolated fake-daemon fixture


@pytest.mark.parametrize("phase", ["build", "publication"])
@pytest.mark.parametrize("kind", ["base rollback copy", "base build candidate", "untagged base image"])
def test_cleanup_uses_shared_guards_across_data_directories(world, monkeypatch, tmp_path, phase, kind):
    item = next(i for i in cl.inventory().eligible(True) if i.kind == kind)
    with c.base_lock("debian", phase):
        monkeypatch.setattr(c, "BASE", tmp_path / "other-data")
        result = contextvars.Context().run(cl.apply, [item.key], superseded=True)
        assert result[0][1].startswith("busy")
    assert cl.apply([item.key], superseded=True)[0][1] is None


@pytest.mark.parametrize("kind", ["base rollback copy", "base build candidate", "untagged base image"])
@pytest.mark.parametrize("change", ["identity", "ownership", "references", "inspect-error"])
def test_cleanup_rechecks_base_identity_ownership_and_references_under_guards(world, monkeypatch, kind, change):
    item = next(i for i in cl.inventory().eligible(True) if i.kind == kind)
    if change == "identity":
        item.image_id = "sha256:" + "f" * 64  # stale inventory identity
    elif change == "ownership":
        world.d.images[item.image_id]["Config"]["Labels"].pop(cl.MANAGED)
    elif change == "references":
        m = c.resolve(world.live["id"])
        m["image"] = item.ref
        c.save(m)
    else:
        real = c.docker
        def docker(*args, **kwargs):
            if args[:2] == ("image", "inspect"):
                return SimpleNamespace(returncode=1, stdout="", stderr="daemon unavailable")
            return real(*args, **kwargs)
        monkeypatch.setattr(c, "docker", docker)
    before = len(world.d.calls)
    assert cl._remove(item).startswith("skipped:")
    assert not any(a[:2] == ("image", "rm") for a in world.d.calls[before:])


def test_retagged_untagged_base_is_not_removed(world):
    item = next(i for i in cl.inventory().eligible(True) if i.kind == "untagged base image")
    world.d.images[item.image_id]["tags"].add("opencode-sandbox:debian")
    assert "no longer untagged" in cl._remove(item)


@pytest.mark.parametrize("suffix", ["candidate-0123456789ab", "previous-abcdef012345"])
def test_base_names_without_ownership_are_never_cleanup_authority(world, suffix):
    ref = "opencode-sandbox:debian-" + suffix
    world.d.images[world.d.tag_of(ref)]["Config"]["Labels"] = {}
    item = next(i for i in cl.inventory().items if i.ref == ref)
    assert item.status == cl.NOT_MANAGED and item.scope is None


def test_cleanup_explains_unsafe_lock_namespace_instead_of_calling_it_busy(world, monkeypatch, tmp_path):
    from opencode_sandbox import base_locks
    item = next(i for i in cl.inventory().eligible() if i.base_distro)
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir(mode=0o777)
    unsafe.chmod(0o777)
    monkeypatch.setattr(base_locks, "_TMP", unsafe)
    assert "Unsafe base lock parent" in cl._remove(item)


@pytest.mark.parametrize("keep", [False, True])
def test_update_participant_order_and_short_publication_guard(monkeypatch, keep):
    held, calls = [], []
    real_lock = c.base_lock
    @contextmanager
    def lock(distro, phase, *, timeout=30):
        with real_lock(distro, phase, timeout=timeout):
            held.append(phase)
            try: yield
            finally: held.pop()
    real_docker = fake_docker(calls)
    def docker(*args, **kwargs):
        if args[0] in ("build", "run"):
            assert held == ["build"]  # candidate build/verification do not exclude creation
        elif args[0] == "tag" or args[:2] in (("image", "rm"), ("image", "inspect")):
            assert held == ["build", "publication"]
        return real_docker(*args, **kwargs)
    monkeypatch.setattr(c, "base_lock", lock)
    monkeypatch.setattr(c, "ensure_runtime", lambda: None)
    monkeypatch.setattr(c, "require_docker_space", lambda _: None)
    monkeypatch.setattr(c, "docker", docker)
    v.update_base("2.1.4", keep_previous=keep)
    assert not held


@pytest.mark.parametrize("change", ["replaced", "removed", "unmanaged", "inspect-error"])
def test_update_refuses_changed_or_uninspectable_current_base(monkeypatch, change):
    calls, state = [], {"built": False}
    real = fake_docker(calls)
    def docker(*args, **kwargs):
        if args[0] == "build":
            state["built"] = True
        if args == ("image", "inspect", "opencode-sandbox:debian") and state["built"]:
            if change in ("removed", "inspect-error"):
                return SimpleNamespace(returncode=1, stdout="", stderr="No such image: base" if change == "removed" else "daemon failed")
            data = json.loads(real(*args, **kwargs).stdout)
            if change == "replaced":
                data[0]["Id"] = NEW
            else:
                data[0]["Config"]["Labels"] = {}
            return SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr="")
        return real(*args, **kwargs)
    monkeypatch.setattr(c, "ensure_runtime", lambda: None)
    monkeypatch.setattr(c, "require_docker_space", lambda _: None)
    monkeypatch.setattr(c, "docker", docker)
    with pytest.raises(c.SandboxError, match="changed|unmanaged|Cannot inspect"):
        v.update_base("2.1.4")
    assert not any(a[0] == "tag" for a in calls)
    assert all("candidate" in a[-1] for a in calls if a[:2] == ("image", "rm"))


@pytest.mark.parametrize("response", ["invalid-json", "invalid-id", "unmanaged", "other-distro", "other-data", "inspect-error"])
def test_unproven_base_is_not_replaced_or_built(monkeypatch, response):
    calls = []
    data = [{"Id": OLD, "Config": {"Labels": {**c.distros.get("debian").image_labels(), cl.MANAGED: "true"}}}]
    if response == "invalid-id": data[0]["Id"] = ""
    if response == "unmanaged": data[0]["Config"]["Labels"] = {}
    if response == "other-distro": data[0]["Config"]["Labels"]["org.opencode-sandbox.distro"] = "arch"
    if response == "other-data": data[0]["Config"]["Labels"][c.DATA_LABEL] = "other"
    def docker(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=int(response == "inspect-error"),
            stdout="bad" if response == "invalid-json" else json.dumps(data), stderr="daemon failed")
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c, "ensure_runtime", lambda: None)
    monkeypatch.setattr(c, "require_docker_space", lambda _: None)
    with pytest.raises(c.SandboxError, match="Invalid|Refusing|Cannot inspect"):
        v.update_base("2.1.4")
    assert [a[0] for a in calls] == ["image"]


def test_known_missing_base_allows_first_build(monkeypatch):
    calls, state = [], {"published": False}
    real = fake_docker(calls)
    def docker(*args, **kwargs):
        if args == ("image", "inspect", "opencode-sandbox:debian") and not state["published"]:
            return SimpleNamespace(returncode=1, stdout="[]", stderr="Error response from daemon: No such image: opencode-sandbox:debian")
        if args[0] == "tag": state["published"] = True
        return real(*args, **kwargs)
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c, "ensure_runtime", lambda: None)
    monkeypatch.setattr(c, "require_docker_space", lambda _: None)
    result = v.update_base("2.1.4")
    assert result["previous_image"] is None and state["published"]


@pytest.mark.parametrize("collision", ["candidate", "previous"])
def test_colliding_image_tags_are_not_overwritten_or_removed(monkeypatch, collision):
    import secrets
    calls = []
    real = fake_docker(calls)
    def docker(*args, **kwargs):
        if args[:2] == ("image", "inspect") and f"-{collision}-" in args[-1]:
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"Id": OLD, "Config": {"Labels": {
                **c.distros.get("debian").image_labels(), cl.MANAGED: "true"}}}]), stderr="")
        return real(*args, **kwargs)
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c, "ensure_runtime", lambda: None)
    monkeypatch.setattr(c, "require_docker_space", lambda _: None)
    monkeypatch.setattr(secrets, "token_hex", lambda _: "0" * 12)
    with pytest.raises(c.SandboxError, match="already exists"):
        v.update_base("2.1.4")
    assert not any(a[0] == "tag" for a in calls)
    assert not any(a[:2] == ("image", "rm") and f"-{collision}-" in a[-1] for a in calls)


def test_rollback_rechecks_copy_and_base_after_verification(monkeypatch):
    ref = "opencode-sandbox:debian-previous-" + "0" * 12
    calls, state = [], {"verified": False}
    real = fake_docker(calls, previous_tags=(ref,))
    def docker(*args, **kwargs):
        if args[:2] == ("image", "ls"):
            return SimpleNamespace(returncode=0, stdout=ref, stderr="")
        if "--format" in args:
            return SimpleNamespace(returncode=0, stdout="2.1.4", stderr="")
        result = real(*args, **kwargs)
        if state["verified"] and args == ("image", "inspect", ref):
            data = json.loads(result.stdout)
            data[0]["Id"] = NEW
            result.stdout = json.dumps(data)
        return result
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c, "ensure_runtime", lambda: None)
    monkeypatch.setattr(c, "verify_image", lambda *args: state.update(verified=True))
    with pytest.raises(c.SandboxError, match="changed during verification"):
        v.rollback_base()
    assert not any(a[0] == "tag" or a[:2] == ("image", "rm") for a in calls)
