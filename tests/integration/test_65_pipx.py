"""The documented installation (D-042): pipx from the Git repository at a version tag, without a
source checkout (campaign rows B09–B12). A disposable clone of this repository's HEAD gets two
test tags (the current version and the next patch version; the tags exist only in the clone), and
pipx runs with its own PIPX_HOME and a private HOME, so neither the user's pipx nor their
launchers are touched; Docker is the user's rootless daemon through the unchanged Docker context.

Measured and asserted: install, run without the source tree, the bundled image assets, an
environment created, started and used; `pipx upgrade` and `pipx reinstall` keep a tag spec as it
is, `pipx install --force <spec>@<tag>` moves to another tag (also back), data survive both and
`pipx uninstall`; an install.sh launcher and a pipx launcher never replace each other.

OCS_TEST_PIPX_BUILD=1 adds a full image build from the installed package's assets into an
`ocs-test-` tag (downloads the distribution's base image; both are removed again when they were
not present before; Docker's build cache keeps the layers)."""
import json
import os
import shutil
import sys
from pathlib import Path

from campaign import ROOT

NAME = "ocs-test-pipx"


def pipx_command():
    try:
        import pipx  # noqa: F401
        return [sys.executable, "-m", "pipx"]
    except ImportError:
        found = shutil.which("pipx")
        return [found] if found else None


def test_pipx_install_upgrade_uninstall(campaign, checks):
    camp, ck = campaign, checks
    pipx = pipx_command()
    assert pipx, "pipx is needed: pip install pipx in the test venv"
    base = camp.tmp("pipx")
    repo, home, pipx_home = base / "repo", base / "home", base / "pipx-home"
    bindir = home / ".local" / "bin"
    camp._run(["git", "clone", "--quiet", "--no-local", str(ROOT), str(repo)], check=True)
    head = camp._run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True).stdout.strip()
    init = repo / "src" / "opencode_sandbox" / "__init__.py"
    v1 = init.read_text().split('"')[1]
    major_minor, patch = v1.rsplit(".", 1)
    v2 = f"{major_minor}.{int(patch) + 1}"
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    camp._run([*git, "tag", "-a", f"v{v1}", "-m", "test tag"], check=True)
    init.write_text(init.read_text().replace(f'"{v1}"', f'"{v2}"'))
    camp._run([*git, "commit", "-qam", f"test: {v2}"], check=True)
    camp._run([*git, "tag", "-a", f"v{v2}", "-m", "test tag"], check=True)
    camp.note(f"pipx clone {repo} of {head} with test tags v{v1}, v{v2}; PIPX_HOME {pipx_home}")
    url = f"git+file://{repo}"

    env = {k: v for k, v in camp.env.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
    env.update(HOME=str(home), PIPX_HOME=str(pipx_home), PIPX_BIN_DIR=str(bindir),
               PIPX_MAN_DIR=str(home / ".local/share/man"), PWD="/",
               DOCKER_CONFIG=str(Path(os.path.expanduser("~")) / ".docker"),
               PATH=f"{bindir}:/usr/bin:/bin")
    home.mkdir()
    launcher = bindir / "opencode-sandbox"

    def px(*args, check=True):
        return camp._run([*pipx, *args], check=check, env=env)

    def ocs(*args, check=True):
        return camp._run([str(launcher), *args], check=check, env=env, label="(pipx) opencode-sandbox " + " ".join(args))

    def version():
        p = ocs("--version", check=False)
        return p.stdout.strip().rsplit(" ", 1)[-1] if p.returncode == 0 else None

    # B09 install from a tag, run without the source tree
    p = px("install", f"{url}@v{v1}")
    ck(p.returncode == 0 and launcher.is_symlink() and version() == v1, f"B09 pipx install @v{v1}: launcher, --version {version()}")
    venv_python = pipx_home / "venvs" / "opencode-sandbox" / "bin" / "python"
    where = camp._run([str(venv_python), "-I", "-c", ("import json, opencode_sandbox, opencode_sandbox.distros as d; print(json.dumps("
                       "[opencode_sandbox.__file__, sorted(str(p.relative_to(d.IMAGES)) for p in d.IMAGES.rglob('*') if p.is_file())]))")],
                      check=True, env=env)
    module, assets = json.loads(where.stdout)
    ck(module.startswith(str(pipx_home)) and not module.startswith(str(ROOT / "src")),
       f"B09 the installed package runs, not the source tree ({module})")
    ck(assets == sorted(str(p.relative_to(ROOT / "src/opencode_sandbox/assets/images"))
                        for p in (ROOT / "src/opencode_sandbox/assets/images").rglob("*") if p.is_file()),
       f"B09 every image asset is installed ({len(assets)})")
    ck(ocs("--help", check=False).returncode == 0, "B09 --help")
    doctor = ocs("doctor", check=False)
    ck(doctor.returncode == 0 and "Daemon identity: verified" in doctor.stdout, f"B09 doctor of the installed manager (exit {doctor.returncode})")

    # B10 an environment through the installed manager
    ocs("create", NAME, "--no-integrations")
    camp.adopt(NAME)
    ocs("start", NAME)
    os_release = ocs("exec", NAME, "--", "cat", "/etc/os-release", check=False)
    ck(os_release.returncode == 0 and "Debian" in os_release.stdout, "B10 create, start and exec through the pipx installation")
    ocs("stop", NAME)

    if os.environ.get("OCS_TEST_PIPX_BUILD") == "1":
        tag = "ocs-test-pipx-build:debian"
        source = "node:24-bookworm"
        had_source = camp.docker("image", "inspect", source, check=False).returncode == 0
        camp.note(f"image {tag} (build from the installed assets); {source} present before: {had_source}")
        build = camp._run([str(venv_python), "-I", "-c",
                           ("from opencode_sandbox import core as c, distros as d\n"
                           f"c.build_image(d.get('debian'), '2.2.0', {tag!r}); print(d.IMAGES)")],
                          check=False, env=env, timeout=3600)
        ck(build.returncode == 0 and str(pipx_home) in build.stdout,
           f"B10 a full image build and verification from the installed package's assets (exit {build.returncode})")
        camp.docker("image", "rm", tag, check=False)
        if not had_source:
            camp.docker("image", "rm", source, check=False)

    # B11 upgrade and downgrade between tags
    px("upgrade", "opencode-sandbox", check=False)
    ck(version() == v1, f"B11 pipx upgrade keeps the tag spec (still {version()})")
    px("reinstall", "opencode-sandbox", check=False)
    ck(version() == v1, f"B11 pipx reinstall keeps the tag spec (still {version()})")
    plain = px("install", f"{url}@v{v2}", check=False)
    ck(version() == v1 and "--force" in plain.stdout + plain.stderr, "B11 pipx install without --force does not replace an installation")
    px("install", "--force", f"{url}@v{v2}")
    ck(version() == v2, f"B11 pipx install --force @v{v2} upgrades ({version()})")
    ck(NAME in ocs("list").stdout, "B11 environments survive the upgrade")
    px("install", "--force", f"{url}@v{v1}")
    ck(version() == v1, f"B11 pipx install --force @v{v1} goes back ({version()})")
    spec = json.loads(px("list", "--json").stdout)["venvs"]["opencode-sandbox"]["metadata"]["main_package"]["package_or_url"]
    ck(spec == f"{url}@v{v1}", f"B11 pipx records the tag spec ({spec})")

    # B12 uninstall keeps data; launchers of install.sh and pipx never replace each other
    eid = camp.ids[NAME]
    px("uninstall", "opencode-sandbox")
    ck(not launcher.exists() and not launcher.is_symlink(), "B12 pipx uninstall removes the launcher")
    ck((camp.data / "environments" / eid / "metadata.json").is_file()
       and camp.docker("container", "inspect", f"ocs-{eid}", check=False).returncode == 0,
       "B12 pipx uninstall keeps environments, their containers and volumes")
    release = home / ".local/share/opencode-sandbox-manager/current/bin/opencode-sandbox"
    release.parent.mkdir(parents=True)
    release.write_text("#!/bin/sh\necho install.sh-release\n")
    release.chmod(0o755)
    bindir.mkdir(parents=True, exist_ok=True)
    launcher.symlink_to(release)
    p = px("install", f"{url}@v{v1}", check=False)
    ck(os.readlink(launcher) == str(release) and "Not modifying" in p.stdout + p.stderr,
       "B12 pipx does not replace an install.sh launcher (warns 'Not modifying')")
    px("uninstall", "opencode-sandbox")
    ck(os.readlink(launcher) == str(release), "B12 pipx uninstall leaves the install.sh launcher")
    launcher.unlink()
    shutil.rmtree(home / ".local/share/opencode-sandbox-manager")
    px("install", f"{url}@v{v1}")
    p = camp._run(["bash", str(ROOT / "install.sh"), "doctor"], check=False, env=env)
    ck(p.returncode == 1 and "pipx uninstall opencode-sandbox" in p.stderr and os.readlink(launcher).startswith(str(pipx_home)),
       "B12 install.sh refuses a pipx launcher and says how to resolve it")
    px("uninstall", "opencode-sandbox")
    ck(not (pipx_home / "venvs" / "opencode-sandbox").exists(), "B12 nothing of the pipx installation is left in PIPX_HOME")
