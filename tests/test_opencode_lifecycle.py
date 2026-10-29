"""D-019: OpenCode lifecycle — journalled per-environment update with checkpoint rollback,
explicit rollback, pins at container creation, self-update disabled, base rollback (mocked Docker;
real runs in tests/integration)."""
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from opencode_sandbox import core as c
from opencode_sandbox import integrations as ig
from opencode_sandbox import opencode_versions as v
from opencode_sandbox.cli import app

runner = CliRunner()


class Crash(BaseException):
    """Stands in for SIGKILL/KeyboardInterrupt: not an Exception, so no rollback runs."""


class FakeDocker:
    def __init__(self, monkeypatch, version="2.1.4", install="ok", base_label="2.1.4"):
        self.calls, self.exists, self.running = [], True, False
        self.version, self.install, self.base_label = version, install, base_label
        self.images = {"opencode-sandbox:debian"}
        monkeypatch.setattr(c, "ensure_runtime", lambda distro=None: None)
        monkeypatch.setattr(c, "ensure_volume", lambda m: None)
        monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
        monkeypatch.setattr(c, "mounted_profile", lambda m: "")
        monkeypatch.setattr(c, "observed_runtime", lambda m: None)
        monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": self.running, "Status": "exited"} if self.exists else None)
        monkeypatch.setattr(c, "docker", self)

    def ok(self, out=""):
        return SimpleNamespace(returncode=0, stdout=out, stderr="")

    def __call__(self, *args, capture=False, check=True):
        self.calls.append(args)
        op = args[0]
        if op == "commit":
            self.images.add(args[2])
        elif op == "run":
            self.exists = self.running = True
        elif op == "start":
            self.running = True
        elif op == "stop":
            self.running = False
        elif op == "rm":
            assert not self.running or "-f" in args
            self.exists = False
        elif op == "image" and args[1] == "ls":
            return self.ok("\n".join(sorted(self.images)))
        elif op == "image" and args[1] == "rm":
            self.images.discard(args[2])
        elif op == "image" and args[1] == "inspect":
            if "--format" in args and "opencode-version" in args[3]:
                return self.ok(self.base_label + "\n")
            return self.ok() if args[-1] in self.images else SimpleNamespace(returncode=1, stdout="", stderr="No such image")
        elif op == "exec" and args[2:4] == ("opencode", "--version"):
            return self.ok(f"opencode v{self.version}\n")
        elif op == "exec" and "ocs-install-opencode" in args:
            if self.install == "fail":
                raise c.SandboxError("npm ERR! network")
            if self.install == "crash":
                raise Crash()
            self.version = args[-1] if self.install == "ok" else "2.1.9"
        return self.ok()

    def ops(self):
        return [a[0] if a[0] not in ("image", "container") else " ".join(a[:2]) for a in self.calls]


def env(name="ocs-qa-up", **fields):
    m = c.create(name, "scratch", provisioning=ig.request([]))
    m.update(fields)
    c.save(m)
    return m


def test_successful_update_is_journalled_and_keeps_a_rollback_point(monkeypatch):
    fake = FakeDocker(monkeypatch)
    m = env()
    seen = []
    real_mark = c.mark
    monkeypatch.setattr(c, "mark", lambda m, state, **f: (seen.append((state, f.get("operation", m.get("operation")))), real_mark(m, state, **f)))
    result = v.update_environment(m, "2.2.0")
    assert result["version"] == "2.2.0" and result["previous_version"] == "2.1.4"
    checkpoint = result["checkpoint"]
    assert checkpoint.startswith(f"ocs-checkpoint:{m['id']}-") and checkpoint in fake.images
    ops = fake.ops()
    assert ops.index("commit") < ops.index("start") and ops[-1] == "stop" and not fake.running
    assert seen[0] == ("updating", "opencode-update")
    m = c.resolve(m["id"])
    assert m["operation"] is None and m["status"] == "stopped" and m.get("image") is None
    record = m["opencode_update"]
    assert record["state"] == "done" and record["from"] == "2.1.4" and record["to"] == "2.2.0"
    assert record["result"] == "updated 2.1.4 -> 2.2.0" and record["checkpoint"] == checkpoint
    from opencode_sandbox import cleanup
    assert checkpoint in cleanup.referenced_images([m])  # in use: not removed by cleanup --superseded


def test_same_version_changes_nothing(monkeypatch):
    fake = FakeDocker(monkeypatch, version="2.2.0")
    m = env()
    assert v.update_environment(m, "2.2.0") == {"version": "2.2.0", "previous_version": "2.2.0", "unchanged": True}
    assert not any("ocs-install-opencode" in a for a in fake.calls)
    assert not any(t.startswith("ocs-checkpoint:") for t in fake.images)
    m = c.resolve(m["id"])
    assert "opencode_update" not in m and m["operation"] is None


def test_update_repairs_a_broken_installation(monkeypatch):
    """Arch, real: a user's `opencode upgrade` left a placeholder binary (npm 12 blocks the
    postinstall); `opencode --version` fails. The update must still install."""
    fake = FakeDocker(monkeypatch)
    real = fake.__call__

    def broken(*args, capture=False, check=True):
        if args[0] == "exec" and args[2:4] == ("opencode", "--version") and fake.version == "2.1.4":
            fake.calls.append(args)
            raise c.SandboxError("Command failed (255): docker exec")
        return real(*args, capture=capture, check=check)
    monkeypatch.setattr(c, "docker", broken)
    m = env()
    result = v.update_environment(m, "2.1.5")
    assert result["previous_version"] is None and result["version"] == "2.1.5"
    assert c.resolve(m["id"])["opencode_update"]["result"] == "updated unknown (broken) -> 2.1.5"


def test_versions_report_a_broken_installation(monkeypatch):
    fake = FakeDocker(monkeypatch)
    fake.running = True
    m = env()
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="postinstall not run"))
    (item,) = [i for i in v.versions() if i["id"] == m["id"]]
    assert item["version"] is None and "`opencode --version` failed in the container" in v.environment_line(item)


def test_latest_is_resolved_on_the_host_first(monkeypatch):
    fake = FakeDocker(monkeypatch)
    monkeypatch.setattr(v, "latest", lambda timeout=8: "2.2.0")
    v.update_environment(env(), "latest")
    assert next(a for a in fake.calls if "ocs-install-opencode" in a)[-1] == "2.2.0"


@pytest.mark.parametrize("install,message", [("fail", "npm ERR! network"), ("wrong", "installed 2.1.9, expected 2.2.0")])
def test_failed_update_rolls_back_to_the_checkpoint(monkeypatch, install, message):
    fake = FakeDocker(monkeypatch, install=install)
    m = env()
    with pytest.raises(c.SandboxError, match="Rolled back") as err:
        v.update_environment(m, "2.2.0")
    assert message in str(err.value)
    m = c.resolve(m["id"])
    checkpoint = m["opencode_update"]["checkpoint"]
    assert m["image"] == m["last_snapshot"] == checkpoint and m["operation"] is None
    assert m["opencode_update"]["state"] == "rolled-back" and message in m["opencode_update"]["result"]
    assert not fake.exists  # removed; the next start creates it from the checkpoint
    c.start(m)
    run = next(a for a in fake.calls if a[0] == "run")
    assert checkpoint in run and run[run.index("--env") + 1] == "OPENCODE_DISABLE_AUTOUPDATE=1"


def test_interrupted_update_keeps_its_journal_until_update_recover(monkeypatch):
    fake = FakeDocker(monkeypatch, install="crash")
    m = env()
    with pytest.raises(Crash):
        v.update_environment(m, "2.2.0")
    m = c.resolve(m["id"])
    assert m["operation"] == "opencode-update" and m["opencode_update"]["state"] == "applying" and fake.running
    for call in (c.start, c.repair):
        with pytest.raises(c.SandboxError, match="update-recover"):
            call(m)
    c.stop(m)  # stops the container but must not erase the journal
    assert not fake.running and c.resolve(m["id"])["operation"] == "opencode-update"
    for call in (lambda: v.update_environment(m, "2.2.0"), lambda: v.rollback_environment(m)):
        with pytest.raises(c.SandboxError, match="pending operation .*update-recover"):
            call()
    result = runner.invoke(app, ["opencode", "update-recover", m["name"]])
    assert result.exit_code == 0, result.output
    m = c.resolve(m["id"])
    assert m["operation"] is None and m["image"] == m["opencode_update"]["checkpoint"]
    assert "interrupted" in m["opencode_update"]["result"]
    with pytest.raises(c.SandboxError, match="No interrupted OpenCode update"):
        v.update_recover(m)


def test_stop_keeps_every_recovery_journal(monkeypatch):
    """`stop` overwrote the operation with 'stop' and then cleared it."""
    fake = FakeDocker(monkeypatch)
    for op in sorted(c.JOURNALS):
        fake.running = True
        m = env(f"ocs-qa-j-{op}", operation=op)
        c.stop(m)
        assert not fake.running and c.resolve(m["id"])["operation"] == op


def test_explicit_rollback_snapshots_the_current_layer_first(monkeypatch):
    fake = FakeDocker(monkeypatch)
    m = env()
    checkpoint = v.update_environment(m, "2.2.0")["checkpoint"]
    fake.running = True
    with pytest.raises(c.SandboxError, match="Stop the environment"):
        v.rollback_environment(c.resolve(m["id"]))
    fake.running = False
    result = runner.invoke(app, ["opencode", "rollback", m["name"], "--yes"])
    assert result.exit_code == 0, result.output
    assert "Rolled back OpenCode 2.2.0 -> 2.1.4; previous system layer kept as ocs-snapshot:" in result.output
    snapshot = next(a[2] for a in fake.calls if a[0] == "commit" and a[2].startswith("ocs-snapshot:"))
    m = c.resolve(m["id"])
    assert m["image"] == checkpoint and m["opencode_update"]["state"] == "rolled-back" and snapshot in fake.images
    with pytest.raises(c.SandboxError, match="No completed OpenCode update"):
        v.rollback_environment(m)


def test_rollback_without_a_container_keeps_the_derived_image(monkeypatch):
    """A runtime change after the update removed the container: its system layer is the
    environment's ocs-runtime image, which the rollback would otherwise untag."""
    fake = FakeDocker(monkeypatch)
    m = env()
    checkpoint = v.update_environment(m, "2.2.0")["checkpoint"]
    m = c.resolve(m["id"]); m["image"] = runtime = f"ocs-runtime:{m['id']}-0123456789ab"; c.save(m)
    fake.images.add(runtime); fake.exists = False
    result = v.rollback_environment(m)
    assert result["snapshot"].startswith(f"ocs-snapshot:{m['id']}-")
    assert ("tag", runtime, result["snapshot"]) in fake.calls and ("image", "rm", runtime) in fake.calls
    assert c.resolve(m["id"])["image"] == checkpoint


def test_rollback_respects_the_pin_and_a_pruned_checkpoint(monkeypatch):
    fake = FakeDocker(monkeypatch)
    m = env()
    checkpoint = v.update_environment(m, "2.2.0")["checkpoint"]
    v.set_policy(c.resolve(m["id"]), "pinned", "2.2.0")
    with pytest.raises(c.SandboxError, match="pinned to OpenCode 2.2.0"):
        v.rollback_environment(c.resolve(m["id"]))
    v.set_policy(c.resolve(m["id"]), "notify")
    fake.images.discard(checkpoint)
    with pytest.raises(c.SandboxError, match="no longer exists"):
        v.rollback_environment(c.resolve(m["id"]))


def test_pinned_environment_gets_no_other_version_from_the_base_image(monkeypatch):
    fake = FakeDocker(monkeypatch, base_label="2.2.0")
    fake.exists = False
    m = env(opencode_policy="pinned", opencode_pin="2.1.4")
    with pytest.raises(c.SandboxError, match="pinned to OpenCode 2.1.4, but base image opencode-sandbox:debian has OpenCode 2.2.0"):
        c.start(m)
    assert not any(a[0] == "run" for a in fake.calls) and c.resolve(m["id"])["status"] != "error"
    fake.base_label = "2.1.4"
    c.start(c.resolve(m["id"]))
    assert fake.running
    # Derived images carry the environment's own installation: not checked.
    fake.exists, fake.base_label = False, "2.2.0"
    m = c.resolve(m["id"]); m["image"] = f"ocs-runtime:{m['id']}-abc"; c.save(m)
    fake.images.add(m["image"])  # start checks that a manager image exists
    c.start(m)


def test_environment_lines():
    pin = {"mode": "pinned", "version": "2.1.4"}
    notify, manual = {"mode": "notify", "version": None}, {"mode": "manual", "version": None}
    run = {"state": "running"}
    assert v.environment_line({**run, "policy": notify, "version": "2.1.4"}, "2.2.0") == "2.1.4; update available: 2.1.4 -> 2.2.0"
    assert v.environment_line({**run, "policy": notify, "version": "2.2.0"}, "2.2.0") == "2.2.0; current"
    assert v.environment_line({**run, "policy": notify, "version": "2.1.4"}) == "2.1.4; notify"
    assert v.environment_line({**run, "policy": manual, "version": "2.1.4"}, "2.2.0") == "2.1.4; manual"
    assert v.environment_line({**run, "policy": pin, "version": "2.1.4"}, "2.2.0") == "2.1.4; pinned"
    assert "but runs 2.2.0 (changed outside the manager)" in v.environment_line({**run, "policy": pin, "version": "2.2.0"})
    assert v.environment_line({"state": "stopped", "policy": notify, "version": None}) == "notify; not checked (stopped)"
    assert v.environment_line({"state": "error: x", "policy": None, "version": None}) == "error: x"


def test_cli_versions_check_and_status(monkeypatch):
    fake = FakeDocker(monkeypatch)
    m = env()
    fake.running = True
    monkeypatch.setattr(v, "latest", lambda timeout=8: "2.2.0")
    result = runner.invoke(app, ["opencode", "versions", "--check"])
    assert result.exit_code == 0 and "npm registry: 2.2.0" in result.output
    assert f"{m['name']}: 2.1.4; update available: 2.1.4 -> 2.2.0" in result.output
    fake.running = False
    v.update_environment(m, "2.2.0")
    monkeypatch.setattr(c, "running", lambda m: False)
    monkeypatch.setattr(c, "profile_mismatch", lambda m: None)
    result = runner.invoke(app, ["status", m["name"]])
    assert "Last OpenCode update: updated 2.1.4 -> 2.2.0" in result.output and "rollback point ocs-checkpoint:" in result.output


def test_rollback_base_swaps_with_the_newest_verified_copy(monkeypatch):
    calls, verified = [], []
    tags = {"opencode-sandbox:debian-previous-aaaaaaaaaaaa": "2026-10-01T00:00:00Z",
            "opencode-sandbox:debian-previous-bbbbbbbbbbbb": "2026-10-20T00:00:00Z",
            "opencode-sandbox:arch-previous-cccccccccccc": "2026-10-25T00:00:00Z"}

    def docker(*a, capture=False, check=True):
        calls.append(a)
        if a[:2] == ("image", "ls"):
            return SimpleNamespace(returncode=0, stdout="opencode-sandbox:debian\n" + "\n".join(tags), stderr="")
        if a[:2] == ("image", "inspect") and a[3] == "{{.Created}}":
            return SimpleNamespace(returncode=0, stdout=tags[a[4]], stderr="")
        if a[:2] == ("image", "inspect") and "opencode-version" in a[3]:
            return SimpleNamespace(returncode=0, stdout="2.1.4\n", stderr="")
        if a[:2] == ("image", "inspect"):
            return SimpleNamespace(returncode=0, stdout="sha256:current\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(c, "ensure_runtime", lambda distro=None: None)
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c, "verify_image", lambda d, tag, version: verified.append((d.id, tag, version)))
    result = v.rollback_base("debian")
    newest = "opencode-sandbox:debian-previous-bbbbbbbbbbbb"
    assert verified == [("debian", newest, "2.1.4")] and result["version"] == "2.1.4"
    tag_calls = [a for a in calls if a[0] == "tag"]
    assert tag_calls == [("tag", "sha256:current", result["previous_image"]), ("tag", newest, "opencode-sandbox:debian")]
    assert calls[-1] == ("image", "rm", newest)
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=0, stdout="opencode-sandbox:debian\n", stderr=""))
    with pytest.raises(c.SandboxError, match="No rollback copy"):
        v.rollback_base("debian")


def test_container_env_disables_opencode_self_update(monkeypatch):
    fake = FakeDocker(monkeypatch)
    fake.exists = False
    m = env()
    c.start(m)
    run = next(a for a in fake.calls if a[0] == "run")
    assert ("--env", "OPENCODE_DISABLE_AUTOUPDATE=1") == run[run.index("--env"):run.index("--env") + 2]
