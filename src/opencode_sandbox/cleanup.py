"""Disk usage inventory and safe cleanup (D-011).

`inventory()` is read-only: it lists what the manager owns on the Docker daemon and in its data
directory, with approximate sizes, and classifies every object. `apply(keys)` removes only objects
the user confirmed from a preview, after re-checking each one; it never uses `docker system
prune`, never forces a removal (`docker rm`/`image rm`/`volume rm` without `-f`, so Docker itself
refuses anything a container still uses) and never touches direct workspaces, environment
directories, exports or backups.

Ownership (D-011): the label `org.opencode-sandbox.managed=true`, the manager's name patterns and,
for per-environment objects, the data-directory label `org.opencode-sandbox.data-dir`: several
data directories (OPENCODE_SANDBOX_HOME) can share one daemon, and an environment of another one is
not an orphan of this one. Objects without these labels are listed as "not managed" and never
removed.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import core as c
from . import distros

MANAGED, ID, VERSION = "org.opencode-sandbox.managed", "org.opencode-sandbox.id", "org.opencode-sandbox.manager-version"

# Statuses
IN_USE, KEPT, BASE, ORPHAN, LEFTOVER, SUPERSEDED = "in use", "kept", "base image", "orphan", "leftover", "superseded"
NOT_MANAGED, OTHER_DATA = "not managed", "other data directory"
DEFAULT, EXTRA = "default", "superseded"  # cleanup scopes

ENV_IMAGE = re.compile(r"(?P<kind>ocs-snapshot|ocs-runtime|ocs-backup|ocs-checkpoint):(?P<id>[0-9a-f]{16})-[0-9A-Za-z._-]+")
ENV_VOLUME = re.compile(r"ocs-(?:home|stage)-(?P<id>[0-9a-f]{16})(?:-[0-9a-f]{8})?")
ENV_CONTAINER = re.compile(r"ocs-(?P<id>[0-9a-f]{16})")
BACKUP_TEMP = re.compile(r"\.backup-[A-Za-z0-9_]{1,32}")
OWNED_KINDS = {"ocs-snapshot": "snapshot", "ocs-runtime": "runtime image", "ocs-backup": "restored system image",
               "ocs-checkpoint": "OpenCode update checkpoint"}


@dataclass
class Item:
    category: str            # container | volume | image | directory
    ref: str                 # what is removed: container id, volume name, image tag or id, path
    name: str                # shown
    kind: str
    status: str
    detail: str = ""
    owner: str | None = None
    owner_name: str | None = None
    size: int | None = None  # bytes, approximate
    unique: int | None = None  # images: bytes not shared with other images (approximate)
    image_id: str | None = None
    tags: tuple = ()          # images: every tag of the image
    scope: str | None = None  # DEFAULT or EXTRA when cleanup may remove it
    lock: tuple = ()          # lock keys held (non-blocking) while it is re-checked and removed

    @property
    def key(self):
        return f"{self.category}:{self.ref}"


@dataclass
class Inventory:
    data_dir: str
    data_id: str
    items: list = field(default_factory=list)
    environments: list = field(default_factory=list)
    host: list = field(default_factory=list)
    build_cache: dict | None = None
    errors: list = field(default_factory=list)

    def eligible(self, superseded=False):
        return [i for i in self.items if i.scope == DEFAULT or (superseded and i.scope == EXTRA)]


# ---------------------------------------------------------------------------------------------
# Sizes

_UNITS = {"B": 1, "kB": 10**3, "KB": 10**3, "MB": 10**6, "GB": 10**9, "TB": 10**12, "PB": 10**15}


def parse_size(text):
    """Docker's human sizes (decimal units, e.g. "2.41GB", "14.3kB"); None if not a size."""
    m = re.fullmatch(r"\s*([0-9.]+)\s*([kKMGTP]?B)\s*(?:\(.*\))?", str(text or ""))
    if not m:
        return None
    try:
        return int(float(m.group(1)) * _UNITS[m.group(2)])
    except (KeyError, ValueError):
        return None


def human(n, *, approx=True):
    if n is None:
        return "size unknown"
    for unit, factor in (("GB", 10**9), ("MB", 10**6), ("kB", 10**3)):
        if n >= factor:
            return f"{'≈' if approx else ''}{n / factor:.1f} {unit}"
    return f"{'≈' if approx else ''}{n} B"


def tree_size(path):
    """(bytes on disk, complete) of a directory tree: symlinks not followed, mounts not crossed;
    complete is False when something was unreadable (files of subordinate UIDs)."""
    try:
        dev = os.lstat(path).st_dev
    except OSError:
        return None, False
    total, complete, stack = 0, True, [str(path)]
    while stack:
        try:
            entries = os.scandir(stack.pop())
        except OSError:
            complete = False
            continue
        with entries:
            for e in entries:
                try:
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    complete = False
                    continue
                total += st.st_blocks * 512
                if e.is_dir(follow_symlinks=False) and st.st_dev == dev:
                    stack.append(e.path)
    return total, complete


def _docker_df(inv):
    """Sizes from `docker system df -v` (Docker's approximations): images by id, volumes by name,
    containers by id; build cache totals from `docker system df`."""
    sizes = {"images": {}, "volumes": {}, "containers": {}}
    p = c.docker("system", "df", "-v", "--format", "{{json .}}", capture=True, check=False)
    try:
        data = json.loads(p.stdout) if p.returncode == 0 else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        inv.errors.append("sizes unavailable: docker system df -v failed")
        data = {}
    for i in data.get("Images") or ():
        sizes["images"][i.get("ID", "")] = (parse_size(i.get("Size")), parse_size(i.get("UniqueSize")))
    for v in data.get("Volumes") or ():
        sizes["volumes"][v.get("Name", "")] = parse_size(v.get("Size"))
    for x in data.get("Containers") or ():
        sizes["containers"][x.get("ID", "")] = parse_size(x.get("Size"))
    p = c.docker("system", "df", "--format", "{{json .}}", capture=True, check=False)
    for line in (p.stdout or "").splitlines() if p.returncode == 0 else ():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("Type") == "Build Cache":
            inv.build_cache = {"size": parse_size(row.get("Size")), "reclaimable": parse_size(row.get("Reclaimable")),
                               "records": row.get("TotalCount")}
    return sizes


# ---------------------------------------------------------------------------------------------
# Docker listing

def _inspect(kind, refs):
    if not refs:
        return []
    p = c.docker(kind, "inspect", *refs, capture=True, check=False)
    try:
        data = json.loads(p.stdout or "[]")
    except ValueError as exc:
        raise c.SandboxError(f"Invalid docker {kind} inspect response") from exc
    if p.returncode and not data:
        raise c.SandboxError(f"docker {kind} inspect failed: {(p.stderr or '').strip()[:200]}")
    return data if isinstance(data, list) else []


def _lines(*args):
    p = c.docker(*args, capture=True, check=False)
    if p.returncode:
        raise c.SandboxError(f"docker {' '.join(args[:2])} failed: {(p.stderr or '').strip()[:200]}")
    return [x for x in p.stdout.splitlines() if x.strip()]


def _registry():
    """Environment ids with a directory (also with unreadable metadata) and readable metadata.

    Read AFTER listing Docker objects: every object found then already existed, and the manager
    records an object's owner (metadata, journal) before it creates the object."""
    root = c.BASE / "environments"
    ids = {p.name for p in root.iterdir() if p.is_dir() and re.fullmatch(r"[0-9a-f]{16}", p.name)} if root.is_dir() else set()
    envs = {m["id"]: m for m in c.all_envs()}
    return ids, envs


def referenced_images(envs):
    """Images an environment depends on: its image, last snapshot, the last OpenCode update's
    checkpoint (its rollback point, D-019) and, while an operation is pending, the image it
    replaces."""
    out = set()
    for m in envs:
        out.update(v for v in (m.get("image"), m.get("last_snapshot"), (m.get("opencode_update") or {}).get("checkpoint"),
                               m.get("superseded_image") if m.get("operation") else None) if v)
    return out


def _scope_of(labels, data_id):
    """None when the object belongs to this data directory, else the status to report."""
    if (labels or {}).get(MANAGED) != "true":
        return NOT_MANAGED, "no manager label"
    found = (labels or {}).get(c.DATA_LABEL)
    if not found:
        return NOT_MANAGED, f"no data-directory label (manager {labels.get(VERSION, 'unknown')})"
    if found != data_id:
        return OTHER_DATA, "created for another data directory (OPENCODE_SANDBOX_HOME)"
    return None


def _owner(item, owner, ids, envs):
    item.owner = owner
    item.owner_name = (envs.get(owner) or {}).get("name")
    return owner in ids


def _protected_owner(item, owner, envs, *, lock=True):
    """An owner-dependent removal: needs readable metadata and no pending operation; holds the
    owner's lock while it is re-checked and removed."""
    m = envs.get(owner)
    if m is None:
        item.status, item.scope, item.detail = KEPT, None, "owner's metadata is unreadable: nothing of it is removed"
        return False
    if m.get("operation") or m.get("status") == "deleting":
        item.status, item.scope, item.detail = KEPT, None, f"owner {m['name']} has a pending operation ({m.get('operation') or 'delete'})"
        return False
    if lock:
        item.lock = (owner,)
    return True


def _fetch():
    """Raw Docker data, listed before the registry is read."""
    containers = _inspect("container", _lines("ps", "-a", "-q", "--no-trunc"))
    volumes = _inspect("volume", _lines("volume", "ls", "-q"))
    rows = [line.split("\t", 1) for line in _lines("image", "ls", "-a", "--no-trunc", "--format", "{{.ID}}\t{{.Repository}}:{{.Tag}}")]
    tags = {}
    for image_id, tag in rows:
        tags.setdefault(image_id, set())
        if tag != "<none>:<none>":
            tags[image_id].add(tag)
    images = {x.get("Id"): x for x in _inspect("image", list(tags))}
    return containers, volumes, tags, images


def _containers(inv, sizes, containers, ids, envs, data_id):
    for x in containers:
        labels = (x.get("Config") or {}).get("Labels") or {}
        name = str(x.get("Name", "")).lstrip("/")
        if labels.get(MANAGED) != "true" and not name.startswith("ocs-"):
            continue
        running = bool((x.get("State") or {}).get("Running"))
        item = Item("container", x.get("Id", ""), name, "container", IN_USE, size=sizes["containers"].get(x.get("Id", "")))
        foreign = _scope_of(labels, data_id)
        match = ENV_CONTAINER.fullmatch(name)
        environment = bool(match and labels.get(ID) == match.group("id"))
        if foreign:
            item.status, item.detail = foreign
        elif not environment and c.HELPER_LABEL not in labels:
            # E.g. created by the user from a snapshot: containers inherit their image's labels.
            item.status, item.detail = NOT_MANAGED, "not created by the manager (labels inherited from a manager image)"
        elif not environment:
            item.kind = "helper container"
            if running:
                item.status, item.detail = IN_USE, "running (an operation is in progress)"
            else:
                item.status, item.detail, item.scope = LEFTOVER, "stopped helper container (normally removed automatically)", DEFAULT
        else:
            item.kind = "environment container"
            if _owner(item, labels[ID], ids, envs):
                item.status, item.detail = IN_USE, f"container of {item.owner_name or item.owner}"
            elif running:
                item.status, item.detail = KEPT, "owner deleted, but the container is running: stop it to remove it"
            else:
                item.status, item.detail, item.scope = ORPHAN, "owner environment deleted", DEFAULT
        inv.items.append(item)


def _volumes(inv, sizes, volumes, ids, envs, data_id):
    used = {}
    for m in envs.values():
        with contextlib.suppress(c.SandboxError):
            used[c.volume(m)] = m
    for v in volumes:
        labels, name = v.get("Labels") or {}, v.get("Name", "")
        if labels.get(MANAGED) != "true" and not name.startswith("ocs-"):
            continue
        match = ENV_VOLUME.fullmatch(name)
        item = Item("volume", name, name, "volume", IN_USE, size=sizes["volumes"].get(name))
        foreign = _scope_of(labels, data_id)
        if foreign:
            item.status, item.detail = foreign
        elif not match or labels.get(ID) != match.group("id"):
            item.status, item.detail = NOT_MANAGED, "name or owner label not the manager's"
        else:
            item.kind = "restore staging volume" if name.startswith("ocs-stage-") and name not in used else "home volume"
            if name in used:
                item.owner, item.owner_name = used[name]["id"], used[name]["name"]
                item.status, item.detail = IN_USE, f"home volume of {item.owner_name}"
            elif _owner(item, labels[ID], ids, envs):
                item.status, item.detail = KEPT, "owner exists; removed with it (delete NAME)"
            else:
                item.status, item.detail, item.scope = ORPHAN, "owner environment deleted", DEFAULT
        inv.items.append(item)


def _images(inv, sizes, tags, data, ids, envs, data_id):
    referenced = referenced_images(envs.values())
    repo = distros.REPOSITORY + ":"
    registry = "|".join(re.escape(d) for d in distros.REGISTRY)
    previous = re.compile(rf"{re.escape(repo)}(?P<distro>{registry})-previous-[0-9a-f]{{12}}")
    candidate = re.compile(rf"{re.escape(repo)}(?P<distro>{registry})-candidate-[0-9a-f]{{12}}")
    base = {d.image for d in distros.REGISTRY.values()}
    for image_id, names in tags.items():
        labels = ((data.get(image_id) or {}).get("Config") or {}).get("Labels") or {}
        size, unique = sizes["images"].get(image_id, (None, None))
        short = image_id.removeprefix("sha256:")[:12]
        for tag in sorted(names) or [None]:
            if tag is None and labels.get(MANAGED) != "true":
                continue
            if tag is not None and labels.get(MANAGED) != "true" and not tag.startswith(("ocs-", repo)):
                continue
            item = Item("image", tag or image_id, tag or f"untagged {short}", "image", KEPT, size=size, unique=unique,
                        image_id=image_id, tags=tuple(sorted(names)))
            if len(names) > 1:
                item.detail = f"same image as {', '.join(sorted(names - {tag}))}; "
            _classify_image(item, tag, labels, ids, envs, data_id, referenced, base, previous, candidate)
            inv.items.append(item)


def _classify_image(item, tag, labels, ids, envs, data_id, referenced, base, previous, candidate):
    note = item.detail
    if tag in base:
        item.kind, item.status, item.detail = "base image", BASE, note + "new environments are created from it"
        return
    if tag is not None and (p := previous.fullmatch(tag)):
        item.kind = "base rollback copy"
        if tag in referenced:
            item.status, item.detail = IN_USE, note + "an environment uses it"
        else:
            item.status, item.detail, item.scope = SUPERSEDED, note + f"rollback-base --distro {p.group('distro')} uses the newest", EXTRA
        return
    if tag is not None and (p := candidate.fullmatch(tag)):
        item.kind, item.status, item.scope = "base build candidate", LEFTOVER, DEFAULT
        item.detail, item.lock = note + "left by an interrupted build", (f"base-image-{p.group('distro')}",)
        return
    match = ENV_IMAGE.fullmatch(tag) if tag else None
    if tag in referenced:  # whatever its labels (e.g. a system image restored from another installation)
        owner = next(m for m in envs.values() if tag in referenced_images([m]))
        item.kind = OWNED_KINDS[match.group("kind")] if match else "image"
        item.owner, item.owner_name, item.status, item.detail = owner["id"], owner["name"], IN_USE, note + f"used by {owner['name']}"
        return
    if labels.get(MANAGED) != "true":
        item.status, item.detail = NOT_MANAGED, note + "no manager label"
        return
    if tag is not None and not match:
        item.status, item.detail = NOT_MANAGED, note + "not a name the manager creates"
        return
    if tag is None and not labels.get(ID):
        # A replaced base image (labels without data directory or owner).
        if labels.get(c.DATA_LABEL):
            item.status, item.detail = NOT_MANAGED, note + "untagged, no owner label"
        else:
            item.kind, item.status, item.scope = "untagged base image", SUPERSEDED, EXTRA
            item.detail = note + "replaced base image (Docker refuses while a container uses it)"
        return
    foreign = _scope_of(labels, data_id)
    if foreign:
        item.status, item.detail = foreign[0], note + foreign[1]
        return
    owner = match.group("id") if match else labels.get(ID)
    item.kind = OWNED_KINDS[match.group("kind")] if match else "untagged image"
    exists = _owner(item, owner, ids, envs)
    kind = match.group("kind") if match else None
    if not exists:
        item.status, item.scope = ORPHAN, DEFAULT
        item.detail = note + ("owner environment deleted" if match else "earlier layer of a deleted environment's image")
    elif kind == "ocs-backup":
        # Only ever created by restore for the restored environment, which references it.
        item.status, item.scope, item.detail = LEFTOVER, DEFAULT, note + "not used by any environment"
        _protected_owner(item, owner, envs)
    elif kind in ("ocs-checkpoint", "ocs-runtime"):
        item.status, item.scope, item.detail = SUPERSEDED, EXTRA, note + f"no longer used by {item.owner_name or owner}"
        _protected_owner(item, owner, envs)
    else:
        item.status, item.detail = KEPT, note + ("snapshot of an existing environment (never removed by disk cleanup)" if kind
                                                  else "earlier layer of an existing environment's image")


def _host(inv, ids, envs):
    from . import workspaces
    for eid in sorted(ids):
        m = envs.get(eid)
        d = c.env_dir(eid)
        size, complete = tree_size(d)
        entry = {"id": eid, "name": (m or {}).get("name"), "kind": (m or {}).get("kind"), "path": str(d), "size": size,
                 "complete": complete, "direct": None, "status": None}
        if m is None:
            entry["status"] = "metadata unreadable: inspect it yourself; nothing of it is removed"
        else:
            with contextlib.suppress(c.SandboxError):
                info = workspaces.info(m)
                if info["mode"] == workspaces.DIRECT:
                    entry["direct"] = info["path"]
            if m.get("operation") or m.get("status") == "deleting":
                entry["status"] = f"pending operation {m.get('operation') or 'delete'}"
        inv.environments.append(entry)
    for name, what in (("exports", "exports (changes export NAME)"), ("changes", "change bundles"), ("backups", "backups")):
        p = c.BASE / name
        if p.is_dir() and not p.is_symlink():
            size, complete = tree_size(p)
            inv.host.append({"path": str(p), "what": what, "size": size, "complete": complete})
    root = c.BASE / "backups"
    if root.is_dir() and not root.is_symlink():
        for p in sorted(root.iterdir()):
            if BACKUP_TEMP.fullmatch(p.name) and p.is_dir() and not p.is_symlink():
                size, complete = tree_size(p)
                inv.items.append(Item("directory", str(p), p.name, "unfinished backup", LEFTOVER,
                                      "left by an interrupted backup (removed only while no environment is busy)",
                                      size=size, scope=DEFAULT, lock=tuple(sorted(ids))))


def inventory():
    """Read-only. Raises only when the daemon is not verified; other failures are reported."""
    c.ensure_runtime(False)
    inv = Inventory(str(c.BASE), c.data_id())
    sizes = _docker_df(inv)
    try:
        fetched = _fetch()
    except c.SandboxError as exc:
        inv.errors.append(str(exc))
        fetched = None
    ids, envs = _registry()  # after the Docker listing (see _registry)
    if fetched is not None:
        containers, volumes, tags, images = fetched
        _containers(inv, sizes, containers, ids, envs, inv.data_id)
        _volumes(inv, sizes, volumes, ids, envs, inv.data_id)
        _images(inv, sizes, tags, images, ids, envs, inv.data_id)
    _host(inv, ids, envs)
    return inv


# ---------------------------------------------------------------------------------------------
# Removal

def _recheck(item):
    """Under the item's locks: still safe to remove? None if so, else the reason."""
    if item.category == "directory":
        p = Path(item.ref)
        if p.parent != c.BASE / "backups" or not BACKUP_TEMP.fullmatch(p.name) or p.is_symlink() or not p.is_dir():
            return "no longer an unfinished backup directory"
        return None
    if item.owner and item.lock == (item.owner,):
        try:
            m = c.resolve(item.owner)
        except c.SandboxError:
            return "owner's metadata changed"
        if m.get("operation") or m.get("status") == "deleting":
            return f"owner {m['name']} has a pending operation"
        if item.category == "image" and item.ref in referenced_images([m]):
            return f"now used by {m['name']}"
    return None


def _remove(item):
    """None when removed, else why not. Never forced: Docker refuses objects still in use."""
    with contextlib.ExitStack() as stack:
        try:
            for key in item.lock:
                stack.enter_context(c.lock(key, timeout=0))
        except c.SandboxError:
            return "busy (an operation holds its lock); run cleanup again later"
        reason = _recheck(item)
        if reason:
            return "skipped: " + reason
        if item.category == "directory":
            try:
                shutil.rmtree(item.ref)
            except OSError as exc:
                return f"cannot remove: {exc}"
            return None
        argv = {"container": ("rm",), "volume": ("volume", "rm"), "image": ("image", "rm")}[item.category]
        p = c.docker(*argv, item.ref, capture=True, check=False)
        if p.returncode == 0:
            return None
        error = (p.stderr or "").strip()[:300] or f"docker exit {p.returncode}"
        # Gone meanwhile: e.g. the untagged image a restored image was committed from is
        # removed together with that image. Checked by inspect, not by the message.
        inspect = {"container": ("container", "inspect"), "volume": ("volume", "inspect"),
                   "image": ("image", "inspect")}[item.category]
        if c.docker(*inspect, "--format", "{{.Name}}" if item.category != "image" else "{{.Id}}", item.ref,
                    capture=True, check=False).returncode:
            return None
        if item.category == "image" and not item.tags and "dependent child images" in error:
            return "skipped: still the base of another image; Docker removes it with that image"
        return error


def apply(keys, *, superseded=False):
    """Remove the confirmed preview entries (`Item.key`) that are still eligible after a fresh
    inventory. Each removal is a single Docker or file operation, so an interrupted cleanup leaves
    every object either intact or removed and can simply be run again. Returns [(item or key,
    error or None)]."""
    keys = set(keys)
    results = []
    try:
        guard = c.lock("cleanup", timeout=0)
        guard.__enter__()
    except c.SandboxError as exc:
        raise c.SandboxError("Another cleanup is running") from exc
    try:
        inv = inventory()
        todo = [i for i in inv.eligible(superseded) if i.key in keys]
        results += [(k, "skipped: no longer eligible") for k in sorted(keys - {i.key for i in todo})]
        # Only owners whose images were removed, and only layers not visible in the preview (those
        # the user saw but did not confirm stay).
        deleted = {i.owner for i in todo if i.status == ORPHAN and i.owner and i.category == "image"}
        visible = {i.key for i in inv.items}
        done = set()
        for item in todo:
            results.append((item, _remove(item)))
            done.add(item.key)
        # Removing an image can turn its untagged parent (an earlier snapshot in a recreate chain)
        # into a separate leftover of the same deleted environment: covered by the
        # confirmation ("and their untagged earlier layers"), never anything else.
        for _ in range(20):
            more = [i for i in inventory().eligible() if i.category == "image" and i.name.startswith("untagged ")
                    and i.status == ORPHAN and i.owner in deleted and i.key not in done | visible]
            if not more:
                break
            for item in more:
                results.append((item, _remove(item)))
                done.add(item.key)
    finally:
        guard.__exit__(None, None, None)
    return results


# ---------------------------------------------------------------------------------------------
# Reporting

def _size(item):
    if item.category == "image":
        if item.unique is not None and item.size is not None:
            return f"{human(min(item.unique, item.size))} own, {human(item.size)} with shared layers"
        return human(item.size)
    return human(item.size)


def reclaimable(items):
    """Approximate bytes freed: an image's own (unshared) size counts once, and only when all of
    its tags are among `items`."""
    keys = {i.key for i in items}
    total, images = 0, {}
    for i in items:
        if i.category == "image":
            images.setdefault(i.image_id, i)
        else:
            total += i.size or 0
    for i in images.values():
        if all(f"image:{t}" in keys for t in i.tags):
            total += i.unique or 0
    return total


def _line(item):
    owner = f"; owner {item.owner_name or ('deleted ' + item.owner if item.owner else '')}" if item.owner else ""
    return f"  [{item.status}] {item.kind} {item.name} ({_size(item)}){owner} — {item.detail}"


SIZES_NOTE = ("Sizes are approximate: Docker's estimates in decimal units; image layers shared between images are "
              "counted once per image (\"own\" = not shared).")
BUILD_CACHE_NOTE = ("  daemon-wide: Docker does not record which builds created it, so it is not attributed to the manager "
                    "and disk cleanup never removes it. 'docker builder prune' removes the unused build cache of ALL builds on "
                    "this daemon (the next image build downloads and rebuilds everything).")


def format_inventory(inv):
    lines = [f"Data directory: {inv.data_dir} (Docker label org.opencode-sandbox.data-dir={inv.data_id})",
             SIZES_NOTE, "", "Environments (remove one with: delete NAME):"]
    shown = set()
    for e in inv.environments:
        parts = [f"directory {human(e['size'])}" + ("" if e["complete"] else " or more (some files unreadable)")]
        if e["direct"]:
            parts.append(f"direct workspace {e['direct']} (yours: not counted, never removed)")
        for i in inv.items:
            if i.owner == e["id"] and i.scope is None and i.status in (IN_USE, KEPT):
                parts.append(f"{i.kind} {i.name} ({_size(i)})")
                shown.add(i.key)
        lines.append(f"  {e['name'] or '?'} [{e['id']}] {e['kind'] or ''}: " + "; ".join(parts)
                     + (f" — {e['status']}" if e["status"] else ""))
    if not inv.environments:
        lines.append("  none")
    groups = (
        ("Base images (shared by every data directory; disk cleanup removes only what is listed below):",
         lambda i: i.kind.startswith("base") and i.scope is None),
        ("Removed by disk cleanup (orphans and leftovers):", lambda i: i.scope == DEFAULT),
        ("Removed only by disk cleanup --superseded:", lambda i: i.scope == EXTRA),
        ("Other manager objects (kept):", lambda i: i.status in (IN_USE, KEPT) and i.scope is None),
        ("Not managed by this data directory (never removed; remove them yourself only if you are sure):",
         lambda i: i.status in (NOT_MANAGED, OTHER_DATA)),
    )
    for title, test in groups:
        selected = [i for i in inv.items if i.key not in shown and test(i)]
        shown.update(i.key for i in selected)
        if selected:
            lines += ["", title, *(_line(i) for i in selected)]
    lines += ["", "Host data (never removed by disk cleanup; old backups: backup prune):"]
    lines += [f"  {h['what']}: {h['path']} ({human(h['size'])}{'' if h['complete'] else ' or more'})" for h in inv.host] or ["  none"]
    b = inv.build_cache
    lines += ["", "Docker build cache: " + (f"{human(b['size'])} (reclaimable {human(b['reclaimable'])}, {b['records']} records)"
                                           if b else "unknown"), BUILD_CACHE_NOTE]
    for e in inv.errors:
        lines.append(f"WARNING: {e}")
    default, extra = inv.eligible(), inv.eligible(True)
    total = (f"disk cleanup would remove {len(default)} object(s), freeing {human(reclaimable(default))}; "
             f"disk cleanup --superseded {len(extra)}, {human(reclaimable(extra))}.")
    lines += ["", total]
    return lines


def format_preview(items):
    return [f"  {i.kind} {i.name} ({_size(i)}) — {i.detail}" for i in items]
