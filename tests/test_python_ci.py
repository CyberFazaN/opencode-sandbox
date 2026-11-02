"""Minimum/current Python gates; real Docker stays in the opt-in release campaign."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("workflow", "job"), [
    ("ci", "tests"), ("ci", "package"), ("ci", "pipx"), ("release", "pipx-tag"),
])
def test_python_endpoints_run_tests_packaging_and_pipx(workflow, job):
    text = (ROOT / f".github/workflows/{workflow}.yml").read_text()
    # Split only at another job, not the indented job fields.
    section = re.split(r"\n  \S", text.split(f"\n  {job}:\n", 1)[1], maxsplit=1)[0]
    assert 'python: ["3.11", "3.14"]' in section
    assert "python-version: ${{ matrix.python }}" in section


def test_current_arch_and_lowest_direct_dependency_coverage_remain():
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "container: archlinux:base-devel" in text
    assert "pacman -Syu" in text and "su ci -c" in text
    assert "dependencies: [current, lowest direct]" in text
    assert "typer==0.16.0 textual==4.0.0" in text


@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_ci_validates_stable_and_development_branches(event):
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    triggers = text.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    section = re.split(r"\n  \S", triggers.split(f"  {event}:\n", 1)[1], maxsplit=1)[0]
    assert "branches: [main, develop]" in section
    assert "pull_request_target:" not in triggers


def test_development_pushes_cannot_trigger_release_automation():
    text = (ROOT / ".github/workflows/release.yml").read_text()
    triggers = text.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert triggers.strip() == 'push:\n    tags: ["v*"]'
    assert "permissions: {}" in text
