"""OpenCode version checks and explicitly approved updates.

Never starts stopped environments merely to inspect their versions.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from . import core as c
from . import distros

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
    """Read npm registry metadata without requiring npm or Node on the host."""
    request = urllib.request.Request(REGISTRY, headers={"Accept": "application/json", "User-Agent": "opencode-sandbox-manager"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise c.SandboxError(f"npm registry HTTP {response.status}")
            raw = response.read(65537)
            if len(raw) > 65536:
                raise c.SandboxError("npm registry response too large")
        return normalize(json.loads(raw)["version"])
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
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
    p = c.docker("run", "--rm", "--network", "none", "--security-opt", "no-new-privileges:true",
                 *c.helper_labels("version-probe"), "--entrypoint", "opencode", image,
                 "--version", capture=True)
    return normalize(p.stdout)


def environment_version(m):
    state = c.inspect_container(m)
    if state is None:
        return {"state": "not-created", "version": None}
    if not state.get("Running"):
        return {"state": "stopped", "version": None}
    p = c.docker("exec", c.cname(m), "opencode", "--version", capture=True, check=False)
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
        except c.SandboxError as exc:
            out.append({"name": m["name"], "id": m["id"], "policy": None, "state": f"error: {exc}", "version": None})
    return out


def _content(image):
    """Layers + config + creation time. The image ID is not usable: with the containerd
    image store every build gets a new manifest/attestation digest for identical content."""
    return c.docker("image", "inspect", "--format", "{{json .RootFS.Layers}}|{{json .Config}}|{{.Created}}",
                    image, capture=True).stdout.strip()


def update_base(version, distro=None, *, keep_previous=True):
    """Build and verify a candidate base image for a distribution, then replace the tag.

    With keep_previous the replaced image stays available as `<repo>:<distro>-previous-<hex>`.
    """
    c.ensure_runtime()
    d = distros.get(distros.DEFAULT if distro is None else distro)
    # Resolve "latest" first: the literal build arg "latest" hits Docker's layer
    # cache, so the npm install step was never re-run and nothing was updated.
    version = supported(latest() if version == "latest" else version)
    with c.lock(f"base-image-{d.id}"):
        c.require_docker_space("a base image build")
        candidate = distros.candidate_tag(d, __import__("secrets").token_hex(6))
        try:
            c.build_image(d, version, candidate)
            old = c.docker("image", "inspect", "--format", "{{.Id}}", d.image, capture=True, check=False)
            if old.returncode == 0 and _content(d.image) == _content(candidate):
                # Identical rebuild: a rollback tag would only add clutter.
                return {"version": version, "previous_image": None, "image": d.image, "unchanged": True}
            previous = None
            with c.lock(f"base-tag-{d.id}"):  # not while a pinned environment is checked and created
                if old.returncode == 0 and keep_previous:
                    previous = distros.previous_tag(d, __import__("secrets").token_hex(6))
                    c.docker("tag", old.stdout.strip(), previous)
                c.docker("tag", candidate, d.image)
            if old.returncode == 0 and not keep_previous:
                # Otherwise every rebuild leaves the replaced GB-sized image untagged. Docker refuses
                # while a container still uses it or another tag names it; then it stays.
                c.docker("image", "rm", old.stdout.strip(), capture=True, check=False)
            return {"version": version, "previous_image": previous, "image": d.image}
        finally:
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
    return normalize(c.docker("exec", c.cname(m), "opencode", "--version", capture=True).stdout)


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


def rollback_base(distro=None):
    """Swap a base image with its newest rollback copy (`update-base`), after verifying the copy;
    the replaced image becomes a rollback copy itself, so the swap can be repeated."""
    c.ensure_runtime()
    d = distros.get(distros.DEFAULT if distro is None else distro)
    with c.lock(f"base-image-{d.id}"):
        pattern = re.compile(re.escape(distros.previous_tag(d, "")) + r"[0-9a-f]{12}")
        tags = [t for t in c.docker("image", "ls", "--format", "{{.Repository}}:{{.Tag}}", distros.REPOSITORY,
                                    capture=True).stdout.split() if pattern.fullmatch(t)]
        if not tags:
            raise c.SandboxError(f"No rollback copy of {d.image} ({distros.previous_tag(d, '<hex>')})")
        created = {t: c.docker("image", "inspect", "--format", "{{.Created}}", t, capture=True).stdout.strip() for t in tags}
        previous = max(tags, key=lambda t: created[t])
        label = c.docker("image", "inspect", "--format", _VERSION_FORMAT, previous,
                         capture=True).stdout.strip()
        version = supported(label) if label and label != "<no value>" else image_version(previous)
        c.verify_image(d, previous, version)
        with c.lock(f"base-tag-{d.id}"):  # see update_base
            old = c.docker("image", "inspect", "--format", "{{.Id}}", d.image, capture=True, check=False)
            kept = None
            if old.returncode == 0:
                kept = distros.previous_tag(d, __import__("secrets").token_hex(6))
                c.docker("tag", old.stdout.strip(), kept)
            c.docker("tag", previous, d.image)
        c.docker("image", "rm", previous, capture=True)  # only the tag: d.image names the same image
        return {"image": d.image, "version": version, "previous_image": kept}
