"""Helpers of the real campaign (see conftest.py)."""
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENABLED = os.environ.get("OCS_TEST_DOCKER") == "1"
SOCKET = f"unix:///run/user/{os.getuid()}/docker.sock"
DISTROS = os.environ.get("OCS_TEST_DISTROS", "debian arch").split()
# The manager under test: the source tree, or an installed launcher such as a pipx installation
# (OCS_TEST_MANAGER=/path/to/opencode-sandbox); then the source tree is not put on PYTHONPATH, so
# the commands run the installed package. Helper snippets still import the test venv's package.
INSTALLED = os.environ.get("OCS_TEST_MANAGER")
MANAGER = shlex.split(INSTALLED) if INSTALLED else [sys.executable, "-m", "opencode_sandbox.cli"]


class Campaign:
    def __init__(self, run):
        self.run = run
        self.base = ROOT / ".work" / run
        self.short_dirs = []
        self.data, self.config = self.base / "data", self.base / "config"
        self.logs = ROOT / ".work" / "logs"
        self.logs.mkdir(parents=True, exist_ok=True)
        self.log_path = self.logs / f"{run}.log"
        self.manifest_path = self.logs / f"{run}-manifest.txt"
        self.base.mkdir(parents=True, exist_ok=True)
        self.env = {k: v for k, v in os.environ.items() if k not in ("DOCKER_HOST", "DOCKER_CONTEXT", "PYTHONPATH")}
        self.env.update(OPENCODE_SANDBOX_HOME=str(self.data), OPENCODE_SANDBOX_CONFIG=str(self.config),
                        PYTHONDONTWRITEBYTECODE="1")
        if not INSTALLED:
            self.env["PYTHONPATH"] = str(ROOT / "src")
        self.ids = {}
        self.note(f"run-id {run}")
        self.note(f"manager under test: {shlex.join(MANAGER)}")

    # records -------------------------------------------------------------------------------
    def log(self, text):
        with self.log_path.open("a") as f:
            f.write(text.rstrip("\n") + "\n")

    def note(self, text):
        with self.manifest_path.open("a") as f:
            f.write(text + "\n")

    def tmp(self, name):
        path = self.base / name
        path.mkdir(parents=True, exist_ok=True)
        self.note(f"host dir {path}")
        return path

    def short_dir(self, name):
        """For Unix sockets (paths of at most 108 bytes): a directory outside the checkout, which may
        be deep; removed at the campaign end."""
        path = Path("/tmp/opencode") / f"ocs-test-{self.run}" / name
        path.mkdir(parents=True, exist_ok=True)
        self.note(f"host dir {path} (short path for sockets)")
        self.short_dirs.append(path)
        return path

    # commands ------------------------------------------------------------------------------
    def _run(self, argv, *, check, input=None, timeout=1200, env=None, label=None):
        started = time.time()
        p = subprocess.run(argv, input=input, capture_output=True, text=True, timeout=timeout,
                           env=env or self.env, cwd=env and env.get("PWD") or None, check=False)
        shown = label or " ".join(shlex.quote(a) for a in argv)
        self.log(f"$ {shown}\n{p.stdout}{p.stderr}exit={p.returncode} ({time.time() - started:.1f} s)")
        if check and p.returncode != 0:
            raise AssertionError(f"{shown} -> exit {p.returncode}\n{p.stdout}\n{p.stderr}")
        return p

    def ocs(self, *args, check=True, input=None, timeout=1200, env=None):
        return self._run([*MANAGER, *args], check=check, input=input, timeout=timeout, env=env,
                         label="opencode-sandbox " + " ".join(shlex.quote(str(a)) for a in args))

    def popen(self, *args, env=None):
        self.log("$ opencode-sandbox " + " ".join(shlex.quote(str(a)) for a in args) + "   (background)")
        return subprocess.Popen([*MANAGER, *args], env=env or self.env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, start_new_session=True)

    def docker(self, *args, check=True, input=None, timeout=600):
        return self._run(["docker", "-H", SOCKET, *args], check=check, input=input, timeout=timeout)

    def sh(self, eid, script, check=True, user=None, timeout=900):
        return self.docker("exec", *(["-u", user] if user else []), f"ocs-{eid}", "sh", "-c", script,
                           check=check, timeout=timeout)

    def python(self, code, check=True):
        return self._run([sys.executable, "-c", code], check=check)

    # environments --------------------------------------------------------------------------
    def create(self, name, *args):
        assert name.startswith("ocs-test-")
        out = self.ocs("create", name, *args).stdout
        eid = re.search(rf"^{re.escape(name)} \[([0-9a-f]{{16}})\]", out, re.MULTILINE).group(1)
        self.ids[name] = eid
        self.note(f"environment {name} id={eid} container=ocs-{eid} volume=ocs-home-{eid}")
        return eid

    def adopt(self, name):
        """An environment the product created (restore, dashboard form): record it."""
        out = self.ocs("list").stdout
        eid = re.search(rf"^{re.escape(name)} \[([0-9a-f]{{16}})\]", out, re.MULTILINE).group(1)
        self.ids[name] = eid
        self.note(f"environment {name} id={eid} (created by the product)")
        return eid

    def metadata(self, name):
        return json.loads((self.data / "environments" / self.ids[name] / "metadata.json").read_text())

    def delete(self, name):
        self.ocs("stop", name, check=False)
        self.ocs("delete", name, "--yes")
        self.note(f"deleted {name}")
        self.ids.pop(name, None)

    def inspect(self, eid):
        return json.loads(self.docker("container", "inspect", f"ocs-{eid}").stdout)[0]

    def wait_for(self, predicate, timeout=120, step=0.05):
        deadline = time.time() + timeout
        while time.time() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(step)
        return None

    def kill(self, proc, sig=signal.SIGKILL):
        """Signal the manager process (not its process group: the docker client it started
        keeps running as after a real crash, unless the manager forwards the signal)."""
        os.kill(proc.pid, sig)
        out, _ = proc.communicate(timeout=120)
        self.log(f"[signal {sig.name} -> pid {proc.pid}; exit {proc.returncode}]\n{out}")
        return proc.returncode, out

    # end of session -------------------------------------------------------------------------
    def finish(self):
        self.log("== campaign cleanup")
        out = self.ocs("list", check=False).stdout
        for name in re.findall(r"^(ocs-test-[^ ]+) \[", out, re.MULTILINE):
            self.ocs("stop", name, check=False)
            if self.ocs("delete", name, "--yes", check=False).returncode == 0:
                self.note(f"deleted {name} (campaign end)")
        ours = sorted(set(self.ids.values()) | set(re.findall(r"id=([0-9a-f]{16})", self.manifest_path.read_text())))
        guard = self.python(GUARD % (str(self.data), str(self.config), ours), check=False)
        if guard.returncode == 0:
            self.note("product cleanup: " + self.ocs("disk", "cleanup", "--yes").stdout.strip().replace("\n", " | "))
        label = self.python(f"import os; os.environ['OPENCODE_SANDBOX_HOME']={str(self.data)!r}\n"
                            "from opencode_sandbox import core; print(core.data_id())").stdout.strip()
        left = {kind: self.docker(kind, "ls", "-a" if kind == "container" else "-q", "-q", "--filter",
                                  f"label=org.opencode-sandbox.data-dir={label}", check=False).stdout.split()
                for kind in ("container", "volume")}
        left["image"] = self.docker("image", "ls", "-q", "--filter", f"label=org.opencode-sandbox.data-dir={label}",
                                    check=False).stdout.split()
        self.note(f"left with this data directory's label: {left}")
        for path in self.short_dirs:
            shutil.rmtree(path, ignore_errors=True)
        outside = Path("/tmp/opencode") / f"ocs-test-{self.run}"
        if outside.is_dir() and not any(outside.iterdir()):
            outside.rmdir()  # the tests remove their own contents
        return guard.returncode, left


GUARD = """import os, sys
os.environ['OPENCODE_SANDBOX_HOME'], os.environ['OPENCODE_SANDBOX_CONFIG'] = %r, %r
from opencode_sandbox import cleanup
ours = %r
bad = [i.name for i in cleanup.inventory().eligible(False)
       if not (any(x in i.name or x == (i.owner or '') for x in ours) or i.name.startswith('.backup-')
               or i.name.startswith('ocs-qa-helper-'))]
print('guard: not ours:', bad)
sys.exit(1 if bad else 0)
"""
