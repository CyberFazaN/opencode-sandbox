"""D-009: initial integrations are provisioned once (mocked Docker; the in-container
script runs for real against a fake `opencode`; real runs in tests/integration)."""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import agent_context as ac
from opencode_sandbox import backup as b
from opencode_sandbox import core as c
from opencode_sandbox import integrations as ig
from opencode_sandbox.cli import app

runner = CliRunner()
CONTEXT7 = {"type": "remote", "url": "https://mcp.context7.com/mcp"}


class FakeDocker:
    """A container that exists after `run`; `exec` of the provisioning script answers `answer`."""

    def __init__(self, monkeypatch, answer=None, returncode=0):
        self.calls, self.exists, self.running = [], False, False
        self.answer = {"status": "configured", "detail": "", "servers": {"context7": "configured"}} if answer is None else answer
        self.returncode = returncode
        monkeypatch.setattr(c, "ensure_runtime", lambda distro=None: None)
        monkeypatch.setattr(c, "ensure_volume", lambda m: None)
        monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
        monkeypatch.setattr(c, "mounted_profile", lambda m: "")
        monkeypatch.setattr(c, "observed_runtime", lambda m: None)
        monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": self.running, "Status": "x"} if self.exists else None)
        monkeypatch.setattr(c, "docker", self)

    def __call__(self, *args, capture=False, check=True):
        self.calls.append(args)
        if args[0] == "run":
            self.exists = self.running = True
        elif args[0] == "start":
            self.running = True
        elif args[0] == "exec":
            out = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
            return SimpleNamespace(returncode=self.returncode, stdout=out + "\n", stderr="boom" if self.returncode else "")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def execs(self):
        return [a for a in self.calls if a[0] == "exec"]


def test_request_defaults_opt_out_and_custom():
    assert ig.request() == {"requested": ["context7"], "definitions": {"context7": CONTEXT7}, "state": "pending",
                            "result": None, "at": None}
    none = ig.request([])
    assert none["requested"] == [] and none["state"] == "done" and none["result"] == "none requested"
    custom = ig.request([], ig.parse_custom(["docs=https://example.invalid/mcp"], ["fs=npx -y @scope/server --root '/a b'"]))
    assert custom["definitions"] == {"docs": {"type": "remote", "url": "https://example.invalid/mcp"},
                                     "fs": {"type": "local", "command": ["npx", "-y", "@scope/server", "--root", "/a b"]}}
    assert ig.request(None, {"docs": {"type": "remote", "url": "http://x.invalid/m"}})["requested"] == ["context7", "docs"]
    for names, custom, match in ((["nope"], None, "Unknown integration 'nope'"),
                                 (None, {"context7": CONTEXT7}, "defined twice"),
                                 ([], {"bad name": CONTEXT7}, "Invalid integration name"),
                                 ([], {"x": {"type": "remote", "url": "https://user:pw@host/mcp"}}, "without credentials"),
                                 ([], {"x": {"type": "remote", "url": "ftp://host"}}, "Invalid MCP URL"),
                                 ([], {"x": {"type": "remote", "url": "https://h/m", "headers": {}}}, "Invalid MCP definition"),
                                 ([], {"x": {"type": "local", "command": []}}, "Invalid MCP command")):
        with pytest.raises(c.SandboxError, match=match):
            ig.request(names, custom)
    with pytest.raises(c.SandboxError, match="NAME=VALUE"):
        ig.parse_custom(["noequals"])


def test_create_records_the_request(monkeypatch):
    m = c.create("ocs-qa-int", "scratch")
    assert m["provisioning"]["requested"] == ["context7"] and m["provisioning"]["state"] == "pending"
    text = ac.render(m, **c.guidance_inputs(m, observe=False))
    assert "Requested at creation, set up once at the first container start (not done yet): context7." in text


def test_first_start_provisions_once_and_never_again(monkeypatch):
    fake = FakeDocker(monkeypatch)
    m = c.create("ocs-qa-once", "scratch")
    assert c.start(m) == "configured in the global OpenCode config: context7"
    (call,) = fake.execs()
    assert call[:4] == ("exec", "--workdir", "/root", c.cname(m)) and call[4:6] == ("python3", "-c")
    assert call[6] == ig.SCRIPT and json.loads(call[7]) == {"context7": CONTEXT7}
    m = c.resolve(m["id"])
    assert m["provisioning"]["state"] == "done" and m["provisioning"]["at"]
    assert "Provisioned once, at the first container start: context7 (configured in the global OpenCode config: context7)." \
        in ac.path(m, c.env_dir).read_text()
    fake.running = False
    for _ in range(2):  # later starts, a recreation's start: nothing is applied again
        assert c.start(c.resolve(m["id"])) is None
        fake.running = False
    fake.exists = False
    assert c.start(c.resolve(m["id"])) is None  # new container (recreate / config apply)
    assert len(fake.execs()) == 1


def test_opt_out_never_execs(monkeypatch):
    fake = FakeDocker(monkeypatch)
    m = c.create("ocs-qa-none", "scratch", provisioning=ig.request([]))
    assert c.start(m) is None and fake.execs() == []
    assert "Initial integrations" not in ac.path(m, c.env_dir).read_text()


@pytest.mark.parametrize("answer,returncode,expected", [
    ({"status": "failed", "detail": "", "servers": {"context7": "exit 1: nope"}}, 0, "failed, not retried: context7 (exit 1: nope)"),
    ({"status": "skipped", "detail": "an OpenCode global configuration already existed (opencode.json); not changed", "servers": {}}, 0,
     "skipped: an OpenCode global configuration already existed (opencode.json); not changed"),
    ("", 127, "failed, not retried: provisioning in the container exited 127: boom"),
    ("not json", 0, "failed, not retried: provisioning in the container exited 0"),
])
def test_failures_are_recorded_not_retried_and_do_not_fail_start(monkeypatch, answer, returncode, expected):
    fake = FakeDocker(monkeypatch, answer, returncode)
    m = c.create("ocs-qa-fail", "scratch")
    assert c.start(m).startswith(expected)
    m = c.resolve(m["id"])
    assert m["status"] == "running" and m["provisioning"]["state"] == "done"
    fake.running = False
    c.start(m)
    assert len(fake.execs()) == 1


def test_network_none_is_configured_but_cannot_work(monkeypatch):
    FakeDocker(monkeypatch)
    m = c.create("ocs-qa-off", "scratch")
    m["runtime"]["network"] = "none"
    c.save(m)
    assert c.start(m) == ("configured in the global OpenCode config: context7; "
                          "cannot work offline (network none): context7")


def test_interrupted_provisioning_is_recorded_not_retried(monkeypatch):
    fake = FakeDocker(monkeypatch)
    m = c.create("ocs-qa-crash", "scratch")
    m["provisioning"]["state"] = "applying"  # the manager died during the exec
    c.save(m)
    assert "interrupted during the first start; unknown whether written; not retried" in c.start(m)
    assert fake.execs() == []


def _script(tmp_path, defs, *, fail=False, existing=None):
    home, bin_ = tmp_path / "home", tmp_path / "bin"
    home.mkdir(); bin_.mkdir()
    log = tmp_path / "calls"
    (bin_ / "opencode").write_text(f"#!/bin/sh\necho \"$*\" >> {log}\n" + ("echo bad >&2; exit 3\n" if fail else ""))
    (bin_ / "opencode").chmod(0o755)
    if existing:
        (home / ".config" / "opencode").mkdir(parents=True)
        (home / ".config" / "opencode" / existing).write_text("{}")
    p = subprocess.run([sys.executable, "-c", ig.SCRIPT, json.dumps(defs)], capture_output=True, text=True, check=False,
                       env={**os.environ, "HOME": str(home), "PATH": f"{bin_}:{os.environ['PATH']}"})
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout), (log.read_text().splitlines() if log.exists() else [])


def test_container_script_uses_opencode_mcp_add(tmp_path):
    defs = {"context7": CONTEXT7, "fs": {"type": "local", "command": ["npx", "-y", "srv"]}}
    outcome, calls = _script(tmp_path, defs)
    assert outcome == {"status": "configured", "detail": "", "servers": {"context7": "configured", "fs": "configured"}}
    assert calls == ["mcp add --global context7 --url https://mcp.context7.com/mcp", "mcp add --global fs -- npx -y srv"]


def test_container_script_leaves_an_existing_config_alone(tmp_path):
    outcome, calls = _script(tmp_path, {"context7": CONTEXT7}, existing="opencode.jsonc")
    assert outcome["status"] == "skipped" and "opencode.jsonc" in outcome["detail"] and calls == []


def test_container_script_reports_failures(tmp_path):
    outcome, _ = _script(tmp_path, {"context7": CONTEXT7}, fail=True)
    assert outcome == {"status": "failed", "detail": "", "servers": {"context7": "exit 3: bad"}}


def test_backup_carries_the_request_and_restore_never_reapplies(monkeypatch, tmp_path):
    fake = FakeDocker(monkeypatch)
    m = c.create("ocs-qa-bk", "scratch")
    c.start(m)
    m = c.resolve(m["id"])
    fake.exists = False  # cold backup without container (keeps the mock small)
    monkeypatch.setattr(c, "volume_state", lambda m: None)
    path = b.backup(m, tmp_path / "bk")
    assert b.verify(path)["environment"]["provisioning"]["requested"] == ["context7"]
    monkeypatch.setattr(b, "_check_restore_space", lambda *a: None)
    restored = b.restore(path, "ocs-qa-restored")
    assert restored["provisioning"]["state"] == "done" and restored["provisioning"]["result"] == m["provisioning"]["result"]
    assert restored["provisioning"]["definitions"] == {"context7": CONTEXT7}
    before = len(fake.execs())
    c.start(c.resolve(restored["id"]))
    assert len(fake.execs()) == before


def test_history_of_a_backup_made_before_the_first_start():
    h = ig.as_history(ig.request())
    assert h["state"] == "done" and "made before the first start" in h["result"]
    assert ig.as_history("garbage") == {"requested": [], "definitions": {}, "state": "done", "result": "none recorded", "at": None}
    bad = ig.as_history({"requested": ["x"], "definitions": {"x": {"type": "remote", "url": "bad"}}, "state": "done", "at": 5})
    assert bad["definitions"] == {} and bad["at"] is None


def test_hint():
    m = {"provisioning": ig.request(None, {"fs": {"type": "local", "command": ["npx", "a b"]}})}
    assert ig.hint(m) == ["opencode mcp add --global context7 --url https://mcp.context7.com/mcp",
                          "opencode mcp add --global fs -- npx 'a b'"]


def test_cli_options_and_status(monkeypatch):
    result = runner.invoke(app, ["create", "ocs-qa-a", "--kind", "scratch"])
    assert result.exit_code == 0 and "Integrations (set up once at the first start): context7" in result.output
    result = runner.invoke(app, ["create", "ocs-qa-b", "--kind", "scratch", "--no-integrations"])
    assert result.exit_code == 0 and "Integrations (set up once at the first start): none" in result.output
    assert c.resolve("ocs-qa-b")["provisioning"]["requested"] == []
    result = runner.invoke(app, ["create", "ocs-qa-c", "--kind", "scratch", "--no-integrations",
                                 "--mcp-remote", "docs=https://example.invalid/mcp", "--mcp-local", "fs=npx -y srv"])
    assert result.exit_code == 0 and c.resolve("ocs-qa-c")["provisioning"]["requested"] == ["docs", "fs"]
    result = runner.invoke(app, ["create", "ocs-qa-d", "--integration", "context7", "--no-integrations"])
    assert result.exit_code != 0 and c.all_envs() and "ocs-qa-d" not in [e["name"] for e in c.all_envs()]
    result = runner.invoke(app, ["create", "ocs-qa-e", "--integration", "nope"])
    assert "Unknown integration" in str(result.exception)
    monkeypatch.setattr(c, "ensure_runtime", lambda distro=None: None)
    monkeypatch.setattr(c, "running", lambda m: False)
    monkeypatch.setattr(c, "profile_mismatch", lambda m: None)
    result = runner.invoke(app, ["status", "ocs-qa-a"])
    assert "Initial integrations (history, not current state): context7: pending (first start)" in result.output
    m = c.resolve("ocs-qa-a")
    m["provisioning"].update(state="done", result="failed, not retried: x")
    c.save(m)
    result = runner.invoke(app, ["status", "ocs-qa-a"])
    assert "To add them yourself" in result.output and "opencode mcp add --global context7 --url https://mcp.context7.com/mcp" in result.output


def test_tui_checkbox_opts_out(monkeypatch):
    from test_tui import run, settle

    async def t(app, pilot):
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#name").value = "ocs-qa-tui-int"
        app.screen.query_one("#integration-context7").value = False
        app.screen.query_one("#create").press()
        await settle(pilot, 1.0)
        assert c.resolve("ocs-qa-tui-int")["provisioning"]["requested"] == []
    run(t)
