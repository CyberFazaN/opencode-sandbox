"""Credentials, isolation between environments and daemon identity (campaign rows F01–F04, F06,
C01, C06). Dummy keys only."""
import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
import threading

import pytest
from campaign import MANAGER, SOCKET

pyte = pytest.importorskip("pyte")
from pty_term import Term

HOSTILE = "dummy-$(touch /tmp/ocs-test-pwned)`id`;'\"\\ newline\nend"


def set_profile(camp, name, values):
    """Through the Python API, values on stdin: they never appear in a logged command line."""
    camp._run([sys.executable, "-c", ("import json, sys\nfrom opencode_sandbox import core as c\n"
               f"c.init_dirs(); c.profile_set({name!r}, json.load(sys.stdin))")], check=True, input=json.dumps(values))
    camp.note(f"profile {name} (isolated config dir, dummy values)")


def session_value(camp, name, var):
    """sha256 of $var as the managed `shell` session sees it, typed in a real terminal."""
    t = Term([*MANAGER, "shell", name], 100, 30, env=camp.env, log=camp.log)
    try:
        assert t.wait_for(r"root@|# ?$", 60), t.text()
        t.send(f"printf %s \"${var}\" | sha256sum | cut -c1-16 > /tmp/ocs-test-{var}.sum; exit\r", 3)
        t.exit_code(20)
    finally:
        t.close()


def test_profiles_secrets_and_isolation(campaign, checks):
    camp, ck = campaign, checks
    set_profile(camp, "ocs-test-a", {"QA_KEY": HOSTILE})
    set_profile(camp, "ocs-test-b", {"QA_KEY": "dummy-profile-b"})
    pa = camp.config / "profiles" / "ocs-test-a.json"
    ck(stat.S_IMODE(pa.stat().st_mode) == 0o600, "F01 profile file is 0600")
    listing = camp.ocs("providers", "list").stdout
    ck("QA_KEY" in listing and "dummy" not in listing, "F02 providers list shows names, never values")

    a = camp.create("ocs-test-sec-a", "--no-integrations", "--profile", "ocs-test-a")
    b = camp.create("ocs-test-sec-b", "--no-integrations", "--profile", "ocs-test-b")
    camp.ocs("start", "ocs-test-sec-a")
    camp.ocs("start", "ocs-test-sec-b")

    # F01: the value reaches the session byte for byte and is never evaluated by a shell
    session_value(camp, "ocs-test-sec-a", "QA_KEY")
    got = camp.sh(a, "cat /tmp/ocs-test-QA_KEY.sum").stdout.strip()
    ck(got == hashlib.sha256(HOSTILE.encode()).hexdigest()[:16], "F01 hostile value delivered unchanged to the session")
    ck(camp.sh(a, "test -e /tmp/ocs-test-pwned", check=False).returncode != 0 and not os.path.exists("/tmp/ocs-test-pwned"),
       "F01 the value was not executed (no file created in the container or on the host)")
    session_value(camp, "ocs-test-sec-b", "QA_KEY")
    ck(camp.sh(b, "cat /tmp/ocs-test-QA_KEY.sum").stdout.strip() == hashlib.sha256(b"dummy-profile-b").hexdigest()[:16],
       "F03 each environment gets its own profile")
    ck(camp.sh(a, "test -e /run/secrets/ocs-provider.json && grep -c dummy-profile-b /run/secrets/ocs-provider.json || true").stdout.strip() in ("0", ""),
       "F03 environment A cannot see profile B")

    # F06: no value in the container configuration, process lists, metadata, logs or guidance
    for eid in (a, b):
        inspect = camp.docker("container", "inspect", f"ocs-{eid}").stdout
        ck("dummy" not in inspect, f"F06 not in docker inspect of ocs-{eid}")
        ck("dummy" not in camp.sh(eid, "cat /proc/1/environ | tr '\\0' '\\n'; ps -eo args").stdout, "F06 not in the container's init environment or process list")
    leaked = [str(p) for p in camp.data.rglob("*") if p.is_file() and p.stat().st_size < 10**7
              and (b"dummy-profile-b" in p.read_bytes() or b"touch /tmp/ocs-test-pwned" in p.read_bytes())]
    ck(leaked == [], f"F06 no value anywhere in the data directory {leaked}")
    output = [line for line in camp.log_path.read_text().split("===== test_profiles_secrets_and_isolation")[-1].splitlines()
              if not line.startswith("$ ")]  # the test's own command lines name the value it searches for
    ck(not any("dummy-profile-b" in line for line in output), "F06 no value in any command output of this test")
    exec_env = camp.ocs("exec", "ocs-test-sec-a", "--", "sh", "-c", "echo ${QA_KEY:-unset}")
    ck("unset" in exec_env.stdout, "exec does not load the provider profile (documented)")

    # F03: changing A's profile recreates its container with the new mount; B is unaffected
    b_id = camp.inspect(b)["Id"]
    camp.ocs("config", "apply", "ocs-test-sec-a", "--profile", "ocs-test-b", "--yes")
    session_value(camp, "ocs-test-sec-a", "QA_KEY")
    ck(camp.sh(a, "cat /tmp/ocs-test-QA_KEY.sum").stdout.strip() == hashlib.sha256(b"dummy-profile-b").hexdigest()[:16],
       "F03 after config apply --profile the session sees the new profile")
    ck(camp.inspect(b)["Id"] == b_id, "F03 the other environment's container is untouched")

    # F02: legacy executable .env profiles and loose permissions are refused, never sourced
    legacy = camp.config / "profiles" / "ocs-test-legacy.env"
    legacy.write_text("QA_KEY=$(touch /tmp/ocs-test-pwned-env)\n")
    camp.note(f"legacy profile file {legacy}")
    p = camp.ocs("config", "apply", "ocs-test-sec-b", "--profile", "ocs-test-legacy", "--yes", check=False)
    ck(p.returncode != 0 and ".env" in p.stdout + p.stderr and not os.path.exists("/tmp/ocs-test-pwned-env"),
       f"F02 a legacy .env profile is refused ({(p.stdout + p.stderr).strip()[-160:]})")
    legacy.unlink()
    pb = camp.config / "profiles" / "ocs-test-b.json"
    pb.chmod(0o644)
    report = camp.ocs("check", "ocs-test-sec-b", check=False)
    ck(report.returncode == 1 and "0600" in report.stdout, "F01 check fails for a profile readable by others")
    p = camp.ocs("config", "apply", "ocs-test-sec-a", "--profile", "ocs-test-b", "--pids", "1000", "--yes", check=False)
    ck(p.returncode != 0 and "0600" in p.stdout + p.stderr, f"F01 such a profile is not mounted into a new container ({(p.stdout + p.stderr).strip()[-120:]})")
    pb.chmod(0o600)
    camp.delete("ocs-test-sec-a")
    camp.delete("ocs-test-sec-b")


def _proxy(listen, target, stop):
    server = socket.socket(socket.AF_UNIX)
    server.bind(listen)
    server.listen(4)
    server.settimeout(0.2)

    def pipe(a, b):
        try:
            while data := a.recv(65536):
                b.sendall(data)
        except OSError:
            pass
        finally:
            a.close()
            b.close()
    while not stop.is_set():
        try:
            client, _ = server.accept()
        except TimeoutError:
            continue
        upstream = socket.socket(socket.AF_UNIX)
        upstream.connect(target)
        threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
        threading.Thread(target=pipe, args=(upstream, client), daemon=True).start()
    server.close()


def test_socket_proxy_and_foreign_names_are_refused(campaign, checks):
    """C01/C06: a socket that forwards to the real daemon is not the daemon (unverified-proxy);
    objects with manager-like names but no labels are not adopted."""
    camp, ck = campaign, checks
    work = camp.short_dir("proxy")  # holds the proxy socket
    sock = str(work / "proxy.sock")
    stop = threading.Event()
    threading.Thread(target=_proxy, args=(sock, SOCKET.removeprefix("unix://"), stop), daemon=True).start()
    cfg = work / "docker-config"
    cfg.mkdir(exist_ok=True)
    subprocess.run(["docker", "--config", str(cfg), "context", "create", "ocs-test-proxy", "--docker", f"host=unix://{sock}"],
                   check=True, capture_output=True)
    camp.note(f"docker context ocs-test-proxy in the private config dir {cfg} (not the user's)")
    env = dict(camp.env, DOCKER_CONFIG=str(cfg), OPENCODE_SANDBOX_DOCKER_CONTEXT="ocs-test-proxy")
    ck(subprocess.run(["docker", "--context", "ocs-test-proxy", "version", "--format", "{{.Server.Version}}"], env=env,
                      capture_output=True, text=True, check=False).returncode == 0, "the proxy really reaches the daemon")
    p = camp.ocs("doctor", check=False, env=env)
    ck("unverified-proxy" in p.stdout + p.stderr, f"C01 doctor: unverified-proxy ({(p.stdout + p.stderr).strip()[-200:]})")
    p = camp.ocs("create", "ocs-test-viaproxy", "--no-integrations", check=False, env=env)
    q = camp.ocs("start", "ocs-test-viaproxy", check=False, env=env)
    ck(q.returncode != 0 and "unverified-proxy" in q.stdout + q.stderr, "C01 start through the proxy is refused")
    if p.returncode == 0:
        camp.adopt("ocs-test-viaproxy")
        camp.delete("ocs-test-viaproxy")
    stop.set()

    # C06: a foreign container squatting on the name of a new environment's container
    eid = camp.create("ocs-test-squat", "--no-integrations")
    camp.docker("run", "-d", "--name", f"ocs-{eid}", "--network", "none", "opencode-sandbox:debian", "sleep", "300")
    camp.note(f"foreign container ocs-{eid} (unlabelled squatter, created by the test)")
    p = camp.ocs("start", "ocs-test-squat", check=False)
    ck(p.returncode != 0 and "Traceback" not in p.stdout + p.stderr, f"C06 start refuses a foreign container with its name ({(p.stdout + p.stderr).strip()[-160:]})")
    d = camp.ocs("delete", "ocs-test-squat", "--yes", check=False)
    ck(camp.docker("ps", "-aq", "--filter", f"name=ocs-{eid}").stdout.strip() != "", "C06 delete never removes the foreign container")
    camp.docker("rm", "-f", f"ocs-{eid}")
    camp.note(f"removed foreign container ocs-{eid}")
    if d.returncode != 0:
        camp.delete("ocs-test-squat")
    else:
        camp.ids.pop("ocs-test-squat", None)
