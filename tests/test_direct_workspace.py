"""D-012: direct host workspaces (mocked Docker; real runs in tests/integration)."""
import json
import os
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import agent_context as ac
from opencode_sandbox import backup as b
from opencode_sandbox import config_plan as cp
from opencode_sandbox import core as c
from opencode_sandbox import gitflow
from opencode_sandbox import workspaces as ws
from opencode_sandbox.cli import app

runner = CliRunner()


class FakeDocker:
    """Preflight containers act on the bind-mounted host directory like the real image would."""

    def __init__(self, monkeypatch, *, write=True, remove=True, owner=None):
        self.calls, self.write, self.remove, self.owner = [], write, remove, owner
        monkeypatch.setattr(c, "docker", self)
        monkeypatch.setattr(c, "ensure_runtime", lambda distro=None: None)
        monkeypatch.setattr(c, "docker_root", lambda: None)

    def __call__(self, *args, capture=False, check=True):
        self.calls.append(args)
        ok = SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[0] == "run" and "org.opencode-sandbox.preflight=true" in args:
            src = Path(next(a for a in args if str(a).startswith("type=bind,src="))[len("type=bind,src="):].split(",dst=")[0])
            token, script = args[-1], args[-3]
            marker = src / (ws.PREFLIGHT_PREFIX + token)
            if script.startswith("umask"):
                if not self.write:
                    return SimpleNamespace(returncode=1, stdout="", stderr="Permission denied")
                marker.write_text(f"ocs-preflight {token}\n")
            elif self.remove:
                marker.unlink(missing_ok=True)
        return ok


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "projects" / "app"
    p.mkdir(parents=True)
    (p / "main.py").write_text("print('hi')\n")
    return p


def direct_env(monkeypatch, project, name="ocs-qa-direct", **kw):
    FakeDocker(monkeypatch)
    return c.create(name, "project", workspace_mode="direct", workspace=project, consent=True, **kw)


# --- host-side validation ------------------------------------------------------------------

def test_check_direct_accepts_a_user_project_and_resolves_symlinks(project, tmp_path):
    assert ws.check_direct(project) == project.resolve()
    link = tmp_path / "link"
    link.symlink_to(project)
    assert ws.check_direct(link) == project.resolve()


@pytest.mark.parametrize("bad,reason", [
    ("/", "root directory"),
    ("/etc", "system directory"),
    ("/usr/share", "system directory"),
    ("/run/user", "system directory"),
    ("/mnt", "owned by uid 0"),
    ("/home", "home directory or contains it"),
])
def test_check_direct_refuses_system_and_root_owned(bad, reason):
    if not os.path.isdir(bad):
        pytest.skip(f"{bad} missing")
    with pytest.raises(c.SandboxError, match=reason):
        ws.check_direct(bad)


def test_check_direct_refuses_home_missing_files_and_symlink_to_root(tmp_path, monkeypatch):
    with pytest.raises(c.SandboxError, match="home directory"):
        ws.check_direct(Path.home())
    with pytest.raises(c.SandboxError, match="not accessible"):
        ws.check_direct(tmp_path / "missing")
    (tmp_path / "file").write_text("x")
    with pytest.raises(c.SandboxError, match="must be a directory"):
        ws.check_direct(tmp_path / "file")
    (tmp_path / "etc-link").symlink_to("/etc")
    with pytest.raises(c.SandboxError, match="/etc: it is a system directory"):
        ws.check_direct(tmp_path / "etc-link")


def test_check_direct_refuses_manager_dirs_and_hidden_components(tmp_path):
    c.init_dirs()
    with pytest.raises(c.SandboxError, match="manager data"):
        ws.check_direct(c.BASE / "environments")
    with pytest.raises(c.SandboxError, match="manager data"):
        ws.check_direct(tmp_path)  # contains BASE and CONFIG
    hidden = tmp_path / ".secret" / "proj"
    hidden.mkdir(parents=True)
    with pytest.raises(c.SandboxError, match="hidden"):
        ws.check_direct(hidden)


def test_check_direct_refuses_foreign_and_root_owned_components(project, monkeypatch):
    real = os.lstat
    def lstat(p, owner):
        st = real(p)
        return SimpleNamespace(st_mode=st.st_mode, st_uid=owner, st_gid=st.st_gid, st_dev=st.st_dev)
    monkeypatch.setattr(os, "lstat", lambda p: lstat(p, 4242) if Path(p) == project else real(p))
    with pytest.raises(c.SandboxError, match="owned by uid 4242, not by you"):
        ws.check_direct(project)
    monkeypatch.setattr(os, "lstat", lambda p: lstat(p, 0) if Path(p) == project.parent else real(p))
    with pytest.raises(c.SandboxError, match="owned by root inside your own directories"):
        ws.check_direct(project)
    monkeypatch.setattr(os, "lstat", lambda p: lstat(p, 4242) if Path(p) == project.parent else real(p))
    with pytest.raises(c.SandboxError, match="owned by another user"):
        ws.check_direct(project)


def test_check_direct_refuses_ancestor_writable_by_others(project):
    project.parent.chmod(0o777)
    try:
        with pytest.raises(c.SandboxError, match="writable by other users"):
            ws.check_direct(project)
        project.parent.chmod(0o1777)  # sticky, like /tmp
        assert ws.check_direct(project) == project
    finally:
        project.parent.chmod(0o755)


def test_check_direct_refuses_sockets_and_nested_mounts(project):
    (project / "sub").mkdir()
    sock = socket.socket(socket.AF_UNIX)
    path = project / "sub" / "agent.sock"
    try:
        sock.bind(str(path))
        with pytest.raises(c.SandboxError, match=r"contains sub/agent.sock \(socket\)"):
            ws.check_direct(project)
    finally:
        sock.close()
        path.unlink()
    assert ws.check_direct(project) == project
    with pytest.raises(c.SandboxError, match=r"sub \(another mounted filesystem\)"):
        ws._scan(project, device=-1)


# --- preflight -------------------------------------------------------------------------------

def test_preflight_writes_checks_and_removes_only_its_marker(monkeypatch, project):
    fake = FakeDocker(monkeypatch)
    before = sorted(p.name for p in project.iterdir())
    result = ws.preflight(project, "opencode-sandbox:debian")
    assert result["uid"] == os.getuid() and sorted(p.name for p in project.iterdir()) == before
    runs = [a for a in fake.calls if a[0] == "run"]
    assert len(runs) == 2 and all("--network" in a and "none" in a and "--rm" in a for a in runs)
    assert all("no-new-privileges:true" in a and "--user" not in a for a in runs)
    assert all(f"type=bind,src={project},dst=/workspace" in a for a in runs)


def test_preflight_refuses_other_identity_and_cleans_up(monkeypatch, project):
    FakeDocker(monkeypatch)
    monkeypatch.setattr(os, "getuid", lambda: 4242)
    with pytest.raises(c.SandboxError, match="belong to host uid:gid .* not to you .*not supported"):
        ws.preflight(project, "img")
    assert not list(project.glob(ws.PREFLIGHT_PREFIX + "*"))  # removed by the same container identity


def test_preflight_unwritable_and_undeletable(monkeypatch, project):
    FakeDocker(monkeypatch, write=False)
    with pytest.raises(c.SandboxError, match="could not write"):
        ws.preflight(project, "img")
    FakeDocker(monkeypatch, remove=False)
    with pytest.raises(c.SandboxError, match="could not delete its file"):
        ws.preflight(project, "img")
    assert not list(project.glob(ws.PREFLIGHT_PREFIX + "*"))  # ours: the host removes it


def test_interrupted_preflight_marker_is_removed_next_time(monkeypatch, project):
    FakeDocker(monkeypatch)
    stale = project / (ws.PREFLIGHT_PREFIX + "0123456789abcdef")
    stale.write_text("ocs-preflight 0123456789abcdef\n")
    ws.preflight(project, "img")
    assert not stale.exists()
    user = project / (ws.PREFLIGHT_PREFIX + "notes")
    user.write_text("mine")
    with pytest.raises(c.SandboxError, match="not the manager's: .ocs-preflight-notes"):
        ws.preflight(project, "img")
    assert user.read_text() == "mine"


# --- creation and metadata ---------------------------------------------------------------------

def test_create_direct_records_path_and_copies_nothing(monkeypatch, project):
    m = direct_env(monkeypatch, project)
    assert m["workspace"] == {"mode": "direct", "path": str(project)} and m["source"] is None
    assert not (c.env_dir(m["id"]) / "workspace").exists()
    assert ws.path(m) == project and ws.is_direct(c.resolve(m["id"]))
    assert sorted(p.name for p in project.iterdir()) == ["main.py"]
    assert c.current_env(project / "sub") is None or c.current_env(project)["id"] == m["id"]
    assert c.current_env(project)["id"] == m["id"]


def test_create_direct_refusals(monkeypatch, project, tmp_path):
    fake = FakeDocker(monkeypatch)
    for kwargs, match in (({"consent": False}, "explicit consent"),
                          ({"consent": True, "kind": "quick"}, "Quick sessions are disposable"),
                          ({"consent": True, "source": tmp_path}, "--source"),
                          ({"consent": True, "workspace": None}, "needs a host folder")):
        args = {"kind": "project", "workspace": project, **kwargs}
        kind = args.pop("kind")
        with pytest.raises(c.SandboxError, match=match):
            c.create("ocs-qa-x", kind, workspace_mode="direct", **args)
    with pytest.raises(c.SandboxError, match="needs --workspace-mode direct"):
        c.create("ocs-qa-x", "project", workspace=project)
    assert fake.calls == [] and c.all_envs() == []
    c.create("ocs-qa-a", "project", workspace_mode="direct", workspace=project, consent=True)
    (project / "inner").mkdir()
    for path in (project, project / "inner"):
        with pytest.raises(c.SandboxError, match="overlaps the direct workspace of ocs-qa-a"):
            c.create("ocs-qa-b", "project", workspace_mode="direct", workspace=path, consent=True)


def test_metadata_without_valid_workspace_record_is_ignored(monkeypatch, project):
    m = c.create("ocs-qa-meta", "scratch")
    assert m["workspace"] == {"mode": "managed", "path": None}
    for bad in (None, {"mode": "managed"}, {"mode": "direct", "path": "relative"},
                {"mode": "direct", "path": "/a/../b"}, {"mode": "managed", "path": "/x"}):
        m["workspace"] = bad
        c.save(m)
        assert c.all_envs() == [] and "workspace record" in c.metadata_error(c.env_dir(m["id"]) / "metadata.json")


# --- lifecycle ---------------------------------------------------------------------------------

def test_start_mounts_the_direct_directory_after_rechecking(monkeypatch, project):
    m = direct_env(monkeypatch, project)
    runs = []
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "ensure_volume", lambda m: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: runs.append(a) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    c.start(m)
    assert f"type=bind,src={project},dst=/workspace" in next(a for a in runs if a[0] == "run")
    assert "Working directory: /workspace" in ac.path(m, c.env_dir).read_text()
    moved = project.parent / "moved"
    project.rename(moved)
    other = project.parent / "other"
    other.mkdir()
    project.symlink_to(other)  # the recorded path now leads somewhere else
    runs.clear()
    with pytest.raises(c.SandboxError, match="now resolves to .*other; refusing to mount a different directory"):
        c.start(c.resolve(m["id"]))
    project.unlink()
    with pytest.raises(c.SandboxError, match="not accessible"):
        c.start(c.resolve(m["id"]))
    assert not any(a[0] == "run" for a in runs) and not project.exists()  # never re-created
    assert c.resolve(m["id"])["status"] == "error"


def test_delete_never_touches_the_direct_directory(monkeypatch, project):
    """The container-based `find -delete` must never receive a direct path."""
    m = direct_env(monkeypatch, project)
    calls = []
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    real = c._remove_all_but_metadata
    attempts = []
    def remove(d):
        attempts.append(Path(d))
        raise PermissionError("simulated")
    monkeypatch.setattr(c, "_remove_all_but_metadata", remove)
    with pytest.raises(c.SandboxError, match="permission denied"):
        c.delete(m, force=True)
    assert calls == [] and attempts == [c.env_dir(m["id"])]
    monkeypatch.setattr(c, "_remove_all_but_metadata", real)
    c.delete(c.resolve(m["id"]), force=True)
    assert not c.env_dir(m["id"]).exists() and (project / "main.py").read_text() == "print('hi')\n"
    assert not any("find" in a for a in calls)


def test_container_removal_stays_below_the_environment_directory(monkeypatch):
    m = c.create("ocs-qa-man", "scratch")
    w = ws.managed_path(m)
    w.rmdir()
    w.symlink_to("/tmp")
    monkeypatch.setattr(c, "_remove_all_but_metadata", lambda d: (_ for _ in ()).throw(PermissionError("x")))
    with pytest.raises(c.SandboxError, match="Refusing container-based removal"):
        c._remove_env_dir(m)


def test_changes_export_and_review_refuse_direct(monkeypatch, project):
    m = direct_env(monkeypatch, project)
    assert c.git_changes(m) == c.DIRECT_CHANGES
    with pytest.raises(c.SandboxError, match="nothing to export"):
        c.export(m)
    with pytest.raises(c.SandboxError, match="nothing to export"):
        gitflow.change_summary(m)


def test_agent_context_describes_direct_without_the_host_path(monkeypatch, project):
    m = direct_env(monkeypatch, project)
    text = ac.render(m, **c.guidance_inputs(m, observe=False))
    assert "user's own host directory, mounted directly (not a copy)" in text
    assert str(project) not in text and "started empty" not in text


def test_config_plan_rechecks_the_directory_before_recreating(monkeypatch, project):
    m = direct_env(monkeypatch, project)
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False})
    p = cp.plan(m, {"network": "none"})
    assert p.blockers == () and "direct host directory is mounted again, unchanged" in " ".join(p.steps)
    project.chmod(0o755)
    (project / "s").mkdir()
    sock = socket.socket(socket.AF_UNIX)
    sock.bind(str(project / "s" / "x.sock"))
    try:
        assert "could not mount the direct workspace" in cp.plan(m, {"network": "none"}).blockers[0]
        assert cp.plan(m, {"cpus": 1}).blockers == ()  # docker update keeps the existing mount
    finally:
        sock.close()


# --- backup and restore ----------------------------------------------------------------------

def _backup_mocks(monkeypatch):
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    monkeypatch.setattr(c, "volume_state", lambda m: None)


def test_backup_excludes_direct_workspace_unless_requested(monkeypatch, project, tmp_path):
    m = direct_env(monkeypatch, project)
    _backup_mocks(monkeypatch)
    plain = b.backup(m, tmp_path / "bk")
    manifest = b.verify(plain)
    assert manifest["workspace"] == {"mode": "direct", "included": False} and "workspace.tar.gz" not in manifest["files"]
    full = b.backup(m, tmp_path / "bk", include_workspace=True)
    assert b.verify(full)["workspace"] == {"mode": "direct", "included": True}
    assert sorted(p.name for p in project.iterdir()) == ["main.py"]
    managed = c.create("ocs-qa-managed", "scratch")
    with pytest.raises(c.SandboxError, match="always part of a backup"):
        b.backup(managed, tmp_path / "bk", include_workspace=False)
    # a manifest that claims a managed workspace without the archive is rejected
    data = json.loads((plain / "manifest.json").read_text())
    data["workspace"]["mode"] = "managed"
    (plain / "manifest.json").write_text(json.dumps(data))
    with pytest.raises(c.SandboxError, match="workspace record"):
        b.verify(plain)


def test_restore_of_a_direct_backup_creates_a_managed_environment(monkeypatch, project, tmp_path):
    m = direct_env(monkeypatch, project)
    _backup_mocks(monkeypatch)
    path = b.backup(m, tmp_path / "bk")
    monkeypatch.setattr(b, "_check_restore_space", lambda *a: None)
    restored = b.restore(path, "ocs-qa-restored")
    assert restored["workspace"] == {"mode": "managed", "path": None}
    assert list(ws.managed_path(restored).iterdir()) == []
    assert "not connected to that directory" in " ".join(restored["restore_warnings"])
    assert sorted(p.name for p in project.iterdir()) == ["main.py"]
    m2 = c.resolve(m["id"])
    c.mark(m2, "error", operation="restore")  # _restore_into requires the restore journal
    with pytest.raises(c.SandboxError, match="never writes into a direct workspace"):
        b._restore_into(m2, path, b.verify(path))


# --- CLI and TUI -------------------------------------------------------------------------------

def test_cli_create_direct_needs_consent(monkeypatch, project):
    FakeDocker(monkeypatch)
    monkeypatch.setattr(c, "_tty", lambda: False)
    args = ["create", "ocs-qa-cli", "--workspace-mode", "direct", "--workspace", str(project)]
    result = runner.invoke(app, args)
    assert result.exit_code != 0 and "Not recommended — direct access to host files" in result.output
    assert "confirm with --yes" in result.output and c.all_envs() == []
    result = runner.invoke(app, ["create", "ocs-qa-cli", "--workspace-mode", "direct", "--workspace", "/etc", "--yes"])
    assert result.exit_code != 0 and "system directory" in str(result.exception)
    result = runner.invoke(app, [*args, "--yes"])
    assert result.exit_code == 0, result.output
    assert f"Workspace: DIRECT host folder {project} (Not recommended" in result.output
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    result = runner.invoke(app, ["config", "show", "ocs-qa-cli"])
    assert json.loads(result.output)["workspace"] == {"mode": "direct", "path": str(project)}
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    result = runner.invoke(app, ["delete", "ocs-qa-cli", "--yes"])
    assert result.exit_code == 0 and f"The direct workspace {project} is not touched." in result.output
    assert (project / "main.py").exists()


def test_tui_direct_creation_asks_for_consent(monkeypatch, project):
    from test_tui import run, settle, stack
    FakeDocker(monkeypatch)

    async def t(app, pilot):
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#name").value = "ocs-qa-tui"
        app.screen.query_one("#kind").value = "project"
        app.screen.query_one("#workspace-mode").value = "direct"
        app.screen.query_one("#source").value = str(project)
        app.screen.query_one("#create").press()
        await settle(pilot)
        assert stack(app)[-1] == "ConfirmScreen" and c.all_envs() == []
        text = str(app.screen.query_one("#confirm-panel Static").render())
        assert "Not recommended — direct access to host files" in text and ".ocs-preflight-" in text
        app.screen.query_one("#confirm").press()
        await settle(pilot, 1.0)
        m = c.resolve("ocs-qa-tui")
        assert m["workspace"]["path"] == str(project)
        app.query_one("#envs").move_cursor(row=0)
        await settle(pilot)
        assert "Workspace: DIRECT" in str(app.query_one("#details").render())
    run(t)


def test_tui_form_reports_a_refused_folder_in_place(monkeypatch, tmp_path):
    """Seen in a real terminal: a hidden path component was refused after the form had
    closed, so everything typed was lost."""
    from test_tui import run, settle, stack
    FakeDocker(monkeypatch)
    hidden = tmp_path / ".hidden" / "proj"
    hidden.mkdir(parents=True)

    async def t(app, pilot):
        await pilot.press("n")
        await settle(pilot)
        app.screen.query_one("#name").value = "ocs-qa-tuihidden"
        app.screen.query_one("#workspace-mode").value = "direct"
        app.screen.query_one("#source").value = str(hidden)
        app.screen.query_one("#create").press()
        await settle(pilot)
        assert stack(app)[-1] == "CreateScreen"
        assert "hidden" in str(app.screen.query_one("#create-error").render())
        assert app.screen.query_one("#name").value == "ocs-qa-tuihidden" and c.all_envs() == []
    run(t)
