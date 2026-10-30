"""Rows that need privileged host actions or change the user's daemon (campaign rows B01,
C01, D09; only with the owner's consent). Opt-in on top of OCS_TEST_DOCKER=1:
OCS_TEST_PRIVILEGED=1, and `sudo -n true` must succeed (cached or NOPASSWD credentials; nothing here
ever waits for a password).

What runs and what it touches:
- The manager as root must refuse the user's daemon; /root unchanged.
- A rootful `dockerd` started with sudo in private directories (no iptables, no bridge, vfs) and a
  socket served by another user (nobody): the manager must refuse both; stopped and removed after.
- `systemctl --user restart|stop|start docker` and a SIGKILL of the whole daemon unit with one test
  environment running: the environment's data must survive and `start` must work afterwards.
A host reboot cannot be driven from inside the session (see docs/engineering/CAMPAIGN.md, D09)."""
import grp
import hashlib
import os
import secrets
import shutil
import subprocess
from pathlib import Path

import pytest
from campaign import INSTALLED, MANAGER, ROOT, SOCKET

PRIVILEGED = os.environ.get("OCS_TEST_PRIVILEGED") == "1"
pytestmark = pytest.mark.skipif(not PRIVILEGED, reason="privileged rows: set OCS_TEST_PRIVILEGED=1 (uses sudo)")
MARKERS = "cat /workspace/ws-marker.txt /root/home-marker.txt /etc/ocs-test-system-marker"


@pytest.fixture(scope="module")
def sudo():
    if subprocess.run(["sudo", "-n", "true"], capture_output=True, check=False).returncode != 0:
        pytest.skip("sudo -n true fails: no cached or passwordless sudo")

    def run(camp, *argv, check=False, **kw):
        return camp._run(["sudo", "-n", *argv], check=check, **kw)
    return run


def root_tree(camp, sudo):
    return sudo(camp, "find", "/root", "-printf", "%p %s %T@\\n").stdout


def firewall(camp, sudo):
    rules = sudo(camp, "nft", "list", "ruleset").stdout
    links = subprocess.run(["ip", "-br", "link"], capture_output=True, text=True, check=False).stdout
    return hashlib.sha256(rules.encode()).hexdigest()[:16], sorted(line.split()[0] for line in links.splitlines())


def short_dir(camp, kind):
    """Unix socket paths are limited to 108 bytes: a short directory outside the checkout."""
    path = Path("/tmp/opencode") / f"ocs-test-{kind}-{secrets.token_hex(3)}"
    path.mkdir(parents=True)
    camp.note(f"host dir {path} ({kind})")
    return path


def context_env(camp, name, socket_path):
    cfg = camp.tmp(f"docker-config-{name}")
    subprocess.run(["docker", "--config", str(cfg), "context", "create", name, "--docker", f"host=unix://{socket_path}"],
                   check=True, capture_output=True)
    camp.note(f"docker context {name} in the private config dir {cfg} (not the user's)")
    return dict(camp.env, DOCKER_CONFIG=str(cfg), OPENCODE_SANDBOX_DOCKER_CONTEXT=name)


def test_root_is_refused(campaign, checks, sudo):
    """B01: the manager as root refuses the user's rootless daemon as another user's."""
    camp, ck = campaign, checks
    before = root_tree(camp, sudo)
    # The manager as root: its own UID is 0, so the user's rootless daemon is another user's.
    work = short_dir(camp, "root")
    cfg = work / "docker-config"
    shutil.copytree(Path.home() / ".docker" / "contexts", cfg / "contexts")
    (cfg / "config.json").write_text("{}")
    env = ["env", f"HOME={work}", f"DOCKER_CONFIG={cfg}", f"OPENCODE_SANDBOX_HOME={work}/data",
           f"OPENCODE_SANDBOX_CONFIG={work}/config", "PYTHONDONTWRITEBYTECODE=1",
           *([] if INSTALLED else [f"PYTHONPATH={ROOT / 'src'}"])]
    containers = camp.docker("ps", "-aq").stdout.split()
    p = sudo(camp, *env, *MANAGER, "doctor")
    ck(p.returncode != 0 and "another user" in p.stdout + p.stderr and "Traceback" not in p.stdout + p.stderr,
       f"B01 the manager as root refuses the user's rootless daemon ({(p.stdout + p.stderr).strip()[-160:]})")
    created = sudo(camp, *env, *MANAGER, "create", "ocs-test-asroot", "--no-integrations")
    p = created if created.returncode != 0 else sudo(camp, *env, *MANAGER, "start", "ocs-test-asroot")
    ck(p.returncode != 0 and "another user" in p.stdout + p.stderr, f"B01 create/start as root is refused ({created.returncode})")
    ck(camp.docker("ps", "-aq").stdout.split() == containers, "B01 no container was created")
    sudo(camp, "rm", "-rf", "--", str(work), check=True)
    camp.note(f"removed host dir {work} (root-owned files of the as-root run)")
    ck(root_tree(camp, sudo) == before, "B01 nothing under /root changed")
    ck(not any(p.owner() == "root" for p in (ROOT / "src").rglob("*")), "B01 no root-owned file in the checkout")


def test_rootful_and_foreign_daemons_are_refused(campaign, checks, sudo):
    """C01: a real rootful dockerd and a socket served by another user (UID 65534)."""
    camp, ck = campaign, checks
    net_before, etc_before = firewall(camp, sudo), Path("/etc/docker").exists()
    work = short_dir(camp, "rootful")
    (work / "daemon.json").write_text("{}")
    sock = work / "docker.sock"
    log = (camp.logs / f"{camp.run}-rootful-dockerd.log").open("w")
    daemon = subprocess.Popen(["sudo", "-n", "dockerd", "--config-file", str(work / "daemon.json"), "--data-root", str(work / "data"),
                               "--exec-root", str(work / "exec"), "--pidfile", str(work / "dockerd.pid"), "-H", f"unix://{sock}",
                               "--group", grp.getgrgid(os.getgid()).gr_name, "--iptables=false", "--ip6tables=false", "--bridge=none",
                               "--storage-driver", "vfs"], stdout=log, stderr=subprocess.STDOUT)
    camp.note(f"rootful dockerd (sudo, pid file {work / 'dockerd.pid'}, data in {work})")
    try:
        up = camp.wait_for(lambda: subprocess.run(["docker", "-H", f"unix://{sock}", "info", "--format", "{{.SecurityOptions}}"],
                                                  capture_output=True, text=True, check=False).returncode == 0, 90, 0.5)
        info = subprocess.run(["docker", "-H", f"unix://{sock}", "info", "--format", "{{.SecurityOptions}}"],
                              capture_output=True, text=True, check=False).stdout
        ck(bool(up) and "rootless" not in info, f"C01 a rootful dockerd answers this user's docker CLI ({info.strip()})")
        env = context_env(camp, "ocs-test-rootful", sock)
        p = camp.ocs("doctor", check=False, env=env)
        ck(p.returncode != 0 and "root (a rootful daemon)" in p.stdout + p.stderr, "C01 doctor: rootful daemon refused (mismatch)")
        camp.ocs("create", "ocs-test-viarootful", "--no-integrations", env=env)
        camp.adopt("ocs-test-viarootful")
        p = camp.ocs("start", "ocs-test-viarootful", check=False, env=env)
        ck(p.returncode != 0 and "rootful" in p.stdout + p.stderr and "Traceback" not in p.stdout + p.stderr,
           "C01 start through the rootful daemon refused")
        listed = subprocess.run(["docker", "-H", f"unix://{sock}", "ps", "-aq"], capture_output=True, text=True, check=False).stdout
        ck(listed.strip() == "", "C01 nothing was created on the rootful daemon")
        camp.delete("ocs-test-viarootful")
    finally:
        pid = (work / "dockerd.pid").read_text().strip() if (work / "dockerd.pid").exists() else None
        if pid:
            sudo(camp, "kill", pid)
        try:
            daemon.wait(timeout=60)
        except subprocess.TimeoutExpired:
            if pid:
                sudo(camp, "kill", "-KILL", pid)
            daemon.wait(timeout=30)
        log.close()
        sudo(camp, "umount", "-R", str(work / "exec"))
        sudo(camp, "rm", "-rf", "--", str(work), check=True)
        camp.note(f"stopped the rootful dockerd; removed {work}")
    ck(subprocess.run(["pgrep", "-f", str(work)], capture_output=True, check=False).returncode == 1, "C01 no process of the rootful daemon left")
    ck(firewall(camp, sudo) == net_before, f"C01 firewall rules and network interfaces unchanged {net_before}")
    ck(Path("/etc/docker").exists() == etc_before, "C01 the rootful daemon created no /etc/docker")

    # Another user's socket: the peer check refuses before talking to it.
    other = short_dir(camp, "ou")
    other.chmod(0o777)
    server = ("import os, socket, sys, time\nos.umask(0)\ns = socket.socket(socket.AF_UNIX)\ns.bind(sys.argv[1])\n"
              "s.listen(8)\nopen(sys.argv[1] + '.pid', 'w').write(str(os.getpid()))\ns.settimeout(1)\nend = time.time() + 300\n"
              "while time.time() < end:\n    try:\n        s.accept()[0].close()\n    except TimeoutError:\n        pass\n")
    osock = other / "docker.sock"
    proc = subprocess.Popen(["sudo", "-n", "-u", "nobody", "python3", "-I", "-c", server, str(osock)])
    camp.note(f"socket of user nobody at {osock}")
    try:
        camp.wait_for(lambda: Path(str(osock) + ".pid").exists(), 30, 0.2)
        env = context_env(camp, "ocs-test-other", osock)
        p = camp.ocs("doctor", check=False, env=env)
        ck(p.returncode != 0 and "UID 65534 (another user)" in p.stdout + p.stderr, "C01 another user's socket refused (mismatch)")
    finally:
        pid = Path(str(osock) + ".pid").read_text().strip() if Path(str(osock) + ".pid").exists() else None
        if pid:
            sudo(camp, "-u", "nobody", "kill", pid)
        proc.wait(timeout=30)
        sudo(camp, "rm", "-rf", "--", str(other), check=True)
        camp.note(f"stopped the nobody socket; removed {other}")


def daemon_up(camp):
    return camp.wait_for(lambda: subprocess.run(["docker", "-H", SOCKET, "info"], capture_output=True, check=False).returncode == 0, 120, 0.5)


def daemon_control(camp, *args):
    p = subprocess.run(["systemctl", "--user", *args, "docker.service"], capture_output=True, text=True, check=False)
    camp.log(f"$ systemctl --user {' '.join(args)} docker.service\n{p.stdout}{p.stderr}exit={p.returncode}")
    return p


def daemon_after_crash(camp, systemctl):
    # "activating" includes RestartSec/auto-restart, not a failed start. A competing start
    # counted as another burst and hit the host's existing service start limit.
    if daemon_up(camp):
        return True
    if systemctl("start").returncode:
        return False
    return bool(daemon_up(camp))


@pytest.fixture
def restore_daemon_after_fault(campaign):
    yield
    # Restore the host even when a test assertion fails; never turn that failure into PASS.
    assert daemon_after_crash(campaign, lambda *args: daemon_control(campaign, *args)), "host daemon recovery failed"


def test_daemon_restart_stop_and_crash(campaign, checks, restore_daemon_after_fault):
    """D09: the user's rootless daemon is restarted, stopped and SIGKILLed while an environment runs."""
    camp, ck = campaign, checks
    others = camp.docker("ps", "-q").stdout.split()
    if others:
        pytest.skip(f"other containers are running on the daemon: {others}")
    name = "ocs-test-daemon"
    eid = camp.create(name, "--no-integrations")
    camp.ocs("start", name)
    camp.sh(eid, "echo ocs-test-marker > /workspace/ws-marker.txt; echo ocs-test-marker > /root/home-marker.txt; "
                 "echo ocs-test-marker > /etc/ocs-test-system-marker; sync")

    def intact():
        p = camp.sh(eid, MARKERS, check=False)
        return p.returncode == 0 and p.stdout.count("ocs-test-marker") == 3

    def systemctl(*args):
        return daemon_control(camp, *args)

    systemctl("restart")
    ck(bool(daemon_up(camp)), "D09 daemon back after restart")
    status = camp.ocs("status", name, check=False)
    ck("Running: False" in status.stdout, "D09 after a daemon restart the container is stopped and status says so")
    camp.ocs("start", name)
    ck(intact(), "D09 restart: workspace, home volume and system layer intact; start works")

    systemctl("stop")
    for args in (["start", name], ["status", name]):
        p = camp.ocs(*args, check=False)
        text = p.stdout + p.stderr
        ck("Traceback" not in text and ("unavailable" in text.lower() or "does not exist" in text),
           f"D09 daemon stopped: {args[0]} reports it cleanly ({p.returncode})")
    ck(name in camp.ocs("list").stdout, "D09 daemon stopped: list works")
    systemctl("start")
    ck(bool(daemon_up(camp)), "D09 daemon started again")
    camp.ocs("start", name)
    ck(intact(), "D09 stop/start (as at shutdown and boot): data intact; start works")

    camp.sh(eid, "echo after-crash > /workspace/crash.txt; sync")
    systemctl("kill", "--signal=KILL")
    ck(daemon_after_crash(camp, systemctl), "D09 daemon up after a SIGKILL of the whole unit")
    p = camp.ocs("start", name, check=False)
    ck(p.returncode == 0, f"D09 start after the daemon crash ({(p.stdout + p.stderr).strip()[-160:]})")
    ck(intact() and camp.sh(eid, "cat /workspace/crash.txt", check=False).stdout == "after-crash\n", "D09 crash: data intact")
    report = camp.ocs("check", name, check=False)
    ck(report.returncode == 0, "D09 check passes after the crash")
    camp.delete(name)
