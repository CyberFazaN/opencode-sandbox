"""Shared CLI/TUI OpenCode global-config profiles, exports, drift consent and volume transfer."""
from __future__ import annotations

import ast
import json
import os
import posixpath
import re
import secrets
import selectors
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

from . import config_tree as tree
from . import core as c

TMP = Path("/tmp")  # Never honor TMPDIR for deterministic export discovery.
MARKER = ".ocs-export.json"
BOUNDARY = "/root/.config/opencode/"
SCOPE = ("Only the entire global/local " + BOUNDARY + " tree; not the complete effective OpenCode configuration. "
         "System /etc/opencode/, Agent Context, /workspace and other home state/auth directories are untouched.")
REPLACE_WARNING = ("This replaces the ENTIRE global OpenCode config directory, including plugins, generated files, "
                   "credentials and local state stored there. No merge or live link. ")
RUNNING_WARNING = ("Container is running: changing config while OpenCode may be active is not recommended; "
                   "a future process may be needed to observe it. Nothing is stopped or restarted.")
EXPORT_WARNING = ("The private host export may contain credentials and executable plugins. Other ordinary host users "
                  "are excluded, not root or same-UID processes. It remains under /tmp until deleted or temporary-file cleanup/reboot.")


class Conflict(c.SandboxError):
    def __init__(self, fingerprint):
        super().__init__("Container config changed since the last Export/Apply. Cancel or Overwrite Anyway.")
        self.fingerprint = fingerprint


def profiles_directory():
    return c.CONFIG / "opencode-configs"


def profiles():
    """User-maintained directories, including one symlink at their root; never create/edit sources."""
    directory = profiles_directory()
    if not directory.exists(): return []
    if not directory.is_dir(): raise c.SandboxError("OpenCode profiles location is not a directory")
    return sorted(p.name for p in directory.iterdir() if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", p.name)
                  and p.is_dir())


def profile_path(name):
    c.safe_name(name)
    try:
        # Resolve this single root pointer only. Internal links are never traversed by the codec.
        path = (profiles_directory() / name).resolve(strict=True)
        if not path.is_dir(): raise OSError()
        return path
    except (OSError, RuntimeError):
        raise c.SandboxError("OpenCode config profile is missing or unreadable; source was not imported") from None


def limits():
    try:
        size = int(os.getenv("OPENCODE_SANDBOX_MAX_CONFIG_BYTES", str(tree.MAX_BYTES)))
        entries = int(os.getenv("OPENCODE_SANDBOX_MAX_ARCHIVE_ENTRIES", str(tree.MAX_ENTRIES)))
        if size <= 0 or entries <= 0: raise ValueError()
    except ValueError:
        raise c.SandboxError("Config transfer limits must be positive integers") from None
    # One immutable input/output archive plus staging, with headroom for archive metadata.
    # The destination filesystem independently checks available space while extracting.
    available = shutil.disk_usage(TMP).free - 256 * 1024**2
    return {"max_bytes": min(size, max(0, available // 3)), "max_entries": entries}


def _tree_call(function, *args, **kwargs):
    """Expected data/codec failures must not expose file-byte locals in a CLI traceback."""
    try:
        return function(*args, **kwargs)
    except tree.TreeError as exc:
        raise c.SandboxError(str(exc)) from None
    except (tarfile.TarError, ValueError, UnicodeError, RecursionError):
        raise c.SandboxError("Cannot safely copy/decode the global config tree; source and recovery copies are retained") from None


@contextmanager
def prepared_profile(name):
    """Immutable byte snapshot; no persistent environment changes precede source validation."""
    source = profile_path(name)
    with tempfile.TemporaryFile(dir=TMP) as archive:
        try:
            tree.snapshot(source, archive, allow_missing=False, **limits())
        except (OSError, ValueError, tree.TreeError, tarfile.TarError, RecursionError) as exc:
            raise c.SandboxError(str(exc) if isinstance(exc, tree.TreeError) else
                                 "Cannot safely read the entire OpenCode profile; source left unchanged") from None
        archive.seek(0)
        yield archive


def binding(m):
    return {"schema": 1, "uid": os.getuid(), "data": c.data_id(), "id": m["id"], "created": m["created"]}


def export_path(m):
    c.env_dir(m["id"])
    return TMP / f"ocs-occonfig-{os.getuid()}-{c.data_id()}" / m["id"]


def _read_marker(fd, name):
    leaf = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
    with os.fdopen(leaf) as source:
        st = os.fstat(source.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1 \
                or stat.S_IMODE(st.st_mode) != 0o600 or st.st_size > 8192:
            raise c.SandboxError("Unsafe export ownership marker; nothing was changed")
        try: return json.load(source)
        except (ValueError, UnicodeError): raise c.SandboxError("Invalid export ownership marker; preserved") from None


def _open_private(path):
    fd = os.open(path, tree.DIR_FLAGS)
    st = os.fstat(fd)
    if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o700:
        os.close(fd)
        raise c.SandboxError("Unsafe export directory owner or mode (expected own UID, 0700); preserved")
    current = os.stat(path, follow_symlinks=False)
    if (st.st_dev, st.st_ino) != (current.st_dev, current.st_ino):
        os.close(fd)
        raise c.SandboxError("Export directory changed while opening; preserved")
    return fd


def _same_identity(actual, expected):
    return isinstance(actual, dict) and actual.keys() == expected.keys() and all(
        type(actual[key]) is type(value) and actual[key] == value for key, value in expected.items())


@contextmanager
def workspace(m, *, create=False):
    path = export_path(m)
    parent = path.parent
    if create:
        try:
            parent.mkdir(mode=0o700)
        except FileExistsError:
            pass
        else:
            # A collision without the namespace marker is deliberately not adopted later.
            tree.write_json(parent / MARKER, {"schema": 1, "uid": os.getuid(), "data": c.data_id()})
    try:
        parent_fd = _open_private(parent)
    except FileNotFoundError:
        yield None
        return
    except OSError:
        raise c.SandboxError("Unsafe export namespace; refusing to follow or replace it") from None
    with ExitStack() as descriptors:
        descriptors.callback(os.close, parent_fd)
        found = None
        try:
            if not _same_identity(_read_marker(parent_fd, MARKER), {"schema": 1, "uid": os.getuid(), "data": c.data_id()}):
                raise c.SandboxError("Export namespace identity mismatch; preserved")
            try: fd = _open_private(path)
            except FileNotFoundError: fd = None
            if fd is not None:
                descriptors.callback(os.close, fd)
                record = _read_marker(fd, MARKER)
                if not isinstance(record, dict) or set(record) != {"binding", "fingerprint"} \
                        or not _same_identity(record.get("binding"), binding(m)) \
                        or not isinstance(record.get("fingerprint"), str) \
                        or not re.fullmatch(r"[0-9a-f]{64}", record["fingerprint"]):
                    raise c.SandboxError("Export identity or baseline is invalid; preserved")
                config_fd = os.open("config", tree.DIR_FLAGS, dir_fd=fd)
                descriptors.callback(os.close, config_fd)
                if os.fstat(config_fd).st_uid != os.getuid():
                    raise c.SandboxError("Export config directory is not owned by this user; preserved")
                found = (path, record)
        except (OSError, UnicodeError):
            raise c.SandboxError("Export workspace is unavailable or unsafe; validation changed neither side") from None
        # Do not translate errors from the operation body into a false "nothing changed"
        # claim: publication/baseline persistence may fail after a successful directory switch.
        yield found


def status(m):
    with c.lock(m["id"]):
        m = c.resolve(m["id"])
        with workspace(m) as found:
            return {"state": "Export available" if found else "No export",
                    "path": str(found[0] / "config") if found else None}


def _helper_source():
    # Remove only the package import/future statements, keeping one source for host tests and
    # the stdlib-only container helper. AST spans avoid fragile regex rewriting.
    text = Path(__file__).with_name("config_volume.py").read_text()
    lines = text.splitlines(keepends=True)
    for node in ast.parse(text).body:
        if isinstance(node, ast.ImportFrom) and (node.level or node.module == "__future__"):
            for index in range(node.lineno - 1, node.end_lineno): lines[index] = "\n"
    return Path(tree.__file__).read_text() + "\n" + "".join(lines) + "\nhelper_main()\n"


def _transfer(argv, incoming, outgoing, *, max_output):
    """Bound bytes on the host too: a compromised image cannot fill host disk or stderr RAM."""
    errors, size = bytearray(), 0
    process = None
    sink = tree.ArchiveSink(outgoing, max_output) if outgoing is not None else None
    try:
        with c._session_launch_signals():
            process = subprocess.Popen(argv, stdin=incoming or subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=c.runtime_identity.docker_env(), start_new_session=True)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "data")
            selector.register(process.stderr, selectors.EVENT_READ, "error")
            deadline = time.monotonic() + 1830
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise c.SandboxError("Config transfer exceeded its safety deadline; recover the pending transaction")
                for key, _ in selector.select(0.2):
                    data = os.read(key.fd, 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    if key.data == "error":
                        if len(errors) + len(data) > 16384:
                            raise c.SandboxError("Config helper error output exceeded its bound; no result verified")
                        errors.extend(data)
                    else:
                        size += len(data)
                        if size > max_output:
                            raise c.SandboxError("Config archive exceeded the host transfer limit; previous export/config preserved")
                        if sink is not None: _tree_call(sink.write, data)
            return process.wait(timeout=max(1, deadline - time.monotonic())), bytes(errors)
    except FileNotFoundError:
        raise c.missing_program("docker") from None
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdout.close()
            process.stderr.close()


def _volume_ready(m):
    """Read-only admission before journalling intent, repeated before launching a helper."""
    c.ensure_runtime(False)
    volume = c.assert_volume_owned(m)
    if volume is None:
        if m.get("operation") == "opencode-config":
            raise c.SandboxError("Home volume is unavailable; recovery cannot invent missing data. Restore it from backup, "
                                 "or delete an incomplete initial-Copy environment and create it again")
        raise c.SandboxError("Home volume is unavailable. For a new environment, Start first; "
                             "for a missing existing volume, restore it from backup before retrying")
    labels = volume.get("Labels") or {}
    if labels.get(c.DATA_LABEL) != c.data_id() or labels.get("org.opencode-sandbox.managed") != "true":
        raise c.SandboxError("Home volume does not belong to this manager data directory")
    state = c.inspect_container(m)
    image = c.env_image(m)
    if state is not None:
        image = c.docker("container", "inspect", "--format", "{{.Image}}", c.cname(m), capture=True).stdout.strip()
    if not isinstance(image, str) or not c._IMAGE_REF.fullmatch(image):
        raise c.SandboxError("Invalid config helper image reference; no transfer started")
    probe = c.docker("image", "inspect", "--format", "{{json .Config.Volumes}}", image, capture=True, check=False)
    try:
        declared = json.loads(probe.stdout) if probe.returncode == 0 else False
    except (ValueError, UnicodeError):
        declared = False
    if declared is None: declared = {}
    if not isinstance(declared, dict):
        raise c.SandboxError("Cannot inspect config helper image volumes; no transfer started")
    target = BOUNDARY.rstrip("/")
    for name in declared:
        if not isinstance(name, str) or not name.startswith("/"):
            raise c.SandboxError("Unsupported image volume declaration; no transfer started")
        name = posixpath.normpath("/" + name.lstrip("/"))
        if name != "/root" and (name == target or name.startswith(target + "/") or target.startswith(name.rstrip("/") + "/")):
            raise c.SandboxError("Global config has an overlapping image volume; transfers require the persistent /root volume alone")
    return image


def volume_operation(m, action, *, incoming=None, outgoing=None, **options):
    """Locked service transport. Binary config bytes never enter logs, argv or notifications."""
    image = _volume_ready(m)
    request = {"action": action, "binding": binding(m), **limits(), **options}
    token = secrets.token_hex(12)
    name = "ocs-config-" + token
    argv = ["docker", "-H", c.docker_endpoint(), "run", "--rm", *c.helper_labels("opencode-config"), "--pull", "never", "--name", name,
            "--network", "none", "--security-opt", "no-new-privileges:true", "--cap-drop", "NET_RAW",
            "--cap-drop", "MKNOD", "--user", "0:0",
            "--label", f"org.opencode-sandbox.config-operation={token}",
            "--mount", f"type=volume,src={c.volume(m)},dst=/root" + ("" if options.get("fresh") else ",volume-nocopy"),
            "--entrypoint", "timeout", "-i", image, "--signal=KILL", "1800s", "python3", "-c",
            _helper_source(), json.dumps(request)]
    # The spool is file-backed, not an unbounded capture_output. The helper codec enforces
    # byte/entry limits before writing; host available-space errors abort without publication.
    # No removal by a guessed name after interruption. --rm and the in-container
    # deadline bound orphan helper life; the journal blocks ordinary lifecycle work.
    maximum = min(request["max_bytes"] + request["max_entries"] * 2048 + 1024**2,
                  max(0, shutil.disk_usage(TMP).free - 128 * 1024**2))
    code, raw = _transfer(argv, incoming, outgoing, max_output=maximum if action == "export" else 0)
    try: result = json.loads(raw)
    except (ValueError, UnicodeError): result = {}
    if code or not isinstance(result, dict) or not result:
        # Do not trust arbitrary stderr/messages emitted by an image's Python executable.
        safe_errors = {
            "Unsupported config entry: only directories, regular files and symlinks can be copied",
            "Config source changed while sampling", "Config source changed while copying; neither side was replaced",
            "Insufficient free space for config staging; original tree preserved",
            "Config tree exceeds the transfer byte limit", "Config tree exceeds the entry limit",
            "Config archive exceeds the transfer byte limit", "Insufficient temporary archive space; copies preserved",
            "Initial OpenCode config destination is not fresh; nothing was replaced",
            "Container config changed again during replacement; review again",
            "Container config changed during the switch; original restored, review again",
            "Unrecognized config transaction; preserved for manual recovery",
            "Unexpected config transaction entries; preserved for manual recovery",
            "Config transaction identities changed; old copy preserved for manual recovery",
            "Committed config transaction does not match its installed tree; preserved",
        }
        if isinstance(result, dict) and isinstance(result.get("error"), str) and result["error"] in safe_errors:
            raise c.SandboxError(result["error"])
        raise c.SandboxError(f"Config volume helper failed; check unsupported entries, image Python/timeout, "
                             f"permissions and available space. Interrupted helper {name} may finish before retry; "
                             "original/recovery copies are retained. Use opencode-configs recover for a pending replacement")
    expected_key = "recovered" if action == "recover" else "conflict" if "conflict" in result else "fingerprint"
    if (expected_key == "conflict" and action != "replace") or set(result) != {expected_key} or (expected_key == "recovered" and result[expected_key] is not True) \
            or (expected_key != "recovered" and not isinstance(result[expected_key], str)) \
            or (expected_key != "recovered" and not re.fullmatch(r"[0-9a-f]{64}", result[expected_key])):
        raise c.SandboxError("Config helper returned an invalid result; no fingerprint or success verified")
    return result


def initialize(m, archive):
    """Creation only: new labelled volume, no destination data to merge or overwrite."""
    if c.volume_state(m) is not None:
        raise c.SandboxError("Initial config copy requires a genuinely new home volume")
    try:
        c.ensure_volume(m)
        volume_operation(m, "replace", incoming=archive, fresh=True)
    except BaseException:
        # Only the volume created by this invocation; never force removal of a busy helper.
        cleaned = False
        try:
            owned = c.assert_volume_owned(m)
            if owned is None:
                cleaned = True
            elif (owned.get("Labels") or {}).get(c.DATA_LABEL) == c.data_id() \
                    and (owned.get("Labels") or {}).get("org.opencode-sandbox.managed") == "true":
                cleaned = c.docker("volume", "rm", c.volume(m), capture=True, check=False).returncode == 0
        except (c.SandboxError, OSError):
            cleaned = False  # Unknown cleanup is never proof that metadata can be discarded.
        if not cleaned:
            error = c.SandboxError("Initial config copy failed; its home volume remains in the error environment. "
                                   "Inspect it and retry cleanup with delete --yes; no OpenCode process was launched")
            error.preserve_environment = True
            raise error from None
        raise


def _environment(m):
    m = c.resolve(m["id"])
    if m.get("operation"): raise c.pending_operation(m)
    return m


def _replacement(m, archive, **options):
    _volume_ready(m)  # An unavailable/unowned volume must not strand a new journal.
    c.mark(m, m.get("status", "ready"), operation="opencode-config")
    try:
        return volume_operation(m, "replace", incoming=archive, **options)
    except BaseException:
        c.mark(m, "error", last_error="Global config transfer interrupted/failed; use opencode-configs recover before other lifecycle operations")
        raise


def _complete(m):
    state = c.inspect_container(m)
    c.mark(m, "ready" if state is None else "running" if state.get("Running") else "stopped",
           operation=None, last_error=None)


def recover(m):
    """Explicitly resolve only this operation's recoverable volume transaction."""
    with c.lock(m["id"]):
        m = c.resolve(m["id"])
        if m.get("operation") != "opencode-config":
            raise c.SandboxError("No interrupted global config transfer")
        volume_operation(m, "recover")
        _complete(m)
        return "Recovered global config transfer. A durably committed replacement is retained; an uncommitted switch is rolled back. Export baseline is unchanged; re-export or review any Apply drift."


def export(m, *, replace=False):
    with c.lock(m["id"]):
        m = _environment(m)
        with workspace(m, create=True) as found:
            if found and not replace:
                raise c.SandboxError("Export exists: confirm replacement; existing host edits will be lost")
            path = export_path(m)
            stage = Path(tempfile.mkdtemp(prefix=".export-", dir=path.parent))
            keep_stage = False
            try:
                (stage / "config").mkdir(mode=0o700)
                with tempfile.TemporaryFile(dir=path.parent) as archive:
                    result = volume_operation(m, "export", outgoing=archive)
                    archive.seek(0)
                    _tree_call(tree.unpack, archive, stage / "config", **limits())
                tree.write_json(stage / MARKER, {"binding": binding(m), "fingerprint": result["fingerprint"]})
                keep_stage = True  # Preserve both copies if a signal obscures rename's outcome.
                try:
                    if found: tree.exchange(stage, path)
                    else: os.rename(stage, path)
                except tree.TreeError as exc:
                    keep_stage = False  # unavailable exchange: no switch occurred
                    raise c.SandboxError(str(exc)) from None
                except OSError:
                    keep_stage = False  # failed atomic syscall: old path is unchanged
                    raise
                try:
                    tree.sync_directory(path.parent)
                except BaseException:
                    keep_stage = True  # an interruption during rollback must retain both copies
                    try:
                        if found: tree.exchange(stage, path)
                        else: os.rename(path, stage)
                    except (OSError, tree.TreeError):
                        raise c.SandboxError(f"Export publication/rollback failed; previous copy retained at {stage}. "
                                             "Inspect both directories; neither recovery copy was deleted") from None
                    keep_stage = False
                    tree.sync_directory(path.parent)
                    raise
                keep_stage = False
            finally:
                if not keep_stage and stage.exists(): shutil.rmtree(stage)
            return str(path / "config")


def apply(m, *, overwrite=None):
    with c.lock(m["id"]):
        m = _environment(m)
        with workspace(m) as found:
            if not found: raise c.SandboxError("No export; Export Config first")
            path, record = found
            previous = dict(m)
            with tempfile.TemporaryFile(dir=path.parent) as archive:
                _tree_call(tree.snapshot, path / "config", archive, allow_missing=False, **limits())
                archive.seek(0)
                result = _replacement(m, archive, expected=overwrite if overwrite is not None else record["fingerprint"])
            if "conflict" in result:
                c.save(previous)  # A canceled drift review must not clear errors/change metadata.
                raise Conflict(result["conflict"])
            # Actual installed-container fingerprint, never the editable host tree's baseline.
            tree.write_json(path / MARKER, {**record, "fingerprint": result["fingerprint"]})
            _complete(m)
            return str(path / "config")


def delete_export(m, *, confirmed=False):
    if not confirmed: raise c.SandboxError("Confirm Delete Export: unapplied host edits will be lost")
    with c.lock(m["id"]):
        m = _environment(m)
        with workspace(m) as found:
            if not found: raise c.SandboxError("No export to delete")
            shutil.rmtree(found[0])
            tree.sync_directory(found[0].parent)


def reload(m, source, *, confirmed=False):
    if not confirmed: raise c.SandboxError("Confirm Reload: " + REPLACE_WARNING)
    # Validation/snapshot before any persistent destination change, including an unavailable source.
    if source is not None:
        with prepared_profile(source) as archive:
            return _reload(m, source, archive)
    with tempfile.TemporaryDirectory(dir=TMP) as empty, tempfile.TemporaryFile(dir=TMP) as archive:
        _tree_call(tree.snapshot, empty, archive, allow_missing=False, **limits())
        archive.seek(0)
        return _reload(m, None, archive)


def _reload(m, source, archive):
    with c.lock(m["id"]):
        m = _environment(m)
        # Reload consent is whole-replacement consent, not a stale Export-based overwrite.
        result = _replacement(m, archive)
        _complete(m)
        return {"source": source or "Empty", "fingerprint": result["fingerprint"]}
