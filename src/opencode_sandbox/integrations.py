"""Initial integrations (MCP servers), provisioned once (D-009).

At creation the environment records which integrations were requested (`provisioning` in its
metadata, with the definitions). At the first container start the manager adds them with
OpenCode's own command, `opencode mcp add --global`, which writes the user's global OpenCode
config in the /root volume and keeps everything else in it. The result is recorded as history
("configured", never "working") and nothing is ever applied again: not on later starts,
recreation, configuration changes, updates or restores, and no drift is detected. After that the
configuration belongs to the user and OpenCode.

Measured with OpenCode 2.1.4: `mcp add --global` works offline, does not start
the background service, writes `mcp.servers.<name>`, keeps comments and other keys, silently
replaces an entry with the same name, and turned an unparseable config into a broken one. So the
manager only provisions when no global OpenCode config exists yet; otherwise it leaves it alone.
"""
from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass

from . import core as c


@dataclass(frozen=True)
class Integration:
    name: str
    description: str
    definition: dict  # {"type": "remote", "url": ...} or {"type": "local", "command": [...]}


CATALOG = {
    "context7": Integration(
        "context7", "Context7 remote MCP: current library documentation (no key needed; needs network)",
        {"type": "remote", "url": "https://mcp.context7.com/mcp"}),
}
DEFAULT = ("context7",)
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_URL = re.compile(r"https?://[^\s/@]+(?:/[^\s]*)?")
PENDING, APPLYING, DONE = "pending", "applying", "done"


def _check(name: str, definition: dict) -> dict:
    if not _NAME.fullmatch(name):
        raise c.SandboxError(f"Invalid integration name {name!r}: 1-64 letters, digits, '_' or '-'")
    if definition.get("type") == "remote" and set(definition) == {"type", "url"}:
        if not isinstance(definition["url"], str) or not _URL.fullmatch(definition["url"]):
            raise c.SandboxError(f"Invalid MCP URL for {name}: http(s)://host/path without credentials or spaces")
        return definition
    if definition.get("type") == "local" and set(definition) == {"type", "command"}:
        command = definition["command"]
        if (not isinstance(command, list) or not 1 <= len(command) <= 32
                or not all(isinstance(a, str) and a and "\0" not in a and len(a) <= 1024 for a in command)):
            raise c.SandboxError(f"Invalid MCP command for {name}")
        return definition
    raise c.SandboxError(f"Invalid MCP definition for {name}")


def parse_custom(remote=(), local=()) -> dict:
    """CLI `--mcp-remote NAME=URL` and `--mcp-local "NAME=COMMAND ARGS"` to definitions."""
    out = {}
    for spec, kind in [*((s, "remote") for s in remote), *((s, "local") for s in local)]:
        name, sep, value = spec.partition("=")
        if not sep or not value:
            raise c.SandboxError(f"Expected NAME=VALUE, got {spec!r}")
        if kind == "remote":
            out[name] = {"type": "remote", "url": value}
        else:
            try:
                out[name] = {"type": "local", "command": shlex.split(value)}
            except ValueError as exc:
                raise c.SandboxError(f"Invalid command for {name}: {exc}") from None
    return out


def request(names=None, custom=None) -> dict:
    """The `provisioning` record of a new environment. `names=None` means the defaults; an empty
    list means none (opt-out). `custom` maps names to definitions."""
    names = list(DEFAULT if names is None else names)
    definitions = {}
    for name in names:
        if name not in CATALOG:
            raise c.SandboxError(f"Unknown integration {name!r}; known: {', '.join(sorted(CATALOG))}")
        definitions[name] = dict(CATALOG[name].definition)
    for name, definition in (custom or {}).items():
        if name in definitions:
            raise c.SandboxError(f"Integration {name!r} is defined twice")
        definitions[name] = _check(name, dict(definition))
    return {"requested": list(definitions), "definitions": definitions, "state": PENDING if definitions else DONE,
            "result": None if definitions else "none requested", "at": None}


def as_history(record) -> dict:
    """For a restored environment: what the original requested; never applied again."""
    if not isinstance(record, dict) or not isinstance(record.get("requested"), list):
        return {"requested": [], "definitions": {}, "state": DONE, "result": "none recorded", "at": None}
    definitions = {}
    for name, definition in (record.get("definitions") or {}).items() if isinstance(record.get("definitions"), dict) else ():
        try:
            definitions[name] = _check(name, dict(definition))
        except (c.SandboxError, TypeError, ValueError):
            continue
    out = {"requested": [str(n) for n in record["requested"]], "definitions": definitions, "state": DONE,
           "result": record.get("result") if isinstance(record.get("result"), str) else None,
           "at": record.get("at") if isinstance(record.get("at"), str) else None}
    if record.get("state") != DONE:
        out["result"] = "not provisioned: the backup was made before the first start; add them yourself if wanted"
    return out


# Runs in the container as `python3 -c SCRIPT DEFINITIONS`; prints one JSON object
# {"status": "configured"|"skipped"|"failed", "detail": ..., "servers": {name: "configured"|error}}.
SCRIPT = r"""import json,os,subprocess,sys
os.umask(0o022)  # docker exec inherits rootless dockerd's umask (0000)
defs=json.loads(sys.argv[1])
home=os.path.expanduser('~')
conf=os.path.join(home,'.config','opencode')
existing=[n for n in ('opencode.json','opencode.jsonc','config.json') if os.path.lexists(os.path.join(conf,n))]
if existing:
    print(json.dumps({'status':'skipped','detail':'an OpenCode global configuration already existed ('+', '.join(existing)+'); not changed','servers':{}})); sys.exit(0)
servers={}
for name,d in defs.items():
    argv=['opencode','mcp','add','--global',name]
    argv+=['--url',d['url']] if d['type']=='remote' else ['--',*d['command']]
    try:
        p=subprocess.run(argv,cwd=home,capture_output=True,text=True,timeout=120)
        servers[name]='configured' if p.returncode==0 else ('exit %d: %s'%(p.returncode,(p.stderr or p.stdout).strip()[:200]))
    except (OSError,subprocess.TimeoutExpired) as e:
        servers[name]=str(e)[:200]
ok=all(v=='configured' for v in servers.values())
print(json.dumps({'status':'configured' if ok else 'failed','detail':'','servers':servers}))"""


def _summary(outcome: dict, network: str, definitions: dict) -> str:
    servers = outcome.get("servers") or {}
    if outcome.get("status") == "skipped":
        return "skipped: " + str(outcome.get("detail"))
    done = [n for n, v in servers.items() if v == "configured"]
    failed = [f"{n} ({v})" for n, v in servers.items() if v != "configured"]
    parts = []
    if done:
        parts.append("configured in the global OpenCode config: " + ", ".join(done))
        remote = [n for n in done if definitions.get(n, {}).get("type") == "remote"]
        if remote and network == "none":
            parts.append("cannot work offline (network none): " + ", ".join(remote))
    if failed:
        parts.append("failed, not retried: " + "; ".join(failed))
    return "; ".join(parts) or "nothing configured"


def provision(m: dict) -> str | None:
    """Run the pending provisioning of a started container once. Caller holds the environment
    lock and the container runs. Returns the recorded result, or None when nothing was pending.
    A crash while applying is recorded at the next start as interrupted, never retried."""
    record = m.get("provisioning")
    if not isinstance(record, dict) or record.get("state") not in (PENDING, APPLYING):
        return None
    if record["state"] == APPLYING:
        record.update(state=DONE, at=c.now(),
                      result="interrupted during the first start; unknown whether written; not retried")
        c.save(m)
        return record["result"]
    definitions = {n: _check(n, d) for n, d in (record.get("definitions") or {}).items()}
    record["state"] = APPLYING
    c.save(m)  # journal before touching the container
    try:
        p = c.docker("exec", "--workdir", "/root", c.cname(m), "python3", "-c", SCRIPT, json.dumps(definitions),
                     capture=True, check=False)
        try:
            outcome = json.loads((p.stdout or "").strip().splitlines()[-1]) if p.returncode == 0 else None
        except (ValueError, IndexError):
            outcome = None
        if not isinstance(outcome, dict):
            result = f"failed, not retried: provisioning in the container exited {p.returncode}: " \
                     + ((p.stderr or p.stdout or "").strip()[:200] or "no output")
        else:
            result = _summary(outcome, c.runtime_settings(m)["network"], definitions)
    except c.SandboxError as exc:
        result = f"failed, not retried: {exc}"[:400]
    record.update(state=DONE, at=c.now(), result=result)
    c.save(m)
    return result


def hint(m: dict) -> list[str]:
    """Commands that add the requested integrations by hand (for failed or skipped provisioning)."""
    record = m.get("provisioning") if isinstance(m.get("provisioning"), dict) else {}
    out = []
    for name, d in (record.get("definitions") or {}).items():
        args = ["opencode", "mcp", "add", "--global", name]
        args += ["--url", d["url"]] if d.get("type") == "remote" else ["--", *d.get("command", [])]
        out.append(shlex.join(args))
    return out
