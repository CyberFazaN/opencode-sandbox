"""UP-04: copy choice is not Docker creation order; mocked daemon, real host guards."""
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import cli, distros
from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v


def iid(char):
    return "sha256:" + char * 64


class Copies:
    def __init__(self, monkeypatch):
        self.d = distros.get(distros.DEFAULT)
        self.calls, self.verified = [], []
        self.tags, self.images = {}, {}
        self.add(self.d.image, "c", "2.2.0", "2026-10-01")
        self.first = distros.previous_tag(self.d, "a" * 12)
        self.second = distros.previous_tag(self.d, "b" * 12)
        self.add(self.first, "a", "2.1.4", "2026-10-20")
        monkeypatch.setattr(c, "ensure_runtime", lambda *a: None)
        monkeypatch.setattr(c, "docker", self.docker)
        monkeypatch.setattr(c, "verify_image", lambda d, ref, version: self.verified.append((d.id, ref, version)))

    def add(self, tag, char, version, created):
        self.tags[tag] = iid(char)
        self.images[iid(char)] = {"Id": iid(char), "Created": created, "Config": {"Labels": {
            **self.d.image_labels(), distros.LABEL + "managed": "true", v.VERSION_LABEL: version}}}

    def docker(self, *args, **kwargs):
        self.calls.append(args)
        if args[:2] == ("image", "ls"):
            return SimpleNamespace(returncode=0, stdout="\n".join(self.tags), stderr="")
        if args[:2] == ("image", "inspect"):
            ref = args[-1]
            info = self.images.get(self.tags.get(ref, ref))
            if info is None:
                return SimpleNamespace(returncode=1, stdout="[]", stderr="No such image: " + ref)
            if "--format" in args:
                out = info["Created"] if args[3] == "{{.Created}}" else info["Config"]["Labels"][v.VERSION_LABEL]
            else:
                out = json.dumps([info])
            return SimpleNamespace(returncode=0, stdout=out, stderr="")
        if args[0] == "tag":
            self.tags[args[-1]] = self.tags.get(args[1], args[1])
        elif args[:2] == ("image", "rm"):
            del self.tags[args[-1]]
        else:
            pytest.fail(f"unexpected Docker call: {args}")
        return SimpleNamespace(returncode=0, stdout="", stderr="")


@pytest.fixture
def copies(monkeypatch):
    return Copies(monkeypatch)


@pytest.mark.parametrize("created", ["2026-09-01", "2026-10-20", "2026-10-29"])
def test_several_copies_never_guess_from_creation_time(copies, created):
    copies.add(copies.second, "b", "2.2.0", created)
    with pytest.raises(c.SandboxError, match="Several distinct rollback copies"):
        v.rollback_base()
    assert not copies.verified
    assert not any(a[0] == "tag" or a[:2] == ("image", "rm") for a in copies.calls)


@pytest.mark.parametrize("choice", ["tag", "id"])
def test_explicit_copy_can_restore_cached_older_build_or_downgrade(copies, choice):
    copies.add(copies.second, "b", "2.2.1", "2026-10-29")
    # This lower-version, earlier-created copy might have been the last replacement, or not.
    copies.images[iid("a")]["Created"] = "2020-01-01"
    selected = copies.first if choice == "tag" else iid("a")
    result = v.rollback_base(copy=selected)
    assert result["version"] == "2.1.4" and copies.tags[copies.d.image] == iid("a")
    assert copies.tags[result["previous_image"]] == iid("c")
    assert copies.tags[copies.second] == iid("b") and copies.first not in copies.tags
    assert copies.verified == [(copies.d.id, iid("a"), "2.1.4")]
    assert not any("{{.Created}}" in a for a in copies.calls)


def test_aliases_are_one_copy_not_an_ambiguous_choice(copies):
    copies.tags[copies.second] = iid("a")
    inventory = v.base_rollback_inventory()
    assert len(inventory.copies) == 1
    item = inventory.copies[0]
    assert item.image_id == iid("a") and item.aliases == (copies.first, copies.second)
    assert item.version == "2.1.4" and item.definition.version == copies.d.version
    result = v.rollback_base(plan=v.select_base_rollback(inventory))
    assert copies.first not in copies.tags and copies.second not in copies.tags
    assert copies.tags[result["previous_image"]] == iid("c")
    assert copies.tags[copies.d.image] == iid("a")


@pytest.mark.parametrize("selector", ["nope", "a" * 12, "sha256:" + "a" * 12, "opencode-sandbox:arch-previous-" + "a" * 12])
def test_copy_selector_must_be_exact_and_in_this_distribution(copies, selector):
    with pytest.raises(c.SandboxError, match="exact listed tag or full sha256"):
        v.rollback_base(copy=selector)
    assert not copies.verified


@pytest.mark.parametrize("when", ["before", "after"])
@pytest.mark.parametrize("change", ["copy-id", "copy-missing", "alias-missing", "current-id", "current-missing", "copy-owner", "current-owner", "inspect-error"])
def test_consent_and_verification_revalidate_the_same_objects(copies, monkeypatch, when, change):
    copies.tags[copies.second] = iid("a")
    plan = v.select_base_rollback(v.base_rollback_inventory())
    def mutate():
        if change == "copy-id":
            copies.tags[copies.first] = iid("c")
        elif change == "copy-missing":
            del copies.images[iid("a")]
        elif change == "alias-missing":
            del copies.tags[copies.second]
        elif change == "current-id":
            copies.tags[copies.d.image] = iid("a")
        elif change == "current-missing":
            del copies.tags[copies.d.image]
        elif change.endswith("owner"):
            char = "a" if change == "copy-owner" else "c"
            copies.images[iid(char)]["Config"]["Labels"].pop(distros.LABEL + "managed")
        else:
            def docker(*args, **kwargs):
                return SimpleNamespace(returncode=1, stdout="", stderr="daemon unavailable")
            monkeypatch.setattr(c, "docker", docker)
    if when == "before":
        mutate()
    else:
        monkeypatch.setattr(c, "verify_image", lambda *args: mutate())
    with pytest.raises(c.SandboxError, match="changed|Cannot inspect|unmanaged"):
        v.rollback_base(plan=plan)
    assert not any(a[0] == "tag" or a[:2] == ("image", "rm") for a in copies.calls)


@pytest.mark.parametrize("change", ["daemon", "distribution"])
def test_plan_cannot_move_to_another_daemon_or_distribution(copies, monkeypatch, change):
    plan = v.select_base_rollback(v.base_rollback_inventory())
    if change == "daemon": monkeypatch.setattr(c, "_ENDPOINT", "unix:///different.sock")
    with pytest.raises(c.SandboxError, match="another distribution or daemon"):
        v.rollback_base("arch" if change == "distribution" else None, plan=plan)
    assert not copies.verified


def test_new_copy_after_consent_does_not_replace_the_selected_target(copies):
    plan = v.select_base_rollback(v.base_rollback_inventory())
    copies.add(copies.second, "b", "2.2.1", "2099-01-01")
    v.rollback_base(plan=plan)
    assert copies.tags[copies.d.image] == iid("a") and copies.tags[copies.second] == iid("b")


def test_missing_current_can_be_restored_but_not_silently_replaced_after_consent(copies):
    del copies.tags[copies.d.image]
    plan = v.select_base_rollback(v.base_rollback_inventory())
    assert plan.current_id is None
    result = v.rollback_base(plan=plan)
    assert result["previous_image"] is None and copies.tags[copies.d.image] == iid("a")


def test_current_appearing_after_missing_preview_is_not_overwritten(copies):
    del copies.tags[copies.d.image]
    plan = v.select_base_rollback(v.base_rollback_inventory())
    copies.tags[copies.d.image] = iid("c")
    with pytest.raises(c.SandboxError, match="changed since selection"):
        v.rollback_base(plan=plan)
    assert copies.tags[copies.d.image] == iid("c") and not copies.verified


def test_legacy_provenance_and_missing_creation_time_are_kept(copies):
    info = copies.images[iid("a")]
    del info["Created"]
    info["Config"]["Labels"].update({distros.LABEL + "distro-version": "12", distros.LABEL + "image-revision": "1"})
    inventory = v.base_rollback_inventory()
    assert len(inventory.copies) == 1 and inventory.copies[0].definition.version == "12"
    assert "definition revision 1" in "\n".join(v.format_base_rollback_copies(inventory))
    assert v.select_base_rollback(inventory).selected.image_id == iid("a")


def test_rollback_guards_cover_rechecks_and_swaps_but_not_long_verification(copies, monkeypatch):
    held = []
    real_lock, real_docker = c.base_lock, c.docker
    @contextmanager
    def lock(distro, phase, **kwargs):
        with real_lock(distro, phase, **kwargs):
            held.append(phase)
            try: yield
            finally: held.pop()
    def docker(*args, **kwargs):
        assert held == ["build", "publication"]
        return real_docker(*args, **kwargs)
    def verify(distro, ref, version):
        assert held == ["build"] and ref == iid("a")
    monkeypatch.setattr(c, "base_lock", lock)
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c, "verify_image", verify)
    v.rollback_base()
    assert not held


def test_current_copy_alias_is_a_verified_noop(copies):
    copies.tags[copies.first] = iid("c")
    result = v.rollback_base()
    assert result["unchanged"] and result["previous_image"] is None
    assert copies.first in copies.tags and copies.verified == [(copies.d.id, iid("c"), "2.2.0")]
    assert not any(a[0] == "tag" or a[:2] == ("image", "rm") for a in copies.calls)


def test_legacy_copy_without_version_label_probes_only_immutable_identity(copies, monkeypatch):
    del copies.images[iid("a")]["Config"]["Labels"][v.VERSION_LABEL]
    assert v.base_rollback_inventory().copies[0].version is None
    probes = []
    monkeypatch.setattr(v, "image_version", lambda ref: probes.append(ref) or "2.1.4")
    assert v.rollback_base()["version"] == "2.1.4"
    assert probes == [iid("a")]


@pytest.mark.parametrize("failure", ["definition", "version", "collision"])
def test_failed_verification_or_copy_tag_collision_preserves_everything(copies, monkeypatch, failure):
    before = copies.tags.copy()
    if failure == "collision":
        import secrets
        monkeypatch.setattr(secrets, "token_hex", lambda _: "a" * 12)
    elif failure == "version":
        copies.images[iid("a")]["Config"]["Labels"][v.VERSION_LABEL] = "3.0.0"
    else:
        def verify(*args):
            raise c.SandboxError("current definition tools/OS do not match")
        monkeypatch.setattr(c, "verify_image", verify)
    with pytest.raises(c.SandboxError, match="definition|not supported|already exists"):
        v.rollback_base()
    assert copies.tags == before


def test_named_foreign_copy_is_not_ownership_permission(copies):
    copies.images[iid("a")]["Config"]["Labels"] = {}
    with pytest.raises(c.SandboxError, match="unmanaged"):
        v.base_rollback_inventory()
    assert not copies.verified


def invoke(*args):
    return CliRunner().invoke(cli.app, ["opencode", "rollback-base", *args])


def test_cli_list_is_read_only_and_consolidates_aliases(copies, monkeypatch):
    copies.tags[copies.second] = iid("a")
    monkeypatch.setattr(cli, "_confirm", lambda *a, **k: pytest.fail("list cannot ask for consent"))
    result = invoke("--list")
    assert result.exit_code == 0, result.output
    assert result.output.count(iid("a")) == 1
    assert copies.first in result.output and copies.second in result.output and "build label" in result.output
    assert not copies.verified and all(a[0] == "image" for a in copies.calls)


@pytest.mark.parametrize("yes", [False, True])
def test_cli_multiple_copies_require_a_choice_even_with_yes(copies, monkeypatch, yes):
    copies.add(copies.second, "b", "2.1.3", "2026-10-01")
    monkeypatch.setattr(cli, "_confirm", lambda *a, **k: pytest.fail("no target to confirm"))
    result = invoke(*(["--yes"] if yes else []))
    assert result.exit_code != 0
    assert "Several distinct rollback copies" in str(result.exception)
    assert "--copy" in str(result.exception) and iid("a") in str(result.exception)
    assert not copies.verified


@pytest.mark.parametrize("accept", [False, True])
def test_cli_confirms_exact_target_and_preserves_cancel(copies, monkeypatch, accept):
    def confirm(question, **kwargs):
        assert iid("a") in question and iid("c") in question and copies.d.image in question
        return accept
    monkeypatch.setattr(cli, "_confirm", confirm)
    result = invoke()
    assert (result.exit_code == 0) == accept, result.output
    assert (copies.tags[copies.d.image] == iid("a")) == accept
    assert "Existing containers and writable layers are unchanged" in result.output


@pytest.mark.parametrize("change", ["current", "copy"])
def test_cli_changes_during_confirmation_are_refused(copies, monkeypatch, change):
    def confirm(*args, **kwargs):
        copies.tags[copies.d.image if change == "current" else copies.first] = iid("a" if change == "current" else "c")
        return True
    monkeypatch.setattr(cli, "_confirm", confirm)
    result = invoke()
    assert result.exit_code != 0 and "changed" in str(result.exception)
    assert not copies.verified


def test_cli_yes_with_explicit_id_does_not_prompt(copies, monkeypatch):
    copies.add(copies.second, "b", "2.1.3", "2026-10-01")
    monkeypatch.setattr(cli, "_confirm", lambda *a, **k: pytest.fail("--yes must not prompt"))
    result = invoke("--copy", iid("a"), "--yes")
    assert result.exit_code == 0, result.output
    assert copies.tags[copies.d.image] == iid("a") and "replaced image kept as" in result.output


def test_cli_no_terminal_requires_yes_without_mutation(copies, monkeypatch):
    monkeypatch.setattr(c, "_tty", lambda: False)
    result = invoke()
    assert result.exit_code != 0 and "No terminal to confirm" in str(result.exception)
    assert not copies.verified
    assert invoke("--yes").exit_code == 0


def test_cli_list_rejects_selection_and_empty_list_is_not_a_failure(copies):
    result = invoke("--list", "--copy", copies.first)
    assert result.exit_code != 0 and "cannot be combined" in str(result.exception)
    del copies.tags[copies.first]
    result = invoke("--list")
    assert result.exit_code == 0 and "No rollback copy" in result.output
    result = invoke("--yes")
    assert result.exit_code != 0 and "No rollback copy" in str(result.exception)
