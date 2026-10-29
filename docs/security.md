# Security model

OpenCode Sandbox reduces the risk of letting a coding agent run commands. It is not a hardened
isolation boundary. Read this page before you give an agent work you would not run yourself.

## What the sandbox gives you

- The agent runs in a container of **your own rootless Docker daemon**. It is root inside the
  container, and container root maps to **your user** on the host, not to the host's root. A
  container escape would have your user's privileges.
- With a managed workspace (the default) the agent works on a copy; your project changes only
  when you transfer the changes ([changes.md](changes.md)).
- Host files are visible only at `/workspace` (and read-only manager files under `/run`). The
  manager never mounts the Docker socket into a container and never uses `--privileged` or host
  networking.
- Containers run with `no-new-privileges` and without the capabilities `NET_RAW` and `MKNOD`;
  published ports bind to `127.0.0.1` only.
- OpenCode's self-update is disabled; versions change only through the manager.

## What it does not give you

- **No protection against kernel or container-runtime exploits.** Rootless Docker reduces the
  damage, it does not prevent an escape. For code you consider hostile, use a virtual machine.
- **No network isolation in `bridge` mode** (the default): the agent reaches the internet, your
  local network and services on the host's LAN address; only the host's loopback is blocked.
  There is no egress filtering. Use `--network none` to cut the network entirely
  ([settings.md](settings.md#network-modes)).
- **Credentials are readable by the agent.** The provider profile is mounted into the container,
  and root there can read it. Use scoped, budget-limited keys ([providers.md](providers.md)).
- **A direct workspace is your folder.** The agent can change and delete your files immediately,
  and write files that host tools act on later (Git hooks and configuration, editor, direnv and
  build configuration) ([workspaces.md](workspaces.md#direct-workspaces-not-recommended)).
- **The system layer is the agent's.** The root filesystem inside the container is writable;
  packages the agent installs (including AUR packages) run as root in the container.
- **Backups are not encrypted** and contain what the agent stored in `/root`, which may include
  credentials. Only restore backups you trust: their system image is executable content.
- The Agent Context is guidance for the model, not a security policy.

## Daemon identity

Before any Docker command, the manager verifies that the Docker endpoint is your own rootless
daemon. The same check runs in `doctor`, `check`, the dashboard and the source-checkout
installer. It resolves the Docker context (`OPENCODE_SANDBOX_DOCKER_CONTEXT`, default
`rootless`) to its endpoint and then:

- requires a local `unix://` socket without TLS material (`tcp://`, `ssh://` and TLS are
  **unsupported**);
- connects and reads the socket peer's credentials (`SO_PEERCRED`): the peer must run as your
  UID (otherwise **mismatch**: another user's daemon or a rootful daemon), must be `dockerd`
  (otherwise **unverified-proxy**, for example `socat` or a socket proxy: the daemon behind it
  is unknown), and must run in its own user namespace whose UID and GID 0 map to your UID and
  GID (otherwise **mismatch**);
- requires the engine to report the `rootless` security option (otherwise **mismatch**);
- reports a missing socket, a refused connection or a daemon that does not answer as
  **unavailable**, a Docker CLI that is not installed as **missing**, and a context that does not
  exist or has no Docker endpoint as **not-configured**.

Only **verified** is accepted. Every Docker command then runs against that socket
(`docker -H unix://<socket>`); the endpoint is fixed for the life of the process, and
`DOCKER_HOST`, `DOCKER_CONTEXT`, `DOCKER_TLS_VERIFY` and `DOCKER_CERT_PATH` are ignored. Context
names, socket paths and socket owners are shown but never trusted. What each result means for
you: [troubleshooting.md](troubleshooting.md#daemon-identity-results).

## Host Git

The repository inside a managed workspace is controlled by the agent. The `changes` commands
never use its Git configuration, hooks or drivers, escape control characters in everything they
print, and refuse symlinks that point out of the repository. Do not run host Git, editors or
build tools inside a managed workspace directory; use the `changes` commands instead.

## Known limitations

- Ownership checks rely on Docker labels. Any process that can use the same rootless Docker
  daemon can create objects with forged labels, which the manager would treat as its own. Name
  collisions with unlabelled objects are refused.
- Another process of your user could replace the daemon's socket between the check and its use
  (`$XDG_RUNTIME_DIR` is private to your user).
- The direct-workspace checks are a snapshot at each container start: a socket or mount added
  later inside the directory is visible to the running container.
- Change transfer and backups are not transactional against other processes writing at the same
  time; backups are cold.
- A process killed with `SIGKILL` cannot clean up its temporary directories (`.backup-*`, and
  `/tmp/ocs-install.*` of the source-checkout installer).

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's private vulnerability reporting
(the repository's **Security** tab), not in public issues. Scope and supported versions:
[SECURITY.md](../SECURITY.md).
