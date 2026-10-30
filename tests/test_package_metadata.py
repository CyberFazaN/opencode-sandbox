"""D-036: licence and identity of the published distribution."""
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = tomllib.loads((ROOT / "pyproject.toml").read_text())
PROJECT = CONFIG["project"]
REPOSITORY = "https://github.com/CyberFazaN/opencode-sandbox"


def test_distribution_identity():
    assert PROJECT["name"] == "opencode-sandbox"
    assert PROJECT["scripts"] == {"opencode-sandbox": "opencode_sandbox.cli:main"}
    assert PROJECT["authors"] == [{"name": "CyberFazaN"}]
    assert "unofficial" in PROJECT["description"]
    assert (ROOT / PROJECT["readme"]).is_file()


def test_mit_licence_is_declared_and_shipped():
    assert PROJECT["license"] == "MIT" and PROJECT["license-files"] == ["LICENSE"]
    text = (ROOT / "LICENSE").read_text()
    assert text.startswith("MIT License\n") and "Copyright (c) 2026 CyberFazaN" in text
    # PEP 639: a licence expression replaces the licence classifiers.
    assert not any(c.startswith("License ::") for c in PROJECT["classifiers"])


def test_project_urls_point_to_the_repository():
    assert PROJECT["urls"] and all(url.startswith(REPOSITORY) for url in PROJECT["urls"].values())


def test_readme_states_independence():
    assert "not affiliated with or endorsed by the OpenCode project" in " ".join((ROOT / "README.md").read_text().split())


def test_verified_python_floor_and_lint_target_agree():
    assert PROJECT["requires-python"] == ">=3.11"
    assert CONFIG["tool"]["ruff"]["target-version"] == "py311"
    for minor in range(11, 15):
        assert f"Programming Language :: Python :: 3.{minor}" in PROJECT["classifiers"]
