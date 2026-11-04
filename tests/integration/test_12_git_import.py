"""Working-state Project import is usable in both real rootless image workspaces."""
import os
import subprocess

import pytest
from campaign import DISTROS


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args])


@pytest.mark.parametrize("distro", DISTROS)
def test_working_git_import(campaign, checks, distro):
    camp, ck = campaign, checks
    source = camp.tmp(f"working-source-{distro}")
    git(source, "init", "-q", "-b", "working-branch")
    for name in ("modified", "removed", "rename", "binary"):
        (source / name).write_bytes(b"base\n")
    (source / ".gitignore").write_text(".env\n")
    git(source, "add", ".")
    git(source, "-c", "user.name=ocs-test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base")
    (source / "modified").write_text("staged\n"); git(source, "add", "modified")
    (source / "modified").write_text("working\n"); (source / "modified").chmod(0o755)
    git(source, "rm", "-q", "removed"); git(source, "mv", "rename", "renamed")
    (source / "binary").write_bytes(b"\0staged\xff"); git(source, "add", "binary")
    (source / "binary").write_bytes(b"\0working\xff")
    (source / "new").write_bytes(b"new\0file")
    (source / ".env").write_text("DUMMY_NOT_FOR_IMPORT=excluded")
    (source / "outside-link").symlink_to("../../outside-secret")
    index = (source / ".git/index").read_bytes()
    status = git(source, "status", "--porcelain=v1", "--untracked-files=all").decode()
    name = f"ocs-test-working-{distro}"
    eid = camp.create(name, "--source", str(source), "--include-working-changes", "--distro", distro)
    workspace = camp.data / "environments" / eid / "workspace"
    ck((source / ".git/index").read_bytes() == index, "host index unchanged")
    ck(git(workspace, "status", "--porcelain=v1", "--untracked-files=all").decode() == status, "host Git sees exact staged/unstaged status in imported workspace")
    camp.ocs("start", name)
    observed = camp.sh(eid, "git status --porcelain=v1 --untracked-files=all; git branch --show-current").stdout
    ck(observed == status + "working-branch\n", "container Git sees working state and branch")
    ck(camp.sh(eid, "git show :modified; cat modified; test -x modified; test ! -e .env; test ! -e removed").stdout == "staged\nworking\n", "container sees staged content, worktree, permissions and omissions")
    ck((workspace / "binary").read_bytes() == b"\0working\xff" and git(workspace, "show", ":binary") == b"\0staged\xff", "binary staged and working bytes preserved")
    ck(os.readlink(workspace / "outside-link") == "../../outside-secret", "symlink text preserved without copying target")
    # Start/stop never reapplies or synchronizes the source import.
    (source / "modified").write_text("later host edit\n")
    camp.ocs("stop", name); camp.ocs("start", name)
    ck(camp.sh(eid, "cat modified").stdout == "working\n", "later host edits are independent")
    ck((source / ".git/index").read_bytes() == index, "source index still unchanged after container lifecycle")
    camp.delete(name)
