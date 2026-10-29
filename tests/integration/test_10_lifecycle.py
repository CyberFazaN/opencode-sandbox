"""Lifecycle, persistence, isolation, settings, Git transfer and backup/restore on each distribution
(campaign rows D01–D04, C03, C04, C05, E01, E04–E07, E09–E11, F04)."""
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
from campaign import DISTROS

GIT = ["git", "-c", "user.name=ocs-test", "-c", "user.email=ocs-test@example.invalid"]
MARKERS = "cat /workspace/ws-marker.txt /root/home-marker.txt /etc/ocs-test-system-marker"


def mtimes(root: Path):
    """Whole-second modification times below root (links not followed), without .git."""
    return {p.relative_to(root).as_posix(): int(p.lstat().st_mtime) for p in sorted(root.rglob("*"))
            if not p.relative_to(root).as_posix().startswith(".git")}


def tree(root: Path):
    """Names, types, modes, contents (hash) and symlink targets below root, without .git."""
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/"):
            continue
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode):
            out[rel] = ("link", os.readlink(path))
        elif stat.S_ISDIR(st.st_mode):
            out[rel] = ("dir", oct(st.st_mode & 0o777))
        else:
            out[rel] = ("file", oct(st.st_mode & 0o777), hashlib.sha256(path.read_bytes()).hexdigest()[:16])
    return out


def source_repo(camp, distro):
    src = camp.tmp(f"src-{distro}")
    subprocess.run(["git", "init", "-q", "-b", "main", str(src)], check=True)
    (src / "a b.txt").write_text("spaces\n")
    (src / "-dash.txt").write_text("dash\n")
    (src / "ü-unicode.txt").write_text("unicode\n")
    (src / "run.sh").write_text("#!/bin/sh\necho ok\n")
    (src / "run.sh").chmod(0o755)
    (src / "outside-link").symlink_to("../../../etc/hostname")
    subprocess.run([*GIT, "-C", str(src), "add", "-A"], check=True)
    subprocess.run([*GIT, "-C", str(src), "commit", "-qm", "init"], check=True)
    (src / "uncommitted.txt").write_text("never copied\n")
    return src


def install_packages(camp, eid, distro):
    if distro == "arch":
        camp.sh(eid, "pacman-retry -Syu --needed --noconfirm tree >/tmp/pkg.log 2>&1 || pacman -Syu --needed --noconfirm tree", timeout=1800)
        camp.sh(eid, "ocs-aur -S --noconfirm bash-pipes > /tmp/aur.log 2>&1", timeout=1800)
    else:
        camp.sh(eid, "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends tree >/dev/null", timeout=1800)


def data_id(camp, data):
    return camp.python(f"import os; os.environ['OPENCODE_SANDBOX_HOME']={str(data)!r}\n"
                       "from opencode_sandbox import core; print(core.data_id())").stdout.strip()


def persisted(camp, eid, distro):
    p = camp.sh(eid, MARKERS + " && command -v tree" + (" && command -v pipes.sh && pacman -Q bash-pipes" if distro == "arch" else ""),
                check=False)
    return p.returncode == 0 and p.stdout.count("ocs-test-marker") == 3


@pytest.mark.parametrize("distro", DISTROS)
def test_lifecycle_settings_changes_backup(campaign, checks, distro):
    camp, ck = campaign, checks
    camp.python(f"import os; os.environ['OPENCODE_SANDBOX_CONFIG']={str(camp.config)!r}\nfrom opencode_sandbox import core as c\n"
                "c.init_dirs(); c.profile_set('ocs-test-fake', {'QA_API_KEY': 'not-a-real-key'})")
    src = source_repo(camp, distro)
    name = f"ocs-test-life-{distro}"
    eid = camp.create(name, "--source", str(src), "--distro", distro, "--no-integrations", "--profile", "ocs-test-fake")
    ws = camp.data / "environments" / eid / "workspace"

    # D02 import: committed files only, names, modes and symlinks kept, nothing outside copied
    imported = tree(ws)
    ck(set(imported) == {"a b.txt", "-dash.txt", "ü-unicode.txt", "run.sh", "outside-link"}, f"D02 import set {sorted(imported)}")
    ck(imported.get("run.sh", ("",))[1] in ("0o755", "0o775"), "D02 executable bit kept")
    ck(imported.get("outside-link") == ("link", "../../../etc/hostname"), "D02 committed symlink kept as a link (not followed)")

    # C03/F04 container boundaries
    camp.ocs("start", name)
    info = camp.inspect(eid)
    host = info["HostConfig"]
    ck(host["Privileged"] is False and not host.get("CapAdd") and not host.get("Devices"), "C03 not privileged, no added capabilities or devices")
    ck("no-new-privileges:true" in (host.get("SecurityOpt") or []), "C03 no-new-privileges")
    ck({"NET_RAW", "MKNOD"} <= {cap.removeprefix("CAP_") for cap in host.get("CapDrop") or []},
       f"C03 NET_RAW and MKNOD dropped: {host.get('CapDrop')}")
    caps = camp.sh(eid, "grep CapEff /proc/self/status", check=False).stdout.split()
    ck(len(caps) == 2 and not int(caps[1], 16) & (1 << 13 | 1 << 27), f"C03 effective capabilities without NET_RAW/MKNOD {caps}")
    mounts = {(m["Type"], m["Destination"], m["RW"]) for m in info["Mounts"]}
    ck(mounts == {("bind", "/workspace", True), ("volume", "/root", True), ("bind", "/run/ocs-agent", False),
                  ("bind", "/run/secrets/ocs-provider.json", False)}, f"F04 only the expected mounts {sorted(mounts)}")
    ck(not any("docker.sock" in (m.get("Source") or "") for m in info["Mounts"]), "F04 no Docker socket mounted")
    labels = info["Config"]["Labels"]
    ck(labels.get("org.opencode-sandbox.managed") == "true" and labels.get("org.opencode-sandbox.id") == eid
       and labels.get("org.opencode-sandbox.data-dir"), "C03 ownership and data-directory labels")
    p = camp.sh(eid, "id -u; grep NoNewPrivs /proc/self/status; ls /var/run/docker.sock /run/docker.sock 2>&1 | grep -c 'No such'")
    ck(p.stdout.split() == ["0", "NoNewPrivs:", "1", "2"], f"C03 root in the container, NoNewPrivs, no socket: {p.stdout.split()}")
    camp.sh(eid, "touch /workspace/by-root")
    ck((ws / "by-root").stat().st_uid == os.getuid(), "C03 container root writes files owned by the host user")
    (ws / "by-root").unlink()

    # D03 persistence across stop/start, recreation and a settings change
    camp.sh(eid, "echo ocs-test-marker > /workspace/ws-marker.txt; echo ocs-test-marker > /root/home-marker.txt; "
                 "echo ocs-test-marker > /etc/ocs-test-system-marker")
    install_packages(camp, eid, distro)
    ck(persisted(camp, eid, distro), "D03 markers and packages present")
    camp.ocs("stop", name)
    camp.ocs("start", name)
    ck(persisted(camp, eid, distro), "D03 stop/start keeps workspace, home, system layer and packages")
    old = info["Id"]
    camp.ocs("container", "recreate", name, "--yes")
    ck(camp.inspect(eid)["Id"] != old and persisted(camp, eid, distro), "D04 recreate: new container, everything kept")

    # C04/C05 settings through the change plan
    plan = camp.ocs("config", "plan", name, "--network", "none", "--cpus", "1.5", "--memory", "3g", "--json")
    ck(json.loads(plan.stdout).get("changes"), "C05 config plan lists the changes")
    camp.ocs("config", "apply", name, "--network", "none", "--cpus", "1.5", "--memory", "3g", "--yes")
    host = camp.inspect(eid)["HostConfig"]
    ck(host["NetworkMode"] == "none" and host["NanoCpus"] == 1_500_000_000 and host["Memory"] == 3 * 2**30,
       f"C05 settings applied ({host['NetworkMode']}, {host['NanoCpus']}, {host['Memory']})")
    ck(persisted(camp, eid, distro), "C05 recreation for the network change keeps everything")
    net = camp.sh(eid, "python3 -c \"import socket; socket.create_connection(('1.1.1.1', 443), 3)\" 2>&1; echo rc=$?", check=False)
    ck("rc=1" in net.stdout, "C04 network none: no outside connection")
    report = camp.ocs("check", name, check=False)
    ck(report.returncode == 0 and " 0 failed" in report.stdout, "C04 check passes with network none (nothing reachable measured)")
    ck(re.search(r"\[passed\]\s*Agent Context delivery: configured: .* matches the host file", report.stdout) is not None,
       "G05 check compares the mounted Agent Context with the host file")
    camp.ocs("config", "apply", name, "--pids", "900")
    ck(camp.inspect(eid)["HostConfig"]["PidsLimit"] == 900 and persisted(camp, eid, distro), "C05 PID limit in place, other settings kept")
    ck(camp.ocs("agent-context", "verify", name, check=False).returncode == 0, "G05 Agent Context current after the changes")

    # E06 Git changes: show, bundle, inspect, stage, branch-diff, unstage; the source stays untouched
    camp.sh(eid, "cd /workspace && printf 'changed\\n' > 'a b.txt' && git -c user.name=agent -c user.email=a@example.invalid commit -qam agent "
                 "&& printf 'new\\n' > new-file.txt && rm -- -dash.txt")
    show = camp.ocs("changes", "show", name).stdout
    ck("agent" in show and "new-file.txt" in show, "E06 changes show: commit and untracked file")
    head_before = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout
    status_before = subprocess.run(["git", "-C", str(src), "status", "--porcelain"], capture_output=True, text=True, check=False).stdout
    camp.sh(eid, "ln -s /usr/bin/python3 /workspace/abs-link")
    refused = camp.ocs("changes", "bundle", name, check=False)
    ck(refused.returncode != 0 and "Unsafe symlink target: abs-link" in refused.stdout + refused.stderr,
       "E07 bundle refuses an untracked absolute symlink (it would point into the host repository)")
    camp.sh(eid, "rm /workspace/abs-link")
    bundle = camp.ocs("changes", "bundle", name).stdout.strip().splitlines()[-1]
    inspect = camp.ocs("changes", "inspect", bundle).stdout
    ck("new-file.txt" in inspect and "changed" in inspect and "-dash.txt" in inspect, "E06 bundle has the edit, the deletion and the new file")
    refused = camp.ocs("changes", "stage", bundle, str(src), check=False)
    ck(refused.returncode != 0 and "clean Git repository" in refused.stdout + refused.stderr, "E07 stage refuses a dirty source")
    (src / "uncommitted.txt").unlink()
    status_before = subprocess.run(["git", "-C", str(src), "status", "--porcelain"], capture_output=True, text=True, check=False).stdout
    staged = json.loads(camp.ocs("changes", "stage", bundle, str(src)).stdout)
    branch, commit = staged["branch"], staged["commit"]
    diff = camp.ocs("changes", "branch-diff", str(src), branch).stdout
    ck("new-file.txt" in diff and "+changed" in diff, "E06 review branch has the changes")
    ck(subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout == head_before
       and subprocess.run(["git", "-C", str(src), "status", "--porcelain"], capture_output=True, text=True, check=False).stdout == status_before,
       "E06 source HEAD and working tree unchanged by stage")
    camp.ocs("changes", "unstage", str(src), branch, commit)
    ck(branch not in subprocess.run(["git", "-C", str(src), "branch"], capture_output=True, text=True, check=False).stdout, "E06 unstage removed the branch")
    shutil.rmtree(Path(bundle).parent if Path(bundle).is_dir() else Path(bundle), ignore_errors=True)

    # E01/E04 cold backup with the system layer, verify, restore to a new name, compare
    camp.sh(eid, "mkdir -p /workspace/.venv/bin && ln -s \"$(command -v python3)\" /workspace/.venv/bin/python")  # as in a venv
    camp.ocs("stop", name)
    camp.ocs("backup", "create", name)
    backups = sorted((camp.data / "backups").glob(f"{name}-{eid}-*.ocsbackup"))
    ck(len(backups) == 1, f"E04 one backup directory ({len(backups)})")
    backup = backups[-1]
    camp.note(f"backup {backup}")
    ck(stat.S_IMODE(backup.stat().st_mode) == 0o700, "E04 backup directory is 0700")
    camp.ocs("backup", "verify", str(backup))
    raw = b"".join(p.read_bytes() for p in backup.rglob("*") if p.is_file() and p.stat().st_size < 50 * 2**20)
    ck(b"not-a-real-key" not in raw, "F06 the profile value is not in the backup's small files")
    restored = f"ocs-test-rest-{distro}"
    camp.ocs("backup", "restore", str(backup), restored)
    rid = camp.adopt(restored)
    camp.ocs("backup", "restore-check", restored)
    ck(tree(camp.data / "environments" / rid / "workspace") == tree(ws), "E01 restored workspace identical (names, modes, contents, links)")
    ck(mtimes(camp.data / "environments" / rid / "workspace") == mtimes(ws), "E01 restored modification times")
    ck(persisted(camp, rid, distro), "E01 restored home volume, system layer and packages")
    ck(camp.sh(rid, "/workspace/.venv/bin/python -c 'print(6*7)'", check=False).stdout.strip() == "42",
       "E01 absolute symlink (venv-style) restored as a link and usable in the container")
    # The venv-style link points outside the repository, which a bundle refuses; without it:
    camp.sh(rid, "rm -rf /workspace/.venv")
    bundled = camp.ocs("changes", "bundle", restored, "--destination", str(camp.data / "restored-bundles"), check=False)
    ck(bundled.returncode == 0, f"E06 restored Git project: changes bundle works {bundled.stderr.strip()[-200:]}")
    meta = camp.metadata(restored)
    ck(meta["distro"] == distro and meta["runtime"]["network"] == "none" and meta["runtime"]["pids"] == 900,
       "E01 restored settings and distribution")
    data1 = data_id(camp, camp.data)
    img_labels = json.loads(camp.docker("image", "inspect", meta["image"]).stdout)[0]["Config"]["Labels"]
    ck(meta["image"].startswith(f"ocs-backup:{rid}-") and img_labels.get("org.opencode-sandbox.id") == rid
       and img_labels.get("org.opencode-sandbox.data-dir") == data1,
       f"E01 restored system image belongs to the restored environment ({meta['image']})")

    # E10 restore into a second data directory on the same daemon: the image belongs to that
    # directory, the first directory's cleanup leaves it alone, its own cleanup removes it later
    env2 = {**camp.env, "OPENCODE_SANDBOX_HOME": str(camp.base / "data2"), "OPENCODE_SANDBOX_CONFIG": str(camp.base / "config2")}
    other = f"ocs-test-dir2-{distro}"
    camp.ocs("backup", "restore", str(backup), other, env=env2)
    meta2 = json.loads(next((camp.base / "data2" / "environments").glob("*/metadata.json")).read_text())
    camp.note(f"environment {other} id={meta2['id']} in {camp.base / 'data2'} image={meta2['image']}")
    data2 = data_id(camp, camp.base / "data2")
    img_labels = json.loads(camp.docker("image", "inspect", meta2["image"]).stdout)[0]["Config"]["Labels"]
    ck(img_labels.get("org.opencode-sandbox.id") == meta2["id"] and img_labels.get("org.opencode-sandbox.data-dir") == data2,
       "E10 restored image labelled for the second data directory")
    preview = camp.ocs("disk", "cleanup").stdout
    ck(meta2["image"] not in preview, "E10 the first directory's cleanup does not offer the other directory's image")
    shutil.rmtree(backup)
    camp.note(f"removed backup {backup}")

    # E09 a backup without a container keeps the derived system layer; names starting
    # with '-' round-trip; sockets and FIFOs are left out and reported
    camp.sh(rid, "printf 'dash\\n' > /workspace/-x && mkfifo /workspace/pipe /root/home-pipe && "
                 "python3 -c \"import socket; socket.socket(socket.AF_UNIX).bind('/workspace/app.sock')\"")
    camp.ocs("stop", restored)
    camp.ocs("config", "apply", restored, "--network", "bridge", "--yes")
    ck(camp.docker("container", "inspect", f"ocs-{rid}", check=False).returncode != 0
       and camp.metadata(restored)["image"].startswith(f"ocs-runtime:{rid}-"),
       "E09 config apply while stopped: no container, system layer in an ocs-runtime image")
    out = camp.ocs("backup", "create", restored).stdout
    second = max((camp.data / "backups").glob(f"{restored}-{rid}-*.ocsbackup"))
    camp.note(f"backup {second}")
    manifest = json.loads((second / "manifest.json").read_text())
    ck(manifest["system_image"] is True and manifest["system_image_source"] == "image" and "system-image.tar" in manifest["files"],
       f"E09 backup without a container has the system image ({manifest['system_image_source']})")
    ck(manifest["skipped_special_files"] == {"workspace": ["app.sock", "pipe"], "home": ["home-pipe"]}
       and "socket/FIFO" in out, f"E09 sockets and FIFOs left out and reported {manifest['skipped_special_files']}")
    camp.ocs("backup", "verify", str(second))
    third = f"ocs-test-rest2-{distro}"
    camp.ocs("backup", "restore", str(second), third)
    tid = camp.adopt(third)
    camp.ocs("backup", "restore-check", third)
    ck(persisted(camp, tid, distro), "E09 restore of that backup keeps the installed packages and system files")
    ck(camp.sh(tid, "cat /workspace/-x; test ! -e /workspace/pipe && test ! -e /root/home-pipe && echo none", check=False).stdout.split()
       == ["dash", "none"], "E09 top-level '-x' restored; the FIFOs are not")
    shutil.rmtree(second)
    camp.note(f"removed backup {second}")
    camp.delete(third)

    # D01 delete removes the environment's objects, not the source
    camp.delete(restored)
    camp.delete(name)
    ck(not ws.exists() and (src / "a b.txt").read_text() == "spaces\n" and (src / "-dash.txt").exists(),
       "D01 delete removed the workspace copy, source untouched")
    left = camp.docker("ps", "-aq", "--filter", f"name=ocs-{eid}").stdout + camp.docker("volume", "ls", "-q", "--filter", f"name=ocs-home-{eid}").stdout
    ck(left.strip() == "", "D01 container and home volume removed")

    # E10 (cont.) with the backed-up environment deleted, the first directory's cleanup succeeds and
    # the second directory's restored environment still starts from its image
    cleaned = camp.ocs("disk", "cleanup", "--yes", check=False)
    ck(cleaned.returncode == 0 and "Not removed" not in cleaned.stdout, "E10 the first directory's cleanup exits 0")
    camp.ocs("backup", "restore-check", other, env=env2)
    ck(camp.docker("container", "inspect", "--format", "{{.Config.Image}}", f"ocs-{meta2['id']}").stdout.strip() == meta2["image"],
       "E10 the other directory's restored environment starts from its image after that cleanup")
    camp.ocs("stop", other, env=env2)
    camp.ocs("delete", other, "--yes", env=env2)
    cleaned = camp.ocs("disk", "cleanup", "--yes", env=env2, check=False)
    left2 = [camp.docker(kind, "ls", "-q", *(["-a"] if kind == "container" else []), "--filter",
                         f"label=org.opencode-sandbox.data-dir={data2}").stdout.split() for kind in ("container", "volume", "image")]
    ck(cleaned.returncode == 0 and left2 == [[], [], []], f"E10 the second directory's cleanup exits 0 and removed its objects {left2}")
    shutil.rmtree(camp.base / "data2", ignore_errors=True)
    shutil.rmtree(camp.base / "config2", ignore_errors=True)


CUSTOM = "ubuntu:24.04"  # pre-existing local image; only used, never removed


def test_custom_image_provenance(campaign, checks):
    """E11: a custom-image environment keeps its original image through a reconfiguration,
    a backup without the system layer and its restore."""
    camp, ck = campaign, checks
    if camp.docker("image", "inspect", CUSTOM, check=False).returncode:
        pytest.skip(f"{CUSTOM} is not present locally")
    name = "ocs-test-custom"
    eid = camp.create(name, "--image", CUSTOM, "--no-integrations")
    camp.ocs("start", name)
    camp.ocs("stop", name)
    camp.ocs("config", "apply", name, "--network", "none", "--yes")
    meta = camp.metadata(name)
    ck(meta["image"].startswith(f"ocs-runtime:{eid}-") and meta["custom_image"] == CUSTOM,
       f"E11 after the reconfiguration: image {meta['image']}, custom image {meta.get('custom_image')}")
    camp.ocs("backup", "create", name, "--no-system")
    backup = max((camp.data / "backups").glob(f"{name}-{eid}-*.ocsbackup"))
    camp.note(f"backup {backup}")
    env = json.loads((backup / "manifest.json").read_text())["environment"]
    ck(env["custom_image"] == CUSTOM, f"E11 the backup records the original image ({env['custom_image']})")
    restored = "ocs-test-custom-rest"
    camp.ocs("backup", "restore", str(backup), restored, "--no-system")
    camp.adopt(restored)
    meta = camp.metadata(restored)
    ck(meta["image"] == CUSTOM and meta["custom_image"] == CUSTOM, f"E11 restore --no-system uses the original image ({meta['image']})")
    camp.ocs("start", restored)
    ck(camp.inspect(meta["id"])["Config"]["Image"] == CUSTOM, "E11 the restored container runs the original image")
    shutil.rmtree(backup)
    camp.note(f"removed backup {backup}")
    camp.delete(restored)
    camp.delete(name)
