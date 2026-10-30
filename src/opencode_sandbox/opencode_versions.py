"""OpenCode version checks and explicitly approved updates.

Never starts stopped environments merely to inspect their versions.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from . import core as c
from . import distros, probes

# `opencode --version` prints "opencode v2.1.4"; npm metadata and pins use "2.1.4".
VERSION = re.compile(r"^(?:opencode\s+)?v?(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)$")
POLICIES = {"notify", "manual", "pinned"}
PACKAGE = "@opencode/cli"  # OpenCode V2 only (D-007)
MAJOR = 2  # the contract: OpenCode 2.x only; another major needs a new manager release
REGISTRY = "https://registry.npmjs.org/@opencode%2fcli/latest"


def normalize(raw):
    if not isinstance(raw, str):
        raise c.SandboxError("Version must be a string")
    value = raw.strip().splitlines()[-1].strip() if raw.strip() else ""
    match = VERSION.fullmatch(value)
    if not match:
        raise c.SandboxError(f"Unrecognized OpenCode version: {value[:120]!r}")
    return match.group(1)


def supported(version):
    """Normalize a version the manager may install or pin: OpenCode 2.x."""
    version = normalize(version)
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
        return f"newer than npm latest ({installed} > {newest})"
    return "current"


def latest(timeout=8):
    """One total bounded npm request, including DNS/TLS/body reads; no host npm or Node."""
    try:
        p = c.call([sys.executable, "-I", "-B", str(Path(__file__).with_name("http_probe.py")), REGISTRY, str(timeout)],
                   capture=True, check=False, timeout=timeout, max_output=65536)
        if p.returncode: raise c.SandboxError(p.stderr.strip() or "registry request failed")
        return normalize(json.loads(p.stdout)["version"])
    except (c.SandboxError, OSError, ValueError, KeyError, TypeError) as exc:
        raise c.SandboxError(f"Cannot check OpenCode npm registry: {exc}") from exc


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
    p = probes.image(image, "opencode", "--version", timeout=probes.EXEC_TIMEOUT)
    return normalize(p.stdout)


def environment_version(m):
    state = c.inspect_container(m)
    if state is None:
        return {"state": "not-created", "version": None}
    if not state.get("Running"):
        return {"state": "stopped", "version": None}
    p = probes.exec(m, "opencode", "--version")
    try:
        return {"state": "running", "version": normalize(p.stdout) if p.returncode == 0 else None}
    except c.SandboxError:
        return {"state": "running", "version": None}


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
    lines = [f"npm registry: {newest}"] if newest is not None else []
    for item in items:
        try:
            line = f"{item['name']}: {environment_line(item, newest)}"
            (errors if item["policy"] is None else lines).append(line)
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
    version = supported(latest() if version == "latest" else version)
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


def environment_line(item, newest=None):
    """How `versions`/the dashboard report one environment. Only the notify policy reports updates
    (`newest` from the registry); pinned reports a version changed outside the manager."""
    p, version = item.get("policy"), item.get("version")
    if p is None:
        return item["state"]
    if version is None:
        if item["state"] == "running":
            return f"{p['mode']}; `opencode --version` failed in the container (broken or missing; repair: stop, then opencode update NAME)"
        return f"{p['mode']}; {'not checked (stopped)' if item['state'] == 'stopped' else item['state']}"
    if p["mode"] == "pinned":
        if normalize(version) != p["version"]:
            return f"{version}; pinned {p['version']}, but runs {version} (changed outside the manager)"
        return f"{version}; pinned"
    if p["mode"] == "manual" or newest is None:
        return f"{version}; {p['mode']}"
    return f"{version}; {describe(version, newest)}"


def _exec_version(m):
    p = probes.exec(m, "opencode", "--version")
    if p.returncode: raise c.SandboxError(f"OpenCode version probe failed (exit {p.returncode})")
    return normalize(p.stdout)


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


def update_environment(m, version):
    """Update OpenCode in a stopped container with the image build's install script (D-019).

    Journal `opencode-update` with a docker-commit checkpoint of the container's system layer,
    taken before anything changes. On a failure, and in `update_recover` after a crash, the
    container is replaced by one created from that checkpoint (exactly the previous system
    layer; the /root volume and /workspace are not part of it and not touched). After a success
    the checkpoint stays the environment's rollback point (`rollback_environment`).
    """
    if version == "latest" and policy(m)["mode"] == "pinned":
        raise c.SandboxError(f"Environment pinned to OpenCode {policy(m)['version']}; change policy first")
    target = supported(latest() if version == "latest" else version)
    c.ensure_runtime(False)
    with c.lock(m["id"]):
        m = c.resolve(m["id"])
        if m.get("operation"):
            raise c.pending_operation(m)
        p = policy(m)
        if p["mode"] == "pinned" and target != p["version"]:
            raise c.SandboxError(f"Environment pinned to OpenCode {p['version']}; change policy first")
        if c.runtime_settings(m)["network"] == "none":
            # npm retried for >10 minutes and was left running if interrupted.
            raise c.SandboxError("OpenCode update downloads from npm but this environment has network=none; "
                                 "update the base image instead, or temporarily change the network with config apply NAME --network bridge")
        state = c.inspect_container(m)
        if state is None or state.get("Running"):
            raise c.SandboxError("OpenCode update requires an existing stopped container")
        c.recheck_mount(m)  # the update starts it
        c.require_docker_space("an OpenCode update (checkpoint + npm install)")
        checkpoint = "ocs-checkpoint:" + m["id"] + "-" + __import__("secrets").token_hex(4)
        c.docker("commit", c.cname(m), checkpoint, capture=True)
        before = m.get("opencode_update")
        record = {"state": "applying", "from": None, "to": target, "checkpoint": checkpoint, "at": c.now(), "result": None}
        m["opencode_update"] = record
        c.mark(m, "updating", operation=UPDATE_OP)  # journal: from here on a crash is rolled back
        try:
            c.docker("start", c.cname(m), capture=True)
            try:
                record["from"] = _exec_version(m)
            except c.SandboxError:
                # A broken installation (e.g. a user's `opencode upgrade` on Arch): the
                # install script below is the repair. Its checkpoint holds the broken state.
                record["from"] = None
            c.save(m)
            if record["from"] != target:
                c.docker("exec", c.cname(m), *INSTALL, target, capture=True)
                installed = _exec_version(m)
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
            c.docker("image", "rm", checkpoint, capture=True, check=False)
            return {"version": target, "previous_version": target, "unchanged": True}
        record.update(state="done", at=c.now(), result=f"updated {record['from'] or 'unknown (broken)'} -> {target}")
        c.mark(m, "stopped", operation=None, last_error=None)
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
