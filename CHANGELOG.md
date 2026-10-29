# Changelog

All notable changes to OpenCode Sandbox are recorded here. Versions follow
[Semantic Versioning](https://semver.org/); the format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 6.0.0 — Unreleased

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
