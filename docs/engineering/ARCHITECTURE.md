# Architecture — OpenCode Sandbox 6.1.0

The current design, consolidated from the decisions in `DECISIONS.md` (D-0xx, with rationale
and evidence). Current
state and verification: `BASELINE.md`. User-facing behaviour is in `README.md` and the guides in
`docs/` (D-041; the rootless daemon setup in `docs/install.md`, the daemon identity check in
`docs/security.md`, the injected guidance in `docs/opencode.md`).

Approved staged architecture: D-056 and the [Updates working roadmap](updates/ROADMAP.md).
UP-01 implements generic reports and the Agent Context presentation correction; UP-02 preserves
independent local/registry version results. UP-03 adds daemon-wide base coordination and locked
image revalidation; UP-04 adds explicit identity-bound rollback-copy selection; UP-05 bounds
diagnostic execution and owns client/probe cleanup. UP-06 replaces/clears category-owned dashboard
advisories while preserving operation status. The Updates
interface, disposable version observations/discovery cache and other staged corrections remain pending.

## Boundaries

- One host user, that user's own **rootless** Docker daemon, one container per environment.
  Not a general container manager, no repository or package-repository management, no ongoing
  management of OpenCode configuration after the first start (D-009). Manager-owned settings
  stay separate from OpenCode and user configuration.
- The manager never mounts the Docker socket, never uses `--privileged` or host networking, and
  never changes the host firewall, subordinate IDs, systemd units or daemon configuration.
  Host setup belongs to Docker and distribution documentation; no setup scripts (D-048).
- No migration from other metadata or backup schemas; data of an unsupported schema is reported
  or refused and never modified or deleted (D-002).

## Modules (`src/opencode_sandbox/`)

| Module | Responsibility | Decisions |
|---|---|---|
| `core.py` | Paths, locks, metadata (schema 2), labels, Docker access, create/start/stop/session/exec, snapshot, recreate and recovery journals, export, delete, image build, `error_text` | D-001..D-004, D-016, D-026, D-027, D-030, D-031, D-033, D-034 |
| `runtime_identity.py` | Bounded acquisition and authenticated rootless response-sender proof; shared by CLI/TUI and standalone stdlib diagnostic | D-003, D-048, D-052 |
| `base_locks.py` | Secure UID/verified-endpoint/distribution build and publication guards outside product path overrides; acquisition-order checks | D-056 |
| `diagnostics.py`, `http_probe.py`, `probes.py` | Bounded captured host diagnostics, isolated stdlib HTTP child, container-side probe limits and invocation-owned image-helper cleanup; not long-mutation/session executors | D-056 |
| `distros.py` + `assets/images/` | Registry of managed distributions (Debian 13 default/revision 2, Arch Linux with `paru`/`ocs-aur`), Dockerfiles, validated image provenance, OpenCode install script | D-005, D-006, D-016, D-017, D-051 |
| `opencode_versions.py` | Registry lookup without host npm, policies (notify/manual/pinned; OpenCode 2.x only), journalled base and environment updates, rollback | D-007, D-019, D-033 |
| `agent_context.py` | Renders, verifies and refreshes the injected guidance | D-008, D-018 |
| `integrations.py` | Initial MCP integrations (Context7 by default), provisioned once | D-009 |
| `config_plan.py` | One planner/executor for CPU, memory, PIDs, network, ports, provider profile | D-010 |
| `workspaces.py`, `workspace_io.py` | Managed vs direct workspaces (re-checked at every start); hardened host-side access to agent-writable workspaces (host Git with a private `GIT_DIR`); output destinations outside every workspace | D-012, D-025, D-030, D-033 |
| `gitflow.py` | Change summary, export, bundles, staging and review branches into the source repository; sandbox text escaped, tracked links leaving the repository refused | D-028 |
| `backup.py` | Cold checksummed backups (schema 3) with the system layer also without a container, archive validation, staged recoverable restore, prune per environment | D-022, D-026, D-032 |
| `readiness.py` | Read-only checks for `check`, `doctor`, `status` and dashboard; reported resource capability separate from configuration/enforcement, network reachability measured | D-020, D-053 |
| `cleanup.py` | Disk usage inventory and cleanup limited to this data directory's objects | D-011 |
| `cli.py` | Typer CLI (grouped commands); no arguments starts the dashboard | D-021 |
| `tui.py`, `management_tui.py`, `backup_tui.py`, `git_tui.py`, `preferences.py` | Textual dashboard and its screens (plain text for sandbox content, errors through `core.error_text`) | D-021, D-032, D-034 |
| `tui_runtime.py` | Thread-worker adapter for scoped readiness/diagnostic cancellation and guarded read-only result publication; no UI retry loop | D-052, D-056 |

`tui.ReportScreen` is the shared plain-text, scrollable read-only report for Agent Context,
Versions, readiness and cleanup results. Its title is a required explicit keyword argument,
rendered without markup; there is no versions-specific default. Agent Context uses
`Agent Context — NAME`. A failed container inspection is displayed with the configured-settings
fallback, and the saved guidance is not verified against that unobserved preview. Successful
inspection retains the existing file comparison. Neither path writes guidance or starts a
container; lifecycle generation and CLI verification remain unchanged.

## Docker access and identity (D-003, D-004, D-052)

`runtime_identity.verify()` must return `verified` before any Docker call: the context's socket
is a Unix socket with an own-user listener and a kernel-authenticated response sender
(`SCM_CREDENTIALS`) that is `dockerd`, lives in its own user namespace mapping 0 to the user,
and reports the exact rootless security option in that same bounded HTTP/1.0 `/info` response.
Every response byte needs the same credentials; vanished/replaced processes, ancillary rights,
unbounded/malformed responses and proxies are refused. Rootful daemons, other
users' daemons, proxies and remote endpoints are refused. Afterwards every call is
`docker -H unix://<socket>` with `DOCKER_HOST`/`DOCKER_CONTEXT` dropped (`core.docker()`). The
context name comes from `OPENCODE_SANDBOX_DOCKER_CONTEXT` (default `rootless`). Containers run
as root inside (mapped to the host user), with `--init`, `no-new-privileges` and without the
capabilities `NET_RAW` and `MKNOD`; manager images are run with `--pull never` (D-033).

## Host prerequisites (D-043)

One classification for every caller: `runtime_identity` (`verified`, `unverified-proxy`,
`mismatch`, `unavailable`, `unsupported`, `missing`, `not-configured`, each with a hint and an
exit code 0, 3–8) is used by `doctor`, `check`
(`readiness.daemon_check`), every Docker operation (`core.verify_runtime` raises
`PrerequisiteError` with the code; the endpoint is pinned after successful acquisition and
explicit `ensure_runtime()` calls reverify it) and the dashboard (worker at start/explicit
Refresh). One 10-second monotonic budget includes context lookup, transport and retry waits;
only reset/empty response/backlog/interrupted transport retries with capped backoff. Permissions,
configuration, missing/stale sockets, protocol errors and identity refusals are final. Context
and canonical endpoint resolve once per acquisition. Overlapping core callers share the
in-flight result under a cancellable lock, not a persistent readiness cache or operation replay.
`runtime_feedback()` scopes progress/cancellation per worker; CLI progress is stderr. Synchronous
previews use a short optional-observation budget; TUI previews/pre-attach run off-thread. A host program that is not installed
(`core.run_program`, `core.call`, `core.require_program`) is a `PrerequisiteError` with exit 7
and what to install. `cli.main` turns a `PrerequisiteError` into its exit code; other errors exit
2. Confirmations go through `cli._confirm`: Docker operations verify the daemon before asking,
and without a terminal the command refuses and names `--yes`; `tui` and `providers set` refuse
without a terminal. `doctor` lists Python, Git and the Docker CLI first and works without Docker.

Resource support (D-053) is separate from identity. A fresh bounded/cancellable `core.docker_info()`
query follows identity verification, on the pinned endpoint. `readiness.resource_support_check()`
validates cgroup version/driver and CPU quota/period, memory and PID capability booleans; no
host repair, service query or filesystem delegation assumptions. Missing evidence is not
success. Doctor/check/dashboard share advisory results and upstream hints; doctor exit semantics
and mutation preflights are unchanged. Reported capability and matched container settings are
explicitly not measurements of kernel enforcement.

UP-05 adds a separate short-diagnostic path: `core.docker` bounds a finite allowlist of read-only
inspect/list/info/disk-usage/stats-no-stream calls (eight seconds/1 MiB combined output).
`core.call` only uses `diagnostics.run` when given an explicit timeout; the default subprocess
path for mutations and arbitrary user exec remains unbounded. The runner owns a new client session,
incrementally drains bounded nonblocking pipes, checks a monotonic total budget and worker
cancellation, kills only its process group and reaps the direct client. Exit observation uses
`waitid(WNOWAIT)` so the leader reserves the group ID until the final cleanup signal. Launch uses
the existing callable-signal deferral guard, never a child-inherited signal mask or worker-thread
signal changes. Cleanup waits are bounded and failures are reported, not claimed as reaped.

The npm lookup executes the standalone stdlib `http_probe.py` under an isolated interpreter,
with an eight-second total parent budget and a 64 KiB response limit, including slow DNS/body
reads. Cancellation terminates/reaps that owned child; no persistent downloader/thread or host npm.
Existing daemon-identity acquisition and resource-support mechanisms retain their own budgets.

`probes.exec` wraps only diagnostics in a container-side GNU timeout process group (five seconds
for versions, ten for comprehensive readiness). `probes.image` adds a unique name/token, manager/
data/helper labels, network none and pull never; full image verification has 30 seconds. Clients
get three seconds' grace. A canceled/dead host client does not prove exec ended: container timers
bound ordinary groups even after disconnection. Missing/custom timeout tooling never authorizes an
unbounded retry. Interrupted image-helper cleanup uses separate non-cancelable three-second
inspect/removal calls; full immutable container ID plus invocation/manager/data/helper labels are
required before removal. An inaccessible daemon means unconfirmed cleanup with a named leftover,
not a success claim. Normal helpers self-remove. No environment stop, host socket mount or new
persistent state. Host/process bounds are not a hostile-container boundary or daemon-liveness promise.

Read-only dashboard workers publish through `tui_runtime.publish`, checking cancellation/app
liveness both before queuing and on the UI thread. No late result from a canceled/replaced check.
This neither implements mutation Cancel nor replaces journals/recovery; base candidate cleanup
gets its own uncancelled inspection after an interrupted probe. Full reports can take multiple
per-call budgets, and the existing Versions interface still waits for its attempts before display.

Dashboard startup/explicit Refresh publishes complete base-image check results, including success.
Daemon, resource-support and image advisories own their notification objects and share an explicit
status owner, not rendered-text prefix matching. Category replacement is synchronous on the UI
thread so a queued old toast cannot arrive after success; unrelated notifications, even with the
same title, are untouched. Unknown replaces that category's old result; a phase exception belongs
to its own category, not a false daemon failure. An unverified daemon skips downstream checks
without inventing success. When no operation/readiness wait owns the line, outstanding daemon,
resource and image advisories have that priority; clearing one reveals the remaining advisory.
Readiness waits retain worker ownership and their own notification, restore a remaining wait or
advisory only when they owned the status, and cannot erase mutation progress/results. Operation
guards are unchanged; metadata-only refresh stays Docker-free. No observations/discovery cache or
Updates screen is introduced by this correction.

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

## Base-image coordination (D-056)

Base coordination (D-056) is separate from `core.lock`'s per-data-directory environment locks.
`base_locks` always uses `/tmp/opencode-sandbox-locks-<UID>/` (no HOME/TMPDIR/XDG fallback), with
SHA-256 keys over UID, the canonical pinned verified daemon endpoint and distribution. The
validated temporary parent (root-owned/sticky if writable by others), private own-user directory and regular single-link lock
files are checked with no-follow descriptor-relative access; pathname/inode identity is checked
again after acquisition. Unsafe paths fail closed without chmod/unlink/recreation. File
descriptors are non-inheritable; process death releases the advisory flock, not the file.

Acquire only needed data coordinator -> environment IDs in stable order -> base build -> base
publication. The base guard tracks its execution context and refuses reverse/recursive base
acquisition; `core.lock` refuses data/environment acquisition inside a base guard. Installation
usage will precede these levels in UP-16; it is not implemented yet. Build/rollback hold build
through candidate/copy verification and their own cleanup, taking publication only for guarded
inspection, identity rechecks and tag changes. Creation holds environment then publication from
pin check through Docker creation. All base cleanup takes build then publication nonblocking,
rechecks identity/ownership/references, and releases each item's guards before the next item.
Old managers/manual Docker do not participate, and daemon-shared copies can still be removed
before another data directory's future rollback. Locks do not protect against a hostile same-user
process or make unknown labels into ownership proof.

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

`opencode_versions.versions_report` composes local inventory and an optional npm lookup for both
CLI and TUI. Local collection precedes discovery, and either source's failure leaves the other's
results intact. Per-environment and formatting errors keep their subject and unexpected error
type instead of discarding other rows. CLI `opencode versions` prints available rows to stdout,
errors to stderr and exits 2 on a partial/failed report; the dashboard displays them together
with its failure notice. Without `--check`, the CLI never queries npm. This is a read-only report,
not a new update executor, observation cache or concurrent discovery service. Existing policy
comparisons remain unchanged; only running containers are queried for their binary version.

OpenCode V2 (`@opencode/cli` 2.x, no other major) is installed in the base images; every
container runs with `OPENCODE_DISABLE_AUTOUPDATE=1`. Updates are journalled with a `docker commit`
checkpoint and roll back on failure; `update-base` keeps a verified rollback copy of the replaced
base image. Build/swap/rollback, cleanup and pin-check/container creation use the shared base
guards described above (D-056 supersedes D-033's data-directory-local base locks). Only a known
missing-image response permits a first build; full image identity/managed distribution ownership
is checked before replacement and rechecked at publication, and colliding candidate/copy tags
are refused. Rollback inventory groups managed copy aliases by full immutable image ID, retaining
old-definition provenance without inferring replacement history. A single distinct copy defaults;
several require an exact listed tag/full ID, including `--yes`. Read-only `--list` does no runtime
probe. Frozen inventory/selection records bind consent to daemon, distribution, current base and
selected image/aliases. Execution takes build then publication to revalidate before verification
and again before publishing; probes use the immutable ID and current OS/tool/OpenCode checks.
Changed/missing aliases or current base refuse the stale plan. Publication preserves the replaced
current image and consumes only the selected aliases; an already-current selection is a verified
no-op. No new schema, history service or shared update engine. The managed `run` starts
`opencode --standalone` through `core.LAUNCHER` with the provider profile's variables; a watchdog
hangs the session up when the manager dies. Interactive client creation defers callable exit
signals until the client reference and watchdog PID are owned, then restores/delivers the
pending signal inside cleanup (D-054). No inherited signal mask or worker-thread handler
changes; forced client termination is also reaped. The manager snapshots/restores the attached
stdin terminal's attributes on every exit instead of relying on Docker to undo raw mode.
The Agent Context is an instructions entry in the
image's `/etc/opencode/opencode.json` plus a read-only directory mount `<env>/agent-context/` →
`/run/ocs-agent/`, rendered from configured and observed runtime settings (golden files in
`tests/golden/`). Initial integrations are added with `opencode mcp add --global` at the first
start only, and only without an existing global config.

Base OS reporting (D-051) is not inferred from the current registry: `core.image_definition`
reads the owned container's inherited build labels, else its selected creation image, and
`distros.ImageDefinition` validates them. Agent Context and CLI status use this provenance;
missing/offline labels are unknown. Metadata-only dashboard details remain versionless and
never contact Docker to render a row. A matching current definition can provide its tool list;
old/derived/restored layers do not acquire new-definition promises. This adds no persisted
metadata field or schema migration. Debian's current definition is 13/revision 2; an existing
Debian 12 container is still 12 after a manager upgrade or base rebuild.

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
consider objects labelled with this data directory plus shared managed base candidates/copies and
identifiable untagged replaced bases. Current bases and the build cache are never removed.
Cleanup previews before `--yes`; base removals recheck identity, labels and local references
under shared guards. Unverifiable base distribution/ownership is kept, even under a familiar
name. The existing per-environment removal semantics remain unchanged.

Managed base-definition checks (D-050) compare `Config.Labels` with the registry revision and
distribution identity. `doctor` and the dashboard's existing startup worker share the results,
formatting and hints. Known missing images are warnings with a build command; inspect failures
are `not checked`, not absence. Old/unknown labels warn, newer revisions advise review rather
than an automatic downgrade. These read-only advisories do not gate start or inspect an
existing environment's OS; per-environment checks and cached reports remain separate.

## Quality gates (D-034)

`ruff check src tests` (configuration in `pyproject.toml`) and shellcheck on the shell scripts
report nothing; both run in the unit suite (`tests/test_quality.py`) when installed.

## Packaging (D-036)

Distribution `opencode-sandbox` (MIT, `LICENSE` shipped in the wheel and sdist; PEP 639 metadata,
setuptools >= 77). The wheel and sdist contain the package with its image assets; the sdist
leaves out the tests (`MANIFEST.in`), which need the whole repository.

Python >=3.11 (D-049); no version-specific application path. `pyproject.toml` owns the Python
requirement and wheel validation reads it there. CI covers 3.11/3.14 tests, builds and pipx,
plus rolling Arch Python; current and lowest direct dependencies run at both explicit endpoints.
`doctor` reports the interpreter actually running. Published tags retain their old metadata.

## Installation (D-042, D-044, D-048)

Documented: `pipx install git+https://github.com/CyberFazaN/opencode-sandbox.git@vX.Y.Z`; upgrade or
roll back with `pipx install --force` and another tag; `pipx uninstall opencode-sandbox` keeps all
data. No package index. The image definitions travel inside the package (`assets/images/`), so a
pipx installation builds the base images without a source checkout.

No host/application installer or Rootless Docker setup wizard. Contributors run a local editable
venv; users install with pipx only. `docs/install.md` scopes legacy-uninstall instructions to the
trusted old release's checkout and explains launcher inspection. Nothing automatically removes
old installations, switches launchers or changes existing environments. Interpreter/venv repair
uses pipx; shared prerequisite checks remain in the application.
