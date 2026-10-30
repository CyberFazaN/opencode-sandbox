"""Hardening details: OpenCode major version and probe options, the Agent Context delivery check,
links below the top level of `.git`, data-directory permissions, container capabilities, the pin
check versus a base-image swap, `ocs-aur` option parsing, output inside a workspace, a journal's
image removed outside the manager and the Agent Context refresh after provisioning. Docker is mocked."""
import os
import subprocess

import pytest
from test_arch_image import aur

from opencode_sandbox import agent_context as ac
from opencode_sandbox import backup as b
from opencode_sandbox import core as c
from opencode_sandbox import gitflow
from opencode_sandbox import opencode_versions as v
from opencode_sandbox import readiness as r
from opencode_sandbox import workspace_io as wio


class Docker:
    """Records calls; `responses` maps an argument prefix to (returncode, stdout)."""

    def __init__(self, monkeypatch, responses=None, missing=()):
        self.calls, self.responses, self.missing = [], responses or {}, set(missing)
        monkeypatch.setattr(c, "docker", self)
        monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)

    def __call__(self, *args, capture=False, check=True):
        self.calls.append(args)
        rc, out = 0, ""
        for prefix, answer in self.responses.items():
            if args[:len(prefix)] == prefix:
                rc, out = answer(args) if callable(answer) else answer
        if args[:2] == ("image", "inspect") and args[-1] in self.missing:
            rc = 1
        if check and rc:
            raise c.SandboxError(f"Command failed ({rc}): docker {' '.join(map(str, args[:3]))}")
        return subprocess.CompletedProcess(args, rc, out, "")


# --- OpenCode major version and probe options -----------------------------------------------------

@pytest.mark.parametrize("version", ["3.0.0", "10.1.2"])
def test_only_opencode_2_is_supported(version):
    with pytest.raises(c.SandboxError, match="OpenCode 2.x"):
        v.supported(version)
    assert v.supported("2.9.9") == "2.9.9"


def test_update_to_latest_refuses_another_major(monkeypatch):
    monkeypatch.setattr(v, "latest", lambda timeout=8: "3.0.0")
    Docker(monkeypatch)
    m = c.create("ocs-qa-up", "scratch")
    with pytest.raises(c.SandboxError, match="OpenCode 2.x"):
        v.update_environment(m, "latest")
    with pytest.raises(c.SandboxError, match="OpenCode 2.x"):
        v.update_base("latest", "debian")


def test_report_names_an_unsupported_latest_major():
    assert "not supported" in v.describe("2.2.0", "3.0.0")


def test_version_probe_runs_without_new_privileges(monkeypatch):
    fake = Docker(monkeypatch, {("run",): (0, "opencode v2.2.0\n")})
    assert v.image_version("opencode-sandbox:debian") == "2.2.0"
    run = next(a for a in fake.calls if a[0] == "run")
    assert "no-new-privileges:true" in run


# --- Agent Context delivery check -----------------------------------------------------------------

def _delivery(monkeypatch, mounted):
    m = c.create("ocs-qa-ctx", "scratch")
    host = ac.path(m, c.env_dir)
    host.parent.mkdir(parents=True, exist_ok=True)
    host.write_text("guidance\n")

    def exec_answer(args):
        if args[-1] == ac.SYSTEM_CONFIG:
            return 0, f'{{"instructions": ["{ac.CONTAINER_PATH}"]}}'
        if args[-1] == ac.CONTAINER_PATH:
            return (0, mounted) if mounted is not None else (1, "")
        return 1, ""
    Docker(monkeypatch, {("exec",): exec_answer})
    return r.delivery_check(m, {"Running": True})


def test_delivery_check_fails_without_the_mounted_file(monkeypatch):
    check = _delivery(monkeypatch, None)
    assert check.status == r.FAILED and ac.CONTAINER_PATH in check.detail


def test_delivery_check_warns_when_the_mounted_file_differs(monkeypatch):
    check = _delivery(monkeypatch, "older guidance\n")
    assert check.status == r.WARNING and "differs" in check.detail


def test_delivery_check_passes_and_says_configured(monkeypatch):
    check = _delivery(monkeypatch, "guidance\n")
    assert check.status == r.PASSED and "configured" in check.detail and "loads" not in check.detail


# --- Links below the top level of .git ------------------------------------------------------------

@pytest.fixture
def repo(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    subprocess.run(["git", "-C", str(ws), "init", "-q"], check=True)
    (ws / "a.txt").write_text("a\n")
    subprocess.run(["git", "-C", str(ws), "-c", "user.email=q@x", "-c", "user.name=q", "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(ws), "-c", "user.email=q@x", "-c", "user.name=q", "commit", "-qm", "x"], check=True)
    other = tmp_path / "other"
    other.mkdir()
    return ws, other


@pytest.mark.parametrize("where", ["objects/pack", "objects/ab", "refs/heads", "info/exclude", "refs/tags/t"])
def test_links_below_the_top_level_of_git_are_refused(repo, where):
    ws, other = repo
    target = ws / ".git" / where
    if target.is_dir():
        os.rename(target, other / "moved")
    elif target.exists():
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(other)
    with pytest.raises(c.SandboxError, match="symlink"):
        wio.check_repository(ws)


def test_grafts_are_refused(repo):
    ws, _ = repo
    (ws / ".git" / "info").mkdir(exist_ok=True)
    (ws / ".git" / "info" / "grafts").write_text("")
    with pytest.raises(c.SandboxError, match="grafts"):
        wio.check_repository(ws)


def test_an_ordinary_repository_passes(repo):
    """Guard."""
    ws, _ = repo
    assert wio.check_repository(ws) == ws / ".git"


# --- Data-directory permissions -------------------------------------------------------------------

def test_an_existing_data_directory_keeps_its_permissions(tmp_path, monkeypatch):
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    monkeypatch.setattr(c, "BASE", shared)
    c.init_dirs()
    assert shared.stat().st_mode & 0o777 == 0o755
    assert all((shared / d).stat().st_mode & 0o777 == 0o700 for d in ("environments", "exports", "locks"))


def test_a_new_data_directory_is_private(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "BASE", tmp_path / "new" / "data")
    c.init_dirs()
    assert (tmp_path / "new" / "data").stat().st_mode & 0o777 == 0o700


# --- Container capabilities; pin check versus a base-image swap -----------------------------------

@pytest.fixture
def first_start(monkeypatch):
    held = {}

    def run_answer(args):
        probe = c.BASE / "locks" / "base-tag-debian.lock"
        held["base-tag"] = False
        if probe.exists():
            import fcntl
            with probe.open("a+") as f:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(f, fcntl.LOCK_UN)
                except BlockingIOError:
                    held["base-tag"] = True
        return 0, ""
    fake = Docker(monkeypatch, {("run",): run_answer})
    state = {"value": None}
    monkeypatch.setattr(c, "inspect_container", lambda m: state["value"])
    monkeypatch.setattr(c, "ensure_volume", lambda m: None)
    monkeypatch.setattr(c, "host_cpus", lambda: 8)
    monkeypatch.setattr("opencode_sandbox.integrations.provision", lambda m: None)
    return fake, held


def test_containers_drop_capabilities_they_do_not_need(first_start):
    fake, _ = first_start
    c.start(c.create("ocs-qa-caps", "scratch"))
    run = next(a for a in fake.calls if a[0] == "run")
    drops = {run[i + 1] for i, a in enumerate(run) if a == "--cap-drop"}
    assert {"NET_RAW", "MKNOD"} <= drops


def test_pin_check_and_container_creation_hold_the_base_tag_lock(first_start):
    _, held = first_start
    m = c.create("ocs-qa-pin", "scratch")
    m.update(opencode_policy="pinned", opencode_pin="2.2.0")
    c.save(m)
    c.start(m)
    assert held.get("base-tag") is True


def test_base_tag_swap_holds_the_base_tag_lock(monkeypatch):
    seen = []
    real = c.lock

    def lock(key, timeout=30.0):
        seen.append(key)
        return real(key, timeout)
    monkeypatch.setattr(c, "lock", lock)
    monkeypatch.setattr(c, "build_image", lambda d, version, tag: None)
    monkeypatch.setattr(c, "require_docker_space", lambda what: None)
    Docker(monkeypatch, {("image", "inspect"): (0, "sha256:1")})
    monkeypatch.setattr(v, "_content", lambda image: image)
    v.update_base("2.2.0", "debian")
    assert "base-tag-debian" in seen


# --- ocs-aur option parsing -----------------------------------------------------------------------

@pytest.mark.parametrize("argv", [
    ["pacman", "-Sr", "/tmp", "x"], ["pacman", "-Qb/tmp"], ["pacman", "-Syb", "/tmp"],
    ["pacman", "--roo", "/tmp", "-Q"], ["pacman", "--hookd=/tmp", "-S", "x"], ["pacman", "--db", "/tmp", "-Q"],
    ["pacman", "--conf", "/tmp/pacman.conf", "-S", "x"],
])
def test_broker_refuses_combined_and_abbreviated_options(argv):
    with pytest.raises(ValueError, match="not allowed"):
        aur.check_pacman(argv)


@pytest.mark.parametrize("argv", [["pacman", "-Syu", "--noconfirm"], ["pacman", "-Rns", "foo"],
                                  ["pacman", "-S", "--needed", "--asdeps", "foo"], ["pacman", "-D", "--asexplicit", "foo"],
                                  ["pacman", "-Qqm"], ["pacman", "--dbonly", "-R", "foo"]])
def test_broker_still_allows_ordinary_options(argv):
    """Guard."""
    assert aur.check_pacman(argv) == [aur.PACMAN, *argv[1:]]


# --- Output inside a workspace --------------------------------------------------------------------

def test_output_inside_a_workspace_is_refused(monkeypatch, tmp_path):
    Docker(monkeypatch)
    for name, value in (("inspect_container", lambda m: None), ("assert_volume_owned", lambda m: None),
                        ("volume_state", lambda m: None)):
        monkeypatch.setattr(c, name, value)
    m = c.create("ocs-qa-out", "scratch")
    other = c.create("ocs-qa-other", "scratch")
    inside = c.env_dir(other["id"]) / "workspace" / "out"
    for call in (lambda: b.backup(m, inside), lambda: c.export(m, inside),
                 lambda: gitflow.export_changes(m, c.env_dir(m["id"]) / "workspace")):
        with pytest.raises(c.SandboxError, match="Refusing to write"):
            call()
    assert not inside.exists()
    assert b.backup(m, tmp_path / "elsewhere").parent == tmp_path / "elsewhere"  # guard


# --- A journal's image removed outside the manager ------------------------------------------------

def test_recovery_with_a_removed_image_names_the_way_out(monkeypatch):
    m = c.create("ocs-qa-gone", "scratch")
    tag = f"ocs-runtime:{m['id']}-0123456789ab"
    c.mark(m, "reconfiguring", operation="runtime-recreate", image=tag, last_snapshot=tag)
    Docker(monkeypatch, missing={tag})
    with pytest.raises(c.SandboxError) as refused:
        c.recover_runtime_reconfigure(m)
    text = str(refused.value)
    assert "removed outside the manager" in text and f"changes export {m['name']}" in text and "delete" in text


def test_update_recover_with_a_removed_checkpoint_does_not_suggest_a_refused_command(monkeypatch):
    m = c.create("ocs-qa-gone", "scratch")
    checkpoint = f"ocs-checkpoint:{m['id']}-0123456789"
    c.mark(m, "error", operation=v.UPDATE_OP, opencode_update={"checkpoint": checkpoint, "state": "running"})
    Docker(monkeypatch, missing={checkpoint})
    with pytest.raises(c.SandboxError) as refused:
        v.update_recover(m)
    text = str(refused.value)
    assert "recreate from a snapshot" not in text and "removed outside the manager" in text


def test_start_never_pulls_a_missing_manager_image(first_start, monkeypatch):
    fake, _ = first_start
    m = c.create("ocs-qa-gone", "scratch")
    tag = f"ocs-snapshot:{m['id']}-20261028120000-abcdef"
    m["image"] = tag
    c.mark(m, "recreating", operation="recreate", last_snapshot=tag)
    fake.missing.add(tag)
    with pytest.raises(c.SandboxError, match="removed outside the manager"):
        c.recreate_recover(m)
    assert not any(a[0] == "run" for a in fake.calls)


def test_manager_images_are_run_with_pull_never(first_start):
    fake, _ = first_start
    c.start(c.create("ocs-qa-pull", "scratch"))
    run = next(a for a in fake.calls if a[0] == "run")
    assert "--pull" in run and run[run.index("--pull") + 1] == "never"


# --- Agent Context refresh after provisioning -----------------------------------------------------

def test_a_failed_refresh_after_provisioning_still_marks_running(first_start, monkeypatch):
    m = c.create("ocs-qa-prov", "scratch")
    monkeypatch.setattr("opencode_sandbox.integrations.provision", lambda env: {"context7": "done"})
    refreshes = []

    def refresh(env, env_dir, **inputs):
        refreshes.append(1)
        if len(refreshes) > 1:
            raise OSError(28, "No space left on device")
        return ac.directory(env, env_dir) / "context.md"
    monkeypatch.setattr(ac, "refresh", refresh)
    c.start(m)
    now = c.resolve(m["id"])
    assert (now["status"], now.get("operation")) == ("running", None) and len(refreshes) == 2

