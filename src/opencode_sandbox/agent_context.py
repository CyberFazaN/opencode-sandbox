"""Deterministic, non-secret OpenCode sandbox guidance (D-008).

The manager owns this file outside the workspace, in a directory that is bind-mounted
read-only at /run/ocs-agent (a directory mount shows atomic replacements; a single-file
mount would keep the old inode). The managed image's system config
/etc/opencode/opencode.json lists it in `instructions`, which OpenCode combines with the
instructions of every other config document, so user configuration stays untouched.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from . import distros

CONTAINER_DIR = "/run/ocs-agent"
CONTAINER_PATH = CONTAINER_DIR + "/context.md"
SYSTEM_CONFIG = "/etc/opencode/opencode.json"


OBSERVED = (("network", "network"), ("cpus", "CPU limit"), ("memory", "memory limit"), ("pids", "process limit"))


def render(m: dict, *, image: str, runtime: dict, observed: dict | None = None) -> str:
    """Describe only what the manager configures or verifies for this environment.

    `runtime` is the configured runtime; `observed` the same keys as Docker reports them for
    the existing container (None when there is none, or Docker was not asked). Observed values
    win; a difference is stated, identical values render exactly like the configured ones.
    The OS comes from the environment's registry distribution (metadata), never from the
    image name; derived images (snapshot, runtime change, restore) keep it. A custom image
    can differ in everything: never promise specific executables or users.
    """
    distro = distros.get(m["distro"]) if m.get("distro") is not None else None
    actual = {**runtime, **{k: v for k, v in (observed or {}).items() if k in dict(OBSERVED)}}
    differs = [f"{label} {runtime[key]}" for key, label in OBSERVED if actual[key] != runtime[key]]
    net = actual["network"]
    lines = [
        "# OpenCode Sandbox — environment guidance (managed)",
        "", "You are running inside a Docker container, not on the host operating system.",
        "This is context, not a security boundary. Actual access depends on Docker mounts, privileges and network configuration.",
        "", "## Container, user and privileges",
        "- Container image: " + image,
    ]
    if distro:
        lines.append("- You run as root (UID 0) in the container. Rootless Docker maps it to the host user who owns this "
                     "sandbox: files you create in /workspace belong to that user on the host. Other container users "
                     "map to unprivileged subordinate IDs, so files they create there may not be editable on the host.")
    else:
        lines.append("- The container user is defined by the custom image. Rootless Docker maps container UID 0 to the "
                     "host user who owns this sandbox and other UIDs to unprivileged subordinate IDs.")
    lines += [
        "- The container runs with no-new-privileges: sudo and setuid programs cannot raise privileges. Container root is not root on the host.",
        ("- There is no Docker socket and no host package manager in the container. Host files are mounted "
         "only at /workspace (plus read-only files the manager provides under /run). "
         "Do not try to manage the host, the Docker daemon, hardware or system services."),
        "- Do not assume access to GPU, USB, cameras or audio.",
        "", "## Workspace and persistence",
        f"- Environment: {m['name']} ({m['kind']}). Working directory: /workspace. Work on project files here.",
        *workspace_lines(m),
        ("- /workspace is a bind mount from the host and /root a persistent Docker volume (OpenCode state, user data): "
         "both survive stopping, recreating and reconfiguring the container."),
        ("- Packages and files elsewhere live in the container's system layer: kept across stop/start, recreation and "
         "runtime changes, but lost when the user restores a backup without it. Do not assume they are permanent."),
        "- Keep credentials out of command output, logs, source files and answers.",
        "", "## Network and resources",
        "- Networking mode: " + net,
    ]
    if net == "none":
        lines.append("- Docker network is disabled (loopback only). Do not attempt package downloads or network APIs; "
                     "request a network configuration change from the user if required.")
    else:
        lines.append("- Docker bridge networking is enabled: the internet, other machines on the local network and "
                     "services on the host's network addresses may be reachable. This is not "
                     "network isolation; use only the network services your task needs.")
    for port in runtime["ports"] if net != "none" else ():
        lines.append(f"- Published port: container {port['container']}/{port['protocol']} is reachable from the host at "
                     f"127.0.0.1:{port['host']} only; a server must listen on 0.0.0.0 (not 127.0.0.1) in the container.")
    lines += ["- CPU limit: " + str(actual["cpus"]),
              "- Memory limit: " + str(actual["memory"]),
              "- Process limit: " + str(actual["pids"])]
    if differs:
        lines.append("- The running container was created with these values; the current configuration ("
                     + ", ".join(differs) + ") applies only after the user recreates it.")
    if distro:
        lines += ["", f"## Operating system ({distro.name} {distro.version})", *distro.context_lines()]
        if image != distro.image:
            lines.append("- This container runs an image derived from the managed base image (snapshot, runtime change or restore).")
        lines.append("- Tools may have been changed after image creation; check only when the task needs an exact version or availability.")
    else:
        lines += ["", "## Operating system",
                  "- Custom image: installed tools, OS and package manager are unknown; inspect only when needed."]
    lines += integration_lines(m)
    lines += ["", "## Working behavior",
              "- Start with the user's task; avoid a full system inventory or repeated probing.",
              "- If a dependency is missing, explain the required change; use container-local installation only when appropriate and permitted.",
              "- Never attempt to bypass container boundaries or reconfigure the host.",
              ("- OpenCode's own update check is off in this container (OPENCODE_DISABLE_AUTOUPDATE=1): the sandbox "
               "manager on the host installs and updates OpenCode. Do not run `opencode upgrade`."),
              "- Follow project AGENTS.md instructions in addition to this environment guidance.", ""]
    return "\n".join(lines)


def workspace_lines(m: dict) -> list[str]:
    """What /workspace is. Host paths are not named."""
    if (m.get("workspace") or {}).get("mode") == "direct":
        lines = [("- /workspace is the user's own host directory, mounted directly (not a copy): every change, "
                  "including deleting or overwriting files, happens at once in the user's files on the host. "
                  "There is no undo through the sandbox and backups do not include it by default; ask before "
                  "large deletions or rewrites, and leave version control to the user unless asked.")]
    elif m.get("source"):
        lines = [("- /workspace holds a copy of a host directory, made when the environment was created (Git "
                  "repository: committed files only; other directories: a filtered copy). The original is not "
                  "mounted: your edits reach it only when the user exports or applies them with the manager.")]
    else:
        lines = ["- /workspace started empty; it is not connected to any host project."]
    if m.get("kind") == "quick":
        lines.append("- This is a quick (disposable) session: when it ends, the user decides whether to export, keep, "
                     "promote or delete it. Do not rely on /workspace being kept.")
    return lines


def integration_lines(m: dict) -> list[str]:
    """Initial integrations (D-009) are history: provisioned once, possibly changed since."""
    provisioning = m.get("provisioning")
    requested = provisioning.get("requested") if isinstance(provisioning, dict) else None
    if not requested or not isinstance(requested, list):
        return []
    result = provisioning.get("result")
    names = ", ".join(str(item) for item in requested)
    if provisioning.get("state") in ("pending", "applying"):
        return ["", "## Initial integrations",
                f"- Requested at creation, set up once at the first container start (not done yet): {names}."]
    return ["", "## Initial integrations",
            f"- Provisioned once, at the first container start: {names}" + (f" ({result})" if isinstance(result, str) and result else "") + ".",
            "- They may have been changed or removed since; check the OpenCode configuration before relying on them."]


def directory(m: dict, env_dir) -> Path:
    return env_dir(m["id"]) / "agent-context"


def path(m: dict, env_dir) -> Path:
    return directory(m, env_dir) / "context.md"


def refresh(m: dict, env_dir, *, image: str, runtime: dict, observed: dict | None = None) -> Path:
    target = path(m, env_dir)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    contents = render(m, image=image, runtime=runtime, observed=observed)
    fd, tmp = tempfile.mkstemp(prefix=".agent-context-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(contents)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return target


def verify(m: dict, env_dir, *, image: str, runtime: dict, observed: dict | None = None) -> bool:
    target = path(m, env_dir)
    expected = render(m, image=image, runtime=runtime, observed=observed)
    return target.is_file() and not target.is_symlink() and target.read_text(encoding="utf-8") == expected

