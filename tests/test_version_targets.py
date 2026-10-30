"""Exact consent/eligibility and lifecycle evidence share the existing update executor."""
from types import SimpleNamespace

import pytest
from test_opencode_lifecycle import Crash, FakeDocker, env
from typer.testing import CliRunner

from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v
from opencode_sandbox import update_cache as cache
from opencode_sandbox.cli import app


@pytest.mark.parametrize("value", ["2.01.0", "02.1.0", "2.0.0-01", "2.0.0-", "2.0.0+a..b", "2.0.0+", "v2.1.4",
                                   "opencode v2.1.4", "warning\n2.1.4", " 2.1.4 ", "2.1.4;id", None])
def test_install_targets_are_strict_data(value):
    with pytest.raises(c.SandboxError): v.resolve_target(value)


@pytest.mark.parametrize("value", ["2.1.4", "2.2.0-beta.1", "2.2.0-beta.1+build.01", "2.1.4+build"])
def test_compatible_explicit_alternatives_need_no_discovery(monkeypatch, value):
    monkeypatch.setattr(v, "latest", lambda: pytest.fail("explicit target must not query npm"))
    assert v.resolve_target(value) == value


@pytest.mark.parametrize("change", ["container", "image", "running", "network", "pin", "journal", "endpoint", "target"])
def test_confirmed_environment_plan_is_revalidated_before_mutation(monkeypatch, change):
    fake = FakeDocker(monkeypatch)
    m = env()
    plan = v.prepare_environment_update(m, "2.2.0")
    if change == "container": fake.cid = "c" * 64
    if change == "image": fake.iid = "sha256:" + "d" * 64
    if change == "running": fake.running = True
    if change == "network": m["runtime"]["network"] = "none"; c.save(m)
    if change == "pin": v.set_policy(m, "pinned", "2.1.4")
    if change == "journal": c.mark(m, "error", operation="opencode-update")
    if change == "endpoint": monkeypatch.setattr(c, "docker_endpoint", lambda: "unix:///nonexistent/other.sock")
    fake.calls.clear()
    with pytest.raises(c.SandboxError): v.update_environment(m, "2.3.0" if change == "target" else plan.target, plan=plan)
    assert not any(a[0] in ("commit", "start", "exec", "stop") for a in fake.calls)


def test_cli_confirms_exact_target_and_never_replaces_it_with_later_latest(monkeypatch):
    fake = FakeDocker(monkeypatch)
    m = env()
    seen = []
    monkeypatch.setattr(v, "latest", lambda: "2.2.0")
    from opencode_sandbox import cli
    def confirm(text, **kwargs):
        seen.append(text)
        monkeypatch.setattr(v, "latest", lambda: pytest.fail("confirmed target must not be resolved again"))
        return True
    monkeypatch.setattr(cli, "_confirm", confirm)
    result = CliRunner().invoke(app, ["opencode", "update", m["name"]])
    assert result.exit_code == 0, result.output
    assert len(seen) == 1 and "2.2.0" in seen[0] and "latest" not in seen[0]
    assert next(a for a in fake.calls if "ocs-install-opencode" in a)[-1] == "2.2.0"
    stopped = v.environment_version(c.resolve(m["id"]))
    assert stopped["version"] == "2.2.0" and stopped["verification"] == "last-verified"
    assert stopped["observation"]["identity"]["container"] == fake.cid


def test_cli_base_confirmation_receives_an_exact_target(monkeypatch):
    from opencode_sandbox import cli
    seen = []
    monkeypatch.setattr(v, "latest", lambda: "2.2.0")
    monkeypatch.setattr(cli, "_confirm", lambda text, **kwargs: seen.append(text) or True)
    monkeypatch.setattr(v, "update_base", lambda version, distro: seen.append((version, distro)))
    result = CliRunner().invoke(app, ["opencode", "update-base"])
    assert result.exit_code == 0 and "2.2.0" in seen[0] and "latest" not in seen[0]
    assert seen[1] == ("2.2.0", "debian")


@pytest.mark.parametrize("same", [False, True])
def test_update_verification_is_recorded_without_inventing_an_install(monkeypatch, same):
    fake = FakeDocker(monkeypatch, version="2.2.0" if same else "2.1.4")
    m = env()
    result = v.update_environment(m, "2.2.0")
    observed = v.environment_version(m)
    assert observed["version"] == "2.2.0" and not fake.running
    assert bool(result.get("unchanged")) == same
    assert bool(any("ocs-install-opencode" in a for a in fake.calls)) != same
    assert observed["observation"]["source"] == "container-exec"


@pytest.mark.parametrize("install", ["fail", "crash"])
def test_failure_or_interruption_cannot_retain_preupdate_success(monkeypatch, install):
    fake = FakeDocker(monkeypatch, install=install)
    m = env()
    fake.running = True
    v.environment_version(m)
    fake.running = False
    with pytest.raises(Crash if install == "crash" else c.SandboxError): v.update_environment(m, "2.2.0")
    result = v.environment_version(m)
    assert result["version"] is None
    assert cache.read(v._environment_key(m))["success"]["value"] == "2.1.4"  # old evidence exists, but cannot match


def test_image_labels_are_not_runtime_evidence_and_retagging_invalidates(monkeypatch):
    current, calls = {"id": "sha256:" + "a" * 64}, []
    def docker(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("image", "inspect"):
            return SimpleNamespace(returncode=0, stdout=current["id"] + '|{"org.opencode-sandbox.opencode-version":"2.0.0"}', stderr="")
        return SimpleNamespace(returncode=0, stdout="opencode v2.2.0", stderr="")
    monkeypatch.setattr(c, "docker", docker)
    result = v.image_observation("opencode-sandbox:debian")
    assert result["build_version"] == "2.0.0" and result["observation"] is None
    assert not any(a[0] == "run" for a in calls)
    assert v.image_version("opencode-sandbox:debian") == "2.2.0"
    assert current["id"] in next(a for a in calls if a[0] == "run")
    result = v.image_observation("opencode-sandbox:debian")
    assert result["observation"]["source"] == "image-exec"
    current["id"] = "sha256:" + "b" * 64
    assert v.image_observation("opencode-sandbox:debian")["observation"] is None
    current["id"] = "sha256:" + "a" * 64
    assert v.image_observation("opencode-sandbox:debian")["observation"]["value"] == "2.2.0"
