"""The release helpers in .github/scripts (D-042, docs/engineering/RELEASING.md): the tag and
CHANGELOG check that produces the release notes, and the content check of the distributions."""
import importlib.util
import re
import shutil
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / ".github" / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release_check = load("release_check")
check_dist = load("check_dist")


def project(tmp_path, changelog, version="6.0.0"):
    (tmp_path / "src" / "opencode_sandbox").mkdir(parents=True)
    (tmp_path / "src" / "opencode_sandbox" / "__init__.py").write_text(f'__version__ = "{version}"\n')
    (tmp_path / "CHANGELOG.md").write_text(changelog)
    return tmp_path


@pytest.mark.parametrize("unreleased", ["", "## Unreleased\n\nNext release.\n\n"])
def test_release_notes_come_from_the_dated_section(tmp_path, unreleased):
    root = project(tmp_path, "# Changelog\n\n" + unreleased + "## 6.0.0 — 2026-11-02\n\nInitial release.\n\n### Added\n\n- A\n\n## 5.9.9 — 2026-01-01\n\nOld.\n")
    notes = release_check.notes("v6.0.0", root)
    assert notes.startswith("Initial release.") and "- A" in notes and "Old." not in notes and "Next release." not in notes


@pytest.mark.parametrize(("tag", "changelog", "reason"), [
    ("v6.0.0", "## 6.0.0 — Unreleased\n\nText\n", "not dated"),
    ("v6.0.1", "## 6.0.0 — 2026-11-02\n\nText\n", "does not match"),
    ("6.0.0", "## 6.0.0 — 2026-11-02\n\nText\n", "vX.Y.Z"),
    ("v6.0.0", "## 6.0.1 — 2026-11-02\n\nText\n", "no section"),
    ("v6.0.0", "## 6.0.0 — 2026-11-02\n\n", "empty"),
])
def test_unreleasable_tags_are_refused(tmp_path, tag, changelog, reason):
    with pytest.raises(ValueError, match=reason):
        release_check.notes(tag, project(tmp_path, changelog))


def test_the_current_version_is_releasable_only_with_a_dated_section():
    """The section of __version__ is dated by the release branch (RELEASING.md step 1); a bare
    "Unreleased" section above it (step 6) does not change that."""
    current = release_check.version()
    sections = (ROOT / "CHANGELOG.md").read_text().split("\n## ")[1:]
    heading = next(s.split("\n")[0] for s in sections if s.split()[0] == current)
    if re.fullmatch(rf"{re.escape(current)} — \d{{4}}-\d{{2}}-\d{{2}}", heading.strip()):
        assert release_check.notes(f"v{current}")
    else:
        with pytest.raises(ValueError, match="not dated"):
            release_check.notes(f"v{current}")


def distributions(tmp_path, drop=(), extra=(), requires_python=None):
    """A minimal wheel and sdist with this checkout's version and image assets, minus `drop`,
    plus the sdist files `extra`."""
    v = check_dist.version()
    dist = tmp_path / "dist"
    dist.mkdir()
    info = f"opencode_sandbox-{v}.dist-info"
    requires_python = requires_python or tomllib.loads((check_dist.ROOT / "pyproject.toml").read_text())["project"]["requires-python"]
    files = {f"{info}/METADATA": f"Name: opencode-sandbox\nVersion: {v}\nRequires-Python: {requires_python}\nLicense-Expression: MIT\n",
             f"{info}/entry_points.txt": "[console_scripts]\nopencode-sandbox = opencode_sandbox.cli:main\n",
             f"{info}/licenses/LICENSE": "MIT",
             **{f"opencode_sandbox/assets/images/{a}": "x" for a in check_dist.assets()}}
    with zipfile.ZipFile(dist / f"opencode_sandbox-{v}-py3-none-any.whl", "w") as wheel:
        for name, text in files.items():
            if name not in drop:
                wheel.writestr(name, text)
    tree = tmp_path / f"opencode_sandbox-{v}"
    for name in ("LICENSE", "README.md", "pyproject.toml", "src/opencode_sandbox/__init__.py",
                 *(f"src/opencode_sandbox/assets/images/{a}" for a in check_dist.assets()), *extra):
        if name not in drop:
            (tree / name).parent.mkdir(parents=True, exist_ok=True)
            (tree / name).write_text("x")
    with tarfile.open(dist / f"opencode_sandbox-{v}.tar.gz", "w:gz") as sdist:
        sdist.add(tree, arcname=tree.name)
    shutil.rmtree(tree)
    return dist


def test_complete_distributions_pass(tmp_path):
    assert check_dist.check(distributions(tmp_path)) == []


def test_python_requirement_is_checked_against_the_project(tmp_path, monkeypatch):
    root = project(tmp_path / "project", "")
    (root / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"\n')
    monkeypatch.setattr(check_dist, "ROOT", root)
    assert check_dist.check(distributions(tmp_path)) == []


def test_incorrect_python_requirement_is_reported(tmp_path):
    problems = check_dist.check(distributions(tmp_path, requires_python=">=99"))
    assert any("Requires-Python" in problem for problem in problems)


def test_a_missing_image_asset_or_licence_is_reported(tmp_path):
    asset = check_dist.assets()[0]
    dist = distributions(tmp_path, drop={f"opencode_sandbox/assets/images/{asset}",
                                         f"opencode_sandbox-{check_dist.version()}.dist-info/licenses/LICENSE"})
    problems = check_dist.check(dist)
    assert any("image assets" in p for p in problems) and any("LICENSE missing" in p for p in problems)


def test_tests_in_the_sdist_are_reported(tmp_path):
    dist = distributions(tmp_path, extra=("tests/test_x.py",))
    assert any("contains tests" in p for p in check_dist.check(dist))


@pytest.mark.parametrize("name", ["install.sh", "setup-rootless.sh"])
def test_legacy_installers_in_the_sdist_are_reported(tmp_path, name):
    dist = distributions(tmp_path, extra=(name,))
    assert any(name in p and "retired" in p for p in check_dist.check(dist))
