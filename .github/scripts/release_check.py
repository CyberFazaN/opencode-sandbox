"""Check a release tag and write its release notes (docs/engineering/RELEASING.md).

    python .github/scripts/release_check.py vX.Y.Z [NOTES_FILE]

The tag must be `v` + `__version__`, and CHANGELOG.md must have a dated section
`## X.Y.Z — YYYY-MM-DD` (not "Unreleased"); its body becomes the release notes."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def version(root=ROOT):
    text = (root / "src" / "opencode_sandbox" / "__init__.py").read_text()
    return re.search(r'^__version__ = "([^"]+)"$', text, re.MULTILINE).group(1)


def notes(tag, root=ROOT):
    """The release notes for `tag`; raises ValueError with the reason when the tag is not releasable."""
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError(f"tag {tag!r} is not of the form vX.Y.Z")
    current = version(root)
    if tag != f"v{current}":
        raise ValueError(f"tag {tag} does not match __version__ {current}")
    changelog = (root / "CHANGELOG.md").read_text()
    sections = re.split(r"^## ", changelog, flags=re.MULTILINE)
    for section in sections[1:]:
        heading, _, body = section.partition("\n")
        if heading.split()[0] != current:
            continue
        if not re.fullmatch(rf"{re.escape(current)} — \d{{4}}-\d{{2}}-\d{{2}}", heading.strip()):
            raise ValueError(f"CHANGELOG.md section {heading.strip()!r} is not dated (## {current} — YYYY-MM-DD)")
        if not body.strip():
            raise ValueError(f"CHANGELOG.md section {current} is empty")
        return body.strip() + "\n"
    raise ValueError(f"CHANGELOG.md has no section for {current}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    try:
        text = notes(sys.argv[1])
    except ValueError as exc:
        sys.exit(f"FAIL: {exc}")
    if len(sys.argv) == 3:
        Path(sys.argv[2]).write_text(text)
    print(f"{sys.argv[1]}: releasable; notes {len(text.splitlines())} lines")
