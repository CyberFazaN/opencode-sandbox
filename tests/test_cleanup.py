"""D-011: disk usage inventory and safe cleanup (mocked Docker; real runs in tests/integration)."""
import json
import os
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import backup as b
from opencode_sandbox import cleanup as cl
from opencode_sandbox import core as c
from opencode_sandbox import integrations as ig
from opencode_sandbox.cli import app

runner = CliRunner()
MUTATING = {"rm", "volume rm", "image rm", "run", "commit", "tag", "create", "stop", "start", "kill", "prune"}
GONE = "e" * 16


def ok(out=""):
    return SimpleNamespace(returncode=0, stdout=out, stderr="")


def fail(err):
    return SimpleNamespace(returncode=1, stdout="", stderr=err)


def lab(owner=None, *, managed=True, data=True, **extra):
    out = {}
    if managed:
        out.update({cl.MANAGED: "true", cl.VERSION: "6.0.0"})
    if data:
        out[c.DATA_LABEL] = c.data_id() if data is True else data
    if owner:
        out[cl.ID] = owner
    out.update(extra)
    return out


class Daemon:
    """Containers, volumes and images with Docker's refusal rules (no -f anywhere)."""

    def __init__(self, monkeypatch):
        self.containers, self.volumes, self.images, self.hidden, self.calls = {}, {}, {}, {}, []
        self.df_ok = True
        monkeypatch.setattr(c, "docker", self)
        monkeypatch.setattr(c, "ensure_runtime", lambda distro=None: None)

    def container(self, name, labels, *, running=False, image=None, volumes=()):
        cid = f"{len(self.containers):064x}"
        self.containers[cid] = {"Id": cid, "Name": "/" + name, "Config": {"Labels": labels}, "State": {"Running": running},
                                "Image": image, "Mounts": [{"Type": "volume", "Name": v} for v in volumes]}
        return cid

    def volume(self, name, labels):
        self.volumes[name] = {"Name": name, "Labels": labels}

    def image(self, tags, labels, *, unique="100MB", parent=None, hidden=False):
        iid = "sha256:" + f"{len(self.images) + len(self.hidden) + 1:x}".rjust(12, "a") + "0" * 52
        (self.hidden if hidden else self.images)[iid] = {"Id": iid, "Config": {"Labels": labels}, "tags": set(tags),
                                                         "unique": unique, "parent": parent}
        return iid

    def tag_of(self, ref):
        return next((i for i, x in self.images.items() if ref in x["tags"] or ref == i), None)

    def ops(self):
        return {" ".join(a[:2]) if a[0] in ("volume", "image") else a[0] for a in self.calls}

    def __call__(self, *a, capture=False, check=True):
        self.calls.append(a)
        if a[:3] == ("system", "df", "-v"):
            if not self.df_ok:
                return fail("df failed")
            return ok(json.dumps({
                "Images": [{"ID": i, "Size": "2.2GB", "UniqueSize": x["unique"]} for i, x in self.images.items()],
                "Volumes": [{"Name": n, "Size": "12MB"} for n in self.volumes],
                "Containers": [{"ID": i, "Size": "5MB"} for i in self.containers], "BuildCache": []}))
        if a[:2] == ("system", "df"):
            return ok('{"Type":"Images","Size":"6GB"}\n{"Type":"Build Cache","Size":"12.7GB","Reclaimable":"11.39GB","TotalCount":"67"}\n')
        if a[:2] == ("ps", "-a"):
            return ok("\n".join(self.containers))
        if a[:2] == ("container", "inspect"):
            return ok(json.dumps([self.containers[x] for x in a[2:] if x in self.containers]))
        if a[:2] == ("volume", "ls"):
            return ok("\n".join(self.volumes))
        if a[:2] == ("volume", "inspect"):
            return ok(json.dumps([self.volumes[x] for x in a[2:] if x in self.volumes]))
        if a[:2] == ("image", "ls"):
            rows = [f"{i}\t{t}" for i, x in self.images.items() for t in (sorted(x["tags"]) or ["<none>:<none>"])]
            return ok("\n".join(rows))
        if a[:2] == ("image", "inspect"):
            found = [self.images[x] for x in a[2:] if x in self.images]
            if "--format" in a:
                return ok("") if found or a[-1] in {t for x in self.images.values() for t in x["tags"]} else fail("No such image")
            return ok(json.dumps([{k: v for k, v in x.items() if k in ("Id", "Config")} for x in found]))
        if a[0] == "rm":
            x = self.containers.get(a[1])
            if x is None:
                return fail("No such container")
            if x["State"]["Running"]:
                return fail("Error response from daemon: cannot remove container: container is running: stop the container before removing")
            del self.containers[a[1]]
            return ok()
        if a[:2] == ("volume", "rm"):
            if any(m["Name"] == a[2] for x in self.containers.values() for m in x["Mounts"]):
                return fail("Error response from daemon: remove volume: volume is in use")
            self.volumes.pop(a[2], None)
            return ok()
        if a[:2] == ("image", "rm"):
            iid = self.tag_of(a[2])
            if iid is None:
                return fail("No such image")
            x = self.images[iid]
            if a[2] in x["tags"] and len(x["tags"]) > 1:
                x["tags"].discard(a[2])
                return ok()
            if any(y["Image"] == iid for y in self.containers.values()):
                return fail("Error response from daemon: conflict: unable to remove repository reference (must force) - container is using its referenced image")
            del self.images[iid]
            for hid, h in list(self.hidden.items()):  # The parent shows up afterwards
                if hid == x["parent"]:
                    self.images[hid] = self.hidden.pop(hid)
            return ok()
        raise AssertionError(a)


def env(name, **fields):
    m = c.create(name, "scratch", provisioning=ig.request([]))
    m.update(fields)
    c.save(m)
    return m


@pytest.fixture
def world(monkeypatch):
    """A live environment, a deleted one's leftovers, decoys of every kind."""
    d = Daemon(monkeypatch)
    live = env("ocs-qa-live")
    lid = live["id"]
    w = SimpleNamespace(d=d, live=live)
    w.base = d.image(["opencode-sandbox:debian"], lab(data=False))
    w.previous = d.image(["opencode-sandbox:debian-previous-abcdef012345"], lab(data=False), unique="10kB")
    w.candidate = d.image(["opencode-sandbox:debian-candidate-0123456789ab"], lab(data=False))
    w.replaced = d.image([], lab(data=False), unique="40MB")
    live["image"] = f"ocs-runtime:{lid}-111111111111"
    live["opencode_update"] = {"checkpoint": f"ocs-checkpoint:{lid}-aaaaaaaa", "state": "done"}
    c.save(live)
    w.live_image = d.image([live["image"]], lab(lid))
    w.live_ckpt = d.image([live["opencode_update"]["checkpoint"]], lab(lid))
    w.live_old_runtime = d.image([f"ocs-runtime:{lid}-222222222222"], lab(lid))
    w.live_old_ckpt = d.image([f"ocs-checkpoint:{lid}-bbbbbbbb"], lab(lid))
    w.live_snapshot = d.image([f"ocs-snapshot:{lid}-20260101000000"], lab(lid))
    w.live_backup = d.image([f"ocs-backup:{lid}-0123456789"], lab(lid))
    w.live_layer = d.image([], lab(lid))
    w.live_restored = d.image([f"ocs-backup:{'9' * 16}-9999999999"], lab("9" * 16, data="1" * 16))  # from another installation
    live["last_snapshot"] = f"ocs-backup:{'9' * 16}-9999999999"
    c.save(live)
    w.live_ctr = d.container(f"ocs-{lid}", lab(lid), running=True, image=w.live_image, volumes=[f"ocs-home-{lid}"])
    d.volume(f"ocs-home-{lid}", lab(lid))
    # Leftovers of a deleted environment of this data directory
    w.gone_parent = d.image([], lab(GONE), hidden=True)
    w.gone_snapshot = d.image([f"ocs-snapshot:{GONE}-20250101000000"], lab(GONE), parent=w.gone_parent)
    w.gone_runtime = d.image([f"ocs-runtime:{GONE}-abcdef012345"], lab(GONE))
    w.gone_layer = d.image([], lab(GONE))
    w.gone_ctr = d.container(f"ocs-{GONE}", lab(GONE))
    d.volume(f"ocs-home-{GONE}", lab(GONE))
    d.volume(f"ocs-stage-{GONE}-0123abcd", lab(GONE))
    w.helper_done = d.container("eager_helper", lab(**{c.HELPER_LABEL: "preflight"}))
    w.helper_busy = d.container("busy_helper", lab(**{c.HELPER_LABEL: "backup"}), running=True)
    # The user's own container from a snapshot image: it inherits the image's manager labels.
    w.user_from_snapshot = d.container("my-experiment", lab(lid), image=w.live_snapshot)
    # Decoys: another data directory, no data label (older objects), no manager label, unrelated
    other = "f" * 16
    w.other_img = d.image([f"ocs-snapshot:{other}-20250101000000"], lab(other, data="0" * 16))
    w.other_ctr = d.container(f"ocs-{other}", lab(other, data="0" * 16))
    d.volume(f"ocs-home-{other}", lab(other, data="0" * 16))
    w.nolabel_img = d.image([], lab("d" * 16, data=False))
    w.lookalike_img = d.image([f"ocs-snapshot:{'c' * 16}-20250101000000"], {})
    w.lookalike_ctr = d.container(f"ocs-{'c' * 16}", {})
    d.volume(f"ocs-home-{'c' * 16}", {})
    w.unlabelled_base = d.image(["opencode-sandbox:custom"], {})  # in the manager's repository, no labels
    w.ubuntu = d.image(["ubuntu:24.04"], {})
    w.user_ctr = d.container("my-postgres", {"com.example": "x"})
    d.volume("pgdata", {})
    return w


def status(inv):
    return {i.name: (i.status, i.scope) for i in inv.items}


def test_inventory_classifies_everything_and_is_read_only(world):
    d, lid = world.d, world.live["id"]
    inv = cl.inventory()
    s = status(inv)
    assert s["opencode-sandbox:debian"] == ("base image", None)
    assert s["opencode-sandbox:debian-previous-abcdef012345"] == ("superseded", "superseded")
    assert s["opencode-sandbox:debian-candidate-0123456789ab"] == ("leftover", "default")
    assert s[f"untagged {world.replaced[7:19]}"] == ("superseded", "superseded")
    assert s[f"ocs-runtime:{lid}-111111111111"] == ("in use", None)
    assert s[f"ocs-checkpoint:{lid}-aaaaaaaa"] == ("in use", None)  # the rollback point (D-019)
    assert s[f"ocs-runtime:{lid}-222222222222"] == ("superseded", "superseded")
    assert s[f"ocs-checkpoint:{lid}-bbbbbbbb"] == ("superseded", "superseded")
    assert s[f"ocs-snapshot:{lid}-20260101000000"] == ("kept", None)
    assert s[f"ocs-backup:{lid}-0123456789"] == ("leftover", "default")
    assert s[f"untagged {world.live_layer[7:19]}"] == ("kept", None)
    assert s[f"ocs-backup:{'9' * 16}-9999999999"] == ("in use", None)
    assert s[f"ocs-{lid}"] == ("in use", None) and s[f"ocs-home-{lid}"] == ("in use", None)
    for name in (f"ocs-snapshot:{GONE}-20250101000000", f"ocs-runtime:{GONE}-abcdef012345", f"untagged {world.gone_layer[7:19]}",
                 f"ocs-{GONE}", f"ocs-home-{GONE}", f"ocs-stage-{GONE}-0123abcd"):
        assert s[name] == ("orphan", "default"), name
    assert s["eager_helper"] == ("leftover", "default") and s["busy_helper"] == ("in use", None)
    assert s["my-experiment"] == ("not managed", None)
    other = "f" * 16
    for name in (f"ocs-snapshot:{other}-20250101000000", f"ocs-{other}", f"ocs-home-{other}"):
        assert s[name] == ("other data directory", None), name
    for name in (f"untagged {world.nolabel_img[7:19]}", f"ocs-snapshot:{'c' * 16}-20250101000000", f"ocs-{'c' * 16}",
                 f"ocs-home-{'c' * 16}", "opencode-sandbox:custom"):
        assert s[name][0] == "not managed" and s[name][1] is None, name
    assert not {"ubuntu:24.04", "my-postgres", "pgdata"} & set(s)  # unrelated objects are not even listed
    assert not d.ops() & MUTATING
    assert inv.build_cache == {"size": 12_700_000_000, "reclaimable": 11_390_000_000, "records": "67"}
    text = "\n".join(cl.format_inventory(inv))
    assert "Docker build cache: ≈12.7 GB (reclaimable ≈11.4 GB, 67 records)" in text and "disk cleanup never removes it" in text
    assert f"ocs-qa-live [{lid}] scratch: directory" in text and f"home volume ocs-home-{lid}" in text
    assert "disk cleanup would remove 9 object(s)" in text


def test_cleanup_removes_only_confirmed_orphans_and_every_decoy_survives(world):
    d, lid = world.d, world.live["id"]
    inv = cl.inventory()
    keys = [i.key for i in inv.eligible()]
    results = cl.apply(keys)
    errors = {(i if isinstance(i, str) else i.name): e for i, e in results if e}
    assert errors == {}
    removed = {i.name for i, e in results if not e}
    assert f"untagged {world.gone_parent[7:19]}" in removed  # Exposed parent, same deleted owner
    s = status(cl.inventory())
    assert not [n for n, (st, _) in s.items() if st in ("orphan", "leftover")]
    for name in ("opencode-sandbox:debian", "opencode-sandbox:debian-previous-abcdef012345", f"ocs-runtime:{lid}-111111111111",
                 f"ocs-snapshot:{lid}-20260101000000", f"ocs-runtime:{lid}-222222222222", f"ocs-{lid}", f"ocs-home-{lid}",
                 "busy_helper", f"ocs-snapshot:{'f' * 16}-20250101000000", f"ocs-{'f' * 16}", f"ocs-home-{'f' * 16}",
                 f"ocs-snapshot:{'c' * 16}-20250101000000", f"ocs-{'c' * 16}", f"ocs-home-{'c' * 16}", "opencode-sandbox:custom"):
        assert name in s, name
    assert "ubuntu:24.04" in {t for x in d.images.values() for t in x["tags"]} and "pgdata" in d.volumes
    assert any(x["Name"] == "/my-postgres" for x in d.containers.values())
    assert not any("-f" in a or "--force" in a or "prune" in a for a in d.calls)
    # --superseded: checkpoints/runtime images no longer used, rollback copies, the replaced base
    extra = cl.inventory().eligible(True)
    assert {i.name for i in extra} == {"opencode-sandbox:debian-previous-abcdef012345", f"ocs-runtime:{lid}-222222222222",
                                       f"ocs-checkpoint:{lid}-bbbbbbbb", f"untagged {world.replaced[7:19]}"}
    assert all(e is None for _, e in cl.apply([i.key for i in extra], superseded=True))
    s = status(cl.inventory())
    assert s[f"ocs-checkpoint:{lid}-aaaaaaaa"] == ("in use", None) and f"ocs-snapshot:{lid}-20260101000000" in s


def test_only_previewed_objects_are_removed(world):
    d = world.d
    preview = [i.key for i in cl.inventory().eligible() if i.category == "volume"]
    late = d.container("late_helper", lab(**{c.HELPER_LABEL: "backup"}))  # appears after the preview
    results = cl.apply(preview + ["volume:never-listed"])
    assert late in d.containers and f"ocs-{GONE}" in {x["Name"][1:] for x in d.containers.values()}
    assert ("volume:never-listed", "skipped: no longer eligible") in results
    assert {i.name for i, e in results if not isinstance(i, str) and e is None} == {f"ocs-home-{GONE}", f"ocs-stage-{GONE}-0123abcd"}
    # Images: an untagged layer that was visible in the preview but not confirmed stays.
    layer = f"image:{world.gone_layer}"
    results = cl.apply([f"image:ocs-snapshot:{GONE}-20250101000000"])
    assert world.gone_layer in d.images and layer not in {i.key for i, _ in results if not isinstance(i, str)}
    assert world.gone_parent not in d.images and world.gone_parent not in d.hidden  # exposed by the removal: removed


def test_docker_refusals_are_reported_and_never_forced(world):
    d = world.d
    # A stopped container of a deleted environment still uses its orphan image and volume.
    target = d.tag_of(f"ocs-runtime:{GONE}-abcdef012345")
    d.containers[world.gone_ctr]["Image"] = target
    d.containers[world.gone_ctr]["Mounts"] = [{"Type": "volume", "Name": f"ocs-home-{GONE}"}]
    d.containers[world.gone_ctr]["State"]["Running"] = True  # the user started it by hand
    inv = cl.inventory()
    s = status(inv)
    assert s[f"ocs-{GONE}"] == ("kept", None)  # running orphan: stop it first
    items = [i for i in inv.eligible() if i.name in (f"ocs-runtime:{GONE}-abcdef012345", f"ocs-home-{GONE}")]
    results = {i.name: e for i, e in cl.apply([i.key for i in items])}
    assert "container is using its referenced image" in results[f"ocs-runtime:{GONE}-abcdef012345"]
    assert "volume is in use" in results[f"ocs-home-{GONE}"]
    assert target in d.images and f"ocs-home-{GONE}" in d.volumes


def test_busy_owner_pending_operation_and_unreadable_metadata_protect(world):
    d, live = world.d, world.live
    backup_key = f"image:ocs-backup:{live['id']}-0123456789"
    with c.lock(live["id"]):  # an operation of the owner is running
        results = cl.apply([backup_key])
    assert results[0][1].startswith("busy") and d.tag_of(f"ocs-backup:{live['id']}-0123456789")
    live = c.resolve(live["id"]); live["operation"] = "runtime-recreate"; c.save(live)
    s = status(cl.inventory())
    assert s[f"ocs-backup:{live['id']}-0123456789"] == ("kept", None)
    assert s[f"ocs-runtime:{live['id']}-222222222222"] == ("kept", None)
    # Unreadable metadata: the environment directory exists, so nothing of it is an orphan.
    broken = "b" * 16
    (c.BASE / "environments" / broken).mkdir()
    (c.BASE / "environments" / broken / "metadata.json").write_text("{not json")
    d.image([f"ocs-snapshot:{broken}-20250101000000"], lab(broken))
    d.image([f"ocs-backup:{broken}-0123456789"], lab(broken))
    inv = cl.inventory()
    s = status(inv)
    assert s[f"ocs-snapshot:{broken}-20250101000000"] == ("kept", None)
    assert s[f"ocs-backup:{broken}-0123456789"] == ("kept", None)
    entry = next(e for e in inv.environments if e["id"] == broken)
    assert "metadata unreadable" in entry["status"]


def test_another_data_directory_is_never_an_orphan_source(world, tmp_path, monkeypatch):
    """The hazard behind 'never run images-prune --yes with an isolated data dir'."""
    mine = cl.inventory()
    assert status(mine)[f"ocs-{world.live['id']}"] == ("in use", None)
    monkeypatch.setattr(c, "BASE", tmp_path / "second-data-dir")
    other = cl.inventory()
    s = status(other)
    lid = world.live["id"]
    for name in (f"ocs-{lid}", f"ocs-home-{lid}", f"ocs-runtime:{lid}-111111111111", f"ocs-snapshot:{GONE}-20250101000000", "eager_helper"):
        assert s[name] == ("other data directory", None), name
    assert {i.name for i in other.eligible(True)} <= {"opencode-sandbox:debian-previous-abcdef012345",
                                                      "opencode-sandbox:debian-candidate-0123456789ab",
                                                      f"untagged {world.replaced[7:19]}"}


def test_candidate_needs_the_base_build_lock(world):
    key = "image:opencode-sandbox:debian-candidate-0123456789ab"
    with c.lock("base-image-debian"):
        assert cl.apply([key])[0][1].startswith("busy")
    assert cl.apply([key])[0][1] is None


def test_unfinished_backup_directories(world):
    root = c.BASE / "backups"
    temp = root / ".backup-abc123"
    (temp / "sub").mkdir(parents=True)
    (temp / "sub" / "home.tar.gz").write_bytes(b"x" * 9000)
    (root / "app-0123-20260101-abcdef.ocsbackup").mkdir()
    (root / ".backup-link").symlink_to(temp)
    inv = cl.inventory()
    item = next(i for i in inv.items if i.category == "directory")
    assert item.name == ".backup-abc123" and item.scope == "default" and item.size >= 9000
    assert {h["what"] for h in inv.host} >= {"backups"}
    with c.lock(world.live["id"]):  # a backup of any environment may be writing it
        assert cl.apply([item.key])[0][1].startswith("busy")
    assert temp.exists()
    assert cl.apply([item.key])[0][1] is None
    assert not temp.exists() and (root / "app-0123-20260101-abcdef.ocsbackup").is_dir()


def test_errors_are_reported_and_another_cleanup_blocks(world):
    world.d.df_ok = False
    inv = cl.inventory()
    assert "sizes unavailable" in inv.errors[0] and all(i.size is None for i in inv.items if i.category != "directory")
    with c.lock("cleanup"), pytest.raises(c.SandboxError, match="Another cleanup is running"):
        cl.apply([])


def test_sizes_and_reclaim_estimate(tmp_path):
    assert cl.parse_size("2.41GB") == 2_410_000_000 and cl.parse_size("14.3kB") == 14_300
    assert cl.parse_size("0B") == 0 and cl.parse_size("11.39GB (89%)") == 11_390_000_000 and cl.parse_size("N/A") is None
    assert cl.human(1_500_000) == "≈1.5 MB" and cl.human(None) == "size unknown"
    two = [cl.Item("image", "a:1", "a:1", "x", "orphan", image_id="i1", unique=100, tags=("a:1", "a:2")),
           cl.Item("image", "u", "untagged", "x", "orphan", image_id="i2", unique=50, tags=()),
           cl.Item("volume", "v", "v", "x", "orphan", size=7)]
    assert cl.reclaimable(two) == 57  # a:1 shares the image with a:2, which stays
    d = tmp_path / "t"
    (d / "a").mkdir(parents=True)
    (d / "a" / "f").write_bytes(b"x" * 5000)
    (d / "link").symlink_to("/usr")
    (d / "closed").mkdir()
    os.chmod(d / "closed", 0)
    try:
        size, complete = cl.tree_size(d)
    finally:
        os.chmod(d / "closed", 0o700)
    assert 5000 <= size < 100_000 and complete is False


def test_cli_disk_preview_and_cleanup(world):
    d = world.d
    result = runner.invoke(app, ["disk", "usage"])
    assert result.exit_code == 0 and "Removed by disk cleanup (orphans and leftovers):" in result.output
    assert "Not managed by this data directory" in result.output
    before = len(d.calls)
    result = runner.invoke(app, ["disk", "cleanup"])
    assert result.exit_code == 0 and "Would remove 9 object(s)" in result.output and "Rerun 'disk cleanup --yes'" in result.output
    assert "plus untagged earlier layers" in result.output
    assert not {a[0] for a in d.calls[before:]} & {"rm"} and not any(a[:2] in (("image", "rm"), ("volume", "rm")) for a in d.calls[before:])
    d.containers[world.helper_done]["State"]["Running"] = False
    target = d.tag_of(f"ocs-runtime:{GONE}-abcdef012345")
    d.containers[world.user_ctr]["Image"] = target  # Docker will refuse this one
    result = runner.invoke(app, ["disk", "cleanup", "--yes"])
    assert result.exit_code == 1 and "Not removed: orphan" not in result.output
    assert f"Not removed: runtime image ocs-runtime:{GONE}-abcdef012345" in result.output and "Removed: home volume" in result.output
    result = runner.invoke(app, ["disk", "cleanup", "--superseded"])
    assert "Rerun 'disk cleanup --yes --superseded'" in result.output


def test_tui_disk_screen_confirms_before_removing(world):
    import asyncio

    from opencode_sandbox import tui
    d = world.d

    async def main():
        app = tui.Dashboard()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("D")
            for _ in range(50):
                await pilot.pause(); await asyncio.sleep(0.05)
                if type(app.screen).__name__ == "DiskScreen":
                    break
            assert type(app.screen).__name__ == "DiskScreen" and "Removed by disk cleanup" in app.screen.report
            app.screen.query_one("#disk-cleanup").press(); await pilot.pause()
            assert type(app.screen).__name__ == "ConfirmScreen" and "Remove 9 object(s)" in app.screen.message
            assert f"ocs-{GONE}" in {x["Name"][1:] for x in d.containers.values()}  # nothing removed yet
            app.screen.query_one("#confirm").press()
            for _ in range(50):
                await pilot.pause(); await asyncio.sleep(0.05)
                if type(app.screen).__name__ == "OpenCodeVersionsScreen":
                    break
            assert "Removed: environment container" in app.screen.report
    asyncio.run(main())
    assert f"ocs-{GONE}" not in {x["Name"][1:] for x in d.containers.values()}
    assert "pgdata" in d.volumes and f"ocs-home-{world.live['id']}" in d.volumes


def test_labels_scope_objects_to_the_data_directory(tmp_path, monkeypatch):
    labels = c.labels("0123456789abcdef")
    assert f"{c.DATA_LABEL}={c.data_id()}" in labels and labels[-1] == "org.opencode-sandbox.id=0123456789abcdef"
    assert not any(c.DATA_LABEL in x for x in c.labels(scoped=False))
    first = c.data_id()
    monkeypatch.setattr(c, "BASE", tmp_path / "elsewhere")
    assert c.data_id() != first and len(first) == 16


def test_backup_helper_is_a_local_registry_image(monkeypatch):
    """No unpinned ubuntu:24.04 from Docker Hub."""
    present = {"opencode-sandbox:arch"}
    calls = []

    def docker(*a, **k):
        calls.append(a)
        if a[:2] == ("image", "inspect"):
            return ok("[]") if a[-1] in present else fail("No such image")
        return ok()
    monkeypatch.setattr(c, "docker", docker)
    m = env("ocs-qa-backup")
    assert b.helper_image(m) == "opencode-sandbox:arch"  # Debian environment, only the Arch image is local
    present.add("opencode-sandbox:debian")
    assert b.helper_image(m) == "opencode-sandbox:debian"
    assert b.helper_image({**m, "distro": None, "image": "example.org/x:1"}) == "opencode-sandbox:debian"
    present.clear()
    with pytest.raises(c.SandboxError, match="need a local base image"):
        b.helper_image(m)
    present.add("opencode-sandbox:debian")
    dest = c.BASE / "t" / "home.tar.gz"
    dest.parent.mkdir(parents=True)
    monkeypatch.setattr(b, "_validate_archive", lambda p: None)
    (dest.parent / b.HOME_SKIPPED).write_bytes(b"")  # the helper's (empty) list of left-out files
    b._volume_tar(m, dest)
    run = next(a for a in calls if a[0] == "run")
    assert "ubuntu:24.04" not in run and run[run.index("--entrypoint") + 1] == "sh"
    assert run[run.index("opencode-sandbox:debian") + 1] == "-ec" and f"{c.DATA_LABEL}={c.data_id()}" in run


def test_direct_workspace_is_listed_but_never_walked_or_removed(world, tmp_path):
    project = tmp_path / "projects" / "app"
    project.mkdir(parents=True)
    (project / "big.bin").write_bytes(b"x" * 300_000)
    m = env("ocs-qa-direct", workspace={"mode": "direct", "path": str(project)})
    inv = cl.inventory()
    entry = next(e for e in inv.environments if e["id"] == m["id"])
    assert entry["direct"] == str(project) and entry["size"] < 300_000
    assert f"direct workspace {project} (yours: not counted, never removed)" in "\n".join(cl.format_inventory(inv))
    cl.apply([i.key for i in inv.eligible(True)], superseded=True)
    assert (project / "big.bin").stat().st_size == 300_000


def test_every_helper_container_carries_the_helper_label():
    """cleanup removes a stopped manager container only when it is an environment's or carries
    the helper label; an unlabelled `run --rm` would never be cleaned up after a daemon crash."""
    import re
    from pathlib import Path
    src = Path(c.__file__).parent
    found = 0
    for path in src.glob("*.py"):
        lines = path.read_text().splitlines()
        for n, line in enumerate(lines):
            if re.search(r"""["']run["'],\s*["']--rm["']""", line):
                found += 1
                assert "helper_labels(" in " ".join(lines[n:n + 2]), f"{path.name}:{n + 1}"
    assert found >= 5
