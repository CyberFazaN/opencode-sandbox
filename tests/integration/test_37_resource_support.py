"""C05: daemon-reported support is separate from real kernel controller settings.

No host policy/service changes or stress/OOM/fork exhaustion. A disposable network-none
custom-image environment reads its own cgroup v2 files, before/after dynamic settings changes.
"""
import json
import re


def limits(camp, eid):
    values = camp.sh(eid, "cat /sys/fs/cgroup/cpu.max /sys/fs/cgroup/memory.max /sys/fs/cgroup/pids.max").stdout.splitlines()
    quota, period = map(int, values[0].split())
    return quota / period, int(values[1]), int(values[2])


def test_reported_support_and_actual_kernel_limits(campaign, checks):
    camp, ck = campaign, checks
    doctor = camp.ocs("doctor")
    ck(re.search(r"\[passed\]\s+Resource-limit support:.*cgroup v2.*driver systemd", doctor.stdout) is not None,
       "C05 doctor reports required CPU/memory/pids support on the working host")
    ck("enforcement not measured" in doctor.stdout, "C05 doctor does not present reported capability as measured enforcement")
    name = "ocs-test-resource-support"
    eid = camp.create(name, "--image", "ubuntu:24.04", "--no-integrations")
    camp.ocs("config", "apply", name, "--network", "none", "--cpus", "0.5", "--memory", "256m", "--pids", "64", "--yes")
    camp.ocs("start", name)
    ck(limits(camp, eid) == (0.5, 256 * 2**20, 64), "C05 actual cpu.max/memory.max/pids.max match initial settings")
    camp.sh(eid, "echo preserved > /workspace/marker; echo preserved > /root/marker")
    camp.ocs("config", "apply", name, "--cpus", "0.75", "--memory", "320m", "--pids", "96", "--yes")
    ck(limits(camp, eid) == (0.75, 320 * 2**20, 96), "C05 actual kernel limit values change after dynamic config apply")
    ck(camp.sh(eid, "cat /workspace/marker /root/marker").stdout == "preserved\npreserved\n",
       "C05 updating limits preserves workspace and home data")
    result = camp.ocs("check", name, check=False)
    ck(re.search(r"\[passed\]\s+Resource-limit support:", result.stdout) is not None,
       "C05 per-environment check shares the host support diagnostic")
    ck("container configuration matches" in result.stdout and "kernel enforcement not measured" in result.stdout,
       "C05 container settings check is honestly labeled, independent of this test's kernel measurement")
    report = json.loads((camp.data / "environments" / eid / "readiness.json").read_text())
    ck(next(item for item in report["checks"] if item["id"] == "resource-support")["status"] == "passed",
       "C05 cached report stores the final shared support result without schema migration")
    camp.delete(name)
