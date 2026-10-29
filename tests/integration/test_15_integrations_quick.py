"""Initial integrations exactly once (campaign row G10) and quick sessions (D08), real Docker."""
import json
import re

import pytest
from campaign import MANAGER

pyte = pytest.importorskip("pyte")
from pty_term import Term

CONFIG = "/root/.config/opencode/opencode.json"


def test_context7_is_added_once_and_then_belongs_to_the_user(campaign, checks):
    camp, ck = campaign, checks
    name = "ocs-test-int"
    eid = camp.create(name)  # default integrations: Context7
    out = camp.ocs("start", name).stdout
    ck("context7" in out.lower(), f"G10 the first start sets up Context7 ({out.strip()[-120:]})")
    config = json.loads(camp.sh(eid, f"cat {CONFIG}").stdout)
    ck("context7" in json.dumps(config.get("mcp", {})), "G10 the server is in the environment's global OpenCode config")
    status = camp.ocs("status", name).stdout
    ck(re.search(r"Initial integrations \(history, not current state\): context7: ", status) is not None, "G10 status reports it as history")
    camp.sh(eid, f"python3 -c \"import json; p='{CONFIG}'; c=json.load(open(p)); c.pop('mcp', None); json.dump(c, open(p, 'w'))\"")
    edited = camp.sh(eid, f"sha256sum {CONFIG}").stdout
    camp.ocs("stop", name)
    camp.ocs("start", name)
    camp.ocs("container", "recreate", name, "--yes")
    camp.ocs("config", "apply", name, "--network", "none", "--yes")
    ck(camp.sh(eid, f"sha256sum {CONFIG}").stdout == edited, "G10 never re-applied: the user's removal survives start, recreate and settings changes")
    camp.delete(name)


def test_quick_session_promote_and_keep(campaign, checks):
    camp, ck = campaign, checks
    before = set(re.findall(r"^(quick-[0-9a-f]+) ", camp.ocs("list").stdout, re.MULTILINE))
    for choice in ("p", "k"):
        t = Term([*MANAGER, "quick", "--shell"], 100, 30, env=camp.env, log=camp.log)
        try:
            ck(t.wait_for(r"root@|# ?$", 120), f"D08 quick --shell opens a disposable session ({choice})")
            t.send("echo quick-data > /workspace/q.txt; exit\r", 3)
            ck(t.wait_for(r"Action: \[e\]xport", 30), "D08 afterwards the actions are offered")
            t.send(choice + "\r", 3)
            t.snap(f"quick after {choice}")
            t.exit_code(60)
        finally:
            t.close()
    out = camp.ocs("list").stdout
    quick = set(re.findall(r"^(quick-[0-9a-f]+) ", out, re.MULTILINE)) - before
    promoted = re.findall(r"^(scratch-[0-9a-f]{6}) \[([0-9a-f]{16})\]", out, re.MULTILINE)
    ck(len(quick) == 1 and len(promoted) == 1, f"D08 one session promoted to scratch, one kept as quick ({quick}, {promoted})")
    for name in [*quick, *(n for n, _ in promoted)]:
        eid = camp.adopt(name)
        ck((camp.data / "environments" / eid / "workspace" / "q.txt").read_text() == "quick-data\n", f"D08 {name} kept the session's files")
        camp.delete(name)
