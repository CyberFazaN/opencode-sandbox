"""The application has one installation path (D-048), not host setup scripts."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["install.sh", "setup-rootless.sh"])
def test_legacy_installers_are_not_shipped_in_the_checkout(name):
    assert not (ROOT / name).exists()


def test_install_guide_recommends_pipx_and_scopes_legacy_uninstall_to_old_checkouts():
    text = (ROOT / "docs/install.md").read_text()
    current, legacy = text.split("## Moving from a legacy source installation", 1)
    assert "pipx install git+https://" in current
    assert "./install.sh" not in current and "./setup-rootless.sh" not in text
    assert "old checkout" in legacy and "./install.sh uninstall" in legacy
    assert "do not delete" in legacy.lower() and "command -v opencode-sandbox" in legacy


def test_python_upgrade_repair_uses_pipx_not_a_replacement_installer():
    text = " ".join((ROOT / "docs/troubleshooting.md").read_text().split())
    assert "Python minor upgrade" in text and "pipx reinstall" in text and "--python" in text
