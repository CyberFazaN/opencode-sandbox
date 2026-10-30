"""Real OpenCode in the managed `run` on each distribution: first prompt with a fake
OpenAI-compatible provider inside the container (network none, dummy key), Agent Context delivery,
user configuration untouched, sessions ended; version reporting and the pinned policy
(campaign rows G01, G02, G04–G06, G08, H05)."""
import json
import re
import sys
from pathlib import Path

import pytest
from campaign import DISTROS, MANAGER

from opencode_sandbox import distros

pyte = pytest.importorskip("pyte")
from pty_term import Term

FAKE = Path(__file__).with_name("fake_llm.py")
def user_config(camp):
    """A user configuration for the fake OpenAI-compatible provider (`fake_llm.py`)."""
    return ('{"providers":{"qa":{"name":"QA","env":["QA_API_KEY"],"package":"@opencode/ai/providers/openai-compatible",'
            '"settings":{"baseURL":"http://127.0.0.1:8765/v1"},"models":{"qa-model":{"name":"QA model"}}}},\n "model":"qa/qa-model"}\n')


@pytest.mark.parametrize("distro", DISTROS)
def test_first_prompt_delivers_the_agent_context(campaign, checks, distro):
    camp, ck = campaign, checks
    camp._run([sys.executable, "-c", ("import json,sys\nfrom opencode_sandbox import core as c\nc.init_dirs(); "
               "c.profile_set('ocs-test-oc', json.load(sys.stdin))")], check=True,
              input=json.dumps({"QA_API_KEY": "not-a-real-keyoc"}))
    src = camp.tmp(f"oc-src-{distro}-QA-HOST-PATH-MARKER")
    for args in (["init", "-q", "-b", "main"], ["commit", "-q", "--allow-empty", "-m", "init"]):
        camp._run(["git", "-C", str(src), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], check=True)
    name = f"ocs-test-oc-{distro}"
    eid = camp.create(name, "--source", str(src), "--distro", distro, "--profile", "ocs-test-oc", "--no-integrations")
    camp.ocs("config", "apply", name, "--network", "none", "--cpus", "1.5", "--memory", "3g", "--pids", "600", "--yes")
    camp.ocs("start", name)
    camp.docker("exec", "-i", f"ocs-{eid}", "sh", "-c", "umask 022; mkdir -p /root/.config/opencode; cat > /root/.config/opencode/opencode.json",
                input=user_config(camp))
    camp.sh(eid, "umask 022; echo QA-MARKER-AGENTS-MD > /workspace/AGENTS.md")
    before = camp.sh(eid, "sha256sum /root/.config/opencode/opencode.json").stdout
    camp.docker("exec", "-i", f"ocs-{eid}", "sh", "-c", "cat > /tmp/fake_llm.py", input=FAKE.read_text())
    camp.docker("exec", "-d", f"ocs-{eid}", "python3", "/tmp/fake_llm.py", "/tmp/qa-capture.jsonl")

    version = re.search(r"\d+\.\d+\.\d+", camp.sh(eid, "opencode --version").stdout).group(0)
    versions = camp.ocs("opencode", "versions").stdout
    ck(version in versions and name in versions, f"G01 `opencode versions` reports the binary's version {version}")

    t = Term([*MANAGER, "run", name], 100, 30, env=camp.env, log=camp.log)
    try:
        opened = t.wait_for(r"(?i)ask anything|ctrl\+p|build|qa model", 60)
        t.pump(5)
        t.snap(f"OpenCode {distro} before the prompt")
        ck(opened, "G04 OpenCode TUI opened by `run`")
        t.send("Reply with the single word OK. QA-FIRST-PROMPT", 1)
        t.send("\r", 1)
        replied = t.wait_for("QA-FAKE-REPLY", 60)
        t.snap(f"OpenCode {distro} after the reply")
        ck(replied, "G04 the fake provider's reply is shown")
        for keys in ("\x03", "\x03", "\x04"):
            t.send(keys, 2)
        code = t.exit_code(30)
        ck(code in (0, 1, 130) and t.restored(), f"H05 OpenCode exited ({code}) and the terminal was restored")
    finally:
        t.close()

    capture = camp.sh(eid, "cat /tmp/qa-capture.jsonl").stdout
    camp.logs.joinpath(f"{camp.run}-{distro}-capture.jsonl").write_text(capture)
    guidance = camp.ocs("agent-context", "show", name).stdout.strip()
    bodies = [json.dumps(json.loads(line)["body"], ensure_ascii=False) for line in capture.splitlines() if line.strip()]
    agent = [b for b in bodies if "environment guidance (managed)" in b]
    ck(bool(agent), f"G04 the guidance reached the model ({len(agent)} of {len(bodies)} requests)")
    text = agent[0] if agent else ""
    ck(json.dumps(guidance, ensure_ascii=False)[1:-1] in text, "G04 the complete current guidance, verbatim")
    definition = distros.get(distro)
    ck(f"Base OS: {definition.name} {definition.version}." in text,
       f"G04 first request identifies the built {definition.name} {definition.version} base")
    for marker in ("Networking mode: none", "CPU limit: 1.5", "Memory limit: 3g", "Process limit: 600",
                   "QA-MARKER-AGENTS-MD", "QA-FIRST-PROMPT", "## Operating system ("):
        ck(marker in text, f"G04 first request contains {marker!r}")
    ck("QA-HOST-PATH-MARKER" not in text and "not-a-real-keyoc" not in text, "G08 no host path and no key in the request body")
    ck(camp.sh(eid, "sha256sum /root/.config/opencode/opencode.json").stdout == before, "G06 the user's OpenCode configuration is unchanged")
    left = camp.sh(eid, "ps -eo args | grep -v grep | grep -c 'opencode' || true").stdout.strip()
    ck(left == "0", f"H05 no OpenCode process left in the container ({left})")
    ck(camp.ocs("agent-context", "verify", name, check=False).returncode == 0, "G08 agent-context verify")

    # G02/G03: pinned policy refuses other versions without downloading anything
    current = version
    camp.ocs("opencode", "policy-set", name, "pinned", "--version", current)
    camp.ocs("stop", name)
    p = camp.ocs("opencode", "update", name, "--version", "2.1.4" if current != "2.1.4" else "2.2.0", "--yes", check=False)
    ck(p.returncode != 0 and "pinned" in (p.stdout + p.stderr).lower(), "G02 pinned policy refuses an update to another version")
    camp.delete(name)
