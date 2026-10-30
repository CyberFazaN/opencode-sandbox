# Changelog

All notable changes to OpenCode Sandbox are recorded here. Versions follow
[Semantic Versioning](https://semver.org/); the format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 6.1.0 — 2026-10-30

Compatibility and reliability update (Beta). Python 3.11 or newer; the Debian base image is now
Debian 13. Tested with real Docker on Arch Linux only.

### Added

- Bounded Rootless Docker readiness: daemon acquisition shares one cancellable 10-second budget,
  shows a waiting notice in the CLI and the dashboard, and the dashboard's Refresh (`r`) retries
  the prerequisite checks. A ready daemon stays fast; permanent failures still fail at once, and
  Docker mutations are never retried.
- Socket-activated rootless daemons: the identity check now authenticates the kernel
  credentials of the process that actually sends the response, so a systemd listener is
  accepted only when your own rootless `dockerd` answers. Proxies are still refused.
- Resource-limit support diagnostics in `doctor`, `check NAME` and the dashboard: cgroup
  version and driver, and Docker-reported CPU quota, memory and PID limit support. Missing
  support is a warning and missing evidence is `not checked`; nothing changes host settings or
  blocks existing environments.
- Base-image revision checks in `doctor` and at dashboard startup: managed base images are
  compared with the manager's image definitions, an inspection failure is no longer reported as
  a missing image, and the hints to rebuild or review never block existing environments.
- Python 3.11, 3.12 and 3.13 are accepted (the minimum was 3.14). 3.11 and 3.14 are tested;
  3.12 and 3.13 are not tested separately. CI covers 3.11 and 3.14 with current and lowest
  direct dependencies, plus the rolling Arch Linux Python.

### Changed

- The Debian image definition is Debian 13 (`node:24-trixie`), image revision 2. Upgrading the
  manager does not rebuild images: run `opencode-sandbox build --distro debian` when `doctor`
  reports revision 1. Existing containers and system backups keep their OS; nothing is migrated.
- Agent Context and `status NAME` take the base OS version from the image's build labels, or
  report it as unknown, instead of the current definition; Debian 12 environments are no longer
  described as Debian 13.
- `doctor` exit status 0 means that host programs and the daemon identity are verified;
  resource, image or storage warnings can accompany it. The per-environment "Resource limits"
  check describes the container configuration, not measured enforcement.
- pipx from a GitHub release tag is the only installation method. The installation guide covers
  moving from the 6.0.0 source installer and repairing pipx after a Python minor upgrade.
- Rootless Docker setup documentation refers to Docker's official guide, the distribution's
  documentation and the ArchWiki instead of a host installation recipe, and states what the
  diagnostics do not verify.

### Fixed

- Catchable exit signals during interactive client creation no longer bypass host-client
  cleanup. The manager records the client PID before delivering the signal, then hangs up
  the session; a client that needs a forced kill is also reaped.
- Terminal settings are restored after an interactive session, even when the client exits
  without undoing raw mode.

### Removed

- Root-level `install.sh` and `setup-rootless.sh`. Existing installations and environments are
  not modified; remove a 6.0.0 source installation with `./install.sh uninstall` from the 6.0.0
  sources ([docs/install.md](docs/install.md#moving-from-a-legacy-source-installation)).

## 6.0.0 — 2026-10-29

Initial public release (Beta). For Linux hosts with rootless Docker; tested with real Docker on
Arch Linux only. See README for the tested versions and the known limitations.

### Added

- Per-environment OpenCode V2 (`@opencode/cli` 2.x) containers on the current user's own
  rootless Docker daemon; the daemon's identity is verified before use, and rootful, other
  users', remote and proxied daemons are refused.
- Environment kinds scratch, project (a Git clone or a filtered copy of a folder) and quick
  (disposable session); managed workspaces by default and, not recommended, direct host
  workspaces with consent, path checks and a preflight.
- Base images for Debian 12 (default) and Arch Linux (AUR through `ocs-aur`), built locally;
  custom images with `create --image`.
- Provider credential profiles (JSON, mode 0600) mounted read-only into the container.
- Settings for CPU, memory, processes, network (`bridge` or `none`), published ports
  (127.0.0.1 only) and the provider profile through one change plan (`config plan|apply`).
- Git change review and transfer: `changes show|export|bundle|inspect|review|stage|apply`;
  host Git never uses the workspace's configuration.
- Cold backups with checksums, validated restores into new environments, snapshots and
  container recreation; journalled operations with explicit recovery commands.
- OpenCode version policies (notify, manual, pinned), per-environment update and rollback,
  base image updates with rollback copies; OpenCode's own self-update is disabled.
- One-time initial integrations (Context7 by default) and injected sandbox guidance (Agent
  Context).
- Read-only readiness checks (`check`, `doctor`) including measured network reachability; disk
  usage and conservative cleanup.
- Textual dashboard (usable at 80x24) and a Typer CLI; installer `install.sh` for source
  checkouts.
