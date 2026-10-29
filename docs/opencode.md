# OpenCode in the sandbox

## Sessions

`run NAME` starts OpenCode V2 as root in `/workspace` with the provider profile's variables:
`opencode --standalone`, a private OpenCode server per launch. (The V2 background service would
keep the environment of whichever client started it first, so the provider keys of later
launches would be ignored.) `shell NAME` opens a root bash with the same variables; OpenCode
started from there, or from `exec`, also reads the Agent Context, but `exec` does not load the
provider profile.

If the terminal closes or the manager process ends (also by `SIGKILL`, through a per-session
watchdog), the manager hangs up the session inside the container, like a real terminal would;
jobs started with `nohup` survive.

Your own OpenCode configuration is left alone: `~/.config/opencode/` in the home volume,
project `opencode.json` and `AGENTS.md` files, and an `OPENCODE_CONFIG_CONTENT` value in the
provider profile. The manager writes OpenCode's configuration only once, for the
[initial integrations](workspaces.md#initial-integrations).

## Agent Context

The manager writes guidance for each environment that tells OpenCode about the sandbox. It
states only what the manager configures or verifies:

- **Container, user and privileges:** the image; container root (UID 0) mapped by rootless
  Docker to your host user (custom images: the image defines the user); `no-new-privileges`
  (sudo and setuid cannot raise privileges); no Docker socket, host services or host package
  managers; host files only at `/workspace` (plus read-only manager files under `/run`).
- **Workspace and persistence:** the environment's name and kind; whether `/workspace` is a copy
  of a host directory, started empty, or a host directory mounted directly (every change is
  immediate in your files, no undo, not in backups by default; the host path is never named);
  quick sessions are disposable; what survives stop and start, recreation, settings changes and
  restores.
- **Network and resources:** the network mode, published ports (host loopback only; servers must
  listen on `0.0.0.0`), CPU, memory and process limits. When the container exists, the values
  come from Docker; if they differ from the configuration, the guidance reports the container's
  values and says that the configuration applies after recreation.
- **Operating system:** the distribution, package manager, install hint, notes (Arch: AUR via
  `ocs-aur`) and the tool list of the environment's distribution, recorded at `create`, never
  guessed from the image name. Every image build checks that the listed tools exist. Snapshots,
  runtime and restored images keep these lines and are marked as derived. Custom images get no
  operating-system or tool claims.
- **Initial integrations:** the names requested at creation and the recorded outcome of the
  one-time setup (or "not done yet"), always followed by "may have been changed or removed
  since"; never what is configured now.
- **Working behaviour:** start with the task, no system inventory, follow the project's
  `AGENTS.md`; OpenCode's own update check is off, so do not run `opencode upgrade`.

**Delivery.** The guidance lives on the host in the environment's `agent-context/` directory,
which every container mounts read-only at `/run/ocs-agent/` (file `context.md`). The managed
images contain the system configuration `/etc/opencode/opencode.json` with only
`"instructions": ["/run/ocs-agent/context.md"]`. OpenCode combines `instructions` from all its
configuration files, so the guidance is added to your configuration, never replaces it. A
custom image without that file gets no guidance; `run` warns.

**Freshness.** `run` and `shell` regenerate the guidance from current metadata and the
container's settings before every launch, and a refresh is visible in a running container at
once. Commands:

```sh
opencode-sandbox agent-context show NAME     # preview
opencode-sandbox agent-context verify NAME   # compare with the container
opencode-sandbox agent-context refresh NAME  # rewrite now
```

They fall back to the configured settings (with a note) when Docker cannot be asked. The
guidance is descriptive, not a security policy. It was verified with OpenCode 2.1.4 and 2.2.0 on
Debian and Arch by capturing the first model request of a managed `run` with a fake provider;
not with real model providers.

## Versions

Only OpenCode 2.x (npm package `@opencode/cli`) is installed or pinned; a newer major version is
reported, never installed. OpenCode in a sandbox is installed and updated only by the manager:
every container runs with `OPENCODE_DISABLE_AUTOUPDATE=1`, so OpenCode's own update check and
self-update (also `update: auto` in your OpenCode configuration) are off. An `opencode upgrade`
inside a container left world-writable files, about 940 MB of platform packages and a 470 MB
npm cache in `/root`, and on Arch a broken binary.

| Command | Does |
|---|---|
| `opencode check [--distro ID]` | Compares a base image's version with the npm registry (over HTTPS, no host npm, no background checks) |
| `opencode versions [--check]` | Each environment's running version and policy (stopped containers are not started); with `--check`, environments with the notify policy report available updates |
| `opencode status NAME` | The version one environment runs |
| `opencode policy NAME`, `opencode policy-set NAME notify\|manual\|pinned [--version X]` | The update policy |
| `opencode update NAME [--version X] --yes` | Update a stopped environment |
| `opencode rollback NAME --yes` | Undo its last update |
| `opencode update-recover NAME` | Finish an interrupted update (rolls back) |
| `opencode update-base [--version X] [--distro ID]` | Rebuild a base image, keep a rollback copy |
| `opencode rollback-base [--distro ID] --yes` | Swap a base image with its newest rollback copy |

**Policies.** `notify` (the default) reports available updates with `versions --check`;
`manual` reports nothing; `pinned` refuses updates to other versions, refuses to create a
container from a base image built with another version, and reports a version changed outside
the manager.

**Environment updates.** `opencode update` works on a **stopped** environment with network. It
resolves `latest` first and refuses versions below 2.0.0. It commits a checkpoint
`ocs-checkpoint:<id>-*` of the container's system layer, journals the update, and on any
failure replaces the container with one created from the checkpoint (the system layer exactly
as before; `/root` and `/workspace` are not touched). It also repairs a broken installation.
`opencode rollback` undoes the last successful update the same way, keeping the current system
layer as an `ocs-snapshot:*` image first; the last update's checkpoint is kept as the rollback
point (`disk cleanup --superseded` keeps it).

**Base images.** `opencode update-base` builds and verifies a candidate and keeps the replaced
image as `opencode-sandbox:<distro>-previous-<hex>` (not for identical rebuilds);
`opencode rollback-base` verifies the newest rollback copy and swaps it in (the replaced image
becomes a rollback copy, so you can swap back). `build` rebuilds without a rollback copy. Base
images only affect containers created later. Rebuilds reuse Docker's cached operating-system
layers and refresh only OpenCode; update operating-system packages inside an environment with
its package manager.
