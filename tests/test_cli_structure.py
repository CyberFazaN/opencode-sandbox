"""Command groups, and every command (and option) the product or the user documents name exists."""
import re
from pathlib import Path

import typer
from typer.core import TyperGroup
from typer.testing import CliRunner

from opencode_sandbox import core as c
from opencode_sandbox import integrations as ig
from opencode_sandbox.cli import app

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "opencode_sandbox"
GROUPS = {"changes", "backup", "container", "disk", "config", "opencode", "agent-context", "providers"}


def root():
    return typer.main.get_command(app)


def resolves(words):
    """True when `words` start with an existing command path: a command (arguments may follow)
    or a group followed by nothing or an option (it shows its help)."""
    cmd = root()
    for word in words:
        if not isinstance(cmd, TyperGroup):
            return True
        if word.startswith("-"):
            return cmd is not root()
        cmd = cmd.commands.get(word)
        if cmd is None:
            return False
    return cmd is not root()


def test_top_level_is_small_and_grouped():
    commands = root().commands
    groups = {n for n, x in commands.items() if isinstance(x, TyperGroup)}
    assert groups == GROUPS
    assert len(commands) <= 25, sorted(commands)
    removed = {"diff", "export", "snapshot", "recreate", "recreate-recover", "runtime-usage", "backups", "restore",
               "backup-verify", "backup-prune", "restore-check", "restore-resume", "restore-rollback", "cleanup", "images",
               "images-prune", *(f"changes-{x}" for x in ("export", "review", "apply", "inspect", "stage", "diff", "unstage"))}
    assert not removed & set(commands)  # no aliases (no users to keep compatible)
    for words in (["changes", "show"], ["changes", "export"], ["changes", "bundle"], ["changes", "branch-diff"],
                  ["backup", "create"], ["backup", "list"], ["backup", "restore"], ["backup", "restore-rollback"],
                  ["container", "usage"], ["container", "snapshot"], ["container", "recreate"],
                  ["container", "recreate-recover"], ["disk", "usage"], ["disk", "cleanup"]):
        assert resolves(words), words


def test_every_help_works_and_groups_show_their_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for panel in ("Environments", "Sessions", "Settings, changes and data", "Maintenance"):
        assert panel in result.output
    stack = [([], root())]
    while stack:
        path, cmd = stack.pop()
        result = runner.invoke(app, [*path, "--help"])
        assert result.exit_code == 0, (path, result.output)
        if isinstance(cmd, TyperGroup):
            stack += [([*path, n], x) for n, x in cmd.commands.items()]
    # A group without a subcommand shows its help instead of an error.
    result = runner.invoke(app, ["backup"])
    assert "create" in result.output and "restore" in result.output


COMMAND = re.compile(r"opencode-sandbox ([a-z][^`\n\"'),;:]*)")
PROSE = {"without", "is", "and", "or", "can", "in", "on", "itself", "data", "manager", "a", "the", "to"}


def named_commands(text):
    for match in COMMAND.finditer(text):
        words = match.group(1).split()
        if words[0] in PROSE:  # prose after the program name, not a command
            continue
        yield match.group(0), words


def test_every_command_hint_in_the_product_exists():
    """Hints in errors, readiness checks and dialogs must name commands that exist."""
    bad = [(path.name, text) for path in sorted(SRC.glob("*.py")) for text, words in named_commands(path.read_text())
           if not resolves(words)]
    assert bad == []


def leaf(words):
    """The command that `words` name (None if a word is unknown) and the words after it."""
    cmd, rest = root(), list(words)
    while isinstance(cmd, TyperGroup) and rest and not rest[0].startswith("-"):
        cmd = cmd.commands.get(rest.pop(0))
        if cmd is None:
            return None, rest
    return cmd, rest


def unknown_options(words):
    """Options in `words` that their command does not have (`--opt`, `[--opt X]`, `--opt=V`)."""
    cmd, rest = leaf(words)
    if cmd is None or isinstance(cmd, TyperGroup):
        return []
    known = {o for p in cmd.params for o in (*p.opts, *p.secondary_opts)} | {"--help"}
    bad = []
    for word in rest:
        if word == "--" or word.startswith("#"):  # exec's command, or a comment in a code block
            break
        bad += [o for o in re.findall(r"(?<![\w-])--[a-z][a-z-]*", word) if o not in known]
    return bad


def user_documents():
    return [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]


def test_every_command_in_the_user_documents_exists():
    """README.md and every guide in docs/: command paths and their options."""
    bad = []
    for path in user_documents():
        text = path.read_text()
        named = [(full, words) for full, words in named_commands(text)]
        # Backticked forms without the program name: `backup create NAME`, `disk cleanup --yes` ...
        for code in re.findall(r"`([a-z][a-z-]*(?: [^`]*)?)`", text):
            words = code.split()
            if words[0] not in root().commands or words[1:2] == ["..."]:
                continue
            if words[0] == "opencode" and words[1:2] in (["mcp"], ["upgrade"]):
                continue  # OpenCode's own commands inside the container
            alternatives = words[1].split("|") if len(words) > 1 else [None]
            named += [(code, [words[0], *([a] if a else []), *words[2:]]) for a in alternatives]
        for full, words in named:
            if not resolves(words):
                bad.append((path.name, full))
            elif unknown_options(words):
                bad.append((path.name, full, unknown_options(words)))
    assert bad == []


def test_the_document_check_finds_unknown_commands_and_options():
    assert not resolves(["backup", "nonsense"]) and resolves(["backup", "create", "NAME"])
    assert unknown_options(["backup", "create", "NAME", "--stop", "[--no-system]"]) == []
    assert unknown_options(["backup", "create", "NAME", "--force"]) == ["--force"]
    assert unknown_options(["exec", "NAME", "--", "ls", "--all"]) == []
    assert unknown_options(["disk", "cleanup", "#", "--not-an-option"]) == []


def test_create_defaults_and_shared_kind_rules(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "a.txt").write_text("x")
    result = runner.invoke(app, ["create", "ocs-qa-plain", "--no-integrations"])
    assert result.exit_code == 0, result.output
    assert c.resolve("ocs-qa-plain")["kind"] == "scratch"
    assert "Workspace: managed, started empty" in result.output and "Next: opencode-sandbox run ocs-qa-plain" in result.output
    assert "Distribution: Debian (OS version not inspected)" in result.output and "Integrations (set up once at the first start): none" in result.output
    result = runner.invoke(app, ["create", "ocs-qa-copy", "--source", str(project), "--no-integrations"])
    assert result.exit_code == 0, result.output
    assert c.resolve("ocs-qa-copy")["kind"] == "project"
    assert f"managed copy of {project}" in result.output
    # The dashboard form's rule holds for the CLI too.
    result = runner.invoke(app, ["create", "ocs-qa-bad", "--kind", "scratch", "--source", str(project)])
    assert result.exit_code != 0 and c.all_envs() and "ocs-qa-bad" not in {m["name"] for m in c.all_envs()}
    for kwargs, message in (({"kind": "scratch", "source": project}, "starts empty"),
                            ({"kind": "nope"}, "scratch, project or quick"),
                            ({"workspace_mode": "direct"}, "needs a host folder"),
                            ({"workspace_mode": "direct", "workspace": project, "kind": "quick"}, "disposable"),
                            ({"distro": "nope"}, "nope"), ({"image": "bad image"}, "Invalid image")):
        try:
            c.creation_options("ocs-qa-x", **kwargs)
        except c.SandboxError as exc:
            assert message in str(exc), (kwargs, exc)
        else:
            raise AssertionError(kwargs)
    assert c.creation_options("x", workspace_mode="direct", workspace=project) == ("project", "debian")
    assert c.creation_options("x", image="example.org/a:1") == ("scratch", None)
    assert c.create("ocs-qa-api", provisioning=ig.request([]))["kind"] == "scratch"


def test_every_command_has_help_text():
    """`opencode status` and `opencode check` were listed without a description."""
    missing = []
    stack = [([], root())]
    while stack:
        path, cmd = stack.pop()
        if isinstance(cmd, TyperGroup):
            stack += [([*path, n], x) for n, x in cmd.commands.items()]
        if path and not (cmd.help or cmd.short_help):
            missing.append(" ".join(path))
    assert missing == []


def test_every_option_has_help_text():
    """Options without help appeared as bare `--yes`, `--version`, `--destination` in --help."""
    missing = []
    stack = [([], root())]
    while stack:
        path, cmd = stack.pop()
        if isinstance(cmd, TyperGroup):
            stack += [([*path, n], x) for n, x in cmd.commands.items()]
            continue
        missing += [(" ".join(path), p.opts[0]) for p in cmd.params
                    if getattr(p, "param_type_name", "") == "option" and p.name != "help" and not p.help]
    assert missing == []
