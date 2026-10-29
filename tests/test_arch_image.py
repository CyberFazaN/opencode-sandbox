"""D-006: Arch image contract and the ocs-aur privilege broker (logic only; the real
container behaviour is covered by the campaign in tests/integration)."""
import os
import re
import subprocess
import types

import pytest

from opencode_sandbox import distros

ARCH = distros.REGISTRY["arch"]
SCRIPT = distros.IMAGES / "arch" / "ocs-aur"


def load():
    # Not via an import loader: that would write __pycache__ into the image assets.
    module = types.ModuleType("ocs_aur")
    exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), module.__dict__)  # noqa: S102
    return module


aur = load()


def test_registry_record():
    assert ARCH.image == "opencode-sandbox:arch" and ARCH.version == "rolling" and ARCH.package_manager == "pacman"
    assert dict(ARCH.os_release) == {"ID": "arch", "BUILD_ID": "rolling"}
    assert {ARCH.aur_helper, "ocs-aur", "makepkg"} <= set(ARCH.tools) and "ocs-aur --version" in ARCH.smoke
    assert aur.HELPER == f"/usr/bin/{ARCH.aur_helper}"
    text = "\n".join(ARCH.context_lines())
    assert "Base OS: Arch Linux rolling. Use pacman" in text and "pacman -Syu --needed PACKAGE" in text
    assert "ocs-aur -S PACKAGE" in text and "aurbuild" in text and "ocs-aur -Gp PACKAGE" in text
    assert "never in /workspace" in text
    assert "ocs-aur" not in "\n".join(distros.REGISTRY["debian"].context_lines())


def test_dockerfile_contract():
    text = ARCH.dockerfile.read_text()
    assert text.startswith("# Build context") and "FROM archlinux:base-devel AS base" in text
    # The helper is built by the unprivileged user, in its own stage; makepkg never runs as root.
    lines = text.splitlines()
    user = next(i for i, line in enumerate(lines) if line.strip() == "USER aurbuild")
    makepkg = [i for i, line in enumerate(lines) if "makepkg --" in line]
    assert makepkg and all(i > user for i in makepkg)
    assert all(not line.startswith("USER ") for line in lines[makepkg[-1]:])  # final stage starts as root again
    assert re.search(r"ARG PARU_AUR_COMMIT=[0-9a-f]{40}\n", text)  # reviewed PKGBUILD revision
    assert "RUN --mount=type=bind,from=paru," in text and "pacman -U" in text and "rust" not in text.split("FROM base\n")[1]
    assert "COPY --chmod=0755 arch/ocs-aur /usr/local/bin/ocs-aur" in text
    assert f"ln -s /usr/local/bin/ocs-aur {aur.SUDO}" in text
    assert "--home-dir /var/lib/aurbuild" in text and "OPTIONS+=(!debug)" in text
    assert "ENV NPM_CONFIG_PREFIX=/usr/local" in text  # npm -g stays out of pacman's /usr/lib
    assert "sudoers" not in text and "chmod u+s" not in text and "setcap" not in text


def test_build_retries_pacman_downloads():
    """Mirror transfers stalled during builds; every pacman download step retries."""
    text = ARCH.dockerfile.read_text()
    retry = distros.IMAGES / "arch" / "pacman-retry"
    assert subprocess.run(["sh", "-n", str(retry)], check=False).returncode == 0
    assert 'for attempt in 1 2 3; do' in retry.read_text() and 'pacman "$@" && exit 0' in retry.read_text()
    downloads = [line for line in text.splitlines() if re.search(r"pacman(-retry)? .*-S", line)]
    assert downloads and all("pacman-retry" in line for line in downloads)


def test_script_runs_isolated_python():
    first = SCRIPT.read_text().splitlines()[0]
    assert first == "#!/usr/bin/python3 -I" and os.access(SCRIPT, os.X_OK)


@pytest.mark.parametrize("argv", [
    ["pacman", "-S", "--asdeps", "--noconfirm", "foo"],
    ["/usr/bin/pacman", "-U", "/var/lib/aurbuild/.cache/paru/clone/foo/foo-1-1-any.pkg.tar.zst"],
    ["pacman", "--config", "/etc/pacman.conf", "-U", "x.pkg.tar.zst"],
    ["pacman", "--config=/etc/pacman.conf", "-D", "--asdeps", "foo"],
    ["pacman", "-Rns", "foo", "--", "--root"],
])
def test_broker_allows_pacman(argv):
    assert aur.check_pacman(argv) == [aur.PACMAN, *argv[1:]]


@pytest.mark.parametrize("argv,match", [
    (["/bin/sh", "-c", "id"], "only pacman"),
    (["pacmanx", "-Q"], "only pacman"),
    (["pacman", "--root", "/tmp", "-Q"], "--root"),
    (["pacman", "-r", "/tmp", "-Q"], "-r"),
    (["pacman", "--dbpath=/tmp", "-Q"], "--dbpath"),
    (["pacman", "--hookdir", "/tmp/hooks", "-S", "x"], "--hookdir"),
    (["pacman", "--config", "/tmp/pacman.conf", "-S", "x"], "--config"),
    (["pacman", "--config"], "--config"),
    (["pacman", "-U", "/workspace/evil.pkg.tar.zst"], "is in /workspace"),
    (["pacman", "-U", "/var/lib/aurbuild/../../../workspace/x"], "is in /workspace"),
    ([], "malformed"),
    ("pacman -Q", "malformed"),
    (["pacman", 1], "malformed"),
])
def test_broker_refuses(argv, match):
    with pytest.raises(ValueError, match=re.escape(match)):
        aur.check_pacman(argv)


def test_helper_options_managed_by_the_wrapper():
    for arg in ("--sudo", "--sudo=/bin/sh", "--clonedir", "--clonedir=/workspace", "--chroot", "--makepkg"):
        assert aur.refused_option(arg, aur.HELPER_REFUSED)
    for arg in ("-S", "--noconfirm", "--skipreview", "-Gp", "--sudoers-like-name-but-not"):
        assert not aur.refused_option(arg, aur.HELPER_REFUSED)
    assert aur.under_workspace("/workspace") and aur.under_workspace("/workspace/a/b")
    assert not aur.under_workspace("/workspaces/x") and not aur.under_workspace("pkgname")


def test_wrapper_refuses_non_root_and_client_outside_a_session(monkeypatch, capsys):
    monkeypatch.setattr(aur.os, "geteuid", lambda: 1000)
    with pytest.raises(SystemExit) as exc:
        aur.main(["-S", "foo"])
    assert exc.value.code == 2 and "run as root" in capsys.readouterr().err
    monkeypatch.delenv("OCS_AUR_SOCKET", raising=False)
    with pytest.raises(SystemExit) as exc:
        aur.elevate(["pacman", "-Q"])
    assert exc.value.code == 1 and "only works inside" in capsys.readouterr().err


def test_caller_must_be_a_direct_child_of_the_helper():
    assert aur.parent(os.getpid()) == os.getppid()
    aur.check_caller(os.getpid(), os.getppid())
    with pytest.raises(ValueError, match="does not come from the AUR helper"):
        aur.check_caller(os.getpid(), os.getpid())


def test_clean_environment_drops_secrets(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret")
    monkeypatch.setenv("TERM", "xterm")
    env = aur.clean_env(HOME="/var/lib/aurbuild")
    assert "OPENROUTER_API_KEY" not in env and env["TERM"] == "xterm" and env["PATH"] == "/usr/local/bin:/usr/bin"
