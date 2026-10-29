"""The user documentation (D-041): links and anchors resolve, code fits 80 columns, the install
commands name the current release, the guides are indexed, and the dashboard screenshot can be
regenerated. Commands and options named in the documents: tests/test_cli_structure.py."""
import re
from pathlib import Path

from test_language import ACTIVE_ROOT_DOCS, USER_GUIDES, active_files

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


def test_anchor_rules_match_github():
    sample = ROOT / ".work" / "anchor-sample.md"
    sample.parent.mkdir(exist_ok=True)
    sample.write_text("# Direct workspaces (not recommended)\n## 1. Check the host\n## Keys\n## Keys\n"
                      "```sh\n# a comment, not a heading\n```\n## `check NAME` and `doctor`\n")
    try:
        assert anchors(sample) == {"direct-workspaces-not-recommended", "1-check-the-host", "keys", "keys-1",
                                   "check-name-and-doctor"}
    finally:
        sample.unlink()


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


def test_daemon_hints_name_the_published_setup_guide():
    assert rid.SETUP_GUIDE == f"{REPOSITORY}/blob/main/docs/install.md#prepare-docker"
    for classification in (rid.MISMATCH, rid.UNAVAILABLE, rid.MISSING, rid.NOT_CONFIGURED):
        assert rid.SETUP_GUIDE in rid.HINTS[classification], classification
    assert "ROOTLESS-ARCH" not in (ROOT / "install.sh").read_text()


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
    for name in USER_GUIDES - {"README.md"}:
        assert f"]({name})" in index, name
        assert f"](docs/{name}" in readme, name


def test_user_documents_do_not_mention_internal_records():
    """D-037/D-038: no development history, audit or task references in the user documentation."""
    pattern = re.compile(r"V6-ISS|\bISSUE-|\bAUD-|\baudit|\b[TR]\d\d\b|\bRF\b|\b5\.\d+\.\d+|\b5\.x\b|6\.1\.0|docs/history|docs/engineering"
                         r"|ROOTLESS-ARCH|AGENT-CONTEXT\.md", re.IGNORECASE)
    found = [(path.name, m.group(0)) for path in user_documents() for m in pattern.finditer(path.read_text())]
    assert found == []


def test_documents_do_not_require_arch_linux_as_the_host():
    """D-046: Linux hosts in general; Arch Linux is the tested host, not a requirement."""
    pattern = re.compile(r"(only|supported) (tested )?host|You need Arch|Arch Linux is the (only|required|supported)|requires? Arch"
                         r"|other than Arch", re.IGNORECASE)
    files = [*user_documents(), *(ROOT / name for name in ACTIVE_ROOT_DOCS),
             ROOT / ".github/ISSUE_TEMPLATE/bug_report.yml"]
    found = [(path.name, line.strip()) for path in files for line in path.read_text().splitlines() if pattern.search(line)]
    assert found == []
    requirements = (DOCS / "install.md").read_text()
    for prerequisite in ("| Linux |", "newuidmap", "user namespaces", "cgroup v2", "pacman -S python-pipx git` on Arch Linux"):
        assert prerequisite in requirements, prerequisite


def test_the_dashboard_screenshot_can_be_regenerated():
    import dashboard_screenshot

    svg = dashboard_screenshot.render()
    assert svg.startswith("<svg") and "webapp" in svg and "api-refactor" in svg
    assert "/tmp" not in svg and "ocs-screenshot-" not in svg and str(Path.home()) not in svg
    committed = (DOCS / "images" / "dashboard.svg").read_text(encoding="utf-8")
    for name, *_ in dashboard_screenshot.ENVIRONMENTS:
        assert name in committed, name


# D-037/D-038/D-045: the public tree has no references to private records or earlier versions.
RECORD_REFERENCES = re.compile(
    r"V6-ISS|\bISSUE-\d|\bOBS-\d|\bAUD-\d|\b[TR]\d\d\b|\bRF\b|\bP0\d\b|(?<!no-)\baudit|[Rr]emediation|TEST-RESULTS"
    r"|docs/history|engineering/history|qa-v5|publication/|\b5\.x\b|\bv5\b|\b5\.\d+\.\d+|6\.1\.0")
# Commit hashes in documents (the workflows pin actions by commit SHA on purpose).
COMMIT_HASH = re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b")
CODE_REFERENCES = re.compile(
    r"V6-ISS|\bISSUE-\d|\bOBS-\d|\bAUD-\d|(?<!no-)\baudit|[Rr]emediation|TEST-RESULTS|docs/history|engineering/history"
    r"|qa-v5|ocs-test-[tr]\d\d-|\"t1\d-")


def public_records():
    """The project's documents: root documents, user guides, engineering records (not the
    working records of a running effort in a subdirectory, D-045) and the GitHub files."""
    return [*(ROOT / n for n in sorted(ACTIVE_ROOT_DOCS)), *user_documents(), *sorted((DOCS / "engineering").glob("*.md")),
            *sorted(p for p in (ROOT / ".github").rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".md", ".yml", ".py", ".sh"))]


def test_public_records_have_no_internal_references():
    found = [(path.relative_to(ROOT).as_posix(), m.group(0)) for path in public_records()
             for pattern in ((RECORD_REFERENCES, COMMIT_HASH) if path.suffix == ".md" else (RECORD_REFERENCES,))
             for m in pattern.finditer(path.read_text(encoding="utf-8"))]
    assert found == []


def test_code_and_tests_have_no_internal_references():
    files = [ROOT / "install.sh", ROOT / "setup-rootless.sh", ROOT / "pyproject.toml",
             *(p for top in ("src", "tests") for p in sorted((ROOT / top).rglob("*"))
               if p.is_file() and "__pycache__" not in p.parts and not any(x.endswith(".egg-info") for x in p.parts)
               and p.suffix in (".py", ".sh", ".json", ""))]
    found = []
    for path in files:
        if path == Path(__file__).resolve():
            continue  # the patterns themselves
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        found += [(path.relative_to(ROOT).as_posix(), m.group(0)) for m in CODE_REFERENCES.finditer(text)]
    assert found == []
