"""Failure injection on test resources (campaign rows D04, D05, D06, E02, G03, I01, I02).

A `docker` shim on PATH runs the real CLI, except that the Nth call matching OCS_FAULT_MATCH
(a shell `case` pattern over the arguments) SIGKILLs the manager process — before the call, or
after it when OCS_FAULT_WHEN=after. No cleanup handler can run (as after a crash or the OOM
killer); the recovery command named by the product must then restore a usable environment."""
import shutil
import signal
import stat
import time

import pytest

SHIM = """#!/bin/sh
case "$*" in
  $OCS_FAULT_MATCH)
    n=$(( $(cat "$OCS_FAULT_COUNT" 2>/dev/null || echo 0) + 1 )); echo $n > "$OCS_FAULT_COUNT"
    if [ "$n" = "${OCS_FAULT_NTH:-1}" ]; then
      [ "$OCS_FAULT_WHEN" = after ] && "$OCS_REAL_DOCKER" "$@" >/dev/null 2>&1
      echo "FAULT: SIGKILL of the manager (pid $PPID) $OCS_FAULT_WHEN docker $*" >> "$OCS_FAULT_LOG"
      kill -KILL $PPID; exit 137
    fi;;
esac
exec "$OCS_REAL_DOCKER" "$@"
"""
MARKERS = "cat /workspace/ws-marker.txt /root/home-marker.txt /etc/ocs-test-system-marker"


@pytest.fixture(scope="module")
def fault(campaign):
    camp = campaign
    bindir = camp.tmp("fault-bin")
    shim = bindir / "docker"
    shim.write_text(SHIM)
    shim.chmod(0o755)
    real = shutil.which("docker")

    def run(args, match, when="before", nth=1):
        count = bindir / "count"
        count.unlink(missing_ok=True)
        env = dict(camp.env, PATH=f"{bindir}:{camp.env['PATH']}", OCS_REAL_DOCKER=real, OCS_FAULT_MATCH=match,
                   OCS_FAULT_WHEN=when, OCS_FAULT_NTH=str(nth), OCS_FAULT_COUNT=str(count),
                   OCS_FAULT_LOG=str(camp.log_path))
        p = camp.ocs(*args, check=False, env=env)
        return p.returncode
    return run


@pytest.fixture(scope="module")
def env(campaign):
    camp = campaign
    name = "ocs-test-fault"
    eid = camp.create(name, "--no-integrations")
    camp.ocs("start", name)
    camp.sh(eid, "echo ocs-test-marker > /workspace/ws-marker.txt; echo ocs-test-marker > /root/home-marker.txt; "
                 "echo ocs-test-marker > /etc/ocs-test-system-marker")
    yield name, eid
    camp.delete(name)


def intact(camp, eid):
    p = camp.sh(eid, MARKERS, check=False)
    return p.returncode == 0 and p.stdout.count("ocs-test-marker") == 3


def pending(camp, name):
    m = camp.metadata(name)
    return m.get("operation"), m.get("status")


# Each case: the docker call at which the manager dies, and whether the product has journalled
# the operation by then. Before the journal only non-destructive steps have run (a stop, a commit), so
# the environment must be unchanged and the operation can simply be repeated.
@pytest.mark.parametrize("match, when, journal", [
    ("*-H * stop ocs-*", "after", False), ("*-H * commit *", "before", False), ("*-H * commit *", "after", False),
    ("*-H * rm ocs-*", "after", True),
    ("*-H * run -d *", "before", True), ("*-H * run -d *", "after", True),
])
def test_recreate_killed_then_recover(campaign, checks, fault, env, match, when, journal):
    camp, ck = campaign, checks
    name, eid = env
    old = camp.inspect(eid)["Id"]
    rc = fault(["container", "recreate", name, "--yes"], match, when)
    ck(rc == -signal.SIGKILL, f"manager SIGKILLed {when} `{match}` (exit {rc})")
    op, status = pending(camp, name)
    camp.log(f"after the kill: operation={op} status={status}")
    if journal:
        ck(op == "recreate", f"journal recorded ({op})")
        start = camp.ocs("start", name, check=False)
        ck(start.returncode != 0 and "recreate-recover" in start.stdout + start.stderr, "start refuses and names `container recreate-recover`")
        ck("recreate-recover" in camp.ocs("check", name, check=False).stdout, "check names `container recreate-recover`")
        camp.ocs("container", "recreate-recover", name)
    else:
        ck(op is None and camp.inspect(eid)["Id"] == old, "killed before the journal: the container is untouched")
        camp.ocs("container", "recreate", name, "--yes")
    ck(pending(camp, name)[0] is None, "no pending operation afterwards")
    ck(intact(camp, eid), "workspace, home volume and system layer intact")
    ck(camp.inspect(eid)["State"]["Running"], "container running")


def test_recreate_recover_refuses_the_old_running_container(campaign, checks, fault, env):
    """D05: killed before the old container's removal, which is then started again
    from outside the manager: recovery must not take it for the replacement."""
    camp, ck = campaign, checks
    name, eid = env
    old = camp.inspect(eid)["Id"]
    rc = fault(["container", "recreate", name, "--yes"], "*-H * rm ocs-*", "before")
    ck(rc == -signal.SIGKILL and pending(camp, name)[0] == "recreate", f"killed before the removal, journal recorded (exit {rc})")
    camp.docker("start", f"ocs-{eid}")
    refused = camp.ocs("container", "recreate-recover", name, check=False)
    ck(refused.returncode != 0 and "old container" in refused.stdout + refused.stderr
       and f"opencode-sandbox stop {name}" in refused.stdout + refused.stderr and pending(camp, name)[0] == "recreate",
       "recreate-recover refuses the old running container and keeps the journal")
    camp.ocs("stop", name)
    refused = camp.ocs("container", "recreate-recover", name, check=False)
    ck(refused.returncode != 0 and "still exists" in refused.stdout + refused.stderr, "a stopped old container: removal asked for")
    camp.docker("rm", f"ocs-{eid}")
    camp.ocs("container", "recreate-recover", name)
    ck(pending(camp, name)[0] is None and camp.inspect(eid)["Id"] != old and camp.inspect(eid)["State"]["Running"],
       "after the removal recovery creates and starts the replacement")
    ck(intact(camp, eid), "workspace, home volume and system layer intact")


# `journal`: the operation recorded when the manager dies: the recreation's own journal, or the
# start that follows it (the new container is created by `start`, which a later start finishes).
@pytest.mark.parametrize("match, when, journal", [
    ("*-H * commit *", "after", None), ("*-H * rm ocs-*", "after", "runtime-recreate"),
    ("*-H * run -d *", "before", "start"), ("*-H * run -d *", "after", "start"),
])
def test_config_apply_killed_then_recover(campaign, checks, fault, env, match, when, journal):
    camp, ck = campaign, checks
    name, eid = env
    target = "none" if camp.metadata(name)["runtime"]["network"] == "bridge" else "bridge"
    rc = fault(["config", "apply", name, "--network", target, "--yes"], match, when)
    ck(rc == -signal.SIGKILL, f"manager SIGKILLed {when} `{match}` during config apply (exit {rc})")
    op, status = pending(camp, name)
    camp.log(f"after the kill: operation={op} status={status}")
    if journal == "runtime-recreate":
        ck(op == journal, f"journal recorded ({op})")
        start = camp.ocs("start", name, check=False)
        ck(start.returncode != 0 and "config recover" in start.stdout + start.stderr, "start refuses and names `config recover`")
        camp.ocs("config", "recover", name)
        camp.ocs("start", name)
    elif journal == "start":
        ck(op == journal, f"interrupted start recorded ({op}, {status})")
        ck(camp.ocs("start", name, check=False).returncode == 0, "the next start finishes it")
    else:
        ck(op is None and camp.inspect(eid)["HostConfig"]["NetworkMode"] != target, "killed before the journal: old container, old settings")
        camp.ocs("config", "apply", name, "--network", target, "--yes")
        camp.ocs("start", name)
    info = camp.inspect(eid)
    ck(info["HostConfig"]["NetworkMode"] == target and camp.metadata(name)["runtime"]["network"] == target,
       f"the requested network {target} is in effect")
    ck(pending(camp, name)[0] is None and intact(camp, eid), "no pending operation; data intact")


def test_backup_killed_leaves_only_a_temporary_directory(campaign, checks, fault, env):
    camp, ck = campaign, checks
    name, eid = env
    rc = fault(["backup", "create", name, "--stop", "--no-system"], "*-H * run *", "after")
    ck(rc == -signal.SIGKILL, f"manager SIGKILLed after the first helper run of a backup (exit {rc})")
    leftovers = list((camp.data / "backups").glob(".backup-*"))
    ck(len(leftovers) == 1, f"one temporary .backup-* directory left ({len(leftovers)})")
    ck(not list((camp.data / "backups").glob("*.ocsbackup")), "no published (partial) backup")
    preview = camp.ocs("disk", "cleanup").stdout
    ck(".backup-" in preview, "disk cleanup lists the unfinished backup directory")
    camp.ocs("disk", "cleanup", "--yes")
    ck(not list((camp.data / "backups").glob(".backup-*")), "disk cleanup removed it")
    helpers = camp.docker("ps", "-aq", "--filter", "label=org.opencode-sandbox.helper").stdout.split()
    ck(helpers == [], f"no helper container left ({helpers})")
    camp.ocs("backup", "create", name, "--no-system")
    ck(len(list((camp.data / "backups").glob(f"{name}-*.ocsbackup"))) == 1, "a new backup succeeds afterwards")
    camp.ocs("start", name)
    ck(intact(camp, eid), "environment intact")


def test_backup_sigterm_runs_cleanup(campaign, checks, env):
    camp, ck = campaign, checks
    name, _eid = env
    camp.ocs("stop", name)
    proc = camp.popen("backup", "create", name)
    seen = camp.wait_for(lambda: list((camp.data / "backups").glob(".backup-*")), timeout=120, step=0.02)
    ck(bool(seen), "backup in progress (temporary directory exists)")
    time.sleep(0.5)
    rc, _out = camp.kill(proc, signal.SIGTERM)
    ck(rc != 0, f"SIGTERM ends the backup (exit {rc})")
    ck(not list((camp.data / "backups").glob(".backup-*")), "SIGTERM: the temporary directory was removed")
    ck(camp.docker("ps", "-aq", "--filter", "label=org.opencode-sandbox.helper").stdout.split() == [], "no helper container left")
    ck(pending(camp, name)[0] is None, "no pending operation")


@pytest.mark.parametrize("match, when, way", [("*-H * volume create *", "after", "rollback"),
                                              ("*-H * image load *", "before", "rollback"),
                                              ("*-H * volume create *", "after", "resume")])
def test_restore_killed_then_rollback_or_resume(campaign, checks, fault, env, match, when, way):
    camp, ck = campaign, checks
    name, eid = env
    backups = sorted((camp.data / "backups").glob(f"{name}-*.ocsbackup"))
    if not backups or "image load" in match:
        camp.ocs("stop", name)
        camp.ocs("backup", "create", name)  # with the system image, so `image load` happens
        backups = sorted((camp.data / "backups").glob(f"{name}-*.ocsbackup"))
    target = f"ocs-test-frest-{way}-{'load' if 'load' in match else 'vol'}"
    rc = fault(["backup", "restore", str(backups[-1]), target], match, when)
    ck(rc == -signal.SIGKILL, f"manager SIGKILLed {when} `{match}` during restore (exit {rc})")
    rid = camp.adopt(target)
    m = camp.metadata(target)
    ck(m.get("operation") == "restore", f"restore journal recorded (status {m.get('status')}, stage {m.get('restore_stage')})")
    start = camp.ocs("start", target, check=False)
    ck(start.returncode != 0 and "restore-resume" in start.stdout + start.stderr, "start refuses and names the restore commands")
    if way == "rollback":
        camp.ocs("backup", "restore-rollback", target, "--yes")
        camp.ids.pop(target, None)
        ck(target not in camp.ocs("list").stdout, "rollback removed the incomplete environment")
        vols = camp.docker("volume", "ls", "-q", "--filter", f"name=ocs-stage-{rid}").stdout.split()
        ck(vols == [], f"rollback removed the staging volume ({vols})")
    else:
        resumed = camp.ocs("backup", "restore-resume", target, check=False)
        if resumed.returncode == 0:
            camp.ocs("backup", "restore-check", target)
            ck(intact(camp, rid), "resumed restore has the data")
        else:
            ck("rollback" in resumed.stdout + resumed.stderr, f"resume refuses safely and names rollback: {resumed.stdout.strip()[-200:]}")
            camp.ocs("backup", "restore-rollback", target, "--yes")
            camp.ids.pop(target, None)
        if target in camp.ocs("list").stdout:
            camp.delete(target)
    camp.ocs("start", name)
    ck(intact(camp, eid), "the source environment is untouched")


@pytest.mark.parametrize("match, when, journal", [
    ("*-H * commit *", "after", False), ("*-H * start *", "before", True), ("*-H * exec *", "before", True),
])
def test_opencode_update_killed_then_rolled_back(campaign, checks, fault, env, match, when, journal):
    """No download happens: the manager dies before the install script runs."""
    camp, ck = campaign, checks
    name, eid = env
    camp.ocs("stop", name)
    rc = fault(["opencode", "update", name, "--version", "2.1.4", "--yes"], match, when)
    ck(rc == -signal.SIGKILL, f"manager SIGKILLed {when} `{match}` during opencode update (exit {rc})")
    op, status = pending(camp, name)
    camp.log(f"after the kill: operation={op} status={status}")
    if journal:
        ck(op == "opencode-update", f"update journal recorded ({op})")
        start = camp.ocs("start", name, check=False)
        ck(start.returncode != 0 and "update-recover" in start.stdout + start.stderr, "start refuses and names `opencode update-recover`")
        camp.ocs("opencode", "update-recover", name)
    else:
        ck(op is None, "killed before the journal: nothing to recover")
    ck(pending(camp, name)[0] is None, "no pending operation afterwards")
    camp.ocs("start", name)
    version = camp.sh(eid, "opencode --version").stdout.strip()
    ck("2.2.0" in version, f"the version from before the update ({version})")
    ck(intact(camp, eid), "data intact")


def test_delete_killed_midway_can_be_repeated(campaign, checks, fault):
    camp, ck = campaign, checks
    name = "ocs-test-fdel"
    eid = camp.create(name, "--no-integrations")
    camp.ocs("start", name)
    rc = fault(["delete", name, "--yes"], "*-H * rm -f *", "after")
    ck(rc == -signal.SIGKILL, f"manager SIGKILLed after removing the container (exit {rc})")
    again = camp.ocs("delete", name, "--yes", check=False)
    if again.returncode != 0:
        camp.ocs("repair", name, check=False)
        again = camp.ocs("delete", name, "--yes", check=False)
    ck(again.returncode == 0, f"delete can be repeated ({again.stdout.strip()[-200:]} {again.stderr.strip()[-200:]})")
    camp.ids.pop(name, None)
    vols = camp.docker("volume", "ls", "-q", "--filter", f"name=ocs-home-{eid}").stdout.split()
    ck(vols == [] and not (camp.data / "environments" / eid).exists(), "volume and directory gone")


def test_docker_unavailable_and_low_space_refuse_cleanly(campaign, checks, env):
    camp, ck = campaign, checks
    name, _eid = env
    missing = dict(camp.env, OPENCODE_SANDBOX_DOCKER_CONTEXT="ocs-test-no-such-context")
    for args in (["start", name], ["status", name], ["disk", "usage"]):
        p = camp.ocs(*args, check=False, env=missing)
        text = p.stdout + p.stderr
        ck((p.returncode == 8 or args[0] == "status") and "Traceback" not in text and "not-configured" in text,
           f"{' '.join(args)} with a context that does not exist: not-configured, exit 8 (or a report) "
           f"(exit {p.returncode}: {text.strip()[-160:]})")
    ck(camp.ocs("list", check=False, env=missing).returncode == 0, "list works without Docker")
    foreign = dict(camp.env, DOCKER_HOST="tcp://127.0.0.1:9", DOCKER_CONTEXT="default")
    ck(camp.ocs("status", name, check=False, env=foreign).returncode == 0, "DOCKER_HOST/DOCKER_CONTEXT pointing elsewhere are ignored")
    doctor = camp.ocs("doctor", check=False, env=foreign)
    ck("DOCKER_HOST is set but ignored" in doctor.stdout + doctor.stderr, "doctor notes the ignored DOCKER_HOST")
    images = set(camp.docker("image", "ls", "-q").stdout.split())
    low = dict(camp.env, OPENCODE_SANDBOX_DOCKER_RESERVE_BYTES=str(10**15))
    p = camp.ocs("container", "snapshot", name, check=False, env=low)
    ck(p.returncode != 0 and "free disk space" in p.stdout + p.stderr, "snapshot refused below the space reserve")
    ck(set(camp.docker("image", "ls", "-q").stdout.split()) == images, "nothing was committed")


def test_unreadable_workspace_file_is_reported(campaign, checks, env):
    camp, ck = campaign, checks
    name, eid = env
    camp.ocs("stop", name, check=False)
    camp.ocs("start", name)
    camp.sh(eid, "echo secret > /workspace/private.txt && chmod 000 /workspace/private.txt")
    camp.ocs("stop", name)
    p = camp.ocs("backup", "create", name, "--no-system", check=False)
    text = p.stdout + p.stderr
    ws = camp.data / "environments" / eid / "workspace" / "private.txt"
    ck(stat.S_IMODE(ws.stat().st_mode) == 0 and p.returncode != 0 and "private.txt" in text and "Traceback" not in text,
       f"backup names the unreadable file ({text.strip()[-200:]})")
    camp.ocs("start", name)
    camp.sh(eid, "rm /workspace/private.txt")
    for b in (camp.data / "backups").glob(f"{name}-*.ocsbackup"):
        shutil.rmtree(b)
        camp.note(f"removed backup {b}")


def test_concurrent_operations_serialize(campaign, checks, env):
    """D07: operations on one environment from several processes at once; the same name twice."""
    camp, ck = campaign, checks
    name, eid = env
    camp.ocs("start", name, check=False)
    procs = [camp.popen("container", "recreate", name, "--yes"), camp.popen("container", "recreate", name, "--yes"),
             camp.popen("config", "apply", name, "--pids", "1500", "--yes"), camp.popen("stop", name)]
    results = [(p.wait(timeout=600), p.stdout.read()) for p in procs]
    camp.log("concurrent results: " + repr(results))
    ck(all("Traceback" not in out for _, out in results), f"no crash ({[rc for rc, _ in results]})")
    pending_refusals = [out for rc, out in results if rc != 0 and "pending operation" in out]
    ck(all("wait until it finishes" in out for out in pending_refusals),
       f"a refusal during a running operation says to wait, not only to recover ({len(pending_refusals)})")
    containers = camp.docker("ps", "-a", "--filter", f"label=org.opencode-sandbox.id={eid}", "--format", "{{.Names}}").stdout.split()
    ck(containers == [f"ocs-{eid}"], f"exactly one container afterwards ({containers})")
    ck(pending(camp, name)[0] is None, "no operation left pending")
    camp.ocs("start", name)
    ck(intact(camp, eid), "data intact")
    ck(camp.metadata(name)["runtime"]["pids"] == camp.inspect(eid)["HostConfig"]["PidsLimit"], "metadata and container agree on the settings")
    same = [camp.popen("create", "ocs-test-twin", "--no-integrations") for _ in range(3)]
    codes = [p.wait(timeout=300) for p in same]
    listed = [line for line in camp.ocs("list").stdout.splitlines() if line.startswith("ocs-test-twin ")]
    ck(codes.count(0) == 1 and len(listed) == 1, f"the same name created once ({codes}, {len(listed)} listed)")
    if listed:
        camp.adopt("ocs-test-twin")
        camp.delete("ocs-test-twin")
