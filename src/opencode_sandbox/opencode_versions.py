"""OpenCode version checks and explicitly approved updates.

Never starts stopped environments merely to inspect their versions.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path

from . import core as c
from . import distros, probes
from . import update_cache as cache

# `opencode --version` prints "opencode v2.1.4"; npm metadata and pins use "2.1.4".
_NUMBER = r"(?:0|[1-9][0-9]*)"
_PRE = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_SEMVER = rf"{_NUMBER}\.{_NUMBER}\.{_NUMBER}(?:-{_PRE}(?:\.{_PRE})*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
VERSION = re.compile(rf"^(?:opencode\s+)?v?({_SEMVER})$")
POLICIES = {"notify", "manual", "pinned"}
PACKAGE = "@opencode/cli"  # OpenCode V2 only (D-007)
MAJOR = 2  # the contract: OpenCode 2.x only; another major needs a new manager release
REGISTRY = "https://registry.npmjs.org/@opencode%2fcli"
METADATA_LIMIT = 8 * 1024 * 1024  # abbreviated packument measured ~2 MiB; finite room for growth


def normalize(raw):
    if not isinstance(raw, str):
        raise c.SandboxError("Version must be a string")
    value = raw.strip().splitlines()[-1].strip() if raw.strip() else ""
    match = VERSION.fullmatch(value)
    if not match or len(value) > 220:
        raise c.SandboxError(f"Unrecognized OpenCode version: {value[:120]!r}")
    return match.group(1)


def supported(version):
    """Normalize a version the manager may install or pin: OpenCode 2.x."""
    # Runtime probes may print a warning/prefix; install targets and pins must be exact data.
    if not isinstance(version, str) or len(version) > 200 or not re.fullmatch(_SEMVER, version):
        raise c.SandboxError("Expected an exact semantic version, such as 2.2.0 (no command/output prefixes)")
    if int(version.split(".")[0]) != MAJOR:
        raise c.SandboxError(f"OpenCode {version} is not supported; this manager installs OpenCode {MAJOR}.x only "
                             f"(npm package {PACKAGE}). Choose a {MAJOR}.x version with --version")
    return version


def _key(version):
    core, _, pre = normalize(version).partition("+")[0].partition("-")
    nums = tuple(int(x) for x in core.split("."))
    # Semver: a pre-release sorts before its release; numeric identifiers numerically.
    ids = tuple((0, int(x), "") if x.isdigit() else (1, 0, x) for x in pre.split(".")) if pre else None
    return nums, (1,) if ids is None else (0, ids)


def compare(a, b):
    """-1, 0 or 1 by semantic-version precedence (not string comparison)."""
    ka, kb = _key(a), _key(b)
    return (ka > kb) - (ka < kb)


def describe(installed, newest):
    if int(normalize(newest).split(".")[0]) != MAJOR:
        return f"npm latest is {newest}: that major version is not supported by this manager (OpenCode {MAJOR}.x only)"
    order = compare(installed, newest)
    if order < 0:
        return f"update available: {installed} -> {newest}"
    if order > 0:
        return f"newer than latest supported stable ({installed} > {newest})"
    return "current"


def _registry_key():
    return f"npm:{REGISTRY}:supported-major={MAJOR}"


def discovery():
    """Local-only discovery snapshot; success and the latest attempt are independent."""
    data = cache.read(_registry_key())
    success = cache.observation(data, "npm-metadata", {"url": REGISTRY, "major": MAJOR})
    if success:
        try:
            supported(success["value"])
            if "-" in success["value"].partition("+")[0]: success = None
        except c.SandboxError: success = None
    attempt = cache.attempt(data)
    stale = success is None or time.time() - success["at"] >= 86400 or bool(attempt and not attempt["ok"])
    return {"success": success, "attempt": attempt, "stale": stale}


def _compatible(metadata):
    if not isinstance(metadata, dict) or not isinstance(metadata.get("versions"), dict):
        raise c.SandboxError("Invalid npm metadata: expected a versions object")
    candidates = []
    for version, record in metadata["versions"].items():
        if not isinstance(record, dict) or record.get("version") != version:
            continue
        try: value = supported(version)
        except c.SandboxError: continue
        if "-" not in value.partition("+")[0]: candidates.append(value)
    if not candidates:
        raise c.SandboxError(f"No supported stable OpenCode {MAJOR}.x release in npm metadata; choose an explicit --version")
    return max(candidates, key=lambda value: (_key(value), value))


def _retry_until(value):
    try:
        if not isinstance(value, str): return None
        delay = int(value) if value.isdigit() else parsedate_to_datetime(value).timestamp() - time.time()
        until = time.time() + max(delay, 0)
        return until if until <= 253402300799 else None  # latest representable UTC date, not an early retry
    except (ValueError, TypeError, OverflowError): return None


def latest(timeout=8):
    """Fresh latest supported stable release, not npm's potentially incompatible latest tag.

    One bounded metadata request, including DNS/TLS/body, without host npm/Node. Persist only a
    small selected result, never the packument. A cached success cannot authorize installation
    after an explicit failure. Rate-limit attempts are retained for later manual/background users.
    """
    data = discovery()
    attempt = data["attempt"]
    retry = (attempt or {}).get("retry_until")
    if type(retry) in (int, float) and time.time() < retry <= 253402300799:
        raise c.SandboxError(f"Cannot check OpenCode npm registry: rate limited; retry after {cache.when(retry)}")
    attempt = {"at": time.time(), "ok": False}
    cache.write(_registry_key(), {"success": data["success"], "attempt": {**attempt, "error": "check did not complete"}})
    try:
        p = c.call([sys.executable, "-I", "-B", str(Path(__file__).with_name("http_probe.py")), REGISTRY, str(timeout), str(METADATA_LIMIT)],
                   capture=True, check=False, timeout=timeout, max_output=METADATA_LIMIT + 1024)
        if p.returncode:
            try: error = json.loads(p.stderr)
            except ValueError: error = {}
            if isinstance(error, dict) and error.get("status"):
                if error["status"] in (429, 503): attempt["retry_until"] = _retry_until(error.get("retry_after", ""))
                raise c.SandboxError(f"HTTP {error['status']}" + (f"; retry after {cache.when(attempt['retry_until'])}" if attempt.get("retry_until") else ""))
            raise c.SandboxError(p.stderr.strip() or "registry request failed")
        value = _compatible(json.loads(p.stdout))
    except (c.SandboxError, OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        attempt["error"] = c.error_text(exc)[:1000]
        cache.write(_registry_key(), {"success": data["success"], "attempt": attempt})
        raise c.SandboxError(f"Cannot check OpenCode npm registry: {exc}") from exc
    cache.write(_registry_key(), {"success": cache.evidence(value, "npm-metadata", {"url": REGISTRY, "major": MAJOR}),
                                  "attempt": {**attempt, "ok": True}})
    return value


def resolve_target(version, m=None):
    """Resolve once before consent; executors receive/revalidate this exact target, never latest."""
    if m is not None and version == "latest" and policy(m)["mode"] == "pinned":
        raise c.SandboxError(f"Environment pinned to OpenCode {policy(m)['version']}; change policy first")
    target = supported(latest() if version == "latest" else version)
    if m is not None and policy(m)["mode"] == "pinned" and target != policy(m)["version"]:
        raise c.SandboxError(f"Environment pinned to OpenCode {policy(m)['version']}; change policy first")
    return target


def policy(m):
    p = m.get("opencode_policy", "notify")
    if p not in POLICIES:
        raise c.SandboxError("Invalid OpenCode update policy")
    pin = m.get("opencode_pin")
    if p == "pinned":
        if not pin:
            raise c.SandboxError("Pinned policy requires a version")
        supported(pin)
    return {"mode": p, "version": pin if p == "pinned" else None}


def set_policy(m, mode, version=None):
    if mode not in POLICIES:
        raise c.SandboxError("Policy must be notify, manual or pinned")
    if mode == "pinned":
        if not version:
            raise c.SandboxError("Pinned policy requires --version")
        version = supported(version)
    elif version is not None:
        raise c.SandboxError("--version only applies to pinned policy")
    with c.lock(m["id"]):
        m = c.resolve(m["id"])
        if m.get("operation"):
            raise c.pending_operation(m)
        m["opencode_policy"] = mode
        m["opencode_pin"] = version if mode == "pinned" else None
        c.save(m)
    return policy(m)


def image_version(image):
    result = image_observation(image, check=True)
    if result.get("error"): raise c.SandboxError(result["error"])
    return result["observation"]["value"]


def image_observation(image, *, check=False):
    """Labels are build provenance only; only explicit Check runs a bounded immutable helper."""
    p = c.docker("image", "inspect", "--format", "{{.Id}}|{{json .Config.Labels}}", image, capture=True)
    try:
        image_id, raw = p.stdout.strip().split("|", 1)
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id): raise ValueError("invalid image ID")
        labels = json.loads(raw) or {}
        if not isinstance(labels, dict): raise TypeError("invalid labels")
    except (ValueError, TypeError) as exc:
        raise c.SandboxError("Invalid image version inspection") from exc
    identity = {"image": image_id, "endpoint": c.docker_endpoint()}
    key = "image:" + identity["endpoint"] + ":" + image_id
    data = cache.read(key)
    old = cache.observation(data, "image-exec", identity)
    if old:
        try:
            if normalize(old["value"]) != old["value"]: old = None
        except c.SandboxError: old = None
    result = {"image": image_id, "build_version": labels.get(VERSION_LABEL), "observation": old,
              "attempt": cache.attempt(data), "verification": "last-verified" if old else "unknown"}
    if not check: return result
    attempt = {"at": time.time(), "ok": False}
    try:
        value = normalize(probes.image(image_id, "opencode", "--version", timeout=probes.EXEC_TIMEOUT).stdout)
    except c.SandboxError as exc:
        attempt["error"] = c.error_text(exc)[:1000]
        cache.write(key, {"success": old, "attempt": attempt})
        return {**result, "error": attempt["error"], "attempt": attempt}
    observation = cache.evidence(value, "image-exec", identity)
    attempt["ok"] = True
    cache.write(key, {"success": observation, "attempt": attempt})
    return {**result, "observation": observation, "attempt": attempt, "verification": "verified"}


def environment_history(m):
    """Docker-free dated history, never proof of the current container or its running state."""
    data = cache.read(_environment_key(m))
    old = cache.observation(data, "container-exec")
    if old and (old["identity"].get("lifecycle") != _lifecycle(m)
                or old["identity"].get("environment") != m["id"] or old["identity"].get("data") != c.data_id()):
        old = None
    if old:
        try:
            if normalize(old["value"]) != old["value"]: old = None
        except c.SandboxError: old = None
    if m.get("operation"): old = None
    result = {"state": "unknown", "version": old["value"] if old else None, "observation": old,
              "verification": "history-unverified" if old else "unknown", "attempt": cache.attempt(data)}
    if m.get("operation"): result["recovery"] = str(c.pending_operation(m))
    return result


def environment_version(m, *, check=True):
    """Actual or last-verified evidence; inaccessible Docker only permits qualified history."""
    m = c.resolve(m["id"])
    try:
        return _environment_version(m, check=check)
    except c.SandboxError as exc:
        result = environment_history(m)
        old = result["observation"]
        attempt = {"at": time.time(), "ok": False, "error": c.error_text(exc)[:1000]}
        if check: cache.write(_environment_key(m), {"success": old, "attempt": attempt})
        if not old:
            raise
        return {**result, "error": c.error_text(exc), "attempt": attempt if check else result["attempt"]}


def _environment_version(m, *, check=True):
    # Re-read metadata: historical completed-update fields do not verify the current binary.
    m = c.resolve(m["id"])
    state = c.inspect_container(m)
    if state is None:
        result = {"state": "not-created", "version": None, "observation": None}
        if m.get("operation"): result["recovery"] = str(c.pending_operation(m))
        return result
    identity = _environment_identity(m)
    data = cache.read(_environment_key(m))
    old = cache.observation(data, "container-exec", identity)
    if old:
        try:
            if normalize(old["value"]) != old["value"]: old = None
        except c.SandboxError: old = None
    attempt = cache.attempt(data)
    if attempt and attempt.get("identity") != identity: attempt = None
    result = {"state": "running" if state.get("Running") else "stopped", "version": old["value"] if old else None,
              "observation": old, "verification": "last-verified" if old else "unknown", "attempt": attempt}
    if m.get("operation"):
        return {**result, "version": None, "observation": None, "verification": "unknown",
                "recovery": str(c.pending_operation(m))}
    if not check or not state.get("Running"):
        return result
    attempt = {"at": time.time(), "ok": False, "identity": identity}
    cache.write(_environment_key(m), {"success": old, "attempt": {**attempt, "error": "probe did not complete"}})
    try:
        value = _exec_version(m, container_id=identity["container"])
        current = c.resolve(m["id"])
        if current.get("operation") or _environment_identity(current) != identity:
            old = None
            result.update(version=None, observation=None, verification="unknown")
            raise c.SandboxError("Environment/container changed during the version check; no fresh result verified")
    except c.SandboxError as exc:
        attempt["error"] = c.error_text(exc)[:1000]
        cache.write(_environment_key(m), {"success": old, "attempt": attempt})
        return {**result, "error": attempt["error"], "attempt": attempt}
    observation = cache.evidence(value, "container-exec", identity)
    attempt["ok"] = True
    cache.write(_environment_key(m), {"success": observation, "attempt": attempt})
    return {**result, "version": value, "observation": observation, "verification": "verified", "attempt": attempt}


def _environment_key(m):
    return "environment:" + m["id"]


def _lifecycle(m):
    # Stop/start/status/policy changes retain dated evidence. Replacement/update/restore do not.
    fields = {key: m.get(key) for key in ("id", "created", "image", "custom_image", "opencode_update")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def _environment_identity(m):
    fmt = '{{.Id}}|{{.Image}}|{{index .Config.Labels "org.opencode-sandbox.id"}}'
    p = c.docker("container", "inspect", "--format", fmt, c.cname(m), capture=True)
    parts = p.stdout.strip().split("|")
    if len(parts) != 3 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]) or not re.fullmatch(r"sha256:[0-9a-f]{64}", parts[1]):
        raise c.SandboxError("Invalid immutable container/image identity in version inspection")
    if parts[2] != m["id"]: raise c.SandboxError("Container name collision / ownership mismatch in version inspection")
    return {"environment": m["id"], "container": parts[0], "image": parts[1],
            "endpoint": c.docker_endpoint(), "data": c.data_id(), "lifecycle": _lifecycle(m)}


def versions():
    """One broken environment (bad policy, Docker error) must not hide the others."""
    out = []
    for m in c.all_envs():
        try:
            out.append({"name": m["name"], "id": m["id"], "policy": policy(m), **environment_version(m)})
        except Exception as exc:  # noqa: BLE001 — batch inventory reports each failure with its type
            out.append({"name": m["name"], "id": m["id"], "policy": None, "state": f"error: {c.error_text(exc)}", "version": None})
    return out


def versions_report(*, check=False):
    """Return (lines, errors) for CLI/TUI inventory and an independent optional npm check.

    Keep local rows even when discovery fails, and still attempt discovery if local inventory
    fails. Callers must display the errors and signal the partial failure, not just the rows.
    """
    errors = []
    try:
        items = versions()
    except Exception as exc:  # noqa: BLE001 — report boundary; never hide the independent source
        items = []
        errors.append(f"Local version inventory failed: {c.error_text(exc)}")
    newest = None
    if check:
        try:
            newest = latest()
        except Exception as exc:  # noqa: BLE001 — report boundary; retain local inventory on failure
            errors.append(f"npm registry check failed: {c.error_text(exc)}")
    cached = discovery()
    if newest is None and cached["success"]:
        newest = cached["success"]["value"]
        lines = [f"npm registry (cached; last checked {cache.when(cached['success']['at'])}): {newest}"]
    else:
        lines = [f"npm registry: {newest}"] if newest is not None else []
    for item in items:
        try:
            line = f"{item['name']}: {environment_line(item, newest)}"
            (errors if item["policy"] is None else lines).append(line)
            if item.get("error"): errors.append(f"{item['name']}: version check failed: {item['error']}")
        except Exception as exc:  # noqa: BLE001 — one failed row must not discard the other rows
            errors.append(f"{item['name']}: check failed ({c.error_text(exc)})")
    return lines, errors


def _content(image):
    """Layers + config + creation time. The image ID is not usable: with the containerd
    image store every build gets a new manifest/attestation digest for identical content."""
    return c.docker("image", "inspect", "--format", "{{json .RootFS.Layers}}|{{json .Config}}|{{.Created}}",
                    image, capture=True).stdout.strip()


def _unused_base_tag(distro, tag):
    """Under publication: never overwrite a colliding candidate or rollback-copy tag."""
    if c.inspect_base_image(distro, tag, missing=True) is not None:
        raise c.SandboxError(f"Base image tag already exists: {tag}; refusing to overwrite it")
    return tag


def update_base(version, distro=None, *, keep_previous=True):
    """Build and verify a candidate base image for a distribution, then replace the tag.

    With keep_previous the replaced image stays available as `<repo>:<distro>-previous-<hex>`.
    """
    c.ensure_runtime()
    d = distros.get(distros.DEFAULT if distro is None else distro)
    # Resolve "latest" first: the literal build arg "latest" hits Docker's layer
    # cache, so the npm install step was never re-run and nothing was updated.
    version = resolve_target(version)
    with c.base_lock(d.id, "build"):
        c.require_docker_space("a base image build")
        candidate = distros.candidate_tag(d, __import__("secrets").token_hex(6))
        with c.base_lock(d.id, "publication"):
            original = c.inspect_base_image(d, d.image, missing=True)
            _unused_base_tag(d, candidate)
        try:
            c.build_image(d, version, candidate)
            previous = None
            with c.base_lock(d.id, "publication"):  # not held throughout a long build
                old = c.inspect_base_image(d, d.image, missing=True)
                if (old or {}).get("Id") != (original or {}).get("Id"):
                    raise c.SandboxError("Base image changed during the build; refusing replacement; retry after review")
                built = c.inspect_base_image(d, candidate)
                if old and _content(old["Id"]) == _content(built["Id"]):
                    return {"version": version, "previous_image": None, "image": d.image, "unchanged": True}
                if old and keep_previous:
                    previous = _unused_base_tag(d, distros.previous_tag(d, __import__("secrets").token_hex(6)))
                    c.docker("tag", old["Id"], previous)
                c.docker("tag", built["Id"], d.image)
                if old and not keep_previous:
                    # Docker refuses deletion while a container or another tag still uses it.
                    c.docker("image", "rm", old["Id"], capture=True, check=False)
            return {"version": version, "previous_image": previous, "image": d.image}
        finally:
            with c.runtime_feedback(progress=None, cancelled=None), c.base_lock(d.id, "publication"):
                if c.inspect_base_image(d, candidate, missing=True):
                    c.docker("image", "rm", candidate, capture=True, check=False)


# The shared install script of the image builds also performs in-container updates.
INSTALL = ("sh", "-c", (distros.IMAGES / "common" / "install-opencode.sh").read_text(encoding="utf-8"),
           "ocs-install-opencode")
UPDATE_OP = "opencode-update"
# OpenCode's own update check/self-update (TUI start; `update` in the user's global config) is
# switched off in every container the manager creates (D-019): measured with 2.1.4, `update: auto`
# and `opencode upgrade` run `npm install --global --force` under docker exec's umask 0000, leaving
# world-writable files, all four platform packages (~940 MB) and a ~470 MB npm cache in /root.
SELF_UPDATE_ENV = "OPENCODE_DISABLE_AUTOUPDATE=1"
VERSION_LABEL = distros.LABEL + "opencode-version"
_VERSION_FORMAT = '{{index .Config.Labels "' + VERSION_LABEL + '"}}'


def check_pin(m):
    """Before a pinned environment gets a container from its registry base image: refuse when the
    image was built with another OpenCode version (its label). Derived images (runtime, snapshot,
    checkpoint, backup) carry the environment's own installation; custom images have no label."""
    p = policy(m)
    if p["mode"] != "pinned" or m.get("image") or m.get("distro") is None:
        return
    d = distros.get(m["distro"])
    out = c.docker("image", "inspect", "--format", _VERSION_FORMAT, d.image,
                   capture=True, check=False)
    built = (out.stdout or "").strip() if out.returncode == 0 else ""
    if built and built != "<no value>" and built != p["version"]:
        raise c.SandboxError(
            f"{m['name']} is pinned to OpenCode {p['version']}, but base image {d.image} has OpenCode {built}. "
            f"Run: opencode-sandbox opencode update-base --distro {d.id} --version {p['version']}, "
            f"or change the policy: opencode-sandbox opencode policy-set {m['name']} notify")


def comparison(item, newest=None, *, unsolicited=False):
    """Availability is information, not execution eligibility; pins and Manual still compare."""
    p, version = item.get("policy"), item.get("version")
    if not p or not version or not newest or (unsolicited and p["mode"] != "notify"): return None
    return describe(version, newest)


def environment_line(item, newest=None):
    """Shared explicit CLI/TUI comparison. Dated evidence never becomes a fresh verification."""
    p, version = item.get("policy"), item.get("version")
    if p is None:
        return item["state"]
    if item.get("recovery"):
        return f"{p['mode']}; Unknown; {item['recovery']}"
    if version is None:
        if item["state"] == "running":
            return f"{p['mode']}; `opencode --version` failed in the container (broken or missing; repair: stop, then opencode update NAME)"
        return f"{p['mode']}; {'not checked (stopped); Unknown' if item['state'] == 'stopped' else item['state']}"
    suffix = ""
    if item.get("verification") in ("last-verified", "history-unverified") and item.get("observation"):
        suffix = f"; last verified {cache.when(item['observation']['at'])} ({item['state']}; not a fresh check)"
        if item["verification"] == "history-unverified": suffix += "; current container identity unverified"
    if item.get("error"): suffix += f"; latest probe failed: {item['error']}"
    if p["mode"] == "pinned":
        if normalize(version) != p["version"]:
            status = f"pinned {p['version']}, but {'last verified' if suffix else 'runs'} {version} (changed outside the manager)"
        else: status = "pinned"
    else: status = p["mode"]
    available = comparison(item, newest) if item.get("verification") != "history-unverified" else None
    if available:
        status = available if p["mode"] == "notify" else f"{status}; {available}"
    return f"{version}; {status}{suffix}"


def _exec_version(m, *, container_id=None):
    p = probes.exec(m, "opencode", "--version", container_id=container_id)
    if p.returncode: raise c.SandboxError(f"OpenCode version probe failed (exit {p.returncode})")
    return normalize(p.stdout)


def update_blocker(m, state, target):
    """Pure shared eligibility, also re-evaluated under the execution lock; no network/start."""
    supported(target)
    if m.get("operation"): return str(c.pending_operation(m))
    p = policy(m)
    if p["mode"] == "pinned" and target != p["version"]:
        return f"Environment pinned to OpenCode {p['version']}; change policy first"
    if c.runtime_settings(m)["network"] == "none":
        return ("OpenCode update downloads from npm but this environment has network=none; "
                "update the base image instead, or temporarily change the network with config apply NAME --network bridge")
    if state is None or state.get("Running"):
        return "OpenCode update requires an existing stopped container"
    return None


@dataclass(frozen=True)
class EnvironmentUpdatePlan:
    target: str
    identity: tuple[tuple[str, str], ...]


def prepare_environment_update(m, version):
    target = resolve_target(version, m)
    c.ensure_runtime(False)
    m = c.resolve(m["id"])
    state = c.inspect_container(m)
    reason = update_blocker(m, state, target)
    if reason: raise c.SandboxError(reason)
    return EnvironmentUpdatePlan(target, tuple(sorted(_environment_identity(m).items())))


def _remember_update(m, value, identity, at):
    """Actual runtime verification just completed; journal closure changes its lifecycle binding."""
    observation = cache.evidence(value, "container-exec", {**identity, "lifecycle": _lifecycle(m)})
    observation["at"] = at
    cache.write(_environment_key(m), {"success": observation, "attempt": {"at": at, "ok": True, "identity": observation["identity"]}})


def _restore_checkpoint(m, result):
    """Replace the container by one created (at the next start) from the update's checkpoint: the
    system layer exactly as before the update; /root volume and /workspace are not touched. Uses the
    runtime-recreate journal, so a crash here is finished by `config recover`. Caller holds the lock."""
    record = m["opencode_update"]
    checkpoint = record["checkpoint"]
    if c.docker("image", "inspect", checkpoint, capture=True, check=False).returncode:
        raise c.missing_image(m, checkpoint, "opencode-sandbox opencode update-recover {name}")
    state = c.inspect_container(m)
    if state is not None:
        c.assert_volume_owned(m)
        if state.get("Running"):
            c.docker("stop", c.cname(m), capture=True)
    superseded = m.get("image")
    m["image"] = m["last_snapshot"] = checkpoint
    record.update(state="rolled-back", result=result, at=c.now())
    c.mark(m, "reconfiguring", operation="runtime-recreate", superseded_image=superseded)
    if state is not None:
        c.docker("rm", c.cname(m), capture=True)
    c._finish_reconfigure(m)


def update_environment(m, version, *, plan=None):
    """Update OpenCode in a stopped container with the image build's install script (D-019).

    Journal `opencode-update` with a docker-commit checkpoint of the container's system layer,
    taken before anything changes. On a failure, and in `update_recover` after a crash, the
    container is replaced by one created from that checkpoint (exactly the previous system
    layer; the /root volume and /workspace are not part of it and not touched). After a success
    the checkpoint stays the environment's rollback point (`rollback_environment`).
    """
    target = supported(version) if plan is not None else resolve_target(version, m)
    if plan is not None and target != plan.target:
        raise c.SandboxError("Update target differs from the confirmed target; review again")
    c.ensure_runtime(False)
    with c.lock(m["id"]):
        m = c.resolve(m["id"])
        if m.get("operation"):
            raise c.pending_operation(m)
        # Policy/network refusals precede Docker inspection, as in the original executor.
        reason = update_blocker(m, {"Running": False}, target)
        if reason: raise c.SandboxError(reason)
        state = c.inspect_container(m)
        reason = update_blocker(m, state, target)
        if reason: raise c.SandboxError(reason)
        if plan is not None and tuple(sorted(_environment_identity(m).items())) != plan.identity:
            raise c.SandboxError("Environment/container changed since confirmation; review again")
        c.recheck_mount(m)  # the update starts it
        c.require_docker_space("an OpenCode update (checkpoint + npm install)")
        identity = _environment_identity(m)
        checkpoint = "ocs-checkpoint:" + m["id"] + "-" + __import__("secrets").token_hex(4)
        c.docker("commit", c.cname(m), checkpoint, capture=True)
        before = m.get("opencode_update")
        record = {"state": "applying", "from": None, "to": target, "checkpoint": checkpoint, "at": c.now(), "result": None}
        m["opencode_update"] = record
        c.mark(m, "updating", operation=UPDATE_OP)  # journal: from here on a crash is rolled back
        try:
            c.docker("start", c.cname(m), capture=True)
            try:
                record["from"] = _exec_version(m, container_id=identity["container"])
                verified_at = time.time()
            except c.SandboxError:
                # A broken installation (e.g. a user's `opencode upgrade` on Arch): the
                # install script below is the repair. Its checkpoint holds the broken state.
                record["from"] = None
            c.save(m)
            if record["from"] != target:
                c.docker("exec", c.cname(m), *INSTALL, target, capture=True)
                installed = _exec_version(m, container_id=identity["container"])
                verified_at = time.time()
                if installed != target:
                    raise c.SandboxError(f"installed {installed}, expected {target}")
            c.docker("stop", c.cname(m), capture=True)
        except Exception as exc:  # any failure rolls back to the checkpoint, then is raised
            failure = c.error_text(exc)
            try:
                _restore_checkpoint(m, f"update to {target} failed ({failure[:300]}); rolled back to the checkpoint")
            except Exception as restore_exc:  # noqa: BLE001 — reported together with the update failure
                raise c.SandboxError(f"OpenCode update failed: {failure}; rollback failed: {c.error_text(restore_exc)}. "
                                     f"Run: opencode-sandbox opencode update-recover {m['name']}") from exc
            raise c.SandboxError(f"OpenCode update failed: {failure}. Rolled back: the container is recreated from "
                                 f"checkpoint {checkpoint} at the next start (system layer as before the update; "
                                 "/root and /workspace untouched).") from exc
        if record["from"] == target:
            m["opencode_update"] = before
            if before is None:
                m.pop("opencode_update")
            c.mark(m, "stopped", operation=None, last_error=None)
            _remember_update(m, target, identity, verified_at)
            c.docker("image", "rm", checkpoint, capture=True, check=False)
            return {"version": target, "previous_version": target, "unchanged": True}
        record.update(state="done", at=c.now(), result=f"updated {record['from'] or 'unknown (broken)'} -> {target}")
        c.mark(m, "stopped", operation=None, last_error=None)
        _remember_update(m, target, identity, verified_at)
        return {"version": target, "previous_version": record["from"], "checkpoint": checkpoint}


def update_recover(m):
    """Finish an interrupted update by rolling back to its checkpoint (never by guessing whether
    npm completed). Run `update` again afterwards if wanted."""
    c.ensure_runtime(False)
    with c.lock(m["id"]):
        m = c.resolve(m["id"])
        if m.get("operation") != UPDATE_OP:
            raise c.SandboxError("No interrupted OpenCode update")
        if not (m.get("opencode_update") or {}).get("checkpoint"):
            raise c.SandboxError("The update journal has no checkpoint; manual recovery required")
        _restore_checkpoint(m, "interrupted; rolled back to the checkpoint by update-recover")
        return {"image": m["image"], "rolled_back": True}


def rollback_environment(m):
    """Undo the last successful update: the container is recreated from its checkpoint. The current
    system layer (also later changes) is kept as an ocs-snapshot first: committed from the container,
    or, when a runtime change already removed the container, the environment's derived image tagged."""
    c.ensure_runtime(False)
    with c.lock(m["id"]):
        m = c.resolve(m["id"])
        if m.get("operation"):
            raise c.pending_operation(m)
        record = m.get("opencode_update") or {}
        if record.get("state") != "done" or not record.get("checkpoint"):
            raise c.SandboxError("No completed OpenCode update to roll back")
        p = policy(m)
        if p["mode"] == "pinned" and record["from"] != p["version"]:
            raise c.SandboxError(f"Environment pinned to OpenCode {p['version']}; change policy first")
        if c.docker("image", "inspect", record["checkpoint"], capture=True, check=False).returncode:
            raise c.SandboxError(f"Checkpoint {record['checkpoint']} no longer exists (pruned?); cannot roll back")
        state = c.inspect_container(m)
        if state is not None and state.get("Running"):
            raise c.SandboxError("Stop the environment before rolling back OpenCode")
        snapshot = None
        if state is not None:
            snapshot = c.snapshot(m)
        elif m.get("image"):
            snapshot = c.snapshot_tag(m)
            c.docker("tag", m["image"], snapshot)
        _restore_checkpoint(m, f"rolled back {record['to']} -> {record['from'] or 'unknown (broken)'}" + (f"; previous system layer kept as {snapshot}" if snapshot else ""))
        return {"version": record["from"], "rolled_back_from": record["to"], "snapshot": snapshot, "image": m["image"]}


@dataclass(frozen=True)
class BaseRollbackCopy:
    image_id: str
    aliases: tuple[str, ...]
    definition: distros.ImageDefinition
    version: str | None  # build label only; execution still verifies the actual image


@dataclass(frozen=True)
class BaseRollbackInventory:
    distro: str
    endpoint: str
    current_id: str | None
    copies: tuple[BaseRollbackCopy, ...]


@dataclass(frozen=True)
class BaseRollbackPlan:
    distro: str
    endpoint: str
    current_id: str | None
    selected: BaseRollbackCopy


def _base_rollback_inventory(d):
    """Caller holds publication. Names find copies; full inspection proves their ownership."""
    pattern = re.compile(re.escape(distros.previous_tag(d, "")) + r"[0-9a-f]{12}")
    tags = sorted({t for t in c.docker("image", "ls", "--format", "{{.Repository}}:{{.Tag}}",
                                     distros.REPOSITORY, capture=True).stdout.split() if pattern.fullmatch(t)})
    images, aliases = {}, {}
    for tag in tags:
        info = c.inspect_base_image(d, tag)
        images[info["Id"]] = info
        aliases.setdefault(info["Id"], []).append(tag)
    copies = []
    for image_id, info in sorted(images.items()):
        labels = info["Config"]["Labels"]
        label = labels.get(VERSION_LABEL)
        version = normalize(label) if label and label != "<no value>" else None
        copies.append(BaseRollbackCopy(image_id, tuple(aliases[image_id]),
                                       distros.image_definition(d.id, labels), version))
    current = c.inspect_base_image(d, d.image, missing=True)
    return BaseRollbackInventory(d.id, c.docker_endpoint(), (current or {}).get("Id"), tuple(copies))


def base_rollback_inventory(distro=None):
    """Read-only, alias-consolidated copies. No helper containers, network lookup or date ranking."""
    c.ensure_runtime()
    d = distros.get(distros.DEFAULT if distro is None else distro)
    with c.base_lock(d.id, "publication"):
        return _base_rollback_inventory(d)


def format_base_rollback_copies(inventory):
    lines = []
    for item in inventory.copies:
        lines.append(f"{item.image_id} | OpenCode {item.version or 'unknown'} (build label) | "
                     f"{item.definition.distro} {item.definition.version}, definition revision {item.definition.revision}")
        lines.extend(f"  {tag}" for tag in item.aliases)
    return lines or [f"No rollback copy of {distros.get(inventory.distro).image}"]


def select_base_rollback(inventory, copy=None):
    """Resolve an exact tag/full immutable ID before consent; confirmation bypass never chooses."""
    if not inventory.copies:
        raise c.SandboxError(f"No rollback copy of {distros.get(inventory.distro).image}")
    if copy is None:
        if len(inventory.copies) != 1:
            raise c.SandboxError("Several distinct rollback copies; select one with --copy TAG_OR_FULL_IMAGE_ID "
                                 "(also required with --yes). List them with opencode-sandbox opencode rollback-base "
                                 f"--distro {inventory.distro} --list\n" + "\n".join(format_base_rollback_copies(inventory)))
        selected = inventory.copies[0]
    else:
        selected = next((item for item in inventory.copies if copy == item.image_id or copy in item.aliases), None)
        if selected is None:
            raise c.SandboxError("Rollback copy not found; use an exact listed tag or full sha256 image ID (--list)")
    return BaseRollbackPlan(inventory.distro, inventory.endpoint, inventory.current_id, selected)


def _recheck_base_rollback(d, plan):
    """Under publication, bind both tag removal and replacement to the consented identities."""
    if d.id != plan.distro or plan.endpoint != c.docker_endpoint():
        raise c.SandboxError("Rollback selection belongs to another distribution or daemon; review again")
    for tag in plan.selected.aliases:
        if c.inspect_base_image(d, tag)["Id"] != plan.selected.image_id:
            raise c.SandboxError("Base image or rollback copy changed since selection or during verification; review again")
    selected = c.inspect_base_image(d, plan.selected.image_id)
    if selected["Id"] != plan.selected.image_id:
        raise c.SandboxError("Rollback copy identity changed; review again")
    current = c.inspect_base_image(d, d.image, missing=True)
    if (current or {}).get("Id") != plan.current_id:
        raise c.SandboxError("Base image changed since selection or during verification; review again")
    return selected


def rollback_base(distro=None, *, copy=None, plan=None):
    """Verify and swap an explicitly selected copy; preserve the replaced base, never guess order."""
    c.ensure_runtime()
    d = distros.get((plan.distro if plan else distros.DEFAULT) if distro is None else distro)
    if plan is not None and copy is not None:
        raise c.SandboxError("Supply a rollback plan or copy, not both")
    with c.base_lock(d.id, "build"):
        with c.base_lock(d.id, "publication"):
            if plan is None:
                plan = select_base_rollback(_base_rollback_inventory(d), copy)
            selected = _recheck_base_rollback(d, plan)
        image_id = plan.selected.image_id
        label = selected["Config"]["Labels"].get(VERSION_LABEL)
        version = supported(label) if label and label != "<no value>" else supported(image_version(image_id))
        c.verify_image(d, image_id, version)
        with c.base_lock(d.id, "publication"):
            _recheck_base_rollback(d, plan)
            if plan.current_id == image_id:
                return {"image": d.image, "version": version, "previous_image": None, "unchanged": True}
            kept = None
            if plan.current_id:
                kept = _unused_base_tag(d, distros.previous_tag(d, __import__("secrets").token_hex(6)))
                c.docker("tag", plan.current_id, kept)
            c.docker("tag", image_id, d.image)
            for tag in plan.selected.aliases:
                c.docker("image", "rm", tag, capture=True)  # only aliases: d.image now names this image
        return {"image": d.image, "version": version, "previous_image": kept}
