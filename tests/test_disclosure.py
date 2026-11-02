"""Runtime consent exposes host-tool risks and remains usable; guidance qualifies network access."""
import asyncio

from opencode_sandbox import agent_context as a
from opencode_sandbox import tui, workspaces
from opencode_sandbox.cli import DIRECT_CONSENT

M = {"id": "0123456789abcdef", "name": "demo", "kind": "scratch", "source": None, "distro": "debian"}
R = {"network": "bridge", "cpus": "2.0", "memory": "4g", "pids": 100, "ports": []}


def test_direct_consent_names_files_that_host_tools_act_on():
    text = DIRECT_CONSENT.format(path="/home/someone/project")
    assert "Git hooks" in text and "Git configuration" in text and "editor" in text and "build" in text
    assert "before you run" in text


def test_direct_consent_fits_an_80x24_terminal():
    """The dashboard shows the same text; its buttons must stay reachable at 80x24."""
    async def main():
        app = tui.Dashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.push_screen(tui.ConfirmScreen(f"{workspaces.LABEL}.\n\n" + DIRECT_CONSENT.format(
                path="/home/someone/projects/a-fairly-long-project-directory-name")))
            await pilot.pause()
            for selector in ("#confirm", "#cancel"):
                r = app.screen.query_one(selector).region
                assert r.width > 0 and r.height > 0 and r.bottom <= 24, selector
    asyncio.run(main())


def test_agent_context_bridge_wording_matches_the_measured_reachability():
    text = a.render(M, image="opencode-sandbox:debian", runtime=R)
    assert "no access to host services" not in text
    assert "services on the host's network addresses" in text and "not network isolation" in text
    offline = a.render(M, image="opencode-sandbox:debian", runtime={**R, "network": "none"})
    assert "no access to host services" not in offline and "loopback only" in offline
