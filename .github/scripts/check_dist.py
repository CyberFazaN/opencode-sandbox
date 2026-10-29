"""Check the built sdist and wheel: name and version, licence, entry point, Python requirement,
every image asset in the package, and no tests in the sdist.

    python .github/scripts/check_dist.py dist/

Packaging validation only (D-042): nothing is uploaded."""
import email.parser
import re
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "src" / "opencode_sandbox" / "assets" / "images"


def version():
    text = (ROOT / "src" / "opencode_sandbox" / "__init__.py").read_text()
    return re.search(r'^__version__ = "([^"]+)"$', text, re.MULTILINE).group(1)


def assets():
    return sorted(p.relative_to(ASSETS).as_posix() for p in ASSETS.rglob("*") if p.is_file())


def check(dist):
    problems = []
    v = version()
    wheels = sorted(Path(dist).glob("*.whl"))
    sdists = sorted(Path(dist).glob("*.tar.gz"))
    if [w.name for w in wheels] != [f"opencode_sandbox-{v}-py3-none-any.whl"]:
        problems.append(f"expected exactly the wheel opencode_sandbox-{v}-py3-none-any.whl, found {[w.name for w in wheels]}")
    if [s.name for s in sdists] != [f"opencode_sandbox-{v}.tar.gz"]:
        problems.append(f"expected exactly the sdist opencode_sandbox-{v}.tar.gz, found {[s.name for s in sdists]}")
    if problems:
        return problems

    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())
        info = f"opencode_sandbox-{v}.dist-info"
        meta = email.parser.Parser().parsestr(wheel.read(f"{info}/METADATA").decode())
        expected = {"Name": "opencode-sandbox", "Version": v, "Requires-Python": ">=3.14", "License-Expression": "MIT"}
        problems += [f"wheel metadata {key}: {meta.get(key)!r}, expected {value!r}"
                     for key, value in expected.items() if meta.get(key) != value]
        if f"{info}/licenses/LICENSE" not in names:
            problems.append("wheel: LICENSE missing in dist-info/licenses")
        if "opencode-sandbox = opencode_sandbox.cli:main" not in wheel.read(f"{info}/entry_points.txt").decode():
            problems.append("wheel: console script opencode-sandbox missing")
        packaged = sorted(n[len("opencode_sandbox/assets/images/"):] for n in names
                          if n.startswith("opencode_sandbox/assets/images/") and not n.endswith("/"))
        if packaged != assets():
            problems.append(f"wheel image assets {packaged} differ from the source tree {assets()}")
        if any(n.startswith("tests/") for n in names):
            problems.append("wheel contains tests")

    with tarfile.open(sdists[0]) as sdist:
        top = f"opencode_sandbox-{v}/"
        names = {m.name[len(top):] for m in sdist.getmembers() if m.name.startswith(top)}
        for required in ("LICENSE", "README.md", "pyproject.toml", "src/opencode_sandbox/__init__.py",
                         *(f"src/opencode_sandbox/assets/images/{a}" for a in assets())):
            if required not in names:
                problems.append(f"sdist: {required} missing")
        if any(n.startswith("tests/") for n in names):
            problems.append("sdist contains tests (MANIFEST.in prunes them)")
    return problems


if __name__ == "__main__":
    found = check(sys.argv[1] if len(sys.argv) > 1 else "dist")
    for problem in found:
        print(f"FAIL: {problem}")
    print("distributions OK" if not found else f"{len(found)} problem(s)")
    sys.exit(1 if found else 0)
