"""Render the dashboard screenshot of the user documentation from fake data.

    python tests/dashboard_screenshot.py [docs/images/dashboard.svg]

No Docker daemon, no real data: the manager's directories are a temporary directory, Docker is
replaced by stubs, and the environments, their sources and states are invented.
`tests/test_dashboard_screenshot.py` keeps this script working."""
import asyncio
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from opencode_sandbox import core as c
from opencode_sandbox import readiness, tui
from opencode_sandbox import runtime_identity as rid

SIZE = (100, 30)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "images" / "dashboard.svg"
# (name, kind, distribution, recorded state, profile, shown source, settings)
ENVIRONMENTS = [
    ("webapp", "project", "debian", "running", "work", "~/code/webapp", {"cpus": "4.0", "memory": "8g"}),
    ("api-refactor", "project", "debian", "stopped", "work", "~/code/api", {}),
    ("aur-tools", "scratch", "arch", "stopped", "default", None, {"network": "none"}),
    ("notes", "scratch", "debian", "created", "default", None, {}),
]


def render(size=SIZE) -> str:
    with tempfile.TemporaryDirectory(prefix="ocs-screenshot-") as tmp:
        identity = rid.Identity(rid.VERIFIED, "rootless", "unix:///run/user/1000/docker.sock", "/run/user/1000/docker.sock")
        done = SimpleNamespace(returncode=0, stdout="", stderr="")
        with mock.patch.object(c, "BASE", Path(tmp) / "data"), mock.patch.object(c, "CONFIG", Path(tmp) / "config"), \
                mock.patch.object(c, "_ENDPOINT", None), mock.patch.object(c, "docker", lambda *a, **k: done), \
                mock.patch.object(c, "ensure_runtime", lambda *a, **k: None), \
                mock.patch.object(c, "inspect_container", lambda m: None), \
                mock.patch.object(rid, "verify", lambda *a, **k: identity), \
                mock.patch.object(readiness, "image_checks", list):  # the illustration assumes current base images
            for name, kind, distro, state, profile, source, settings in reversed(ENVIRONMENTS):  # newest first
                m = c.create(name, "scratch", profile=profile, distro=distro)
                m.update(kind=kind, status=state, source=source)
                m.setdefault("runtime", {}).update(settings)
                c.save(m)

            async def main():
                app = tui.Dashboard()
                async with app.run_test(size=size) as pilot:
                    await pilot.pause()
                    await asyncio.sleep(0.3)
                    await pilot.pause()
                    return app.export_screenshot(title="OpenCode Sandbox")
            return asyncio.run(main())


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(), encoding="utf-8")
    print(output)
