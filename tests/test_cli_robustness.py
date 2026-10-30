"""CLI robustness: crashes, metadata robustness, profile checks."""
import os
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import core as c
from opencode_sandbox.cli import app

runner = CliRunner()


def test_every_command_help_renders():
    group = __import__("typer").main.get_command(app)
    def walk(cmd, path):
        yield path
        if getattr(cmd, "commands", None):
            for name, sub in cmd.commands.items():
                yield from walk(sub, path + [name])
    paths = list(walk(group, []))
    assert len(paths) > 40
    for path in paths:
        result = runner.invoke(app, path + ["--help"])
        assert result.exit_code == 0, (path, result.output)


def test_runtime_recover_without_pending_operation_is_clean_error(monkeypatch):
    m = c.create("ocs-qa-rr", "scratch")
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    result = runner.invoke(app, ["config", "recover", m["id"]])
    assert isinstance(result.exception, c.SandboxError)
    assert "No interrupted configuration change" in str(result.exception)


@pytest.mark.parametrize("content", ["[]", '{"id":"0000000000000000"}', "not json",
                                     '{"id":"ffffffffffffffff","name":"spoof","kind":"scratch"}'])
def test_invalid_metadata_is_ignored_and_reported(content):
    good = c.create("ocs-qa-good", "scratch")
    bad = c.BASE / "environments" / "0000000000000000"
    bad.mkdir(parents=True)
    (bad / "metadata.json").write_text(content)
    assert [m["id"] for m in c.all_envs()] == [good["id"]]
    assert c.invalid_metadata() == [bad / "metadata.json"]
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0 and "ocs-qa-good" in result.output
    assert (bad / "metadata.json").read_text() == content  # never modified


def test_config_apply_preserves_omitted_settings(monkeypatch):
    m = c.create("ocs-qa-rc", "scratch")
    custom = {"cpus": "2", "memory": "4g", "pids": 512, "network": "none", "ports": []}
    m["runtime"] = custom
    c.save(m)
    from opencode_sandbox import config_plan as cp
    seen = []
    real = cp.apply
    monkeypatch.setattr(cp, "apply", lambda m, changes, confirmed=None: seen.append(changes) or real(m, changes, confirmed=confirmed))
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "image_definition", lambda m, container=False: None)  # guidance refresh
    result = runner.invoke(app, ["config", "apply", m["id"], "--pids", "1024", "--yes"])
    assert result.exit_code == 0, result.output
    assert seen == [{"pids": 1024}]  # only the change; merged with current values
    assert c.runtime_settings(c.resolve(m["id"])) == {**c.validate_runtime_settings(custom), "pids": 1024}


def _start_until_run(monkeypatch, m):
    """Run start() with fake Docker; return the docker run argv or raise."""
    calls = []
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "ensure_volume", lambda m: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    c.start(m)
    return next(a for a in calls if a[0] == "run")


def test_start_refuses_legacy_env_profile(monkeypatch):
    m = c.create("ocs-qa-legacy", "scratch")
    (c.CONFIG / "profiles" / "default.env").write_text("export K=$(id)\n")
    with pytest.raises(c.SandboxError, match="Legacy"):
        _start_until_run(monkeypatch, m)
    assert c.resolve(m["id"])["status"] == "error"


def test_start_refuses_world_readable_or_symlinked_profile(monkeypatch, tmp_path):
    m = c.create("ocs-qa-perm", "scratch")
    c.profile_set("default", {"OPENAI_API_KEY": "dummy"})
    p = c.profile_path("default")
    os.chmod(p, 0o644)
    with pytest.raises(c.SandboxError, match="0600"):
        _start_until_run(monkeypatch, m)
    p.unlink()
    (tmp_path / "elsewhere").write_text("{}")
    p.symlink_to(tmp_path / "elsewhere")
    m2 = c.create("ocs-qa-perm2", "scratch")
    with pytest.raises(c.SandboxError, match="Unsafe profile"):
        _start_until_run(monkeypatch, m2)


def test_start_mounts_valid_profile_read_only(monkeypatch):
    m = c.create("ocs-qa-ok", "scratch")
    c.profile_set("default", {"OPENAI_API_KEY": "dummy"})
    argv = _start_until_run(monkeypatch, m)
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "--mount"]
    assert any(x.endswith("dst=/run/secrets/ocs-provider.json,readonly") for x in mounts)
    assert "dummy" not in " ".join(argv)


def test_exec_opencode_warns_that_managed_context_is_not_applied(monkeypatch):
    """G07: generic exec of opencode gets neither provider profile nor Agent Context."""
    c.create("ocs-qa-g07", "scratch")
    monkeypatch.setattr(c, "exec_cmd", lambda m, cmd: 0)
    result = runner.invoke(app, ["exec", "ocs-qa-g07", "--", "opencode", "run", "x"])
    assert result.exit_code == 0 and "use 'opencode-sandbox run ocs-qa-g07'" in result.output
    result = runner.invoke(app, ["exec", "ocs-qa-g07", "--", "ls"])
    assert "Agent Context" not in result.output
    help_text = runner.invoke(app, ["exec", "--help"], terminal_width=200).output
    assert "[args]" in help_text and "NOT applied" in help_text


def test_quick_without_terminal_creates_nothing(monkeypatch):
    """Each non-interactive 'quick' left a preserved quick environment behind."""
    monkeypatch.setattr(c, "_tty", lambda: False)
    result = runner.invoke(app, ["quick"])
    assert result.exit_code != 0 and c.all_envs() == []


def test_sigterm_runs_cleanup_and_kills_child(tmp_path):
    """SIGTERM skipped except/finally cleanup; the docker child kept running."""
    import os
    import signal
    import subprocess
    import sys
    import textwrap
    import time
    marker, tag = tmp_path / "cleaned", f"61.{os.getpid()}"
    script = textwrap.dedent(f"""
        import subprocess, sys
        from opencode_sandbox import cli
        def work():
            try:
                subprocess.run(["sleep", {tag!r}])  # like core.docker(): subprocess.run
            except BaseException:
                open({str(marker)!r}, "w").write("cleanup ran"); raise
        cli.app.command("qa-work")(work)
        sys.argv = ["opencode-sandbox", "qa-work"]
        cli.main()
    """)
    running = lambda: subprocess.run(["pgrep", "-f", "sleep " + tag], capture_output=True, check=False).returncode == 0
    proc = subprocess.Popen([sys.executable, "-c", script], env={**os.environ, "HOME": str(tmp_path)})
    for _ in range(200):
        if running(): break
        time.sleep(0.05)
    assert running()
    proc.send_signal(signal.SIGTERM)
    try:
        assert proc.wait(timeout=10) == 128 + signal.SIGTERM
        assert marker.read_text() == "cleanup ran"
        time.sleep(0.2)
        assert not running()
    finally:
        subprocess.run(["pkill", "-f", "sleep " + tag], check=False)


def test_import_failure_is_summarized_and_rolled_back(tmp_path, monkeypatch):
    """I01: ENOSPC during a non-Git import printed shutil.Error's raw list of tuples."""
    import errno
    import shutil
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    for i in range(3):
        (src / "sub" / f"f{i}").write_text("x")
    def full(s, d, *a, **k):
        raise OSError(errno.ENOSPC, "No space left on device", str(d))
    monkeypatch.setattr(shutil, "copyfile", full)  # copytree binds copy2 at definition time
    with pytest.raises(c.SandboxError, match=r"Import failed for 3 file\(s\), first: .*No space left on device.*nothing was created"):
        c.create("ocs-qa-full", "project", src)
    assert c.all_envs() == [] and not any((c.BASE / "environments").iterdir())


def test_partial_runtime_updates_do_not_lose_each_other(monkeypatch):
    """Concurrent '--cpus' / '--pids' / '--memory' changes kept only the last one."""
    from opencode_sandbox import config_plan as cp
    m = c.create("ocs-qa-lost", "scratch")
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "image_definition", lambda m, container=False: None)  # guidance refresh
    stale = c.resolve(m["id"])  # every caller read the environment before the others wrote
    for change in ({"cpus": 1}, {"pids": 333}, {"memory": "3g"}):
        cp.apply(stale, change)
    saved = c.runtime_settings(c.resolve(m["id"]))
    assert (saved["cpus"], saved["pids"], saved["memory"]) == ("1.0", 333, "3g")
    result = runner.invoke(app, ["config", "apply", m["id"], "--network", "none"])
    assert result.exit_code == 0, result.output
    saved = c.runtime_settings(c.resolve(m["id"]))
    assert (saved["cpus"], saved["pids"], saved["memory"], saved["network"]) == ("1.0", 333, "3g", "none")


def test_create_refuses_a_profile_that_does_not_exist():
    """A mistyped --profile created the environment, and its container then had no credentials."""
    result = runner.invoke(app, ["create", "ocs-qa-prof", "--profile", "nosuch", "--no-integrations"])
    assert result.exit_code != 0 and "opencode-sandbox providers set nosuch" in str(result.exception)
    assert "ocs-qa-prof" not in {m["name"] for m in c.all_envs()}
    # The default profile may be absent (an environment without credentials), as for config apply.
    assert runner.invoke(app, ["create", "ocs-qa-prof", "--no-integrations"]).exit_code == 0
    c.CONFIG.joinpath("profiles").mkdir(parents=True, exist_ok=True)
    c.CONFIG.joinpath("profiles", "work.json").write_text("{}")
    c.CONFIG.joinpath("profiles", "work.json").chmod(0o600)
    assert runner.invoke(app, ["create", "ocs-qa-prof2", "--profile", "work", "--no-integrations"]).exit_code == 0
