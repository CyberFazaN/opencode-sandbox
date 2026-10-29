"""Verify that the Docker endpoint is the current user's own rootless daemon (D-003).

The manager's Docker context (default ``rootless``) is resolved once to a ``unix://`` socket.
The socket's peer credentials (``SO_PEERCRED``) and ``/proc`` must show ``dockerd`` running as
this user inside a user namespace that maps container UID/GID 0 to this user, and the engine
must report ``rootless``. Names (context, socket path, socket owner) are recorded, never trusted.

Standard library only, without package imports, so ``install.sh`` and ``setup-rootless.sh`` can
run it from the source tree before a venv exists:

    python -I -B src/opencode_sandbox/runtime_identity.py [--context NAME] [--json]

Exit status: 0 verified, 3 unverified-proxy, 4 mismatch, 5 unavailable, 6 unsupported,
7 missing (no Docker CLI), 8 not-configured (the context does not exist or has no endpoint).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import stat
import struct
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERIFIED = "verified"
UNVERIFIED_PROXY = "unverified-proxy"
MISMATCH = "mismatch"
UNAVAILABLE = "unavailable"
UNSUPPORTED = "unsupported"
MISSING = "missing"
NOT_CONFIGURED = "not-configured"
EXIT_CODES = {VERIFIED: 0, UNVERIFIED_PROXY: 3, MISMATCH: 4, UNAVAILABLE: 5, UNSUPPORTED: 6, MISSING: 7, NOT_CONFIGURED: 8}
DEFAULT_CONTEXT = "rootless"
# Variables that would otherwise redirect or alter the Docker CLI; -H overrides the endpoint,
# these are dropped so they cannot add TLS or a second endpoint behind the verified one.
IGNORED_ENV = ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_TLS")
# A pipx installation has no source checkout, so the hints name the published guide.
SETUP_GUIDE = "https://github.com/CyberFazaN/opencode-sandbox/blob/main/docs/install.md#prepare-docker"
HINTS = {
    UNVERIFIED_PROXY: "Point the context at the rootless daemon's own socket (usually "
                      "unix://$XDG_RUNTIME_DIR/docker.sock), not at a proxy.",
    MISMATCH: f"Use your own rootless daemon (see {SETUP_GUIDE}); another user's daemon or a "
              "rootful daemon would own the files and containers created for you.",
    UNAVAILABLE: "Start your rootless daemon (systemctl --user start docker) or check the context "
                 f"with 'docker context inspect'. See {SETUP_GUIDE}",
    UNSUPPORTED: "Only a local unix:// socket of your own rootless daemon is supported.",
    MISSING: "Install Docker with its rootless extras from your distribution's packages or "
             "Docker's (Arch Linux: pacman -S docker; the setup tool dockerd-rootless-setuptool.sh "
             "comes from the AUR package docker-rootless-extras or from Docker's upstream scripts). "
             f"See {SETUP_GUIDE}",
    NOT_CONFIGURED: "Run dockerd-rootless-setuptool.sh install, which creates the context 'rootless', "
                    "or set OPENCODE_SANDBOX_DOCKER_CONTEXT to the name of your rootless context "
                    f"(list them with 'docker context ls'). See {SETUP_GUIDE}",
}
# The Docker CLI's answer when a context name is unknown (Docker 29: 'context "x": context not found: ...').
_CONTEXT_UNKNOWN = ("context not found", "does not exist")


@dataclass(frozen=True)
class Identity:
    classification: str
    context: str
    endpoint: str | None = None
    socket: str | None = None
    pid: int | None = None
    executable: str | None = None
    reasons: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())

    @property
    def verified(self) -> bool:
        return self.classification == VERIFIED

    def message(self) -> str:
        """One paragraph for errors: classification, reasons and what to do."""
        text = f"Docker daemon identity: {self.classification} (context '{self.context}'"
        text += f", {self.endpoint})" if self.endpoint else ")"
        if self.reasons:
            text += ": " + "; ".join(self.reasons)
        hint = HINTS.get(self.classification)
        return text + (f". {hint}" if hint else "")

    def report(self) -> str:
        lines = [f"Docker context: {self.context}"]
        if self.endpoint:
            lines.append(f"Endpoint: {self.endpoint}")
        if self.pid is not None:
            lines.append(f"Daemon process: pid {self.pid}" + (f", {self.executable}" if self.executable else ""))
        lines.append(f"Daemon identity: {self.classification}")
        lines += [f"  reason: {r}" for r in self.reasons]
        lines += [f"  note: {n}" for n in self.notes]
        if not self.verified and self.classification in HINTS:
            lines.append(f"  hint: {HINTS[self.classification]}")
        return "\n".join(lines)


def docker_env(environ=None) -> dict:
    env = dict(os.environ if environ is None else environ)
    for name in IGNORED_ENV:
        env.pop(name, None)
    return env


CLI_NOT_FOUND = "Docker CLI not found"


def _docker(argv, docker="docker", timeout=30):
    try:
        p = subprocess.run([docker, *argv], capture_output=True, text=True, env=docker_env(),
                           timeout=timeout, check=False, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return None, CLI_NOT_FOUND
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"Docker CLI failed: {exc}"
    if p.returncode:
        lines = (p.stderr or p.stdout or "").strip().splitlines()
        return None, lines[-1] if lines else f"exit {p.returncode}"
    return p.stdout, None


def resolve_context(context, docker="docker"):
    """Return (endpoint, classification-or-None, reason) for a named context."""
    out, err = _docker(["context", "inspect", "--format", "{{json .}}", context], docker)
    if out is None:
        if err == CLI_NOT_FOUND:
            return None, MISSING, "the Docker CLI (docker) is not installed or not on PATH"
        if any(marker in err for marker in _CONTEXT_UNKNOWN):
            return None, NOT_CONFIGURED, f"Docker context '{context}' does not exist"
        return None, UNAVAILABLE, f"cannot inspect Docker context '{context}': {err}"
    try:
        data = json.loads(out)
        endpoint = data["Endpoints"]["docker"]["Host"]
    except (ValueError, KeyError, TypeError):
        return None, NOT_CONFIGURED, f"Docker context '{context}' has no readable docker endpoint"
    if not isinstance(endpoint, str) or not endpoint.startswith("unix://"):
        return str(endpoint), UNSUPPORTED, f"endpoint {endpoint!r} is not a local unix:// socket"
    if (data.get("TLSMaterial") or {}).get("docker"):
        return endpoint, UNSUPPORTED, "context uses TLS material; a local rootless socket needs none"
    return endpoint, None, ""


def peer_credentials(path):
    """Connect to a UNIX socket; return (pid, uid, gid, connected socket)."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect(path)
        pid, uid, gid = struct.unpack("3i", s.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
    except BaseException:
        s.close()
        raise
    return pid, uid, gid, s


def _id_map(text):
    """Parse /proc/<pid>/{uid,gid}_map; return the outside ID of inside ID 0, or None."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "0" and int(parts[2]) >= 1:
            return int(parts[1])
    return None


def inspect_peer(pid, uid, gid, *, proc=Path("/proc"), my_uid=None, my_gid=None):
    """Classify the socket's peer process. Return (classification-or-None, reasons, executable, notes)."""
    my_uid = os.getuid() if my_uid is None else my_uid
    my_gid = os.getgid() if my_gid is None else my_gid
    notes = []
    if uid != my_uid:
        who = "root (a rootful daemon)" if uid == 0 else f"UID {uid} (another user)"
        return MISMATCH, [f"the socket is served by {who}, not by UID {my_uid}"], None, notes
    if pid <= 0:
        return UNVERIFIED_PROXY, ["the peer process is not visible from this PID namespace"], None, notes
    base = proc/str(pid)
    try:
        exe = os.readlink(base/"exe")
    except OSError as exc:
        return UNVERIFIED_PROXY, [f"cannot read the peer executable of pid {pid}: {exc.strerror}"], None, notes
    if exe.endswith(" (deleted)"):
        exe = exe[:-len(" (deleted)")]
        notes.append("the daemon binary was replaced on disk since the daemon started (restart it after updates)")
    if os.path.basename(exe) != "dockerd":
        return UNVERIFIED_PROXY, [(f"the socket is served by {exe} (pid {pid}), not dockerd; the daemon behind it "
                                   "cannot be identified")], exe, notes
    try:
        peer_ns = os.readlink(base/"ns"/"user")
        own_ns = os.readlink(proc/"self"/"ns"/"user")
        uid_map = (base/"uid_map").read_text()
        gid_map = (base/"gid_map").read_text()
    except OSError as exc:
        return UNVERIFIED_PROXY, [f"cannot read the user namespace of pid {pid}: {exc.strerror}"], exe, notes
    if peer_ns == own_ns:
        return MISMATCH, ["dockerd runs in this user namespace, so it is not a rootless daemon"], exe, notes
    reasons = []
    root_uid, root_gid = _id_map(uid_map), _id_map(gid_map)
    if root_uid != my_uid:
        reasons.append(f"the daemon's user namespace maps UID 0 to {root_uid}, not to {my_uid}")
    if root_gid != my_gid:
        reasons.append(f"the daemon's user namespace maps GID 0 to {root_gid}, not to {my_gid}")
    if reasons:
        return MISMATCH, reasons, exe, notes
    return None, [], exe, notes


def engine_reports_rootless(endpoint, docker="docker"):
    """Return (True|False|None, detail); None when the engine did not answer."""
    out, err = _docker(["-H", endpoint, "info", "--format", "{{json .SecurityOptions}}"], docker)
    if out is None:
        return None, err
    return "rootless" in out.lower(), out.strip()


def verify(context=None, *, endpoint=None, docker="docker", proc=Path("/proc")) -> Identity:
    """Classify the daemon behind ``context`` (or a fixed ``endpoint``, skipping context resolution)."""
    context = context or os.getenv("OPENCODE_SANDBOX_DOCKER_CONTEXT") or DEFAULT_CONTEXT
    notes = [f"{name} is set but ignored; the manager uses context '{context}'"
             for name in ("DOCKER_HOST", "DOCKER_CONTEXT") if os.environ.get(name)]
    if endpoint is None:
        endpoint, problem, reason = resolve_context(context, docker)
        if problem:
            return Identity(problem, context, endpoint, reasons=(reason,), notes=tuple(notes))
    elif not endpoint.startswith("unix://"):
        return Identity(UNSUPPORTED, context, endpoint, reasons=(f"endpoint {endpoint!r} is not unix://",))
    path = endpoint[len("unix://"):]
    if not os.path.isabs(path):
        return Identity(UNSUPPORTED, context, endpoint, reasons=("the socket path is not absolute",), notes=tuple(notes))
    real = os.path.realpath(path)
    if real != path:
        notes.append(f"socket path {path} resolves to {real}; using {real}")
        path, endpoint = real, "unix://" + real

    def result(cls, reasons, pid=None, exe=None):
        return Identity(cls, context, endpoint, path, pid, exe, tuple(reasons), tuple(notes))

    try:
        st = os.stat(path)
    except FileNotFoundError:
        return result(UNAVAILABLE, [f"socket {path} does not exist (daemon not running?)"])
    except OSError as exc:
        return result(UNAVAILABLE, [f"cannot stat socket {path}: {exc.strerror}"])
    if not stat.S_ISSOCK(st.st_mode):
        return result(UNSUPPORTED, [f"{path} is not a socket"])
    notes.append(f"socket owner {st.st_uid}:{st.st_gid} (recorded, not trusted)")
    try:
        pid, uid, gid, conn = peer_credentials(path)
    except OSError as exc:
        return result(UNAVAILABLE, [f"cannot connect to {path}: {exc.strerror or exc} (daemon not running?)"])
    try:
        cls, reasons, exe, peer_notes = inspect_peer(pid, uid, gid, proc=proc)
    finally:
        conn.close()
    notes += peer_notes
    if cls:
        return result(cls, reasons, pid, exe)
    rootless, detail = engine_reports_rootless(endpoint, docker)
    if rootless is None:
        return result(UNAVAILABLE, [f"dockerd (pid {pid}) did not answer 'docker info': {detail}"], pid, exe)
    if not rootless:
        return result(MISMATCH, ["the engine does not report the 'rootless' security option"], pid, exe)
    return result(VERIFIED, [(f"dockerd pid {pid} runs as UID {uid} in its own user namespace mapping 0 -> "
                              f"{uid}:{gid}; engine reports rootless")], pid, exe)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Verify the Docker daemon identity used by OpenCode Sandbox.")
    ap.add_argument("--context", default=None, help="Docker context (default: $OPENCODE_SANDBOX_DOCKER_CONTEXT or rootless)")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args(argv)
    ident = verify(args.context)
    print(json.dumps(asdict(ident), indent=2) if args.json else ident.report())
    return EXIT_CODES[ident.classification]


if __name__ == "__main__":
    sys.exit(main())
