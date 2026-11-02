"""The application has one installation path (D-048), not host setup scripts."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["install.sh", "setup-rootless.sh"])
def test_legacy_installers_are_not_shipped_in_the_checkout(name):
    assert not (ROOT / name).exists()
