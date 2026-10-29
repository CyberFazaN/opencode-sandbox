"""One plan and one executor for changes of manager-owned environment settings (D-010).

Every caller (CLI `config plan|apply`, the TUI container settings) computes a `Plan` with
`plan()`, shows `describe()` and applies it with `apply()`. Categories, from least to most
disruptive, follow measured rootless Docker behaviour:

- saved: no container exists yet; the settings apply when it is created.
- dynamic: `docker update` changes CPU, memory and PID limits of a running or stopped container
  in place (cgroup v2 delegation), and they persist across restarts.
- restart: lowering the memory limit of a running container below its usage makes the kernel
  kill the whole container (measured: exit 137, OOMKilled), so the container is stopped,
  updated and started again.
- recreate: network mode, published ports and the provider profile mount are fixed at
  container creation; the container is stopped, its system layer committed, and a new one
  created (`core.reconfigure_runtime` journal).
The Agent Context is regenerated after every applied change.

The workspace mode (managed or direct, D-012) is fixed at creation and not a setting here; a
recreation of an environment with a direct workspace re-checks that directory first and mounts it
again unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import agent_context as ac
from . import core as c
from . import workspaces

CATEGORIES = ("none", "saved", "dynamic", "restart", "recreate")
LIMITS = ("cpus", "memory", "pids")
FIELDS = (*LIMITS, "network", "ports", "profile")
LABELS = {"cpus": "CPU limit", "memory": "memory limit", "pids": "process limit", "network": "network",
          "ports": "published ports", "profile": "provider profile"}


@dataclass(frozen=True)
class Change:
    field: str
    old: object
    new: object
    category: str
    reason: str


@dataclass(frozen=True)
class Plan:
    env_id: str
    name: str
    container: str  # missing | stopped | running
    current: dict
    target: dict
    changes: tuple[Change, ...]
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    steps: tuple[str, ...] = field(default=())

    @property
    def category(self) -> str:
        return max((ch.category for ch in self.changes), key=CATEGORIES.index, default="none")

    def as_dict(self) -> dict:
        return {"environment": self.name, "container": self.container, "category": self.category,
                "changes": [{"field": ch.field, "old": ch.old, "new": ch.new, "category": ch.category,
                             "reason": ch.reason} for ch in self.changes],
                "steps": list(self.steps), "warnings": list(self.warnings), "blockers": list(self.blockers),
                "target": self.target}


def parse_ports(specs) -> list[dict]:
    """HOST:CONTAINER[/tcp|udp] specifications (CLI options, TUI field) to port mappings."""
    ports = []
    for spec in specs:
        pair, _, protocol = spec.strip().partition("/")
        try:
            host, container = pair.split(":")
            ports.append({"host": int(host), "container": int(container), "protocol": protocol or "tcp"})
        except ValueError:
            raise c.SandboxError(f"Invalid port mapping {spec!r}: expected HOST:CONTAINER[/tcp|udp]") from None
    return ports


def current(m: dict) -> dict:
    return {**c.runtime_settings(m), "profile": m.get("profile", "default")}


def check_profile(name: str) -> str:
    c.safe_name(name)
    c.profile_read(name)  # refuses legacy .env, symlinks, wrong permissions, bad JSON
    if name != "default" and not c.profile_path(name).is_file():
        raise c.SandboxError(f"Provider profile '{name}' not found; create it with: opencode-sandbox providers set {name}")
    return name


def blocking_operation(m, container):
    """A failed first start (no container) is not a journal: fixing its settings is the normal way out."""
    failed_start = m.get("operation") == "start" and m.get("status") == "error" and container == "missing"
    return bool(m.get("operation")) and not failed_start


def _memory_category(old, new, running):
    if running and c.memory_bytes(new) < c.memory_bytes(old):
        return "restart", "a lower memory limit can make the kernel kill a running container, so it is stopped first"
    return "dynamic", "docker update"


def plan(m: dict, changes: dict) -> Plan:
    """Read-only: what applying `changes` (a subset of FIELDS) would do now."""
    unknown = set(changes) - set(FIELDS)
    if unknown:
        raise c.SandboxError("Unknown setting: " + ", ".join(sorted(unknown)))
    m = c.resolve(m["id"])
    now = current(m)
    runtime = c.validate_runtime_settings({**c.runtime_settings(m), **{k: v for k, v in changes.items() if k != "profile"}})
    target = {**runtime, "profile": check_profile(changes["profile"]) if "profile" in changes else now["profile"]}
    state = c.inspect_container(m)
    container = "missing" if state is None else ("running" if state.get("Running") else "stopped")
    running = container == "running"
    out = []
    for key in FIELDS:
        if target[key] == now[key]:
            continue
        if container == "missing":
            category, reason = "saved", "applies when the container is created"
        elif key == "memory":
            category, reason = _memory_category(now[key], target[key], running)
        elif key in LIMITS:
            category, reason = "dynamic", "docker update"
        else:
            category, reason = "recreate", "fixed when Docker creates the container"
        out.append(Change(key, now[key], target[key], category, reason))
    result = Plan(m["id"], m["name"], container, now, target, tuple(out))
    warnings, blockers = [], []
    if blocking_operation(m, container):
        blockers.append(str(c.pending_operation(m)))
    if float(target["cpus"]) > c.host_cpus():
        blockers.append(f"CPU limit {float(target['cpus']):g} exceeds the {c.host_cpus()} CPUs on this host")
    blockers += ["Port conflict: " + conflict for conflict in c.port_conflicts(m, runtime)]
    changed = {ch.field for ch in out}
    if "network" in changed or "ports" in changed:
        warnings.append("Network none: no internet or LAN, so model provider APIs and OpenCode updates in the container "
                        "are unavailable." if target["network"] == "none" else
                        "Bridge permits LAN and internet; no LAN firewall is enforced.")
        if target["ports"]:
            warnings.append("Port checks cannot detect other host processes.")
    if running and "pids" in changed and target["pids"] < now["pids"]:
        warnings.append("A running container keeps its processes; new ones fail while more than the limit exist.")
    category = result.category
    direct = workspaces.is_direct(m)
    if direct and (category == "recreate" or (category == "restart" and running)):
        try:
            workspaces.recheck(m)
        except c.SandboxError as exc:
            blockers.append(f"The container could not mount the direct workspace again: {exc}")
    if running and category in ("restart", "recreate"):
        warnings.append("The container is stopped first: running OpenCode sessions and shells in it end.")
    steps = {
        "none": [],
        "saved": ["Save the settings; they apply when the container is created."],
        "dynamic": ["Apply the limits to the existing container with docker update (no restart)."],
        "restart": ["Stop the container.", "Apply the limits with docker update.", "Start the container again."],
        "recreate": [*(["Stop the container."] if running else []),
                     "Commit its system layer (packages, files outside /workspace and /root) to an ocs-runtime image.",
                     "Remove the container; a new one is created from that image with the new settings "
                     + ("now." if running else "at the next start.")
                     + (" The direct host directory is mounted again, unchanged; the /root volume is kept." if direct
                        else " /workspace and the /root volume are kept."),
                     *(["Start the new container."] if running else [])],
    }[category]
    if category != "none":
        steps.append("Regenerate the Agent Context.")
    return Plan(m["id"], m["name"], container, now, target, tuple(out), tuple(warnings), tuple(blockers), tuple(steps))


def describe(p: Plan) -> str:
    lines = [f"Environment: {p.name} (container {p.container})"]
    if not p.changes:
        return "\n".join([*lines, "No changes."])
    lines.append("Changes:")
    lines += [f"  {LABELS[ch.field]}: {_show(ch.old)} -> {_show(ch.new)}  [{ch.category}: {ch.reason}]" for ch in p.changes]
    lines.append(f"Impact: {p.category}")
    lines += ["Steps:", *(f"  {n}. {step}" for n, step in enumerate(p.steps, 1))]
    lines += [f"Warning: {w}" for w in p.warnings]
    lines += [f"Blocked: {b}" for b in p.blockers]
    return "\n".join(lines)


def _show(value):
    if isinstance(value, list):
        return ", ".join(f"{p['host']}:{p['container']}/{p['protocol']}" for p in value) or "none"
    return str(value)


def apply(m: dict, changes: dict, *, confirmed: Plan | None = None) -> dict:
    """Apply `changes`; with `confirmed`, refuse if the plan changed since it was shown."""
    p = plan(m, changes)
    if confirmed is not None and (p.changes, p.container, p.target) != (confirmed.changes, confirmed.container, confirmed.target):
        raise c.SandboxError("The environment changed since the plan was shown; review the new plan")
    if p.blockers:
        raise c.SandboxError("; ".join(p.blockers))
    category = p.category
    # Only the planned changes, merged under the lock into the settings as they are then: a
    # change another process made after the plan is kept.
    changed = {ch.field: ch.new for ch in p.changes if ch.field != "profile"}
    profile = p.target["profile"] if any(ch.field == "profile" for ch in p.changes) else None
    if category == "none":
        return {"category": "none", "applied": False}
    if category == "saved":
        with c.lock(p.env_id):
            m = c.resolve(p.env_id)
            if c.inspect_container(m) is not None or blocking_operation(m, "missing"):
                raise c.SandboxError("The environment changed since the plan was made; review the new plan")
            m["runtime"] = c.validate_runtime_settings({**c.runtime_settings(m), **changed})
            if profile is not None:
                m["profile"] = profile
            c.save(m)
    elif category in ("dynamic", "restart"):
        c.ensure_runtime(False)
        with c.lock(p.env_id):
            m = c.resolve(p.env_id)
            if m.get("operation"):
                raise c.pending_operation(m)
            state = c.inspect_container(m)
            # Journal first: a crash leaves the intent for `config recover`. "start": running now,
            # under the lock, so a container stopped after the plan is not started.
            c.mark(m, m.get("status", "ready"), operation="config-update",
                   pending_config={"runtime": c.validate_runtime_settings({**c.runtime_settings(m), **changed}),
                                   "restart": category == "restart", "start": bool(state and state.get("Running"))})
            _update_container(m)
    else:
        c.ensure_runtime(False)
        # Started again only if this call stopped it: one stopped by someone else stays stopped.
        stopped = p.container == "running" and c.stop(m)
        c.reconfigure_runtime(c.resolve(p.env_id), changed, profile=profile)
        if stopped:
            c.start(c.resolve(p.env_id))
    _refresh_guidance(p.env_id)
    return {"category": category, "applied": True, "settings": p.target}


def _update_container(m):
    """Run the journalled `config-update` steps (idempotent; also used by recover). Lock held."""
    pending = m["pending_config"]
    limits = pending["runtime"]
    try:
        state = c.inspect_container(m)
        if state is not None and pending["start"] and (pending["restart"] or not state.get("Running")):
            c.recheck_mount(m)  # it will be started: check before the stop
        if state is not None:
            if pending["restart"] and state.get("Running"):
                c.docker("stop", c.cname(m), capture=True)
            # docker run gives a container swap = 2 x memory; keep that when the limit changes.
            c.docker("update", "--cpus", limits["cpus"], "--memory", limits["memory"],
                     "--memory-swap", str(2 * c.memory_bytes(limits["memory"])), "--pids-limit", str(limits["pids"]),
                     c.cname(m), capture=True)
            if pending["start"] and not c.inspect_container(m).get("Running"):
                c.docker("start", c.cname(m), capture=True)
    except Exception as exc:
        c.mark(m, "error", last_error=f"Configuration change: {exc}")
        raise
    m["runtime"] = c.validate_runtime_settings({**c.runtime_settings(m), **limits})
    m.pop("pending_config", None)
    state = c.inspect_container(m)
    c.mark(m, "ready" if state is None else ("running" if state.get("Running") else "stopped"),
           operation=None, last_error=None)


def _refresh_guidance(env_id):
    with c.lock(env_id):
        m = c.resolve(env_id)
        ac.refresh(m, c.env_dir, **c.guidance_inputs(m))


def recover(m: dict) -> dict:
    """Finish an interrupted change: re-run a journalled limit update, or complete a container
    recreation (`core.recover_runtime_reconfigure`)."""
    c.ensure_runtime(False)
    m = c.resolve(m["id"])
    if m.get("operation") == "runtime-recreate":
        result = c.recover_runtime_reconfigure(m)
        _refresh_guidance(m["id"])
        return {**result, "next": f"start it with: opencode-sandbox start {m['name']}"}
    if m.get("operation") != "config-update":
        raise c.SandboxError("No interrupted configuration change")
    with c.lock(m["id"]):
        m = c.resolve(m["id"])
        if m.get("operation") != "config-update" or not isinstance(m.get("pending_config"), dict):
            raise c.SandboxError("No interrupted configuration change")
        _update_container(m)
    _refresh_guidance(m["id"])
    return {"recovered": True, "settings": current(c.resolve(m["id"]))}
