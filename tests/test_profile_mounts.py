"""F03: provider profile mounts vs assignment. Dummy values only."""
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c


def mounts_docker(mounts):
    def docker(*a, **k):
        if a[:2] == ("container", "inspect"):
            return SimpleNamespace(returncode=0, stdout=json.dumps(mounts), stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return docker


@pytest.fixture
def env():
    c.init_dirs()
    for name in ("ocs-qa-p1", "ocs-qa-p2"):
        c.profile_set(name, {"QA_KEY": "dummy-" + name})
    return c.create("ocs-qa-pm", "scratch", profile="ocs-qa-p2")


def mount(path):
    return [{"Destination": "/workspace", "Source": "/x"}, {"Destination": c.PROFILE_TARGET, "Source": str(path)}]


def test_assigned_profile_mounted_is_quiet(env, monkeypatch):
    monkeypatch.setattr(c, "docker", mounts_docker(mount(c.profile_path("ocs-qa-p2"))))
    assert c.profile_mismatch(env) is None


def test_restart_after_assign_is_reported(env, monkeypatch):
    """Real run: after 'providers assign' + stop/start the container still read profile 1."""
    monkeypatch.setattr(c, "docker", mounts_docker(mount(c.profile_path("ocs-qa-p1"))))
    warning = c.profile_mismatch(env)
    assert "'ocs-qa-p1'" in warning and "'ocs-qa-p2'" in warning and "recreate ocs-qa-pm --yes" in warning


@pytest.mark.parametrize("exists", [True, False])
def test_no_mount(env, monkeypatch, exists):
    if not exists:
        c.profile_path("ocs-qa-p2").unlink()
    monkeypatch.setattr(c, "docker", mounts_docker([{"Destination": "/workspace", "Source": "/x"}]))
    assert (c.profile_mismatch(env) is not None) == exists


def test_unknown_container_is_not_a_claim(env, monkeypatch):
    monkeypatch.setattr(c, "docker", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="No such container"))
    assert c.profile_mismatch(env) is None


def launcher(monkeypatch, tmp_path, m, show="os.environ.get('QA_KEY')"):
    """Capture the real launcher script from interactive() and run it on the host with redirected paths."""
    seen = {}
    monkeypatch.setattr(c, "_tty", lambda: True)
    monkeypatch.setattr(c, "start", lambda m: None)
    monkeypatch.setattr(c, "observed_runtime", lambda m: None)
    monkeypatch.setattr(c, "image_definition", lambda m, **k: None)  # isolate the launcher, not Docker observation
    monkeypatch.setattr(c, "profile_mismatch", lambda m: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: seen.setdefault("argv", a) and SimpleNamespace(returncode=0))
    c.interactive(m)
    argv = seen["argv"]
    i = argv.index("-c")
    script, context = argv[i + 1], argv[i + 2]
    profile = tmp_path / "ocs-provider.json"
    system = tmp_path / "opencode.json"
    system.write_text(json.dumps({"instructions": [context]}))
    script = (script.replace("/run/secrets/ocs-provider.json", str(profile))
                    .replace("os.execvp(argv[0],argv)", f"print('LAUNCH', {show})"))
    return profile, lambda: subprocess.run([sys.executable, "-c", script, context, str(system), argv[i + 4]],
                                           capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}, check=False)


@pytest.mark.parametrize("content,expected", [("", "LAUNCH None"), ("  \n", "LAUNCH None"),
                                              ('{"QA_KEY": "dummy"}', "LAUNCH dummy")])
def test_launcher_accepts_commit_stub(env, monkeypatch, tmp_path, content, expected):
    """A snapshot keeps an empty mountpoint stub; run crashed with JSONDecodeError."""
    profile, run = launcher(monkeypatch, tmp_path, env)
    profile.write_text(content)
    result = run()
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_launcher_still_rejects_invalid_profile(env, monkeypatch, tmp_path):
    profile, run = launcher(monkeypatch, tmp_path, env)
    profile.write_text('{"bad key": 1}')
    result = run()
    assert result.returncode != 0 and "Invalid provider profile" in result.stderr


def test_start_explains_removed_profile(env, monkeypatch):
    gone = c.profile_path("ocs-qa-p1")
    gone.unlink()
    calls = []
    def docker(*a, **k):
        calls.append(a)
        if a[:2] == ("container", "inspect"):
            return SimpleNamespace(returncode=0, stdout=json.dumps(mount(gone)), stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False})
    monkeypatch.setattr(c, "assert_volume_owned", lambda m: None)
    with pytest.raises(c.SandboxError, match="was removed; restore it, or recreate"):
        c.start(env)
    assert not any(a[0] == "start" for a in calls) and c.resolve(env["id"])["status"] == "ready"


def test_launcher_leaves_user_opencode_config_alone(env, monkeypatch, tmp_path):
    """A profile may carry the user's own OPENCODE_CONFIG_CONTENT; the launcher passes it through unchanged."""
    profile, run = launcher(monkeypatch, tmp_path, env, show="os.environ['OPENCODE_CONFIG_CONTENT'], argv")
    user = json.dumps({"model": "qa/model", "instructions": ["AGENTS.md"]})
    profile.write_text(json.dumps({"OPENCODE_CONFIG_CONTENT": user}))
    result = run()
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"LAUNCH {user} ['opencode', '--standalone']"
    assert "WARNING" not in result.stderr


def test_launcher_warns_when_the_image_lacks_the_system_config(env, monkeypatch, tmp_path):
    _, run = launcher(monkeypatch, tmp_path, env)
    (tmp_path / "opencode.json").write_text("{}")
    result = run()
    assert result.returncode == 0 and "will not receive the sandbox Agent Context" in result.stderr


def test_launcher_rejects_unparsable_profile(env, monkeypatch, tmp_path):
    profile, run = launcher(monkeypatch, tmp_path, env)
    profile.write_text("not json")
    result = run()
    assert result.returncode != 0 and "Invalid provider profile" in result.stderr and "LAUNCH" not in result.stdout
