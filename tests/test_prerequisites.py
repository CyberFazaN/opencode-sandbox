"""Host prerequisites (D-042): missing programs, an unusable Docker daemon and missing terminals are
reported with the reason, what to do and an exit status of their own, by the CLI and the dashboard;
nothing is installed or configured, and nothing is asked that cannot be carried out."""
import asyncio
import os
import shutil
import sys
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import cli, readiness, tui
from opencode_sandbox import core as c
from opencode_sandbox import runtime_identity as rid
from opencode_sandbox import workspace_io as wio

runner = CliRunner()


def daemon(monkeypatch, classification, reason="reason"):
    monkeypatch.setattr(rid, "verify", lambda context=None, endpoint=None, **k: rid.Identity(
        classification, context or "rootless", None if classification == rid.MISSING else "unix:///x.sock",
        reasons=(reason,)))
    monkeypatch.setattr(c, "_ENDPOINT", None)


def host(monkeypatch, missing=()):
    """Hermetic host: which programs exist, their --version, and a Docker that answers nothing."""
    monkeypatch.setattr(shutil, "which", lambda name: None if name in missing else f"/usr/bin/{name}")
    monkeypatch.setattr(c, "run_program", lambda argv, **k: SimpleNamespace(returncode=0, stdout=f"{argv[0]} version 1\n"))
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="no"))


# --- host programs ------------------------------------------------------------------------------

def test_host_checks_name_each_program_and_what_needs_it(monkeypatch):
    host(monkeypatch, missing=("git",))
    checks = {x.id: x for x in readiness.host_checks()}
    assert checks["python"].status == readiness.PASSED and sys.version.split()[0] in checks["python"].detail
    assert checks["docker"].status == readiness.PASSED and "/usr/bin/docker version 1" in checks["docker"].detail
    git = checks["git"]
    assert git.status == readiness.FAILED and "change review" in git.detail and "pacman -S git" in git.hint


def test_a_missing_program_is_a_prerequisite_error_with_a_hint(tmp_path):
    with pytest.raises(c.PrerequisiteError) as e:
        c.run_program([str(tmp_path / "git"), "--version"])
    assert e.value.exit_code == rid.EXIT_CODES[rid.MISSING] and "Install Git" in str(e.value)
    with pytest.raises(c.PrerequisiteError, match="Required executable not found: docker"):
        c.call([str(tmp_path / "docker"), "version"])


def test_host_git_without_git_is_a_prerequisite_error(monkeypatch, tmp_path):
    repo = tmp_path / "w"
    (repo / ".git" / "objects").mkdir(parents=True)
    (repo / ".git" / "refs").mkdir()
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with pytest.raises(c.PrerequisiteError, match="Install Git"):
        wio.git(repo, "status")


def test_changes_show_of_a_git_workspace_needs_git(monkeypatch, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "base"]):
        c.call(["git", "-C", src, "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args])
    m = c.create("ocs-test-nogit", "project", src)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    result = runner.invoke(cli.app, ["changes", "show", m["name"]])
    assert isinstance(result.exception, c.PrerequisiteError) and "Install Git" in str(result.exception)
    assert isinstance(c.git_changes(m), str)  # the preview before a deletion and in the dashboard does not raise


# --- doctor ------------------------------------------------------------------------------------

def test_doctor_without_a_docker_cli_gives_the_install_hint_once(monkeypatch):
    host(monkeypatch, missing=("docker",))
    daemon(monkeypatch, rid.MISSING)
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == rid.EXIT_CODES[rid.MISSING]
    assert result.output.count("pacman -S docker") == 1 and "See the daemon identity below" in result.output


@pytest.mark.parametrize("classification", [rid.MISSING, rid.NOT_CONFIGURED, rid.UNAVAILABLE, rid.UNSUPPORTED,
                                            rid.MISMATCH, rid.UNVERIFIED_PROXY])
def test_doctor_exits_with_the_classification_and_its_hint(monkeypatch, classification):
    host(monkeypatch)
    daemon(monkeypatch, classification)
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == rid.EXIT_CODES[classification]
    assert f"Daemon identity: {classification}" in result.output and rid.HINTS[classification] in result.output
    assert result.output.index("[passed]") < result.output.index("Daemon identity")  # host programs first


def test_doctor_with_a_verified_daemon_but_no_git_exits_7(monkeypatch):
    host(monkeypatch, missing=("git",))
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == rid.EXIT_CODES[rid.MISSING]
    assert "Daemon identity: verified" in result.output and "[failed]" in result.output


def test_doctor_help_documents_the_exit_status():
    text = runner.invoke(cli.app, ["doctor", "--help"]).output
    assert "Exit status" in " ".join(text.split()) and "8 the Docker context is not configured" in " ".join(text.split())


# --- exit status of operations -----------------------------------------------------------------

@pytest.mark.parametrize("classification", [rid.MISSING, rid.NOT_CONFIGURED, rid.UNAVAILABLE])
def test_an_operation_without_a_usable_daemon_exits_with_its_code(monkeypatch, classification, capsys):
    daemon(monkeypatch, classification)
    monkeypatch.setattr(sys, "argv", ["opencode-sandbox", "build"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == rid.EXIT_CODES[classification]
    err = capsys.readouterr().err
    assert f"Docker daemon identity: {classification}" in err and rid.HINTS[classification] in err


def test_help_and_version_need_no_docker(monkeypatch):
    monkeypatch.setattr(rid, "verify", lambda *a, **k: pytest.fail("no daemon check for --help/--version"))
    assert runner.invoke(cli.app, ["--version"]).exit_code == 0
    assert runner.invoke(cli.app, ["--help"]).exit_code == 0
    assert runner.invoke(cli.app, ["list"]).exit_code == 0


# --- no terminal, and checks before asking --------------------------------------------------------

def test_confirmation_without_a_terminal_names_yes(monkeypatch):
    m = c.create("ocs-test-confirm", "scratch")
    result = runner.invoke(cli.app, ["container", "recreate", m["name"]])
    assert isinstance(result.exception, c.SandboxError) and "No terminal to confirm" in str(result.exception)
    assert "--yes" in str(result.exception)


def test_the_daemon_is_checked_before_a_confirmation(monkeypatch):
    m = c.create("ocs-test-ask", "scratch")
    daemon(monkeypatch, rid.UNAVAILABLE)
    monkeypatch.setattr(c, "_tty", lambda: True)
    monkeypatch.setattr(cli.typer, "confirm", lambda *a, **k: pytest.fail("asked although the daemon is not usable"))
    monkeypatch.setattr(cli.typer, "prompt", lambda *a, **k: pytest.fail("asked although the daemon is not usable"))
    for args in (["container", "recreate", m["name"]], ["delete", m["name"]], ["opencode", "rollback-base"]):
        result = runner.invoke(cli.app, args)
        assert isinstance(result.exception, c.PrerequisiteError), (args, result.output)
        assert result.exception.exit_code == rid.EXIT_CODES[rid.UNAVAILABLE]
    assert c.resolve(m["id"])  # nothing deleted


def test_delete_without_a_terminal_refuses_and_keeps_the_environment():
    m = c.create("ocs-test-keep", "scratch")
    result = runner.invoke(cli.app, ["delete", m["name"]])
    assert "No terminal to confirm the deletion" in str(result.exception) and c.resolve(m["id"])


@pytest.mark.parametrize("args", [["tui"], ["providers", "set", "ocs-test", "--key", "X"]])
def test_terminal_only_commands_refuse_without_a_terminal(args):
    result = runner.invoke(cli.app, args)
    assert isinstance(result.exception, c.SandboxError) and "interactive terminal" in str(result.exception)
    assert not (c.CONFIG / "profiles" / "ocs-test.json").exists()


# --- dashboard ---------------------------------------------------------------------------------

def dashboard(test):
    async def main():
        app = tui.Dashboard()
        async with app.run_test(size=(100, 30)) as pilot:
            for _ in range(20):
                await pilot.pause(); await asyncio.sleep(0.05)
            await test(app, pilot)
    asyncio.run(main())


def test_dashboard_opens_without_docker_and_explains(monkeypatch):
    c.create("ocs-test-dash", "scratch")
    daemon(monkeypatch, rid.MISSING, "the Docker CLI (docker) is not installed or not on PATH")

    async def t(app, pilot):
        notes = [n for n in app._notifications if n.title == "Docker is not ready"]
        assert notes and "not installed" in notes[0].message and "opencode-sandbox doctor" in notes[0].message
        assert "Docker is not ready" in str(app.query_one("#status").render())
        assert app.query_one("#envs").row_count == 1  # the environments are still listed
    dashboard(t)


def test_dashboard_says_nothing_when_docker_is_ready():
    async def t(app, pilot):
        assert not [n for n in app._notifications if n.title == "Docker is not ready"]
        assert "Docker is not ready" not in str(app.query_one("#status").render())
    dashboard(t)


def test_the_scripts_and_the_package_share_one_classification():
    """install.sh/setup-rootless.sh run runtime_identity.py from the tree; the manager imports it."""
    assert c.runtime_identity is rid and os.path.basename(rid.__file__) == "runtime_identity.py"
