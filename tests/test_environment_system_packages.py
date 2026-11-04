"""Opt-in system package upgrade inside an existing environment's checkpointed OpenCode update
(mocked Docker; real runs in tests/integration/test_53_environment_updates.py)."""
import pytest
from test_opencode_lifecycle import FakeDocker, env, runner

from opencode_sandbox import core as c
from opencode_sandbox import distros
from opencode_sandbox import opencode_versions as v
from opencode_sandbox.cli import app


def upgrades(fake, monkeypatch, outcome="ok"):
    """Record package-upgrade execs; `fail` exits non-zero, `break` leaves OpenCode unrunnable."""
    real, seen = c.docker, []
    scripts = {d.system_upgrade: d.id for d in distros.REGISTRY.values()}

    def docker(*args, capture=False, check=True):
        if args[0] == "exec" and args[2:4] == ("sh", "-c") and args[4] in scripts:
            fake.calls.append(args)
            seen.append(scripts[args[4]])
            if outcome == "fail": raise c.SandboxError("Command failed (100): E: Unable to fetch some archives")
            if outcome == "break": fake.version = "broken"
            return fake.ok()
        if outcome == "break" and fake.version == "broken" and args[0] == "exec" and args[-2:] == ("opencode", "--version"):
            fake.calls.append(args)
            raise c.SandboxError("Command failed (127): opencode: not found")
        return real(*args, capture=capture, check=check)
    monkeypatch.setattr(c, "docker", docker)
    return seen


def kinds(fake):
    return ["upgrade" if a[0] == "exec" and a[4:5] and a[4] in {d.system_upgrade for d in distros.REGISTRY.values()}
            else "install" if a[0] == "exec" and "ocs-install-opencode" in a else a[0] for a in fake.calls]


@pytest.mark.parametrize("distro", list(distros.REGISTRY))
def test_requested_upgrade_runs_first_inside_the_checkpoint_with_the_distribution_tool(monkeypatch, distro):
    fake = FakeDocker(monkeypatch)
    seen = upgrades(fake, monkeypatch)
    m = env(distro=distro)
    plan = v.prepare_environment_update(m, "2.2.0", system_packages=True)
    assert plan.system_packages
    result = v.update_environment(m, "2.2.0", plan=plan)
    assert seen == [distro] and result["system_packages"] and result["previous_version"] == "2.1.4"
    ops = kinds(fake)
    assert ops.index("commit") < ops.index("start") < ops.index("upgrade") < ops.index("install") < len(ops) - 1
    assert ops[-1] == "stop" and not fake.running
    record = c.resolve(m["id"])["opencode_update"]
    assert record["state"] == "done" and record["system_packages"] and record["result"] == "system packages upgraded; updated 2.1.4 -> 2.2.0"
    manager = {"pacman": "pacman -Su", "apt": "apt-get"}[distros.get(distro).package_manager]
    assert manager in distros.get(distro).system_upgrade


def test_unchecked_update_never_upgrades_packages(monkeypatch):
    fake = FakeDocker(monkeypatch)
    seen = upgrades(fake, monkeypatch)
    m = env()
    plan = v.prepare_environment_update(m, "2.2.0")
    result = v.update_environment(m, "2.2.0", plan=plan)
    assert not plan.system_packages and seen == [] and "system_packages" not in result
    assert "system_packages" not in c.resolve(m["id"])["opencode_update"]
    assert v.system_upgrade_lines(m, False) == ["System packages: not upgraded; only OpenCode is updated."]


def test_confirmed_plan_decides_even_if_the_caller_differs(monkeypatch):
    fake = FakeDocker(monkeypatch)
    seen = upgrades(fake, monkeypatch)
    m = env()
    v.update_environment(m, "2.2.0", plan=v.prepare_environment_update(m, "2.2.0"), system_packages=True)
    assert seen == []


def test_failed_package_upgrade_never_updates_opencode_and_restores_the_checkpoint(monkeypatch):
    fake = FakeDocker(monkeypatch)
    upgrades(fake, monkeypatch, "fail")
    m = env()
    with pytest.raises(c.SandboxError) as err:
        v.update_environment(m, "2.2.0", system_packages=True)
    message = str(err.value)
    assert message.startswith("System package upgrade failed: Command failed (100)") and "OpenCode was not updated" in message
    assert "not part of the checkpoint" in message and "untouched" not in message
    assert "install" not in kinds(fake) and fake.version == "2.1.4"
    m = c.resolve(m["id"])
    record = m["opencode_update"]
    assert record["state"] == "rolled-back" and record["result"].startswith("system package upgrade failed (")
    assert "OpenCode not updated" in record["result"] and m["image"] == record["checkpoint"] and m["operation"] is None


def test_same_version_upgrade_keeps_its_checkpoint_as_the_rollback_point(monkeypatch):
    fake = FakeDocker(monkeypatch, version="2.2.0")
    upgrades(fake, monkeypatch)
    m = env()
    result = v.update_environment(m, "2.2.0", system_packages=True)
    assert "unchanged" not in result and result["checkpoint"] in fake.images and "install" not in kinds(fake)
    assert c.resolve(m["id"])["opencode_update"]["result"] == "system packages upgraded; OpenCode 2.2.0 unchanged"
    rolled = v.rollback_environment(c.resolve(m["id"]))
    assert rolled["image"] == result["checkpoint"]
    assert "checkpointed pre-upgrade system packages restored (changes outside the system layer remain)" \
        in c.resolve(m["id"])["opencode_update"]["result"]


def test_upgrade_that_breaks_the_binary_reinstalls_the_confirmed_target(monkeypatch):
    fake = FakeDocker(monkeypatch, version="2.2.0")
    upgrades(fake, monkeypatch, "break")
    m = env()
    result = v.update_environment(m, "2.2.0", system_packages=True)
    assert result["version"] == "2.2.0" and fake.version == "2.2.0" and kinds(fake).count("install") == 1


def test_custom_image_refuses_a_package_upgrade_before_any_change(monkeypatch):
    fake = FakeDocker(monkeypatch)
    m = c.create("ocs-qa-custom-pkg", "scratch", image="example.org/custom:1")
    with pytest.raises(c.SandboxError, match="package manager is unknown"):
        v.prepare_environment_update(m, "2.2.0", system_packages=True)
    with pytest.raises(c.SandboxError, match="package manager is unknown"):
        v.update_environment(m, "2.2.0", system_packages=True)
    assert not any(a[0] in ("commit", "start", "exec") for a in fake.calls)
    assert v.prepare_environment_update(m, "2.2.0").system_packages is False


def test_disclosure_never_claims_full_reversibility():
    m = c.create("ocs-qa-disclose", "scratch", distro="arch")
    text = "\n".join(v.system_upgrade_lines(m, True))
    assert "not fully reversible" in text and "OpenCode is not updated" in text
    assert distros.get("arch").system_upgrade_summary in text and "paru" in text


def test_cli_flag_reaches_the_confirmed_plan_and_reports_the_upgrade(monkeypatch):
    fake = FakeDocker(monkeypatch)
    seen = upgrades(fake, monkeypatch)
    m = env()
    from opencode_sandbox import cli
    asked = []
    monkeypatch.setattr(cli, "_confirm", lambda text, **kwargs: asked.append(text) or True)
    result = runner.invoke(app, ["opencode", "update", m["name"], "--version", "2.2.0", "--update-system-packages"])
    assert result.exit_code == 0, result.output
    assert "not fully reversible" in result.output and "upgrade its system packages" in asked[0]
    assert "System packages upgraded; Updated OpenCode 2.1.4 -> 2.2.0" in result.output and seen == ["debian"]
    result = runner.invoke(app, ["opencode", "rollback", m["name"]])
    assert result.exit_code == 0, result.output
    assert "changes outside the system layer" in asked[1]
