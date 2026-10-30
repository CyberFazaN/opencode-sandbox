"""D-056: real host files/processes, fake daemon identity; no real Docker mutations."""
import contextvars
import os
import stat
import subprocess
import sys

import pytest

from opencode_sandbox import base_locks as bl
from opencode_sandbox import core as c


def child(tmp_path, code, *, endpoint=None):
    """A fresh interpreter with unrelated product/runtime/home overrides and context alias."""
    prefix = f"""
from pathlib import Path
from opencode_sandbox import base_locks as bl, core as c
bl._TMP = Path({str(bl._TMP)!r})
c._ENDPOINT = {endpoint or c.docker_endpoint()!r}
c.CONTEXT = 'different-context-alias'
"""
    env = {**os.environ, "OPENCODE_SANDBOX_HOME": str(tmp_path / "other-data"),
           "OPENCODE_SANDBOX_CONFIG": str(tmp_path / "other-config"),
           "HOME": str(tmp_path / "other-home"), "TMPDIR": str(tmp_path / "other-tmp"),
           "XDG_RUNTIME_DIR": str(tmp_path / "other-runtime")}
    return subprocess.run([sys.executable, "-B", "-c", prefix + code], text=True,
                          capture_output=True, env=env, timeout=10, check=False)


@pytest.mark.parametrize("phase", ["build", "publication"])
def test_processes_converge_despite_data_config_context_and_runtime_overrides(tmp_path, phase):
    code = f"""
try:
    with c.base_lock('debian', {phase!r}, timeout=0): print('acquired')
except c.SandboxError as exc:
    print(exc)
"""
    with c.base_lock("debian", phase):
        p = child(tmp_path, code)
        assert p.returncode == 0 and "Base image busy:" in p.stdout, p.stderr
    p = child(tmp_path, code)
    assert p.returncode == 0 and p.stdout.strip() == "acquired", p.stderr
    assert not c.BASE.exists() and not c.CONFIG.exists()  # no product directories for base guards


@pytest.mark.parametrize("phase", ["build", "publication"])
def test_guards_are_independent_for_daemons_and_distributions(tmp_path, phase):
    code = f"with c.base_lock('arch', {phase!r}, timeout=0): print('acquired')"
    with c.base_lock("debian", phase):
        p = child(tmp_path, code)
        assert p.returncode == 0 and "acquired" in p.stdout, p.stderr
        p = child(tmp_path, f"with c.base_lock('debian', {phase!r}, timeout=0): print('acquired')",
                  endpoint="unix:///different/verified.sock")
        assert p.returncode == 0 and "acquired" in p.stdout, p.stderr


def test_build_does_not_exclude_creation_but_publication_does(tmp_path):
    code = "with c.base_tag_lock({'distro':'debian'}): print('acquired')"
    with c.base_lock("debian", "build"):
        assert child(tmp_path, code).returncode == 0
        with c.base_lock("debian", "publication"):
            p = child(tmp_path, """
try:
    with c.base_lock('debian', 'publication', timeout=0): print('acquired')
except c.SandboxError: print('busy')
""")
            assert p.stdout.strip() == "busy", p.stderr


def test_lock_order_refuses_data_callback_and_publication_to_build():
    with c.base_lock("debian", "publication"):
        with pytest.raises(c.SandboxError, match="order violation"), c.lock("registry"):
            pytest.fail("earlier lock acquired")
        with pytest.raises(c.SandboxError, match="order violation"), c.base_lock("debian", "build", timeout=0):
            pytest.fail("earlier lock acquired")
    with c.lock("registry"), c.lock("0" * 16), c.base_lock("debian", "build"), c.base_lock("debian", "publication"):
        assert bl.held()
    assert not bl.held()


def test_separate_execution_contexts_exclude_each_other():
    def attempt():
        with c.base_lock("debian", "build", timeout=0):
            pytest.fail("another caller acquired the guard")
    with c.base_lock("debian", "build"), pytest.raises(c.SandboxError, match="busy"):
        contextvars.Context().run(attempt)


def namespace():
    return bl._TMP / f"opencode-sandbox-locks-{os.getuid()}"


def test_private_modes_stable_inode_and_noninheritable_descriptors(tmp_path):
    with c.base_lock("debian", "build"):
        path, = namespace().glob("*.lock")
        before = path.stat()
        # Even close_fds=False must not leak the flock into a freshly exec'd child.
        code = f"""
import os, sys
found = []
for name in os.listdir('/proc/self/fd'):
    try: info = os.fstat(int(name))
    except OSError: continue
    if (info.st_dev, info.st_ino) == {(before.st_dev, before.st_ino)!r}: found.append(name)
print(found, flush=True)
sys.stdin.read()
"""
        p = subprocess.Popen([sys.executable, "-c", code], text=True, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, close_fds=False)
    try:
        assert p.stdout.readline().strip() == "[]"
        with c.base_lock("debian", "build", timeout=0):
            assert path.stat().st_ino == before.st_ino
        assert stat.S_IMODE(namespace().stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    finally:
        p.communicate(timeout=5)
    assert child(tmp_path, "with c.base_lock('debian','build',timeout=0): print('acquired')").returncode == 0


@pytest.mark.parametrize("bad", ["symlink", "permissions", "file"])
def test_unsafe_namespace_is_refused_without_repair(tmp_path, bad):
    target = namespace()
    if bad == "symlink":
        other = tmp_path / "other"
        other.mkdir()
        target.symlink_to(other, target_is_directory=True)
    elif bad == "permissions":
        target.mkdir(mode=0o755)
    else:
        target.write_text("not a directory")
    before = target.lstat()
    with pytest.raises(c.SandboxError, match="[Uu]nsafe|safely"), c.base_lock("debian", "build", timeout=0):
        pytest.fail("unsafe namespace accepted")
    assert target.lstat() == before


@pytest.mark.parametrize("bad", ["symlink", "hardlink", "permissions", "fifo", "directory"])
def test_unsafe_lock_file_is_refused_without_repair(tmp_path, bad):
    with c.base_lock("debian", "build"):
        path, = namespace().glob("*.lock")
    path.unlink()  # test-owned file, not held; fault injection only
    if bad == "symlink":
        other = tmp_path / "target"
        other.write_text("must stay")
        path.symlink_to(other)
    elif bad == "hardlink":
        other = tmp_path / "target"
        other.touch(mode=0o600)
        os.link(other, path)
    elif bad == "permissions":
        path.touch(mode=0o644)
    elif bad == "fifo":
        os.mkfifo(path, mode=0o600)
    else:
        path.mkdir(mode=0o700)
    before = path.lstat()
    with pytest.raises(c.SandboxError, match="[Uu]nsafe|safely"), c.base_lock("debian", "build", timeout=0):
        pytest.fail("unsafe lock accepted")
    assert path.lstat() == before


def test_foreign_directory_owner_is_refused(monkeypatch):
    # No chown/sudo needed: ownership proof is independent of the permission proof.
    namespace().mkdir(mode=0o700)
    inode = namespace().stat().st_ino
    real = bl.os.fstat
    def fstat(fd):
        result = real(fd)
        if result.st_ino == inode:
            fields = list(result)
            fields[4] = os.getuid() + 1
            return os.stat_result(fields)
        return result
    monkeypatch.setattr(bl.os, "fstat", fstat)
    with pytest.raises(c.SandboxError, match="own UID"), c.base_lock("debian", "build"):
        pytest.fail("foreign directory accepted")


def test_identity_must_be_verified_before_creating_lock_files(monkeypatch):
    def fail():
        raise c.SandboxError("daemon identity refused")
    monkeypatch.setattr(c, "verify_runtime", fail)
    with pytest.raises(c.SandboxError, match="identity refused"), c.base_lock("debian", "build"):
        pytest.fail("unverified daemon accepted")
    assert not namespace().exists()


def test_body_error_is_not_misreported_as_a_lock_namespace_failure():
    with pytest.raises(OSError, match="operation failed"), c.base_lock("debian", "build"):
        raise OSError("operation failed")
    with c.base_lock("debian", "build", timeout=0):
        assert bl.held()


@pytest.mark.parametrize("directory", [False, True])
def test_replaced_path_is_detected_after_acquisition(monkeypatch, directory):
    real = bl.fcntl.flock
    def flock(fd, operation):
        real(fd, operation)
        if operation & bl.fcntl.LOCK_EX:
            path = namespace() if directory else next(namespace().glob("*.lock"))
            path.rename(path.with_name(path.name + ".moved"))
            if directory:
                path.mkdir(mode=0o700)
            else:
                path.touch(mode=0o600)
    monkeypatch.setattr(bl.fcntl, "flock", flock)
    with pytest.raises(c.SandboxError, match="path changed"), c.base_lock("debian", "build"):
        pytest.fail("a replaced lock pathname was accepted")


def test_process_death_releases_lock_without_replacing_inode(tmp_path):
    script = tmp_path / "holder.py"
    script.write_text(f"""
from pathlib import Path
from opencode_sandbox import core as c, base_locks as bl
bl._TMP = Path({str(bl._TMP)!r})
c._ENDPOINT = {c.docker_endpoint()!r}
with c.base_lock('debian','build'):
    print('ready', flush=True)
    input()
""")
    p = subprocess.Popen([sys.executable, "-B", str(script)], text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        assert p.stdout.readline().strip() == "ready"
        path, = namespace().glob("*.lock")
        inode = path.stat().st_ino
        p.kill()
        p.communicate(timeout=5)
        with c.base_lock("debian", "build", timeout=0):
            assert path.stat().st_ino == inode
    finally:
        if p.poll() is None:
            p.kill()
        p.communicate(timeout=5)
