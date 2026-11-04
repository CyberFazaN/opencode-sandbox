"""Whole-config/rootless ownership/recovery and direct launches, both image definitions.

Use the disposable-venv test image-namespace hook for run-owned current-asset builds, or
current bases. No existing base image is replaced or deleted by these tests.
"""
import json
import os
import shlex
from pathlib import Path

import pytest
from campaign import DISTROS

from opencode_sandbox import core as c
from opencode_sandbox import distros


def export_path(camp, name):
    text = camp.ocs("opencode-configs", "status", name).stdout
    return Path(next(line for line in text.splitlines() if line.startswith("/tmp/") and line.endswith("/config")))


@pytest.mark.parametrize("distro", DISTROS)
def test_config_copy_stopped_transfer_drift_reload_and_backup(campaign, checks, distro):
    camp, ck = campaign, checks
    root = camp.config / "opencode-configs"
    root.mkdir(parents=True, exist_ok=True)
    source = camp.tmp("config-source-" + distro)
    (source / "opencode.json").write_text('{"username":"ocs-test-profile"}')
    (source / "command").write_text("#!/bin/sh\nexit 0\n")
    (source / "command").chmod(0o751)
    (source / "relative").symlink_to("../outside")
    (source / "absolute").symlink_to("/not-a-host-mount")
    selected = "ocs-test-profile-" + distro
    (root / selected).symlink_to(source, target_is_directory=True)
    name = "ocs-test-config-" + distro
    eid = camp.create(name, "--distro", distro, "--opencode-config", selected, "--no-agent-context")
    ck(camp.docker("container", "inspect", "ocs-" + eid, check=False).returncode != 0,
       "Copy installed the profile before any environment container/OpenCode launch")
    # Operate while there is no environment container, then while it is stopped.
    camp.ocs("opencode-configs", "export", name)
    exported = export_path(camp, name)
    camp.note(f"config export {exported.parent}")
    ck((exported / "opencode.json").read_text() == '{"username":"ocs-test-profile"}', "Full copied profile is independent and exportable")
    ck((exported / "command").stat().st_mode & 0o777 == 0o751, "Executable mode retained on host")
    ck(os.readlink(exported / "relative") == "../outside" and os.readlink(exported / "absolute") == "/not-a-host-mount", "Nested symlinks copied verbatim, not followed")
    ck(all(p.lstat().st_uid == os.getuid() for p in exported.iterdir()), "Export contents map to the ordinary host user")
    camp.ocs("start", name)
    config = json.loads(camp.sh(eid, "cat /etc/opencode/opencode.json").stdout)
    ck("/run/ocs-agent/context.md" not in config["instructions"], "Disabled context has no system instruction but file is mounted")
    ck(camp.sh(eid, "test -r /run/ocs-agent/context.md").returncode == 0, "Disabled context remains generated and mounted")
    camp.sh(eid, "mkdir -p /root/.local/share/opencode; printf dummy-auth > /root/.local/share/opencode/auth.json")
    camp.ocs("stop", name)
    (exported / "opencode.json").write_text('{"username":"host-edit"}')
    camp.ocs("opencode-configs", "apply", name)
    ck(not camp.inspect(eid)["State"]["Running"], "Stopped Apply did not start the environment")
    camp.ocs("opencode-configs", "apply", name)  # repeated baseline is the installed tree
    camp.ocs("start", name)
    ck("host-edit" in camp.sh(eid, "cat /root/.config/opencode/opencode.json").stdout, "Edited export installed")
    ck(camp.sh(eid, "stat -c '%u:%g %a' /root/.config/opencode/command").stdout.strip() == "0:0 751", "Rootless import ownership is container root:root with exact modes")
    camp.sh(eid, "printf container-drift > /root/.config/opencode/drift")
    conflict = camp.ocs("opencode-configs", "apply", name, check=False)
    ck(conflict.returncode != 0 and "Overwrite Anyway" in conflict.stdout + conflict.stderr, "Container-side drift requires separate explicit consent")
    camp.ocs("opencode-configs", "apply", name, "--overwrite")
    ck(camp.sh(eid, "test ! -e /root/.config/opencode/drift").returncode == 0, "Explicit override replaces the newer tree")
    camp.ocs("opencode-configs", "reload", name, "--empty", "--yes")
    ck(camp.sh(eid, "find /root/.config/opencode -mindepth 1 -print").stdout == "", "Empty clears precisely the global directory")
    ck(camp.sh(eid, "cat /root/.local/share/opencode/auth.json").stdout == "dummy-auth", "Adjacent auth/state remains unchanged")
    camp.ocs("opencode-configs", "reload", name, "--profile", selected, "--yes")
    original = camp.sh(eid, "sha256sum /root/.config/opencode/opencode.json").stdout
    (root / selected).unlink()  # source convenience is not a runtime dependency
    camp.ocs("container", "recreate", name, "--yes")
    ck(camp.sh(eid, "sha256sum /root/.config/opencode/opencode.json").stdout == original, "Imported profile survives recreation with source unavailable")
    ck(export_path(camp, name) == exported, "Export rediscovered using stable identity after recreation")
    camp.ocs("stop", name)
    backup = camp.ocs("backup", "create", name, "--no-system").stdout.strip().splitlines()[-1]
    restored = "ocs-test-config-restored-" + distro
    camp.ocs("backup", "restore", backup, restored)
    rid = camp.adopt(restored)
    ck(camp.metadata(restored)["agent_context_enabled"] is False, "Backup/restore retains context state")
    ck(camp.metadata(restored)["opencode_config_source"] == selected, "Backup retains source identifier without requiring it")
    camp.ocs("start", restored)
    ck("ocs-test-profile" in camp.sh(rid, "cat /root/.config/opencode/opencode.json").stdout, "Home backup contains independent global tree")
    camp.ocs("opencode-configs", "delete-export", name, "--yes")
    camp.delete(restored)
    camp.delete(name)


@pytest.mark.parametrize("distro", DISTROS)
def test_direct_wrapper_context_reconciliation_and_actual_runtime_paths(campaign, checks, distro):
    camp, ck = campaign, checks
    profile = "ocs-test-wrapper-" + distro
    camp.python(f"from opencode_sandbox import core as c; c.profile_set({profile!r},{{'OCS_TEST_DUMMY':'dummy-not-a-credential'}})")
    name = "ocs-test-wrapper-" + distro
    eid = camp.create(name, "--distro", distro, "--profile", profile)
    camp.ocs("start", name)
    wrapped, plain = (camp.sh(eid, command + " --version").stdout.strip() for command in ("ocs-opencode", "opencode"))
    ck(wrapped.startswith("opencode v2.") and wrapped == plain, "Discoverable executable runs actual standalone OpenCode")
    hint = camp.docker("exec", "ocs-" + eid, "bash", "-ic", "exit").stdout
    ck(hint.count("plain opencode does not load it") == 1, "Direct interactive shell shows one accurate hint")
    login = camp.docker("exec", "ocs-" + eid, "bash", "-lic", "exit").stdout
    ck(login.count("plain opencode does not load it") == 1, "Login/profile startup does not duplicate the shell hint")
    quiet = camp.docker("exec", "ocs-" + eid, "bash", "-c", "printf noninteractive").stdout
    ck(quiet == "noninteractive", "No shell hint in scripts")
    loaded = camp.docker("exec", "-e", "OCS_PROVIDER_LOADED=1", "ocs-" + eid, "bash", "-ic", "exit").stdout
    ck("plain opencode" not in loaded, "Already-injected shell suppresses the missing-profile hint")
    camp.sh(eid, "python3 -c " + shlex.quote("import json; p='/etc/opencode/opencode.json'; json.dump({'username':'keep','instructions':['unrelated','/run/ocs-agent/context.md','/run/ocs-agent/context.md']},open(p,'w'))"))
    camp.ocs("start", name)
    document = json.loads(camp.sh(eid, "cat /etc/opencode/opencode.json").stdout)
    ck(document == {"username": "keep", "instructions": ["unrelated", "/run/ocs-agent/context.md"]}, "Every Start deduplicates exact instruction and preserves unrelated values/order")
    camp.ocs("config", "apply", name, "--no-agent-context")
    document = json.loads(camp.sh(eid, "cat /etc/opencode/opencode.json").stdout)
    ck(document == {"username": "keep", "instructions": ["unrelated"]}, "Live toggle removes only context, no process interruption")
    # Do not execute plugins/models. Debug paths inspects this actual OpenCode binary safely.
    paths = camp.sh(eid, "opencode debug paths").stdout
    ck("/root/.config/opencode" in paths and "/root/.local/share/opencode" in paths, "Actual V2 global config and data/auth paths are distinct")
    camp.sh(eid, "printf '{broken' > /etc/opencode/opencode.json")
    failure = camp.ocs("start", name, check=False)
    ck(failure.returncode != 0 and "reconcile" in failure.stdout + failure.stderr, "Malformed system JSON blocks managed start, not overwritten")
    ck(camp.sh(eid, "cat /etc/opencode/opencode.json").stdout == "{broken", "Malformed user-edited system document remains intact")
    camp.delete(name)


@pytest.mark.parametrize("distro", DISTROS)
@pytest.mark.parametrize("phase", ["exchange", "cleanup"])
def test_real_volume_abrupt_helper_death_recovers_switch_and_cleanup(campaign, checks, distro, phase):
    camp, ck = campaign, checks
    name = "ocs-test-config-fault-" + distro
    eid = camp.create(name, "--distro", distro)
    unavailable = camp.ocs("opencode-configs", "reload", name, "--empty", "--yes", check=False)
    ck(unavailable.returncode != 0 and not camp.metadata(name).get("operation"),
       "Unavailable pre-first-start volume refuses Reload without stranding lifecycle recovery")
    camp.ocs("start", name)
    camp.sh(eid, "mkdir -p /root/.config/opencode; printf old > /root/.config/opencode/value")
    camp.ocs("opencode-configs", "export", name)
    exported = export_path(camp, name)
    camp.note(f"config export {exported.parent}")
    (exported / "value").write_text("new")
    camp.ocs("stop", name)
    # Inject only into a run-owned subprocess; the product codec/transport/volume journal is real.
    hook = ("original_exchange=exchange\ndef exchange(a,b):\n original_exchange(a,b)\n os.kill(os.getpid(),9)\n" if phase == "exchange" else
            "original_remove=shutil.rmtree\ndef remove(p):\n original_remove(p)\n os.kill(os.getpid(),9)\nshutil.rmtree=remove\n")
    code = f'''from opencode_sandbox import opencode_configs as oc,core as c
original=oc._helper_source
def injected():
    source=original()
    return source.rsplit('helper_main()',1)[0]+{hook!r}+'\\nhelper_main()\\n'
oc._helper_source=injected
oc.apply(c.resolve({name!r}))
'''
    failed = camp.python(code, check=False)
    ck(failed.returncode != 0 and camp.metadata(name).get("operation") == "opencode-config", "Helper death retains lifecycle-blocking transfer journal")
    blocked = camp.ocs("start", name, check=False)
    ck(blocked.returncode != 0 and "opencode-configs recover" in blocked.stdout + blocked.stderr, "Ordinary start cannot bypass interrupted transfer")
    camp.ocs("opencode-configs", "recover", name)
    camp.ocs("start", name)
    ck(camp.sh(eid, "cat /root/.config/opencode/value").stdout == ("old" if phase == "exchange" else "new"),
       "Real rootless volume recovery restores uncommitted switch or retains committed tree through interrupted cleanup")
    camp.ocs("opencode-configs", "delete-export", name, "--yes")
    camp.delete(name)


@pytest.mark.parametrize("distro", DISTROS)
def test_initial_copy_preserves_image_home_and_refuses_nonfresh_global_config(campaign, checks, distro):
    camp, ck = campaign, checks
    source_name = "ocs-test-home-profile-" + distro
    source = camp.config / "opencode-configs" / source_name
    source.mkdir(parents=True)
    (source / "opencode.json").write_text('{"username":"profile-seed"}')
    data = camp.python("from opencode_sandbox import core as c; print(c.data_id())").stdout.strip()
    images, names = [], []
    try:
        for variant in ("fresh", "nonempty", "overlay"):
            tag = f"ocs-test-home-{camp.run}-{distro}:" + variant
            probe = camp.docker("image", "inspect", tag, check=False)
            assert probe.returncode and "no such image" in probe.stderr.lower(), "Refusing a pre-existing/unknown image"
            context = camp.tmp("home-image-" + distro + "-" + variant)
            content = (f"FROM {distros.get(distro).image}\n"
                       "RUN printf image-home > /root/ocs-config-home-sentinel\n")
            if variant == "nonempty":
                content += "RUN mkdir -p /root/.config/opencode && printf '%s' '{\"username\":\"image-seed\"}' > /root/.config/opencode/opencode.json\n"
            if variant == "overlay": content += 'VOLUME ["/root/.config/opencode"]\n'
            (context / "Dockerfile").write_text(content)
            camp.note("planned image " + tag)
            camp.docker("build", "--network", "none", "--label", f"org.opencode-sandbox.test={camp.run}",
                        "--label", f"{c.DATA_LABEL}={data}", "-t", tag, str(context))
            (info,) = json.loads(camp.docker("image", "inspect", tag).stdout)
            images.append((tag, info["Id"]))
            camp.note(f"image {tag} id={info['Id']}")
        fresh, nonempty = images[0][0], images[1][0]
        name = "ocs-test-home-copy-" + distro
        eid = camp.create(name, "--image", fresh, "--opencode-config", source_name)
        names.append(name)
        camp.ocs("start", name)
        ck(camp.sh(eid, "cat /root/ocs-config-home-sentinel").stdout == "image-home", "Initial Copy retains image-provided non-config home data")
        ck("profile-seed" in camp.sh(eid, "cat /root/.config/opencode/opencode.json").stdout, "Fresh image destination receives the selected profile")
        failed_name = "ocs-test-home-refused-" + distro
        camp.note("planned refused environment " + failed_name)
        failed = camp.ocs("create", failed_name, "--image", nonempty, "--opencode-config", source_name, check=False)
        ck(failed.returncode != 0 and "not fresh" in failed.stdout + failed.stderr, "Image-seeded global config refuses initial Copy instead of merging/overwriting")
        if failed_name in camp.ocs("list").stdout:
            camp.adopt(failed_name)
            names.append(failed_name)
        overlay_name = "ocs-test-home-overlay-" + distro
        camp.note("planned refused environment " + overlay_name)
        overlay = camp.ocs("create", overlay_name, "--image", images[2][0], "--opencode-config", source_name, check=False)
        ck(overlay.returncode != 0 and "overlapping image volume" in overlay.stdout + overlay.stderr,
           "Overlapping image volume refuses transfer before creating an anonymous config tree")
        if overlay_name in camp.ocs("list").stdout:
            camp.adopt(overlay_name)
            names.append(overlay_name)
        local = "ocs-test-home-local-" + distro
        lid = camp.create(local, "--image", nonempty)
        names.append(local)
        camp.ocs("start", local)
        ck("image-seed" in camp.sh(lid, "cat /root/.config/opencode/opencode.json").stdout, "Local preserves an image's existing global config")
        camp.ocs("opencode-configs", "reload", local, "--profile", source_name, "--yes")
        ck("profile-seed" in camp.sh(lid, "cat /root/.config/opencode/opencode.json").stdout, "Explicit Reload can replace the nonfresh global tree")
        ck(camp.sh(lid, "cat /root/ocs-config-home-sentinel").stdout == "image-home", "Reload still leaves adjacent home data intact")
    finally:
        for name in names:
            if name in camp.ids: camp.delete(name)
        for tag, expected in reversed(images):
            (info,) = json.loads(camp.docker("image", "inspect", tag).stdout)
            assert info["Id"] == expected and info["Config"]["Labels"]["org.opencode-sandbox.test"] == camp.run
            camp.docker("image", "rm", tag)
            camp.note("deleted image " + tag)
