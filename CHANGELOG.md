# Changelog

All notable changes to OpenCode Sandbox are recorded here. Versions follow
[Semantic Versioning](https://semver.org/); the format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- Opt-in **Include working changes** for managed Project Git imports, shared by CLI and dashboard:
  status/count preview, staged/unstaged index fidelity, non-ignored untracked files, binary data,
  permissions and symlinks, with read-only source access and explicit unsupported-state failures.
  Committed-only cloning remains the default.
- User-maintained **OpenCode Configs**, one-time Local/Copy creation, and shared CLI/dashboard
  global-config Export/Apply/Delete/Reload/Empty workflows. Private temporary exports survive
  screen closure; whole-tree fingerprints detect container drift; recoverable volume replacement
  preserves the original tree on failure and works while environments are stopped.
- Optional specialized Agent Context per environment, default on, retained through lifecycle and
  backups. Neutral base-image system config is reconciled at every managed start without replacing
  unrelated instructions/config; disabled contexts remain generated and mounted.
- Both base images provide `ocs-opencode`, sharing safe provider validation with managed launches,
  preserving arguments and using a private server. Interactive direct shells get a conditional hint.

### Changed

- Cleaner Updates views with a Manager summary, consistent shortcut footer, visible
  operation results and Check All. Cancel Check controls are removed; closing still cleans up checks.
- Explicit environment version checks temporarily start existing stopped containers, then restore
  their stopped state under lifecycle locks, including independent cleanup after manager death.
  Check All confirms stopped targets; F5/F6 provide explicit Start/Stop. Running updates require
  caution consent and finish stopped, without an automatic restart.
- Unsupported automatic manager updates offer manual guidance; only freshly verified GitHub pipx
  installations receive a version-specific, settings-preserving command to copy.
- Every base build, cached or refresh, upgrades system packages with fresh indexes (Debian
  `apt-get upgrade`, Arch full `pacman -Syu`); there is no opt-out. Rebuild forms separate the
  OpenCode version and cache/refresh mode. With the new neutral config/launcher assets,
  Debian/Arch image definitions advance to revisions 4/3.
- Environment OpenCode updates add opt-in **Update system packages**
  (`opencode update --update-system-packages`), off by default: installed packages are upgraded
  inside the update checkpoint first, and a failed upgrade stops before OpenCode. Package
  upgrades are not fully reversible by rollback; custom-image environments refuse the option.
- Manager Settings adds opt-in selected-text copying with accurate native/OSC 52 feedback.
  Editable inputs are excluded. Keys toggles with `?` and supports Esc/Close; compact-terminal
  feedback is more consistent.
- Dashboard and Updates button rows use one menu strip per row: unfilled, separated labels, a
  full-width selection-colored focus, underline on hover and red-text Delete. Wrapped rows no
  longer merge into tiles; Updates tabs use the default underline with an accent active label.
- Provider profiles reject `OPENCODE_CONFIG_CONTENT`, `OPENCODE_CONFIG` and `OPENCODE_CONFIG_DIR`
  at write/read/launch boundaries; native config files/profiles remain the configuration route.
  `providers list` reports an unusable profile and continues with the others (exit status 1).

### Removed

- Built-in MCP integration catalogs, creation controls and once-only provisioning metadata/logic.
  Existing user-authored OpenCode/MCP configuration is not proactively changed.

## 6.2.0 — 2026-11-02

Component Updates and recovery release (Beta). Python 3.11 or newer; environment/backup schemas
and image definitions are unchanged. Upgrading does not rebuild images, migrate environments or
enable automatic discovery. Actual post-reboot manager recovery remains unverified (accepted
release risk); no automatic reboot or recovery is performed.

### Added

- Compact Updates views (`v`) replace the dashboard's Versions report: Manager, Base Images and
  Environment OpenCode, local/cached-first without network requests or version probes on opening.
  Explicit Check has independent registry/object results and cancellable owned read-only work;
  Details discloses full evidence, errors, recovery and existing CLI guidance.
- Read-only Manager checks (`manager status --check` and Updates): official published full
  GitHub releases, dated independent failures, strict release tags and no implicit downgrade.
  Local-only pipx provenance inspection reconciles the running package, VCS record, interpreter,
  recorded source/options, actual executable/launcher and custom locations. Unsupported/editable/
  foreign/shadowed/ambiguous installs get manual guidance, never takeover or conversion. Optional
  daily discovery now includes an independent GitHub source, with no automatic installation.
- Optional daily npm metadata discovery in dashboard Preferences, off by default: durable
  attempt claims throttle failures/restarts/interruption, shared source requests coalesce across
  CLI/Updates/background callers, and Retry-After applies to explicit checks too. One quiet
  policy-filtered cached-availability indicator replaces repeated notices; no automatic runtime
  probe, start, install or persistent service. Scheduling fails closed without safe writable
  storage; bounded explicit discovery remains available.
- Explicit Environment OpenCode Start/Update/Policy/Rollback/Recover in Updates, with compact
  controls, scrollable exact consent, locked revalidation and existing checkpoint/journal handlers.
  Recovery Center can also review interrupted OpenCode updates. Approved operations survive
  closing Updates; read-only cancellation is not mutation rollback.
- Base Images Build/Rebuild and Rollback in Updates, with exact image/target/mode consent and
  rollback-preserving publication. Choose cached rebuild or explicit Refresh & Rebuild;
  `build --refresh` and `opencode update-base --refresh` pull upstream and bypass build cache
  without pruning it. App-owned builds expose bounded output in Details and survive Close.
- Early process-lifetime installation leases for supported CLI/dashboard instances, independent
  of data/configuration locations. A small stdlib bootstrap acquires shared access before CLI
  imports; internal exclusive access refuses while another instance/session/worker is alive.
  Persistent private lock files are never treated as stale or repaired. Older managers, direct
  library callers and external pipx/Docker do not honor these locks; normal startup has no bypass.
- Explicit exact-tag manager updates in Updates and `manager update --tag`, with Cancel-first
  source/commit/installation/tool/network consent, real foreground terminal restoration and
  actual worker/process-death exclusion. A frozen stdlib helper revalidates published GitHub
  source, existing pipx/Python/dependencies and effective public-default client policy before
  exact-tag replacement; no tool/Python switch, automatic restart/rollback or Update All.
  Recognized locations/source Python are retained; unknown/custom settings get manual guidance,
  not silent removal. Only inspected pipx 1.18.7 is supported. Host build code is not sandboxed,
  HTTPS/API evidence is not signed-tag authentication, and force is not a backup.
- Durable incomplete-update state and private recovery inputs outside the replaceable venv.
  A parked installer independently proves live kernel ownership and durable process admission
  before exec. Owned groups/adopted descendants are reaped without stale-PID signals; exact
  installed records/source/commit/launcher and separate runtime/CLI-health queries determine
  success, not an installer exit code or cache. Explicit frozen verify-only recovery survives a
  broken launcher, with manual previous-tag reinstall guidance. Unknown hard-interruption
  quiescence remains blocked in the same boot and may need a reboot before verification;
  no identical-dependency or offline restoration promise, automatic reboot or state reset.

### Fixed

- The dashboard's Agent Context preview has its own environment-specific heading instead of
  "OpenCode versions". When container inspection fails, it explains the configured-settings
  fallback and leaves saved guidance unverified rather than incorrectly calling it outdated.
  Readiness, cleanup and version reports retain their own headings in a shared read-only view.
- OpenCode version inventory in the CLI and dashboard keeps available local rows when npm
  discovery fails, and keeps registry results when local inventory fails. Per-environment errors
  do not hide other rows. The CLI reports partial failures on stderr with exit status 2;
  stopped containers are never started for discovery.
- Base builds, publication, rollback and cleanup now coordinate across data directories and
  context aliases for the same verified daemon. Pinned container creation holds publication
  through its version check and creation. Image identity/ownership is rechecked before changes;
  cleanup leaves busy candidates and rollback copies alone.
- Base build consent binds the existing image, exact OpenCode target, definition and refresh
  mode, rechecked before building and publication. Candidate verification uses its immutable ID;
  a retagged candidate is neither published nor silently cleaned as the operation's own image.
- Base rollback no longer guesses replacement order from Docker creation dates. It consolidates
  aliases, defaults only for one distinct copy, and requires `--copy` for several, even with
  `--yes`; `--list` shows full identities and aliases. Confirmation and execution bind to the
  same immutable copy/current base, preserving verification and the replaced image.
- Short Docker diagnostics and npm checks now have total execution/output bounds and reap their
  owned clients on timeout or cancellation. Container probes have their own deadlines; interrupted
  image helpers get bounded, label-checked cleanup. Canceled read-only dashboard workers cannot
  publish late results. Builds, installs, commits and interactive commands keep their existing timing.
- Dashboard refresh replaces or clears only its own daemon, resource-support and base-image
  advisories, including successful checks. Unknown results replace obsolete warnings without
  claiming success, and advisory/readiness cleanup preserves active operation progress and results.
- Stopped environments retain dated, identity-bound OpenCode verification or show Unknown;
  build labels and completed-update metadata are not treated as current runtime evidence.
  Disposable caches preserve successful evidence separately from failed attempts, without
  changing environment/backup schemas or starting containers for discovery.
- OpenCode discovery selects the latest supported stable 2.x release even if npm latest moves
  to another major. Explicit Manual/Pinned comparisons no longer hide newer versions; pin and
  lifecycle restrictions remain. Updates resolve exact targets before confirmation and revalidate
  them instead of silently selecting a later release.
- Updates controls stay visible at 80x24 even when dashboard advisory notices exist; their
  ownership is preserved and full messages remain available in Details. Recovery journals remain
  visible even when their container is absent.
- Checkpoint restoration failures persist their actual journal and error reason, including the
  configuration-recovery successor after removal begins. Updates Details rereads authoritative
  journal metadata instead of waiting for Docker inventory, and operation forms/Details keep
  advisory overlays from covering consent controls.

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
  sources ([docs/install.md](https://github.com/CyberFazaN/opencode-sandbox/blob/v6.1.0/docs/install.md#moving-from-a-legacy-source-installation)).

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
- One-time initial integrations and injected sandbox guidance (Agent
  Context).
- Read-only readiness checks (`check`, `doctor`) including measured network reachability; disk
  usage and conservative cleanup.
- Textual dashboard (usable at 80x24) and a Typer CLI; installer `install.sh` for source
  checkouts.
