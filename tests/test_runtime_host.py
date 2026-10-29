"""Default CPU limit must not exceed the host (Docker rejects --cpus > nproc)."""
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c


@pytest.mark.parametrize("ncpu,expected", [(4, "4.0"), (2, "2.0"), (16, "8.0"), (None, "1.0")])
def test_default_cpus_fit_host(monkeypatch, ncpu, expected):
    monkeypatch.setattr(c.os, "cpu_count", lambda: ncpu)
    assert c.create("ocs-qa-cpu", "scratch")["runtime"]["cpus"] == expected


def test_start_rejects_cpu_limit_above_host_before_any_state_change(monkeypatch):
    monkeypatch.setattr(c.os, "cpu_count", lambda: 4)
    m = c.create("ocs-qa-cpu", "scratch")
    m["runtime"]["cpus"] = "8.0"
    c.save(m)
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    monkeypatch.setattr(c, "docker", lambda *a, **k: pytest.fail(f"docker called: {a}"))
    with pytest.raises(c.SandboxError, match="config apply ocs-qa-cpu --cpus 4"):
        c.start(m)
    assert c.resolve(m["id"])["status"] == "ready"


def test_runtime_set_allowed_after_failed_first_start_but_not_other_journals(monkeypatch):
    monkeypatch.setattr(c.os, "cpu_count", lambda: 4)  # default 4, so "2" is a change on any host
    m = c.create("ocs-qa-cpu", "scratch")
    monkeypatch.setattr(c, "inspect_container", lambda m: None)
    from opencode_sandbox import config_plan as cp
    c.mark(m, "error", operation="start", last_error="Creation failed")
    assert cp.apply(m, {"cpus": "2"})["category"] == "saved"
    assert c.runtime_settings(c.resolve(m["id"]))["cpus"] == "2.0"
    for op in ("recreate", "delete", "restore", "runtime-recreate", "config-update"):
        c.mark(c.resolve(m["id"]), "error", operation=op)
        with pytest.raises(c.SandboxError, match="pending operation"):
            cp.apply(m, {"cpus": "1"})


def test_command_failure_names_docker_subcommand(monkeypatch):
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=125, stderr="boom", stdout=""))
    with pytest.raises(c.SandboxError, match=r"\(125\): docker run\n"):
        c.docker("run", "-d", "x", capture=True)


@pytest.mark.parametrize("tty,flags", [(False, ("-i",)), (True, ("-i", "-t"))])
def test_exec_allocates_tty_only_when_attached(monkeypatch, tty, flags):
    """'exec' must work from scripts/pipes (no TTY)."""
    m = c.create("ocs-qa-exec", "scratch")
    calls = []
    monkeypatch.setattr(c, "start", lambda m: None)
    monkeypatch.setattr(c, "_tty", lambda: tty)
    monkeypatch.setattr(c, "docker", lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=7))
    assert c.exec_cmd(m, ["true"]) == 7
    assert calls[0] == ("exec", *flags, c.cname(m), "/bin/sh", "-c", 'umask 022 && exec "$@"', "ocs-exec", "true")


def test_interactive_without_terminal_fails_clearly(monkeypatch):
    m = c.create("ocs-qa-exec", "scratch")
    monkeypatch.setattr(c, "_tty", lambda: False)
    monkeypatch.setattr(c, "start", lambda m: pytest.fail("must not start"))
    with pytest.raises(c.SandboxError, match="interactive terminal"):
        c.interactive(m)
