"""Real Docker + keyboard-only Updates at 80x24/larger; actual loopback HTTP, no public npm.

Source-dashboard harness substitutes the registry URL and manifests/names/labels transient
helpers, following test_43. No model call, update or base build.
"""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from campaign import DISTROS

pytest.importorskip("pyte")
from pty_term import ENTER, ESC, TAB, Term

pytestmark = [pytest.mark.real_session, pytest.mark.real_identity]


@pytest.mark.parametrize("distro", DISTROS)
@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
def test_manual_updates_terminal(campaign, checks, distro, size):
    camp, ck = campaign, checks
    name = f"ocs-test-updates-{distro}-{size[0]}"
    eid = camp.create(name, "--distro", distro, "--no-integrations")
    camp.ocs("start", name)
    camp.ocs("opencode", "versions")
    camp.ocs("stop", name)
    before = camp.inspect(eid)
    metadata_path = camp.data / "environments" / eid / "metadata.json"
    metadata = metadata_path.read_bytes()
    state = {"requests": 0, "fail": False, "delay": 0}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["requests"] += 1
            time.sleep(state["delay"])
            self.send_response(503 if state["fail"] else 200)
            self.end_headers()
            try: self.wfile.write(json.dumps({"versions": {"2.2.1": {"version": "2.2.1"}}}).encode())
            except BrokenPipeError: pass  # deliberately canceled parent-owned HTTP child
        def log_message(self, *args): pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    camp.note(f"loopback HTTP fixture 127.0.0.1:{server.server_port}; no inbound LAN listener")
    script = camp.tmp("updates-terminal") / "dashboard.py"
    script.write_text("from opencode_sandbox import core as c, probes, opencode_versions as v\n"
                      "from opencode_sandbox.tui import Dashboard\n"
                      f"v.REGISTRY='http://127.0.0.1:{server.server_port}/metadata'\n"
                      f"probes.PREFIX={'ocs-test-' + camp.run + '-' + distro + '-probe-'!r}\n"
                      "real_docker=c.docker\n"
                      "def docker(*args, **kwargs):\n"
                      " if args[0]=='run' and '--name' in args:\n"
                      "  name=args[args.index('--name')+1]\n"
                      f"  with open({str(camp.manifest_path)!r}, 'a') as stream: stream.write('container '+name+' test='+{camp.run!r}+'\\n')\n"
                      f"  args=(args[0], '--label', {'org.opencode-sandbox.test=' + camp.run!r}, *args[1:])\n"
                      " return real_docker(*args, **kwargs)\n"
                      "c.docker=docker\nDashboard().run()\n")
    camp.note(f"host file {script} (source dashboard, loopback registry and manifested/named/labeled helpers)")
    t = Term([sys.executable, str(script)], *size, env=camp.env, log=camp.log)
    try:
        ck(t.wait_for(name, 30), "Updates terminal: dashboard metadata visible")
        t.send("v", .5)
        ck(t.wait_for("Installation classification: not assessed", 15), "Updates terminal: immediate Manager view, eligibility not invented")
        t.send("3", .5)
        ck(t.wait_for("last verified", 20) and "stopped" in t.text(), "Updates terminal: dated stopped version, actual state")
        ck(state["requests"] == 0, "Updates terminal: opening/views made zero HTTP requests")
        ck("Close" in t.text() and "Details" in t.text() and "Check" in t.text(), "Updates terminal: primary controls visible")
        t.snap("Updates local/cached view")
        t.send("c", .5)
        ck(t.wait_for("npm: 2.2.1", 20) and state["requests"] == 1, "Updates terminal: explicit bounded real HTTP lookup")
        ck(t.wait_for("update available", 10), "Updates terminal: selected stopped evidence compared with exact supported target")
        t.send("d", .5)
        ck(t.wait_for("Environment OpenCode — Details", 10), "Updates terminal: progressive read-only Details")
        t.send(ESC, .3)
        t.send("2", .5)
        ck(t.wait_for("Upstream OS/package freshness not assessed", 20), "Updates terminal: base freshness is not inferred from labels")
        t.send("c", .5)
        ck(t.wait_for("OpenCode: 2.2.0; last verified", 30), "Updates terminal: explicit immutable base probe verified")
        t.snap("Updates explicit base check")
        state["fail"] = True
        t.send("3c", .5)
        ck(t.wait_for("Check failed:", 20) and "HTTP 503" in t.text() and "cached" in t.text(), "Updates terminal: HTTP failure retains dated cached discovery")
        state.update(fail=False, delay=3)
        t.send("c", .2)
        ck(t.wait_for("Checking npm", 5), "Updates terminal: truthful independent progress")
        t.send(TAB * 3 + ENTER, .5)
        ck(t.wait_for("npm check canceled", 5), "Updates terminal: keyboard Cancel remains responsive")
        t.send(ESC, .3)
        t.send("q", .5)
        code = t.exit_code(15)
        ck(code == 0 and t.restored(), "Updates terminal: Close/Q restores terminal, no automatic restart")
        after = camp.inspect(eid)
        ck(not after["State"]["Running"] and after["State"]["StartedAt"] == before["State"]["StartedAt"]
           and metadata_path.read_bytes() == metadata, "Updates terminal: stopped Check never starts or mutates metadata")
        containers = camp.docker("ps", "-a", "--format", "{{.Names}}").stdout.splitlines()
        ck(containers == [f"ocs-{eid}"], "Updates terminal: explicit image helper left no extra container")
    finally:
        t.close()
        server.shutdown(); thread.join(); server.server_close()
    camp.delete(name)
