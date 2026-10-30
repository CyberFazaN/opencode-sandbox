# Decisions

The design decisions of OpenCode Sandbox with their rationale. The IDs `D-0xx` are stable: code,
tests and documents cite them. A changed decision gets a new entry that supersedes the old one,
and the old entry's status line says so. The current design is summarised in `ARCHITECTURE.md`;
verification is recorded in `BASELINE.md` and the release test matrix `CAMPAIGN.md` (row IDs such
as `B09` or `G04`).

## D-001 Manager version with a single source — accepted, installer reader retired by D-048

The manager version has one literal, `src/opencode_sandbox/__init__.py:__version__`;
`pyproject.toml` reads it (`dynamic = ["version"]`, `attr = "opencode_sandbox.__version__"`) and
`install.sh` reads it from the source tree. 6.0.0 is the initial public version. Independent
identifiers stay separate: manager version; OpenCode version (detected at runtime, image label
`org.opencode-sandbox.opencode-version`); distribution id and version (registry and label); image
revision (label, derived from the build inputs); metadata schema (`schema`, bumped only when the
format changes); backup schema. Verified: `tests/test_version.py`,
`tests/test_package_metadata.py`.

## D-002 No migration from other schema versions — accepted

No migration from other metadata or backup schema versions and no compatibility layer (it would
double naming and recovery logic). Metadata of an unsupported schema is reported and left
untouched; a backup of another schema is refused with a clear message. Such data is never
modified or deleted, and Docker objects the manager does not recognise are listed by cleanup as
"not managed" (D-011), never removed.

## D-003 Docker endpoint and daemon identity — accepted, installer details superseded by D-048, credential proof by D-052

- Supported: the user's own rootless daemon on a local UNIX socket. The configured context
  (default `rootless`) is resolved once; TCP, SSH, npipe and TLS endpoints are `unsupported`.
  Later calls use `docker -H unix://<path>` without `DOCKER_HOST`, `DOCKER_CONTEXT`,
  `DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH`; the endpoint is fixed at a process's first verification
  and re-verified, never re-resolved, by each `ensure_runtime()`.
- Identity from `SO_PEERCRED`: `verified` = peer uid is ours, the peer is `dockerd`, its user
  namespace maps UID and GID 0 to ours and the engine reports `rootless`; `unverified-proxy` =
  same uid, another process (a socket proxy, peer PID 0, unreadable `/proc`); `mismatch` = another
  uid (another user's or a rootful daemon); also `unavailable`, `unsupported`, `missing`,
  `not-configured` (D-043). Symlinked sockets are resolved; socket owner, group and path names are
  never trusted. No override flag.
- Accepted residual risk: a same-user process could replace the socket between check and use
  (`/run/user/<uid>` is 0700).
- The module is stdlib-only so `install.sh` can run it before a venv exists. The manager never
  switches contexts, starts services or touches another user's daemon.
- Verified: `tests/test_runtime_identity.py`, rows C01, C09. Documented: `docs/security.md`.

## D-004 Container execution identity — accepted

The sandbox process runs as container UID 0, which is the host user under rootless Docker:
package management works and files the agent creates in a bind mount are owned by the host user
(measured; a container UID 2000 cannot write to a host-owned 0755 directory). No `--userns`, no
`--user`, no host chown. Non-root container users map to subordinate IDs (documented). The mapping
is read from `/proc/self/uid_map` at runtime, not assumed. Verified: row C03.

## D-005 Declarative distribution registry — accepted

- `distros.py` holds one frozen `Distro` record per distribution in `REGISTRY`
  (`DEFAULT = "debian"`), with the derived image `opencode-sandbox:<id>`, Dockerfile
  `assets/images/<id>/Dockerfile` (shared files in `common/`), Agent Context lines and labels.
  Distribution-specific behaviour elsewhere is a review failure (a test greps `src/`).
- Build-time labels from the registry: `distro`, `distro-version`, `image-revision`,
  `opencode-package`, `opencode-version` (descriptive only: derived images inherit it).
- Every build goes to `<repo>:<id>-candidate-<hex>`, is verified (os-release entries, D-017;
  `opencode --version`) and only then tagged. `build` is `update-base` without a rollback copy and
  removes the replaced image (Docker refuses while a container uses it). Rollback copies:
  `<repo>:<id>-previous-<hex12>`.
- Agent Context and readiness take the operating system from the `distro` metadata plus the
  registry, never from the image name.
- Verified: `tests/test_distros.py`, row C02.

## D-006 AUR helper and build identity — accepted

paru, built from a pinned AUR commit in a separate build stage, is run only through the root-owned
wrapper `ocs-aur`. Both paru and yay worked under no-new-privileges; paru was chosen for its clean
root refusal ("can't install AUR package as root"; yay tries `systemd-run` and fails with a D-Bus
error), review by default and smaller size (8 MiB versus 12 MiB). Its longer Rust build affects
only image builds.

No-new-privileges blocks setuid, so sudo cannot work. `ocs-aur`, run by container root, opens a
private broker socket under `/run/ocs-aur/` (root:aurbuild), runs paru as `aurbuild` with a
minimal environment (no provider keys) and `--sudo` pointing at a shim that passes argv, cwd and
the standard streams to the broker, which runs `/usr/bin/pacman` with them. Accepted only: peer UID
`aurbuild`; the peer is a direct child of the paru this `ocs-aur` started (PKGBUILD code runs
below makepkg and is refused; relies on Yama ptrace restrictions); argv[0] `pacman`; none of
`--root`, `--dbpath`, `--config` (except `/etc/pacman.conf`), `--hookdir`, `--gpgdir`,
`--sysroot`, `--cachedir`, `--logfile`, `-r`, `-b`, no short-option cluster containing `r` or `b`,
no prefix of a refused long option; no path in `/workspace`. The wrapper refuses the helper
options it manages (`--sudo*`, `--clonedir`, `--builddir`, `--chroot`, `--makepkg*`, `--pacman`,
`--config`, `--root`, `--dbpath`) and arguments under `/workspace`.

Limits: `aurbuild` exists because makepkg refuses root; it is no boundary against packages the
user installs (their scripts run as root). paru links libalpm, so an in-container `pacman -Syu`
that bumps its soname breaks paru until the image is rebuilt. Verified: `tests/test_arch_image.py`,
`tests/test_hardening.py`, rows K01, M01.

## D-007 OpenCode V2 only — accepted

Sandboxes install OpenCode V2, the npm package `@opencode/cli`; every major other than 2 is
refused (D-033). One installation per container. Measured with 2.1.4: `npm install -g` works under
no-new-privileges (about 60 s; the install script passes `--allow-scripts=@opencode/cli` for the
postinstall) and installs all four linux-x64 variants (about 920 MB, accepted). `opencode
--version` prints `opencode v2.1.4`; `opencode` and `opencode2` are the same binary.
`OPENCODE_CONFIG_CONTENT` is honoured but undocumented. Provider credentials must be in the
server's environment. Verified: `tests/test_opencode_versions.py`, rows G01, C02.

## D-008 Agent Context delivery — accepted

The guidance is available from the first prompt through `run`, never overrides user-managed
OpenCode configuration and can be refreshed without recreation.
- The image ships `/etc/opencode/opencode.json` = `{"instructions": ["/run/ocs-agent/context.md"]}`.
  OpenCode V2 combines `instructions` from every configuration document and deduplicates
  identical paths (measured).
- The host file `<env>/agent-context/context.md` is in a directory bind-mounted read-only at
  `/run/ocs-agent/`, so an atomic replace on the host is visible in the container. `run` and
  `shell` regenerate it before each launch; `OPENCODE_CONFIG_CONTENT` is not touched.
- Managed `run` launches `opencode --standalone`: any other client starts a background
  `serve --service` reparented to PID 1 that keeps the first client's environment, so a later
  client's provider key was ignored (measured). `--standalone` runs a private server that ends
  with the client.
- The launcher warns when an image's system configuration does not list the guidance (custom
  images); no fallback injection.
- A random per-launch token in the session's environment lets the host SIGHUP exactly that
  session when the host launcher ends abnormally (D-021).
- Verified: `tests/test_agent_context_integration.py`, `tests/test_run_hangup.py`,
  `tests/integration/test_40_opencode.py`, rows G04 (real first prompt), G05, H05.

## D-009 Initial integration provisioning — accepted

Provisioning runs once, at the first successful container start, with OpenCode's own mechanism;
it is never re-applied on start, recreation, repair, update or restore. Context7 is the default
(remote MCP `https://mcp.context7.com/mcp`, no credential); with `network=none` the result is
"configured, cannot work offline".
- `opencode mcp add --global NAME --url URL` (or `NAME -- COMMAND...`) works offline, does not
  start the background service and keeps comments and other keys, but replaces a same-name entry
  and corrupts an unparseable file (measured). It is therefore run only when no global
  configuration file (`opencode.json`, `opencode.jsonc`, `config.json`) exists; otherwise the
  result is "skipped" and nothing is written.
- Metadata (also in backups) records the request and outcome as history: `provisioning =
  {requested, definitions, state: pending|applying|done, result, at}`. Definitions carry no
  headers or environment (no secrets). Opt-out: `requested=[]`, `state=done`.
- `core.start()` runs it under the environment lock (`applying` saved first); an interrupted or
  failed run is recorded and not retried, and never fails the start. Restore keeps the record; a
  backup taken before the first start restores as "not provisioned". No plugins are provisioned.
- Verified: `tests/test_integrations.py`, `tests/integration/test_15_integrations_quick.py`, rows
  G10, M03.

## D-010 Central runtime change plan — accepted

One planner (`config_plan.py`) classifies every manager-owned setting change (`cpus`, `memory`,
`pids`, `network`, `ports`, `profile`) and renders a diff; one executor applies it through the
durable journals; CLI and dashboard share them. `apply(m, changes, confirmed=plan)` re-plans and
refuses if the shown plan no longer holds. Categories, measured on rootless Docker with cgroup v2
delegation:
- `saved`: no container; applied at creation.
- `dynamic`: CPU, memory, PIDs through `docker update`, running or stopped; persists across
  restarts. Memory is always passed with `--memory-swap` = 2 x memory (otherwise Docker keeps the
  old swap value and refuses memory above it).
- `restart`: lowering memory of a running container (a live decrease below the usage killed the
  container): stop, update, start.
- `recreate`: network, ports, provider profile. Network disconnect/connect leaves an inconsistent
  mode and is not used. A running container is stopped; `core.reconfigure_runtime` commits,
  journals (`runtime-recreate`, recording `superseded_image`) and removes it, and starts the
  replacement if it was running.
- Dynamic and restart changes are journalled (`config-update`) before Docker is touched;
  `config recover` re-runs the idempotent steps. Only `config_plan.py` and
  `core.reconfigure_runtime` write `runtime` and `profile` (tested). Merging under the lock: D-031.
- Verified: `tests/test_config_plan.py`, rows C05, M04. Documented: `docs/settings.md`.

## D-011 Disk usage and cleanup boundaries — accepted

`disk usage` (read-only) and `disk cleanup [--superseded] [--yes]` (preview by default; dashboard
key `D`). Never `docker system prune` or `image prune -a`.
- Every object except base images carries `org.opencode-sandbox.data-dir=` the first 16 hex digits
  of the SHA-256 of the resolved `OPENCODE_SANDBOX_HOME`; objects without it or with another value
  are "not managed" or "other data directory" and never removed. A path hash keeps leftovers of a
  recreated data directory cleanable; a moved data directory's objects become foreign (safe side).
- Helper containers carry `org.opencode-sandbox.helper=<purpose>` (required on every `run --rm`);
  since containers inherit image labels, only `ocs-<id>` with the matching id label or the helper
  label count as the manager's.
- An owner exists while `environments/<id>` exists (also with unreadable metadata). Docker is
  listed before the registry is read, and owners are recorded before their objects are created,
  so no owner is missed.
- Default scope: objects of owners that no longer exist, stopped helper containers, unused
  `ocs-backup:*`, base build candidates, `.backup-*` directories in the default backup directory.
  `--superseded` adds unused `ocs-checkpoint:*` and `ocs-runtime:*` images, base rollback copies
  and untagged base images. Never: containers, volumes and snapshots of existing environments,
  base images, environment directories, direct workspaces, exports, bundles, backups, the build
  cache.
- Removal re-inventories under a `cleanup` lock, removes only confirmed keys still eligible
  (owner-dependent ones under the owner's lock; busy = skipped), never forces, and is simply run
  again after an interruption. Untagged parent layers it exposes go in follow-up passes.
- Sizes are approximate (`docker system df -v`, allocated blocks; direct workspaces not walked).
- The build cache cannot be attributed (no labels); it is reported daemon-wide, never removed.
- Verified: `tests/test_cleanup.py`, `tests/test_cleanup_untagged_parents.py`, rows J02, M05, E10.
  Documented: `docs/maintenance.md`.

## D-012 Direct workspaces are externally owned — accepted, partly superseded by D-025

Metadata stores `workspace: {mode: managed|direct, path}` (required, fixed at creation; malformed
makes the metadata unsupported, never managed by default). No code path deletes, chowns, chmods,
restores into or recursively modifies a direct path.
- `workspaces.check_direct` reports all reasons: an existing directory (symlinks resolved); not
  `/`, not in system trees (`/bin /boot /dev /etc /lib* /opt /proc /root /run /sbin /srv /sys /usr
  /var`); not the home directory or a parent of it; not being, containing or inside the manager's
  data or configuration directories, `$XDG_RUNTIME_DIR` or the Docker data root; no hidden
  component; owned by the current UID; parents owned by root or the user, no root-owned parent
  below a user-owned one, none writable by others without the sticky bit; no sockets, device nodes
  or other filesystems inside (bind mounts are recursive). `recheck` also requires the recorded
  path to still resolve to itself; when it runs: D-030.
- Consent is required (`--yes`, or a prompt; without a terminal and `--yes` refused); the
  dashboard shows the same text.
- Preflight before metadata is written: containers of the environment's image, as its own user,
  write and delete a marker file that the host must see as a regular file with its UID and GID.
- Two environments may not use the same or nested direct directories.
- Backups exclude the directory unless `--include-workspace`; restore always creates a managed
  environment. Change transfer refuses direct workspaces. Host Git: D-025.
- Verified: `tests/test_direct_workspace.py`, `tests/integration/test_25_direct.py`, rows L01,
  L02, M01, M02. Documented: `docs/workspaces.md`.

## D-013 English-only active text — accepted

Active documents, messages, comments and tests are English. `tests/test_language.py` reports
letters outside ASCII (per-file allowlist for intentional non-ASCII test fixture names) and
frequent German, French and Spanish function words (in Python only comments and strings). It
catches pasted or untranslated text, not grammar.

## D-014 Scratch space — accepted, partly superseded by D-023

Large logs, venvs and temporary artifacts go to the Git-ignored `.work/` directory (test venv
`.work/venv`, test run data under `.work/<run-id>/`); no records are kept there. Deferred features
go to `TODO.md`. Where the records live: D-023 and D-045.

## D-015 Network modes unchanged — accepted

The modes are `bridge` and `none`; no LAN or host isolation is claimed. With rootlesskit's
`--net=slirp4netns --disable-host-loopback`, host 127.0.0.1 services are not reachable through the
slirp gateway, but the host's LAN address and the LAN are reachable from `bridge` (measured).
Reachability depends on the rootlesskit flags; readiness reports them when visible and what it
measured (D-020), not a guarantee. Verified: row C04. Documented: `docs/security.md`.

## D-016 Distribution in metadata; explicit custom images — accepted, installer detail superseded by D-048

Metadata schema 2 requires `distro`: a registry id, or `null` for `create --image REF` (then
`image` is required). Missing, unknown, or `null` without `image` is reported as invalid and left
untouched. The distribution is fixed at creation. A custom image is a recorded per-environment
choice (`--image`, no environment variable); `opencode-sandbox:*` references are refused (use
`--distro`). Backups (schema 3) record `distro` and `custom_image`; restore refuses manifests
without them. `install.sh` keeps the literal default `opencode-sandbox:debian`; a test keeps it
equal to `distros.DEFAULT`. Verified: `tests/test_distros.py`.

## D-017 Rolling releases in the registry — accepted, Debian pin superseded by D-051

`Distro.os_release` lists the `/etc/os-release` entries a build must report: Debian `ID=debian`,
`VERSION_ID=12`; Arch `ID=arch`, `BUILD_ID=rolling` (its `VERSION_ID` is the upstream image date
and changes weekly). The Arch registry version is `rolling` (label and Agent Context). The build
verification also requires every `tools` entry on `PATH` and every `smoke` command to succeed
(Arch: `paru --version`, `ocs-aur --version`), running the candidate with no-new-privileges.
Verified: `tests/test_distros.py`, `tests/test_arch_image.py`, row C02.

## D-018 Agent Context content contract — accepted, OS/provenance rule superseded by D-051

`agent_context.render` states only what the manager configures or verifies: container, user and
privileges; workspace and persistence; network and resources; working behaviour; one
operating-system section from the registry's `context_lines()`, or "unknown" for custom images,
which also get no user claim.
- Workspace lines depend on metadata only: a copy renders as "copy of a host directory", never the
  host path (it would reach the model provider); `quick` as disposable; direct mounts have their
  own lines.
- `core.guidance_inputs(m)` adds the observed runtime (network, CPUs, memory, PIDs from `docker
  container inspect`) when a container exists. Observed values win and a difference is stated;
  identical values render byte-identically. Ports are omitted when the effective network is
  `none`. The `bridge` text states the measured reachability (D-029). CLI and dashboard fall back
  to the configuration, with a note, when Docker fails.
- Integrations render as requested-but-pending, then "Provisioned once, at the first container
  start: NAMES (RESULT). They may have been changed or removed since"; nothing else.
- Golden files `tests/golden/agent-context-{debian,arch,custom}.md` pin the text
  (`tests/test_agent_context.py`). Verified: rows G05, G08.

## D-019 OpenCode lifecycle and self-update — accepted

The manager owns OpenCode's installation in its containers; OpenCode's updater is off and the
user's OpenCode configuration is not touched.
- Every container runs with `OPENCODE_DISABLE_AUTOUPDATE=1`: OpenCode's self-update (with
  `update: auto`) left world-writable files and a large npm cache in /root and could break
  OpenCode (measured). The variable wins over the user's configuration and is the only
  manager-owned switch. A manual `opencode upgrade` is reported and `opencode update` repairs it.
- Policies (`opencode policy-set`): `notify` (default) reports available updates; `manual` reports
  nothing; `pinned X` refuses other versions, refuses a container from a registry base image with
  a different `opencode-version` label (custom images not checked) and reports a running version
  differing from the pin. Updates are always explicit.
- `opencode update NAME` (stopped, networked): `latest` resolved on the host; checkpoint
  `ocs-checkpoint:<id>-<hex>`; journal `operation=opencode-update`; start, run the install script,
  verify, stop. Same version: nothing installed. Failure: the environment's image is set to the
  checkpoint through the `runtime-recreate` journal (the system layer as before; /root and
  /workspace are not part of it). A crash leaves the journal: `start` and `repair` refuse,
  `opencode update-recover` rolls back (it never guesses whether npm completed).
- `opencode rollback NAME` uses the same mechanism and first keeps the current layer as
  `ocs-snapshot:*`. `opencode update-base` rebuilds a base image and keeps a rollback copy;
  `opencode rollback-base` verifies the newest copy, swaps it in and keeps the replaced image.
- Verified: `tests/test_opencode_lifecycle.py`, rows G02, G03, G09, M03. Documented:
  `docs/opencode.md`.

## D-020 Readiness checks and network transparency — accepted, base-definition diagnostics extended by D-050

- `readiness.py` serves `check NAME`, the dashboard (`i`), `status` and `doctor`. Results:
  `passed`, `warning`, `failed`, `not checked` (with reason), `not applicable`; a check that
  raises becomes `not checked`; without a verified daemon only host-side checks run. `check` exits
  1 if any check failed.
- Read-only: nothing is started, stopped, recreated or edited. Its only writes are the cached
  report `<env>/readiness.json` (0600, never profile values) and a short-lived listener on the
  host's 127.0.0.1. `status` and the dashboard details read the cache and never probe.
- Network: configured versus actual mode and published ports. Reachability is stated only as
  measured from the container's `python3`: internet = a verified TLS handshake with
  registry.npmjs.org (a TCP connect is no evidence: a NAT accepted one to a TEST-NET address);
  host loopback = a token received by a host listener on 127.0.0.1 via slirp4netns' 10.0.2.2;
  host LAN address and default gateway = answered or not. No listener on a LAN address.
- Published ports must be exactly the configured `127.0.0.1:HOST -> CONTAINER/proto`; a server
  listening on loopback only is a warning.
- A provider profile replaced on the host is seen after a restart; the check compares the mounted
  file's inode and asks for one.
- Verified: `tests/test_readiness.py`, row J01. Documented: `docs/maintenance.md`.

## D-021 Command structure, creation flow and dashboard terms — accepted

- 24 top-level entries in four help panels (Environments, Sessions, Settings changes and data,
  Maintenance); related operations are groups: `changes`, `backup`, `container`, `disk`,
  `config`, `opencode`, `agent-context`, `providers`. No aliases. `changes show` is the one change
  preview, also for non-Git and direct workspaces. "export" = `.tar.gz` in `exports/`, "bundle" =
  review bundle in `changes/`. Recovery commands stay in their groups (a restore has two ways out:
  resume, rollback).
- Every command and option named in the product and the documents must exist
  (`tests/test_cli_structure.py`).
- Creation rules live in `core.creation_options()`, shared by CLI and dashboard: without a kind, a
  copied folder or a direct workspace makes a project, otherwise scratch; scratch with a folder is
  refused. The dashboard form shows name, kind and folder; the rest is under "More options" with
  the CLI's defaults. Custom images are CLI-only.
- Dashboard labels use the CLI's terms; the details pane uses the same functions as `status`.
- Session watchdog: per `run`/`shell` session a small process in its own session reads a pipe from
  the manager; EOF without "done" (however the manager ends) makes it SIGHUP the docker client and
  run the token hang-up (D-008). A failure to start it is ignored.
- Verified: `tests/test_tui.py`, `tests/test_run_hangup.py`, `tests/integration/test_50_tui.py`,
  rows H01-H08. Documented: `docs/dashboard.md`.

## D-022 Symlinks in backups are kept as links — accepted

Backups store and restore symbolic links verbatim, also absolute ones or ones leaving the workspace
(every venv has `bin/python -> /usr/bin/python`). Refusing them added no protection: the agent can
create such links in the live workspace anyway, and the extractor never follows links (regular
files first with exclusive create, links last, members below a link or non-directory and
duplicates refused). Still refused: NUL and backslash in link targets, special files, unsafe
hardlinks, non-canonical names. Change bundles keep refusing links leaving the repository
(D-028). Verified: `tests/test_backup_hardening.py`, `tests/test_archive_paths.py`, rows E01, E03.

## D-023 Engineering records are current-state documents — accepted, partly superseded by D-045

The maintainer records in `docs/engineering/` describe the current state and are kept true when
the code changes: `BASELINE.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `ISSUES.md`, `CAMPAIGN.md`,
`RELEASING.md`. `TODO.md` and `.work/` keep their D-014 roles. Location rules: D-045.

## D-024 Records of a multi-cycle effort — superseded by D-045

Governed where the working records of an earlier multi-cycle effort (state, tasks, handoff, test
evidence) lived inside `docs/engineering/` and the branch they were committed on.

## D-025 Host Git never uses the workspace repository's configuration — accepted

Every host Git command on a managed workspace (`workspace_io.git`) runs with a private throw-away
`GIT_DIR` outside the workspace: a manager-written configuration carrying only the storage format
(`extensions.objectformat` sha1 or sha256, `extensions.refstorage` files or reftable, read with
`git config --file`, which does not follow includes), snapshot copies of `HEAD` and the index (no
symlinks followed, size limits) and links to `objects`, `refs`, `reftable`, `info` and
`packed-refs`. Structural checks: a real `.git` directory, no top-level symlinks, no `commondir`,
`alternates` or `config.worktree` (and D-033). A gitlink in the index is refused before any
command, because Git reads a populated nested repository's configuration (measured, also without
`.gitmodules`). `GIT_NO_LAZY_FETCH=1` is set.

Why: an allowlist cannot cover nested repositories or a change between check and Git's read. Git
in a helper container was not chosen (previews would need Docker). Consequences: submodule
entries are refused by all host Git features; split-index repositories fail closed; object data is
read live (D-033); each call costs two extra Git processes and an index copy.
Verified: `tests/test_git_boundary.py`, row E08.

## D-026 Image provenance: original custom image and restored-image ownership — accepted

A custom-image environment records its original image in `custom_image` (never changed); `image`
names the image the next container is created from (derived images after recreation,
reconfiguration, rollback or restore). Backups record `custom_image`; a restore without a system
layer uses it. It need not be local: like `create --image`, the first start lets Docker pull it,
and the restore warns. Manager images are run with `--pull never` (D-033).

A restored system image becomes the environment's own: after `image load`, a never-started
container with the environment's name and labels is committed to `ocs-backup:<id>-<hex>` and
removed (as is a loaded tag the restore created), so cleanup never takes it for another data
directory's. A superseded `ocs-runtime` image is untagged only when no environment of this data
directory references it. Verified: `tests/test_image_provenance.py`, rows E10, E11.

## D-027 Recreation stops a running container first — accepted

`container recreate` stops a running container gracefully before committing its system layer,
removes it without `-f` and starts the replacement. Refusing instead would only add a manual
step, since recreation ends with a running replacement. The stop precedes the journal, so an
interruption leaves a stopped, unchanged container. A container started from outside after the
commit is never removed; `container recreate-recover` refuses while a container that is not the
replacement runs (compared by `Config.Image`) and names `opencode-sandbox stop NAME`. Verified:
`tests/test_recreate_consistency.py`, `tests/test_recreate_faults.py`, rows D04, D05.

## D-028 Change transfer: links must stay inside the repository; review output escaped — accepted

A symbolic link enters the user's repository through `changes review`, `stage` or `apply` only if
its target stays inside the repository, tracked or untracked. The check runs on the preflight
clone after the patch; a link the source already has at the base commit is kept. Refusing (not an
opt-in) keeps both kinds consistent; a needed link can be made by hand after review. Paths host
tools act on, links and new executables are listed (`attention`), not refused. All CLI and
dashboard text from the sandbox goes through `core.printable` (control and format characters
escaped, newline and tab kept). Verified: `tests/test_review_flow.py`, rows E07, E12. Documented:
`docs/changes.md`.

## D-029 Disclosure of host-side effects — accepted, partly superseded by D-030

- The direct-workspace consent text (one string for CLI and dashboard, fitting 80x24) names the
  risk class (files host programs act on later: Git hooks and configuration, editor, direnv and
  build settings) and the action (review them before running such tools). The full statement and
  the advice not to run host Git, editors or build tools inside a managed workspace directory are
  in `docs/workspaces.md` and `docs/security.md`.
- The Agent Context states the measured `bridge` reachability, not "no access to host services".
- Base images and rollback copies are documented as shared by every data directory on the daemon
  (`docs/maintenance.md`).
- When the direct-workspace checks run: D-030.
- Verified: `tests/test_disclosure.py`, row L01.

## D-030 Direct workspace re-checked before every container start — accepted

`workspaces.recheck` runs before every start or creation of a direct-workspace container: creation,
`start` of a stopped container, `container recreate-recover`, a settings change that restarts or
recreates, `opencode update`. It runs before any state change, so a refusal leaves the container
stopped and no journal. A `docker update` without restart mounts nothing and is not re-checked.
The checks are a snapshot at start time. Verified: `tests/test_direct_restart.py`, row L02.

## D-031 A journal is re-marked only by its owner; settings changes merge under the lock — accepted

- An operation re-checks its state under the environment lock (the earlier check is only a fast
  refusal). A failure handler re-marks the environment only while the journal is still its own
  (it holds the lock, or re-reads the same operation); another operation's journal is never
  replaced. The restore step accepts only the restore journal; `backup restore-rollback` runs its
  check under the lock through `delete(precondition=...)`.
- An environment created by an operation gets that operation's journal in its first save.
- `delete` removes `metadata.json` last, so an interrupted deletion stays listed and can be
  retried; a kill at the very end leaves an empty directory that `disk usage` reports.
- `config apply` merges only the planned changes into the settings as they are under the lock and
  restarts a container only if this call stopped it.
- Verified: `tests/test_journals.py`, `tests/test_transactions.py`, rows D06, D07, M06.

## D-032 Backup manifests, restore details, first-start failure and dashboard text — accepted

- `backup verify` requires a JSON object manifest with an `environment` object and a string
  `created`; malformed manifests are `SandboxError`s. `backup prune` keeps `--keep` backups per
  (name, environment id), newest by `created` (timezone required); a backup without a valid time
  is never deleted. Backups without an id are grouped by name.
- Restore keeps modification times and records no `source`; change transfer needs only the base
  commit.
- A failed `docker run` at the first start removes the never-started container it left, so
  `config apply` fixes the cause without `repair --cleanup`; a container that ran is never removed.
- Default snapshot tags are `ocs-snapshot:<id>-<time>-<6 hex>`; an existing tag is never moved.
- Dashboard text from environments, backups and errors is never interpreted as markup. The
  Recovery Center offers repair and settings-change recovery and names the CLI command for other
  journals (more actions: `TODO.md`).
- Verified: `tests/test_backup_restore_edge_cases.py`, `tests/test_snapshot_tag.py`,
  `tests/test_tui_text.py`, rows C08, D11.

## D-033 Hardening rules and their limits — accepted, installer details superseded by D-048

- OpenCode 2.x only: every other major is refused, also when `latest` resolves to one; another
  major needs a manager release.
- Agent Context delivery check: configuration plus mounted file compared with the host file;
  whether OpenCode reads it is shown only by the real first-prompt test (row G04).
- `.git` data: no symlink below `objects`, `refs`, `reftable`, `info`, no `info/grafts`, checked
  when each host Git command starts. Accepted residual risk: a link created while a command runs
  can change the data it reads (read only); copying the object store was not chosen (cost).
- The data directory is created 0700 (an existing one keeps its permissions); the manager's
  subdirectories are always 0700.
- Containers run with `--cap-drop NET_RAW --cap-drop MKNOD` (measured with apt, pacman, AUR builds,
  npm, OpenCode and the probes); further drops were not measured and not taken.
- A short lock `base-tag-<distro>` is held by `start` from the pin check to `docker run` and by
  `update-base`/`rollback-base` while they move tags.
- Exports, change bundles and backups are refused inside any environment's workspace (resolved
  through symlinks).
- A removed image yields one message (`core.missing_image`) naming what is intact, the way back
  and the way out (`changes export` or `bundle`, then `delete --yes`). Custom images are still
  pulled at the first start (D-026).
- A failed Agent Context refresh after provisioning is logged and the start completes.
- `install.sh doctor` reports a release that no longer starts; `docs/install.md` documents the
  reinstall after a Python minor upgrade and removing old releases. Deferred (`TODO.md`): release
  pruning and a dependency lock file.
- Verified: `tests/test_hardening.py`, rows B03, C03.

## D-034 Quality gates and error reporting — accepted, script list superseded by D-048

- `ruff check src tests` (default rules, measured with 0.17.3) and `shellcheck` (0.11.0) on
  `install.sh`, `setup-rootless.sh`, `pacman-retry` and `install-opencode.sh` report nothing; both
  run in `tests/test_quality.py` and are skipped when missing. Dockerfile `RUN` lines are not
  checked.
- Configured: B008 (Typer's declaration style); BLE001 and RUF012 in `*tui.py`: dashboard actions
  and workers catch all errors to keep running and must show them through `core.error_text` (an
  AST test enforces it). Other broad catches carry a `noqa` with the reason.
- `core.error_text` shows `SandboxError` by message and any other error also by type. Silent
  catches are limited to the errors they expect, so a defect surfaces instead of looking like an
  invalid backup or an empty selection.

## D-035 Repository layout and branches — superseded by D-045

Governed the repository layout after the release preparation (which records were in force and
where earlier ones were kept). Still valid: `main` is the only long-lived branch; work happens on
short-lived topic branches merged into `main` with a merge commit after review.

## D-036 Licence and identity — accepted, partly superseded by D-042 and D-048

MIT licence, `Copyright (c) 2026 CyberFazaN`. Product "OpenCode Sandbox"; owner CyberFazaN;
repository `CyberFazaN/opencode-sandbox`; distribution name `opencode-sandbox` (installed by pipx,
not published to an index, D-042); command `opencode-sandbox`. Described as an independent
open-source project, not affiliated with the OpenCode project; the README names no person (the
owner appears in `LICENSE`, `pyproject.toml` and the repository URL). `pyproject.toml` carries SPDX `license` and `license-files`,
author, URLs and Beta classifiers. The sdist is the buildable package only (`MANIFEST.in` prunes
`tests/`, which need the whole repository). Kept on purpose: the installer directory
`~/.local/share/opencode-sandbox-manager/` and the npm registry User-Agent. Verified:
`tests/test_package_metadata.py`.

## D-037 AI provenance disclosure — accepted

README states prominently and factually that code, tests and documentation were written with
OpenCode and Claude Opus 5.5 with minimal human review, what that means for
security and reliability, and how contributions are reviewed. Public documents do not describe
the development history and claim no code quality beyond the recorded test evidence.

## D-038 Public history and scope — accepted, partly superseded by D-046

6.0.0 is the initial public version; the public repository's history begins there. Status Beta;
the host scope (originally Arch Linux only) is D-046. The public tree holds the product, tests, user
documentation and current-state maintainer records (D-045), no historical documents. Code, tests
and documents use decision IDs and release-matrix row IDs, no other internal identifiers
(`tests/test_user_docs.py` checks the user documents, the records and the code). `CHANGELOG.md` starts with 6.0.0.

## D-039 Distribution through a package index — superseded by D-042

Planned a PyPI distribution installed with `uv tool install` or `pipx install`. Still valid: the
manager, its locally built base images and OpenCode have separate versions; no prebuilt images;
distribution packages, Flatpak/Snap/AppImage, a containerised manager and `curl | bash` are
rejected; an AUR package is deferred (`TODO.md`).

## D-040 CI and release process — accepted, partly superseded by D-042 and D-049

Hosted CI runs only what a hosted runner can show honestly: static checks, the fake-Docker unit
suite, package build and wheel smoke, lowest-direct dependencies. The real campaign
(`tests/integration/`) is a manual release gate on the maintainer's Arch Linux machine; no
self-hosted runner. Releases start from an owner-created `v*` tag: the release workflow checks the
tag against `__version__` and the CHANGELOG section, runs the CI checks against the tag including
a pipx installation from it, and creates a draft GitHub Release for the owner to publish; no
artifacts are uploaded (D-042). Checklist: `RELEASING.md`.
- Workflows: `ci.yml` (unit suite with the current and the lowest direct dependencies, the unit
  suite in an `archlinux:base-devel` container as an unprivileged user, package build and content
  check, pipx installation from the checkout with `doctor` refusing the runner's daemon, actionlint
  and zizmor), `release.yml` (calls `ci.yml`), `images.yml` (weekly build and verification of both
  base images with `core.build_image`; never published), `dependabot.yml` (actions only, seven-day
  cooldown). Helpers in `.github/scripts/` with unit tests (`tests/test_release_scripts.py`).
- Every job has `contents: read` except the draft job (`contents: write`); the workflow default is
  `permissions: {}`; actions are pinned to commit SHAs; checkouts do not persist credentials; no
  caches. The steps were rehearsed locally (`BASELINE.md`); the workflows run on GitHub only after
  publication.

## D-041 Public documentation layout — accepted

Plain Markdown on GitHub, no documentation site. `README.md` is an overview linking the
task-oriented guides `docs/*.md` (install, getting started, concepts, workspaces, providers,
settings, OpenCode, backup, changes, maintenance, dashboard, security, troubleshooting), indexed in
`docs/README.md`; `--help` is the command reference. Daemon hints name the published setup guide
(`runtime_identity.SETUP_GUIDE`). The screenshot `docs/images/dashboard.svg` is generated from fake
data by `tests/dashboard_screenshot.py`. Checks: `tests/test_cli_structure.py` (commands and
options named in README and `docs/` exist); `tests/test_user_docs.py` (links and anchors resolve,
code blocks fit 80 columns, install commands name the release tag `v<__version__>`, every guide is
indexed, no internal references).

## D-042 pipx from GitHub, no package index; runtime prerequisites — accepted, installer retention superseded by D-048

Supersedes D-039 and the package-index parts of D-036 and D-040.
- Install: `pipx install git+https://github.com/CyberFazaN/opencode-sandbox.git@vX.Y.Z`. Nothing
  is published to PyPI or another index; no wheels on releases. The upgrade procedure is
  documented explicitly (D-044); uninstalling keeps environments, backups, profiles, Docker data.
- `install.sh` stays for installs from a source checkout (`doctor`, `verify`, `setup-rootless`);
  not the primary path. No other mechanism.
- CI installs with pipx from the checkout (for a release, the tag) and checks packaged resources
  and CLI startup; sdist and wheel builds are validation only. The release workflow creates a
  draft GitHub Release from the CHANGELOG section; nothing is uploaded to a registry.
- Prerequisites are diagnosed by the existing checks (D-043); `--help`, `--version` and `doctor`
  work without Docker; nothing is installed or configured on the host.
- Verified: rows B09-B12, C09. Documented: `docs/install.md`.

## D-043 Prerequisite diagnostics and exit codes — accepted, installer caller retired by D-048

- Classifications and exit codes: `verified` 0, `unverified-proxy` 3, `mismatch` 4, `unavailable`
  5 (daemon not running or not answering), `unsupported` 6, `missing` 7 (no Docker CLI; also a
  missing Git), `not-configured` 8 (no such context or no endpoint). 1 = a check failed or the user
  declined; 2 = usage and operation errors, including a confirmation without a terminal. The same
  codes hold for `install.sh`, `doctor` and every command.
- A Docker operation verifies the daemon before asking for confirmation. A confirmation without a
  terminal refuses and names `--yes`; `tui` and `providers set` refuse without a terminal.
- The dashboard checks the daemon once in a worker and reports problems; the list works without
  Docker and each action checks again (only a verified endpoint is cached).
- `changes show` of a Git workspace requires Git; the previews in `delete` and the dashboard say
  "Git preview unavailable". No wizard and no host changes: hints name the commands.
- Verified: `tests/test_prerequisites.py`, `tests/integration/test_35_prerequisites.py`, row C09.
  Documented: `docs/troubleshooting.md`.

## D-044 pipx installation procedure — accepted, installer interaction superseded by D-048, Python floor by D-049

Measured with pipx 1.18.7.
- `pipx install git+https://github.com/CyberFazaN/opencode-sandbox.git@vX.Y.Z` needs pipx, Git and
  access to GitHub and PyPI (dependencies resolved at install time within the declared ranges);
  pipx's Python must be 3.14 or newer (`--python python3.14`). The installed package runs without
  the source tree and builds images from its own assets.
- Upgrade or roll back with `pipx install --force ...@vOTHER`: `pipx upgrade` and `pipx reinstall`
  keep the tag; `pipx install` without `--force` refuses. Untagged specs are not documented. Base
  images and OpenCode are updated separately (`build`, `opencode update-base`, `opencode update`).
- `pipx uninstall opencode-sandbox` removes only the application and launcher.
- With `install.sh` (same launcher `~/.local/bin/opencode-sandbox`) neither replaces the other's
  working launcher; pipx only warns, so the documents say to uninstall one first, and `install.sh`
  recognises a pipx launcher and names `pipx uninstall opencode-sandbox`.
- `OCS_TEST_MANAGER=<launcher>` runs the real campaign against an installed manager;
  `tests/integration/test_65_pipx.py` covers rows B09-B12 in a disposable clone with test tags
  (`OCS_TEST_PIPX_BUILD=1` adds the image build).
- Not verified: installing from the GitHub repository itself, other pipx versions, the refusal by
  an older pipx Python.

## D-045 Public engineering records — accepted

`docs/engineering/` holds current-state maintainer records only: `BASELINE.md` (state, test
commands, latest verification, unverified behaviour), `ARCHITECTURE.md`, `DECISIONS.md`,
`ISSUES.md` (known issues and accepted limitations; new issues are tracked in GitHub issues),
`CAMPAIGN.md` (release test matrix) and `RELEASING.md` (release checklist). Working records of a
multi-cycle effort may live in a subdirectory of `docs/engineering/` while it runs and are removed
from the tree when it ends; Git history keeps them. Supersedes D-024 and D-035 and the location
rules of D-023.

## D-046 Linux hosts: intended compatibility and tested evidence — accepted, partly superseded by D-047/D-048/D-049

Supersedes the host scope of D-038.
- The manager is intended for any Linux host that meets the technical prerequisites; Arch Linux
  is the primary development and test host, not a requirement. Prerequisites: the user's own
  rootless Docker daemon on a local `unix://` socket (D-003), which needs subordinate UID and GID
  ranges, `newuidmap`/`newgidmap`, unprivileged user namespaces (some distributions restrict them
  by policy) and cgroup v2 with the `cpu`, `memory` and `pids` controllers delegated to the user
  (the manager sets CPU, memory and process limits on every container); Python 3.14 or newer with
  pipx; Git; a terminal for confirmations and the dashboard.
- Evidence: the real campaign runs on Arch Linux only. Hosted CI adds the unit suite (fake
  Docker) and a pipx installation on GitHub's Ubuntu runner, and the unit suite in an Arch Linux
  container. No other distribution is called tested, and no compatibility is guaranteed, until a
  recorded run (`BASELINE.md`, `CAMPAIGN.md`) shows it. Reports from other distributions are
  welcome and answered on a best-effort basis.
- The base images (Debian 12, Arch Linux; D-005) are the distribution inside the containers and
  are independent of the host's distribution.
- Arch-specific or narrower parts, documented and kept: the package check and `--offer-packages`
  of `install.sh` use pacman and run only when `/etc/os-release` says `ID=arch` (elsewhere a
  warning, no package check); `install.sh` runs `python`, not `python3`; `setup-rootless.sh`
  warns on other distributions and offers only a systemd user service; hints name pacman as an
  example and `systemctl --user` for starting the daemon. `doctor` does not check cgroup
  controller delegation or user-namespace policy. Portability work: `TODO.md`.
- Documented: `README.md`, `docs/install.md`. Limitations: `ISSUES.md`.

## D-047 Stabilization priorities and upstream-owned host setup — accepted

Owner direction, 2026-10-29: prepare a dependable stable release through compatibility,
reliability, data safety, recovery, installation simplicity, UX and documentation, not feature
expansion. The classified backlog is `TODO.md`; the active multi-cycle plan and progress live
in a working-record subdirectory of `docs/engineering/` (D-045; removed by D-055). Continue one verified task per cycle and retain
all Git and publication permissions. No stable status or version is claimed by the plan.

- Supersedes the hand-maintained host setup documentation approach of D-046: link Docker's
  official rootless guide and the distribution's official documentation, with the ArchWiki for
  Arch-specific packaging/setup conventions. Describe prerequisites and application diagnostics;
  do not maintain host package, system configuration or daemon installation recipes.
- Approves retiring the legacy scripts retained by D-042/D-044 and the installer-portability
  work of D-046. Until that task is verified, the scripts still exist; no replacement installer
  or wizard. pipx from a GitHub release tag remains the sole recommended application install.
  Shared CLI/TUI diagnostics and safety tests must survive their removal.
- Promote Python-floor verification (3.11 first, then newer versions as needed), Debian 13 and
  its image-revision/old-state compatibility prerequisites. Current Python >= 3.14 and Debian 12
  declarations remain until the corresponding implementation is verified. Full real Docker
  campaigns are not required for every Python version; minimum/current Arch Python unit CI,
  packaging and pipx are required.
- Preserve existing dependency-bound CI and release-campaign evidence, but rerun changed paths;
  do not convert historical PASS into evidence for untested configurations. A stable release
  still needs every P0/P1 gate met or explicitly BLOCKED with accepted risk (RELEASING).

## D-048 pipx-only installation; retire host setup scripts — accepted

Implements the retirement approved by D-047. Removes `install.sh` and `setup-rootless.sh`, not
replaces them. Supersedes installer-specific details of D-001/D-003/D-016/D-033/D-034/D-036 and
installer retention, interactions and host setup of D-042/D-043/D-044/D-046; their references to
the old scripts describe the retired behaviour, not current instructions.

- pipx from a GitHub release tag is the only recommended user installation. Contributors use an
  editable local venv. Python/package/venv creation belongs to pipx and packaging, not a second
  installer. No host package offers, service starts, context changes, UID allocations or wizard.
- Keep `runtime_identity.py` (including its standalone diagnostic entry point), shared host,
  image and storage checks, and CLI/TUI classifications/exit codes. Bootstrap-only package/setup
  instructions are upstream-owned; hints link the guide rather than assuming a setup helper or
  systemd service. Existing cgroup/user-namespace diagnostic gaps remain explicit work (D-047).
- Do not remove old installations or user state automatically. Transition instructions inspect
  the launcher, then use the trusted old release's uninstaller in its old checkout before pipx.
  A pipx venv broken by a Python minor upgrade is rebuilt with `pipx reinstall --python`; the
  recorded tag and environment data remain separate. Never delete an unidentified launcher.
- Retire installer-only tests and campaign rows B02–B08; retain B01's manager-as-root refusal,
  C01's rootful/foreign/proxy refusal, C09 prerequisite/terminal checks, pipx lifecycle/data
  retention and foreign-launcher safety. Preserve container-local install scripts and their
  tests. Current shellcheck targets are `pacman-retry`, `install-opencode.sh` and
  `.github/scripts/pipx_smoke.sh`; package validation rejects retired installers in the sdist.

## D-049 Verified Python 3.11 floor; endpoint CI — accepted

Implements D-047 (Python floor); supersedes the 3.14-only requirements of D-044/D-046 and extends D-040's
CI endpoints. Python 3.11.18 runs the unchanged full unit/host/Textual-pilot/local-process
suite, including filesystem/archive safety, without compatibility shims. An isolated trial
copy verified sdist/wheel builds/content and pipx Git-tag installation, replacement in both
directions and uninstall/data retention before the checkout's requirement was lowered.

- Declare `requires-python >=3.11`, classifiers 3.11–3.14 and Ruff `py311`. The wheel checker
  reads the requirement from `pyproject.toml`, not a second hardcoded floor. No application
  logic, security policy, dependency bound, schema, image or manager version changes.
- Keep existing Typer/Textual ranges and setuptools >=77. Current dependencies resolve on
  3.11; lowest direct dependencies remain covered too. Record resolved versions and actual
  executions in BASELINE; bounds are not locks on transitive dependencies.
- CI runs unit/host/pilot/process, package and pipx checks on 3.11 and 3.14, retaining the
  rolling Arch unprivileged job and lowest-direct-dependency coverage at both explicit
  endpoints. Release-tag pipx checks cover both endpoints. No hosted Docker campaign added.
- 3.12/3.13 are in the supported range but not separately verified; say so. A full real
  Docker/OpenCode campaign is still required on the release host, not every Python version.
  Revised workflows are not claimed as hosted PASS before they run.
- Published `v6.0.0` remains Python >=3.14. Install examples still name that published tag and
  the interpreter it needs; the new floor belongs to this checkout/the next release. No tag
  rewrite or implicit publication. pipx's own interpreter and its application's interpreter
  are separate; `--python` selects the latter.

## D-050 Shared managed base-image definition diagnostics — accepted

Implements D-047 (base-image diagnostics), extending D-020 before changing any image definition. `image_checks()`
previously treated every successful inspect as current and every failure as missing. It now
reads each registry base tag's `Config.Labels`, with no build/pull/container/metadata writes.

- Require matching manager-managed/distribution identity and a positive canonical decimal
  `image-revision` label. Compare with the registry; equal also checks `distro-version`.
  Current means matching build labels, not verified OS/package currency or a security boundary.
- Old revision: warning with the explicit distribution build command. Missing/malformed or
  inconsistent labels: warning, review the image before a manual rebuild. Newer revision:
  warning, check manager/release compatibility and do not rebuild merely to hide it.
- Only a Docker `No such image` response establishes absence. Other inspect failures and invalid
  responses are `not checked`, with an inspect hint, never a misleading build recommendation.
  One expected inspect exception does not hide checks of the other base tags.
- Reuse these checks in the existing dashboard startup worker after daemon verification;
  shared report formatting and hints, plain-text advisory notices, no new UI/update subsystem.
  Do not overwrite a pending operation's status. `doctor` exit semantics are unchanged;
  clarify that image/storage warnings and incomplete image checks may accompany exit 0.
- These are global registry base tags only. Keep start/pinning, per-environment readiness and
  derived/restored images unchanged; a notice does not force OS migration or recreate a used
  container. No image revision, distribution, schema, manager version or release status bump.
- Regression matrix: `tests/test_image_readiness.py` plus existing readiness/prerequisite/TUI
  coverage. Read-only real evidence and unexecuted layers are recorded separately in BASELINE.

## D-051 Debian 13 definition; retain and describe old system layers — accepted

Implements D-047 (Debian 13) after D-050. Supersedes D-017's Debian-12 build pin and D-018's
registry-derived OS version/tool promises. Debian now uses `node:24-trixie`, version 13,
image revision 2. Node 24's official image registry includes trixie; OpenCode 2.2.0 has native
Linux packages and no declared npm engine restriction. Actual packaged build verification
checks OS, tools, smoke commands and OpenCode. Arch's definition/revision is unchanged.

- Distribution metadata still identifies the family, not an OS upgrade. No metadata/backup
  schema or manager version/status change, no migration and no automatic base replacement.
  Stop/start, recreation, snapshots and system-image restore preserve the existing layer.
  Explicit no-system restore instead uses the current local base and discards system packages.
- `ImageDefinition` validates non-secret managed/distribution/version/revision build labels.
  For an owned container, use its inherited labels rather than a mutable base tag; otherwise
  inspect the selected creation image, including a derived/restored image. Missing, invalid or
  unavailable provenance is unknown, never today's registry version. This is base provenance,
  not an observation of OS/package modifications inside the container or a security boundary.
- Agent Context gets only inspected provenance. Current matching definitions may promise their
  verified tools/notes; older/different definitions do not inherit a newer tool list. Offline
  previews are versionless. First creation captures selected-image labels under the base-tag
  lock, also when no pending integrations will trigger a later refresh. Launch regeneration
  and user-owned OpenCode configuration separation stay unchanged.
- CLI status uses inspected provenance. Creation output and metadata-only dashboard details
  say the OS version is uninspected, with no Docker probing on the UI thread or new metadata
  cache. New-environment menus/help label registry versions as build definitions.
- Base rollback still verifies the current OS definition: a Debian-13 manager refuses a
  Debian-12 base rollback copy instead of silently downgrading it. Copies are not automatically
  deleted; old environments/system backups remain usable and per-environment OpenCode
  update/rollback preserves their OS. This limitation is explicit in the guides.
- Real verification uses the existing campaign and an isolated installed candidate. Test-only
  tag namespace hooks stay outside the product/package; existing base tags/IDs are never
  replaced. A pre-change installed manager creates the retained Debian-12 container/backups.
  The exact evidence and unexecuted layers remain in BASELINE/CAMPAIGN; the final release gates
  are not replaced by this scoped campaign.

## D-052 Bounded readiness and authenticated response senders — accepted

Implements D-047's bounded-readiness priority. Supersedes D-003's SO_PEERCRED-only executable proof and D-043's one-shot
dashboard readiness behavior; endpoint/own-rootless boundaries and exit classifications stay.
An authorized isolated real rootless daemon confirmed FD handoff through RootlessKit 3.3.0:
SO_PEERCRED identifies user systemd even when warm; SCM_CREDENTIALS identifies dockerd. A
retry-only patch cannot support that valid listener without weakening identity.

- Enable SO_PASSCRED before connect. Refuse foreign/rootful listener identity immediately.
  Send only HTTP/1.0 GET /info, no request body; authenticate every received byte using kernel
  SCM_CREDENTIALS. Require one unchanged own-user dockerd sender, its existing executable and
  user-namespace UID/GID map proof, and exact `name=rootless` in the same JSON response.
  Do not trust a unit, path/owner, claimed HTTP PID, or forwarded rootless text. Direct and
  inherited listeners share this proof; there is no systemd whitelist or required systemd call.
- Bound headers to 16 KiB and the full response to 512 KiB; require HTTP 200, EOF completion,
  consistent optional Content-Length, no transfer/content encoding or duplicate headers.
  Reject missing/truncated/changing credentials and ancillary file descriptors (close any
  received rights with close-on-exec protection). Recheck /proc executable/maps after reading
  and compare process start time to detect mid-response PID reuse. This retains the existing
  same-user process-observation/check-to-use residual, not cryptographic executable attestation
  or protection against a hostile process with the user's daemon access. No new kernel minimum
  beyond the existing Linux UNIX-credential/user-namespace requirements is selected.
- One monotonic 10 s budget covers context subprocess, socket I/O and capped retry backoff;
  100 ms polling permits cooperative cancellation. A ready endpoint has no forced sleep/notice.
  Retry only typed reset/empty response/timeout/backlog/interruption; never missing/stale socket,
  permissions, malformed/unsupported context, protocol/HTTP errors or identity failures.
  Context and canonical endpoint are pinned for the entire unsuccessful acquisition too.
  Context CLI children are killed/reaped on cancellation; bounded cleanup may add up to 0.4 s.
- Core coalesces overlapping acquisitions only, with each caller's deadline/cancellation;
  explicit later verification still probes again. No global Docker-command retry, mutation
  replay, host service management, context switch or background readiness monitor.
- CLI/standalone progress goes to stderr once after 250 ms; errors keep concrete causes/codes.
  Existing Textual workers get scoped feedback/cancel checks. Explicit Refresh rechecks;
  successful retry clears only prerequisite notices. Guidance/pre-attach work is off-thread;
  interactive startup after suspend retains CLI feedback. Optional CLI previews use 250 ms.
- Real cold-start budget evidence, proxy refusals, process/pilot/terminal tests, endpoint Python
  and dependency verification and limits live in BASELINE/CAMPAIGN. The isolated activation
  opt-in is not general permission to restart the user's daemon or rerun privileged rows.
  The final full campaign and release decision remain separate.

## D-053 Report resource support separately from limit configuration — accepted

Reproduced a misleading success: readiness compared only Docker HostConfig CPU/memory/PID
settings, without checking whether the daemon reported the corresponding capabilities. A
verified rootless identity or accepted setting is not proof of kernel enforcement.

- One shared `resource_support_check()` for doctor, per-environment readiness and dashboard
  startup/explicit Refresh. Use fresh read-only Docker info on the already verified/pinned
  endpoint; never resolve a new context or query before identity success. A five-second query
  budget reuses D-052's child cleanup/cooperative cancellation, without retrying any operation.
  Raw info/error text is not printed (it may contain proxy URLs/host details).
- Require cgroup v2, the documented rootless systemd cgroup driver and exact true boolean
  CPU CFS quota/period, memory and PID capability flags for a reported-support PASS. Explicit
  false flags, cgroup v1 or driver none warn; absent/malformed evidence and unfamiliar versions
  or drivers are NOT CHECKED. No mandatory systemctl/D-Bus or host cgroup filesystem probe;
  other driver setups are not silently certified or rejected as an identity failure.
  Ignore unrelated cpuset/I/O/swap warnings for settings the manager does not request.
- PASS says "Docker reports" support and "enforcement not measured". The existing per-container
  Resource limits check still compares settings, now labeled as configuration only; its id
  and cache schema stay unchanged. The new report entry is additive, not a migration.
- Advisory results never gate start/configuration or change metadata/host policy. Preserve
  doctor exit meanings: host programs and identity determine exit 0, optional resource/image/
  storage warnings or unknown checks can remain. Shared report text/hints, off-thread dashboard
  notices preserve an active operation and clear only their own stale notice after refresh.
  Guidance belongs to Docker/distribution docs, not repair commands or a setup wizard.
- Regression tests cover unsupported/missing/unknown/corrupt evidence, identity refusal,
  bounded/canceled probes, output sanitization and CLI/pilot parity. The existing C05 campaign
  is extended to read actual cpu.max/memory.max/pids.max in a disposable rootless container
  before/after settings changes, not merely inspect HostConfig. Evidence/limits: BASELINE.
  No stress/OOM/fork exhaustion, host service/policy edit or extra privileged permission.

## D-054 Own an interactive client before delivering catchable launch signals — accepted

The release verification traced the H05 observation to SIGTERM interrupting `Popen`'s fork/exec return before the
client PID was stored. The child was running, but client cleanup had no reference and the
watchdog had no PID. Container hangup alone did not end the orphaned host client.

- Defer callable SIGINT/SIGTERM/SIGHUP handlers only over interactive client creation and
  watchdog PID registration, on the main thread. Restore the original handlers and invoke
  the first pending handler inside the owned client's existing cleanup guard. Do not defer
  the session's ordinary wait or install process-wide handlers from a worker.
- Do not block signals (an inherited mask can disable client cleanup), use `preexec_fn` in
  the threaded application, add a launch wrapper or change ignored/default dispositions.
  Preserve signal exit semantics, normal exits, exactly-once token hangup and watchdog policy.
  Explicitly wait after the fallback SIGKILL, not just after successful SIGHUP.
- Capture the attached input terminal's attributes before client creation and restore them
  in `finally` after client cleanup, using TCSANOW (no output drain/input flush). The real
  SIGTERM/SIGHUP checks showed Docker can leave echo/canonical mode disabled despite ending
  the session correctly. Never substitute another terminal for absent/non-tty stdin; a
  closed terminal or failed restoration must not replace the session's original error/exit.
- Scope is the demonstrated catchable-signal ownership gap, not a generic subprocess rewrite
  or a guarantee against SIGKILL/power loss, unavailable Docker or repeated cleanup signals.
  D-008/D-021 token and watchdog behaviour is unchanged. No schema/image/version change.
- Verification: deterministic real fork/exec-window regressions on each Python endpoint,
  handler/mask/worker/reaping tests, traced concurrent host reproducer before/after, and the
  existing real terminal/OpenCode campaign. Details: BASELINE and CAMPAIGN H05.

## D-055 Release 6.1.0: version, status and the end of the stabilization records — accepted

Owner decision, 2026-10-30, after an independent review of every change since 6.0.0.
- The release is **6.1.0**, not a patch release: it adds functionality (readiness and
  socket-activation identity, resource-support and base-image diagnostics, Python 3.11 to 3.13),
  changes the Debian default definition and removes the 6.0.0 source installer. This follows the
  Semantic Versioning that `CHANGELOG.md` declares. The internal-reference checks of D-038 no
  longer forbid the string `6.1.0`; it now names a public release.
- Development status stays **Beta**: real evidence covers one host distribution, a fake model
  provider, and hosted CI has not yet run the revised matrix.
- The stabilization working records end with this release (D-045): their durable facts are in
  BASELINE, DECISIONS (D-047..D-054), ISSUES, CAMPAIGN, RELEASING and TODO; Git history keeps the
  cycle records. Supersedes D-047's record location; its priorities remain the roadmap in TODO.
  The internal-reference checks also refuse the removed plan's task labels.
- Install examples name `v6.1.0` and the 3.11 floor; this supersedes D-049's note that they kept
  naming the 6.0.0 tag.
