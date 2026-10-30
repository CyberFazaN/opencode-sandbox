"""Persistent environment metadata and Docker orchestration; no shell=True."""
from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import re
import secrets
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import termios
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from . import distros, runtime_identity

APP = "opencode-sandbox"
BASE = Path(os.getenv("OPENCODE_SANDBOX_HOME", Path.home()/".local/share"/APP)).expanduser()
CONFIG = Path(os.getenv("OPENCODE_SANDBOX_CONFIG", Path.home()/".config"/APP)).expanduser()
CONTEXT = os.getenv("OPENCODE_SANDBOX_DOCKER_CONTEXT", "rootless")
# Schema 2 (never released without them) includes `distro`: a registry id, or null for an
# environment created from a custom image (`image` set at creation), see D-016; and
# `workspace`: {mode: managed|direct, path}, see D-012 and workspaces.py.
METADATA_SCHEMA = 2
_IMAGE_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,254}")

class SandboxError(RuntimeError): pass

class PrerequisiteError(SandboxError):
    """A host prerequisite is not met (Docker daemon, Docker CLI, Git); `exit_code` follows the
    daemon identity classification (runtime_identity.EXIT_CODES), so scripts can tell why."""
    def __init__(self, message, exit_code):
        super().__init__(message)
        self.exit_code = exit_code

# What to do when a program the manager runs on the host is not installed.
PROGRAM_HINTS = {"git": "Install Git from your distribution's packages (Arch Linux: pacman -S git); it is "
                        "needed for project imports from Git and for change review and transfer.",
                 "docker": runtime_identity.HINTS[runtime_identity.MISSING]}

def missing_program(name):
    hint = PROGRAM_HINTS.get(name, "Install it and make sure it is on PATH.")
    return PrerequisiteError(f"Required executable not found: {name}. {hint}",
                             runtime_identity.EXIT_CODES[runtime_identity.MISSING])

def error_text(exc):
    """How a caught error is reported to the user: the manager's own errors by their message,
    any other error also by its type (a bare KeyError message is only a quoted key)."""
    if isinstance(exc, SandboxError): return str(exc)
    return f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__

DATA_LABEL = "org.opencode-sandbox.data-dir"

def data_id():
    """Identifies this data directory on a shared daemon (D-011): environments of another
    OPENCODE_SANDBOX_HOME are not orphans of this one."""
    return hashlib.sha256(os.fsencode(str(BASE.resolve()))).hexdigest()[:16]

def labels(owner=None, *, scoped=True):
    """`--label` arguments marking a Docker object as created by this manager; `scoped` adds the
    data-directory label (everything except base images, which every data directory shares)."""
    from . import __version__
    args=["--label","org.opencode-sandbox.managed=true","--label",f"org.opencode-sandbox.manager-version={__version__}"]
    if scoped: args += ["--label",f"{DATA_LABEL}={data_id()}"]
    if owner is not None: args += ["--label",f"org.opencode-sandbox.id={owner}"]
    return args

HELPER_LABEL = "org.opencode-sandbox.helper"

def helper_labels(purpose):
    """Labels of a short-lived `--rm` helper container. Containers inherit their image's labels,
    so only this container label tells the manager's helpers from other containers created from
    a manager image (cleanup, D-011)."""
    return [*labels(),"--label",f"{HELPER_LABEL}={purpose}"]

def require_program(name):
    """Before an operation that needs a host program: fail early with what to install."""
    if shutil.which(name) is None: raise missing_program(name)

def run_program(argv, *, check=False, **kwargs):
    """subprocess.run for a host program; a missing program is a PrerequisiteError with a hint."""
    try:
        return subprocess.run(argv, check=check, **kwargs)
    except FileNotFoundError as exc:
        raise missing_program(os.path.basename(str(argv[0]))) from exc

def call(argv, *, capture=False, check=True, cwd=None, env=None):
    try:
        p = subprocess.run([str(x) for x in argv], cwd=cwd, env=env, text=True, capture_output=capture, check=False)
    except FileNotFoundError as exc:
        raise missing_program(os.path.basename(str(argv[0]))) from exc
    except OSError as exc:
        raise SandboxError(f"Cannot execute {argv[0]}: {exc}") from exc
    if check and p.returncode:
        # Name the real operation (e.g. "docker run"), not just the global options.
        words=[str(x) for x in argv[:1]]+[str(x) for x in argv[1:] if not str(x).startswith("-")][:2]
        if words[0]=="docker" and len(argv)>3 and argv[1]=="-H": words=["docker",str(argv[3])]
        raise SandboxError(f"Command failed ({p.returncode}): {' '.join(words)}\n{p.stderr if capture else ''}")
    return p

# The context is resolved to its unix:// endpoint once per process (D-003); later context
# edits cannot redirect an already verified manager to another daemon.
_ENDPOINT = None
_RUNTIME_LOCK = threading.Lock()
_RUNTIME_GENERATION = 0
_RUNTIME_LAST = None
_RUNTIME_FEEDBACK = ContextVar("runtime_feedback", default=None)

def _runtime_progress(message):
    if message: print(message, file=sys.stderr, flush=True)

@contextmanager
def runtime_feedback(*, progress=_runtime_progress, cancelled=None, timeout=runtime_identity.READINESS_TIMEOUT):
    """Scoped CLI/worker feedback; never installs process-wide UI callbacks."""
    token = _RUNTIME_FEEDBACK.set({"progress": progress, "cancelled": cancelled, "timeout": timeout})
    try: yield
    finally: _RUNTIME_FEEDBACK.reset(token)

def verify_runtime(strict=True):
    """Verify the daemon identity (D-003); return the Identity, raising unless verified when strict."""
    global _ENDPOINT, _RUNTIME_GENERATION, _RUNTIME_LAST
    budget = runtime_identity.Budget(**(_RUNTIME_FEEDBACK.get() or {"progress": _runtime_progress}))
    generation = _RUNTIME_GENERATION
    acquired = False
    try:
        while not _RUNTIME_LOCK.acquire(blocking=False):
            budget.pause(0.05)
        acquired = True
        budget.remaining()
        if generation != _RUNTIME_GENERATION:
            ident = _RUNTIME_LAST  # overlapping callers share only this completed acquisition
        else:
            ident = runtime_identity.verify(CONTEXT, endpoint=_ENDPOINT, budget=budget)
            if budget.cancelled and budget.cancelled(): raise runtime_identity.Cancelled()
            if ident.verified:
                budget.remaining()  # a canceled/expired preflight must not permit mutation
                _ENDPOINT = ident.endpoint
            _RUNTIME_LAST = ident
            _RUNTIME_GENERATION += 1
    except runtime_identity.Deadline as exc:
        ident = runtime_identity.Identity(runtime_identity.UNAVAILABLE, CONTEXT, _ENDPOINT, reasons=(str(exc),))
    finally:
        if acquired: _RUNTIME_LOCK.release()
        if budget.notified and budget.progress: budget.progress(None)
    if not ident.verified and strict: raise PrerequisiteError(ident.message(), runtime_identity.EXIT_CODES[ident.classification])
    return ident

def docker_endpoint():
    if _ENDPOINT is None: verify_runtime()
    return _ENDPOINT

def docker(*args, capture=False, check=True):
    return call(["docker", "-H", docker_endpoint(), *args], capture=capture, check=check, env=runtime_identity.docker_env())

def docker_info():
    """Fresh read-only daemon evidence on the pinned endpoint; bounded/cancellable, no replay.

    Never expose the raw response/error: info can contain proxy URLs and other host details.
    """
    endpoint = docker_endpoint()
    feedback = _RUNTIME_FEEDBACK.get() or {}
    budget = runtime_identity.Budget(5, cancelled=feedback.get("cancelled"))
    try:
        out, error = runtime_identity._docker(["-H", endpoint, "info", "--format", "{{json .}}"], budget=budget)
    except runtime_identity.Deadline as exc:
        raise SandboxError("Docker info query exceeded the 5-second diagnostic budget") from exc
    if error: raise SandboxError("Docker info query failed; check daemon status/logs and rerun doctor")
    try:
        info = json.loads(out)
    except (ValueError, TypeError, RecursionError) as exc:
        raise SandboxError("Docker info query returned invalid JSON") from exc
    if not isinstance(info, dict): raise SandboxError("Docker info query returned invalid data (expected an object)")
    return info

def docker_cli():
    """Shell-ready docker prefix for hints shown to the user."""
    return f"docker -H {shlex.quote(_ENDPOINT)}" if _ENDPOINT else f"docker --context {shlex.quote(CONTEXT)}"

def ensure_runtime(distro=None):
    """Verify the daemon; with a registry Distro also require its base image."""
    verify_runtime()
    if distro and docker("image", "inspect", distro.image, capture=True, check=False).returncode:
        raise SandboxError(f"Image {distro.image} missing. Run: opencode-sandbox build --distro {distro.id}")

def env_distro(m):
    """The environment's registry distribution, or None for a custom image."""
    return distros.get(m["distro"]) if m.get("distro") is not None else None

def env_image(m):
    """The image the environment's container is (re)created from."""
    return m.get("image") or env_distro(m).image

def custom_image(m):
    """The image a custom-image environment was created from, or None for a registry
    distribution. `image` changes to derived images (recreate, reconfiguration, restore); this
    does not."""
    if m.get("distro") is not None: return None
    if m.get("custom_image"): return m["custom_image"]
    image=m.get("image")  # metadata written before custom_image existed
    return None if image and image.split(":",1)[0] in MANAGER_IMAGE_KINDS else image

def init_dirs():
    """The data and configuration directories are made private when the manager creates them;
    an existing directory chosen with OPENCODE_SANDBOX_HOME/_CONFIG keeps its permissions. The
    manager's own subdirectories are always 0700."""
    for p in (BASE, CONFIG):
        if not p.exists():
            p.mkdir(parents=True)
            p.chmod(0o700)
    for p in (BASE/"environments", BASE/"exports", BASE/"locks", CONFIG/"profiles"):
        p.mkdir(parents=True,exist_ok=True)
        p.chmod(0o700)

@contextmanager
def lock(key, timeout=30.0):
    """Cross-process advisory lock with bounded waiting; all mutations use it."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", key):
        raise SandboxError("Invalid lock key")
    init_dirs()
    with (BASE/"locks"/(key+".lock")).open("a+") as f:
        deadline=time.monotonic()+timeout
        while True:
            try:
                fcntl.flock(f,fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SandboxError(f"Environment busy: {key} (lock timeout)")
                time.sleep(0.05)
        try: yield
        finally: fcntl.flock(f,fcntl.LOCK_UN)

def now(): return datetime.now(UTC).isoformat()

def printable(text):
    """Text derived from workspace content, for the terminal: control and format characters are
    escaped (newline and tab kept), so the content cannot hide or rewrite other output."""
    return "".join(ch if ch.isprintable() or ch in "\n\t" else ch.encode("unicode_escape").decode() for ch in text)

def safe_name(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}",name):
        raise SandboxError("Name must be 1-64 letters, digits, dot, underscore or dash")
    return name

def env_dir(eid):
    if not re.fullmatch(r"[0-9a-f]{16}",eid): raise SandboxError("Invalid environment id")
    return BASE/"environments"/eid

def save(m):
    """Atomic, durable metadata replacement; caller holds environment lock for mutations."""
    d=env_dir(m["id"]); d.mkdir(parents=True,exist_ok=True)
    fd, name=tempfile.mkstemp(prefix=".metadata-",dir=d)
    try:
        with os.fdopen(fd,"w") as f:
            os.fchmod(f.fileno(),0o600)
            json.dump(m,f,indent=2,ensure_ascii=False)
            f.flush(); os.fsync(f.fileno())
        os.replace(name,d/"metadata.json")
        directory_fd=os.open(d,os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory_fd)
        finally: os.close(directory_fd)
    finally:
        if os.path.exists(name): os.unlink(name)

def mark(m, state, **fields):
    m.update(fields)
    m["status"]=state
    m["updated"]=now()
    save(m)


def _read_metadata(p):
    """Return (metadata, None) if well-formed, of the current schema and its id matches
    its directory (no spoofing); otherwise (None, reason)."""
    try: m=json.loads(p.read_text())
    except (ValueError,OSError,UnicodeError): return None, "unreadable or invalid JSON"
    if (not isinstance(m,dict) or m.get("id")!=p.parent.name or not re.fullmatch(r"[0-9a-f]{16}",p.parent.name)
            or not isinstance(m.get("name"),str) or not isinstance(m.get("kind"),str)
            or not isinstance(m.get("created",""),str)):
        return None, "malformed metadata"
    if m.get("schema")!=METADATA_SCHEMA:
        # Other schemas are not migrated and never modified (D-002).
        return None, (f"metadata schema {m.get('schema')!r} is not supported (expected {METADATA_SCHEMA}); "
                      "this environment is not managed by this version and is left unchanged")
    if "distro" not in m:
        return None, "metadata has no distribution (written by a pre-release build)"
    if m["distro"] is None:
        if not isinstance(m.get("image"),str): return None, "custom-image environment without an image"
    elif m["distro"] not in distros.REGISTRY:
        return None, f"unknown distribution {m['distro']!r}"
    from . import workspaces
    try: workspaces.info(m)
    except SandboxError: return None, "missing or invalid workspace record"
    return m, None

def _load_metadata(p):
    return _read_metadata(p)[0]

def metadata_error(p):
    """Why all_envs() ignores this metadata file, or None if it is valid."""
    return _read_metadata(p)[1]

def all_envs():
    init_dirs(); out=[]
    for p in (BASE/"environments").glob("*/metadata.json"):
        m=_load_metadata(p)
        if m is not None: out.append(m)
    return sorted(out,key=lambda x:x.get("created",""),reverse=True)

def invalid_metadata():
    """Metadata files ignored by all_envs(); reported, never modified or deleted."""
    init_dirs()
    return sorted(p for p in (BASE/"environments").glob("*/metadata.json") if _load_metadata(p) is None)

MIN_ID_PREFIX = 6

def resolve(key):
    """The environment with this exact id, else this exact name, else the only one whose id
    starts with `key` (at least MIN_ID_PREFIX hex characters). An empty, short or stale key never
    selects some other environment."""
    if not isinstance(key,str) or not key:
        raise SandboxError("Environment name or id is empty")
    if re.fullmatch(r"[0-9a-f]{16}",key) and (BASE/"environments"/key/"metadata.json").is_file():
        m=_load_metadata(BASE/"environments"/key/"metadata.json")
        if m is not None: return m
    envs=all_envs()
    named=[m for m in envs if m["name"]==key]
    if len(named)==1: return named[0]
    matches=named or ([m for m in envs if m["id"].startswith(key)]
                      if re.fullmatch(rf"[0-9a-f]{{{MIN_ID_PREFIX},15}}",key) else [])
    if len(matches)!=1: raise SandboxError(f"Environment {key!r}: {'not found' if not matches else 'ambiguous; use ID'}")
    return matches[0]

def check_new_name(name):
    """A valid name that cannot be mistaken for another environment's id."""
    safe_name(name)
    if re.fullmatch(r"[0-9a-f]{16}",name):
        raise SandboxError(f"Name {name!r} looks like an environment id; choose another name")
    return name

def current_env(path=None):
    """The environment imported from, or directly mounting, this directory (or a parent)."""
    from . import workspaces
    p=Path(path or Path.cwd()).resolve()
    def origin(m): return m["workspace"]["path"] if workspaces.is_direct(m) else m.get("source")
    matches=[m for m in all_envs() if origin(m) and (p==Path(origin(m)) or Path(origin(m)) in p.parents)]
    if not matches: return None
    return max(matches,key=lambda m:len(origin(m)))

def host_cpus():
    return os.cpu_count() or 1

def default_cpus():
    """8 CPUs, or fewer on smaller hosts: Docker rejects --cpus above the host count."""
    return str(min(8, host_cpus()))

# Container settings are persisted per environment; config_plan.py decides how a change
# reaches an existing container. Docker bridge networking is not a security boundary.
def validate_runtime_settings(settings):
    if not isinstance(settings, dict): raise SandboxError("Runtime settings must be an object")
    if set(settings) - {"cpus", "memory", "pids", "network", "ports"}:
        raise SandboxError("Unknown runtime setting")
    cpus = settings.get("cpus", default_cpus())
    try: cpu = float(cpus)
    except (TypeError, ValueError): raise SandboxError("CPU limit must be numeric")
    if not 0.1 <= cpu <= 256: raise SandboxError("CPU limit must be between 0.1 and 256")
    memory = str(settings.get("memory", "16g")).lower()
    if not re.fullmatch(r"[1-9][0-9]*(?:[kmg])?", memory): raise SandboxError("Invalid memory limit")
    pids = settings.get("pids", 2048)
    if isinstance(pids, bool) or not str(pids).isdigit() or not 32 <= int(pids) <= 1048576:
        raise SandboxError("PIDs limit must be 32..1048576")
    network = settings.get("network", "bridge")
    if network not in ("bridge", "none"):
        raise SandboxError("Only bridge or none networking is supported")
    ports = settings.get("ports", [])
    if not isinstance(ports, list) or len(ports) > 32: raise SandboxError("Expected at most 32 port mappings")
    seen=set(); cleaned=[]
    for item in ports:
        if not isinstance(item, dict) or set(item) != {"host", "container", "protocol"}:
            raise SandboxError("Port must contain host, container and protocol")
        host, container, proto = item["host"], item["container"], item["protocol"]
        if isinstance(host, bool) or isinstance(container, bool) or not str(host).isdigit() or not str(container).isdigit():
            raise SandboxError("Port numbers must be integers")
        host,container=int(host),int(container)
        if not 1024 <= host <= 65535 or not 1 <= container <= 65535 or proto not in ("tcp", "udp"):
            raise SandboxError("Invalid port mapping (host ports must be >=1024)")
        if (host,proto) in seen: raise SandboxError("Duplicate host port")
        seen.add((host,proto)); cleaned.append({"host":host,"container":container,"protocol":proto})
    if network == "none" and cleaned: raise SandboxError("Ports require bridge networking")
    return {"cpus":str(cpu),"memory":memory,"pids":int(pids),"network":network,"ports":cleaned}

def runtime_settings(m):
    return validate_runtime_settings(m.get("runtime", {}))

def port_conflicts(m, settings):
    """Detect declared reservations in other environments (not external processes)."""
    proposed={(p["host"], p["protocol"]) for p in validate_runtime_settings(settings)["ports"]}
    conflicts=[]
    for other in all_envs():
        if other["id"] == m["id"] or other.get("status") == "deleting": continue
        reserved={(p["host"],p["protocol"]) for p in runtime_settings(other)["ports"]}
        for port, proto in sorted(proposed & reserved):
            conflicts.append(f"{port}/{proto} reserved by {other['name']}")
    return conflicts

def runtime_usage(m):
    """Docker's one-shot stats; returns raw daemon values, never guessed metrics."""
    state=inspect_container(m)
    if state is None: return {"state":"missing"}
    if not state.get("Running"): return {"state":"stopped"}
    p=docker("stats","--no-stream","--format","{{json .}}",cname(m),capture=True)
    try: data=json.loads(p.stdout.strip().splitlines()[0])
    except (ValueError,IndexError) as exc: raise SandboxError("Invalid docker stats response") from exc
    return {"state":"running","cpu":data.get("CPUPerc"),"memory":data.get("MemUsage"),
            "memory_percent":data.get("MemPerc"),"network_io":data.get("NetIO"),
            "processes":data.get("PIDs")}

def reconfigure_runtime(m, settings, profile=None):
    """Replace a stopped container, retaining /root volume, workspace and committed layer.
    The recreate step of config_plan.apply(); `settings` is the complete target runtime and
    `profile` (when given) the provider profile the new container mounts.

    Crash recovery: metadata image and pending operation persist after image commit;
    on failure before removal the original container remains; after removal a
    retry of start() uses the committed image. A superseded ocs-runtime tag of
    this environment is untagged afterwards (its layers live on in the new image).
    """
    ensure_runtime(False)
    with lock(m["id"]):
        m=resolve(m["id"])
        settings=validate_runtime_settings({**runtime_settings(m), **settings})  # merged under the lock
        if m.get("operation"): raise pending_operation(m)
        if profile is not None: m["profile"]=profile
        conflicts=port_conflicts(m,settings)
        if conflicts: raise SandboxError("Port conflict: "+", ".join(conflicts))
        state=inspect_container(m)
        if state is None:
            m["runtime"]=settings; save(m)
            return {"image":env_image(m),"recreated":False}
        assert_volume_owned(m)
        was_running=bool(state.get("Running"))
        if was_running:
            raise SandboxError("Stop the environment before reconfiguration for a consistent snapshot")
        require_docker_space("runtime reconfiguration (docker commit)")
        superseded=m.get("image")
        tag=f"ocs-runtime:{m['id']}-{secrets.token_hex(6)}"
        docker("commit",cname(m),tag,capture=True)
        # Intent and image are durable before destructive removal.
        m["image"]=tag
        m["runtime"]=settings
        mark(m,"reconfiguring",operation="runtime-recreate",last_snapshot=tag,superseded_image=superseded)
        try:
            docker("rm",cname(m),capture=True)
        except Exception as exc:
            mark(m,"error",last_error=f"Reconfiguration: {exc}")
            raise
        _finish_reconfigure(m)
    # Do not auto-start: preserves the user's stopped state.
    return {"image":tag,"recreated":True}

def recover_runtime_reconfigure(m):
    """Complete a durable runtime-recreate intent, never removing an unowned container.

    The committed image and requested settings were saved before container removal.
    A stopped old container may remain if Docker rm failed or the process crashed.
    """
    ensure_runtime(False)
    with lock(m["id"]):
        m=resolve(m["id"])
        if m.get("operation") != "runtime-recreate":
            raise SandboxError("No interrupted runtime reconfiguration")
        if not m.get("image") or m.get("image") != m.get("last_snapshot"):
            raise SandboxError("Missing committed image reference; manual recovery required")
        if docker("image", "inspect", m["image"], capture=True, check=False).returncode:
            raise missing_image(m, m["image"], "opencode-sandbox config recover {name}")
        state=inspect_container(m)
        if state is not None:
            if state.get("Running"):
                raise SandboxError("Container is running; stop it before recovery")
            assert_volume_owned(m)
            docker("rm", cname(m), capture=True)
        _finish_reconfigure(m)
        return {"image":m["image"],"recovered":True}

def _finish_reconfigure(m):
    """Close the journal; untag this environment's superseded ocs-runtime image (its layers
    live on in the new one). Other tags (user snapshots, base images) are never touched."""
    superseded=m.pop("superseded_image",None)
    mark(m,"ready",operation=None,last_error=None)
    if superseded and superseded!=m["image"] and superseded.startswith(f"ocs-runtime:{m['id']}-"):
        from .cleanup import referenced_images
        if superseded not in referenced_images(all_envs()):  # never untag an image in use
            docker("image","rm",superseded,capture=True,check=False)


def _copy_untrusted(source, workspace):
    """No symlinks or hidden files by default; prevent accidental secret copying."""
    for item in source.iterdir():
        if item.name.startswith(".") or item.is_symlink() or item.name in ("node_modules","target","dist","build","__pycache__"):
            continue
        if item.is_dir():
            def ignore_untrusted(directory, names):
                parent = Path(directory)
                # Also skip FIFOs/sockets/devices: copying them hangs or fails.
                return {name for name in names if name.startswith(".") or name in ("node_modules", "__pycache__", "target", "dist", "build") or (parent / name).is_symlink()
                        or not ((parent / name).is_dir() or (parent / name).is_file())}
            shutil.copytree(item,workspace/item.name,symlinks=False,ignore=ignore_untrusted)
        elif item.is_file(): shutil.copy2(item,workspace/item.name)

KINDS = ("scratch", "project", "quick")

def creation_options(name, kind=None, source=None, *, distro=None, image=None, workspace_mode="managed", workspace=None):
    """The checks of `create` that need neither the file system nor Docker, shared by the CLI and
    the dashboard form. Returns (kind, distro id or None): without a kind, a copied source or
    a direct workspace makes a project, nothing an empty scratch environment."""
    from . import workspaces
    check_new_name(name)
    if kind is None:
        kind = "project" if source is not None or workspace_mode == workspaces.DIRECT else "scratch"
    if kind not in KINDS: raise SandboxError("Kind must be scratch, project or quick")
    if workspace_mode not in (workspaces.MANAGED, workspaces.DIRECT): raise SandboxError("Workspace mode must be managed or direct")
    if workspace_mode == workspaces.MANAGED:
        if workspace is not None:
            raise SandboxError("--workspace needs --workspace-mode direct; use --source to copy a directory")
        if kind == "scratch" and source is not None:
            raise SandboxError("A scratch environment starts empty; an environment with a copy of a folder is a project")
    else:
        if source is not None: raise SandboxError("A direct workspace is used in place; copying a folder (--source) does not apply")
        if workspace is None: raise SandboxError("A direct workspace needs a host folder (--workspace PATH)")
        if kind == "quick": raise SandboxError("Quick sessions are disposable; a direct workspace is not. Use project or scratch")
    if image is not None:
        if distro is not None: raise SandboxError("Choose either a distribution or a custom image, not both")
        if not isinstance(image,str) or not _IMAGE_REF.fullmatch(image):
            raise SandboxError(f"Invalid image reference: {str(image)[:80]!r}")
        if image.startswith(distros.REPOSITORY+":"):
            raise SandboxError(f"{image} is a manager image; use --distro instead of --image")
        return kind, None
    return kind, distros.get(distros.DEFAULT if distro is None else distro).id

def create(name, kind=None, source=None, profile="default", *, distro=None, image=None,
           workspace_mode="managed", workspace=None, consent=False, provisioning=None, journal=None):
    """`distro` selects a registry image (default distribution); `image` a custom image instead.
    `kind` None: see creation_options.

    `workspace_mode="direct"` mounts the existing host directory `workspace` itself (D-012). It
    needs `consent` (the caller has shown workspaces.LABEL and the preflight), a verified daemon
    and a passing preflight in the environment's image; nothing is copied or created in it.

    `provisioning` is an `integrations.request()` record; None requests the default integrations.
    `journal`: fields written with the first save, so the environment never exists without them
    (a restore's journal and settings).
    """
    from . import integrations, workspaces
    if provisioning is None: provisioning=integrations.request()
    kind,distro=creation_options(name,kind,source,distro=distro,image=image,workspace_mode=workspace_mode,workspace=workspace)
    if source is not None:
        try: source=Path(source).expanduser().resolve(strict=True)
        except OSError as exc: raise SandboxError(f"Source not accessible: {source} ({exc.strerror})") from None
        if not source.is_dir(): raise SandboxError("Source must be a directory")
        home=Path.home().resolve()
        if source==Path(source.anchor) or source==home or source in home.parents:
            # Would copy every non-hidden personal file into the agent's workspace.
            raise SandboxError(f"Refusing to import {source}: choose a project directory, not the home directory or a parent of it")
        if not (source/".git").exists():
            top=call(["git","-C",source,"rev-parse","--show-toplevel"],capture=True,check=False)
            if top.returncode==0:
                raise SandboxError(f"Source is inside Git repository {top.stdout.strip()}; import the repository root instead")
        elif call(["git","-C",source,"rev-parse","--verify","--quiet","HEAD^{commit}"],capture=True,check=False).returncode:
            raise SandboxError("Source Git repository has no commits; commit once (only committed files are imported)")
    init_dirs()
    direct=None
    if workspace_mode==workspaces.DIRECT:
        if any(other["name"]==name for other in all_envs()):
            raise SandboxError(f"Environment name already exists: {name}")
        if not consent: raise SandboxError(f"A direct workspace needs explicit consent ({workspaces.LABEL})")
        ensure_runtime(distros.get(distro) if image is None else None)
        if image is not None and docker("image","inspect",image,capture=True,check=False).returncode:
            raise SandboxError(f"Image {image} not found locally; the preflight needs it")
        direct=workspaces.check_direct(workspace)
        workspaces.preflight(direct, image or distros.get(distro).image)
    with lock("registry"):
        # Names are the primary CLI/TUI handle; duplicates made every name lookup ambiguous.
        if any(other["name"]==name for other in all_envs()):
            raise SandboxError(f"Environment name already exists: {name}")
        if direct is not None and (shared:=workspaces.overlapping(direct, all_envs())):
            raise SandboxError(f"{direct} overlaps the direct workspace of {', '.join(shared)}; two agents would edit the same files")
        eid=secrets.token_hex(8); d=env_dir(eid); d.mkdir(mode=0o700)
        workspace=d/"workspace"
        origin=None
        try:
            if direct is not None:
                pass  # the host directory is used as it is
            elif source:
                if (source/".git").exists() or call(["git","-C",source,"rev-parse","--show-toplevel"],capture=True,check=False).returncode==0:
                    # Local clone deliberately excludes uncommitted/ignored changes.
                    call(["git","clone","--no-hardlinks","--",str(source),str(workspace)],capture=True)
                    origin=call(["git","-C",workspace,"rev-parse","HEAD"],capture=True).stdout.strip()
                else:
                    # No symlinks or hidden files by default; prevent accidental secret copying.
                    workspace.mkdir()
                    try: _copy_untrusted(source, workspace)
                    except shutil.Error as exc:  # copytree collects per-file errors (e.g. ENOSPC)
                        errors=exc.args[0] if exc.args and isinstance(exc.args[0],list) else []
                        first=errors[0][2] if errors and len(errors[0])==3 else str(exc)
                        raise SandboxError(f"Import failed for {max(len(errors),1)} file(s), first: {first}; nothing was created") from None
                    except OSError as exc:
                        raise SandboxError(f"Import failed: {exc}; nothing was created") from None
                    origin=None
            else: workspace.mkdir()
            m={"id":eid,"name":name,"kind":kind,"source":str(source) if source else None,"base_commit":origin,"profile":profile,"created":now(),"status":"ready","schema":METADATA_SCHEMA,"runtime":validate_runtime_settings({}),
               "distro":distro,"workspace":{"mode":workspace_mode,"path":str(direct) if direct else None},
               "provisioning":provisioning}
            if image is not None: m["image"]=m["custom_image"]=image  # custom_image never changes
            if journal:
                m.update(journal,runtime=validate_runtime_settings(journal.get("runtime",{})))
            save(m)
            return m
        except BaseException:
            shutil.rmtree(d,ignore_errors=True); raise

def cname(m): return "ocs-"+m["id"]
def volume(m):
    value=m.get("home_volume") or "ocs-home-"+m["id"]
    if not re.fullmatch(r"ocs-(?:home|stage)-[0-9a-f]{16}(?:-[0-9a-f]{8})?", value):
        raise SandboxError("Invalid managed volume name")
    return value

def profile_path(name):
    return CONFIG/"profiles"/(safe_name(name)+".json")

def profile_list():
    init_dirs()
    return sorted(p.stem for p in (CONFIG/"profiles").glob("*.json"))

def profile_read(name):
    """Never interpret credential files as shell programs. Legacy .env is refused."""
    p=profile_path(name)
    legacy=p.with_suffix(".env")
    if legacy.exists():
        raise SandboxError(f"Legacy executable profile found: {legacy}. Review and migrate it manually; it will not be sourced")
    if not p.exists(): return {}
    if p.is_symlink() or not p.is_file(): raise SandboxError("Unsafe profile path")
    if p.stat().st_mode & 0o077: raise SandboxError("Profile permissions must be 0600")
    try: values=json.loads(p.read_text())
    except (ValueError, UnicodeError) as exc: raise SandboxError("Invalid profile JSON") from exc
    if not isinstance(values,dict): raise SandboxError("Profile must be a JSON object")
    _validate_profile(values)
    return values

def _validate_profile(values):
    for k,v in values.items():
        if not isinstance(k,str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*",k) or not isinstance(v,str) or "\0" in v:
            raise SandboxError("Invalid environment variable or value")

def profile_set(name, values):
    init_dirs(); p=profile_path(name)
    # Fail closed until legacy credentials are explicitly migrated.
    profile_read(name)
    _validate_profile(values)
    fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=".secret-")
    try:
        with os.fdopen(fd,"w") as f:
            os.fchmod(f.fileno(),0o600)
            json.dump(values,f)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def profile_keys(name):
    return sorted(profile_read(name))

def volume_state(m):
    """Return volume inspect dict or None. Never treat daemon errors as absence."""
    p=docker("volume","inspect",volume(m),capture=True,check=False)
    if p.returncode:
        err=(p.stderr or "").lower()
        if "no such volume" in err or "not found" in err: return None
        raise SandboxError(f"Volume inspect failed: {p.stderr.strip()}")
    try:
        data=json.loads(p.stdout)
        if not isinstance(data,list) or len(data)!=1: raise ValueError("unexpected shape")
        return data[0]
    except (ValueError,TypeError,IndexError) as exc:
        raise SandboxError("Invalid Docker volume inspect response") from exc

def assert_volume_owned(m):
    v=volume_state(m)
    if v is not None and (v.get("Labels") or {}).get("org.opencode-sandbox.id") != m["id"]:
        raise SandboxError(f"Volume ownership mismatch: {volume(m)}; refusing operation")
    return v

def ensure_volume(m):
    existing=assert_volume_owned(m)
    if existing is None:
        docker("volume","create",*labels(m["id"]),volume(m),capture=True)
        assert_volume_owned(m)

def container_exists(m): return docker("container","inspect",cname(m),capture=True,check=False).returncode==0

def running(m):
    state=inspect_container(m)
    return bool(state and state.get("Running"))

def assert_owned(m):
    """Refuse operations on Docker objects not labelled as belonging to this environment."""
    p=docker("container", "inspect", "--format", '{{index .Config.Labels "org.opencode-sandbox.id"}}', cname(m), capture=True, check=False)
    if p.returncode:
        raise SandboxError(f"Cannot verify ownership of {cname(m)}: {p.stderr.strip()}")
    if p.stdout.strip()!=m["id"]:
        raise SandboxError(f"Container name collision / ownership mismatch: {cname(m)}")


def inspect_container(m):
    """Return Docker container state, or None when missing. Raise on daemon failures."""
    p=docker("container","inspect","--format","{{json .State}}",cname(m),capture=True,check=False)
    if p.returncode:
        message=(p.stderr or "").lower()
        # Only Docker's "missing object" answers; a stopped daemon reports
        # "dial unix ...docker.sock: connect: no such file or directory".
        if re.search(r"no such (container|object)", message): return None
        raise SandboxError(f"Cannot inspect {cname(m)}: {p.stderr.strip()}")
    try: state=json.loads(p.stdout)
    except ValueError as exc: raise SandboxError("Invalid Docker inspect response") from exc
    assert_owned(m)
    return state

_MEMORY_UNITS={"k":1024,"m":1024**2,"g":1024**3}

def memory_bytes(text):
    text=str(text)
    return int(text[:-1])*_MEMORY_UNITS[text[-1]] if text[-1] in _MEMORY_UNITS else int(text)

def observed_runtime(m):
    """Network and limits of the existing container as Docker reports them, in the format of
    runtime_settings(); None when there is no container."""
    if inspect_container(m) is None: return None
    p=docker("container","inspect","--format","{{json .HostConfig}}",cname(m),capture=True)
    try:
        host=json.loads(p.stdout)
        configured=runtime_settings(m)
        nano,memory,pids=int(host.get("NanoCpus") or 0),int(host.get("Memory") or 0),int(host.get("PidsLimit") or 0)
    except (ValueError,TypeError,AttributeError) as exc:
        raise SandboxError("Invalid Docker inspect response") from exc
    if memory==memory_bytes(configured["memory"]): shown=configured["memory"]
    else: shown=next((f"{memory//f}{u}" for u,f in reversed(_MEMORY_UNITS.items()) if memory%f==0),str(memory))
    return {"network":host.get("NetworkMode"),"cpus":str(nano/1e9) if nano else "unlimited",
            "memory":shown if memory else "unlimited","pids":pids if pids>0 else "unlimited"}

def image_definition(m, *, container=False):
    """Read base provenance from the owned container, else the selected creation image.

    A retained container's inherited labels cannot follow a later move of the base tag.
    Derived/restored images inherit their base labels. Unknown labels never fall back to
    the current registry version. No container is started and no metadata is changed.
    """
    distro=env_distro(m)
    if distro is None: return None
    if container: assert_owned(m)
    p=docker("container" if container else "image","inspect","--format","{{json .Config.Labels}}",
             cname(m) if container else env_image(m),capture=True,check=False)
    if p.returncode: return None
    try: labels=json.loads(getattr(p,"stdout","") or "")
    except ValueError: return None
    return distros.image_definition(distro.id,labels)

def distribution_description(m, definition=None):
    """A pure metadata-only view is deliberately versionless; do not contact Docker for UI rows."""
    distro=env_distro(m)
    if distro is None: return f"custom image {custom_image(m) or env_image(m)}"
    if definition is not None and definition.matches(distro):
        return f"{distro.name} {definition.version} (base image labels)"
    return f"{distro.name} (OS version not inspected)"

def guidance_inputs(m, *, observe=True):
    """Keyword arguments for agent_context.render/refresh/verify of this environment."""
    observed=observed_runtime(m) if observe else None
    definition=image_definition(m,container=observed is not None) if observe else None
    return {"image":env_image(m),"runtime":runtime_settings(m),"observed":observed,"definition":definition}

def pending_operation(m):
    """The refusal for an environment with a journalled operation. The lock is
    released between an operation's steps, so the journal alone cannot tell a command that is
    still running from an interrupted one: name both, and the recovery command."""
    from .readiness import RECOVERY
    op=m.get("operation")
    # An interrupted first start may have left a container that never ran.
    fallback="opencode-sandbox repair {name} --cleanup" if op=="start" else "opencode-sandbox repair {name}"
    hint=RECOVERY.get(op,fallback).format(name=m["name"])
    return SandboxError(f"{m['name']} has a pending operation ({op}). If another manager command is "
                        f"still working on it, wait until it finishes; if it was interrupted, run: {hint}")

def _remove_unstarted(m):
    """A failed `docker run` can leave the container it created (e.g. the host port was taken).
    It never ran, so its layer holds nothing: remove it, so the settings can be fixed with
    `config apply` like after any other failed first start. Best effort: if it
    stays, `repair NAME --cleanup` removes it."""
    try:
        state=inspect_container(m)
        if state is not None and not state.get("Running") and state.get("Status")=="created":
            docker("rm",cname(m),capture=True,check=False)
    except SandboxError:
        pass

@contextmanager
def base_tag_lock(m):
    """Held while a container is created from a registry base image, and by update-base and
    rollback-base while they move the base tag: the pin check and docker run see the same image.
    Derived and custom images are not affected."""
    if m.get("image") or m.get("distro") is None:
        yield; return
    with lock(f"base-tag-{m['distro']}"):
        yield

def missing_image(m, image, command):
    """The refusal when an image a journal or the next container needs was removed outside the
    manager (cleanup keeps such images): what still works, and what does not."""
    name=m["name"]
    return SandboxError(
        f"Image {image}, which {name} needs, was removed outside the manager (the manager's cleanup keeps it), so "
        "the container cannot be created from it. The workspace and the /root volume are not affected. If you still "
        f"have the image (for example saved with docker image save), load it under that name and run: "
        f"{command.format(name=name)}. Otherwise save the workspace with 'opencode-sandbox changes export {name}' (or "
        f"'opencode-sandbox changes bundle {name}' for a Git project) and remove the environment with "
        f"'opencode-sandbox delete {name} --yes', which also removes the /root volume.")

def recheck_mount(m):
    """Docker mounts a direct workspace again at every container start, following the path as it
    is then: re-check the recorded directory before any start or creation."""
    from . import workspaces
    if workspaces.is_direct(m):
        workspaces.recheck(m)

def start(m, *, _resume_recreate=False):
    ensure_runtime(None if m.get("image") else env_distro(m))
    with lock(m["id"]):
        m=resolve(m["id"])
        if m.get("operation")=="delete" or m.get("status")=="deleting":
            raise SandboxError("Environment deletion pending; retry delete --yes")
        if m.get("operation") in ("runtime-recreate","config-update","restore","opencode-update") \
                or (m.get("operation")=="recreate" and not _resume_recreate):
            raise pending_operation(m)
        state=inspect_container(m)
        if state is None:
            # The pin check and docker run see the same base image.
            with base_tag_lock(m):
                cpus=float(runtime_settings(m)["cpus"])
                if cpus > host_cpus():
                    raise SandboxError(f"CPU limit {cpus:g} exceeds the {host_cpus()} CPUs on this host. "
                                       f"Run: opencode-sandbox config apply {m['name']} --cpus {host_cpus()}")
                from . import opencode_versions
                opencode_versions.check_pin(m)
                image=env_image(m)
                pull=image==m.get("custom_image")  # a custom image is pulled like docker run would (D-026)
                if not pull and docker("image","inspect",image,capture=True,check=False).returncode:
                    if image.split(":",1)[0] in MANAGER_IMAGE_KINDS:
                        raise missing_image(m, image, "opencode-sandbox container recreate-recover {name}" if _resume_recreate
                                            else "opencode-sandbox start {name}")
                    raise SandboxError(f"Base image {image} is missing; build it: opencode-sandbox build --distro {m.get('distro')}")
                mark(m,"creating",operation="recreate" if _resume_recreate else "start")
                # A failed docker run may leave a created container and/or volume.
                try:
                    ensure_volume(m)
                    runtime=runtime_settings(m)
                    conflicts=port_conflicts(m,runtime)
                    if conflicts: raise SandboxError("Port conflict: "+", ".join(conflicts))
                    from . import agent_context as ac
                    from . import workspaces
                    if workspaces.is_direct(m):
                        # Re-checked whenever Docker creates the mount; never created or repaired here.
                        workspaces.recheck(m)
                    # No container yet: the configured values are what docker run applies below.
                    inputs = guidance_inputs(m, observe=False)
                    # The selected image is local and the base-tag lock is held. Capture its
                    # provenance even when this environment has no pending integrations to
                    # trigger a post-start refresh (e.g. a retained/restored environment).
                    inputs["definition"] = image_definition(m)
                    guidance = ac.refresh(m, env_dir, **inputs)
                    # Never pull a manager image (its name is local); drop capabilities an agent
                    # does not need: raw sockets, device nodes.
                    args=["run","-d","--name",cname(m),"--init","--security-opt","no-new-privileges:true",
                          *([] if pull else ["--pull","never"]),"--cap-drop","NET_RAW","--cap-drop","MKNOD",
                          "--memory",runtime["memory"],"--cpus",runtime["cpus"],
                          "--pids-limit",str(runtime["pids"]),"--network",runtime["network"],
                          "--mount",f"type=bind,src={workspaces.path(m)},dst=/workspace",
                          "--mount",f"type=volume,src={volume(m)},dst=/root",
                          # OpenCode's own self-update is off; the manager updates it (D-019).
                          "--env",opencode_versions.SELF_UPDATE_ENV,
                          *labels(m["id"])]
                    # A directory mount, so later refreshes are visible in the running container.
                    args += ["--mount", f"type=bind,src={guidance.parent},dst={ac.CONTAINER_DIR},readonly",
                             "--workdir", "/workspace"]
                    for mapping in runtime["ports"]:
                        args += ["--publish",f"127.0.0.1:{mapping['host']}:{mapping['container']}/{mapping['protocol']}"]
                    profile_name=m.get("profile","default")
                    # Same checks as every other reader: legacy .env, symlink, 0600, JSON shape.
                    profile_read(profile_name)
                    profile=profile_path(profile_name)
                    if profile.exists():
                        args += ["--mount",f"type=bind,src={profile},dst=/run/secrets/ocs-provider.json,readonly"]
                    args += [image,"sleep","infinity"]
                    docker(*args,capture=True)
                except Exception as exc:
                    mark(m,"error",last_error=f"Creation failed: {exc}")
                    _remove_unstarted(m)
                    raise
        elif not state.get("Running"):
            assert_volume_owned(m)
            recheck_mount(m)  # before the state changes: a refusal leaves it stopped
            mounted=mounted_profile(m)
            if mounted and not os.path.exists(mounted):
                raise SandboxError(f"Provider profile file {mounted} was removed; restore it, or recreate the environment "
                                   f"to run without it: opencode-sandbox container recreate {m['name']} --yes")
            mark(m,"starting",operation="recreate" if _resume_recreate else "start")
            try: docker("start",cname(m),capture=True)
            except Exception as exc:
                mark(m,"error",last_error=f"Start failed: {exc}")
                raise
        from . import integrations
        # Once, at the first start (D-009); a failure is recorded, never retried, and never fails start.
        provisioned=integrations.provision(m)
        if provisioned is not None:
            from . import agent_context as ac
            # Not fatal: every launch regenerates it, and the container runs.
            try: ac.refresh(m, env_dir, **guidance_inputs(m))
            except (SandboxError, OSError) as exc: logging.getLogger(APP).warning("Agent Context refresh failed: %s", exc)
        mark(m,"running",last_error=None,operation=None)
        return provisioned

def repair(m, *, cleanup=False):
    """Reconcile metadata against Docker without destroying user data.

    With cleanup, remove only a non-running, labelled partial container. Volumes
    and workspace are deliberately retained.
    """
    ensure_runtime(False)
    with lock(m["id"]):
        m=resolve(m["id"])
        state=inspect_container(m)
        if m.get("operation")=="delete" or m.get("status")=="deleting":
            raise SandboxError("Deletion pending; retry explicit delete --yes (repair will not resurrect it)")
        if m.get("operation") in ("runtime-recreate","recreate","config-update","restore","opencode-update"):
            raise pending_operation(m)  # repair never publishes partial data or discards a journal
        if state is None:
            mark(m,"ready",last_error=None,operation=None)
            return "missing container; workspace and volumes retained"
        if cleanup and not state.get("Running"):
            # Only a partial container (never started) or a dead one: an exited container's
            # writable layer holds the user's system changes, which removing it would lose.
            if state.get("Status") not in ("created","dead"):
                raise SandboxError("Refusing --cleanup: this stopped container has run before and its writable layer holds "
                                   "system changes (packages, files outside /workspace and /root). Use "
                                   f"'opencode-sandbox container recreate {m['name']} --yes' (keeps them via snapshot) or 'delete'.")
            docker("rm",cname(m),capture=True)
            mark(m,"ready",last_error=None,operation=None)
            return "partial container removed; volume and workspace retained"
        status="running" if state.get("Running") else "stopped"
        if state.get("Dead"): status="error"
        mark(m,status,last_error=None if status!="error" else "Docker reports dead container",operation=None)
        return f"reconciled: {status}"

def _tty():
    import sys
    return sys.stdin.isatty() and sys.stdout.isatty()

PROFILE_TARGET = "/run/secrets/ocs-provider.json"

def mounted_profile(m):
    """Host path of the profile bind-mounted into the container, "" if none, None if unknown."""
    p=docker("container","inspect","--format","{{json .Mounts}}",cname(m),capture=True,check=False)
    if p.returncode: return None
    try: mounts=json.loads(getattr(p,"stdout","") or "[]") or []
    except ValueError: return None
    for mount in mounts:
        if isinstance(mount,dict) and mount.get("Destination")==PROFILE_TARGET:
            return mount.get("Source") or ""
    return ""

def profile_mismatch(m):
    """Mounts are fixed at container creation: a restart keeps the old profile."""
    mounted=mounted_profile(m)
    if mounted is None: return None
    assigned=m.get("profile","default"); path=profile_path(assigned)
    expected=os.path.realpath(path) if path.exists() else ""
    if (os.path.realpath(mounted) if mounted else "")==expected: return None
    have=f"'{Path(mounted).stem}'" if mounted else "none"
    return (f"container uses provider profile {have}, assigned is '{assigned}'"
            + ("" if expected else " (profile file does not exist)")
            + f". A restart keeps the mounted profile; apply with: opencode-sandbox container recreate {m['name']} --yes")

# Runs inside the container as `python3 -c LAUNCHER CONTEXT SYSTEM_CONFIG TOKEN`. Provider variables
# from the profile go into the environment of the process that runs the OpenCode server.
# `--standalone` gives every managed launch its own server: the V2 background service keeps the
# environment of whichever client started it first (provider keys of a later launch were not
# applied) and outlives the terminal.
LAUNCHER = """import json,os,pathlib,sys
context,system,token=sys.argv[1],sys.argv[2],sys.argv[3]
p=pathlib.Path('/run/secrets/ocs-provider.json')
raw=p.read_text() if p.exists() else ''
try: d=json.loads(raw) if raw.strip() else {}  # empty = mountpoint stub kept by docker commit
except ValueError: d=None
if not isinstance(d,dict) or not all(isinstance(k,str) and k.isidentifier() and isinstance(v,str) for k,v in d.items()):
    sys.exit('Invalid provider profile')
os.environ.update(d)
try: configured=context in pathlib.Path(system).read_text()
except OSError: configured=False
if not configured:
    print('WARNING: '+system+' does not list '+context+'; OpenCode will not receive the sandbox Agent Context in this image.',file=sys.stderr)
argv=['bash'] if os.environ.get('OCS_SHELL')=='1' else ['opencode','--standalone']
os.environ['OCS_RUN_TOKEN']=token  # lets the host hang up exactly this session
os.umask(0o022)  # docker exec inherits rootless dockerd's umask (0000)
os.execvp(argv[0],argv)"""

def interactive(m, shell=False):
    if not _tty():
        raise SandboxError("run/shell need an interactive terminal; use 'exec NAME -- COMMAND' for scripts")
    provisioned = start(m)
    if provisioned: print(f"Initial integrations: {provisioned}", file=sys.stderr)
    from . import agent_context as ac
    m = resolve(m["id"])
    warning = profile_mismatch(m)
    if warning: print(f"WARNING: {warning}", file=sys.stderr)
    # Regenerate before every launch; the directory mount makes it visible at once.
    with lock(m["id"]):
        m = resolve(m["id"])
        ac.refresh(m, env_dir, **guidance_inputs(m))
    token = secrets.token_hex(8)
    watchdog = session_watchdog(m, token)
    try:
        rc = docker_attached("exec", "-it", "-e", f"OCS_SHELL={int(shell)}", cname(m),
                             "python3", "-c", LAUNCHER, ac.CONTAINER_PATH, ac.SYSTEM_CONFIG, token,
                             on_start=lambda pid: _tell(watchdog, f"{pid}\n"))
    except BaseException:
        hangup_session(m, token)
        raise
    finally:
        _tell(watchdog, "done\n", close=True)
    if rc < 0: hangup_session(m, token)  # the docker client itself was killed
    return rc

@contextmanager
def _session_launch_signals():
    """Do not unwind Popen before it returns the PID of an already-running client.

    Defer callable exit handlers only through creation/registration, then restore and deliver
    the first signal inside the caller's cleanup guard. Never mask signals (the child would
    inherit that mask), change ignored/default dispositions, or install handlers in a worker.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    handlers, pending = {}, []

    def defer(signum, frame):
        if not pending: pending.append((signum, frame))

    try:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            handler = signal.getsignal(sig)
            if callable(handler):
                handlers[sig] = handler
                signal.signal(sig, defer)
        yield
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        if pending:
            signum, frame = pending[0]
            handlers[signum](signum, frame)

def docker_attached(*args, on_start=None):
    """An interactive docker client on this terminal; `on_start(pid)` once it runs. Exit code."""
    argv, env = ["docker", "-H", docker_endpoint(), *args], runtime_identity.docker_env()
    terminal = None
    try:
        fd = sys.stdin.fileno()
        terminal = fd, termios.tcgetattr(fd)
    except (AttributeError, OSError, ValueError, termios.error):
        pass  # no usable terminal (e.g. a pipe); never change another terminal
    p = None
    try:
        with _session_launch_signals():
            try:
                p = subprocess.Popen(argv, env=env)
            except OSError as exc:
                raise SandboxError(f"Cannot execute docker: {exc}") from exc
            if on_start: on_start(p.pid)
        return p.wait()
    except BaseException:
        if p is not None and p.poll() is None:
            p.send_signal(signal.SIGHUP)  # as a closing terminal would
            try: p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()  # reap the forced exit too
        raise
    finally:
        if terminal is not None:
            try: termios.tcsetattr(terminal[0], termios.TCSANOW, terminal[1])
            except (OSError, ValueError, termios.error): pass  # closed/hung-up terminal must not replace the session exit

# The manager itself can die without running any cleanup (SIGKILL, OOM killer): its docker client
# then keeps the terminal and the session keeps running in the container. A watchdog
# in its own session reads a pipe from the manager; EOF without "done" means the manager is gone
# (the kernel closes the pipe however a process ends), so it hangs up the client and the session.
WATCHDOG = """import os,signal,subprocess,sys
words=sys.stdin.read().split()
if 'done' in words: sys.exit(0)
if words and words[0].isdigit():
    try: os.kill(int(words[0]),signal.SIGHUP)
    except OSError: pass
subprocess.run(sys.argv[1:],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
"""

def session_watchdog(m, token):
    """Best effort: None when it cannot start (the session then runs without it)."""
    argv = [sys.executable, "-I", "-c", WATCHDOG, "docker", "-H", docker_endpoint(),
            "exec", cname(m), "sh", "-c", HANGUP, "ocs-hangup", token]
    try:
        return subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=runtime_identity.docker_env(), start_new_session=True, text=True)
    except OSError:
        return None

def _tell(watchdog, text, close=False):
    if watchdog is None: return
    try:
        watchdog.stdin.write(text); watchdog.stdin.flush()
        if close:
            watchdog.stdin.close()
            watchdog.wait(2)  # it exits at once after "done"
    except (OSError, ValueError, subprocess.TimeoutExpired): pass

# docker exec keeps the process running when its client goes away (terminal closed, SIGHUP):
# abandoned OpenCode sessions piled up in the container. Deliver the hangup the terminal would have.
HANGUP = """for e in /proc/[0-9]*/environ; do
  grep -qzx "OCS_RUN_TOKEN=$1" "$e" 2>/dev/null || continue
  p=${e#/proc/}; kill -HUP "${p%/environ}" 2>/dev/null
done; exit 0"""

def hangup_session(m, token):
    try: docker("exec", cname(m), "sh", "-c", HANGUP, "ocs-hangup", token, capture=True, check=False)
    except Exception: pass  # noqa: BLE001, S110 — best effort while the launcher exits; never replaces the exception that ended the session

def exec_cmd(m,cmd):
    """Run a command; allocate a TTY only when attached to one (pipes/scripts work)."""
    start(m)
    flags=["-i","-t"] if _tty() else ["-i"]
    # docker exec inherits rootless dockerd's umask (0000): files would be world-writable.
    return docker("exec",*flags,cname(m),"/bin/sh","-c",'umask 022 && exec "$@"',"ocs-exec",*cmd,check=False).returncode

# Interrupted operations whose journal only their recovery command may close.
JOURNALS = frozenset({"runtime-recreate","recreate","config-update","delete","restore","opencode-update"})

def stop(m):
    """True if this call stopped a running container."""
    ensure_runtime(False)
    with lock(m["id"]):
        m=resolve(m["id"])
        state=inspect_container(m)
        running=bool(state and state.get("Running"))
        if m.get("operation") in JOURNALS:
            # Stopping is safe, but the journal stays for its recovery (stop used to erase it).
            if running: docker("stop",cname(m),capture=True)
            return running
        if running:
            mark(m,"stopping",operation="stop")
            try: docker("stop",cname(m),capture=True)
            except Exception as exc:
                mark(m,"error",last_error=f"Stop failed: {exc}")
                raise
        mark(m,"stopped",operation=None,last_error=None)
        return running

def docker_reserve():
    return int(os.getenv("OPENCODE_SANDBOX_DOCKER_RESERVE_BYTES", str(2*1024**3)))

def docker_root():
    p=docker("info","--format","{{.DockerRootDir}}",capture=True,check=False)
    path=Path((getattr(p,"stdout",None) or "").strip())
    return path if p.returncode==0 and path.is_absolute() and path.exists() else None

def require_docker_space(what):
    """Refuse commit/build/npm work that would fill the disk midway (ENOSPC).

    Heuristic reserve, not an exact estimate; unknown Docker root skips the check.
    """
    root=docker_root()
    if root is None: return None
    free=shutil.disk_usage(root).free
    if free<docker_reserve():
        raise SandboxError(f"Not enough free disk space for {what}: {free/2**30:.1f} GiB free on {root}, "
                           f"{docker_reserve()/2**30:.1f} GiB reserve required. Free space first "
                           "('opencode-sandbox disk usage' and 'disk cleanup') or adjust OPENCODE_SANDBOX_DOCKER_RESERVE_BYTES.")
    return free

def snapshot(m,tag=None):
    """docker commit captures container writable layer, not /root volume or /workspace."""
    ensure_runtime(False)
    if inspect_container(m) is None: raise SandboxError("No container to snapshot")
    if tag is not None: check_snapshot_tag(m, tag)
    require_docker_space("a container snapshot")
    tag=tag or snapshot_tag(m)
    docker("commit",cname(m),tag,capture=True)
    return tag

def snapshot_tag(m):
    """A new default snapshot tag: the time has one-second resolution, so a random suffix; a tag
    that exists is never moved by `docker commit`/`docker tag`."""
    tag=f"ocs-snapshot:{m['id']}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"
    if docker("image","inspect",tag,capture=True,check=False).returncode==0:
        raise SandboxError(f"Image {tag} already exists; snapshots never replace an existing tag")
    return tag

MANAGER_IMAGE_KINDS = ("ocs-snapshot", "ocs-runtime", "ocs-backup", "ocs-checkpoint")  # repositories, cleanup.ENV_IMAGE

def check_snapshot_tag(m, tag):
    """`docker commit` moves an existing tag, so a chosen tag could have replaced a base image or
    another environment's image. Only new tags; in the manager's repositories only
    this environment's ocs-snapshot:<id>-*."""
    if not _IMAGE_REF.fullmatch(tag) or "@" in tag or ":" not in tag.rsplit("/",1)[-1]:
        raise SandboxError(f"Invalid image tag {tag[:80]!r}: use REPOSITORY:TAG")
    repo=tag.rsplit(":",1)[0]
    if repo in (distros.REPOSITORY, *MANAGER_IMAGE_KINDS) and not tag.startswith(f"ocs-snapshot:{m['id']}-"):
        raise SandboxError(f"{repo} is a manager repository; choose another tag, or ocs-snapshot:{m['id']}-NAME")
    if docker("image","inspect",tag,capture=True,check=False).returncode==0:
        raise SandboxError(f"Image {tag} already exists; snapshots never replace an existing tag")

def recreate(m, confirm=False):
    """Preserve writable layer via commit, then recreate using that exact image.

    Keep the journal until the replacement is running. Interrupted operations
    must be explicitly recovered; generic repair may not erase the intent.
    """
    if not confirm: raise SandboxError("Recreation requires explicit confirmation; apt packages in volumes are not included in system snapshots")
    ensure_runtime(False)
    with lock(m["id"]):
        m=resolve(m["id"])
        if m.get("operation"):
            raise pending_operation(m)
        state=inspect_container(m)
        if state is not None:
            # Stop first, like reconfiguration: the commit then holds the final state (no
            # half-written package database, no change lost between commit and removal) and
            # processes get a graceful stop. A kill here leaves a stopped container, no journal.
            if state.get("Running"): docker("stop",cname(m),capture=True)
            tag=snapshot(m)
            m["image"]=tag
            mark(m,"recreating",last_snapshot=tag,operation="recreate")
            # Not -f: a container started again after the commit is never removed.
            try: docker("rm",cname(m),capture=True)
            except Exception as exc:
                mark(m,"error",last_error=f"Recreate removal failed: {exc}")
                raise
        else:
            mark(m,"recreating",operation="recreate")
    return recreate_recover(m)


def recreate_recover(m):
    """Explicitly finish a journalled recreation; do not discard its snapshot."""
    ensure_runtime(False)
    with lock(m["id"]):
        m=resolve(m["id"])
        if m.get("operation") != "recreate":
            raise SandboxError("No pending recreation")
        state=inspect_container(m)
        if m.get("last_snapshot") and m.get("image") != m["last_snapshot"]:
            raise SandboxError("Recreation image differs from recorded snapshot")
        if state is not None:
            image=docker("container","inspect","--format","{{.Config.Image}}",cname(m),capture=True).stdout.strip()
            if state.get("Running"):
                if image != env_image(m):
                    # The old container: its removal failed or never ran.
                    raise SandboxError(
                        f"The running container is the old container (image {image!r}), not the replacement from "
                        f"{env_image(m)!r}; changes made in it after the snapshot are not in that snapshot. Stop it with "
                        f"'opencode-sandbox stop {m['name']}', then rerun 'opencode-sandbox container recreate-recover {m['name']}'.")
                mark(m,"running",operation=None,last_error=None)
                return "replacement already running"
            if not m.get("image") or image != m["image"]:
                raise SandboxError(
                    f"A stopped container from image {image!r} still exists; it is not the recorded "
                    f"replacement ({m.get('image')!r}). Its layer was already committed to that snapshot. "
                    f"Inspect it, then remove it with '{docker_cli()} rm {cname(m)}' and rerun 'opencode-sandbox container recreate-recover {m['name']}'.")
            # The replacement was created from the snapshot but never started.
            recheck_mount(m)
            mark(m,"starting",operation="recreate")
            try: docker("start",cname(m),capture=True)
            except Exception as exc:
                mark(m,"error",operation="recreate",last_error=f"Recreation start failed: {exc}")
                raise
            mark(m,"running",operation=None,last_error=None)
            return "replacement started"
        # Preserve the journal through container creation. A crash at any point
        # remains explicitly recoverable instead of looking like a normal start.
    try:
        start(m, _resume_recreate=True)
    except Exception as exc:
        with lock(m["id"]):
            current=resolve(m["id"])
            # Only the recreation's own journal; another operation's is never replaced.
            if current.get("operation")=="recreate":
                mark(current,"error",last_error=f"Recreation start failed: {exc}")
        raise
    return "recreated"

DIRECT_CHANGES=("Direct workspace: the agent edits the host directory itself, so there is nothing to export; "
                "review and commit the changes with Git in that directory.")

def git_changes(m):
    """Preview changes. The workspace (including .git) is agent-controlled: use hardened Git."""
    from . import workspace_io as wio
    from . import workspaces
    if workspaces.is_direct(m): return DIRECT_CHANGES
    w=workspaces.managed_path(m)
    if not wio.is_git_workspace(w): return "Not a Git repository; 'changes export' archives the whole workspace."
    base=m.get("base_commit")
    if not base: return "No base commit recorded"
    try:
        diff=wio.git(w,"diff","--no-ext-diff","--no-textconv","--stat",base,"--",check=False)
        commits=wio.git(w,"log","--oneline",f"{base}..HEAD","--",check=False)
        status=wio.git(w,"status","--short",check=False)
    except SandboxError as exc:
        return f"Git preview unavailable: {exc}"
    text=lambda b: b.decode("utf-8",errors="replace")
    return "Commits:\n"+text(commits)+"\nDiff:\n"+text(diff)+"\nWorking tree:\n"+text(status)

def _tar_bytes(tf, name, data, mode=0o600):
    info=tarfile.TarInfo(name); info.size=len(data); info.mode=mode; info.mtime=int(time.time())
    import io
    tf.addfile(info, io.BytesIO(data))

def export(m,destination=None):
    """Never write to source. Bundle commits + unstaged/staged changes and untracked files.

    The workspace is agent-controlled: symlinks are archived as links (never
    dereferenced) and files are read without following symlinks.
    """
    from . import workspace_io as wio
    from . import workspaces
    if workspaces.is_direct(m): raise SandboxError(DIRECT_CHANGES)
    w=workspaces.managed_path(m)
    if destination: workspaces.refuse_output_inside(destination, "an export")
    init_dirs(); dest=Path(destination).expanduser() if destination else BASE/"exports"
    dest.mkdir(parents=True,exist_ok=True)
    prefix=m["name"]+"-"+m["id"]+"-"+datetime.now().strftime("%Y%m%d%H%M%S")
    target=dest/(prefix+".tar.gz")
    git_mode=wio.is_git_workspace(w) and m.get("base_commit")
    wio.require_readable(w,m["name"],skip_git=bool(git_mode))
    skipped=[]
    try: fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError: raise SandboxError("Export exists; refusing overwrite") from None
    try:
        with os.fdopen(fd,"wb") as raw, tarfile.open(fileobj=raw,mode="w:gz") as tf:
            if git_mode:
                base=m["base_commit"]
                # Includes commits since base plus staged/unstaged tracked changes.
                _tar_bytes(tf,"changes.patch",wio.git(w,"diff","--binary","--no-ext-diff","--no-textconv",base,"--"))
                names=wio.git(w,"ls-files","--others","--exclude-standard","-z").split(b"\0")
                for raw_name in names:
                    if not raw_name: continue
                    name=os.fsdecode(raw_name)
                    try:
                        data,mode=wio.read_file(w,name)
                        _tar_bytes(tf,"untracked/"+name,data,mode)
                    except SandboxError: skipped.append(name)
            else:
                for root,dirs,files in os.walk(w,followlinks=False):
                    dirs[:]=sorted(d for d in dirs if not (root==str(w) and d==".git"))
                    for name in sorted(files)+[d for d in dirs if os.path.islink(os.path.join(root,d))]:
                        p=Path(root)/name; rel=p.relative_to(w).as_posix()
                        st=os.lstat(p)
                        if stat.S_ISLNK(st.st_mode):
                            info=tarfile.TarInfo("workspace/"+rel); info.type=tarfile.SYMTYPE
                            info.linkname=os.readlink(p); tf.addfile(info)
                        elif stat.S_ISREG(st.st_mode):
                            try:
                                data,mode=wio.read_file(w,rel)
                                _tar_bytes(tf,"workspace/"+rel,data,mode)
                            except SandboxError: skipped.append(rel)
                        else: skipped.append(rel)
            _tar_bytes(tf,"manifest.json",json.dumps({"environment":m,"exported":now(),"skipped":skipped},indent=2).encode())
    except BaseException:
        target.unlink(missing_ok=True); raise
    return target

def delete(m, *, force=False, precondition=None):
    """Retryable deletion: journal intent before destructive Docker operations.

    A failed deletion leaves the workspace and metadata, allowing explicit retry.
    Docker objects are only removed after their ownership is verified. `precondition(m)` runs
    on the current metadata under the lock and may refuse.
    """
    if not force: raise SandboxError("Deletion requires explicit confirmation")
    ensure_runtime(False)
    with lock(m["id"]):
        m=resolve(m["id"])
        if precondition is not None: precondition(m)
        # Ownership preflight BEFORE journalling: a refused collision must not leave
        # the environment stuck in "deletion pending" when nothing was deleted.
        state=inspect_container(m)
        v=assert_volume_owned(m)
        mark(m,"deleting",operation="delete")
        try:
            if state is not None:
                docker("rm","-f",cname(m),capture=True)
            if v is not None:
                docker("volume","rm",volume(m),capture=True)
            # Once both Docker objects are gone, metadata/workspace may be removed.
            # A crash here leaves a deletion intent; retry is safe.
            _remove_env_dir(m)
        except Exception as exc:
            if env_dir(m["id"]).exists():
                mark(m,"deleting",last_error=f"Deletion incomplete: {exc}")
            raise

def _remove_env_dir(m):
    """Remove the environment directory, including workspace files owned by
    subordinate UIDs (created by non-root users in the container), which only
    the rootless user namespace can delete.

    Only the managed workspace below the environment directory is ever removed: a direct
    workspace lives elsewhere and is never computed here (D-012)."""
    from . import workspaces
    d=env_dir(m["id"])
    direct=workspaces.is_direct(m)
    try:
        _remove_all_but_metadata(d)
        return _remove_metadata_last(d)
    except PermissionError:
        if direct:
            # Only manager files are below d; no container-based removal for these environments.
            raise SandboxError(f"Cannot remove {d}: permission denied") from None
    w=workspaces.managed_path(m)
    if w.parent!=d or w.resolve().parent!=d.resolve():
        raise SandboxError(f"Refusing container-based removal outside {d}")
    if w.is_dir() and not w.is_symlink():
        # Prefer a registry image (known to have find); the environment's own image otherwise.
        options=[*(d.image for d in distros.REGISTRY.values()),*([m["image"]] if m.get("image") else [])]
        image=next((i for i in options if not docker("image","inspect",i,capture=True,check=False).returncode),None)
        if not image:
            raise SandboxError(f"Workspace has container-owned files and no local image is available to remove them: {w}")
        docker("run","--rm","--network","none","--security-opt","no-new-privileges:true",
               *helper_labels("cleanup"),"--label",f"org.opencode-sandbox.cleanup={m['id']}",
               "--mount",f"type=bind,src={w},dst=/w","--entrypoint","find",image,
               "/w","-mindepth","1","-delete",capture=True)
    try: _remove_all_but_metadata(d)
    except OSError as exc: raise SandboxError(f"Cannot remove {d}: {exc}") from exc
    _remove_metadata_last(d)

def _remove_all_but_metadata(d):
    """The workspace first, metadata.json last: until the very end an interrupted deletion stays
    listed with its journal and can be retried."""
    entries=sorted(d.iterdir(),key=lambda p:p.name!="workspace")
    for p in entries:
        if p.name=="metadata.json": continue
        if p.is_dir() and not p.is_symlink(): shutil.rmtree(p)
        else: p.unlink()

def _remove_metadata_last(d):
    (d/"metadata.json").unlink(missing_ok=True)
    d.rmdir()

def promote(m,kind,name=None):
    if kind not in ("project","scratch"): raise SandboxError("Can promote only to project/scratch")
    with lock("registry"), lock(m["id"]):
        m=resolve(m["id"])
        if name and name!=m["name"]:
            if any(other["name"]==name for other in all_envs()):
                raise SandboxError(f"Environment name already exists: {name}")
            m["name"]=check_new_name(name)
        m["kind"]=kind
        save(m)

def build_image(distro, version, tag):
    """Build a registry image with OpenCode `version` (concrete) as `tag`, then verify it."""
    from . import opencode_versions as v
    meta={**distro.image_labels(), distros.LABEL+"opencode-package": v.PACKAGE,
          distros.LABEL+"opencode-version": version}
    docker("build","--build-arg",f"OPENCODE_VERSION={version}",*labels(scoped=False),
           *(arg for key,value in meta.items() for arg in ("--label",f"{key}={value}")),
           "-t",tag,"-f",str(distro.dockerfile),str(distros.IMAGES))
    verify_image(distro, tag, version)

def _image_facts(distro):
    """Shell script printing os-release entries, missing tools, failed smoke commands, then
    the OpenCode version (last line)."""
    lines=["sed -n 's/^\\([A-Z_]*\\)=\\(.*\\)$/ocs-os: \\1=\\2/p' /etc/os-release",
           "for t in "+" ".join(shlex.quote(t) for t in distro.tools)+"; do "
           "command -v \"$t\" >/dev/null 2>&1 || echo \"ocs-problem: $t is not on PATH\"; done"]
    lines+=[f"sh -c {shlex.quote(cmd)} >/dev/null 2>&1 || echo {shlex.quote(f'ocs-problem: {cmd} failed')}"
            for cmd in distro.smoke]
    # Registry images archive home volumes for backup/restore (backup.helper_image).
    lines.append("tar --create --acls --xattrs --file=/dev/null /etc/hostname >/dev/null 2>&1 || "
                 "echo 'ocs-problem: tar --acls --xattrs failed (needed for backups)'")
    return "\n".join([*lines,"opencode --version"])

def verify_image(distro, tag, version):
    """Refuse a built image whose OS, tools or OpenCode version differ from the registry."""
    from . import opencode_versions as v
    # Same hardening as an environment's container (start()).
    p=docker("run","--rm","--network","none","--security-opt","no-new-privileges:true",*helper_labels("image-verify"),
             "--entrypoint","sh",tag,"-c",_image_facts(distro),capture=True)
    lines=p.stdout.splitlines()
    reported=dict(line[len("ocs-os: "):].partition("=")[::2] for line in lines if line.startswith("ocs-os: "))
    reported={key:value.strip().strip('"\'') for key,value in reported.items()}
    expected=dict(distro.os_release)
    if any(reported.get(key)!=value for key,value in expected.items()):
        actual=", ".join(f"{key}={reported.get(key,'?')}" for key in expected)
        raise SandboxError(f"Built image reports {actual}; the registry expects "
                           +", ".join(f"{k}={v_}" for k,v_ in expected.items())+" (update distros.py or the Dockerfile)")
    problems=[line[len("ocs-problem: "):] for line in lines if line.startswith("ocs-problem: ")]
    if problems: raise SandboxError("Built image does not match the registry: "+"; ".join(problems))
    installed=v.normalize(p.stdout)
    if installed!=version: raise SandboxError(f"Built OpenCode {installed}, expected {version}")

def build(distro=None, version=None):
    """Build (or rebuild) a distribution's base image; no rollback copy (see update-base)."""
    from . import opencode_versions as v
    return v.update_base(version or "latest", distro, keep_previous=False)

TRANSIENT_STATES = frozenset({"creating", "starting", "stopping", "recreating", "deleting", "error"})

def pending_repairs():
    """Non-destructive startup scan. Never contact Docker or mutate metadata."""
    return [m for m in all_envs() if m.get("status") in TRANSIENT_STATES or m.get("operation")]

def repair_all():
    """Reconcile interrupted environments one by one; retain failures for inspection."""
    results=[]
    for m in pending_repairs():
        try: results.append((m["id"], repair(m), None))
        except Exception as exc: results.append((m["id"], None, error_text(exc)))  # noqa: BLE001 — one failure must not stop the others
    return results
