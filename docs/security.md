# Security model

OpenCode Sandbox reduces the risk of letting a coding agent run commands. It is not a hardened
isolation boundary. Read this page before you give an agent work you would not run yourself.

## What the sandbox gives you

- By default the agent runs in a container of **your own rootless Docker daemon**. It is root inside the
  container, and container root maps to **your user** on the host, not to the host's root. A
  container escape would have your user's privileges.
- With a managed workspace (the default) the agent works on a copy; your project changes only
  when you transfer the changes ([changes.md](changes.md)).
- Host files are visible only at `/workspace` (and read-only manager files under `/run`). The
  manager never mounts the Docker socket into a container and never uses `--privileged` or host
  networking.
- Rootless containers run with `no-new-privileges`. Both backends drop the capabilities `NET_RAW` and `MKNOD`;
  published ports bind to `127.0.0.1` only.
- OpenCode's self-update is disabled; versions change only through the manager.

## Rootful Docker

Rootful support is off by default. When explicitly enabled and selected at creation, the
manager authenticates the local root-owned daemon at `/run/docker.sock` and requires Docker
without user namespace remapping. Access to that socket already grants host root authority.
The manager uses the daemon for the environment's lifetime.

The session starts as the host user and can become container root using passwordless
`sudo`. Rootful containers omit `no-new-privileges` to make this possible. A container escape
can have host root impact. Container-root commands can also write root-owned files and change
ownership or permissions on writable bind mounts. The manager still drops `NET_RAW` and
`MKNOD`, keeps Docker's normal separation, and leaves privileged mode, extra capabilities,
host networking and Docker socket mounts disabled.

This risk extends to the host even without a container escape. Root-owned setuid files or
files with capabilities on a writable workspace can elevate privileges if executed on the
host. Use rootless Docker for untrusted work. Prefer a managed copy, do not execute untrusted
workspace files on the host, and use storage already mounted with `nosuid` as defense in depth.

## What it does not give you

- **No protection against kernel or container-runtime exploits.** Rootless Docker reduces the
  damage, it does not prevent an escape. For code you consider hostile, use a virtual machine.
- **No egress or LAN isolation in `bridge` mode** (the default): the agent can reach the internet,
  your local network and services on the host's LAN address. The tested rootless configuration
  blocks the host's loopback; this is not a guarantee for every setup. Use `--network none` to
  disconnect the container from external networks
  ([settings.md](settings.md#network-modes)).
- **Credentials are readable by the agent.** The provider profile is mounted into the container,
  and root there can read it. Use scoped, budget-limited keys ([providers.md](providers.md)).
- **A direct workspace is your folder.** The agent can change and delete your files immediately,
  and write files that host tools act on later (Git hooks and configuration, editor, direnv and
  build configuration) ([workspaces.md](workspaces.md#direct-workspaces-not-recommended)).
- **The system layer is the agent's.** The root filesystem inside the container is writable;
  packages the agent installs (including AUR packages) run as root in the container.
- **Backups are not encrypted** and contain what the agent stored in the home volume, which may include
  credentials. Only restore backups you trust: their system image is executable content.
- The Agent Context is guidance for the model, not a security policy.

## Daemon identity

The manager verifies the selected Docker backend before using it. The same check runs in
`doctor`, `check`, Docker-backed operations and the dashboard. For rootless, the manager
resolves the Docker context (`OPENCODE_SANDBOX_DOCKER_CONTEXT`, default
`rootless`) to its endpoint and then:

- requires a local `unix://` socket without TLS material (`tcp://`, `ssh://` and TLS are
  **unsupported**);
- refuses a foreign/rootful socket peer, then sends a bounded read-only `/info` request;
- requires kernel response-sender credentials (`SCM_CREDENTIALS`) for every response byte:
  the sender must run as your UID, be `dockerd`, and live in its own user namespace whose
  UID and GID 0 map to your UID and GID (otherwise **mismatch** or **unverified-proxy**);
- requires the same authenticated response to report the exact `rootless` security option.
  An inherited systemd listener is allowed only when the actual responder passes every check.
  A proxy forwarding genuine Docker text still fails: the kernel identifies the proxy sender;
- reports a missing socket, a refused connection or a daemon that does not answer as
  **unavailable**, a Docker CLI that is not installed as **missing**, and a context that does not
  exist or has no Docker endpoint as **not-configured**.

For rootful, the manager uses the fixed `/run/docker.sock` under root-controlled directories.
The same bounded response proof must identify a local UID 0 `dockerd` with an unmapped user
namespace; Docker's security options must show neither rootless mode nor user namespace remapping.
A rootful socket is never a fallback for a failing rootless context.

Only **verified** is accepted. Commands run against the verified socket (`docker -H unix://<socket>`),
not the CLI's default context. `DOCKER_HOST`, `DOCKER_CONTEXT`, `DOCKER_TLS_VERIFY` and
`DOCKER_CERT_PATH` are ignored. Context names or socket ownership alone do not prove identity.
See [troubleshooting.md](troubleshooting.md#daemon-identity-results) for the possible results.

Readiness has a 10-second total acquisition budget, including context lookup. A ready daemon
does not sleep. Only specific transport interruptions are retried; missing/stale sockets,
permission/configuration failures and failed identity proof are not retried. Slow probes show
one waiting notice; Ctrl+C or dashboard quit cancels the preflight. The manager never starts
services itself, but connecting can trigger a listener you already configured for activation.
It never retries Docker mutations.

## Base-image coordination

Base-image guards live in `/tmp/opencode-sandbox-locks-<UID>/`, not in a selected data or
configuration directory. Their keys use your UID, the canonical verified daemon endpoint and
distribution; context aliases and daemon restarts do not split the guards. The location ignores
HOME, TMPDIR and XDG overrides and has no alternate fallback. An unsafe/unusable namespace
refuses the operation rather than silently choosing another lock location.

The manager checks ownership and private modes (0700 directory, 0600 regular single-link files),
refuses symlinks and changed path identities, and never repairs, replaces or removes lock files.
Do not delete this directory while any manager instance might be running. A crashed process
releases its locks automatically; its lock files are not stale locks to remove. Older managers,
manual Docker commands and a hostile process of your own user are outside this advisory protocol.

## OpenCode global-config transfers

Config sources and exports can contain credentials or executable plugins. The manager copies
data without executing profile code on the host; using imported config inside OpenCode is still
a trust decision. Temporary host exports have own-UID `0700` parent directories, validated
identity markers and symlink-safe traversal/cleanup. This excludes ordinary other users, not
host root or processes of your own UID. No recursive symlink dereference or arbitrary host mount
is used. Whole-tree imports do not touch system/project config or auth/state outside the defined
global config directory. See [transfer boundaries and recovery](opencode-configs.md).

Sampling/final checks, same-volume staging and recoverable exchange protect normal file-transfer
failures and observed concurrent changes. Manager/volume locks coordinate the manager, not
arbitrary writers inside a container. Prefer Apply/Reload while stopped; no hot-reload or hostile
same-UID transaction guarantee is claimed. Host transport also bounds untrusted container output
and archive metadata before decoding; file contents/credentials are not diagnostic output.

## Host Git

The repository inside a managed workspace is controlled by the agent. The `changes` commands
never use its Git configuration, hooks or drivers, escape control characters in everything they
print, and refuse symlinks that point out of the repository. Do not run host Git, editors or
build tools inside a managed workspace directory; use the `changes` commands instead.

## Known limitations

- Ownership checks rely on Docker labels. Any process that can use the same Docker
  daemon can create objects with forged labels, which the manager would treat as its own. Name
  collisions with unlabelled objects are refused.
- Another process of your user could replace the rootless socket between the check and its use
  (`$XDG_RUNTIME_DIR` is private to your user).
- The direct-workspace checks are a snapshot at each container start: a socket or mount added
  later inside the directory is visible to the running container.
- Change transfer and backups are not transactional against other processes writing at the same
  time; backups are cold.
- A process killed with `SIGKILL` cannot clean up its temporary directories (`.backup-*`).

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's private vulnerability reporting
(the repository's **Security** tab), not in public issues. Scope and supported versions:
[SECURITY.md](../SECURITY.md).
