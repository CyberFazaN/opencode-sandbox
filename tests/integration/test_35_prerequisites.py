"""Host prerequisites against the real CLI and the real Docker CLI (campaign row C09, D-042):
a missing Docker CLI or Git, a context that does not exist, a missing socket, a file instead of a
socket, a TCP endpoint and a missing terminal are each reported with their classification, hint
and exit status; the dashboard opens without Docker and says so. The user's Docker configuration
is never touched: the test contexts live in a private DOCKER_CONFIG, and PATH is reduced to
symlinks of the needed programs."""
import os
import shutil

import pytest
from campaign import MANAGER

pyte = pytest.importorskip("pyte")
from pty_term import Term

TOOLS = ("python3", "python", "git", "docker", "bash", "sh", "env", "cat", "ls", "id", "stat", "readlink")


def tools(base, without):
    path = base / f"bin-no{without}"
    path.mkdir(exist_ok=True)
    for name in TOOLS:
        found = shutil.which(name)
        if name != without and found and not (path / name).exists():
            (path / name).symlink_to(found)
    return str(path)


def test_prerequisites_are_diagnosed(campaign, checks):
    camp, ck = campaign, checks
    base = camp.short_dir("prerequisites")  # holds the test sockets
    real = camp.docker("context", "inspect", "rootless", "--format", "{{.Endpoints.docker.Host}}").stdout.strip()
    config = base / "dockercfg"
    contexts = {"rootless": real, "ocs-test-nosocket": f"unix://{base}/missing.sock",
                "ocs-test-tcp": "tcp://127.0.0.1:1", "ocs-test-file": f"unix://{base}/notasocket"}
    (base / "notasocket").touch()
    for name, host in contexts.items():
        camp._run(["docker", "--config", str(config), "context", "create", name, "--docker", f"host={host}"], check=True)
    env = dict(camp.env, DOCKER_CONFIG=str(config))
    no_docker = dict(env, PATH=tools(base, "docker"))
    no_git = dict(env, PATH=tools(base, "git"))
    camp.create("ocs-test-prereq")
    repo = base / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "x"]):
        camp._run(["git", "-C", str(repo), *args], check=True)

    rows = [
        ("--help without Docker", no_docker, ["--help"], 0, "Usage"),
        ("--version without Docker", no_docker, ["--version"], 0, "opencode-sandbox "),
        ("list without Docker", no_docker, ["list"], 0, "ocs-test-prereq"),
        ("doctor without the Docker CLI", no_docker, ["doctor"], 7, "Daemon identity: missing"),
        ("start without the Docker CLI", no_docker, ["start", "ocs-test-prereq"], 7, "pacman -S docker"),
        ("doctor, context does not exist", dict(env, OPENCODE_SANDBOX_DOCKER_CONTEXT="ocs-test-absent"), ["doctor"], 8,
         "Docker context 'ocs-test-absent' does not exist"),
        ("doctor, socket missing", dict(env, OPENCODE_SANDBOX_DOCKER_CONTEXT="ocs-test-nosocket"), ["doctor"], 5,
         "Daemon identity: unavailable"),
        ("doctor, TCP endpoint", dict(env, OPENCODE_SANDBOX_DOCKER_CONTEXT="ocs-test-tcp"), ["doctor"], 6,
         "Daemon identity: unsupported"),
        ("doctor, a file instead of a socket", dict(env, OPENCODE_SANDBOX_DOCKER_CONTEXT="ocs-test-file"), ["doctor"], 6,
         "is not a socket"),
        ("doctor without Git", no_git, ["doctor"], 7, "Git: not found on PATH"),
        ("create from Git without Git", no_git, ["create", "ocs-test-prereq-git", "--source", str(repo)], 7, "Install Git"),
        ("delete without a terminal", env, ["delete", "ocs-test-prereq"], 2, "confirm with --yes"),
        ("recreate without a terminal", env, ["container", "recreate", "ocs-test-prereq"], 2, "Confirm with --yes"),
        ("tui without a terminal", env, ["tui"], 2, "needs an interactive terminal"),
        ("doctor, verified", env, ["doctor"], 0, "Daemon identity: verified"),
    ]
    for label, row_env, args, code, text in rows:
        p = camp.ocs(*args, check=False, env=row_env)
        out = p.stdout + p.stderr
        ck(p.returncode == code and text in out and "Traceback" not in out,
           f"C09 {label}: exit {p.returncode} (expected {code}), {text!r} {'shown' if text in out else 'missing'}")
    ck("ocs-test-prereq-git" not in camp.ocs("list").stdout, "C09 a refused creation leaves no environment")
    ck(camp.metadata("ocs-test-prereq") is not None, "C09 the refused deletion kept the environment")

    t = Term([*MANAGER], 80, 24, env=dict(no_docker, TERM="xterm-256color"), log=camp.log)
    try:
        ck(t.wait_for("Docker is not ready", 30), "C09 dashboard without Docker opens and says so (80x24)")
        ck("ocs-test-prereq" in t.text(), "C09 dashboard without Docker still lists the environments")
        t.send("?", 1)
        ck("Keys" in t.text() or "keys" in t.text(), "C09 dashboard without Docker answers keys")
        t.send("\x1b", 1)
        t.send("q", 1)
        ck(t.exit_code() == 0 and t.restored(), "C09 dashboard quits cleanly, terminal restored")
    finally:
        t.close()
    ck(sorted(os.listdir(config / "contexts" / "meta")) and "ocs-test-tcp" not in camp.docker("context", "ls").stdout,
       "C09 the test contexts exist only in the private DOCKER_CONFIG")
