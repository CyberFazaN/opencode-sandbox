"""Readiness checks and network transparency (mocked Docker; real runs in tests/integration).

Every check has a passing case and at least one negative case here."""
import json
import os
import re
import socket
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import agent_context as ac
from opencode_sandbox import core as c
from opencode_sandbox import distros
from opencode_sandbox import integrations as ig
from opencode_sandbox import readiness as r
from opencode_sandbox import runtime_identity as rid
from opencode_sandbox.cli import app

runner = CliRunner()
GOOD = {"internet": "verified", "host-loopback": "unreachable", "host-lan": "refused", "lan-gateway": "refused"}
ROOTLESSKIT_FLAGS, HOST_GATEWAY = r.rootlesskit_flags, r.host_gateway
MUTATING = {"run", "start", "stop", "rm", "commit", "create", "kill", "restart", "tag"}


def ok(out=""):
    return SimpleNamespace(returncode=0, stdout=out, stderr="")


def fail(err="error", rc=1):
    return SimpleNamespace(returncode=rc, stdout="", stderr=err)


class FakeDocker:
    def __init__(self, monkeypatch, m):
        self.m, self.calls = m, []
        self.exists, self.running, self.dead = True, True, False
        rt = c.runtime_settings(m)
        self.host = {"NetworkMode": rt["network"], "NanoCpus": int(float(rt["cpus"]) * 1e9),
                     "Memory": c.memory_bytes(rt["memory"]), "PidsLimit": rt["pids"], "PortBindings": {}}
        self.env = ["PATH=/usr/bin", "OPENCODE_DISABLE_AUTOUPDATE=1"]
        self.images = {"opencode-sandbox:debian"}
        self.base_label = "2.2.0"
        self.definition_labels = {distros.LABEL + "managed": "true", **distros.get(distros.DEFAULT).image_labels()}
        self.volume = {"Name": c.volume(m), "Labels": {"org.opencode-sandbox.id": m["id"]}}
        self.owner = m["id"]
        self.probe = lambda spec: dict(GOOD)
        self.probe_rc = 0
        self.system_config = json.dumps({"instructions": [ac.CONTAINER_PATH]})
        self.version = "opencode v2.2.0"
        self.proc_net = ""
        self.inode = None
        self.mounts = []
        monkeypatch.setattr(c, "docker", self)
        monkeypatch.setattr(c, "docker_root", lambda: None)

    def __call__(self, *a, capture=False, check=True):
        self.calls.append(a)
        if a[:2] == ("container", "inspect"):
            if not self.exists:
                return fail("Error: No such container: " + a[-1])
            fmt = a[3]
            if fmt == "{{json .State}}":
                return ok(json.dumps({"Running": self.running, "Dead": self.dead, "Status": "running" if self.running else "exited"}))
            if "org.opencode-sandbox.id" in fmt:
                return ok(self.owner + "\n")
            if fmt == "{{json .HostConfig}}":
                return ok(json.dumps(self.host))
            if fmt == "{{json .Config.Labels}}":
                return ok(json.dumps(self.definition_labels))
            if fmt == "{{json .Mounts}}":
                return ok(json.dumps(self.mounts))
            if fmt == "{{json .}}":
                return ok(json.dumps({"HostConfig": self.host, "Config": {"Env": self.env}, "Mounts": self.mounts}))
        if a[:2] == ("volume", "inspect"):
            return ok(json.dumps([self.volume])) if self.volume else fail("Error: no such volume")
        if a[:2] == ("image", "inspect"):
            if "--format" in a and a[3] == "{{json .Config.Labels}}":
                return ok(json.dumps(self.definition_labels)) if a[-1] in self.images else fail("Error: No such image")
            if "--format" in a and "opencode-version" in a[3]:
                return ok(self.base_label + "\n")
            return ok("[{}]") if a[-1] in self.images else fail("Error: No such image")
        if a[0] == "exec":
            argv = a[2:]
            if argv[:2] == ("python3", "-c"):
                if self.probe_rc:
                    return fail("exec: python3: not found", self.probe_rc)
                result = self.probe(json.loads(argv[3]))
                return ok(result if isinstance(result, str) else json.dumps(result) + "\n")
            if argv[:2] == ("cat", ac.SYSTEM_CONFIG):
                return ok(self.system_config) if self.system_config is not None else fail("No such file", 1)
            if argv[:2] == ("cat", ac.CONTAINER_PATH):  # the mounted Agent Context
                host = ac.path(self.m, c.env_dir)
                return ok(host.read_text()) if host.exists() else fail("No such file", 1)
            if argv[:2] == ("opencode", "--version"):
                return ok(self.version + "\n") if self.version else fail("not found", 127)
            if argv[0] == "sh":
                return ok(self.proc_net)
            if argv[0] == "stat":
                return ok(f"{self.inode}\n") if self.inode is not None else fail("stat: not found", 127)
        return ok()

    def ops(self):
        return {a[0] for a in self.calls}


@pytest.fixture(autouse=True)
def host(monkeypatch):
    monkeypatch.setattr(r, "rootlesskit_flags", lambda: {"net": "slirp4netns", "disable_host_loopback": True, "port_driver": "builtin"})
    monkeypatch.setattr(r, "host_address", lambda: "192.0.2.10")
    monkeypatch.setattr(r, "host_gateway", lambda: "192.0.2.1")


def env(name="ocs-qa-ready", **fields):
    m = c.create(name, "scratch", provisioning=ig.request([]))
    m.update(fields)
    c.save(m)
    return m


def by_id(report):
    return {x["id"]: x for x in report["checks"]}


def checks(m):
    return by_id(r.run(m))


def test_healthy_running_environment_passes_and_the_check_is_read_only(monkeypatch):
    m = env()
    fake = FakeDocker(monkeypatch, m)
    ac.refresh(m, c.env_dir, **c.guidance_inputs(m))
    result = checks(m)
    assert {k: v["status"] for k, v in result.items()} == {
        "daemon": "passed", "resource-support": "passed", "workspace": "passed", "operation": "passed", "image": "passed", "container": "passed",
        "volume": "passed", "runtime": "passed", "network": "passed", "ports": "not applicable",
        "reachability": "passed", "profile": "passed", "agent-context": "passed",
        "agent-context-delivery": "passed", "opencode": "passed", "storage": "not checked"}
    assert not fake.ops() & MUTATING
    detail = result["reachability"]["detail"]
    assert "not isolated from the LAN" in detail and "internet: reachable (verified TLS handshake with registry.npmjs.org)" in detail
    assert "host 127.0.0.1 services: not reachable (10.0.2.2: unreachable; rootlesskit --disable-host-loopback)" in detail
    assert "host LAN address 192.0.2.10: reachable (the host answered)" in detail
    assert "LAN gateway 192.0.2.1: answered" in detail
    assert result["opencode"]["detail"] == "2.2.0; notify; self-update off"


def test_unverified_daemon_fails_and_nothing_else_touches_docker(monkeypatch):
    m = env()
    monkeypatch.setattr(rid, "verify", lambda context=None, **k: rid.Identity(rid.UNAVAILABLE, "rootless", None, reasons=("no daemon",)))
    monkeypatch.setattr(c, "docker", lambda *a, **k: pytest.fail("docker must not run"))
    result = runner.invoke(app, ["check", m["name"]])
    assert result.exit_code == 1
    assert "[failed]" in result.output and "Docker daemon: Docker daemon identity: unavailable" in result.output
    report = r.cached(m)
    statuses = {x["id"]: x["status"] for x in report["checks"]}
    assert statuses["daemon"] == "failed" and statuses["workspace"] == "passed" and statuses["container"] == "not checked"
    assert statuses["agent-context"] == "warning"  # configured inputs, file not written yet


@pytest.mark.parametrize("fields,status,text", [
    ({"operation": "opencode-update"}, "failed", "opencode-sandbox opencode update-recover ocs-qa-ready"),
    ({"operation": "runtime-recreate"}, "failed", "opencode-sandbox config recover ocs-qa-ready"),
    ({"operation": "starting"}, "warning", "opencode-sandbox repair ocs-qa-ready"),
    ({"status": "error", "last_error": "Creation failed: x"}, "warning", "Creation failed: x"),
    ({"status": "running"}, "warning", "metadata says running, Docker reports stopped"),
])
def test_operation_check(monkeypatch, fields, status, text):
    m = env(**fields)
    fake = FakeDocker(monkeypatch, m)
    fake.running = False
    check = checks(m)["operation"]
    assert check["status"] == status and text in check["detail"] + (check["hint"] or "")


def test_workspace_check_managed_and_direct(monkeypatch, tmp_path):
    m = env()
    FakeDocker(monkeypatch, m)
    (c.env_dir(m["id"]) / "workspace").rmdir()
    check = checks(m)["workspace"]
    assert check["status"] == "failed" and "managed workspace directory missing" in check["detail"]
    project = tmp_path / "projects" / "app"; project.mkdir(parents=True)
    d = env("ocs-qa-direct", workspace={"mode": "direct", "path": str(project)})
    FakeDocker(monkeypatch, d)
    assert checks(d)["workspace"]["status"] == "passed"
    other = tmp_path / "projects" / "other"; other.mkdir()
    project.rmdir(); project.symlink_to(other)
    check = checks(d)["workspace"]
    assert check["status"] == "failed" and "now resolves to" in check["detail"]


def test_image_check(monkeypatch):
    m = env()
    fake = FakeDocker(monkeypatch, m)
    fake.images.clear()
    assert checks(m)["image"]["status"] == "warning"  # container exists, cannot be recreated
    fake.exists = False
    check = checks(m)["image"]
    assert check["status"] == "failed" and check["hint"] == "opencode-sandbox build --distro debian"
    fake.images.add("opencode-sandbox:debian")
    p = env("ocs-qa-pin", opencode_policy="pinned", opencode_pin="2.1.4")
    FakeDocker(monkeypatch, p).exists = False
    check = checks(p)["image"]
    assert check["status"] == "failed" and "pinned to OpenCode 2.1.4, but base image" in check["detail"]


def test_container_and_volume_checks(monkeypatch):
    m = env()
    fake = FakeDocker(monkeypatch, m)
    fake.dead = True
    assert checks(m)["container"]["status"] == "failed"
    fake.dead = False
    fake.volume = None
    assert checks(m)["volume"]["status"] == "failed"
    fake.volume = {"Name": c.volume(m), "Labels": {}}
    check = checks(m)["volume"]
    assert check["status"] == "failed" and "does not belong to this environment" in check["detail"]
    fake.exists, fake.volume = False, None
    result = checks(m)
    assert result["container"]["status"] == result["volume"]["status"] == "not applicable"
    assert result["reachability"]["status"] == "not checked" and result["opencode"]["status"] == "not checked"
    fake.exists, fake.owner, fake.volume = True, "ffffffffffffffff", {"Name": c.volume(m), "Labels": {"org.opencode-sandbox.id": m["id"]}}
    result = checks(m)
    assert result["container"]["status"] == "failed" and "ownership mismatch" in result["container"]["detail"]
    # The other checks still report; container-dependent ones say why they did not run.
    assert len(result) == 16 and result["volume"]["status"] == "passed" and result["profile"]["status"] == "passed"
    assert result["network"]["status"] == result["opencode"]["status"] == "not checked"
    assert result["network"]["detail"] == "container not inspected"


def test_runtime_and_network_mismatch_give_the_recreation_hint(monkeypatch):
    m = env()
    fake = FakeDocker(monkeypatch, m)
    fake.host.update(NanoCpus=1_000_000_000, NetworkMode="none")
    result = checks(m)
    assert result["runtime"]["status"] == "warning" and "(container: 1.0)" in result["runtime"]["detail"]
    assert result["network"]["status"] == "warning"
    assert result["network"]["detail"] == "configured bridge, but the container runs with none"
    assert result["network"]["hint"] == f"Recreate the container to apply the configuration: opencode-sandbox container recreate {m['name']} --yes"


def _tcp_line(addr, port, state="0A"):
    return f"   0: {addr}:{port:04X} 00000000:0000 {state} 0 0 0 tcp"


def test_ports_check(monkeypatch):
    m = env(runtime={**c.runtime_settings(env("ocs-qa-x")), "ports": [{"host": 18080, "container": 8000, "protocol": "tcp"}]})
    fake = FakeDocker(monkeypatch, m)
    fake.host["PortBindings"] = {}
    check = checks(m)["ports"]
    assert check["status"] == "warning" and "container publishes none" in check["detail"]
    fake.host["PortBindings"] = {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18080"}]}
    check = checks(m)["ports"]
    assert check["status"] == "passed" and "nothing listens on 8000" in check["detail"]
    assert "host 127.0.0.1:18080 -> container 8000/tcp (this host only" in check["detail"]
    fake.proc_net = _tcp_line("0100007F", 8000)
    check = checks(m)["ports"]
    assert check["status"] == "warning" and "listens on 127.0.0.1:8000 only" in check["detail"]
    fake.proc_net = _tcp_line("00000000", 8000) + "\n" + _tcp_line("00000000", 9000)
    assert checks(m)["ports"]["status"] == "passed"
    fake.proc_net = _tcp_line("00000000", 8000, state="01")  # an established connection, no listener
    assert "nothing listens" in checks(m)["ports"]["detail"]
    fake.host["PortBindings"] = {"8000/tcp": [{"HostIp": "0.0.0.0", "HostPort": "18080"}]}
    assert checks(m)["ports"]["status"] == "warning"


def test_reachability_negative_cases(monkeypatch):
    m = env()
    fake = FakeDocker(monkeypatch, m)
    fake.running = False
    assert checks(m)["reachability"]["status"] == "not checked"
    fake.running = True
    fake.probe = lambda spec: {**GOOD, "internet": "no-dns"}
    check = checks(m)["reachability"]
    assert check["status"] == "warning" and "internet: not reachable (registry.npmjs.org: no-dns)" in check["detail"]
    fake.probe_rc = 127
    check = checks(m)["reachability"]
    assert check["status"] == "not checked" and "needs python3" in check["detail"]
    fake.probe_rc = 0
    fake.probe = lambda spec: "not json"
    assert checks(m)["reachability"]["status"] == "not checked"
    fake.probe = lambda spec: {"internet": ["x"]}
    assert checks(m)["reachability"]["status"] == "not checked"


def test_host_loopback_reach_is_observed_on_the_host(monkeypatch):
    """The container's claim does not matter: the host listener sees the token."""
    m = env()
    fake = FakeDocker(monkeypatch, m)
    seen = {}

    def connect(spec):
        host, port, token = spec["host-loopback"]
        seen.update(host=host, lan=spec["host-lan"])
        with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
            s.sendall(token.encode())
        return {**GOOD, "host-loopback": "unreachable"}  # lies
    fake.probe = connect
    check = checks(m)["reachability"]
    assert seen["host"] == "10.0.2.2" and seen["lan"][0] == "192.0.2.10"
    assert check["status"] == "warning" and "host 127.0.0.1 services: REACHABLE" in check["detail"]
    assert "--disable-host-loopback" in check["hint"]


def test_reachability_with_other_network_drivers_and_no_lan(monkeypatch):
    monkeypatch.setattr(r, "rootlesskit_flags", lambda: {"net": "pasta", "disable_host_loopback": False, "port_driver": "implicit"})
    monkeypatch.setattr(r, "host_address", lambda: None)
    monkeypatch.setattr(r, "host_gateway", lambda: None)
    m = env()
    fake = FakeDocker(monkeypatch, m)
    specs = []
    fake.probe = lambda spec: (specs.append(spec), {"internet": "verified"})[1]
    check = checks(m)["reachability"]
    assert set(specs[0]) == {"internet"} and check["status"] == "passed"
    assert "host 127.0.0.1 services: not checked (rootless network driver pasta)" in check["detail"]
    assert "host LAN address: not checked" in check["detail"] and "LAN gateway: not checked" in check["detail"]


def test_network_none_is_measured(monkeypatch):
    m = env(runtime={**c.runtime_settings(env("ocs-qa-x")), "network": "none"})
    fake = FakeDocker(monkeypatch, m)
    fake.probe = lambda spec: {"internet": "no-dns", "host-loopback": "unreachable", "host-lan": "unreachable", "lan-gateway": "unreachable"}
    check = checks(m)["reachability"]
    assert check["status"] == "passed" and check["detail"].startswith("no network: nothing outside the container was reachable")
    fake.probe = lambda spec: {**GOOD, "internet": "no-dns"}  # the LAN answered although network=none
    assert checks(m)["reachability"]["status"] == "failed"


def test_profile_check(monkeypatch):
    m = env(profile="qa")
    fake = FakeDocker(monkeypatch, m)
    check = checks(m)["profile"]
    assert check["status"] == "warning" and "does not exist" in check["detail"]
    c.profile_set("qa", {"QA_KEY": "secret-value-1"})
    path = c.profile_path("qa")
    fake.mounts = [{"Destination": c.PROFILE_TARGET, "Source": str(path)}]
    fake.inode = path.stat().st_ino
    check = checks(m)["profile"]
    assert check["status"] == "passed" and check["detail"] == "'qa': 1 variable(s)"
    c.profile_set("qa", {"QA_KEY": "secret-value-2"})  # New inode
    check = checks(m)["profile"]
    assert check["status"] == "warning" and "changed after the container started" in check["detail"]
    assert "stop ocs-qa-ready && opencode-sandbox start" in check["hint"]
    fake.mounts = []
    check = checks(m)["profile"]
    assert check["status"] == "warning" and "container uses provider profile none, assigned is 'qa'" in check["detail"]
    os.chmod(path, 0o644)
    check = checks(m)["profile"]
    assert check["status"] == "failed" and "0600" in check["detail"]
    assert "secret-value" not in json.dumps(r.cached(m))


def test_agent_context_file_and_delivery(monkeypatch):
    m = env()
    fake = FakeDocker(monkeypatch, m)
    result = checks(m)
    assert result["agent-context"]["status"] == "warning"
    assert result["agent-context"]["hint"] == f"opencode-sandbox agent-context refresh {m['name']}"
    ac.refresh(m, c.env_dir, **c.guidance_inputs(m))
    assert checks(m)["agent-context"]["status"] == "passed"
    fake.system_config = json.dumps({"instructions": []})
    check = checks(m)["agent-context-delivery"]
    assert check["status"] == "failed" and "does not list /run/ocs-agent/context.md" in check["detail"]
    fake.system_config = None
    assert "is missing or unreadable" in checks(m)["agent-context-delivery"]["detail"]
    fake.running = False
    assert checks(m)["agent-context-delivery"]["status"] == "not checked"


def test_opencode_check(monkeypatch):
    m = env()
    fake = FakeDocker(monkeypatch, m)
    fake.version = None
    check = checks(m)["opencode"]
    assert check["status"] == "failed" and "opencode --version` failed" in check["detail"]
    fake.version = "opencode v2.2.0"
    fake.env = ["PATH=/usr/bin"]
    check = checks(m)["opencode"]
    assert check["status"] == "warning" and "self-update is not disabled" in check["detail"]
    fake.env.append("OPENCODE_DISABLE_AUTOUPDATE=1")
    custom = env("ocs-qa-custom", distro=None, image="example.org/tools:1")
    FakeDocker(monkeypatch, custom).version = None
    check = checks(custom)["opencode"]
    assert check["status"] == "failed" and "custom image without a working OpenCode" in check["detail"] and "opencode update" not in check["hint"]
    p = env("ocs-qa-pin", opencode_policy="pinned", opencode_pin="2.1.4")
    FakeDocker(monkeypatch, p)
    check = checks(p)["opencode"]
    assert check["status"] == "warning" and "changed outside the manager" in check["detail"]
    assert check["hint"].endswith("opencode update ocs-qa-pin --version 2.1.4")


def test_storage_check(monkeypatch, tmp_path):
    monkeypatch.setattr(c, "docker_root", lambda: tmp_path)
    monkeypatch.setenv("OPENCODE_SANDBOX_DOCKER_RESERVE_BYTES", str(2**62))
    check = r.storage_check()
    assert check.status == "warning" and "need" in check.detail
    monkeypatch.setenv("OPENCODE_SANDBOX_DOCKER_RESERVE_BYTES", "1")
    assert r.storage_check().status == "passed"


def test_a_crashing_check_does_not_hide_the_others(monkeypatch):
    m = env()
    FakeDocker(monkeypatch, m)
    monkeypatch.setattr(r, "rootlesskit_flags", lambda: 1 / 0)
    result = checks(m)
    assert result["reachability"]["status"] == "not checked" and "division by zero" in result["reachability"]["detail"]
    assert result["opencode"]["status"] == "passed"


def test_cache_status_and_cli(monkeypatch):
    m = env()
    fake = FakeDocker(monkeypatch, m)
    assert r.cached(m) is None and r.cached_line(m) == "not checked yet"
    result = runner.invoke(app, ["check", m["name"]])
    assert result.exit_code == 0, result.output
    assert f"Readiness of {m['name']}" in result.output and "Summary: " in result.output and "[passed]" in result.output
    path = c.env_dir(m["id"]) / r.CACHE
    assert path.stat().st_mode & 0o777 == 0o600
    assert re.fullmatch(r"last check 20\d\d-\d\d-\d\d \d\d:\d\d:\d\d UTC: \d+ passed, .*", r.cached_line(m))
    other = env("ocs-qa-other")
    (c.env_dir(other["id"]) / r.CACHE).write_text(path.read_text())  # another environment's report
    assert r.cached(other) is None
    monkeypatch.setattr(c, "profile_mismatch", lambda m: None)
    result = runner.invoke(app, ["status", m["name"]])
    assert "Network: bridge\n  bridge is NOT isolation from the LAN or the internet" in result.output
    assert "  measured 20" in result.output and "host 127.0.0.1 services: not reachable" in result.output
    assert "Readiness: last check 20" in result.output
    fake.host["NetworkMode"] = "none"
    result = runner.invoke(app, ["status", m["name"]])
    assert "Network: configured bridge, container runs with none — Recreate the container" in result.output
    fake.exists = False
    result = runner.invoke(app, ["status", other["name"]])
    assert "Network: bridge (configured; no container yet)" in result.output
    assert "reachability not measured; run: opencode-sandbox check ocs-qa-other" in result.output


def test_network_lines_without_docker():
    m = env(runtime={**c.runtime_settings(env("ocs-qa-x")), "network": "none"})
    lines = r.network_lines(m, r.UNKNOWN)
    assert lines[0] == "Network: none (configured; container not inspected)"
    assert "no network: model provider APIs" in lines[1]


def test_doctor_reports_images_and_storage(monkeypatch):
    m = env()
    fake = FakeDocker(monkeypatch, m)
    fake.images.clear()
    monkeypatch.setattr(r, "host_checks", list)  # the host's programs: tests/test_prerequisites.py
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "[warning]" in result.output and "Base image opencode-sandbox:debian: missing" in result.output
    assert "-> opencode-sandbox build --distro debian" in result.output
    assert "[not checked]   Docker storage" in result.output


def test_host_helpers(tmp_path):
    proc = tmp_path / "proc"
    (proc / "123").mkdir(parents=True)
    (proc / "123" / "comm").write_text("rootlesskit\n")
    (proc / "123" / "cmdline").write_bytes(b"rootlesskit\0--net=slirp4netns\0--disable-host-loopback\0--port-driver=builtin\0dockerd\0")
    (proc / "self").mkdir()
    assert ROOTLESSKIT_FLAGS(proc) == {"net": "slirp4netns", "disable_host_loopback": True, "port_driver": "builtin"}
    assert ROOTLESSKIT_FLAGS(tmp_path / "missing") is None
    route = tmp_path / "route"
    route.write_text("Iface\tDestination\tGateway \tFlags\n"
                     "eth0\t000200C0\t00000000\t0001\n"
                     "eth0\t00000000\t010200C0\t0003\n")
    assert HOST_GATEWAY(route) == "192.0.2.1"  # a documentation address (RFC 5737)
    assert HOST_GATEWAY(tmp_path / "none") is None


def test_probe_script_runs_and_classifies(tmp_path):
    """The script the container executes, run here against loopback only."""
    import subprocess
    import sys
    listener = socket.socket(); listener.bind(("127.0.0.1", 0)); listener.listen(1)
    closed = socket.socket(); closed.bind(("127.0.0.1", 0)); port_closed = closed.getsockname()[1]; closed.close()
    spec = {"open": ["127.0.0.1", listener.getsockname()[1], "tok"], "closed": ["127.0.0.1", port_closed],
            "dns": ["ocs-qa-no-such-host.invalid", 9]}
    out = subprocess.run([sys.executable, "-c", r.PROBE, json.dumps(spec)], capture_output=True, text=True, timeout=30, check=True)
    listener.close()
    assert json.loads(out.stdout) == {"open": "connected", "closed": "refused", "dns": "no-dns"}


def test_tui_check_key_shows_the_report_and_the_details_line(monkeypatch):
    import asyncio

    from opencode_sandbox import tui
    m = env()
    FakeDocker(monkeypatch, m)

    async def main():
        app = tui.Dashboard()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert "Readiness: not checked yet" in str(app.query_one("#details").render())
            await pilot.press("i")
            for _ in range(30):
                await pilot.pause(); await asyncio.sleep(0.1)
                if type(app.screen).__name__ == "OpenCodeVersionsScreen":
                    break
            assert type(app.screen).__name__ == "OpenCodeVersionsScreen"
            assert f"Readiness of {m['name']}" in app.screen.report and "[passed]" in app.screen.report
            await pilot.press("escape"); await pilot.pause()
            assert "Readiness: last check 20" in str(app.query_one("#details").render())
    asyncio.run(main())
