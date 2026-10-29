# Architecture — OpenCode Sandbox 6.0.0

The current design, consolidated from the decisions in `DECISIONS.md` (D-0xx, with rationale
and evidence). Current
state and verification: `BASELINE.md`. User-facing behaviour is in `README.md` and the guides in
`docs/` (D-041; the rootless daemon setup in `docs/install.md`, the daemon identity check in
`docs/security.md`, the injected guidance in `docs/opencode.md`).

## Boundaries

- One host user, that user's own **rootless** Docker daemon, one container per environment.
  Not a general container manager, no repository or package-repository management, no ongoing
  management of OpenCode configuration after the first start (D-009). Manager-owned settings
  stay separate from OpenCode and user configuration.
- The manager never mounts the Docker socket, never uses `--privileged` or host networking, and
  never changes the host firewall, subordinate IDs, systemd units or daemon configuration
  (`setup-rootless.sh` only offers `systemctl --user enable --now docker.service` after consent).
- No migration from other metadata or backup schemas; data of an unsupported schema is reported
  or refused and never modified or deleted (D-002).

## Modules (`src/opencode_sandbox/`)

| Module | Responsibility | Decisions |
|---|---|---|
| `core.py` | Paths, locks, metadata (schema 2), labels, Docker access, create/start/stop/session/exec, snapshot, recreate and recovery journals, export, delete, image build, `error_text` | D-001..D-004, D-016, D-026, D-027, D-030, D-031, D-033, D-034 |
| `runtime_identity.py` | Verifies that the endpoint is the user's own rootless daemon; also run by `install.sh`/`setup-rootless.sh` as a standalone script | D-003 |
| `distros.py` + `assets/images/` | Registry of managed distributions (Debian 12 default, Arch Linux with `paru`/`ocs-aur`), Dockerfiles, OpenCode install script | D-005, D-006, D-016, D-017 |
| `opencode_versions.py` | Registry lookup without host npm, policies (notify/manual/pinned; OpenCode 2.x only), journalled base and environment updates, rollback | D-007, D-019, D-033 |
| `agent_context.py` | Renders, verifies and refreshes the injected guidance | D-008, D-018 |
| `integrations.py` | Initial MCP integrations (Context7 by default), provisioned once | D-009 |
| `config_plan.py` | One planner/executor for CPU, memory, PIDs, network, ports, provider profile | D-010 |
| `workspaces.py`, `workspace_io.py` | Managed vs direct workspaces (re-checked at every start); hardened host-side access to agent-writable workspaces (host Git with a private `GIT_DIR`); output destinations outside every workspace | D-012, D-025, D-030, D-033 |
| `gitflow.py` | Change summary, export, bundles, staging and review branches into the source repository; sandbox text escaped, tracked links leaving the repository refused | D-028 |
| `backup.py` | Cold checksummed backups (schema 3) with the system layer also without a container, archive validation, staged recoverable restore, prune per environment | D-022, D-026, D-032 |
| `readiness.py` | Read-only checks for `check`, `doctor`, `status` and the dashboard; network reachability measured | D-020 |
| `cleanup.py` | Disk usage inventory and cleanup limited to this data directory's objects | D-011 |
| `cli.py` | Typer CLI (grouped commands); no arguments starts the dashboard | D-021 |
| `tui.py`, `management_tui.py`, `backup_tui.py`, `git_tui.py`, `preferences.py` | Textual dashboard and its screens (plain text for sandbox content, errors through `core.error_text`) | D-021, D-032, D-034 |

## Docker access and identity (D-003, D-004)

`runtime_identity.verify()` must return `verified` before any Docker call: the context's socket
is a Unix socket whose peer (`SO_PEERCRED`) runs as the current UID, is `dockerd`, lives in its own
user namespace mapping 0 to the user, and the engine reports `rootless`. Rootful daemons, other
users' daemons, proxies and remote endpoints are refused. Afterwards every call is
`docker -H unix://<socket>` with `DOCKER_HOST`/`DOCKER_CONTEXT` dropped (`core.docker()`). The
context name comes from `OPENCODE_SANDBOX_DOCKER_CONTEXT` (default `rootless`). Containers run
as root inside (mapped to the host user), with `--init`, `no-new-privileges` and without the
capabilities `NET_RAW` and `MKNOD`; manager images are run with `--pull never` (D-033).

## Host prerequisites (D-043)

One classification for every caller: `runtime_identity` (`verified`, `unverified-proxy`,
`mismatch`, `unavailable`, `unsupported`, `missing`, `not-configured`, each with a hint and an
exit code 0, 3–8) is used by `install.sh`, `setup-rootless.sh`, `doctor`, `check`
(`readiness.daemon_check`), every Docker operation (`core.verify_runtime` raises
`PrerequisiteError` with the code; the endpoint is verified once per process) and the dashboard
(the same daemon check in a worker at start). A host program that is not installed
(`core.run_program`, `core.call`, `core.require_program`) is a `PrerequisiteError` with exit 7
and what to install. `cli.main` turns a `PrerequisiteError` into its exit code; other errors exit
2. Confirmations go through `cli._confirm`: Docker operations verify the daemon before asking,
and without a terminal the command refuses and names `--yes`; `tui` and `providers set` refuse
without a terminal. `doctor` lists Python, Git and the Docker CLI first and works without Docker.

## Data and Docker objects

- Data directory `OPENCODE_SANDBOX_HOME` (default `~/.local/share/opencode-sandbox`):
  `environments/<id>/` (`metadata.json`, managed `workspace/`, `agent-context/`,
  `readiness.json`), `exports/`, `changes/`, `backups/`, `locks/`. Configuration
  `OPENCODE_SANDBOX_CONFIG` (default `~/.config/opencode-sandbox`): `profiles/*.json` (0600,
  never shell-sourced; legacy `.env` refused), `ui.json`.
- Names: container `ocs-<id>`, home volume `ocs-home-<id>` (`/root`), staging volumes
  `ocs-stage-<id>-<hex>`, images `ocs-snapshot:`, `ocs-runtime:`, `ocs-checkpoint:`, `ocs-backup:`,
  base images `opencode-sandbox:<distro>` with rollback copies `opencode-sandbox:<distro>-previous-<hex12>`.
- Labels: `org.opencode-sandbox.managed=true`, `org.opencode-sandbox.manager-version`; all but
  base images `org.opencode-sandbox.data-dir` (hash of the data directory); per-environment
  objects `org.opencode-sandbox.id`; `--rm` helpers `org.opencode-sandbox.helper`. Ownership is
  decided by labels plus metadata; unlabelled objects with a manager name are refused, never
  adopted or deleted.
- Persistence: `/workspace` (managed directory or direct host folder), `/root` (volume), the
  container's system layer (kept across recreation by `docker commit` into `ocs-runtime:`).

## Operations and recovery

Mutations hold a per-environment `flock` (`core.lock`). Multi-step operations write a journal in
the metadata (`operation`: `recreate`, `runtime-recreate`, `config-update`, `restore`,
`opencode-update`, `delete`, `start`) before their first destructive step and clear it only when
done; the lock is released between steps, so a pending journal means "still running or
interrupted" (`core.pending_operation`). Each journal has one explicit recovery
command (`readiness.RECOVERY`); `start` and `repair` refuse until it runs. Handlers re-read the
metadata under the lock and only re-mark their own journal; `delete` removes `metadata.json`
last; a recreation stops the container before `docker commit` and removes the old one without
`-f` (D-027, D-031). An image a journal needs that was removed outside the manager is reported
with the remaining ways out (`core.missing_image`, D-033). Crash points were tested with SIGKILL
at every Docker step (CAMPAIGN D05, E02, G03).

## Settings changes (D-010)

`config plan`/`config apply` and the dashboard Settings screen use `config_plan.py`: each change
is classified as saved (no container), dynamic (`docker update`), restart, or recreate (commit the
system layer, new container, journal `runtime-recreate`). Ports bind to 127.0.0.1 only.

## Workspaces (D-012)

Managed (empty or a copy/clone of a source; the only kind deletion and restore touch) or direct
(a host folder mounted as is; host checks, explicit consent and a container preflight; re-checked
before every container start, D-030; never chowned, chmodded or deleted; excluded from backups
unless requested).

Host-side access to a workspace treats it as agent-written (D-025, D-028, D-033): host Git runs
with a private throw-away `GIT_DIR` (manager-written config, snapshots of `HEAD` and the index,
data-only links to objects and refs), so no program configured in the workspace repository is
ever run; gitlinks, redirections and symlinks below `.git` data directories are refused. Exports,
change bundles and backups are refused inside any environment's workspace. Metadata
`workspace: {mode, path}`; `workspaces.path(m)` is what Docker mounts.

## OpenCode (D-007, D-008, D-018, D-019, D-009)

OpenCode V2 (`@opencode/cli` 2.x, no other major) is installed in the base images; every
container runs with `OPENCODE_DISABLE_AUTOUPDATE=1`. Updates are journalled with a `docker commit`
checkpoint and roll back on failure; `update-base` keeps a verified rollback copy of the replaced
base image. The pin check and the creation of a container from a registry base image hold the lock
`base-tag-<distro>`, which `update-base`/`rollback-base` take while they move the tag (D-033). The managed `run` starts
`opencode --standalone` through `core.LAUNCHER` with the provider profile's variables; a watchdog
hangs the session up when the manager dies. The Agent Context is an instructions entry in the
image's `/etc/opencode/opencode.json` plus a read-only directory mount `<env>/agent-context/` →
`/run/ocs-agent/`, rendered from configured and observed runtime settings (golden files in
`tests/golden/`). Initial integrations are added with `opencode mcp add --global` at the first
start only, and only without an existing global config.

## Backups (D-022)

Cold backups (the environment is stopped) with a manifest and checksums: workspace archive, home
volume archive, optionally the system image. Symlinks are stored verbatim; extraction never writes
through a link and refuses traversal, special files, unsafe hardlinks, duplicate and non-canonical
names. The system layer is saved also when no container exists (from the derived image); the
workspace archive is validated before the backup is published; sockets and FIFOs are left out and
reported. Restore always creates a new environment through a staging volume, journalled
(`restore`, written when the environment is created), with `restore-resume`/`restore-rollback`;
restored images are labelled for the restoring data directory, and a custom image keeps its
original reference (D-026, D-032).

## Readiness, disk and cleanup (D-020, D-011)

`check NAME` and `doctor` are read-only; reachability (internet, host LAN address, host
loopback) is measured from the running container, not assumed. `disk usage` and `disk cleanup`
consider only objects labelled with this data directory, never base images or the build cache;
cleanup previews before `--yes`, and an object already gone at its turn counts as removed.

## Quality gates (D-034)

`ruff check src tests` (configuration in `pyproject.toml`) and shellcheck on the shell scripts
report nothing; both run in the unit suite (`tests/test_quality.py`) when installed.

## Packaging (D-036)

Distribution `opencode-sandbox` (MIT, `LICENSE` shipped in the wheel and sdist; PEP 639 metadata,
setuptools >= 77). The wheel and sdist contain the package with its image assets; the sdist
leaves out the tests (`MANIFEST.in`), which need the whole repository.

## Installation (D-042, D-044)

Documented: `pipx install git+https://github.com/CyberFazaN/opencode-sandbox.git@vX.Y.Z`; upgrade or
roll back with `pipx install --force` and another tag; `pipx uninstall opencode-sandbox` keeps all
data. No package index. The image definitions travel inside the package (`assets/images/`), so a
pipx installation builds the base images without a source checkout.

## Installer (source checkouts)

`install.sh` (never as root) installs a versioned venv under
`~/.local/share/opencode-sandbox-manager/releases/`, switches `current` atomically and links the
launcher into `~/.local/bin`; read-only `doctor`/`--dry-run` (which also reports a release that no
longer starts after a Python minor upgrade); package offers only with `--offer-packages` and
consent; manual rollback by switching `current` (README).
