"""`install.sh` in a throw-away HOME, answering its prompts in a real terminal (campaign rows
B01, B03–B07): dry run writes nothing, no TTY fails, install, update, failed update keeps the
active release, the README's manual rollback, foreign launcher refused, uninstall keeps data.
Downloads typer/textual from PyPI into the throw-away venvs."""
import os
import subprocess
from pathlib import Path

import pytest
from campaign import ROOT

pyte = pytest.importorskip("pyte")
from pty_term import Term


def listing(home):
    return sorted(str(p.relative_to(home)) for p in home.rglob("*"))


def test_install_update_rollback_uninstall(campaign, checks):
    camp, ck = campaign, checks
    home = Path("/tmp/opencode") / f"ocs-test-{camp.run}" / "home"
    home.mkdir(parents=True, exist_ok=True)
    camp.note(f"host dir {home} (throw-away HOME for install.sh)")
    env = {"HOME": str(home), "PATH": f"{home}/.local/bin:/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
           "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""), "DOCKER_CONFIG": str(Path.home() / ".docker"),
           "PIP_DISABLE_PIP_VERSION_CHECK": "1", "TERM": "xterm-256color"}
    app = home / ".local/share/opencode-sandbox-manager"
    link = home / ".local/bin/opencode-sandbox"

    def run(*args, extra=None, input=None):
        p = subprocess.run(["bash", str(ROOT / "install.sh"), *args], env={**env, **(extra or {})}, capture_output=True,
                           text=True, input=input, timeout=900, stdin=None if input is not None else subprocess.DEVNULL, check=False)
        camp.log(f"$ install.sh {' '.join(args)}\n{p.stdout}{p.stderr}exit={p.returncode}")
        return p

    def interactive(*args, answers=("y", "y"), extra=None):
        t = Term(["bash", str(ROOT / "install.sh"), *args], 120, 40, env={**env, **(extra or {})}, log=camp.log)
        try:
            for n, answer in enumerate(answers, 1):
                if not camp.wait_for(lambda n=n: t.pump(0.2) or t.raw.count(b"[y/N]") >= n or not t.alive, 600, 0):
                    break
                if t.raw.count(b"[y/N]") < n:
                    break  # the installer ended before asking
                t.send(answer + "\r", 1)
            code = t.exit_code(900)
            camp.log(f"$ install.sh {' '.join(args)} (pty)\n{t.text()}\nexit={code}")
            return code, t.text()
        finally:
            t.close()

    before = listing(home)
    p = run("install", "--dry-run")
    ck(p.returncode == 0 and listing(home) == before, "B01 --dry-run writes nothing")
    p = run("doctor")
    ck(p.returncode == 0 and listing(home) == before and "Daemon identity: verified" in p.stdout, "B01 doctor is read-only and verifies the daemon")
    p = run("install")
    ck(p.returncode != 0 and "needs a TTY" in p.stdout + p.stderr and listing(home) == before, "B07 without a terminal: refusal, nothing written")

    code, _text = interactive("install")
    releases = sorted((app / "releases").iterdir()) if (app / "releases").exists() else []
    ck(code == 0 and len(releases) == 1 and (app / "current").resolve() == releases[0], f"B03 install: one release, current points at it ({code})")
    ck(link.is_symlink() and os.readlink(link) == str(app / "current/bin/opencode-sandbox"), "B03 launcher links to current")
    version = subprocess.run([str(link), "--version"], env=env, capture_output=True, text=True, check=False)
    ck(version.stdout.strip() == "opencode-sandbox 6.0.0", f"B03 the launcher runs ({version.stdout.strip()})")
    doctor = subprocess.run([str(link), "doctor"], env=env, capture_output=True, text=True, check=False)
    ck(doctor.returncode == 0 and "Daemon identity: verified" in doctor.stdout, "B03 installed manager: doctor passes")

    code, _text = interactive("update", answers=("y",))
    releases = sorted((app / "releases").iterdir())
    ck(code == 0 and len(releases) == 2 and (app / "current").resolve() == releases[1], "B04 update: new release active, previous kept")

    # B04 a failed update (package index unreachable, no cache) keeps the active release
    code, _text = interactive("update", answers=("y",), extra={"PIP_INDEX_URL": "http://127.0.0.1:9/simple", "PIP_NO_CACHE_DIR": "1"})
    after = sorted((app / "releases").iterdir())
    ck(code != 0 and after == releases and (app / "current").resolve() == releases[1], f"B04 failed update: exit {code}, current unchanged, no partial release")
    ck(subprocess.run([str(link), "--version"], env=env, capture_output=True, check=False).returncode == 0, "B04 the launcher still works")

    # B05 the README's manual rollback
    r = subprocess.run(f"cd {app} && ln -sfn releases/{releases[0].name} .current.tmp && mv -Tf .current.tmp current",
                       shell=True, env=env, capture_output=True, text=True, check=False)
    ck(r.returncode == 0 and (app / "current").resolve() == releases[0]
       and subprocess.run([str(link), "--version"], env=env, capture_output=True, check=False).returncode == 0, "B05 manual rollback works")

    # B06 uninstall: a foreign launcher is refused; data and configuration are kept
    data = home / ".local/share/opencode-sandbox"
    config = home / ".config/opencode-sandbox"
    for d in (data, config):
        d.mkdir(parents=True, exist_ok=True)
        (d / "ocs-test-keep").write_text("keep")
    link.unlink()
    link.symlink_to("/usr/bin/true")
    p = run("uninstall")
    ck(p.returncode != 0 and "another application" in p.stdout + p.stderr and (app / "releases").exists(), "B06 foreign launcher refused")
    link.unlink()
    link.symlink_to(app / "current/bin/opencode-sandbox")
    code, _text = interactive("uninstall", answers=("y",))
    ck(code == 0 and not (app / "releases").exists() and not (app / "current").exists() and not link.exists(),
       "B06 uninstall removed releases, current and the launcher")
    ck((data / "ocs-test-keep").exists() and (config / "ocs-test-keep").exists(), "B06 data and configuration directories kept")
    subprocess.run(["rm", "-rf", "--", str(home)], check=True)
    camp.note(f"removed host dir {home}")
