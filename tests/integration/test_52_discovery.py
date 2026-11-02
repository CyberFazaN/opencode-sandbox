"""Opt-in daily metadata discovery in a real terminal: loopback HTTP, retained real runtimes.

Only the registry URL and read-only Docker argv recording are substituted. No paid/public API,
mutation mock, helper, base build, host preference or service. Product cleanup owns all resources.
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from campaign import DISTROS

pytest.importorskip("pyte")
from pty_term import ENTER, ESC, TAB, Term

pytestmark = [pytest.mark.real_session, pytest.mark.real_identity]


@pytest.mark.parametrize("distro", DISTROS)
@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
def test_daily_discovery_terminal(campaign, checks, distro, size):
    camp, ck = campaign, checks
    name = f"ocs-test-discovery-{distro}-{size[0]}"
    eid = camp.create(name, "--distro", distro, "--no-integrations")
    camp.ocs("start", name)
    camp.ocs("opencode", "versions")
    camp.ocs("stop", name)
    before = camp.inspect(eid)
    metadata_path = camp.data / "environments" / eid / "metadata.json"
    metadata = metadata_path.read_bytes()
    state = {"requests": 0, "fail": False}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/manager':
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps([{'tag_name': 'v6.1.0', 'draft': False, 'prerelease': False,
                    'published_at': '2026-10-30T12:00:00Z', 'body': 'test manager release',
                    'html_url': 'https://github.com/CyberFazaN/opencode-sandbox/releases/tag/v6.1.0'}]).encode())
                return
            state["requests"] += 1
            self.send_response(503 if state["fail"] else 200)
            self.end_headers()
            self.wfile.write(b'{"versions":{"2.2.1":{"version":"2.2.1"}}}')
        def log_message(self, *args): pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    directory = camp.tmp("discovery-terminal")
    script, calls_path = directory / "dashboard.py", directory / "docker.jsonl"
    script.write_text("import json\nfrom opencode_sandbox import core as c, opencode_versions as v, manager_releases as mr\n"
                      "from opencode_sandbox.tui import Dashboard\n"
                      f"v.REGISTRY='http://127.0.0.1:{server.server_port}/metadata'\n"
                      f"mr.API='http://127.0.0.1:{server.server_port}/manager'\n"
                      "real_docker=c.docker\n"
                      "def docker(*args, **kwargs):\n"
                      f" with open({str(calls_path)!r},'a') as stream: stream.write(json.dumps(args)+'\\n')\n"
                      " return real_docker(*args, **kwargs)\n"
                      "c.docker=docker\nDashboard().run()\n")
    camp.note(f"loopback HTTP fixture 127.0.0.1:{server.server_port}; no inbound LAN listener")
    camp.note(f"host files {script}, {calls_path}; source harness only registry URL and Docker argv recording")
    terminal = None
    try:
        terminal = Term([sys.executable, str(script)], *size, env=camp.env, log=camp.log)
        ck(terminal.wait_for(name, 30), "Daily terminal: default-off dashboard ready")
        ck(state["requests"] == 0, "Daily terminal: no unsolicited default network request")
        terminal.send("g", .5)
        ck(terminal.wait_for("Daily metadata discovery", 10) and "Save" in terminal.text(), "Daily terminal: opt-in and Save visible")
        terminal.snap("Daily discovery preference before opt-in")
        terminal.send(TAB * 3 + " " + TAB + ENTER, 1)
        ck(terminal.wait_for(r"Updates \(1\)", 20), "Daily terminal: keyboard opt-in yields one quiet dated-history indicator")
        preferences_path = camp.config / "ui.json"
        ck(preferences_path.exists() and json.loads(preferences_path.read_text())["daily_discovery"], "Daily terminal: preference persisted")
        ck(state["requests"] == 1, "Daily terminal: opt-in attempted npm once, not per environment")
        terminal.send("q", .5)
        ck(terminal.exit_code(15) == 0 and terminal.restored(), "Daily terminal: quit restores terminal")
        terminal.close()

        # Same source/data root and a new process must reuse the successful attempt.
        terminal = Term([sys.executable, str(script)], *size, env=camp.env, log=camp.log)
        ck(terminal.wait_for(r"Updates \(1\)", 20) and state["requests"] == 1, "Daily terminal: restart reuses daily successful attempt")
        terminal.send("v", .3)
        terminal.send("3", .5)
        ck(terminal.wait_for("npm: 2.2.1", 15), "Daily terminal: cached discovery visible without implicit Check")
        state["fail"] = True
        terminal.send("c", .5)
        ck(terminal.wait_for("HTTP 503", 15) and state["requests"] == 2, "Daily terminal: explicit early refresh keeps failure visible")
        terminal.send(ESC, .3)
        terminal.send("q", .5)
        ck(terminal.exit_code(15) == 0 and terminal.restored(), "Daily terminal: failed-discovery quit restores terminal")
        terminal.close()

        terminal = Term([sys.executable, str(script)], *size, env=camp.env, log=camp.log)
        ck(terminal.wait_for(r"Updates \(1\)", 20) and state["requests"] == 2, "Daily terminal: failure/restart cannot trigger another automatic request")
        terminal.send("g", .3)
        terminal.send(TAB * 3 + " " + TAB + ENTER, .5)
        ck(terminal.wait_for(name, 10) and "Updates (1)" not in terminal.text(), "Daily terminal: disabling hides unsolicited indicator")
        terminal.send("q", .5)
        ck(terminal.exit_code(15) == 0 and terminal.restored(), "Daily terminal: disabled quit restores terminal")
        after = camp.inspect(eid)
        calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
        ck(not any(call[0] in ("run", "start", "exec", "build", "commit", "stop", "rm") for call in calls),
           "Daily terminal: scheduling/manual stopped Check never invokes runtime/image probes or mutation")
        ck(not after["State"]["Running"] and after["State"]["StartedAt"] == before["State"]["StartedAt"]
           and metadata_path.read_bytes() == metadata, "Daily terminal: actual stopped state/startup time/metadata unchanged")
    finally:
        if terminal: terminal.close()
        server.shutdown(); thread.join(); server.server_close()
    camp.delete(name)
