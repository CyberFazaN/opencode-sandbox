"""One version literal, version-independent resource names, labelled Docker objects."""
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

import opencode_sandbox
from opencode_sandbox import backup as b
from opencode_sandbox import core as c

ROOT = Path(__file__).resolve().parents[1]


def test_single_version_literal():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "version" not in project["project"] and "version" in project["project"]["dynamic"]
    assert project["tool"]["setuptools"]["dynamic"]["version"] == {"attr": "opencode_sandbox.__version__"}
    assert opencode_sandbox.__version__ == "6.0.0"
    sources = [p for p in (ROOT / "src").rglob("*.py")] + [ROOT / "install.sh", ROOT / "pyproject.toml"]
    literal = re.compile(r"\b6\.\d+\.\d+\b")
    holders = [p.relative_to(ROOT).as_posix() for p in sources if literal.search(p.read_text())]
    assert holders == ["src/opencode_sandbox/__init__.py"]


def test_cli_version_option():
    p = subprocess.run([sys.executable, "-m", "opencode_sandbox.cli", "--version"], capture_output=True, text=True, check=False)
    assert p.returncode == 0 and p.stdout.strip() == f"opencode-sandbox {opencode_sandbox.__version__}"


def test_installer_reads_version_from_package(tmp_path):
    p = subprocess.run(["bash", str(ROOT / "install.sh"), "uninstall", "--dry-run"], capture_output=True, text=True, check=False,
                       env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}, timeout=60)
    assert f"OpenCode Sandbox {opencode_sandbox.__version__}" in p.stdout


def test_resource_names_are_version_independent():
    m = {"id": "0123456789abcdef"}
    assert c.cname(m) == "ocs-0123456789abcdef"
    assert c.volume(m) == "ocs-home-0123456789abcdef"
    assert c.volume({**m, "home_volume": "ocs-stage-0123456789abcdef-0123abcd"}) == "ocs-stage-0123456789abcdef-0123abcd"
    with pytest.raises(c.SandboxError):
        c.volume({**m, "home_volume": "other-home-0123456789abcdef"})


def test_labels_mark_manager_objects():
    assert c.labels(scoped=False) == ["--label", "org.opencode-sandbox.managed=true",
                                      "--label", f"org.opencode-sandbox.manager-version={opencode_sandbox.__version__}"]
    assert c.labels()[-2:] == ["--label", f"org.opencode-sandbox.data-dir={c.data_id()}"]
    assert c.labels("0123456789abcdef")[-2:] == ["--label", "org.opencode-sandbox.id=0123456789abcdef"]


def test_container_and_volume_are_labelled(monkeypatch):
    m = c.create("ocs-test-labels", "scratch")
    calls = []

    def docker(*args, capture=False, check=True):
        calls.append(args)
        if args[:2] == ("container", "inspect"):
            return SimpleNamespace(returncode=1, stdout="", stderr="Error: No such container: x")
        if args[:2] == ("volume", "inspect"):
            if any(a[:2] == ("volume", "create") for a in calls):
                return SimpleNamespace(returncode=0, stdout=json.dumps([{"Labels": {"org.opencode-sandbox.id": m["id"]}}]), stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="Error: no such volume")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    c.start(m)
    for verb in ("volume", "run"):
        call = next(a for a in calls if a[0] == verb and (verb == "run" or a[1] == "create"))
        assert "org.opencode-sandbox.managed=true" in call
        assert f"org.opencode-sandbox.manager-version={opencode_sandbox.__version__}" in call
        assert f"org.opencode-sandbox.id={m['id']}" in call
    run = next(a for a in calls if a[0] == "run")
    assert run[run.index("--name") + 1] == f"ocs-{m['id']}"


def test_new_metadata_uses_schema_2():
    m = c.create("ocs-test-schema", "scratch")
    assert m["schema"] == c.METADATA_SCHEMA == 2


def test_unsupported_metadata_schema_is_refused_and_untouched():
    m = c.create("ocs-test-oldschema", "scratch")
    path = c.env_dir(m["id"]) / "metadata.json"
    data = json.loads(path.read_text()); data["schema"] = 1
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    assert c.all_envs() == [] and c.invalid_metadata() == [path]
    assert "not supported" in c.metadata_error(path) and "left unchanged" in c.metadata_error(path)
    with pytest.raises(c.SandboxError, match="not found"):
        c.resolve("ocs-test-oldschema")
    assert path.read_bytes() == before


def test_cli_list_explains_refused_metadata():
    from typer.testing import CliRunner

    from opencode_sandbox import cli
    m = c.create("ocs-test-oldcli", "scratch")
    path = c.env_dir(m["id"]) / "metadata.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "schema": 1}))
    result = CliRunner().invoke(cli.app, ["list"])
    assert "schema 1 is not supported" in result.output


@pytest.mark.parametrize("schema", [1, 2])
def test_unsupported_backup_schemas_are_refused(tmp_path, schema):
    root = tmp_path / "old.ocsbackup"; root.mkdir()
    (root / "workspace.tar.gz").write_bytes(b"x")
    (root / "manifest.json").write_text(json.dumps({"format": "opencode-sandbox-backup", "schema": schema,
                                                    "files": {"workspace.tar.gz": b.digest(root / "workspace.tar.gz")}}))
    with pytest.raises(c.SandboxError, match="Unsupported backup schema"):
        b.verify(root)
