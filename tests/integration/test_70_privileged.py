"""Rows that need privileged host actions or change the user's daemon (campaign rows B01, B02, B08,
C01, D09; only with the owner's consent). Opt-in on top of OCS_TEST_DOCKER=1:
OCS_TEST_PRIVILEGED=1, and `sudo -n true` must succeed (cached or NOPASSWD credentials; nothing here
ever waits for a password).

What runs and what it touches:
- `sudo install.sh …` / `sudo setup-rootless.sh` and the manager as root: must refuse; /root unchanged.
- `install.sh install --offer-packages` in a throw-away HOME with a `pacman -Q` shim that reports
  fuse-overlayfs as missing: the real `sudo pacman -S` runs and is declined at pacman's own prompt.
- `setup-rootless.sh` answering yes: `systemctl --user enable --now docker.service` (already enabled
  and running: no change) and `docker run --rm hello-world` (image removed afterwards if it was new).
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
import time
from pathlib import Path

import pytest
from campaign import INSTALLED, MANAGER, ROOT, SOCKET

pyte = pytest.importorskip("pyte")
from pty_term import Term

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
    """B01: the installer, the rootless wizard and the manager refuse to run as root."""
    camp, ck = campaign, checks
    before = root_tree(camp, sudo)
    for script, args in (("install.sh", ["install"]), ("install.sh", ["install", "--dry-run"]), ("install.sh", ["doctor"]),
                         ("install.sh", ["update"]), ("install.sh", ["uninstall"]), ("setup-rootless.sh", []),
                         ("setup-rootless.sh", ["--dry-run"])):
        p = sudo(camp, "bash", str(ROOT / script), *args)
        ck(p.returncode == 1 and ("refuse root" in p.stderr or "never sudo" in p.stderr),
           f"B01 sudo {script} {' '.join(args)}: refused ({p.returncode}: {p.stderr.strip()[-80:]})")
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


def test_offer_packages_runs_sudo_pacman_only_after_consent(campaign, checks, sudo):
    """B02: a missing repository package is offered; `n` runs nothing, `y` runs the real
    `sudo pacman -S`, which is declined at pacman's own prompt (no package change)."""
    camp, ck = campaign, checks
    home = Path("/tmp/opencode") / f"ocs-test-{camp.run}" / "home-b02"
    shims = home / "shims"
    shims.mkdir(parents=True, exist_ok=True)
    camp.note(f"host dir {home} (throw-away HOME, pacman/sudo shims)")
    calls = home / "sudo-calls.txt"
    (shims / "pacman").write_text('#!/bin/sh\n[ "$1" = -Qq ] && [ "$2" = fuse-overlayfs ] && exit 1\nexec /usr/bin/pacman "$@"\n')
    (shims / "sudo").write_text(f'#!/bin/sh\necho "$*" >> {calls}\nexec /usr/bin/sudo -n "$@"\n')
    for shim in shims.iterdir():
        shim.chmod(0o755)
    env = {"HOME": str(home), "PATH": f"{shims}:/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "TERM": "xterm-256color",
           "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""), "DOCKER_CONFIG": str(Path.home() / ".docker")}
    packages = subprocess.run(["pacman", "-Q"], capture_output=True, text=True, check=True).stdout

    def install(answers):
        t = Term(["bash", str(ROOT / "install.sh"), "install", "--offer-packages"], 120, 40, env=env, log=camp.log)
        try:
            prompts = (b"[y/N]", b"[Y/n]")
            for n, answer in enumerate(answers, 1):
                if not camp.wait_for(lambda n=n: t.pump(0.2) or sum(t.raw.count(x) for x in prompts) >= n or not t.alive, 300, 0):
                    break
                if sum(t.raw.count(x) for x in prompts) < n:
                    break
                t.send(answer + "\r", 2)
            code = t.exit_code(300)
            text = t.raw.decode(errors="replace")
            camp.log(f"$ install.sh install --offer-packages (pty, answers {answers})\n{text}\nexit={code}")
            return code, text
        finally:
            t.close()

    code, text = install(["n", "n"])
    ck("Not installed (verify repo availability): fuse-overlayfs" in text and "Run sudo pacman -S -- fuse-overlayfs?" in text,
       "B02 the missing package is listed and offered")
    ck(not calls.exists(), "B02 declined: sudo was never invoked")
    ck(not (home / ".local/share/opencode-sandbox-manager/releases").exists(), f"B02 declined install: nothing installed ({code})")
    code, text = install(["y", "n", "n"])
    ran = calls.read_text() if calls.exists() else ""
    ck(ran.strip() == "pacman -S -- fuse-overlayfs", f"B02 consent: exactly `sudo pacman -S -- fuse-overlayfs` ran ({ran.strip()})")
    ck("Proceed with installation?" in text, "B02 the real pacman asked for its own confirmation (declined)")
    ck(subprocess.run(["pacman", "-Q"], capture_output=True, text=True, check=True).stdout == packages, "B02 installed packages unchanged")
    camp.log(f"B02 installer exit after pacman was declined: {code}")
    shutil.rmtree(home)
    camp.note(f"removed host dir {home}")


def test_setup_rootless_guided_steps(campaign, checks):
    """B08: the guided systemd step and the smoke test, answered with yes."""
    camp, ck = campaign, checks
    unit = lambda what: subprocess.run(["systemctl", "--user", what, "docker.service"], capture_output=True,
                                       text=True, check=False).stdout.strip()
    state = (unit("is-enabled"), unit("is-active"))
    had_hello = camp.docker("image", "inspect", "hello-world", check=False).returncode == 0
    pid = subprocess.run(["systemctl", "--user", "show", "-p", "MainPID", "--value", "docker.service"],
                         capture_output=True, text=True, check=False).stdout.strip()
    t = Term(["bash", str(ROOT / "setup-rootless.sh")], 120, 40, env=camp.env, log=camp.log)
    try:
        for n in (1, 2):
            camp.wait_for(lambda n=n: t.pump(0.2) or t.raw.count(b"[y/N]") >= n or not t.alive, 300, 0)
            if t.raw.count(b"[y/N]") >= n:
                t.send("y\r", 2)
        code = t.exit_code(300)
        text = t.raw.decode(errors="replace")
        camp.log(f"$ setup-rootless.sh (pty, yes to both)\n{text}\nexit={code}")
    finally:
        t.close()
    if not had_hello:
        camp.note("image hello-world (pulled by setup-rootless.sh)")
    ck("Enable and start the USER docker.service?" in text and "Hello from Docker!" in text,
       "B08 both guided steps ran after consent (systemd enable --now, hello-world)")
    ck("Rootless engine: READY" in text and code == 0, f"B08 final check READY ({code})")
    local_bin = Path.home() / ".local/bin/dockerd-rootless-setuptool.sh"
    if local_bin.exists():
        ck("[MISSING] dockerd-rootless-setuptool.sh" not in text, "B08 the setup tool in ~/.local/bin is found")
    after_pid = subprocess.run(["systemctl", "--user", "show", "-p", "MainPID", "--value", "docker.service"],
                               capture_output=True, text=True, check=False).stdout.strip()
    ck((unit("is-enabled"), unit("is-active")) == state == ("enabled", "active") and after_pid == pid,
       "B08 an enabled, running daemon is left as it was (same main PID)")
    ck(camp.docker("ps", "-aq", "--filter", "ancestor=hello-world").stdout.strip() == "", "B08 the smoke container was removed (--rm)")
    if not had_hello:
        camp.docker("image", "rm", "hello-world")
        camp.note("removed image hello-world")


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
        inst = subprocess.run(["bash", str(ROOT / "install.sh"), "doctor"], env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, check=False)
        camp.log(f"$ install.sh doctor (rootful context)\n{inst.stdout}{inst.stderr}exit={inst.returncode}")
        ck("Daemon identity: mismatch" in inst.stdout and "rootful" in inst.stdout, "C01 install.sh doctor: mismatch, rootful")
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


def test_daemon_restart_stop_and_crash(campaign, checks):
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
        p = subprocess.run(["systemctl", "--user", *args, "docker.service"], capture_output=True, text=True, check=False)
        camp.log(f"$ systemctl --user {' '.join(args)} docker.service\n{p.stdout}{p.stderr}exit={p.returncode}")
        return p

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
    time.sleep(2)
    if systemctl("is-active").stdout.strip() != "active":
        systemctl("start")
    ck(bool(daemon_up(camp)), "D09 daemon up after a SIGKILL of the whole unit")
    p = camp.ocs("start", name, check=False)
    ck(p.returncode == 0, f"D09 start after the daemon crash ({(p.stdout + p.stderr).strip()[-160:]})")
    ck(intact() and camp.sh(eid, "cat /workspace/crash.txt", check=False).stdout == "after-crash\n", "D09 crash: data intact")
    report = camp.ocs("check", name, check=False)
    ck(report.returncode == 0, "D09 check passes after the crash")
    camp.delete(name)
