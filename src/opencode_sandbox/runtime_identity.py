"""Verify that the Docker endpoint is the current user's own rootless daemon (D-003).

The manager's Docker context (default ``rootless``) is resolved once to a ``unix://`` socket.
The response sender's kernel credentials (``SCM_CREDENTIALS``) and ``/proc`` must show ``dockerd`` running as
this user inside a user namespace that maps container UID/GID 0 to this user, and the engine
must report ``rootless``. Names (context, socket path, socket owner) are recorded, never trusted.

Standard library only, without package imports. The CLI and dashboard share this verifier;
it can also run directly for diagnostics without importing the application:

    python -I -B src/opencode_sandbox/runtime_identity.py [--context NAME] [--json]

Exit status: 0 verified, 3 unverified-proxy, 4 mismatch, 5 unavailable, 6 unsupported,
7 missing (no Docker CLI), 8 not-configured (the context does not exist or has no endpoint).
"""
from __future__ import annotations

import argparse
import errno
import json
import os
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
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
    UNAVAILABLE: "Check your rootless daemon's status and logs using your distribution's documentation, "
                 f"and check the context with 'docker context inspect'. See {SETUP_GUIDE}",
    UNSUPPORTED: "Only a local unix:// socket of your own rootless daemon is supported.",
    MISSING: "Install Docker with rootless support using Docker's official guide and your "
             "distribution's documentation. "
             f"See {SETUP_GUIDE}",
    NOT_CONFIGURED: "Configure a context for your own rootless daemon using the setup guide, "
                    "or set OPENCODE_SANDBOX_DOCKER_CONTEXT to the name of an existing rootless context "
                    f"(list them with 'docker context ls'). See {SETUP_GUIDE}",
}
# The Docker CLI's answer when a context name is unknown (Docker 29: 'context "x": context not found: ...').
_CONTEXT_UNKNOWN = ("context not found", "does not exist")
READINESS_TIMEOUT = 10.0
POLL = 0.1
MAX_RESPONSE = 512 * 1024


class Cancelled(BaseException):
    """A canceled preflight is not a failed operation or a daemon identity result."""


class Deadline(TimeoutError):
    pass


class Budget:
    """One monotonic acquisition budget, including context lookup and concurrent callers."""
    def __init__(self, timeout=READINESS_TIMEOUT, progress=None, cancelled=None):
        self.started = time.monotonic()
        self.timeout = timeout
        self.deadline = self.started + timeout
        self.progress = progress
        self.cancelled = cancelled
        self.notified = False

    def remaining(self):
        if self.cancelled and self.cancelled():
            raise Cancelled()
        now = time.monotonic()
        if self.progress and not self.notified and now - self.started >= 0.25:
            self.notified = True
            self.progress(f"Waiting for Docker readiness (up to {self.timeout:g}s); cancel to stop waiting.")
        if now >= self.deadline:
            raise Deadline(f"Docker readiness deadline exhausted after {self.timeout:g}s")
        return self.deadline - now

    def pause(self, seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            time.sleep(min(POLL, self.remaining(), max(0, until - time.monotonic())))


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


def _docker(argv, docker="docker", timeout=READINESS_TIMEOUT, *, budget=None):
    budget = budget or Budget(timeout)
    try:
        budget.remaining()
        p = subprocess.Popen([docker, *argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=docker_env(), stdin=subprocess.DEVNULL, start_new_session=True)
    except FileNotFoundError:
        return None, CLI_NOT_FOUND
    except OSError as exc:
        return None, f"Docker CLI failed: {exc}"
    try:
        while True:
            try:
                out, err = p.communicate(timeout=min(POLL, budget.remaining()))
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        # Including Ctrl-C/SystemExit/cancellation: reap only this owned read-only CLI child.
        if p.poll() is None:
            try: os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        try:
            p.communicate(timeout=0.2)
        except subprocess.TimeoutExpired:
            try: os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            p.stdout.close()
            p.stderr.close()
            p.wait(timeout=0.2)
    if p.returncode:
        lines = (err or out or "").strip().splitlines()
        return None, lines[-1] if lines else f"exit {p.returncode}"
    return out, None


def resolve_context(context, docker="docker", *, budget=None):
    """Return (endpoint, classification-or-None, reason) for a named context."""
    out, err = _docker(["context", "inspect", "--format", "{{json .}}", context], docker, budget=budget)
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
    tls = data.get("TLSMaterial") or {}
    if not isinstance(tls, dict):
        return endpoint, NOT_CONFIGURED, f"Docker context '{context}' has malformed TLS material"
    if tls.get("docker"):
        return endpoint, UNSUPPORTED, "context uses TLS material; a local rootless socket needs none"
    return endpoint, None, ""


def peer_credentials(path, *, budget=None):
    """Connect to a UNIX socket; return (pid, uid, gid, connected socket)."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(min(POLL, budget.remaining()) if budget else 5)
        # Must be enabled before connecting: no unauthenticated prefix may be buffered.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
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


class SenderError(ValueError):
    pass


class ResponseError(ValueError):
    pass


def _process_token(pid, proc):
    """Detect a process exiting/being replaced while its response is read (/proc stat field 22)."""
    try:
        text = ((proc or Path("/proc")) / str(pid) / "stat").read_text()
        return text.rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError) as exc:
        raise SenderError("cannot read the response sender's process start time") from exc


def _response(conn, budget, proc):
    """Bounded HTTP/1.0 /info; authenticate every received byte, including headers.

    Requesting HTTP/1.0 avoids chunking. EOF terminates the response; length, when supplied,
    must agree. No redirects, compression, upgrades, request bodies or Docker mutations.
    """
    request = memoryview(b"GET /info HTTP/1.0\r\nHost: localhost\r\n\r\n")
    while request:
        conn.settimeout(min(POLL, budget.remaining()))
        try:
            n = conn.send(request)
            if not n: raise ConnectionResetError("socket closed while sending readiness request")
            request = request[n:]
        except TimeoutError:
            continue
    data, sender, evidence, token = bytearray(), None, None, None
    while True:
        conn.settimeout(min(POLL, budget.remaining()))
        try:
            chunk, anc, flags, _ = conn.recvmsg(16384, socket.CMSG_SPACE(12), socket.MSG_CMSG_CLOEXEC)
        except TimeoutError:
            continue
        rights = False
        for level, kind, value in anc:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                rights = True
                for fd in struct.unpack(f"{len(value) // 4}i", value[:len(value) // 4 * 4]):
                    os.close(fd)
        if rights:
            raise SenderError("unexpected file descriptors in readiness response")
        if not chunk:
            break
        creds = [struct.unpack("3i", value) for level, kind, value in anc
                 if level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(value) == 12]
        if flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC) or len(creds) != 1:
            raise SenderError("missing or truncated kernel response-sender credentials")
        if sender is not None and creds[0] != sender:
            raise SenderError("response sender changed during the readiness probe")
        if sender is None:
            sender = creds[0]
            evidence = inspect_peer(*sender, proc=proc)
            if evidence[0]:
                return sender, evidence, None
            token = _process_token(sender[0], proc)
        data.extend(chunk)
        if len(data) > MAX_RESPONSE:
            raise ResponseError("Docker readiness response exceeds 512 KiB")
        if b"\r\n\r\n" not in data and len(data) > 16384:
            raise ResponseError("Docker readiness response headers exceed 16 KiB")
    if not data:
        raise ConnectionResetError("socket closed without a readiness response")
    if _process_token(sender[0], proc) != token:
        raise SenderError("response sender process changed while reading readiness")
    # Recheck the live process after receiving the complete response, not a claimed HTTP PID.
    evidence = inspect_peer(*sender, proc=proc)
    if evidence[0]:
        return sender, evidence, None
    header, sep, body = bytes(data).partition(b"\r\n\r\n")
    lines = header.split(b"\r\n")
    if not sep or len(header) > 16384 or lines[0] not in (b"HTTP/1.0 200 OK", b"HTTP/1.1 200 OK"):
        raise ResponseError("Docker readiness probe did not return a valid HTTP 200 response")
    headers = {}
    for line in lines[1:]:
        key, colon, value = line.partition(b":")
        key = key.lower()
        if not colon or key in headers:
            raise ResponseError("malformed or duplicate readiness response header")
        headers[key] = value.strip()
    if b"transfer-encoding" in headers or b"content-encoding" in headers:
        raise ResponseError("encoded readiness response is unsupported (expected HTTP/1.0 JSON)")
    length = headers.get(b"content-length")
    if length is not None and (len(length) > 8 or not length.isdigit() or int(length) != len(body)):
        raise ResponseError("readiness response Content-Length does not match the body")
    try:
        info = json.loads(body)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ResponseError("readiness response is not valid JSON") from exc
    options = info.get("SecurityOptions") if isinstance(info, dict) else None
    rootless = isinstance(options, list) and "name=rootless" in options
    return sender, evidence, rootless


def verify(context=None, *, endpoint=None, docker="docker", proc=Path("/proc"),
           timeout=READINESS_TIMEOUT, progress=None, cancelled=None, budget=None) -> Identity:
    """Classify the daemon behind ``context`` (or a fixed ``endpoint``, skipping context resolution)."""
    context = context or os.getenv("OPENCODE_SANDBOX_DOCKER_CONTEXT") or DEFAULT_CONTEXT
    notes = [f"{name} is set but ignored; the manager uses context '{context}'"
             for name in ("DOCKER_HOST", "DOCKER_CONTEXT") if os.environ.get(name)]
    budget = budget or Budget(timeout, progress, cancelled)
    try:
        budget.remaining()
        if endpoint is None:
            endpoint, problem, reason = resolve_context(context, docker, budget=budget)
            if problem:
                return Identity(problem, context, endpoint, reasons=(reason,), notes=tuple(notes))
    except Deadline as exc:
        return Identity(UNAVAILABLE, context, endpoint, reasons=(str(exc),), notes=tuple(notes))
    if not isinstance(endpoint, str) or not endpoint.startswith("unix://"):
        return Identity(UNSUPPORTED, context, endpoint, reasons=(f"endpoint {endpoint!r} is not unix://",))
    path = endpoint[len("unix://"):]
    if not os.path.isabs(path) or "\0" in path:
        return Identity(UNSUPPORTED, context, endpoint, reasons=("the socket path is not an absolute valid path",), notes=tuple(notes))
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
    last = "readiness probe did not complete"
    delay = 0.1
    while True:
        try:
            budget.remaining()
            pid, uid, gid, conn = peer_credentials(path, budget=budget)
            with conn:
                cls, reasons, exe, _ = inspect_peer(pid, uid, gid, proc=proc)
                # A foreign/rootful listener is never a rootless activation candidate.
                if cls == MISMATCH:
                    return result(cls, reasons, pid, exe)
                last = f"waiting for an authenticated Docker /info response on {path}"
                sender, evidence, rootless = _response(conn, budget, proc)
            pid, uid, gid = sender
            cls, reasons, exe, peer_notes = evidence
            notes += peer_notes
            if cls:
                return result(cls, reasons, pid, exe)
            if not rootless:
                return result(MISMATCH, ["the engine does not report the 'rootless' security option"], pid, exe)
            budget.remaining()
            return result(VERIFIED, [(f"kernel-authenticated response from dockerd pid {pid} as UID {uid} "
                                      f"in its own user namespace mapping 0 -> {uid}:{gid}; engine reports rootless")], pid, exe)
        except Deadline as exc:
            return result(UNAVAILABLE, [f"{exc}; last probe: {last}"])
        except SenderError as exc:
            return result(UNVERIFIED_PROXY, [str(exc)])
        except ResponseError as exc:
            return result(UNAVAILABLE, [str(exc)])
        except OSError as exc:
            last = f"cannot connect to or read {path}: {exc.strerror or exc}"
            # Only transport interruption/backlog, never permissions, stale/missing sockets,
            # malformed configuration, an HTTP error, or a failed sender identity check.
            if not isinstance(exc, (socket.timeout, ConnectionResetError)) and exc.errno not in (errno.EAGAIN, errno.EINTR):
                return result(UNAVAILABLE, [last])
        try:
            budget.pause(delay)
        except Deadline as exc:
            return result(UNAVAILABLE, [f"{exc}; last probe: {last}"])
        delay = min(0.5, delay * 2)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Verify the Docker daemon identity used by OpenCode Sandbox.")
    ap.add_argument("--context", default=None, help="Docker context (default: $OPENCODE_SANDBOX_DOCKER_CONTEXT or rootless)")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args(argv)
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)

    handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGHUP)}
    try:
        ident = verify(args.context, progress=lambda message: print(message, file=sys.stderr, flush=True))
    finally:
        for sig, handler in handlers.items(): signal.signal(sig, handler)
    print(json.dumps(asdict(ident), indent=2) if args.json else ident.report())
    return EXIT_CODES[ident.classification]


if __name__ == "__main__":
    try: sys.exit(main())
    except KeyboardInterrupt: sys.exit(130)
