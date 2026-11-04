"""Real retained Debian/Arch binary evidence, stopped checks, updates and checkpoint recovery.

Only campaign-manifested environments; existing bases are read-only inputs. Installs download
explicit compatible versions, no model/provider calls or host OpenCode. Retained OS is not a
current-definition rebuild/freshness claim.
"""
import json

import pytest
import test_30_faults
from campaign import DISTROS

pytestmark = [pytest.mark.real_session, pytest.mark.real_identity]

fault = test_30_faults.fault


@pytest.mark.parametrize("distro", DISTROS)
def test_observations_follow_actual_binary_and_lifecycle(campaign, checks, fault, distro):
    camp, ck = campaign, checks
    name = f"ocs-test-evidence-{distro}"
    eid = camp.create(name, "--distro", distro)
    camp.ocs("start", name)
    camp.sh(eid, "umask 022; mkdir -p /root/.config/opencode; echo '{}' > /root/.config/opencode/opencode.json; "
                 "echo evidence-marker > /etc/ocs-test-evidence; echo home-marker > /root/ocs-test-evidence; "
                 "echo workspace-marker > /workspace/ocs-test-evidence")
    config = camp.sh(eid, "sha256sum /root/.config/opencode/opencode.json").stdout
    version = camp.sh(eid, "opencode --version").stdout.strip().split()[-1].removeprefix("v")
    ck(version == "2.2.0", f"retained {distro} fixture has expected actual binary {version}")
    initial = camp.inspect(eid)
    observed = json.loads(camp.python(f"from opencode_sandbox import core as c, opencode_versions as v; "
                                     f"import json; print(json.dumps(v.environment_version(c.resolve({name!r}))))").stdout)
    ck(observed["version"] == version and observed["verification"] == "verified"
       and observed["observation"]["identity"]["container"] == initial["Id"]
       and observed["observation"]["identity"]["image"] == initial["Image"], "actual runtime evidence binds full immutable IDs")
    camp.ocs("stop", name)
    path = camp.data / "environments" / eid / "metadata.json"
    before, stopped = path.read_bytes(), camp.inspect(eid)
    report = camp.ocs("opencode", "versions").stdout
    ck(version in report and "last verified" in report and "not a fresh check" in report, "stopped report retains dated evidence")
    after = camp.inspect(eid)
    ck(not after["State"]["Running"] and after["State"]["StartedAt"] == stopped["State"]["StartedAt"]
       and path.read_bytes() == before, "ordinary stopped check neither starts nor mutates authoritative metadata")

    unchanged = camp.ocs("opencode", "update", name, "--version", version, "--yes").stdout
    ck("already installed; nothing changed" in unchanged and not camp.inspect(eid)["State"]["Running"], "same-version verification is a stopped no-install result")
    camp.ocs("opencode", "policy-set", name, "pinned", "--version", version)
    refused = camp.ocs("opencode", "update", name, "--version", "2.1.4", "--yes", check=False)
    ck(refused.returncode != 0 and "pinned" in refused.stdout + refused.stderr, "exact-target planning cannot bypass a pin")
    camp.ocs("opencode", "policy-set", name, "manual")

    updated = camp.ocs("opencode", "update", name, "--version", "2.1.4", "--yes", timeout=1800).stdout
    ck("Updated OpenCode 2.2.0 -> 2.1.4" in updated and not camp.inspect(eid)["State"]["Running"], "explicit compatible alternative installs and finishes stopped")
    ck("2.1.4" in camp.ocs("opencode", "versions").stdout, "verified update result becomes stopped evidence, not inherited 2.2.0 build label")
    camp.ocs("opencode", "rollback", name, "--yes")
    unknown = camp.ocs("opencode", "status", name).stdout
    ck("'version': None" in unknown, "checkpoint rollback invalidates prior container observations")
    camp.ocs("start", name)
    ck(camp.inspect(eid)["Id"] != initial["Id"] and "2.2.0" in camp.ocs("opencode", "versions").stdout, "replacement is freshly verified, not inferred from update history")
    ck(camp.sh(eid, "sha256sum /root/.config/opencode/opencode.json").stdout == config, "user OpenCode configuration survives update/rollback")

    camp.ocs("stop", name)
    rc = fault(["opencode", "update", name, "--version", "2.1.4", "--yes"], "*-H * exec *ocs-install-opencode*", "before")
    ck(rc == -9 and camp.metadata(name).get("operation") == "opencode-update", "SIGKILL before install retains authoritative update journal")
    recovery = camp.ocs("opencode", "versions").stdout
    ck("Unknown" in recovery and "pending operation" in recovery, "interrupted update cannot publish old or target version as verified")
    camp.ocs("stop", name)
    camp.ocs("opencode", "update-recover", name)
    ck("'version': None" in camp.ocs("opencode", "status", name).stdout, "recovery does not turn checkpoint metadata into runtime evidence")
    camp.ocs("start", name)
    ck("2.2.0" in camp.ocs("opencode", "versions").stdout, "recovered actual binary verified")
    markers = camp.sh(eid, "cat /etc/ocs-test-evidence /root/ocs-test-evidence /workspace/ocs-test-evidence").stdout
    ck(all(value in markers for value in ("evidence-marker", "home-marker", "workspace-marker")), "system/home/workspace markers survive failure recovery")

    camp.ocs("stop", name)
    camp.ocs("config", "apply", name, "--network", "none", "--yes")
    ck("'version': None" in camp.ocs("opencode", "status", name).stdout, "runtime recreation invalidates observations before replacement exists")
    camp.ocs("start", name)
    camp.ocs("stop", name)
    ck("Unknown" in camp.ocs("opencode", "versions").stdout, "new stopped container is Unknown until a real runtime probe")
    refused = camp.ocs("opencode", "update", name, "--version", "2.2.0", "--yes", check=False)
    ck(refused.returncode != 0 and "network=none" in refused.stdout + refused.stderr
       and not camp.inspect(eid)["State"]["Running"], "discovery/target changes preserve network-none update refusal")
    camp.ocs("backup", "create", name, "--no-system")
    archive = max((camp.data / "backups").glob(f"{name}-*.ocsbackup"))
    camp.note(f"backup {archive}")
    restored = name + "-restore"
    camp.ocs("backup", "restore", str(archive), restored)
    restored_id = camp.adopt(restored)
    ck(restored_id != eid and "'version': None" in camp.ocs("opencode", "status", restored).stdout,
       "file-only restore gets a new identity and no inherited runtime evidence")
    camp.ocs("start", restored)
    camp.ocs("stop", restored)
    ck("Unknown" in camp.ocs("opencode", "versions").stdout, "restored stopped binary remains Unknown until explicitly probed")
    camp.delete(restored)
    camp.delete(name)
