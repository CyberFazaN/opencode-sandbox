"""Quick sessions (D08), real Docker."""
import re

import pytest
from campaign import MANAGER

pyte = pytest.importorskip("pyte")
from pty_term import Term


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
