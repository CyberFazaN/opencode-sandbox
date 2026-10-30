"""Agent Context rendering: shared sections, inspected base provenance, observed runtime.

Golden files: tests/golden/agent-context-*.md. After an intended wording change, regenerate with
OCS_UPDATE_GOLDEN=1 pytest tests/test_agent_context.py and review the diff.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from opencode_sandbox import agent_context as a
from opencode_sandbox import core as c
from opencode_sandbox import distros

GOLDEN = Path(__file__).parent / "golden"
M = {'id': '0123456789abcdef', 'name': 'demo', 'kind': 'scratch', 'source': None, 'distro': 'debian'}
R = {'network': 'none', 'cpus': '2.0', 'memory': '4g', 'pids': 100, 'ports': []}
PORT = {'host': 18080, 'container': 8080, 'protocol': 'tcp'}

CASES = {
    # Debian project imported from a host directory, bridge network with a published port.
    "debian": ({**M, 'kind': 'project', 'source': '/home/someone/private/project'}, 'opencode-sandbox:debian',
               {**R, 'network': 'bridge', 'ports': [PORT]}),
    # Arch scratch environment without network.
    "arch": ({**M, 'distro': 'arch'}, 'opencode-sandbox:arch', R),
    # Custom image, quick session.
    "custom": ({**M, 'kind': 'quick', 'distro': None}, 'example.org/team/tools:1', {**R, 'network': 'bridge'}),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_golden(case):
    m, image, runtime = CASES[case]
    d = distros.get(m["distro"]) if m.get("distro") else None
    definition = distros.ImageDefinition(d.id, d.version, d.revision) if d else None
    text = a.render(m, image=image, runtime=runtime, definition=definition)
    golden = GOLDEN / f"agent-context-{case}.md"
    if os.environ.get("OCS_UPDATE_GOLDEN") == "1":
        golden.write_text(text, encoding="utf-8")
    assert text == golden.read_text(encoding="utf-8")


@pytest.mark.parametrize("case", sorted(CASES))
def test_shared_sections_and_no_secrets_or_host_paths(case):
    m, image, runtime = CASES[case]
    text = a.render(m, image=image, runtime=runtime)
    for heading in ("## Container, user and privileges", "## Workspace and persistence", "## Network and resources",
                    "## Operating system", "## Working behavior"):
        assert text.count(heading) == 1
    assert "no-new-privileges" in text and "no Docker socket" in text and "Networking mode: " + runtime["network"] in text
    assert "/home/" not in text and "API_KEY" not in text and "ocs-provider.json" not in text
    assert "## Initial integrations" not in text  # nothing provisioned


@pytest.mark.parametrize("distro", sorted(distros.REGISTRY))
def test_os_section_claims_only_registry_facts(distro):
    """The tool list is exactly the registry's (each build verifies it); other distributions' tools never leak."""
    d = distros.REGISTRY[distro]
    text = a.render({**M, 'distro': distro}, image=d.image, runtime=R,
                    definition=distros.ImageDefinition(d.id, d.version, d.revision))
    section = text.split(f"## Operating system ({d.name} {d.version})\n", 1)[1].split("\n## ", 1)[0]
    assert "- The managed base image includes: " + ", ".join(d.tools) + "." in section
    for other in distros.REGISTRY.values():
        if other.package_manager != d.package_manager:
            assert other.package_manager not in text
        for tool in set(other.tools) - set(d.tools):
            assert tool not in text
    assert "root (UID 0)" in text


def test_custom_image_makes_no_os_tool_or_user_claims():
    m, image, runtime = CASES["custom"]
    text = a.render(m, image=image, runtime=runtime)
    assert "unknown" in text and "includes:" not in text and "Base OS" not in text
    assert "root (UID 0)" not in text and "defined by the custom image" in text
    for d in distros.REGISTRY.values():
        assert d.package_manager not in text
    # A manager-named image does not make an environment managed (was a name-prefix check).
    assert 'includes:' not in a.render({**M, 'distro': None}, image='opencode-sandbox:debian', runtime=R)


def test_derived_image_keeps_the_inspected_definition():
    """Retained build provenance, not today's registry or the image name."""
    text = a.render(M, image='ocs-runtime:0123456789abcdef-aaaaaaaaaaaa', runtime=R,
                    definition=distros.ImageDefinition(M['distro'], '12', 1))
    assert 'Base OS: Debian 12' in text and 'derived from the managed base image' in text
    assert 'Custom image' not in text
    assert 'derived' not in a.render(M, image='opencode-sandbox:debian', runtime=R)


def test_workspace_lines_follow_kind_and_source():
    copy = a.render({**M, 'kind': 'project', 'source': '/x'}, image='i', runtime=R)
    assert "copy of a host directory" in copy and "The original is not mounted" in copy and "started empty" not in copy
    empty = a.render({**M, 'kind': 'project'}, image='i', runtime=R)
    assert "started empty" in empty and "copy of a host" not in empty
    quick = a.render({**M, 'kind': 'quick', 'source': '/x'}, image='i', runtime=R)
    assert "copy of a host directory" in quick and "quick (disposable) session" in quick
    assert "disposable" not in a.render(M, image='i', runtime=R)


def test_network_and_ports():
    off = a.render(M, image='i', runtime=R)
    assert "network is disabled" in off and "network isolation" not in off and "Published port" not in off
    on = a.render(M, image='i', runtime={**R, 'network': 'bridge', 'ports': [PORT]})
    assert "This is not network isolation" in on
    assert "container 8080/tcp is reachable from the host at 127.0.0.1:18080 only" in on


def test_observed_runtime_matching_renders_like_configured():
    assert a.render(M, image='i', runtime=R, observed=dict(R)) == a.render(M, image='i', runtime=R)


def test_observed_runtime_wins_and_the_difference_is_stated():
    configured = {**R, 'network': 'bridge', 'ports': [PORT]}
    text = a.render(M, image='i', runtime=configured, observed={**configured, 'network': 'none', 'memory': '8g'})
    assert "Networking mode: none" in text and "network is disabled" in text and "Memory limit: 8g" in text
    assert "Published port" not in text  # no network, no ports
    assert "current configuration (network bridge, memory limit 4g) applies only after the user recreates it" in text
    assert "CPU limit: 2.0" in text and "cpu" not in text.split("current configuration", 1)[1].split(")")[0].lower()


def test_initial_integrations_are_history():
    m = {**M, 'provisioning': {'requested': ['context7'], 'result': 'configured', 'at': '2026-10-27T00:00:00Z', 'state': 'done'}}
    text = a.render(m, image='i', runtime=R)
    assert "## Initial integrations" in text and "Provisioned once, at the first container start: context7 (configured)." in text
    assert "may have been changed or removed since" in text
    pending = a.render({**m, 'provisioning': {**m['provisioning'], 'state': 'pending'}}, image='i', runtime=R)
    assert "(not done yet): context7." in pending and "changed or removed since" not in pending
    for bad in ({'requested': []}, {'requested': 'context7'}, 'context7', None):
        assert "Initial integrations" not in a.render({**M, 'provisioning': bad}, image='i', runtime=R)


def test_refresh_verify(tmp_path):
    def env_dir(eid):
        return tmp_path/eid
    path = a.refresh(M, env_dir, image='opencode-sandbox:debian', runtime=R)
    assert path.stat().st_mode & 0o777 == 0o600
    assert a.verify(M, env_dir, image='opencode-sandbox:debian', runtime=R)
    assert a.verify(M, env_dir, image='opencode-sandbox:debian', runtime=R, observed=dict(R))
    assert not a.verify(M, env_dir, image='opencode-sandbox:debian', runtime={**R, 'network': 'bridge'})
    assert not a.verify(M, env_dir, image='opencode-sandbox:debian', runtime=R, observed={**R, 'pids': 50})
    assert path == a.path(M, env_dir) and path.parent.name == 'agent-context'
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_refresh_replaces_file_inside_the_same_directory(tmp_path):
    """The mount is the directory, so an atomic replace is visible in the container."""
    def env_dir(eid):
        return tmp_path/eid
    first = a.refresh(M, env_dir, image='opencode-sandbox:debian', runtime=R)
    directory_inode = first.parent.stat().st_ino
    file_inode = first.stat().st_ino
    second = a.refresh(M, env_dir, image='opencode-sandbox:debian', runtime={**R, 'network': 'bridge'})
    assert second.parent.stat().st_ino == directory_inode and second.stat().st_ino != file_inode
    assert 'bridge' in second.read_text() and sorted(p.name for p in second.parent.iterdir()) == ['context.md']


def fake_inspect(host_config):
    def docker(*args, **kwargs):
        if "{{json .State}}" in args:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"Running": True}), stderr="")
        if "{{json .Config.Labels}}" in args:
            return SimpleNamespace(returncode=0, stdout="null", stderr="")
        assert "{{json .HostConfig}}" in args
        return SimpleNamespace(returncode=0, stdout=json.dumps(host_config), stderr="")
    return docker


def test_observed_runtime_reads_the_container(monkeypatch):
    m = c.create("ocs-qa-obs", "scratch")
    m["runtime"] = c.validate_runtime_settings({"cpus": "1.5", "memory": "16384m", "pids": 300, "network": "none"})
    c.save(m)
    monkeypatch.setattr(c, "assert_owned", lambda m: None)
    monkeypatch.setattr(c, "docker", fake_inspect({"NetworkMode": "none", "NanoCpus": 1500000000,
                                                   "Memory": 16 * 1024**3, "PidsLimit": 300}))
    observed = c.observed_runtime(m)
    assert observed == {"network": "none", "cpus": "1.5", "memory": "16384m", "pids": 300}
    assert a.render(m, **c.guidance_inputs(m)) == a.render(m, **c.guidance_inputs(m, observe=False))
    monkeypatch.setattr(c, "docker", fake_inspect({"NetworkMode": "bridge", "NanoCpus": 0, "Memory": 8 * 1024**3,
                                                   "PidsLimit": 0}))
    assert c.observed_runtime(m) == {"network": "bridge", "cpus": "unlimited", "memory": "8g", "pids": "unlimited"}
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="No such container"))
    assert c.observed_runtime(m) is None
    assert c.memory_bytes("1024k") == 1024**2 and c.memory_bytes("512") == 512


def test_cli_show_falls_back_to_configuration_without_docker(monkeypatch):
    from typer.testing import CliRunner

    from opencode_sandbox import cli
    c.create("ocs-qa-show", "scratch")

    def unavailable(m):
        raise c.SandboxError("Docker is not reachable")
    monkeypatch.setattr(c, "observed_runtime", unavailable)
    result = CliRunner().invoke(cli.app, ["agent-context", "show", "ocs-qa-show"])
    assert result.exit_code == 0 and "Networking mode: bridge" in result.stdout
    assert "container not inspected (Docker is not reachable)" in result.stderr
