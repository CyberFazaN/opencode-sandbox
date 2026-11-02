"""The user documentation (D-041): links and anchors resolve, code fits 80 columns, the install
commands name the current release, the guides are indexed, and the dashboard screenshot can be
regenerated. Commands and options named in the documents: tests/test_cli_structure.py."""
import re
from pathlib import Path

from test_language import active_files

from opencode_sandbox import __version__
from opencode_sandbox import runtime_identity as rid

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPOSITORY = "https://github.com/CyberFazaN/opencode-sandbox"
LINK = re.compile(r"\]\(([^)\s]+)\)")


def user_documents():
    return [ROOT / "README.md", *sorted(DOCS.glob("*.md"))]


def outside_code(text):
    """The lines of a Markdown text that are not in fenced code blocks."""
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            yield line


def code_lines(text):
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif fenced:
            yield line


def anchors(path):
    """GitHub's heading anchors: lower case, punctuation dropped, spaces to hyphens, -N for repeats."""
    seen, found = {}, set()
    for line in outside_code(path.read_text(encoding="utf-8")):
        match = re.match(r"#{1,6} (.+)", line)
        if match:
            slug = re.sub(r"[^\w\- ]", "", match.group(1).strip().lower()).replace(" ", "-")
            found.add(f"{slug}-{seen[slug]}" if slug in seen else slug)
            seen[slug] = seen.get(slug, 0) + 1
    return found


def test_anchor_rules_match_github(tmp_path):
    sample = tmp_path / "anchor-sample.md"
    sample.write_text("# Direct workspaces (not recommended)\n## 1. Check the host\n## Keys\n## Keys\n"
                      "```sh\n# a comment, not a heading\n```\n## `check NAME` and `doctor`\n")
    assert anchors(sample) == {"direct-workspaces-not-recommended", "1-check-the-host", "keys", "keys-1",
                               "check-name-and-doctor"}


def test_relative_links_and_anchors_resolve():
    """In every active Markdown document: relative targets exist, and #anchors exist in their target."""
    broken = []
    for path in active_files():
        if path.suffix != ".md":
            continue
        for target in LINK.findall("\n".join(outside_code(path.read_text(encoding="utf-8")))):
            if re.match(r"[a-z]+:", target):
                continue
            file, _, anchor = target.partition("#")
            resolved = (path.parent / file) if file else path
            if not resolved.exists():
                broken.append((path.relative_to(ROOT).as_posix(), target))
            elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
                broken.append((path.relative_to(ROOT).as_posix(), target, "anchor"))
    assert broken == []


def test_links_into_this_repository_point_at_existing_documents():
    """Absolute links to the repository's own files (the hints of a pipx installation use them)."""
    broken = []
    for path in [*user_documents(), ROOT / "src" / "opencode_sandbox" / "runtime_identity.py"]:
        for url in re.findall(re.escape(REPOSITORY) + r"/blob/main/([^\s)\"'`>]+)", path.read_text(encoding="utf-8")):
            file, _, anchor = url.partition("#")
            if not (ROOT / file).is_file() or (anchor and anchor not in anchors(ROOT / file)):
                broken.append((path.name, url))
    assert broken == []


def test_daemon_hints_link_to_published_documentation():
    prefix = f"{REPOSITORY}/blob/main/"
    assert rid.SETUP_GUIDE.startswith(prefix)
    file, _, anchor = rid.SETUP_GUIDE.removeprefix(prefix).partition("#")
    target = ROOT / file
    assert target.is_file() and target.suffix == ".md"
    assert not anchor or anchor in anchors(target)
    for classification in (rid.MISMATCH, rid.UNAVAILABLE, rid.MISSING, rid.NOT_CONFIGURED):
        assert rid.SETUP_GUIDE in rid.HINTS[classification], classification


def test_code_blocks_fit_80_columns():
    """The documents are read in terminals too; long commands are wrapped with a backslash."""
    wide = [(path.name, line) for path in user_documents() for line in code_lines(path.read_text(encoding="utf-8"))
            if len(line) > 80]
    assert wide == []


def test_install_commands_name_the_current_release():
    tags = {tag for path in user_documents() for tag in re.findall(r"opencode-sandbox\.git@(v[\w.]+)", path.read_text())}
    assert tags == {f"v{__version__}", "vX.Y.Z"}


def test_every_guide_is_indexed_and_linked_from_the_readme():
    index = (DOCS / "README.md").read_text()
    readme = (ROOT / "README.md").read_text()
    for path in sorted(DOCS.glob("*.md")):
        if path.name == "README.md":
            continue
        name = path.name
        assert f"]({name})" in index, name
        assert f"](docs/{name}" in readme, name


def test_the_dashboard_screenshot_can_be_regenerated():
    import dashboard_screenshot

    svg = dashboard_screenshot.render()
    assert svg.startswith("<svg") and "webapp" in svg and "api-refactor" in svg
    assert "/tmp" not in svg and "ocs-screenshot-" not in svg and str(Path.home()) not in svg
    committed = (DOCS / "images" / "dashboard.svg").read_text(encoding="utf-8")
    for name, *_ in dashboard_screenshot.ENVIRONMENTS:
        assert name in committed, name
