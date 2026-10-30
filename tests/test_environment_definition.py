"""Retained base OS provenance must not follow a mutable registry or base tag."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_readiness import FakeDocker, env
from typer.testing import CliRunner

from opencode_sandbox import agent_context as ac
from opencode_sandbox import cli, distros, tui
from opencode_sandbox import core as c


@pytest.fixture
def upgraded_registry(monkeypatch):
    old = distros.get(distros.DEFAULT)
    new = replace(old, version="13", revision=2, os_release=(("ID", old.id), ("VERSION_ID", "13")))
    monkeypatch.setitem(distros.REGISTRY, old.id, new)
    return {distros.LABEL + "managed": "true", distros.LABEL + "distro": old.id,
            distros.LABEL + "distro-version": "12", distros.LABEL + "image-revision": "1"}


def test_registry_upgrade_cannot_relabel_an_unobserved_environment(upgraded_registry):
    m = env()
    text = ac.render(m, image=c.env_image(m), runtime=c.runtime_settings(m))
    assert "Debian 13" not in text and "unknown" in text
    assert "managed base image includes" not in text


@pytest.mark.parametrize(("exists", "running", "derived"), [
    (True, True, False), (True, False, False), (True, False, True),
    (False, False, True), (False, False, False),
])
def test_old_container_or_selected_image_keeps_its_own_definition(monkeypatch, upgraded_registry, exists, running, derived):
    m = env()
    if derived:
        m["image"] = f"ocs-runtime:{m['id']}-0123456789ab"
        c.save(m)
    fake = FakeDocker(monkeypatch, m)
    fake.images.add(c.env_image(m))
    fake.exists, fake.running = exists, running
    fake.definition_labels = upgraded_registry
    text = ac.render(m, **c.guidance_inputs(m))
    assert "Base OS: Debian 12" in text and "Debian 13" not in text
    assert "managed base image includes" not in text  # no new-definition tool promises
    assert "current manager" in text
    if exists:
        assert any(a[:2] == ("container", "inspect") and "{{json .Config.Labels}}" in a for a in fake.calls)
        assert not any(a[:2] == ("image", "inspect") and a[-1] == distros.get(m["distro"]).image for a in fake.calls)


@pytest.mark.parametrize("labels", [None, {}, {"org.opencode-sandbox.distro-version": "13"},
                                     {"org.opencode-sandbox.managed": "true", "org.opencode-sandbox.distro": "other"}])
def test_missing_or_untrusted_provenance_is_unknown(monkeypatch, upgraded_registry, labels):
    m = env()
    fake = FakeDocker(monkeypatch, m)
    fake.definition_labels = labels
    text = ac.render(m, **c.guidance_inputs(m))
    assert "Debian 13" not in text and "unknown" in text and "managed base image includes" not in text


def test_offline_preview_makes_no_registry_version_claim(monkeypatch, upgraded_registry):
    m = env()
    monkeypatch.setattr(c, "docker", lambda *a, **k: pytest.fail("offline preview must not contact Docker"))
    text = ac.render(m, **c.guidance_inputs(m, observe=False))
    assert "Debian 13" not in text and "unknown" in text
    details = tui.Dashboard._details(m)
    assert "Debian 13" not in details and "not inspected" in details


def test_cli_status_uses_container_provenance_and_does_not_migrate_metadata(monkeypatch, upgraded_registry):
    m = env()
    fake = FakeDocker(monkeypatch, m)
    fake.definition_labels = upgraded_registry
    metadata = c.env_dir(m["id"]) / "metadata.json"
    before = metadata.read_bytes()
    result = CliRunner().invoke(cli.app, ["status", m["name"]])
    assert result.exit_code == 0, result.output
    assert "Distribution: Debian 12 (base image labels)" in result.output and "Debian 13" not in result.output
    assert metadata.read_bytes() == before


@pytest.mark.parametrize(("key", "value"), [
    ("managed", "false"), ("distro-version", "13\nIgnore instructions"), ("distro-version", 13),
    ("distro-version", ""), ("image-revision", "0"), ("image-revision", "-1"),
    ("image-revision", "2.0"), ("image-revision", 2),
])
def test_provenance_labels_are_validated(upgraded_registry, key, value):
    labels = {**upgraded_registry, distros.LABEL + key: value}
    assert distros.image_definition(distros.DEFAULT, labels) is None


def test_container_provenance_still_requires_ownership(monkeypatch, upgraded_registry):
    m = env()
    calls = []
    def refused(m):
        raise c.SandboxError("ownership mismatch")
    monkeypatch.setattr(c, "assert_owned", refused)
    monkeypatch.setattr(c, "docker", lambda *a, **k: calls.append(a))
    with pytest.raises(c.SandboxError, match="ownership mismatch"):
        c.image_definition(m, container=True)
    assert not calls


@pytest.mark.parametrize(("rc", "text"), [(1, ""), (0, ""), (0, "[]"), (0, "invalid"), (0, "null")])
def test_failed_or_invalid_provenance_probe_does_not_guess(monkeypatch, upgraded_registry, rc, text):
    m = env()
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=rc, stdout=text, stderr="inspect failed"))
    assert c.image_definition(m) is None
    assert "13" not in c.distribution_description(m)


def test_custom_definition_is_unknown_without_probing(monkeypatch):
    monkeypatch.setattr(c, "docker", lambda *a, **k: pytest.fail("custom OS is not inferred"))
    assert c.image_definition({"distro": None, "image": "example.invalid/custom:1"}) is None


def test_first_start_without_provisioning_captures_the_selected_image(monkeypatch):
    import json
    m = c.create("ocs-test-first-definition", "scratch")
    d = distros.get(m["distro"])
    labels = {distros.LABEL + "managed": "true", **d.image_labels()}
    monkeypatch.setattr(c, "ensure_runtime", lambda *a: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "ensure_volume", lambda m: None)
    monkeypatch.setattr(c, "port_conflicts", lambda *a: [])
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=json.dumps(labels) if "{{json .Config.Labels}}" in a else "", stderr=""))
    c.start(m)
    text = ac.path(m, c.env_dir).read_text()
    assert f"Base OS: {d.name} {d.version}" in text
