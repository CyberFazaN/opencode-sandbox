"""L02: a direct workspace is re-checked at every container start, also for an existing stopped
container. The folders live below /tmp/opencode/ocs-test-<run>/ (a direct
workspace may not have a hidden path component such as .work)."""
import shutil
from pathlib import Path


def test_direct_workspace_is_rechecked_at_every_start(campaign, checks):
    camp, ck = campaign, checks
    root = Path("/tmp/opencode") / f"ocs-test-{camp.run}" / "l02"
    folder, other, moved = root / "project", root / "other", root / "moved"
    folder.mkdir(parents=True)
    other.mkdir()
    camp.note(f"host dir {root} (direct workspace L02)")
    (folder / "host-file.txt").write_text("from the host\n")
    (other / "other-file.txt").write_text("other\n")
    name = "ocs-test-direct"
    eid = camp.create(name, "--workspace-mode", "direct", "--workspace", str(folder), "--yes", "--no-integrations")
    camp.ocs("start", name)
    ck(camp.sh(eid, "cat /workspace/host-file.txt").stdout == "from the host\n", "L02 the container sees the folder")
    camp.ocs("stop", name)

    folder.rename(moved)
    folder.symlink_to(other, target_is_directory=True)
    refused = camp.ocs("start", name, check=False)
    running = camp.docker("container", "inspect", "--format", "{{.State.Running}}", f"ocs-{eid}").stdout.strip()
    meta = camp.metadata(name)
    ck(refused.returncode != 0 and "now resolves to" in refused.stdout + refused.stderr and running == "false",
       "L02 start of the stopped container refuses the folder replaced by a symlink; the container stays stopped")
    ck(meta["status"] == "stopped" and not meta.get("operation"), f"L02 state unchanged ({meta['status']}, {meta.get('operation')})")

    folder.unlink()
    moved.rename(folder)
    camp.ocs("start", name)
    ck(camp.sh(eid, "cat /workspace/host-file.txt").stdout == "from the host\n", "L02 with the folder restored, start works")
    camp.delete(name)
    ck((folder / "host-file.txt").read_text() == "from the host\n" and (other / "other-file.txt").read_text() == "other\n",
       "L02 delete leaves both folders untouched")
    shutil.rmtree(root)
    camp.note(f"removed host dir {root}")
