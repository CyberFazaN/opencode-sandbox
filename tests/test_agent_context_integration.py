"""D-008: Agent Context reaches OpenCode V2 through a read-only directory mount and the image's
system config; managed launches regenerate it and use a private (`--standalone`) server."""
import json
import re
from types import SimpleNamespace

from opencode_sandbox import agent_context as ac
from opencode_sandbox import core as c

ASSETS = c.distros.IMAGES


def test_image_system_config_lists_only_the_agent_context():
    config = json.loads((ASSETS / "common" / "opencode-system.json").read_text())
    assert config == {"instructions": [ac.CONTAINER_PATH]}
    for distro in c.distros.REGISTRY.values():
        dockerfile = distro.dockerfile.read_text()
        assert f"COPY common/opencode-system.json {ac.SYSTEM_CONFIG}" in dockerfile
        assert "opencode-ai" not in dockerfile


def test_interactive_refreshes_guidance_and_launches_standalone(monkeypatch):
    m = c.create("ocs-qa-ac", "scratch")
    commands = []
    monkeypatch.setattr(c, "start", lambda m: None)
    monkeypatch.setattr(c, "observed_runtime", lambda m: None)
    monkeypatch.setattr(c, "_tty", lambda: True)
    monkeypatch.setattr(c, "profile_mismatch", lambda m: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: commands.append(a) or SimpleNamespace(returncode=0))
    assert not ac.path(m, c.env_dir).exists()
    assert c.interactive(m) == 0
    assert ac.verify(m, c.env_dir, image=c.env_image(m), runtime=c.runtime_settings(m))
    args = next(a for a in commands if a[0] == "exec")
    script = args[args.index("-c") + 1]
    assert args[0] == "exec" and args[-3:-1] == (ac.CONTAINER_PATH, ac.SYSTEM_CONFIG)
    assert "['opencode','--standalone']" in script
    assert "OPENCODE_CONFIG_CONTENT" not in script and "base64" not in script


def test_launch_guidance_describes_the_observed_container(monkeypatch):
    """Before a launch the guidance reports what Docker shows for the container."""
    m = c.create("ocs-qa-acobs", "scratch")
    monkeypatch.setattr(c, "start", lambda m: None)
    monkeypatch.setattr(c, "_tty", lambda: True)
    monkeypatch.setattr(c, "profile_mismatch", lambda m: None)
    monkeypatch.setattr(c, "observed_runtime", lambda m: {**c.runtime_settings(m), "network": "none"})
    monkeypatch.setattr(c, "assert_owned", lambda m: None)  # the mocked observation is of an owned container
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))
    assert c.interactive(m) == 0
    text = ac.path(m, c.env_dir).read_text()
    assert "Networking mode: none" in text and "current configuration (network bridge)" in text


def test_every_caller_renders_through_guidance_inputs():
    root = ASSETS.parents[1]
    calls = []
    for name in ("core.py", "cli.py", "tui.py"):
        calls += re.findall(r"\bac\.(?:render|refresh|verify)\([^)]*\)", (root / name).read_text())
    assert len(calls) >= 7 and all("**" in call for call in calls), calls


def test_start_mounts_the_guidance_directory_read_only(monkeypatch):
    m = c.create("ocs-qa-acmount", "scratch")
    calls = []
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "ensure_volume", lambda m: None)
    monkeypatch.setattr(c, "port_conflicts", lambda m, r: [])
    monkeypatch.setattr(c, "docker", lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    c.start(m)
    run = next(a for a in calls if a[0] == "run")
    mount = f"type=bind,src={ac.directory(m, c.env_dir)},dst={ac.CONTAINER_DIR},readonly"
    assert mount in run
    assert ac.path(m, c.env_dir).is_file()


def test_no_opencode_v1_package_or_env_injection_left():
    root = ASSETS.parents[3]
    for path in [*sorted((root / "src").rglob("*.py")), *sorted(f for f in ASSETS.rglob("*") if f.is_file()),
                 root / "docs" / "opencode.md"]:
        text = path.read_text()
        assert "opencode-ai" not in text, path
        assert "/tmp/ocs-agent-context.md" not in text, path
