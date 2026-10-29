"""The dashboard in a real terminal against real Docker, keyboard only (campaign rows H01–H05,
H08: direct workspace from the form, Settings, Backups and restore, Changes, Versions, Check, and
a dashboard killed while a session is open)."""
import os
import re
import shlex
import signal
import subprocess
from pathlib import Path

import pytest
from campaign import MANAGER

pyte = pytest.importorskip("pyte")
from pty_term import DOWN, ENTER, ESC, F5, F6, STAB, TAB, UP, Term

PLAIN, DIRECT, RESTORED = "ocs-test-tui-git", "ocs-test-tui-direct", "ocs-test-tui-rest"


def select(t, name):
    """Move the table cursor until the details pane shows `name`."""
    for keys in [""] + [DOWN] * 6 + [UP] * 12:
        if keys:
            t.send(keys, 0.4)
        if re.search(rf"│ {re.escape(name)}  ", t.text()):
            return True
    return False


def confirm(t, settle=1.0):
    """Dialogs focus Cancel; Tab moves to Confirm."""
    t.send(TAB, 0.3)
    t.send(ENTER, settle)


def tokens(camp, eid):
    p = camp.sh(eid, "for e in /proc/[0-9]*/environ; do tr '\\0' '\\n' < $e 2>/dev/null | grep -q '^OCS_RUN_TOKEN=' "
                     "&& echo ${e%/environ}; done; true", check=False)
    return p.stdout.split()


def host_clients(eid):
    p = subprocess.run(["pgrep", "-af", f"exec -it -e OCS_SHELL=[01] ocs-{eid}"], capture_output=True, text=True, check=False)
    return [x for x in p.stdout.splitlines() if "pgrep" not in x]


def test_dashboard_against_real_docker(campaign, checks):
    camp, ck = campaign, checks
    src = camp.tmp("tui-src")
    for args in (["init", "-q", "-b", "main"], ["commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(["git", "-C", str(src), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], check=True)
    # Direct workspaces may not have hidden path components (like .work): outside the checkout.
    folder = Path("/tmp/opencode") / f"ocs-test-{camp.run}" / "tui-direct-folder"
    folder.mkdir(parents=True, exist_ok=True)
    camp.note(f"host dir {folder} (direct workspace)")
    (folder / "host-file.txt").write_text("from the host\n")
    pid_ = camp.create(PLAIN, "--source", str(src), "--no-integrations")

    t = Term([*MANAGER, "tui"], 100, 30, env=camp.env, log=camp.log)
    try:
        ck(t.wait_for(PLAIN, 30), "H01 dashboard lists the environment")
        # H03 direct workspace from the form, with the consent dialog
        t.send("n", 1)
        t.send(DIRECT, 0.3)
        t.send(TAB + TAB, 0.3)
        t.send(str(folder), 0.3)
        t.send(TAB + ENTER, 1)                 # expand "More options"
        t.send(TAB + TAB + ENTER, 1)           # workspace mode list
        t.send(DOWN + ENTER, 1)                # direct
        t.snap("form with a direct workspace")
        ck("direct host folder" in t.text(), "H03 direct workspace chosen in the form")
        t.send(STAB * 6, 0.5)
        t.send(ENTER, 2)
        t.snap("consent dialog")
        ck(t.wait_for(r"Not recommended", 10), "H03 consent dialog names the risk")
        confirm(t, 3)
        ck(t.wait_for(rf"Created {DIRECT}", 90), "H03 created after consent and preflight")
        did = camp.adopt(DIRECT)
        ck(camp.metadata(DIRECT)["workspace"] == {"mode": "direct", "path": str(folder)}, "H03 metadata: direct workspace at the folder")
        t.pump(2)
        ck(re.search(rf"│ {DIRECT}  ", t.text()) is not None, "H03 the new environment is selected")
        t.send(F5, 1)
        ck(t.wait_for(r"Started", 90), "H03 F5 starts it")
        ck(camp.sh(did, "cat /workspace/host-file.txt").stdout == "from the host\n", "H03 the container sees the host folder itself")

        # H03 Check, Settings, Changes, Backup, Backups/restore, Versions on the Git project
        ck(select(t, PLAIN), "H02 keyboard selection of the other environment")
        t.send(F5, 1)
        ck(t.wait_for(r"Started", 90), "F5 starts the project")
        t.send("i", 1)
        ck(t.wait_for(rf"Readiness of {PLAIN}", 15) and t.wait_for(r"Summary: .* passed, 0 warning, 0 failed", 60),
           "H03 i runs the check and shows the report")
        t.snap("readiness report")
        t.send(ESC, 1)
        ck(t.wait_for(r"Readiness: last check .* passed", 10), "H03 the details pane shows the cached result")
        t.send("t", 1)
        ck(t.wait_for(rf"Settings of {PLAIN}", 10), "H03 t opens Settings")
        t.send("\x7f" * 8, 0.5)  # the cursor starts at the end of the value
        t.send("2", 0.5)
        t.send(TAB * 7, 0.3)
        t.send(ENTER, 1.5)
        t.snap("settings plan")
        ck(re.search(r"CPU limit: 4\.0 -> 2", t.text()) is not None, "H03 the change plan is shown before applying")
        confirm(t, 3)
        ck(camp.wait_for(lambda: camp.inspect(pid_)["HostConfig"]["NanoCpus"] == 2_000_000_000, 30), "H03 the new CPU limit is applied to the container")
        t.send("d", 1.5)
        t.send(TAB * 2 + ENTER, 3)              # Summary
        t.snap("changes screen")
        ck(t.wait_for(r"Base|base", 15), "H03 d opens Changes; Summary shows the change summary")
        t.send(ESC, 1)
        t.send(F6, 1)
        if "Stop" in t.text() and "?" in t.text():
            confirm(t, 3)
        ck(t.wait_for(r"Stopped", 60), "F6 stops the project")
        t.send("b", 2)
        if re.search(r"(?i)back ?up .*\?", t.text()):
            confirm(t, 2)
        ck(t.wait_for(r"(?i)backup.*(created|\.ocsbackup)", 300), "H04 b creates a backup (asynchronous; finishes)")
        t.snap("after backup")
        t.send("B", 2)
        ck(t.wait_for(r"ocs-test-tui-git", 15), "H03 B lists the backup")
        t.send(TAB, 0.3)
        t.send(RESTORED, 0.3)
        t.send(TAB * 2 + ENTER, 2)
        ck(t.wait_for(rf"Restored {RESTORED}", 300), "H03 restore from the Backups screen")
        t.snap("after restore")
        camp.adopt(RESTORED)
        t.send(ESC, 1)
        t.send("v", 2)
        ck(t.wait_for(r"2\.2\.0", 60), "H03 v shows the OpenCode versions")
        t.snap("versions")
        t.send(ESC, 1)
        ck(select(t, DIRECT), "H02 back to the direct environment")
        t.send("q", 1)
        code = t.exit_code()
        ck(code == 0 and t.restored(), f"H01 q quits ({code}) and restores the terminal")
    finally:
        t.close()

    # H05 the dashboard is killed while a shell session it opened is running
    shell = Term(["bash", "--norc", "--noprofile", "-i"], 100, 30, env=camp.env, log=camp.log)
    try:
        shell.pump(1)
        shell.send(" ".join(shlex.quote(a) for a in [*MANAGER, "tui"]) + ENTER, 3)
        ck(shell.wait_for(DIRECT, 30) and select(shell, DIRECT), "dashboard started from a shell")
        shell.send("s", 3)
        ck(shell.wait_for(r"root@|# ?$", 30), "H05 s opens the shell session")
        before, clients = tokens(camp, did), host_clients(did)
        # The source tree runs as `python -m opencode_sandbox.cli tui`, an installed launcher as `python <launcher> tui`.
        pattern = re.escape(MANAGER[-1]) + " tui"
        manager = int(subprocess.run(["pgrep", "-nf", pattern], capture_output=True, text=True, check=False).stdout.split()[0])
        os.kill(manager, signal.SIGKILL)
        gone = camp.wait_for(lambda: not tokens(camp, did) and not host_clients(did), 20, 0.3)
        ck(len(before) >= 1 and len(clients) == 1 and gone, f"H05 SIGKILL of the dashboard ends its session ({before}, {len(clients)} client(s) before)")
    finally:
        shell.close()
    for name in (RESTORED, DIRECT, PLAIN):
        camp.delete(name)
    ck((folder / "host-file.txt").read_text() == "from the host\n", "delete never touches the direct folder")
    (folder / "host-file.txt").unlink()
    folder.rmdir()
    camp.note(f"removed host dir {folder}")
