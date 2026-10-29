"""Subsystems combined, real Docker.

- Arch + AUR + direct workspace + recreation (rows K01, L01, D04)
- backup and restore of a direct-workspace environment, without and with the workspace (E01, L01)
- OpenCode update and rollback with the user's OpenCode configuration and initial integrations (G03, G06, G10)
- settings changes while a shell session is open: in place keeps it, recreation ends it (C05, H05)
- cleanup next to Docker objects the manager does not own (J02, C06)

Direct-workspace folders live below /tmp/opencode/ocs-test-<run>/ (no hidden path component)."""
import hashlib
import json
import os
import re
import secrets
import shutil
from pathlib import Path

import pytest
from campaign import DISTROS, GUARD, MANAGER

pyte = pytest.importorskip("pyte")
from pty_term import Term

CONFIG = "/root/.config/opencode/opencode.json"
MARKERS = "cat /workspace/ws-marker.txt /root/home-marker.txt /etc/ocs-test-system-marker"
WRITE_MARKERS = ("echo ocs-test-marker > /workspace/ws-marker.txt && echo ocs-test-marker > /root/home-marker.txt "
                 "&& echo ocs-test-marker > /etc/ocs-test-system-marker")


def outside(camp, sub):
    root = Path("/tmp/opencode") / f"ocs-test-{camp.run}" / sub
    (root / "project").mkdir(parents=True)
    camp.note(f"host dir {root} (direct workspace {sub})")
    (root / "project" / "host.txt").write_text("from the host\n")
    return root, root / "project"


def listing(folder: Path):
    """Names, modes, owners, sizes, modification times and content hashes (links not followed)."""
    out = {}
    for p in sorted(folder.rglob("*")):
        st = p.lstat()
        digest = hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() and not p.is_symlink() else None
        out[p.relative_to(folder).as_posix()] = (oct(st.st_mode), st.st_uid, st.st_size, st.st_mtime_ns, digest)
    return out


def remove_outside(camp, root):
    shutil.rmtree(root)
    camp.note(f"removed host dir {root}")


@pytest.mark.skipif("arch" not in DISTROS, reason="Arch not selected (OCS_TEST_DISTROS)")
def test_arch_aur_package_in_a_direct_workspace_survives_recreation(campaign, checks):
    camp, ck = campaign, checks
    root, folder = outside(camp, "rf-arch-direct")
    name = "ocs-test-rf-arch-direct"
    eid = camp.create(name, "--distro", "arch", "--workspace-mode", "direct", "--workspace", str(folder),
                      "--yes", "--no-integrations")
    camp.ocs("start", name)
    before = listing(folder)
    aur = camp.sh(eid, "ocs-aur -S --noconfirm bash-pipes > /tmp/aur.log 2>&1", check=False, timeout=1800)
    ck(aur.returncode == 0 and camp.sh(eid, "pacman -Q bash-pipes && command -v pipes.sh", check=False).returncode == 0,
       "K01 AUR package built and installed in an environment with a direct workspace")
    ck(listing(folder) == before, "L01 the AUR build wrote nothing into the direct workspace (builds run in /var/lib/aurbuild)")
    camp.sh(eid, "echo from-container > /workspace/from-container.txt")
    st = (folder / "from-container.txt").stat()
    ck(st.st_uid == os.getuid(), f"L01 a file written by container root is owned by the host user (uid {st.st_uid})")
    camp.ocs("container", "recreate", name, "--yes")
    kept = camp.sh(eid, "pacman -Q bash-pipes && cat /workspace/host.txt /workspace/from-container.txt", check=False)
    ck(kept.returncode == 0 and "from-container" in kept.stdout,
       "D04 recreation keeps the AUR package and mounts the direct folder again")
    ck(camp.ocs("check", name, check=False).returncode == 0, "J01 check passes after the recreation")
    after = listing(folder)
    camp.delete(name)
    ck(listing(folder) == after and (folder / "host.txt").read_text() == "from the host\n",
       "L01 delete leaves the direct folder and its files as they were")
    remove_outside(camp, root)


def test_backup_and_restore_of_a_direct_workspace_environment(campaign, checks):
    camp, ck = campaign, checks
    root, folder = outside(camp, "rf-direct-backup")
    name = "ocs-test-rf-dbk"
    eid = camp.create(name, "--workspace-mode", "direct", "--workspace", str(folder), "--yes", "--no-integrations")
    camp.ocs("start", name)
    camp.sh(eid, WRITE_MARKERS)
    before = listing(folder)
    dest = camp.tmp("rf-direct-backups")
    camp.ocs("backup", "create", name, "--stop", "--destination", str(dest))
    first = max(dest.glob(f"{name}-{eid}-*.ocsbackup"))
    manifest = json.loads((first / "manifest.json").read_text())
    ck(manifest["workspace"] == {**manifest["workspace"], "mode": "direct", "included": False}
       and "workspace.tar.gz" not in manifest["files"], f"E04 default backup of a direct workspace leaves the folder out ({manifest['workspace']})")
    restored = "ocs-test-rf-dbk-r1"
    out = camp.ocs("backup", "restore", str(first), restored)
    rid = camp.adopt(restored)
    ck("managed workspace" in out.stdout + out.stderr, "E01 restore warns that the restored environment has an empty managed workspace")
    camp.ocs("start", restored)
    got = camp.sh(rid, "cat /root/home-marker.txt /etc/ocs-test-system-marker; ls -A /workspace | wc -l", check=False).stdout.split()
    ck(got == ["ocs-test-marker", "ocs-test-marker", "0"], f"E01 home and system layer restored, workspace empty: {got}")
    meta = camp.metadata(restored)
    ck(meta["workspace"]["mode"] == "managed", f"E01 the restored environment is not connected to the folder ({meta['workspace']})")
    ck(listing(folder) == before, "L01 backup and restore did not touch the direct folder")

    camp.ocs("backup", "create", name, "--include-workspace", "--destination", str(dest))
    second = max(dest.glob(f"{name}-{eid}-*.ocsbackup"))
    ck(second != first and "workspace.tar.gz" in json.loads((second / "manifest.json").read_text())["files"],
       "E04 --include-workspace archives the folder")
    restored2 = "ocs-test-rf-dbk-r2"
    camp.ocs("backup", "restore", str(second), restored2)
    rid2 = camp.adopt(restored2)
    camp.ocs("start", restored2)
    got = camp.sh(rid2, MARKERS + " /workspace/host.txt", check=False)
    ck(got.returncode == 0 and got.stdout.count("ocs-test-marker") == 3 and "from the host" in got.stdout,
       "E01 with --include-workspace the folder's files come back in the managed workspace")
    camp.sh(rid2, "echo changed > /workspace/host.txt")
    ck(listing(folder) == before, "L01 a change in the restored copy does not reach the direct folder")
    for env in (restored, restored2, name):
        camp.delete(env)
    ck(listing(folder) == before, "L01 deleting all three environments leaves the folder")
    remove_outside(camp, root)


def test_opencode_update_and_rollback_keep_the_user_configuration(campaign, checks):
    camp, ck = campaign, checks
    name = "ocs-test-rf-ocup"
    eid = camp.create(name)  # default integrations (Context7), written once at the first start
    camp.ocs("start", name)
    camp.sh(eid, f"python3 -c \"import json; p='{CONFIG}'; c=json.load(open(p)); c['theme']='opencode'; "
                 "json.dump(c, open(p, 'w'), indent=1)\" && mkdir -p /root/.config/opencode/agent "
                 "&& printf 'ocs-test agent\\n' > /root/.config/opencode/agent/ocs-test.md")
    files = f"{CONFIG} /root/.config/opencode/agent/ocs-test.md"
    digest = camp.sh(eid, f"sha256sum {files}").stdout
    ck("context7" in camp.sh(eid, f"cat {CONFIG}").stdout, "G10 Context7 written at the first start")
    camp.ocs("stop", name)
    update = camp.ocs("opencode", "update", name, "--version", "2.1.4", "--yes", check=False, timeout=1800)
    ck(update.returncode == 0, f"G03 update to 2.1.4 ({update.stdout.strip()[-200:]} {update.stderr.strip()[-200:]})")
    camp.ocs("start", name)
    ck(camp.sh(eid, "opencode --version").stdout.strip().endswith("2.1.4"), "G03 OpenCode 2.1.4 after the update")
    ck(camp.sh(eid, f"sha256sum {files}").stdout == digest, "G06 the user's OpenCode configuration is unchanged by the update")
    camp.ocs("stop", name)
    camp.ocs("opencode", "rollback", name, "--yes")
    camp.ocs("start", name)
    ck(camp.sh(eid, "opencode --version").stdout.strip().endswith("2.2.0"), "G03 rollback returns to 2.2.0")
    ck(camp.sh(eid, f"sha256sum {files}").stdout == digest, "G06/G10 configuration unchanged by the rollback; integrations not re-applied")
    ck(camp.ocs("agent-context", "verify", name, check=False).returncode == 0, "G05 Agent Context current after update and rollback")
    camp.delete(name)


def test_settings_change_during_an_open_shell_session(campaign, checks):
    camp, ck = campaign, checks
    name = "ocs-test-rf-session"
    eid = camp.create(name, "--no-integrations")
    camp.ocs("start", name)
    camp.sh(eid, WRITE_MARKERS)
    t = Term([*MANAGER, "shell", name], 100, 30, env=camp.env, log=camp.log)
    try:
        ck(t.wait_for(r"root@|# ?$", 60), "H05 shell session open")
        t.send("echo alive-$((40+1))\r", 1)
        ck(t.wait_for(r"alive-41", 15), "shell answers")
        dyn = camp.ocs("config", "apply", name, "--cpus", "1.5", "--yes")
        ck(camp.inspect(eid)["HostConfig"]["NanoCpus"] == 1_500_000_000, f"C05 CPU limit changed in place ({dyn.stdout.strip()[-120:]})")
        t.send("echo alive-$((40+2))\r", 1)
        ck(t.wait_for(r"alive-42", 15) and t.alive, "C05 the open session survives an in-place change")
        plan = camp.ocs("config", "plan", name, "--network", "none").stdout
        ck("sessions and shells in it end" in plan, "C05 the plan says that open sessions end")
        camp.ocs("config", "apply", name, "--network", "none", "--yes")
        code = t.exit_code(90)
        ck(code != "killed (still running)", f"H05 the shell session ended and the manager returned (exit {code})")
        t.snap("after the recreation")
    finally:
        t.close()
    host = camp.inspect(eid)["HostConfig"]
    ck(host["NetworkMode"] == "none" and host["NanoCpus"] == 1_500_000_000, f"C05 both settings in place ({host['NetworkMode']})")
    ck(camp.sh(eid, MARKERS, check=False).stdout.count("ocs-test-marker") == 3, "D04 workspace, home and system layer kept")
    t = Term([*MANAGER, "shell", name], 100, 30, env=camp.env, log=camp.log)
    try:
        ck(t.wait_for(r"root@|# ?$", 60), "H05 a new session opens after the change")
        t.send("exit\r", 1)
        ck(t.exit_code(20) == 0, "H05 and returns")
    finally:
        t.close()
    camp.delete(name)


def test_cleanup_leaves_objects_the_manager_does_not_own(campaign, checks):
    camp, ck = campaign, checks
    tok = secrets.token_hex(4)
    fake, orphan = secrets.token_hex(8), secrets.token_hex(8)
    other_dir = secrets.token_hex(8)
    test_label = ["--label", f"org.opencode-sandbox.test={camp.run}"]
    mine = camp.python(f"import os; os.environ['OPENCODE_SANDBOX_HOME']={str(camp.data)!r}\n"
                       "from opencode_sandbox import core; print(core.data_id())").stdout.strip()
    foreign = {
        "container": [f"ocs-test-rf-unrelated-{tok}", f"ocs-{fake}", f"ocs-test-rf-otherdir-{tok}"],
        "volume": [f"ocs-home-{fake}", f"ocs-test-rf-vol-{tok}"],
        "image": [f"ocs-snapshot:{fake}-ocs-test"],
    }
    camp.note(f"foreign test objects (created and removed by this test): {foreign}; orphan volume ocs-home-{orphan} id={orphan}")
    camp.docker("create", "--name", foreign["container"][0], *test_label, "ubuntu:24.04", "true")
    camp.docker("create", "--name", foreign["container"][1], *test_label, "ubuntu:24.04", "true")
    camp.docker("create", "--name", foreign["container"][2], *test_label, "--label", "org.opencode-sandbox.managed=true",
                "--label", f"org.opencode-sandbox.data-dir={other_dir}", "ubuntu:24.04", "true")
    camp.docker("volume", "create", *test_label, foreign["volume"][0])
    camp.docker("volume", "create", *test_label, "--label", "org.opencode-sandbox.managed=true",
                "--label", f"org.opencode-sandbox.data-dir={other_dir}", foreign["volume"][1])
    camp.docker("tag", "ubuntu:24.04", foreign["image"][0])
    camp.docker("volume", "create", *test_label, "--label", "org.opencode-sandbox.managed=true",
                "--label", f"org.opencode-sandbox.data-dir={mine}", "--label", f"org.opencode-sandbox.id={orphan}",
                f"ocs-home-{orphan}")
    try:
        preview = camp.ocs("disk", "cleanup").stdout
        ck(all(n not in preview for names in foreign.values() for n in names),
           "J02 the preview offers none of the foreign objects for removal")
        ck(f"ocs-home-{orphan}" in preview, "J02 the preview offers this data directory's orphan volume")
        # Earlier tests' deleted environments leave orphans of this data directory (as in Campaign.finish).
        ours = sorted(set(camp.ids.values()) | set(re.findall(r"id=([0-9a-f]{16})", camp.manifest_path.read_text())))
        guard = camp.python(GUARD % (str(camp.data), str(camp.config), ours), check=False)
        ck(guard.returncode == 0, f"cleanup guard: only our objects are eligible ({guard.stdout.strip()})")
        if guard.returncode == 0:
            removed = camp.ocs("disk", "cleanup", "--yes").stdout
            ck(f"ocs-home-{orphan}" in removed and all(n not in removed for names in foreign.values() for n in names),
               "J02 cleanup --yes removes the orphan volume and none of the foreign objects")
        for kind, names in foreign.items():
            for n in names:
                ck(camp.docker(kind, "inspect", n, check=False).returncode == 0, f"J02/C06 {kind} {n} still exists after cleanup")
        ck(camp.docker("volume", "inspect", f"ocs-home-{orphan}", check=False).returncode != 0, "J02 the orphan volume was removed")
        for image in ("opencode-sandbox:debian", "opencode-sandbox:arch", "ubuntu:24.04"):
            ck(camp.docker("image", "inspect", image, check=False).returncode == 0, f"J02 {image} kept")
    finally:
        for n in foreign["container"]:
            camp.docker("rm", n, check=False)
        for n in foreign["volume"] + [f"ocs-home-{orphan}"]:
            camp.docker("volume", "rm", n, check=False)
        camp.docker("image", "rm", foreign["image"][0], check=False)  # untags only: ubuntu:24.04 keeps the image
        camp.note("removed the foreign test objects")


def test_host_commands_ignore_the_workspace_git_configuration(campaign, checks):
    """E08, real container: programs set in the workspace repository's own Git configuration
    (a clean filter, fsmonitor, a diff textconv), written by root in the container, are never run
    by the manager's host commands. The configured programs only create a marker file on the host."""
    camp, ck = campaign, checks
    import subprocess
    src = camp.tmp("rf-e08-src")
    git = ["git", "-c", "user.name=ocs-test", "-c", "user.email=ocs-test@example.invalid", "-C", str(src)]
    subprocess.run(["git", "init", "-q", "-b", "main", str(src)], check=True)
    (src / "a.txt").write_text("base\n")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "base"], check=True)
    marker_dir = Path("/tmp/opencode") / f"ocs-test-{camp.run}" / "e08"
    marker_dir.mkdir(parents=True)
    camp.note(f"host dir {marker_dir} (E08 marker)")
    marker = marker_dir / "marker"
    name = "ocs-test-rf-e08"
    eid = camp.create(name, "--source", str(src), "--no-integrations")
    camp.ocs("start", name)
    program = f"touch {marker} 2>/dev/null; cat"
    camp.sh(eid, "cd /workspace && printf 'a.txt filter=ocs diff=ocs\\n' > .gitattributes "
                 f"&& git config filter.ocs.clean '{program}' && git config diff.ocs.textconv '{program}' "
                 f"&& git config core.fsmonitor 'touch {marker} 2>/dev/null; false' "
                 "&& printf 'changed content and size\\n' > a.txt && git add a.txt && git reset -q")
    ck(not marker.exists(), "E08 setup: nothing on the host yet (the container cannot reach the marker path)")
    dest = camp.tmp("rf-e08-out")
    for args in (["changes", "show", name], ["changes", "export", name, "--destination", str(dest)],
                 ["changes", "bundle", name, "--destination", str(dest)], ["check", name],
                 ["backup", "create", name, "--stop", "--destination", str(dest)]):
        p = camp.ocs(*args, check=False)
        ck(not marker.exists(), f"E08 {' '.join(args[:2])}: no program from the workspace configuration ran (exit {p.returncode})")
    bundles = list(dest.glob("*.ocschanges"))
    if bundles:
        camp.ocs("changes", "inspect", str(bundles[0]), check=False)
        ck(not marker.exists(), "E08 changes inspect: nothing ran")
    # Control: plain host Git in the same workspace does read that configuration, so the checks
    # above are meaningful (the program only creates the marker).
    ws = camp.data / "environments" / eid / "workspace"
    subprocess.run(["git", "-C", str(ws), "status", "--short"], capture_output=True, check=False)
    ck(marker.exists(), "E08 control: plain host Git in the workspace runs the configured program")
    camp.delete(name)
    shutil.rmtree(marker_dir)
    camp.note(f"removed host dir {marker_dir}")
