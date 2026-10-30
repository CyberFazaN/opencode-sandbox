"""Readiness checks: one implementation for `check NAME`, `doctor`, `status` and the dashboard.

`run(m)` is the explicit, comprehensive check: read-only (it never starts, stops or changes an
environment), it measures network reachability from inside a running container, and it stores the
report as the environment's cached readiness (`readiness.json`), which `status` and the dashboard
show without contacting Docker again. Every check has one of five results.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import socket
import subprocess
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from . import core as c

PASSED, WARNING, FAILED, NOT_CHECKED, NOT_APPLICABLE = "passed", "warning", "failed", "not checked", "not applicable"
ORDER = (PASSED, WARNING, FAILED, NOT_CHECKED, NOT_APPLICABLE)
CACHE = "readiness.json"
SCHEMA = 1

# rootlesskit's slirp4netns driver gives the host this address; with --disable-host-loopback
# connections to it never reach the host's 127.0.0.1 (D-015).
SLIRP_HOST = "10.0.2.2"
INTERNET = ("registry.npmjs.org", 443)

# Executed by the container's python3 (registry images have it). Outcomes only, no data: TCP
# connect (optionally sending a token), and a TLS handshake with certificate verification for the
# internet (a NAT that accepts every connection would fake a plain TCP connect).
PROBE = r"""import concurrent.futures as cf,json,socket,ssl,sys
spec=json.loads(sys.argv[1])
def tcp(host,port,token=None):
    try: s=socket.create_connection((host,port),timeout=3)
    except socket.gaierror: return "no-dns"
    except ConnectionRefusedError: return "refused"
    except TimeoutError: return "timeout"
    except OSError as e: return "unreachable" if e.errno in (101,113) else "error"
    try:
        if token: s.sendall(token.encode())
    except OSError: pass
    s.close(); return "connected"
def tls(host,port,token=None):
    try:
        with socket.create_connection((host,port),timeout=5) as s:
            with ssl.create_default_context().wrap_socket(s,server_hostname=host): return "verified"
    except socket.gaierror: return "no-dns"
    except ssl.SSLError: return "tls-error"
    except TimeoutError: return "timeout"
    except OSError as e: return "unreachable" if e.errno in (101,113) else "error"
with cf.ThreadPoolExecutor(8) as pool:
    jobs={k:pool.submit(tls if k=="internet" else tcp,*v) for k,v in spec.items()}
    print(json.dumps({k:j.result() for k,j in jobs.items()}))
"""
REACHED = {"connected", "refused"}  # a refused connection was answered by the target's stack


@dataclass
class Check:
    id: str
    title: str
    status: str
    detail: str
    hint: str | None = None


def _recreate_hint(m):
    return f"Recreate the container to apply the configuration: opencode-sandbox container recreate {m['name']} --yes"


RECOVERY = {
    "runtime-recreate": "opencode-sandbox config recover {name}",
    "config-update": "opencode-sandbox config recover {name}",
    "recreate": "opencode-sandbox container recreate-recover {name}",
    "restore": "opencode-sandbox backup restore-resume {name} (or: opencode-sandbox backup restore-rollback {name} --yes)",
    "delete": "opencode-sandbox delete {name} --yes",
    "opencode-update": "opencode-sandbox opencode update-recover {name}",
}


# ---------------------------------------------------------------------------------------------
# Host

HOST_PROGRAMS = (("git", "Git", "project imports from Git, change review and transfer"),
                 ("docker", "Docker CLI", "everything that uses containers"))


def host_checks():
    """The programs the manager runs on the host (`doctor`): found or not, and what needs them."""
    import shutil
    import sys
    out = [Check("python", "Python", PASSED, f"{sys.version.split()[0]} ({sys.executable})")]
    for name, title, needed in HOST_PROGRAMS:
        path = shutil.which(name)
        if path is None:
            # The Docker CLI's hint is the daemon identity report's ("missing"), printed right after.
            hint = "See the daemon identity below" if name == "docker" else c.PROGRAM_HINTS[name]
            out.append(Check(name, title, FAILED, f"not found on PATH (needed for {needed})", hint))
            continue
        p = c.run_program([path, "--version"], capture_output=True, text=True, check=False, timeout=30,
                          stdin=subprocess.DEVNULL)
        version = (p.stdout or "").strip().splitlines()[:1]
        out.append(Check(name, title, PASSED, f"{version[0] if version else 'version unknown'} ({path})"))
    return out


def daemon_check():
    ident = c.verify_runtime(strict=False)
    if ident.verified:
        return Check("daemon", "Docker daemon", PASSED, f"verified rootless daemon of this user ({ident.endpoint})")
    return Check("daemon", "Docker daemon", FAILED, ident.message(), "See: opencode-sandbox doctor")


RESOURCE_HINT = ("Review Docker's rootless resource-limit requirements and your distribution's guidance: "
                 "https://docs.docker.com/engine/security/rootless/tips/#limiting-resources. "
                 "No host settings are changed by this check.")
RESOURCE_FLAGS = {"CPU quota": ("CpuCfsQuota", "CpuCfsPeriod"), "memory": ("MemoryLimit",), "pids": ("PidsLimit",)}


def resource_support_check():
    """Daemon-reported support, not an active stress test or proof of per-container enforcement."""
    check_id, title = "resource-support", "Resource-limit support"
    try:
        info = c.docker_info()
    except c.SandboxError as exc:
        return Check(check_id, title, NOT_CHECKED, f"support not established: {exc}", RESOURCE_HINT)
    if not isinstance(info, dict):
        return Check(check_id, title, NOT_CHECKED, "support not established: invalid Docker info data", RESOURCE_HINT)
    version, driver = info.get("CgroupVersion"), info.get("CgroupDriver")
    # Only real booleans are evidence: absent fields, strings and integers are unknown.
    missing = [name for name, fields in RESOURCE_FLAGS.items() if any(info.get(key) is False for key in fields)]
    unknown = [name for name, fields in RESOURCE_FLAGS.items()
               if name not in missing and any(type(info.get(key)) is not bool for key in fields)]
    # Do not echo arbitrary daemon fields (or warnings) into diagnostics/logs.
    topology = f"cgroup v{version if version in ('1', '2') else 'unknown'}; "
    topology += f"driver {driver if driver in ('systemd', 'cgroupfs', 'none') else 'unknown'}"
    if version == "1" or driver == "none" or missing:
        why = "Docker reports no support for " + ", ".join(missing) if missing else "rootless limits require cgroup v2 and a supported driver"
        if unknown: why += "; support not established for " + ", ".join(unknown)
        return Check(check_id, title, WARNING, f"{topology}; {why}; limits may be ignored", RESOURCE_HINT)
    if version != "2" or driver != "systemd" or unknown:
        detail = "support not established"
        if unknown: detail += ": missing/invalid evidence for " + ", ".join(unknown)
        return Check(check_id, title, NOT_CHECKED, f"{topology}; {detail}", RESOURCE_HINT)
    return Check(check_id, title, PASSED,
                 f"{topology}; Docker reports CPU quota, memory and pids support; enforcement not measured")


def storage_check():
    root = c.docker_root()
    if root is None:
        return Check("storage", "Docker storage", NOT_CHECKED, "Docker root directory not visible from the host")
    import shutil
    free, reserve = shutil.disk_usage(root).free, c.docker_reserve()
    detail = f"{free / 2**30:.1f} GiB free in {root}"
    if free < reserve:
        return Check("storage", "Docker storage", WARNING,
                     f"{detail}; snapshots, OpenCode updates and image builds need {reserve / 2**30:.1f} GiB",
                     "See what uses it: opencode-sandbox disk usage (remove leftovers: opencode-sandbox disk cleanup)")
    return Check("storage", "Docker storage", PASSED, detail)


def image_checks():
    """Managed base tags only: compare their labels with this manager's image definitions.

    This does not inspect an existing container's OS or require replacing its system layer.
    A diagnostic never rebuilds an image or gates an environment operation.
    """
    from . import distros
    return [_base_image_check(d) for d in distros.REGISTRY.values()]


def _base_image_check(distro):
    from . import distros
    check_id, title = f"image-{distro.id}", f"Base image {distro.image}"
    build = f"opencode-sandbox build --distro {distro.id}"
    inspect_hint = "Check Docker's status and permissions, then rerun: opencode-sandbox doctor"
    try:
        p = c.docker("image", "inspect", "--format", "{{json .Config.Labels}}", distro.image, capture=True, check=False)
    except c.SandboxError as exc:
        return Check(check_id, title, NOT_CHECKED, f"image inspect failed: {c.error_text(exc)[:200]}", inspect_hint)
    if p.returncode:
        error = (p.stderr or "").strip()
        # An inspect failure is not evidence of absence (e.g. a daemon stopped after verification).
        if re.search(r"(?:^|\n)(?:Error(?: response from daemon)?: )?No such image(?::|$)", error, re.IGNORECASE):
            return Check(check_id, title, WARNING, f"missing ({distro.name} environments cannot be created)", build)
        return Check(check_id, title, NOT_CHECKED, f"image inspect failed: {error[:200] or f'exit {p.returncode}'}", inspect_hint)
    try:
        labels = json.loads(p.stdout or "")
    except ValueError:
        labels = ...
    if labels is not None and not isinstance(labels, dict):
        return Check(check_id, title, NOT_CHECKED, "invalid image inspect response (expected labels)", inspect_hint)
    labels = labels or {}
    review = f"Review the image at {distro.image} before rebuilding: {build}"
    if labels.get(distros.LABEL + "managed") != "true" or labels.get(distros.LABEL + "distro") != distro.id:
        return Check(check_id, title, WARNING,
                     "present, but managed/distribution labels are missing or do not match; image revision cannot be verified", review)
    raw = labels.get(distros.LABEL + "image-revision")
    try:
        revision = int(raw) if isinstance(raw, str) and re.fullmatch(r"[1-9][0-9]*", raw) else None
    except ValueError:  # e.g. a label exceeding Python's integer-string conversion limit
        revision = None
    if revision is None:
        return Check(check_id, title, WARNING,
                     "present, but image revision cannot be verified (missing or invalid image-revision label)", review)
    detail = f"{distro.name}; image revision {revision}"
    if revision < distro.revision:
        return Check(check_id, title, WARNING, f"{detail} is older than the manager definition ({distro.revision})", build)
    if revision > distro.revision:
        return Check(check_id, title, WARNING, f"{detail} is newer than the manager definition ({distro.revision})",
                     "Do not rebuild just to remove this warning; check opencode-sandbox --version and the image's release notes")
    if labels.get(distros.LABEL + "distro-version") != distro.version:
        return Check(check_id, title, WARNING,
                     "present, but the distribution version label does not match the manager definition; image revision cannot be verified", review)
    return Check(check_id, title, PASSED, f"{detail} (current definition)")


def rootlesskit_flags(proc=Path("/proc")):
    """The visible command line of this user's rootlesskit (D-015); None when not visible."""
    uid = os.getuid()
    try:
        entries = list(proc.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != uid or (entry / "comm").read_text().strip() != "rootlesskit":
                continue
            argv = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        args = [a.decode(errors="replace") for a in argv if a]
        net = next((a.split("=", 1)[1] for a in args if a.startswith("--net=")), None)
        port = next((a.split("=", 1)[1] for a in args if a.startswith("--port-driver=")), None)
        return {"net": net, "disable_host_loopback": "--disable-host-loopback" in args, "port_driver": port}
    return None


def host_address():
    """The host's primary IPv4 address (route lookup; a UDP connect sends no packet)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            address = s.getsockname()[0]
    except OSError:
        return None
    return None if address.startswith("127.") or address == "0.0.0.0" else address


def host_gateway(route=Path("/proc/net/route")):
    try:
        lines = route.read_text().splitlines()[1:]
    except OSError:
        return None
    for line in lines:
        f = line.split()
        if len(f) > 3 and f[1] == "00000000" and int(f[3], 16) & 2:
            return socket.inet_ntoa(bytes.fromhex(f[2])[::-1])
    return None


class LoopbackListener:
    """A short-lived listener on the host's 127.0.0.1 (never a LAN address) that records whether a
    connection carrying `token` arrived: host-side evidence, a container cannot fake a reach."""

    def __init__(self):
        self.token = secrets.token_hex(8)
        self.reached = False
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                if self._stop.is_set():
                    return  # only after the backlog is empty: a finished probe's connection waits there
                continue
            with conn:
                conn.settimeout(1)
                try:
                    if conn.recv(64).decode(errors="replace") == self.token:
                        self.reached = True
                except OSError:
                    pass

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(2)
        self.sock.close()


# ---------------------------------------------------------------------------------------------
# Environment

def _inspect(m):
    """(state, full inspect dict) of the owned container, or (None, None)."""
    state = c.inspect_container(m)
    if state is None:
        return None, None
    p = c.docker("container", "inspect", "--format", "{{json .}}", c.cname(m), capture=True)
    try:
        data = json.loads(p.stdout)
    except ValueError as exc:
        raise c.SandboxError("Invalid Docker inspect response") from exc
    return state, data if isinstance(data, dict) else {}


def _exec(m, *argv):
    return c.docker("exec", c.cname(m), *argv, capture=True, check=False)


def operation_check(m, state):
    op, status = m.get("operation"), m.get("status")
    if op in RECOVERY:
        return Check("operation", "Pending operation", FAILED, f"{op} is still running in another command or was interrupted; most commands refuse until it finishes or is recovered",
                     RECOVERY[op].format(name=m["name"]))
    if op:
        return Check("operation", "Pending operation", WARNING, f"operation {op} did not finish",
                     f"opencode-sandbox repair {m['name']}")
    if status == "error":
        return Check("operation", "Pending operation", WARNING, f"last error: {m.get('last_error') or 'unknown'}",
                     f"opencode-sandbox repair {m['name']}")
    actual = None if state is ... else "missing" if state is None else "running" if state.get("Running") else "stopped"
    if actual and status in ("running", "stopped") and actual != status:
        return Check("operation", "Pending operation", WARNING, f"metadata says {status}, Docker reports {actual}",
                     f"opencode-sandbox repair {m['name']}")
    return Check("operation", "Pending operation", PASSED, "none")


def workspace_check(m):
    from . import workspaces
    try:
        w = workspaces.info(m)
        if w["mode"] == workspaces.DIRECT:
            target = workspaces.recheck(m)
            return Check("workspace", "Workspace", PASSED, f"direct host directory {target}, checks pass")
        p = workspaces.managed_path(m)
        if p.is_dir() and not p.is_symlink():
            return Check("workspace", "Workspace", PASSED, "managed directory present")
        return Check("workspace", "Workspace", FAILED, f"managed workspace directory missing: {p}",
                     "Restore it from a backup (opencode-sandbox backup list) or delete the environment")
    except c.SandboxError as exc:
        return Check("workspace", "Workspace", FAILED, str(exc))


def image_check(m, state):
    from . import opencode_versions as v
    image = c.env_image(m)
    if c.docker("image", "inspect", image, capture=True, check=False).returncode:
        if state is None:
            return Check("image", "Image", FAILED, f"{image} missing: the next start cannot create the container",
                         f"opencode-sandbox build --distro {m['distro']}" if not m.get("image") and m.get("distro") else None)
        return Check("image", "Image", WARNING, f"{image} missing: the container cannot be recreated from it")
    if state is None:
        try:
            v.check_pin(m)
        except c.SandboxError as exc:
            return Check("image", "Image", FAILED, str(exc))
    return Check("image", "Image", PASSED, image)


def container_check(m, state):
    if state is None:
        return Check("container", "Container", NOT_APPLICABLE, f"not created yet; the next start creates it from {c.env_image(m)}")
    if state.get("Dead") or state.get("OOMKilled"):
        return Check("container", "Container", FAILED, f"Docker reports {'dead' if state.get('Dead') else 'OOM-killed'}",
                     f"opencode-sandbox repair {m['name']}")
    return Check("container", "Container", PASSED, f"{c.cname(m)} {'running' if state.get('Running') else 'stopped'}")


def volume_check(m, state):
    v = c.volume_state(m)
    if v is None:
        if state is None:
            return Check("volume", "Home volume", NOT_APPLICABLE, f"{c.volume(m)} not created yet (created at the next start)")
        return Check("volume", "Home volume", FAILED, f"{c.volume(m)} missing although the container exists")
    if (v.get("Labels") or {}).get("org.opencode-sandbox.id") != m["id"]:
        return Check("volume", "Home volume", FAILED, f"{c.volume(m)} exists but does not belong to this environment "
                     "(no matching label); start and other operations refuse it",
                     "Rename or remove that volume yourself after checking its contents")
    return Check("volume", "Home volume", PASSED, f"{c.volume(m)}, owned")


def _observed_ports(data):
    out = set()
    for key, bindings in ((data.get("HostConfig") or {}).get("PortBindings") or {}).items():
        port, _, proto = key.partition("/")
        for b in bindings or ():
            if str(b.get("HostPort", "")).isdigit() and port.isdigit():
                out.add((b.get("HostIp") or "0.0.0.0", int(b["HostPort"]), int(port), proto or "tcp"))
    return out


def runtime_check(m, state):
    if state is None:
        return Check("runtime", "Resource limits", NOT_APPLICABLE, "no container; the configuration applies when it is created")
    observed, configured = c.observed_runtime(m), c.runtime_settings(m)
    differs = [f"{k} {configured[k]} (container: {observed[k]})" for k in ("cpus", "memory", "pids")
               if str(observed[k]) != str(configured[k])]
    if differs:
        return Check("runtime", "Resource limits", WARNING, "configured " + ", ".join(differs), _recreate_hint(m))
    return Check("runtime", "Resource limits", PASSED,
                 f"container configuration matches: CPUs {configured['cpus']}, memory {configured['memory']}, "
                 f"processes {configured['pids']}; kernel enforcement not measured")


def network_check(m, data):
    configured = c.runtime_settings(m)["network"]
    if data is None:
        return Check("network", "Network mode", NOT_APPLICABLE, f"configured {configured}; applies when the container is created")
    actual = (data.get("HostConfig") or {}).get("NetworkMode")
    if actual != configured:
        return Check("network", "Network mode", WARNING, f"configured {configured}, but the container runs with {actual}",
                     _recreate_hint(m))
    return Check("network", "Network mode", PASSED, f"{actual} (configured and actual)")


def _listeners(text, port, proto):
    """Local addresses bound to `port` in /proc/net/{tcp,tcp6,udp,udp6} contents (tcp: LISTEN)."""
    found = set()
    for line in text.splitlines():
        f = line.split()
        if len(f) < 4 or ":" not in f[1]:
            continue
        address, _, hexport = f[1].rpartition(":")
        try:
            if int(hexport, 16) != port:
                continue
        except ValueError:
            continue
        kind = f[-1] if f[-1] in ("tcp", "udp") else None
        if kind != proto or (proto == "tcp" and f[3] != "0A"):
            continue
        found.add("loopback" if address in ("0100007F", "00000000000000000000000001000000") else "any")
    return found


def ports_check(m, state, data):
    configured = {(p["host"], p["container"], p["protocol"]) for p in c.runtime_settings(m)["ports"]}
    if data is None:
        if not configured:
            return Check("ports", "Published ports", NOT_APPLICABLE, "none configured")
        return Check("ports", "Published ports", NOT_APPLICABLE, "no container; published when it is created")
    observed = _observed_ports(data)
    actual = {(h, cp, proto) for _, h, cp, proto in observed}
    if not configured and not observed:
        return Check("ports", "Published ports", NOT_APPLICABLE, "none configured")
    if actual != configured or any(ip != "127.0.0.1" for ip, *_ in observed):
        shown = ", ".join(f"{ip}:{h}->{cp}/{p}" for ip, h, cp, p in sorted(observed)) or "none"
        return Check("ports", "Published ports", WARNING, f"configured {_ports_text(configured) or 'none'}, container publishes {shown}",
                     _recreate_hint(m))
    lines = [f"host 127.0.0.1:{h} -> container {cp}/{p} (this host only; other machines cannot connect)"
             for h, cp, p in sorted(configured)]
    status, hint = PASSED, None
    if state.get("Running"):
        tables = _exec(m, "sh", "-c", "for f in tcp tcp6 udp udp6; do sed \"s/\\$/ ${f%6}/\" /proc/net/$f 2>/dev/null; done")
        if tables.returncode == 0:
            for i, (_h, cp, p) in enumerate(sorted(configured)):
                bound = _listeners(tables.stdout, cp, p)
                if bound == {"loopback"}:
                    lines[i] += f"; a server listens on 127.0.0.1:{cp} only, which the published port cannot reach"
                    status, hint = WARNING, "Make the server in the container listen on 0.0.0.0"
                elif bound:
                    lines[i] += f"; a server listens on {cp}"
                else:
                    lines[i] += f"; nothing listens on {cp} in the container yet"
        else:
            lines.append("listening sockets in the container not readable")
    return Check("ports", "Published ports", status, "; ".join(lines), hint)


def _ports_text(ports):
    return ", ".join(f"{h}:{cp}/{p}" for h, cp, p in sorted(ports))


def reachability_check(m, state, data, *, flags=..., address=..., gateway=...):
    """Measure from inside the running container; statements say only what was measured."""
    title = "Network reachability (measured)"
    if data is None:
        return Check("reachability", title, NOT_CHECKED, "no container")
    if not state.get("Running"):
        return Check("reachability", title, NOT_CHECKED, "container stopped; measured only in a running container",
                     f"opencode-sandbox start {m['name']}, then run the check again")
    flags = rootlesskit_flags() if flags is ... else flags
    address = host_address() if address is ... else address
    gateway = host_gateway() if gateway is ... else gateway
    actual = (data.get("HostConfig") or {}).get("NetworkMode")
    loopback_known = flags is None or flags.get("net") == "slirp4netns"
    with LoopbackListener() as listener:
        spec = {"internet": list(INTERNET)}
        if loopback_known:
            spec["host-loopback"] = [SLIRP_HOST, listener.port, listener.token]
        if address:
            # The listener is bound to 127.0.0.1 only: this port is closed on the LAN address.
            spec["host-lan"] = [address, listener.port]
        if gateway:
            spec["lan-gateway"] = [gateway, 9]
        p = _exec(m, "python3", "-c", PROBE, json.dumps(spec))
    reached_loopback = listener.reached  # after __exit__: connections still in the backlog are read
    if p.returncode:
        return Check("reachability", title, NOT_CHECKED,
                     f"probe could not run in the container (needs python3; exit {p.returncode})")
    try:
        result = json.loads(p.stdout.strip().splitlines()[-1])
        if not isinstance(result, dict) or not all(isinstance(v, str) for v in result.values()):
            raise ValueError
    except (ValueError, IndexError):
        return Check("reachability", title, NOT_CHECKED, "probe returned no valid result")
    lines, problems = [], []
    internet = result.get("internet")
    if internet == "verified":
        lines.append(f"internet: reachable (verified TLS handshake with {INTERNET[0]})")
    else:
        lines.append(f"internet: not reachable ({INTERNET[0]}: {internet})")
    if not loopback_known:
        lines.append(f"host 127.0.0.1 services: not checked (rootless network driver {flags.get('net')})")
    elif reached_loopback:
        lines.append("host 127.0.0.1 services: REACHABLE (a test listener on the host's 127.0.0.1 received the connection)")
        problems.append("host loopback")
    else:
        lines.append(f"host 127.0.0.1 services: not reachable ({SLIRP_HOST}: {result.get('host-loopback')}"
                     + ("; rootlesskit --disable-host-loopback" if flags and flags.get("disable_host_loopback") else "") + ")")
    lan = result.get("host-lan")
    if address is None:
        lines.append("host LAN address: not checked (none found)")
    elif lan in REACHED:
        lines.append(f"host LAN address {address}: reachable (the host answered) — host services listening on "
                     f"0.0.0.0 or {address} are reachable from this container")
    else:
        lines.append(f"host LAN address {address}: not reachable ({lan})")
    lan_gw = result.get("lan-gateway")
    if gateway is None:
        lines.append("LAN gateway: not checked (no default route)")
    elif lan_gw in REACHED:
        lines.append(f"LAN gateway {gateway}: answered — other machines on the host's networks are likely reachable")
    else:
        lines.append(f"LAN gateway {gateway}: no answer ({lan_gw})")
    lines.append("measured by a process in the container; a process there could influence the result "
                 "(the host 127.0.0.1 result is observed on the host)")
    detail = "; ".join(lines)
    if actual == "none":
        leaked = [k for k in ("host-lan", "lan-gateway") if result.get(k) in REACHED]
        if internet == "verified" or reached_loopback or leaked:
            return Check("reachability", title, FAILED, "network none, but something was reachable: " + detail)
        return Check("reachability", title, PASSED, "no network: nothing outside the container was reachable; " + detail)
    if internet != "verified":
        problems.append("internet")
    if problems:
        hint = ("Model providers and OpenCode updates need the internet" if "internet" in problems else
                "Host services on 127.0.0.1 are reachable from the agent; configure rootlesskit with --disable-host-loopback")
        return Check("reachability", title, WARNING, detail, hint)
    return Check("reachability", title, PASSED, "not isolated from the LAN; " + detail)


def profile_check(m, state, data):
    title, name = "Provider profile", m.get("profile", "default")
    try:
        values = c.profile_read(name)
    except c.SandboxError as exc:
        return Check("profile", title, FAILED, f"profile '{name}': {exc}", "opencode-sandbox providers --help")
    path = c.profile_path(name)
    detail = f"'{name}': {len(values)} variable(s)" if path.exists() else f"'{name}': no profile file (no provider variables)"
    if not path.exists() and name != "default":
        return Check("profile", title, WARNING, f"assigned profile '{name}' does not exist", f"opencode-sandbox providers set {name} --key VARIABLE")
    if data is None:
        return Check("profile", title, PASSED, detail)
    mismatch = c.profile_mismatch(m)
    if mismatch:
        return Check("profile", title, WARNING, mismatch)
    if state.get("Running") and path.exists():
        # The profile is a single-file bind mount; profile_set replaces the file
        # (new inode), the running container keeps the old one until it is restarted.
        p = _exec(m, "stat", "-c", "%i", c.PROFILE_TARGET)
        inode = p.stdout.strip() if p.returncode == 0 else ""
        if inode.isdigit() and int(inode) != path.stat().st_ino:
            return Check("profile", title, WARNING, detail + "; changed after the container started: OpenCode in this "
                         "container still gets the previous values",
                         f"Restart to apply: opencode-sandbox stop {m['name']} && opencode-sandbox start {m['name']}")
        if not inode.isdigit():
            detail += "; mounted file not compared (stat unavailable)"
    return Check("profile", title, PASSED, detail)


def agent_context_check(m, *, observe=True):
    from . import agent_context as ac
    try:
        inputs = c.guidance_inputs(m, observe=observe)
    except c.SandboxError:
        inputs = c.guidance_inputs(m, observe=False)
    if ac.verify(m, c.env_dir, **inputs):
        return Check("agent-context", "Agent Context file", PASSED, "current")
    return Check("agent-context", "Agent Context file", WARNING, "missing or outdated on disk (run regenerates it before every launch)",
                 f"opencode-sandbox agent-context refresh {m['name']}")


def delivery_check(m, state):
    from . import agent_context as ac
    title = "Agent Context delivery"
    if state is None or not state.get("Running"):
        return Check("agent-context-delivery", title, NOT_CHECKED, "container not running")
    p = _exec(m, "cat", ac.SYSTEM_CONFIG)
    if p.returncode != 0 or ac.CONTAINER_PATH not in p.stdout:
        return Check("agent-context-delivery", title, FAILED,
                     f"{ac.SYSTEM_CONFIG} {'does not list' if p.returncode == 0 else 'is missing or unreadable; it does not list'} "
                     f"{ac.CONTAINER_PATH}: OpenCode will not receive the Agent Context in this image")
    # The configuration and the mounted file are checked; whether OpenCode reads it is not observed
    # here (the real first-prompt test does that, CAMPAIGN G04).
    try:
        host = ac.path(m, c.env_dir).read_text(encoding="utf-8")
    except OSError:
        return Check("agent-context-delivery", title, WARNING,
                     f"configured ({ac.SYSTEM_CONFIG} lists {ac.CONTAINER_PATH}); the file is not written yet, so the "
                     "mount is not compared (run writes it before every launch)")
    mounted = _exec(m, "cat", ac.CONTAINER_PATH)
    if mounted.returncode != 0:
        return Check("agent-context-delivery", title, FAILED,
                     f"{ac.CONTAINER_PATH} is not readable in the container (the mount is missing)", _recreate_hint(m))
    if mounted.stdout != host:
        return Check("agent-context-delivery", title, WARNING,
                     f"{ac.CONTAINER_PATH} in the container differs from the host file (the mount shows another directory)",
                     _recreate_hint(m))
    return Check("agent-context-delivery", title, PASSED,
                 f"configured: {ac.SYSTEM_CONFIG} lists {ac.CONTAINER_PATH}, and the mounted file matches the host file")


def opencode_check(m, state, data):
    from . import opencode_versions as v
    title = "OpenCode"
    if state is None or not state.get("Running"):
        return Check("opencode", title, NOT_CHECKED, "container not running")
    item = {"state": "running", "policy": v.policy(m), **v.environment_version(m)}
    line = v.environment_line(item)
    env = (data.get("Config") or {}).get("Env") or []
    if item["version"] is None:
        if m.get("distro") is None:
            return Check("opencode", title, FAILED, "`opencode --version` failed in the container (custom image without a working OpenCode)",
                         "Use an image with OpenCode 2.x, or a registry distribution")
        return Check("opencode", title, FAILED, line, f"opencode-sandbox stop {m['name']} && opencode-sandbox opencode update {m['name']}")
    if v.SELF_UPDATE_ENV not in env:
        return Check("opencode", title, WARNING, f"{line}; OpenCode's own self-update is not disabled in this container", _recreate_hint(m))
    if "changed outside the manager" in line:
        return Check("opencode", title, WARNING, line,
                     f"opencode-sandbox stop {m['name']} && opencode-sandbox opencode update {m['name']} --version {item['policy']['version']}")
    return Check("opencode", title, PASSED, line + "; self-update off")


TITLES = {"daemon": "Docker daemon", "resource-support": "Resource-limit support", "workspace": "Workspace", "operation": "Pending operation", "image": "Image",
          "container": "Container", "volume": "Home volume", "runtime": "Resource limits", "network": "Network mode",
          "ports": "Published ports", "reachability": "Network reachability (measured)", "profile": "Provider profile",
          "agent-context": "Agent Context file", "agent-context-delivery": "Agent Context delivery", "opencode": "OpenCode",
          "storage": "Docker storage"}


def _skipped(ids, why):
    return [Check(i, TITLES[i], NOT_CHECKED, why) for i in ids]


def _guard(fn, *args, **kwargs):
    check_id = kwargs.pop("_id")
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — one failing check must not hide the others
        return Check(check_id, TITLES.get(check_id, check_id), NOT_CHECKED, f"check could not run: {str(exc)[:300]}")


def environment_checks(m):
    m = c.resolve(m["id"])
    out = [_guard(daemon_check, _id="daemon")]
    docker = out[0].status == PASSED
    out.append(_guard(workspace_check, m, _id="workspace"))
    if not docker:
        out.append(_guard(operation_check, m, ..., _id="operation"))
        out += _skipped(("resource-support", "image", "container", "volume", "runtime", "network", "ports", "reachability", "profile"),
                        "Docker daemon not verified")
        out.append(_guard(agent_context_check, m, observe=False, _id="agent-context"))
        out += _skipped(("agent-context-delivery", "opencode", "storage"), "Docker daemon not verified")
        return out
    out.append(_guard(resource_support_check, _id="resource-support"))
    try:
        state, data = _inspect(m)
    except c.SandboxError as exc:
        # E.g. a container with this name that is not the environment's: report the rest anyway.
        out += [_guard(operation_check, m, ..., _id="operation"),
                _guard(image_check, m, ..., _id="image"),
                Check("container", "Container", FAILED, str(exc)),
                _guard(volume_check, m, None, _id="volume"),
                *_skipped(("runtime", "network", "ports", "reachability"), "container not inspected"),
                _guard(profile_check, m, None, None, _id="profile"),
                _guard(agent_context_check, m, observe=False, _id="agent-context"),
                *_skipped(("agent-context-delivery", "opencode"), "container not inspected"),
                _guard(storage_check, _id="storage")]
        return out
    out += [_guard(operation_check, m, state, _id="operation"),
            _guard(image_check, m, state, _id="image"),
            _guard(container_check, m, state, _id="container"),
            _guard(volume_check, m, state, _id="volume"),
            _guard(runtime_check, m, state, _id="runtime"),
            _guard(network_check, m, data, _id="network"),
            _guard(ports_check, m, state, data, _id="ports"),
            _guard(reachability_check, m, state, data, _id="reachability"),
            _guard(profile_check, m, state, data, _id="profile"),
            _guard(agent_context_check, m, _id="agent-context"),
            _guard(delivery_check, m, state, _id="agent-context-delivery"),
            _guard(opencode_check, m, state, data, _id="opencode"),
            _guard(storage_check, _id="storage")]
    return out


def run(m):
    """Run every check for one environment and cache the report; read-only otherwise."""
    from . import __version__
    report = {"schema": SCHEMA, "environment": m["id"], "at": c.now(), "manager_version": __version__,
              "checks": [asdict(x) for x in environment_checks(m)]}
    _save(m, report)
    return report


def _save(m, report):
    d = c.env_dir(m["id"])
    if not d.is_dir():
        return
    fd, tmp = tempfile.mkstemp(prefix=".readiness-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump(report, f, indent=1)
        os.replace(tmp, d / CACHE)
    except OSError:
        Path(tmp).unlink(missing_ok=True)


def cached(m):
    """The last stored report, or None (missing, unreadable or from another environment)."""
    try:
        report = json.loads((c.env_dir(m["id"]) / CACHE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(report, dict) or report.get("schema") != SCHEMA or report.get("environment") != m["id"] \
            or not isinstance(report.get("checks"), list):
        return None
    return report


def counts(report):
    found = {s: 0 for s in ORDER}
    for check in report["checks"]:
        if isinstance(check, dict) and check.get("status") in found:
            found[check["status"]] += 1
    return found


def summary(report):
    n = counts(report)
    when = re.sub(r"\.\d+", "", str(report.get("at", "?"))).replace("T", " ").replace("+00:00", " UTC")
    return f"{when}: " + ", ".join(f"{n[s]} {s}" for s in ORDER if n[s] or s in (PASSED, WARNING, FAILED))


def failed(report):
    return counts(report)[FAILED] > 0


def format_report(report, width=14):
    lines = []
    for check in report["checks"]:
        lines.append(f"[{check['status']}]".ljust(width + 2) + f"{check['title']}: {check['detail']}")
        if check.get("hint") and check["status"] in (WARNING, FAILED, NOT_CHECKED):
            lines.append(" " * (width + 2) + f"-> {check['hint']}")
    return lines


def cached_line(m):
    report = cached(m)
    return f"last check {summary(report)}" if report else "not checked yet"


UNKNOWN = "unknown"


def network_lines(m, observed):
    """For `status`: configured versus actual mode, fixed facts about the mode (D-015) and the
    cached measurement, without probing. `observed`: c.observed_runtime(m), or UNKNOWN when
    Docker could not be asked."""
    configured = c.runtime_settings(m)
    lines = []
    if observed == UNKNOWN:
        lines.append(f"Network: {configured['network']} (configured; container not inspected)")
        actual = configured["network"]
    elif observed is None:
        lines.append(f"Network: {configured['network']} (configured; no container yet)")
        actual = configured["network"]
    else:
        actual = observed["network"]
        if actual == configured["network"]:
            lines.append(f"Network: {actual}")
        else:
            lines.append(f"Network: configured {configured['network']}, container runs with {actual} — {_recreate_hint(m)}")
    if actual == "none":
        lines.append("  no network: model provider APIs, package downloads and OpenCode updates are unavailable")
    else:
        lines.append("  bridge is NOT isolation from the LAN or the internet")
    for p in configured["ports"] if actual != "none" else ():
        lines.append(f"  published: host 127.0.0.1:{p['host']} -> container {p['container']}/{p['protocol']} (this host only)")
    report = cached(m)
    measured = next((x for x in (report or {}).get("checks", []) if isinstance(x, dict) and x.get("id") == "reachability"), None)
    if measured and measured.get("status") not in (NOT_CHECKED, NOT_APPLICABLE):
        lines.append(f"  measured {summary(report).split(': ')[0]}: {measured['detail']}")
    else:
        lines.append(f"  reachability not measured; run: opencode-sandbox check {m['name']} (container running)")
    return lines
