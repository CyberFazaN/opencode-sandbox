"""D-010: one planner and one executor for manager-owned settings (mocked Docker; the
categories themselves were measured with rootless Docker, see tests/integration)."""
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import agent_context as ac
from opencode_sandbox import config_plan as cp
from opencode_sandbox import core as c
from opencode_sandbox.cli import app

runner = CliRunner()


class FakeContainer:
    """Just enough Docker for the executor: inspect, stop, start, update."""

    def __init__(self, monkeypatch, state="running", fail=None):
        self.state, self.calls, self.fail = state, [], fail
        monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
        monkeypatch.setattr(c, "inspect_container", self.inspect)
        monkeypatch.setattr(c, "observed_runtime", lambda m: None)
        monkeypatch.setattr(c, "image_definition", lambda m, **k: None)  # executor fixture: provenance uninspected
        monkeypatch.setattr(c, "docker", self.docker)

    def inspect(self, m):
        return None if self.state == "missing" else {"Running": self.state == "running", "Status": self.state}

    def docker(self, *args, **kwargs):
        self.calls.append(args)
        if self.fail and args[0] == self.fail:
            raise c.SandboxError(f"Command failed (1): docker {args[0]}")
        if args[0] == "stop":
            self.state = "stopped"
        elif args[0] == "start":
            self.state = "running"
        return SimpleNamespace(returncode=0, stdout="", stderr="")


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(c, "host_cpus", lambda: 8)
    m = c.create("ocs-qa-plan", "scratch")
    m["runtime"] = c.validate_runtime_settings({"cpus": "2", "memory": "4g", "pids": 500, "network": "bridge"})
    c.save(m)
    return c.resolve(m["id"])


def categories(p):
    return {ch.field: ch.category for ch in p.changes}


@pytest.mark.parametrize("state,expected", [
    ("missing", {"cpus": "saved", "memory": "saved", "pids": "saved", "network": "saved", "ports": "saved"}),
    ("stopped", {"cpus": "dynamic", "memory": "dynamic", "pids": "dynamic", "network": "recreate", "ports": "recreate"}),
    ("running", {"cpus": "dynamic", "memory": "restart", "pids": "dynamic", "network": "recreate", "ports": "recreate"}),
])
def test_categories(monkeypatch, env, state, expected):
    FakeContainer(monkeypatch, state)
    p = cp.plan(env, {"cpus": 3, "memory": "2g", "pids": 300, "network": "bridge",
                      "ports": [{"host": 18080, "container": 8080, "protocol": "tcp"}]})
    p2 = cp.plan(env, {"network": "none"})
    assert categories(p) == {k: v for k, v in expected.items() if k != "network"}
    assert categories(p2) == {"network": expected["network"]}
    assert p.category == ("saved" if state == "missing" else "recreate")


def test_memory_increase_on_a_running_container_is_dynamic(monkeypatch, env):
    FakeContainer(monkeypatch, "running")
    assert cp.plan(env, {"memory": "8g"}).category == "dynamic"
    assert cp.plan(env, {"memory": "4096m"}).changes[0].category == "dynamic"  # same bytes, other spelling
    p = cp.plan(env, {"memory": "3g", "cpus": 4})
    assert p.category == "restart" and categories(p) == {"cpus": "dynamic", "memory": "restart"}
    assert "Stop the container." in p.steps and "running OpenCode sessions and shells in it end" in " ".join(p.warnings)


def test_profile_assignment_recreates_and_must_exist(monkeypatch, env):
    FakeContainer(monkeypatch, "stopped")
    with pytest.raises(c.SandboxError, match="Provider profile 'work' not found"):
        cp.plan(env, {"profile": "work"})
    c.profile_set("work", {"QA_KEY": "dummy"})
    p = cp.plan(env, {"profile": "work"})
    assert categories(p) == {"profile": "recreate"} and p.target["profile"] == "work"
    assert not any("sessions" in w for w in p.warnings)  # stopped: nothing ends
    assert cp.plan(env, {"profile": "default"}).changes == ()


def test_no_changes_and_unknown_fields(monkeypatch, env):
    FakeContainer(monkeypatch, "running")
    p = cp.plan(env, {"cpus": "2", "memory": "4g"})
    assert p.category == "none" and p.steps == () and "No changes." in cp.describe(p)
    assert cp.apply(env, {"cpus": 2}) == {"category": "none", "applied": False}
    with pytest.raises(c.SandboxError, match="Unknown setting: image"):
        cp.plan(env, {"image": "x"})


def test_blockers(monkeypatch, env):
    FakeContainer(monkeypatch, "stopped")
    assert "exceeds the 8 CPUs" in cp.plan(env, {"cpus": 16}).blockers[0]
    other = c.create("ocs-qa-other", "scratch")
    other["runtime"]["ports"] = [{"host": 18080, "container": 80, "protocol": "tcp"}]
    c.save(other)
    p = cp.plan(env, {"ports": cp.parse_ports(["18080:8080"])})
    assert p.blockers == ("Port conflict: 18080/tcp reserved by ocs-qa-other",)
    with pytest.raises(c.SandboxError, match="Port conflict"):
        cp.apply(env, {"ports": cp.parse_ports(["18080:8080"])})
    c.mark(env, "error", operation="restore")
    assert "pending operation (restore)" in cp.plan(env, {"cpus": 3}).blockers[0]


def test_describe_lists_changes_steps_and_warnings(monkeypatch, env):
    FakeContainer(monkeypatch, "running")
    text = cp.describe(cp.plan(env, {"network": "none", "pids": 100}))
    assert "network: bridge -> none  [recreate: fixed when Docker creates the container]" in text
    assert "process limit: 500 -> 100  [dynamic: docker update]" in text
    assert "Impact: recreate" in text and "1. Stop the container." in text and "Commit its system layer" in text
    assert "Start the new container." in text and "Regenerate the Agent Context." in text
    assert "no internet or LAN" in text and "new ones fail" in text


def test_apply_saved_writes_metadata_only(monkeypatch, env):
    fake = FakeContainer(monkeypatch, "missing")
    c.profile_set("work", {"QA_KEY": "dummy"})
    assert cp.apply(env, {"cpus": 3, "profile": "work"})["category"] == "saved"
    m = c.resolve(env["id"])
    assert c.runtime_settings(m)["cpus"] == "3.0" and m["profile"] == "work" and fake.calls == []
    assert ac.verify(m, c.env_dir, **c.guidance_inputs(m, observe=False))


def test_apply_dynamic_updates_in_place(monkeypatch, env):
    fake = FakeContainer(monkeypatch, "running")
    assert cp.apply(env, {"cpus": 1.5, "memory": "8g", "pids": 900})["category"] == "dynamic"
    assert fake.calls == [("update", "--cpus", "1.5", "--memory", "8g", "--memory-swap", str(16 * 2**30),
                           "--pids-limit", "900", c.cname(env))]
    m = c.resolve(env["id"])
    assert (c.runtime_settings(m)["cpus"], c.runtime_settings(m)["memory"], c.runtime_settings(m)["pids"]) == ("1.5", "8g", 900)
    assert m.get("operation") is None and "pending_config" not in m and m["status"] == "running"
    assert "CPU limit: 1.5" in ac.path(m, c.env_dir).read_text()


def test_apply_restart_stops_updates_starts(monkeypatch, env):
    fake = FakeContainer(monkeypatch, "running")
    assert cp.apply(env, {"memory": "1g"})["category"] == "restart"
    assert [a[0] for a in fake.calls] == ["stop", "update", "start"] and fake.state == "running"
    assert c.runtime_settings(c.resolve(env["id"]))["memory"] == "1g"


def test_apply_recreate_uses_the_journalled_recreation(monkeypatch, env):
    FakeContainer(monkeypatch, "running")
    c.profile_set("work", {"QA_KEY": "dummy"})
    order = []
    monkeypatch.setattr(c, "stop", lambda m: order.append("stop") or True)  # True: it stopped the container
    monkeypatch.setattr(c, "reconfigure_runtime", lambda m, runtime, profile=None: order.append(("recreate", runtime["network"], profile)))
    monkeypatch.setattr(c, "start", lambda m: order.append("start"))
    assert cp.apply(env, {"network": "none", "profile": "work"})["category"] == "recreate"
    assert order == ["stop", ("recreate", "none", "work"), "start"]


def test_reconfigure_runtime_records_the_profile(monkeypatch, env):
    fake = FakeContainer(monkeypatch, "stopped")
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    monkeypatch.setattr(c, "require_docker_space", lambda what: None)
    result = c.reconfigure_runtime(env, {**c.runtime_settings(env), "network": "none"}, profile="work")
    m = c.resolve(env["id"])
    assert m["profile"] == "work" and c.runtime_settings(m)["network"] == "none" and m["image"] == result["image"]
    assert [a[0] for a in fake.calls] == ["commit", "rm"] and m.get("operation") is None


def test_confirmed_plan_must_still_hold(monkeypatch, env):
    fake = FakeContainer(monkeypatch, "stopped")
    shown = cp.plan(env, {"memory": "2g"})
    fake.state = "running"  # started in another terminal after the plan was shown
    with pytest.raises(c.SandboxError, match="changed since the plan was shown"):
        cp.apply(env, {"memory": "2g"}, confirmed=shown)
    assert fake.calls == []


def test_interrupted_update_is_journalled_and_recoverable(monkeypatch, env):
    fake = FakeContainer(monkeypatch, "running", fail="update")
    with pytest.raises(c.SandboxError, match="docker update"):
        cp.apply(env, {"memory": "1g"})
    m = c.resolve(env["id"])
    assert m["operation"] == "config-update" and m["status"] == "error" and "Configuration change" in m["last_error"]
    assert m["pending_config"] == {"runtime": {**c.runtime_settings(env), "memory": "1g"}, "restart": True, "start": True}
    assert c.runtime_settings(m)["memory"] == "4g"  # metadata says what the container still has
    assert fake.state == "stopped"  # crashed between stop and update
    for blocked in (lambda: c.start(m), lambda: c.repair(m), lambda: cp.apply(m, {"cpus": 1})):
        with pytest.raises(c.SandboxError, match="config recover|pending operation"):
            blocked()
    fake.fail = None
    fake.calls.clear()
    result = runner.invoke(app, ["config", "recover", m["name"]])
    assert result.exit_code == 0, result.output
    assert [a[0] for a in fake.calls] == ["update", "start"] and fake.state == "running"
    m = c.resolve(env["id"])
    assert m.get("operation") is None and c.runtime_settings(m)["memory"] == "1g" and m["status"] == "running"


def test_recover_completes_an_interrupted_recreation(monkeypatch, env):
    FakeContainer(monkeypatch, "missing")
    seen = []
    monkeypatch.setattr(c, "recover_runtime_reconfigure", lambda m: seen.append(m["id"]) or {"image": "x", "recovered": True})
    c.mark(env, "reconfiguring", operation="runtime-recreate")
    assert cp.recover(env)["next"] == f"start it with: opencode-sandbox start {env['name']}" and seen == [env["id"]]


def test_parse_ports():
    assert cp.parse_ports(["8080:80", "5353:53/udp"]) == [{"host": 8080, "container": 80, "protocol": "tcp"},
                                                           {"host": 5353, "container": 53, "protocol": "udp"}]
    for bad in ("8080", "a:b", "1:2:3"):
        with pytest.raises(c.SandboxError, match="expected HOST:CONTAINER"):
            cp.parse_ports([bad])


def test_cli_plan_apply_show(monkeypatch, env):
    fake = FakeContainer(monkeypatch, "stopped")
    result = runner.invoke(app, ["config", "plan", env["name"], "--network", "none", "--json"])
    assert result.exit_code == 0 and '"category": "recreate"' in result.output
    result = runner.invoke(app, ["config", "plan", env["name"], "--cpus", "64"])
    assert result.exit_code == 1 and "Blocked: CPU limit 64" in result.output
    monkeypatch.setattr(c, "_tty", lambda: False)
    result = runner.invoke(app, ["config", "apply", env["name"], "--network", "none"])
    assert result.exit_code != 0 and "recreates the container; confirm with --yes" in result.output
    assert fake.calls == []
    result = runner.invoke(app, ["config", "apply", env["name"], "--pids", "700"])  # dynamic: no confirmation needed
    assert result.exit_code == 0 and "Applied (dynamic)." in result.output
    result = runner.invoke(app, ["config", "apply", env["name"], "--publish", "18080:80", "--no-ports"])
    assert result.exit_code != 0
    result = runner.invoke(app, ["config", "show", env["name"]])
    assert result.exit_code == 0 and '"pids": 700' in result.output and '"container": null' in result.output


def test_settings_are_written_only_by_the_executor():
    """Provider assignment (and runtime settings) had two implementations."""
    src = Path(c.__file__).parent
    writers = {}
    for path in sorted(src.glob("*.py")):
        for line in path.read_text().splitlines():
            if re.search(r"""\bm\[["'](profile|runtime)["']\]\s*=(?!=)""", line):
                writers.setdefault(path.name, []).append(line.strip())
    assert set(writers) == {"config_plan.py", "core.py"}, writers
    # core: only reconfigure_runtime, the recreate step of the executor
    assert writers["core.py"] == ["if profile is not None: m[\"profile\"]=profile", 'm["runtime"]=settings; save(m)',
                                  'm["runtime"]=settings'], writers["core.py"]
    for name in ("cli.py", "tui.py", "management_tui.py"):
        text = (src / name).read_text()
        assert "reconfigure_runtime" not in text and "c.save(" not in text, name


def test_recovery_untags_the_superseded_runtime_image(monkeypatch, env):
    """Seen with real Docker: a recreate interrupted before `docker rm` left the previous ocs-runtime image."""
    fake = FakeContainer(monkeypatch, "stopped", fail="rm")
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    monkeypatch.setattr(c, "require_docker_space", lambda what: None)
    old = f"ocs-runtime:{env['id']}-aaaaaaaaaaaa"
    env["image"] = old
    c.save(env)
    with pytest.raises(c.SandboxError):
        c.reconfigure_runtime(env, {**c.runtime_settings(env), "network": "none"})
    m = c.resolve(env["id"])
    assert m["operation"] == "runtime-recreate" and m["superseded_image"] == old and m["image"] != old
    fake.fail = None
    fake.calls.clear()
    monkeypatch.setattr(c, "docker", lambda *a, **k: fake.calls.append(a) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    c.recover_runtime_reconfigure(m)
    assert ("image", "rm", old) in fake.calls
    m = c.resolve(env["id"])
    assert "superseded_image" not in m and m.get("operation") is None
