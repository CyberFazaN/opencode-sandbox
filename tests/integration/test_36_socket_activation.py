"""C10: explicitly authorized isolated user units, never the user's Docker service.

Opt in with OCS_TEST_DOCKER=1 OCS_TEST_SOCKET_ACTIVATION=1. This starts/stops/removes only
new ocs-test-act-* user units and a separate no-network rootless daemon. Needs rootlesskit,
dockerd-rootless.sh, systemd --user and the pre-existing ubuntu:24.04 image. No sudo, package
installation, default context edit, inbound port, or mutation of the original daemon.
"""
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from campaign import GUARD, MANAGER, SOCKET
from pty_term import F5, Term

pytestmark = pytest.mark.skipif(os.environ.get("OCS_TEST_SOCKET_ACTIVATION") != "1",
                                reason="isolated user-unit permission: OCS_TEST_SOCKET_ACTIVATION=1")


@pytest.fixture(scope="module")
def activated(campaign):
    camp = campaign
    launcher = shutil.which("dockerd-rootless.sh")
    if not launcher or not shutil.which("rootlesskit"):
        pytest.fail("socket-activation opt-in requires the rootless daemon tools on PATH")
    name = "ocs-test-act-" + secrets.token_hex(4)
    runtime = Path(f"/run/user/{os.getuid()}") / name
    unit_dir = runtime.parent / "systemd/user"
    assert unit_dir.is_dir(), "user systemd runtime unit directory must exist"
    service, listener = (unit_dir / (name + suffix) for suffix in (".service", ".socket"))
    assert not any(p.exists() or p.is_symlink() for p in (runtime, service, listener))
    root = camp.tmp("activation")
    runtime.mkdir(mode=0o700)
    camp.note(f"C10 units {service} {listener}; runtime tree {runtime}; isolated daemon data {root / 'docker'}")
    delay = root / "delay"
    delay.write_text("2")
    config = root / "daemon.json"
    config.write_text("{}")
    service.write_text(f"""[Unit]
Description=OCS disposable activation test
Requires={name}.socket
After={name}.socket
[Service]
Type=simple
Environment=PATH={Path(launcher).parent}:/usr/bin:/bin
Environment=DOCKERD_ROOTLESS_ROOTLESSKIT_STATE_DIR={runtime}/kit
Environment=DOCKERD_ROOTLESS_ROOTLESSKIT_NET=none
Environment=DOCKERD_ROOTLESS_ROOTLESSKIT_PORT_DRIVER=none
Environment=DOCKERD_ROOTLESS_ROOTLESSKIT_DETACH_NETNS=false
ExecStartPre={sys.executable} -c 'import time; from pathlib import Path; time.sleep(float(Path("{delay}").read_text()))'
ExecStart={launcher} --host=fd:// --config-file={config} --data-root={root}/docker --exec-root={runtime}/exec --pidfile={runtime}/dockerd.pid --storage-driver=vfs --iptables=false --ip6tables=false --bridge=none --ip-forward=false --ip-masq=false
Delegate=yes
KillMode=mixed
TimeoutStopSec=20
""")
    listener.write_text(f"""[Unit]
Description=OCS disposable rootless listener
[Socket]
ListenStream={runtime}/docker.sock
SocketMode=0600
RemoveOnStop=yes
Service={name}.service
""")

    def systemctl(*args, check=True):
        return camp._run(["systemctl", "--user", *args], check=check, timeout=40)

    endpoint = f"unix://{runtime}/docker.sock"
    env = {**camp.env, "DOCKER_CONFIG": str(root / "client"),
           "OPENCODE_SANDBOX_DOCKER_CONTEXT": name,
           "OPENCODE_SANDBOX_HOME": str(root / "data"), "OPENCODE_SANDBOX_CONFIG": str(root / "config")}
    ids = []

    def cold(seconds=2):
        systemctl("stop", name + ".socket", name + ".service")
        systemctl("reset-failed", name + ".service", name + ".socket", check=False)
        delay.write_text(str(seconds))
        systemctl("start", name + ".socket")
        assert systemctl("is-active", name + ".service", check=False).stdout.strip() == "inactive"
        # No Docker probe/inventory between here and the manager invocation under test.

    def ocs(*args, **kwargs):
        return camp.ocs(*args, env=env, timeout=25, **kwargs)

    def docker(*args, **kwargs):
        return camp._run(["docker", "-H", endpoint, *args], check=True, **kwargs)

    systemctl("daemon-reload")
    try:
        cold(0)
        camp._run(["docker", "--config", env["DOCKER_CONFIG"], "context", "create", name,
                   "--docker", f"host={endpoint}"], check=True)
        archive = root / "ubuntu.tar"
        camp.note(f"C10 image archive {archive}; ubuntu:24.04 loaded only into the isolated daemon")
        camp._run(["docker", "-H", SOCKET, "image", "save", "-o", str(archive), "ubuntu:24.04"], check=True)
        docker("image", "load", "-i", str(archive))
        ocs("create", "ocs-test-activation", "--image", "ubuntu:24.04", "--no-integrations")
        meta = json.loads(next((Path(env["OPENCODE_SANDBOX_HOME"]) / "environments").glob("*/metadata.json")).read_text())
        ids.append(meta["id"])
        camp.note(f"C10 isolated environment ocs-test-activation id={meta['id']}")
        ocs("config", "apply", meta["id"], "--network", "none", "--yes")
        yield camp, cold, ocs, docker, env, ids
    finally:
        try:
            cold(0)
            for eid in ids:
                ocs("stop", eid, check=False)
                ocs("delete", eid, "--yes")
            guard_env = dict(env, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
            guard = camp._run([sys.executable, "-c", GUARD % (env["OPENCODE_SANDBOX_HOME"], env["OPENCODE_SANDBOX_CONFIG"], ids)],
                              env=guard_env, check=False)
            assert guard.returncode == 0, "isolated activation cleanup guard refused"
            ocs("disk", "cleanup", "--yes")
            assert not docker("container", "ls", "-aq").stdout.strip()
            assert not docker("volume", "ls", "-q").stdout.strip()
            # This daemon started empty: remove only the one explicitly loaded test image.
            images = docker("image", "ls", "--format", "{{.Repository}}:{{.Tag}}").stdout.splitlines()
            assert images == ["ubuntu:24.04"], images
            docker("image", "rm", "ubuntu:24.04")
            camp.note(f"C10 guarded product cleanup and empty Docker inventory: {name}")
        finally:
            systemctl("stop", name + ".socket", name + ".service")
            service.unlink(); listener.unlink()
            systemctl("daemon-reload")
            assert runtime.parent == Path(f"/run/user/{os.getuid()}") and not runtime.is_symlink()
            assert runtime.stat().st_uid == os.getuid()
            shutil.rmtree(runtime)
            camp.note(f"C10 named units/runtime removed: {name}")


def test_cold_doctor_start_check_and_warm_path(activated, checks):
    _camp, cold, ocs, docker, _env, ids = activated
    cold()
    start = time.monotonic()
    result = ocs("doctor")
    elapsed = time.monotonic() - start
    checks("Daemon identity: verified" in result.stdout and "Waiting for Docker readiness" in result.stderr,
           f"C10 cold doctor verifies actual inherited rootless responder ({elapsed:.2f}s)")
    start = time.monotonic()
    warm = ocs("doctor")
    checks("Waiting for Docker readiness" not in warm.stderr and time.monotonic() - start < 2,
           "C10 warm doctor has no readiness sleep/notice")
    meta = {"id": ids[0]}
    cold()
    ocs("start", meta["id"])
    docker("exec", f"ocs-{meta['id']}", "sh", "-c", "echo preserved > /workspace/marker; echo preserved > /root/marker")
    ocs("stop", meta["id"])
    cold()
    report = ocs("check", meta["id"], check=False)
    checks("[passed] Docker daemon:" in " ".join(report.stdout.split()) and "Waiting for Docker readiness" in report.stderr,
           "C10 check cold acquisition passes (other custom-image checks may fail)")
    ocs("start", meta["id"])
    checks(docker("exec", f"ocs-{meta['id']}", "sh", "-c", "cat /workspace/marker /root/marker").stdout == "preserved\npreserved\n",
           "C10 workspace/home markers survive separate daemon cold starts")
    ocs("stop", meta["id"])


def test_cold_dashboard_and_overlapping_start(activated, checks):
    camp, cold, ocs, _docker, env, ids = activated
    cold()
    term = Term([*MANAGER, "tui"], env=env, log=camp.log)
    try:
        checks(term.wait_for("Waiting for Docker readiness", timeout=5), "C10 dashboard shows truthful cold wait")
        term.send(F5, settle=.1)
        checks(term.wait_for("Started", timeout=15), "C10 concurrent startup/action completes without premature refusal")
        checks(b"Docker is not ready" not in term.raw, "C10 no transient broken-installation warning")
        term.send("q", settle=.1)
        checks(term.exit_code(3) == 0 and term.restored(), "C10 dashboard exits and restores terminal")
    finally:
        term.close()
    ocs("stop", ids[0])


def test_stalled_activation_deadline_and_dashboard_cancellation(activated, checks):
    camp, cold, ocs, _docker, env, _ids = activated
    cold(30)
    start = time.monotonic()
    result = ocs("doctor", check=False)
    checks(result.returncode == 5 and "deadline" in result.stdout and time.monotonic() - start < 12,
           "C10 stalled real activation is bounded with exit 5 and concrete deadline")
    cold(30)
    term = Term([*MANAGER, "tui"], env=env, log=camp.log)
    try:
        checks(term.wait_for("Waiting for Docker readiness", timeout=5), "C10 stalled dashboard remains interactive")
        start = time.monotonic()
        term.send("q", settle=.1)
        checks(term.exit_code(2) == 0 and time.monotonic() - start < 2 and term.restored(),
               "C10 quit cancels preflight promptly and restores the terminal")
    finally:
        term.close()
    cold(30)
    term = Term([*MANAGER, "doctor"], env=env, log=camp.log)
    try:
        checks(term.wait_for("Waiting for Docker readiness", timeout=5), "C10 CLI shows wait in a real terminal")
        start = time.monotonic()
        term.send("\x03", settle=.1)
        checks(term.exit_code(2) != 0 and time.monotonic() - start < 2,
               "C10 CLI Ctrl-C interrupts real socket readiness promptly")
    finally:
        term.close()


def test_real_dockerd_bytes_forwarded_by_same_user_proxy_are_refused(activated, checks):
    camp, cold, ocs, _docker, env, _ids = activated
    cold(0)
    ocs("doctor")
    endpoint = json.loads(camp._run(["docker", "--config", env["DOCKER_CONFIG"], "context", "inspect",
                                     env["OPENCODE_SANDBOX_DOCKER_CONTEXT"]], check=True).stdout)[0]["Endpoints"]["docker"]["Host"]
    path = Path(endpoint.removeprefix("unix://")).with_name("proxy.sock")
    camp.note(f"C10 own-user proxy socket {path}; only its own child process is started/reaped")
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(path)); listener.listen(1)
        code = """import socket,sys
s=socket.socket(fileno=int(sys.argv[1])); c,_=s.accept()
with c, socket.socket(socket.AF_UNIX) as upstream:
 upstream.connect(sys.argv[2]); upstream.sendall(c.recv(4096))
 try:
  while True:
   data=upstream.recv(16384)
   if not data: break
   c.sendall(data)
 except (BrokenPipeError,ConnectionResetError): pass
"""
        child = subprocess.Popen([sys.executable, "-I", "-c", code, str(listener.fileno()), endpoint.removeprefix("unix://")],
                                 pass_fds=(listener.fileno(),))
        try:
            name = env["OPENCODE_SANDBOX_DOCKER_CONTEXT"] + "-proxy"
            camp._run(["docker", "--config", env["DOCKER_CONFIG"], "context", "create", name, "--docker", f"host=unix://{path}"], check=True)
            result = camp.ocs("doctor", env={**env, "OPENCODE_SANDBOX_DOCKER_CONTEXT": name}, check=False, timeout=15)
            checks(result.returncode == 3 and "unverified-proxy" in result.stdout,
                   "C10 genuine rootless engine text forwarded by a same-user proxy cannot verify")
        finally:
            child.wait(timeout=3)
