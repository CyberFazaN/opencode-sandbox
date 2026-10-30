"""Base-image replacement compatibility (D-051; D03/D04, E01/E09, G02/G03/G05/G06).

OCS_TEST_LEGACY_MANAGER points to a separately installed pre-change manager that uses the
retained Debian 12 base tag. The current manager can use a disposable tag namespace supplied
by the test host; the product has no image-repository override. No existing base tag moves.
"""
import hashlib
import os
import shlex
import shutil

import pytest

PATHS = "/workspace/ocs-test-bytes /root/ocs-test-bytes /etc/ocs-test-bytes"
CONFIG = "/root/.config/opencode/opencode.json"
DATA = bytes(range(256)) * 7
CONFIG_DATA = '{"model":"ocs-test-retained/model","mcp":{}}\n'


def write_state(camp, eid):
    camp.sh(eid, "python3 -c \"from pathlib import Path; data=bytes(range(256))*7; "
                 "[Path(p).write_bytes(data) for p in '/workspace/ocs-test-bytes /root/ocs-test-bytes /etc/ocs-test-bytes'.split()]\"")
    camp.docker("exec", "-i", f"ocs-{eid}", "sh", "-c", f"mkdir -p /root/.config/opencode; cat > {CONFIG}", input=CONFIG_DATA)


def state_matches(camp, eid, *, system=True):
    paths = PATHS if system else "/workspace/ocs-test-bytes /root/ocs-test-bytes"
    p = camp.sh(eid, "sha256sum " + paths, check=False)
    lines = p.stdout.splitlines()
    return p.returncode == 0 and len(lines) == (3 if system else 2) and all(
        line.split()[0] == hashlib.sha256(DATA).hexdigest() for line in lines)


def config_matches(camp, eid):
    return camp.sh(eid, f"cat {CONFIG}", check=False).stdout == CONFIG_DATA


def os_is(camp, eid, version):
    text = camp.sh(eid, "cat /etc/os-release").stdout
    return f'VERSION_ID="{version}"' in text or f"VERSION_ID={version}\n" in text


def context_is(camp, name, version):
    text = camp.ocs("agent-context", "show", name).stdout
    other = "13" if version == "12" else "12"
    return f"Base OS: Debian {version}." in text and f"Base OS: Debian {other}." not in text


def version_roundtrip(camp, ck, name, eid, os_version):
    camp.ocs("stop", name)
    camp.ocs("opencode", "update", name, "--version", "2.1.4", "--yes", timeout=1200)
    camp.ocs("start", name)
    ck("2.1.4" in camp.sh(eid, "opencode --version").stdout and state_matches(camp, eid)
       and config_matches(camp, eid), f"G02 {os_version}: actual OpenCode replacement preserves all bytes/config")
    camp.ocs("stop", name)
    camp.ocs("opencode", "rollback", name, "--yes")
    camp.ocs("start", name)
    ck("2.2.0" in camp.sh(eid, "opencode --version").stdout and state_matches(camp, eid)
       and config_matches(camp, eid) and os_is(camp, eid, os_version) and context_is(camp, name, os_version),
       f"G03 {os_version}: rollback preserves OS, bytes/config and truthful provenance")
    ck(camp.ocs("agent-context", "verify", name, check=False).returncode == 0,
       f"G05 {os_version}: recreated checkpoint guidance is current without re-provisioning")


def test_new_debian_definition_update_and_rollback(campaign, checks):
    camp, ck = campaign, checks
    name = "ocs-test-definition13"
    eid = camp.create(name, "--distro", "debian", "--no-integrations")
    camp.ocs("start", name)
    write_state(camp, eid)
    ck(os_is(camp, eid, "13") and context_is(camp, name, "13"), "C02/G05 new base is actually Debian 13 and guidance says 13")
    version_roundtrip(camp, ck, name, eid, "13")
    camp.delete(name)


def test_prechange_container_and_backups_keep_debian12(campaign, checks):
    legacy = os.environ.get("OCS_TEST_LEGACY_MANAGER")
    if not legacy:
        pytest.skip("retained Debian 12 row: set OCS_TEST_LEGACY_MANAGER to the separately installed pre-change manager")
    camp, ck = campaign, checks
    old_env = {k: v for k, v in camp.env.items() if k not in ("OCS_TEST_IMAGE_REPOSITORY", "PYTHONPATH")}
    old_cmd = shlex.split(legacy)

    def old(*args):
        return camp._run([*old_cmd, *args], check=True, env=old_env)

    name = "ocs-test-retained12"
    old("create", name, "--no-integrations")
    eid = camp.adopt(name)
    old("start", name)
    write_state(camp, eid)
    camp.sh(eid, "apt-get update -qq && apt-get install -y -qq --no-install-recommends tree >/dev/null", timeout=1200)
    original_container = camp.inspect(eid)["Id"]
    ck(os_is(camp, eid, "12") and state_matches(camp, eid), "D03 real pre-change manager created a labelled Debian 12 environment")
    old("stop", name)
    old("backup", "create", name)
    system_backup = max((camp.data / "backups").glob(f"{name}-{eid}-*.ocsbackup"))
    camp.note(f"backup {system_backup} (pre-change manager, with Debian 12 system)")
    old("backup", "create", name, "--no-system")
    no_system = max((camp.data / "backups").glob(f"{name}-{eid}-*.ocsbackup"))
    assert no_system != system_backup
    camp.note(f"backup {no_system} (pre-change manager, explicit no-system)")

    metadata = camp.data / "environments" / eid / "metadata.json"
    before = metadata.read_bytes()
    status = camp.ocs("status", name).stdout
    ck("Distribution: Debian 12 (base image labels)" in status and context_is(camp, name, "12")
       and metadata.read_bytes() == before, "G05 retained stopped container: status/context use old labels with no metadata migration")
    camp.ocs("start", name)
    ck(camp.inspect(eid)["Id"] == original_container and os_is(camp, eid, "12") and state_matches(camp, eid),
       "D03 manager upgrade/start did not replace or upgrade the old container")
    camp.ocs("agent-context", "refresh", name)
    ck(context_is(camp, name, "12") and config_matches(camp, eid), "G05/G06 refreshed old guidance is truthful; user config unchanged")
    camp.ocs("container", "recreate", name, "--yes")
    ck(os_is(camp, eid, "12") and state_matches(camp, eid) and context_is(camp, name, "12")
       and config_matches(camp, eid), "D04 old recreation retains Debian 12, system/workspace/home bytes and config")
    camp.ocs("config", "apply", name, "--network", "none", "--yes")
    ck(os_is(camp, eid, "12") and state_matches(camp, eid) and context_is(camp, name, "12")
       and "tree" in camp.sh(eid, "dpkg-query -W tree").stdout, "D04 old settings recreation retains OS, data and installed package")

    restored = "ocs-test-retained-rest12"
    camp.ocs("backup", "restore", str(system_backup), restored)
    rid = camp.adopt(restored)
    camp.ocs("backup", "restore-check", restored)
    ck(os_is(camp, rid, "12") and state_matches(camp, rid) and config_matches(camp, rid)
       and context_is(camp, restored, "12"), "E01 old-manager system backup restores Debian 12 and every marker/config")

    rebased = "ocs-test-retained-nosystem13"
    camp.ocs("backup", "restore", str(no_system), rebased)
    nid = camp.adopt(rebased)
    camp.ocs("backup", "restore-check", rebased)
    ck(os_is(camp, nid, "13") and state_matches(camp, nid, system=False) and config_matches(camp, nid)
       and context_is(camp, rebased, "13") and camp.sh(nid, "test ! -e /etc/ocs-test-bytes", check=False).returncode == 0,
       "E01 explicit no-system backup restores workspace/home on current Debian 13, not a hidden OS migration")

    camp.ocs("stop", name)
    camp.ocs("config", "apply", name, "--network", "bridge", "--yes")
    assert camp.docker("container", "inspect", f"ocs-{eid}", check=False).returncode != 0
    camp.ocs("backup", "create", name)
    derived = max((camp.data / "backups").glob(f"{name}-{eid}-*.ocsbackup"))
    camp.note(f"backup {derived} (old derived image, no container)")
    again = "ocs-test-retained-derived12"
    camp.ocs("backup", "restore", str(derived), again)
    aid = camp.adopt(again)
    camp.ocs("backup", "restore-check", again)
    ck(os_is(camp, aid, "12") and state_matches(camp, aid) and context_is(camp, again, "12"),
       "E09 no-container derived-image backup/restore keeps the old OS and bytes")
    camp.ocs("start", name)
    version_roundtrip(camp, ck, name, eid, "12")
    for item in (again, rebased, restored, name):
        camp.delete(item)
    for backup in (system_backup, no_system, derived):
        shutil.rmtree(backup)
        camp.note(f"removed backup {backup}")


def test_other_metadata_schema_is_not_migrated_or_deleted(campaign, checks):
    camp, ck = campaign, checks
    folder = camp.data / "environments" / "ffffffffffffffff"
    assert not folder.exists()
    camp.note(f"host schema fixture {folder} (dummy schema 1 metadata only, no Docker resources)")
    folder.mkdir(mode=0o700, parents=True)
    path = folder / "metadata.json"
    original = b'{"schema":1,"id":"ffffffffffffffff","name":"ocs-test-foreignschema"}\n'
    path.write_bytes(original)
    listed = camp.ocs("list", check=False)
    refused = camp.ocs("delete", "ocs-test-foreignschema", "--yes", check=False)
    ck("ignoring" in (listed.stdout + listed.stderr).lower() and refused.returncode != 0
       and path.read_bytes() == original, "D03 another metadata schema is ignored, not migrated or deleted")
    path.unlink()  # only this manifested dummy fixture, never product cleanup of another schema
    folder.rmdir()
    camp.note(f"removed dummy host schema fixture {folder}")
