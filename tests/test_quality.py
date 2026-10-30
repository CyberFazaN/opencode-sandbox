"""Quality gates. Errors the dashboard and batch commands
catch are reported with their type when they are not the manager's own errors; catches that
show nothing are limited to the errors they expect; ruff and shellcheck run clean with the
project configuration (skipped when the tool is not installed)."""
import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from test_tui import run, settle
from typer.testing import CliRunner

from opencode_sandbox import backup as b
from opencode_sandbox import cli
from opencode_sandbox import core as c

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "opencode_sandbox"
SHELL_SCRIPTS = [SRC / "assets/images/arch/pacman-retry",
                 SRC / "assets/images/common/install-opencode.sh", ROOT / ".github/scripts/pipx_smoke.sh"]


def test_error_text_names_unexpected_error_types():
    assert c.error_text(c.SandboxError("Environment 'x': not found")) == "Environment 'x': not found"
    assert c.error_text(KeyError("created")) == "KeyError: 'created'"
    assert c.error_text(RuntimeError()) == "RuntimeError"


def _broad_handlers(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            names = [node.type] if not isinstance(node.type, ast.Tuple) else list(node.type.elts)
            if node.type is None or any(isinstance(n, ast.Name) and n.id in ("Exception", "BaseException") for n in names):
                yield node


@pytest.mark.parametrize("module", sorted(p.name for p in SRC.glob("*tui.py")))
def test_every_broad_catch_in_the_dashboard_reports_the_error(module):
    """A dashboard action or worker may catch every error (the dashboard must keep running), but
    it must show it: through core.error_text, so an unexpected error is named by its type."""
    tree = ast.parse((SRC / module).read_text(encoding="utf-8"))
    offenders = []
    for handler in _broad_handlers(tree):
        used = {n.args[0].id for n in ast.walk(handler) if isinstance(n, ast.Call)
                and getattr(n.func, "attr", getattr(n.func, "id", None)) == "error_text"
                and n.args and isinstance(n.args[0], ast.Name)}
        if handler.name is None or handler.name not in used:
            offenders.append(handler.lineno)
    assert offenders == [], f"{module}: broad except without error_text at lines {offenders}"


def test_dashboard_names_an_unexpected_error_type(monkeypatch):
    def broken():
        raise KeyError("id")
    monkeypatch.setattr(c, "pending_repairs", broken)

    async def t(app, pilot):
        await settle(pilot)
        assert any(n.message == "KeyError: 'id'" for n in app._notifications), [n.message for n in app._notifications]
    run(t)


def test_dashboard_selection_tolerates_a_removed_environment_only(monkeypatch):
    m = c.create("ocs-qa-sel", "scratch")

    async def t(app, pilot):
        await settle(pilot)
        assert app.selected()["id"] == m["id"]
        monkeypatch.setattr(c, "resolve", lambda key: (_ for _ in ()).throw(c.SandboxError("not found")))
        assert app.selected() is None  # guard: removed meanwhile
        monkeypatch.setattr(c, "resolve", lambda key: (_ for _ in ()).throw(TypeError("defect")))
        with pytest.raises(TypeError):
            app.selected()
    run(t)


def test_dashboard_reads_invalid_ui_settings_as_defaults(monkeypatch):
    """Guard: a broken ui.json still lists quick environments (the documented default)."""
    c.create("ocs-qa-quick", "quick")
    c.CONFIG.mkdir(parents=True, exist_ok=True)
    (c.CONFIG / "ui.json").write_text("{broken")

    async def t(app, pilot):
        await settle(pilot)
        assert app.query_one("#envs").row_count == 1
    run(t)


def _backup_dir():
    root = c.BASE / "backups" / "x.ocsbackup"
    root.mkdir(parents=True)
    return root


def test_backup_list_marks_invalid_backups_and_lets_defects_through(monkeypatch):
    _backup_dir()
    monkeypatch.setattr(b, "backup_info", lambda path: (_ for _ in ()).throw(c.SandboxError("Missing manifest")))
    out = CliRunner().invoke(cli.app, ["backup", "list"])
    assert out.exit_code == 0 and "INVALID" in out.output and "Missing manifest" in out.output  # guard
    monkeypatch.setattr(b, "backup_info", lambda path: (_ for _ in ()).throw(TypeError("defect")))
    out = CliRunner().invoke(cli.app, ["backup", "list"])
    assert isinstance(out.exception, TypeError)


def test_repair_all_reports_an_unexpected_error_with_its_type(monkeypatch):
    m = c.create("ocs-qa-rep", "scratch")
    monkeypatch.setattr(c, "pending_repairs", lambda: [m])
    monkeypatch.setattr(c, "repair", lambda env: (_ for _ in ()).throw(KeyError("status")))
    assert c.repair_all() == [(m["id"], None, "KeyError: 'status'")]


def _tool(name, env):
    found = os.environ.get(env) or shutil.which(name)
    if not found:
        local = Path(sys.executable).parent / name
        found = str(local) if local.exists() else None
    if not found:
        pytest.skip(f"{name} not installed (set {env})")
    return found


def test_ruff_reports_nothing_in_sources_and_tests():
    ruff = _tool("ruff", "RUFF")
    p = subprocess.run([ruff, "check", "--no-cache", "--output-format=concise", "src", "tests", ".github/scripts"], cwd=ROOT,
                       capture_output=True, text=True, check=False)
    assert p.returncode == 0, p.stdout + p.stderr


def test_shellcheck_reports_nothing_in_the_shell_scripts():
    shellcheck = _tool("shellcheck", "SHELLCHECK")
    p = subprocess.run([shellcheck, "--format=gcc", *map(str, SHELL_SCRIPTS)], cwd=ROOT,
                       capture_output=True, text=True, check=False)
    assert p.returncode == 0, p.stdout + p.stderr
