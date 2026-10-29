"""install.sh behaviour that needs no network: read-only modes, refusals, non-TTY (B01, B07)."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def listing(path):
    return sorted((str(p.relative_to(path)), p.is_symlink(), p.stat(follow_symlinks=False).st_mode) for p in path.rglob("*"))


def run(home, *args, stdin=subprocess.DEVNULL, prefix=()):
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    return subprocess.run([*prefix, "bash", str(ROOT / "install.sh"), *args], env=env, stdin=stdin,
                          capture_output=True, text=True, timeout=120, check=False)


@pytest.mark.parametrize("args", [["doctor"], ["install", "--dry-run"], ["update", "--dry-run"],
                                  ["uninstall", "--dry-run"], ["verify", "--dry-run"]])
def test_read_only_modes_write_nothing(tmp_path, args):
    before = listing(tmp_path)
    result = run(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    assert listing(tmp_path) == before


@pytest.mark.parametrize("action", ["install", "update", "uninstall"])
def test_non_tty_changes_fail_instead_of_reporting_success(tmp_path, action):
    """B07: without a TTY nothing can be confirmed; exit status must say so."""
    if action == "update":  # update requires an existing release
        rel = tmp_path / ".local/share/opencode-sandbox-manager/releases/r/bin"
        rel.mkdir(parents=True)
        (rel / "python").symlink_to(shutil.which("python3"))
        (tmp_path / ".local/share/opencode-sandbox-manager/current").symlink_to(rel.parent)
    before = listing(tmp_path)
    result = run(tmp_path, action)
    assert result.returncode != 0
    assert "confirmation needs a TTY" in result.stderr
    assert listing(tmp_path) == before


@pytest.mark.skipif(shutil.which("unshare") is None, reason="needs util-linux unshare")
def test_refuses_root(tmp_path):
    probe = subprocess.run(["unshare", "-r", "true"], capture_output=True, check=False)
    if probe.returncode:
        pytest.skip("unprivileged user namespaces unavailable")
    result = run(tmp_path, "doctor", prefix=("unshare", "-r"))
    assert result.returncode == 1 and "refuse root" in result.stderr


def test_foreign_launcher_and_symlinked_app_dir_refused(tmp_path):
    (tmp_path / ".local/bin").mkdir(parents=True)
    (tmp_path / ".local/bin/opencode-sandbox").symlink_to("/usr/bin/true")
    result = run(tmp_path, "uninstall", "--dry-run")
    assert result.returncode == 1 and "belongs to another application" in result.stderr
    assert "pipx" not in result.stderr
    (tmp_path / ".local/bin/opencode-sandbox").unlink()
    # A pipx installation (D-042) has the same command name: say how to resolve it.
    for pipx_home in (".local/share/pipx", "custom-pipx-home"):  # the default and a PIPX_HOME of the user's choice
        (tmp_path / ".local/bin/opencode-sandbox").symlink_to(tmp_path / pipx_home / "venvs/opencode-sandbox/bin/opencode-sandbox")
        result = run(tmp_path, "doctor")
        assert result.returncode == 1 and "pipx uninstall opencode-sandbox" in result.stderr, pipx_home
        (tmp_path / ".local/bin/opencode-sandbox").unlink()
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / ".local/share").symlink_to(tmp_path / "elsewhere")
    result = run(tmp_path, "install", "--dry-run")
    assert result.returncode == 1 and "symlink in managed path" in result.stderr


def test_python_older_than_minimum_is_reported_and_refused(tmp_path):
    """The supported minimum is the tested Python (3.14); an older interpreter must not install."""
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "python").write_text("#!/bin/sh\nexec /usr/bin/python3 -c 'import sys; sys.version_info = (3, 13, 9); "
                                 "exec(compile(sys.stdin.read(), \"<stdin>\", \"exec\"))'\n")
    (fake / "python").chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    env = {"HOME": str(home), "PATH": f"{fake}:/usr/bin:/bin"}
    doctor = subprocess.run(["bash", str(ROOT / "install.sh"), "doctor"], env=env, capture_output=True, text=True, timeout=120,
                            check=False)
    assert "python>=3.14" in doctor.stdout + doctor.stderr
    before = listing(home)
    install = subprocess.run(["bash", str(ROOT / "install.sh"), "install"], env=env, stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=120, check=False)
    assert install.returncode != 0 and "Python 3.14+ required" in install.stderr
    assert listing(home) == before


def test_doctor_and_verify_use_the_daemon_identity_check(tmp_path):
    """An empty HOME has no 'rootless' context, so the daemon is not verified; verify fails closed."""
    doctor = run(tmp_path, "doctor")
    assert doctor.returncode == 0, doctor.stderr
    if "Docker CLI unavailable" not in doctor.stdout:
        assert "Daemon identity: not-configured" in doctor.stdout  # no context in an empty HOME
        assert "Agent image" not in doctor.stdout  # never inspected on an unverified daemon
    verify = run(tmp_path, "verify")
    assert verify.returncode == 1
    assert "not verified" in verify.stderr or "Docker CLI missing" in verify.stderr


def test_verifier_without_output_is_not_trusted(tmp_path):
    """A python that exits 0 without a 'verified' report (here: a stub) must not count as verified."""
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "python").write_text("#!/bin/sh\nexit 0\n")
    (fake / "python").chmod(0o755)
    (fake / "docker").write_text("#!/bin/sh\necho 'docker must not be called' >&2; exit 99\n")
    (fake / "docker").chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    env = {"HOME": str(home), "PATH": f"{fake}:/usr/bin:/bin"}
    verify = subprocess.run(["bash", str(ROOT / "install.sh"), "verify"], check=False, env=env, capture_output=True,
                            text=True, timeout=120, stdin=subprocess.DEVNULL)
    assert verify.returncode == 1 and "not verified" in verify.stderr
    assert "docker must not be called" not in verify.stderr


def test_setup_rootless_finds_the_upstream_tool_in_local_bin(tmp_path):
    """The tool in ~/.local/bin was reported MISSING
    when that directory was not on PATH, next to a READY final check."""
    tool = tmp_path / ".local/bin/dockerd-rootless-setuptool.sh"
    tool.parent.mkdir(parents=True)
    tool.write_text("#!/bin/sh\nexit 0\n")
    tool.chmod(0o755)
    result = subprocess.run(["bash", str(ROOT / "setup-rootless.sh"), "--dry-run"], env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120, check=False)
    assert "[OK] dockerd-rootless-setuptool.sh (in ~/.local/bin, which is not on PATH)" in result.stdout, result.stdout
    tool.unlink()
    result = subprocess.run(["bash", str(ROOT / "setup-rootless.sh"), "--dry-run"], env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120, check=False)
    assert "[MISSING] dockerd-rootless-setuptool.sh" in result.stdout
