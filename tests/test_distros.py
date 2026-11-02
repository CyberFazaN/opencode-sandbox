"""D-005: declarative distribution registry, per-environment distribution, custom images."""
import json
import os
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

from opencode_sandbox import backup as b
from opencode_sandbox import core as c
from opencode_sandbox import distros


def test_registry_records_are_complete_and_assets_exist():
    assert distros.DEFAULT in distros.REGISTRY
    for d in distros.REGISTRY.values():
        assert re.fullmatch(r"[a-z][a-z0-9]*", d.id) and d.image == f"opencode-sandbox:{d.id}"
        assert d.dockerfile.is_file() and d.revision >= 1 and d.tools
        assert d.package_manager in "\n".join(d.context_lines())
        assert dict(d.os_release).get("ID") and len(dict(d.os_release)) == len(d.os_release) >= 2
        assert "opencode" in d.tools and "python3" in d.tools  # run/shell need python3
        assert d.image_labels() == {"org.opencode-sandbox.distro": d.id, "org.opencode-sandbox.distro-version": d.version,
                                    "org.opencode-sandbox.image-revision": str(d.revision)}
        assert "FROM " in d.dockerfile.read_text()
    with pytest.raises(dataclass_error()):
        distros.REGISTRY[distros.DEFAULT].id = "x"
    with pytest.raises(c.SandboxError, match="Unknown distribution 'nope'; available: debian, arch"):
        distros.get("nope")


def dataclass_error():
    import dataclasses
    return dataclasses.FrozenInstanceError


def test_custom_images_are_explicit_not_selected_by_environment(tmp_path):
    # A fresh process also covers environment settings read at import/startup time.
    code = '''import json
from opencode_sandbox import core as c
default = c.create("ocs-test-default", "scratch")
explicit = c.create("ocs-test-explicit", "scratch", image="example.org/explicit:1")
print(json.dumps([(m["distro"], c.env_image(m)) for m in (default, explicit)]))
'''
    environment = dict(os.environ, OPENCODE_SANDBOX_HOME=str(tmp_path / "data"),
                       OPENCODE_SANDBOX_CONFIG=str(tmp_path / "config"),
                       OPENCODE_SANDBOX_IMAGE="example.org/not-selected:1",
                       DOCKER_CONFIG=str(tmp_path / "docker-config"),
                       OPENCODE_SANDBOX_DOCKER_CONTEXT="ocs-test-no-daemon")
    result = subprocess.run([sys.executable, "-B", "-c", code], env=environment,
                            capture_output=True, text=True, check=True, timeout=5)
    assert json.loads(result.stdout) == [[distros.DEFAULT, distros.get(distros.DEFAULT).image],
                                        [None, "example.org/explicit:1"]]


def test_install_script_is_valid_posix_sh():
    script = distros.IMAGES / "common" / "install-opencode.sh"
    assert subprocess.run(["sh", "-n", str(script)], check=False).returncode == 0


def test_create_records_the_distribution():
    m = c.create("ocs-qa-d1", "scratch")
    assert m["distro"] == distros.DEFAULT and "image" not in m
    assert c.env_distro(m) is distros.REGISTRY[distros.DEFAULT]
    assert c.env_image(m) == "opencode-sandbox:debian"
    assert c.resolve("ocs-qa-d1")["distro"] == distros.DEFAULT
    with pytest.raises(c.SandboxError, match="Unknown distribution 'nope'; available: debian, arch"):
        c.create("ocs-qa-d2", "scratch", distro="nope")
    arch = c.create("ocs-qa-d3", "scratch", distro="arch")
    assert arch["distro"] == "arch" and c.env_image(arch) == "opencode-sandbox:arch"
    assert sorted(e["name"] for e in c.all_envs()) == ["ocs-qa-d1", "ocs-qa-d3"]


def test_custom_image_is_explicit():
    m = c.create("ocs-qa-custom", "scratch", image="registry.example/team/agent:1.2")
    assert m["distro"] is None and c.env_distro(m) is None and c.env_image(m) == "registry.example/team/agent:1.2"
    for bad, match in (("opencode-sandbox:debian", "use --distro"), ("-x", "Invalid image"), ("a b", "Invalid image")):
        with pytest.raises(c.SandboxError, match=match):
            c.create("ocs-qa-bad", "scratch", image=bad)
    with pytest.raises(c.SandboxError, match="not both"):
        c.create("ocs-qa-bad", "scratch", distro="debian", image="x:1")


@pytest.mark.parametrize("change,reason", [
    (lambda m: m.pop("distro"), "no distribution"),
    (lambda m: m.update(distro="nope"), "unknown distribution 'nope'"),
    (lambda m: m.update(distro=None), "custom-image environment without an image"),
])
def test_metadata_without_a_valid_distribution_is_ignored(change, reason):
    m = c.create("ocs-qa-meta", "scratch")
    path = c.env_dir(m["id"]) / "metadata.json"
    data = json.loads(path.read_text()); change(data); path.write_text(json.dumps(data))
    assert c.all_envs() == [] and reason in c.metadata_error(path)


def test_start_checks_the_distribution_image_and_uses_it(monkeypatch):
    m = c.create("ocs-qa-start", "scratch")
    calls = []
    def docker(*a, **k):
        calls.append(a)
        return SimpleNamespace(returncode=1 if a[:2] == ("image", "inspect") else 0, stdout="", stderr="")
    monkeypatch.setattr(c, "docker", docker)
    with pytest.raises(c.SandboxError, match="opencode-sandbox:debian missing. Run: opencode-sandbox build --distro debian"):
        c.start(m)
    custom = c.create("ocs-qa-start2", "scratch", image="custom:1")
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "ensure_volume", lambda m: None)
    monkeypatch.setattr(c, "port_conflicts", lambda m, r: [])
    calls.clear()
    c.start(custom)
    run = next(a for a in calls if a[0] == "run")
    assert run[-3:] == ("custom:1", "sleep", "infinity") and not any(a[:2] == ("image", "inspect") for a in calls)


def test_backup_manifest_carries_the_distribution_and_restore_requires_it(tmp_path, monkeypatch):
    for name, value in (("ensure_runtime", lambda image=True: None), ("inspect_container", lambda m: None),
                        ("assert_volume_owned", lambda m: None), ("volume_state", lambda m: None)):
        monkeypatch.setattr(c, name, value)
    for name, options in (("registry", {}), ("custom", {"image": "custom:1"})):
        m = c.create(f"ocs-test-{name}", "scratch", **options)
        manifest = b.verify(b.backup(m, tmp_path / "backups"))
        restored = b._restored_settings(manifest["environment"])
        assert restored["distro"] == m["distro"]
        assert restored["custom_image"] == options.get("image")
    env = {"name": "o", "kind": "scratch", "profile": "default"}
    for bad, match in (({}, "does not record the distribution"), ({"distro": "nope"}, "Unknown distribution"),
                       ({"distro": None}, "lacks the image")):
        with pytest.raises(c.SandboxError, match=match):
            b._restored_settings({**env, **bad})
