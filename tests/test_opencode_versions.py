"""G02/G03: registry lookup, semver comparison, policies, base/env updates."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v


@pytest.mark.parametrize("a,b,expected", [
    ("1.10.0", "1.9.9", 1),            # string comparison gets this wrong
    ("2.1.4", "v2.1.4", 0),
    ("1.0.0-beta", "1.0.0", -1),
    ("1.0.0-alpha.2", "1.0.0-alpha.10", -1),
    ("1.0.0-alpha", "1.0.0-alpha.1", -1),
    ("1.0.0-alpha.beta", "1.0.0-alpha.1", 1),
    ("2.0.0+build.5", "2.0.0", 0),
])
def test_semver_compare(a, b, expected):
    assert v.compare(a, b) == expected
    assert v.compare(b, a) == -expected


def test_describe_never_offers_a_downgrade():
    assert v.describe("2.1.4", "2.1.4") == "current"
    assert v.describe("2.9.0", "2.10.0").startswith("update available")
    assert v.describe("2.10.0", "2.9.0").startswith("newer than npm latest")


@pytest.fixture
def registry(monkeypatch):
    """Real HTTP over loopback; each test sets the response."""
    state = {"status": 200, "body": b"{}", "delay": 0}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            import time
            time.sleep(state["delay"])
            self.send_response(state["status"])
            self.end_headers()
            self.wfile.write(state["body"])

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(v, "REGISTRY", f"http://127.0.0.1:{srv.server_port}/@opencode%2fcli/latest")
    yield state
    srv.shutdown()


def test_latest_reads_registry(registry):
    registry["body"] = json.dumps({"version": "2.1.4"}).encode()
    assert v.latest() == "2.1.4"


@pytest.mark.parametrize("status,body", [
    (500, b"oops"), (404, b"{}"), (200, b"not json"), (200, b'{"name":"x"}'),
    (200, json.dumps({"version": "1.0; rm -rf /"}).encode()), (200, b"[" + b" " * 70000 + b"]"),
])
def test_latest_failures_are_clean_errors(registry, status, body):
    registry.update(status=status, body=body)
    with pytest.raises(c.SandboxError):
        v.latest()


def test_latest_timeout(registry):
    registry.update(body=b'{"version":"1.0.0"}', delay=1.5)
    with pytest.raises(c.SandboxError, match="Cannot check"):
        v.latest(timeout=0.3)


def test_latest_offline(monkeypatch):
    monkeypatch.setattr(v, "REGISTRY", "http://127.0.0.1:9/unreachable")
    with pytest.raises(c.SandboxError, match="Cannot check"):
        v.latest(timeout=2)


def test_versions_survive_one_invalid_policy(monkeypatch):
    c.create("good", "scratch")
    bad = c.create("bad", "scratch")
    bad["opencode_policy"] = "yolo"
    c.save(bad)
    monkeypatch.setattr(v, "environment_version", lambda m: {"state": "stopped", "version": None})
    rows = {r["name"]: r for r in v.versions()}
    assert rows["good"]["state"] == "stopped"
    assert rows["bad"]["state"].startswith("error")


def fake_docker(calls, installed="2.1.4", same=False, os_release='ID=debian\nVERSION_ID="12"', problems=""):
    def docker(*a, **k):
        calls.append(a)
        if a[0] == "run":  # verify_image: os-release line, then `opencode --version`
            facts = "".join(f"ocs-os: {line}\n" for line in os_release.splitlines())
            return SimpleNamespace(returncode=0, stdout=f"{facts}{problems}opencode v{installed}\n", stderr="")
        if a[:2] == ("image", "inspect"):
            new = "-candidate-" in a[-1] and not same
            return SimpleNamespace(returncode=0, stdout=("layers:new" if new else "layers:old") + "\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return docker


def test_update_base_latest_builds_explicit_version(monkeypatch):
    """Build arg 'latest' was served from Docker's layer cache."""
    calls = []
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", fake_docker(calls))
    monkeypatch.setattr(v, "latest", lambda timeout=8: "2.1.4")
    result = v.update_base("latest")
    build = next(a for a in calls if a[0] == "build")
    assert "OPENCODE_VERSION=2.1.4" in build and "OPENCODE_VERSION=latest" not in build
    assert result["version"] == "2.1.4" and result["previous_image"].startswith("opencode-sandbox:debian-previous-")
    assert build[build.index("-t") + 1].startswith("opencode-sandbox:debian-candidate-")
    for label in ("distro=debian", "distro-version=12", "image-revision=1", "opencode-version=2.1.4",
                  "opencode-package=@opencode/cli", "managed=true"):
        assert "org.opencode-sandbox." + label in build
    assert build[-3:] == ("-f", str(c.distros.IMAGES / "debian" / "Dockerfile"), str(c.distros.IMAGES))
    assert ("tag", "layers:old", result["previous_image"]) in calls
    assert ("image", "rm", "layers:old") not in calls  # kept as the rollback copy
    assert any(a[:2] == ("image", "rm") for a in calls)  # candidate removed


def test_build_refuses_image_whose_os_differs_from_the_registry(monkeypatch):
    calls = []
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", fake_docker(calls, os_release='ID=debian\nVERSION_ID="13"'))
    with pytest.raises(c.SandboxError, match="reports ID=debian, VERSION_ID=13; the registry expects ID=debian, VERSION_ID=12"):
        v.update_base("2.1.4")
    assert not any(a[0] == "tag" for a in calls)
    run = next(a for a in calls if a[0] == "run")
    assert ("--security-opt", "no-new-privileges:true") == run[4:6]


def test_rolling_release_is_checked_by_build_id(monkeypatch):
    """Arch has no fixed VERSION_ID (it is the upstream image date): BUILD_ID=rolling is pinned."""
    calls = []
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", fake_docker(calls, os_release="ID=arch\nBUILD_ID=rolling\nVERSION_ID=20261018.0.612668"))
    assert v.update_base("2.1.4", "arch")["image"] == "opencode-sandbox:arch"
    build = next(a for a in calls if a[0] == "build")
    assert "org.opencode-sandbox.distro-version=rolling" in build and build[-2] == str(c.distros.IMAGES / "arch" / "Dockerfile")
    monkeypatch.setattr(c, "docker", fake_docker([], os_release="ID=arch\nVERSION_ID=20261018.0.612668"))
    with pytest.raises(c.SandboxError, match="BUILD_ID=\\?"):
        v.update_base("2.1.4", "arch")


def test_build_refuses_image_without_the_promised_tools(monkeypatch):
    calls = []
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    problems = "ocs-problem: paru is not on PATH\nocs-problem: paru --version failed\n"
    monkeypatch.setattr(c, "docker", fake_docker(calls, os_release="ID=arch\nBUILD_ID=rolling", problems=problems))
    with pytest.raises(c.SandboxError, match="paru is not on PATH; paru --version failed"):
        v.update_base("2.1.4", "arch")
    assert not any(a[0] == "tag" for a in calls)
    script = next(a for a in calls if a[0] == "run")[-1]
    assert "for t in bash git" in script and " paru ocs-aur; do" in script and "sh -c 'ocs-aur --version'" in script


def test_update_base_refuses_stale_build(monkeypatch):
    calls = []
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", fake_docker(calls, installed="2.1.3"))
    monkeypatch.setattr(v, "latest", lambda timeout=8: "2.1.4")
    with pytest.raises(c.SandboxError, match="expected 2.1.4"):
        v.update_base("latest")
    assert not any(a[0] == "tag" for a in calls)  # base image untouched


def test_update_base_latest_offline_is_an_error(monkeypatch):
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: pytest.fail("docker must not be called"))
    def offline(timeout=8):
        raise c.SandboxError("Cannot check OpenCode npm registry: offline")
    monkeypatch.setattr(v, "latest", offline)
    with pytest.raises(c.SandboxError, match="Cannot check"):
        v.update_base("latest")


def test_build_resolves_latest_and_keeps_no_rollback_copy(monkeypatch):
    calls = []
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", fake_docker(calls))
    monkeypatch.setattr(v, "latest", lambda timeout=8: "2.1.4")
    result = c.build()
    assert result == {"version": "2.1.4", "previous_image": None, "image": "opencode-sandbox:debian"}
    assert "OPENCODE_VERSION=2.1.4" in next(a for a in calls if a[0] == "build")
    assert [a for a in calls if a[0] == "tag"] == [("tag", next(a for a in calls if a[0] == "build")[-4], "opencode-sandbox:debian")]
    assert ("image", "rm", "layers:old") in calls  # the replaced image is not left behind untagged


def test_build_without_registry_access_is_an_error(monkeypatch):
    """The image label and the verification need a concrete version (no cached "latest")."""
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: pytest.fail("docker must not be called"))
    def offline(timeout=8):
        raise c.SandboxError("Cannot check OpenCode npm registry: offline")
    monkeypatch.setattr(v, "latest", offline)
    with pytest.raises(c.SandboxError, match="Cannot check"):
        c.build()
    with pytest.raises(c.SandboxError, match="Unknown distribution 'nope'"):
        c.build("nope", "2.1.4")


def test_pinned_environment_refuses_other_versions(monkeypatch):
    m = c.create("pin", "scratch")
    v.set_policy(m, "pinned", "2.1.3")
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: pytest.fail("docker must not be called"))
    for target in ("latest", "2.1.4"):
        with pytest.raises(c.SandboxError, match="pinned"):
            v.update_environment(m, target)
    with pytest.raises(c.SandboxError):
        v.set_policy(m, "notify", "1.0.0")
    with pytest.raises(c.SandboxError):
        v.set_policy(m, "pinned", "not-a-version")


def test_update_refused_without_network(monkeypatch):
    """Npm hung >10 min in a network=none environment."""
    m = c.create("offline", "scratch")
    m["runtime"] = c.validate_runtime_settings({**c.runtime_settings(m), "network": "none"})
    c.save(m)
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: pytest.fail(f"docker called: {a}"))
    with pytest.raises(c.SandboxError, match="network=none"):
        v.update_environment(m, "2.1.3")


def test_npm_install_is_bounded(monkeypatch):
    m = c.create("online", "scratch")
    calls = []
    versions = iter(["2.1.2\n", "2.1.3\n"])
    def docker(*a, **k):
        calls.append(a)
        if a[:3] == ("exec", c.cname(m), "opencode"):
            return SimpleNamespace(returncode=0, stdout=next(versions), stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False})
    monkeypatch.setattr(c, "docker", docker)
    assert v.update_environment(m, "2.1.3")["version"] == "2.1.3"
    install = next(a for a in calls if "ocs-install-opencode" in a)
    assert install[2:] == v.INSTALL + ("2.1.3",)
    assert "--fetch-timeout=60000" in v.INSTALL[2] and "--fetch-retries=1" in v.INSTALL[2]
    assert calls[-1][:2] == ("stop", c.cname(m))


def test_identical_rebuild_creates_no_rollback_tag(monkeypatch):
    """Every update-base added an oc-previous tag, even when nothing changed."""
    calls = []
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "docker", fake_docker(calls, same=True))
    result = v.update_base("2.1.4")
    assert result["previous_image"] is None and result["unchanged"]
    assert not any(a[0] == "tag" for a in calls)
    assert any(a[:2] == ("image", "rm") for a in calls)  # candidate still removed


@pytest.mark.parametrize("raw,expected", [("opencode v2.1.4\n", "2.1.4"), ("v2.1.4", "2.1.4"), ("2.1.4", "2.1.4"),
                                          ("warning: x\nopencode v2.2.0-beta.1", "2.2.0-beta.1")])
def test_v2_version_output_is_normalized(raw, expected):
    assert v.normalize(raw) == expected


@pytest.mark.parametrize("bad", ["1.19.4", "0.0.0-dev-84", "opencode v1.19.3"])
def test_v1_and_dev_versions_are_not_installable(bad):
    with pytest.raises(c.SandboxError, match="not supported; this manager installs OpenCode 2.x only"):
        v.supported(bad)
    with pytest.raises(c.SandboxError):
        v.policy({"opencode_policy": "pinned", "opencode_pin": bad})


def test_v1_pin_refused_before_metadata_changes():
    m = c.create("ocs-qa-v1pin", "scratch")
    with pytest.raises(c.SandboxError, match="not supported"):
        v.set_policy(m, "pinned", "1.19.3")
    assert c.resolve(m["id"]).get("opencode_pin") is None


def test_one_install_script_for_builds_and_updates():
    """Same script in the Dockerfile RUN and in `docker exec sh -c` updates, platform-package pruning included."""
    script = (c.distros.IMAGES / "common" / "install-opencode.sh").read_text()
    assert v.PACKAGE == "@opencode/cli" and "%2fcli" in v.REGISTRY
    assert v.INSTALL == ("sh", "-c", script, "ocs-install-opencode")
    assert "umask 022" in script and f"--allow-scripts={v.PACKAGE}" in script and f'"{v.PACKAGE}@$version"' in script
    assert 'rm -rf "$root"/node_modules/@opencode/cli-*' in script
    assert 'export HOME="$scratch/home" TMPDIR="$scratch"' in script  # nothing left in /root or /tmp
    for distro in c.distros.REGISTRY.values():
        assert "COPY common/install-opencode.sh" in distro.dockerfile.read_text()
