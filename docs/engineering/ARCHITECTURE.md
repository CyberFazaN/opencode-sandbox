# Architecture — OpenCode Sandbox

Current design of the `develop` checkout. [DECISIONS](DECISIONS.md) owns essential rationale;
[BASELINE](BASELINE.md) owns verification scope and gaps. User operation/recovery instructions are
in [the guides](../README.md); task/test policy is in [CONTRIBUTING](../../CONTRIBUTING.md).

## Boundaries

- One Linux host user, that user's authenticated **rootless** Docker daemon, one container per
  environment. Not a general container manager or repository/package-repository manager.
- Container root maps to the host user. Containers have `--init`, `no-new-privileges`, dropped
  `NET_RAW`/`MKNOD`, no host Docker socket, privileged mode or host networking. Published ports
  bind only to 127.0.0.1. `bridge` can reach the LAN; it is not egress isolation.
- Manager settings, disposable observation/discovery caches, durable operation state and user
  OpenCode configuration are separate. Initial integrations run once; the manager never manages
  user OpenCode settings afterward. No implicit environment/OS/schema migration.
- Unsupported metadata/backup schemas and unknown ownership are refused and preserved, not
  repaired or deleted. Same-user hostile code and arbitrary external Docker/pipx are outside
  the advisory coordination protocol.

## Modules (`src/opencode_sandbox/`)

| Modules | Responsibility |
|---|---|
| `core.py` | Paths, metadata, labels, environment locks, Docker/lifecycle/session access, recreation journals, snapshots, image builds and shared errors |
| `runtime_identity.py` | Stdlib bounded daemon acquisition and authenticated response-sender proof |
| `base_locks.py` | Daemon/distribution build/publication guards and lock ordering |
| `distros.py`, `assets/images/` | Declarative distribution definitions, build labels/assets, OpenCode install and AUR broker |
| `config_plan.py` | Shared settings diff, consent/preconditions and executor |
| `workspaces.py`, `workspace_io.py`, `gitflow.py` | Managed/direct checks, hardened host access, import/export and Git review/transfer |
| `backup.py`, `cleanup.py` | Validated cold backup/staged restore; data-directory-owned usage/removal |
| `readiness.py`, `diagnostics.py`, `http_probe.py`, `probes.py` | Read-only readiness, finite host/HTTP/container probes and owned-client cleanup |
| `agent_context.py`, `integrations.py` | Render/verify/refresh sandbox guidance; once-only initial MCP provisioning |
| `opencode_versions.py` | Actual binary evidence, supported versions/policies, environment/base update and rollback |
| `update_cache.py`, `update_discovery.py` | Private disposable evidence/attempt storage, source coordination and optional daily discovery |
| `updates.py`, `updates_tui.py`, `environment_updates_tui.py` | Component inventory, independent checks, exact consent and existing environment actions |
| `base_updates_tui.py`, `build_output.py` | Base consent/selection and bounded build progress/output |
| `launcher.py`, `installation_locks.py`, `installation_state.py` | Early process-lifetime installation leasing, fixed verifier witnesses and durable incomplete-update barrier |
| `manager_releases.py`, `manager_installation.py` | Published-release discovery and local-only pipx provenance classification; neither grants execution |
| `manager_tools.py`, `manager_tool_probe.py` | Existing external pipx/Python/settings/dependency-route assessment |
| `manager_targets.py`, `manager_source.py` | Exact published release/ref/tag-chain/commit graph and fresh same-target validation |
| `manager_review.py`, `manager_review_tui.py`, `manager_observations.py` | Exact origin review/Cancel-first consent, critical-record/route binding and frozen local replay |
| `manager_handoff.py`, `manager_helper.py`, `manager_verifier.py` | Private frozen helper, authenticated actual-process-death handoff and dedicated read-only runtime query |
| `manager_execution.py`, `manager_process.py`, `manager_network.py`, `manager_pip_probe.py` | Independent frozen execution prerequisites and effective standard-client policy |
| `manager_operation.py`, `manager_installer.py`, `manager_update.py` | Immutable recovery inputs, parked installer admission, descendant cleanup, durable update and verify-only recovery |
| `manager_records.py`, `manager_result.py`, `manager_health.py` | Expected installed records/source/launcher/runtime and separate fixed CLI-help health verification |
| `cli.py` | Typer command groups, terminal/confirmation boundary and dashboard entry |
| `tui.py`, `management_tui.py`, `backup_tui.py`, `git_tui.py`, `preferences.py`, `tui_runtime.py` | Textual screens/preferences, worker publication, actual-body admission and session tracking |

## Data and Docker objects

- `OPENCODE_SANDBOX_HOME` (default `~/.local/share/opencode-sandbox`):
  `environments/<id>/` contains `metadata.json`, managed `workspace/`, `agent-context/` and
  `readiness.json`; siblings include `exports/`, `changes/`, `backups/`, `locks/`, `update-cache/`.
- `OPENCODE_SANDBOX_CONFIG` (default `~/.config/opencode-sandbox`): `profiles/*.json` (0600,
  data only; executable `.env` refused), `ui.json`. Provider values are never shell-sourced.
- Containers `ocs-<id>`, home volumes `ocs-home-<id>` mounted at `/root`, staging volumes
  `ocs-stage-<id>-<hex>`; images `ocs-snapshot:`, `ocs-runtime:`, `ocs-checkpoint:`, `ocs-backup:`.
  Bases are `opencode-sandbox:<distro>`; rollback copies add `-previous-<hex12>`.
- Labels under `org.opencode-sandbox.*` record managed status, manager version, environment ID,
  helper purpose and (except shared bases) the resolved data-directory hash. Names alone never
  establish ownership. Existing unlabelled collisions are refused, not adopted or deleted.
- `/workspace` and the home volume persist independently of the system layer. Recreation keeps
  that layer with `docker commit`; file-only restore deliberately does not. Commit cannot capture
  mounted data and is not a transactional backup against concurrent writers.

## Locks and operation recovery

Supported entry points acquire only needed guards in this order:

**installation usage → data coordinator → environment IDs in stable order → base build → base publication**.

Installation/base guards use fixed `/tmp/opencode-sandbox-locks-<UID>/`, never HOME/TMPDIR/XDG/data
overrides. Installation keys hash the canonical Python prefix; base keys hash UID, canonical
verified daemon endpoint and distribution. Context aliases converge. Validate private own-UID
0700 directories, 0600 regular single-link files and safe parents using no-follow directory-relative
opens; recheck path/inode agreement after flock. Unsafe paths fail closed, without repair/fallback.
Never unlink a supposedly stale lock: process death releases the lock, not its persistent inode.
Descriptors are CLOEXEC; fork-only children close copies without unlocking the parent's description.

`launcher.main` takes shared non-waiting installation usage before Typer/core/TUI imports or data
creation; `cli.main` reenters it for supported wrappers/module invocation. Usage lasts through
**actual process exit**, including executor/non-daemon shutdown, not just main/dashboard return.
Concurrent ordinary instances are allowed; exclusive update access refuses any holder, including
the caller's own lease. No upgrade/release gap, exported exclusive descriptor or normal-CLI bypass.
Normal help/version also refuse exclusive access (exit 2). Direct library calls and older managers
are not coordinated. Incomplete authoritative update state adds a separate startup barrier.

Base builds/rollback hold build throughout verification/owned cleanup and publication only for
inspection/revalidation/tag changes. Creation holds publication from pin validation through Docker
creation. Cleanup takes build then publication nonblocking, rechecks ownership/references, and
releases each item's guards before proceeding. No per-data-directory lock protects a shared base.

Environment mutations hold `core.lock` for guarded steps. Multi-step operations persist an
`operation` journal (`recreate`, `runtime-recreate`, `config-update`, `restore`, `opencode-update`,
`delete`, `start`); a journal can mean running or interrupted while step locks are released.
`readiness.RECOVERY` names the explicit next handler; `start`/`repair` cannot guess past it.
Handlers reread metadata under lock and re-mark only their own journal. Delete removes metadata
last. Recreation stops before commit and never force-removes an externally restarted container.
Missing images retain journal/error and salvage guidance rather than discarding intact user data.

## Docker access, identity and diagnostics

`runtime_identity.verify()` resolves the configured context (default `rootless`) once and accepts
only a local Unix socket without TLS configuration. Foreign/rootful listeners refuse immediately.
With SO_PASSCRED enabled, each byte of bounded HTTP/1.0 `/info` must have matching SCM_CREDENTIALS:
one live own-UID `dockerd` with its own namespace mapping UID/GID 0 to the host user, and exact
`name=rootless` in that response. Recheck process start time, executable and maps after reading.
Reject proxies, changed/missing credentials, received rights, malformed/encoded responses and PID
reuse. A legitimate inherited listener works because the **response sender**, not systemd's
listening PID, proves identity (D-052). Socket names/ownership and forwarded rootless text do not.

Subsequent calls use the pinned `docker -H unix://<socket>` with Docker endpoint/TLS environment
overrides dropped. Explicit `ensure_runtime()` re-verifies, never re-resolves that endpoint.
Acquisition has one 10-second monotonic context/transport/retry budget; only typed transient
transport failures retry. Identity, permissions/configuration and protocol errors are final.
Overlapping callers share in-flight acquisition only; no permanent readiness cache or mutation
replay. CLI progress is stderr; dashboard feedback/cancellation stays off the UI thread.

| Diagnostic | Bound / ownership |
|---|---|
| Identity response | 16 KiB headers, 512 KiB full response, HTTP 200/EOF/consistent length; no encodings or duplicate headers |
| Read-only Docker/host commands | Finite allowlist; normally eight seconds and 1 MiB combined output; explicit-timeout `core.call` uses `diagnostics.run` |
| Resource-support query | Five seconds on the verified endpoint; report capabilities separately from container configuration/kernel enforcement |
| npm / manager discovery | Isolated stdlib HTTP child, eight seconds including DNS/body; npm 8 MiB, GitHub release list 4 MiB |
| Container version / readiness / image verification | GNU timeout process group: five / ten / thirty seconds; host transport gets three seconds' grace |
| Interrupted image-helper cleanup | Three-second non-cancelable inspection/removal; exact full ID and invocation/manager/data/helper labels required |

Host diagnostics drain bounded pipes, cancel only owned process groups and reap clients. WNOWAIT
reserves group leaders until cleanup to avoid PID-reuse signals. A dead host Docker client is not
proof container exec ended: container timers remain responsible. Missing timeout tooling never
permits an unbounded retry. Helpers use network none/pull never; unreachable Docker leaves a named
unconfirmed leftover, not a success claim. These are liveness bounds, not a hostile-container
security boundary. Builds, installs, commits and interactive commands have no short diagnostic
deadline. `tui_runtime.publish` rejects late canceled/replaced results both before and on the UI thread.

Resource/image diagnostics are advisory: `doctor` exit 0 verifies host programs/identity, not every
capability or image. Unknown evidence is not success. Base labels compare definition revisions,
not actual OS/package freshness; an inspect error is not absence. Category-owned notices replace
only their own old results and never overwrite operation progress/recovery or unrelated notices.

## Settings, workspaces and backups

`config_plan` is shared by CLI/TUI; consent binds a diff that is re-planned under lock. Changes are
saved when no container exists, dynamic for CPU/memory/PIDs, restart for lowering live memory, or
recreate for network/ports/profile. Memory swap is twice memory to avoid Docker retaining a lower
old swap limit. Recreate preserves the system layer and prior running state; configuration merges
only approved fields into fresh locked metadata. Recovery repeats idempotent journalled steps.

Managed workspaces are empty or imported copies/clones; only they may be deleted/restored by the
manager. Direct workspaces need explicit consent, path/owner/mount safety checks and a container
write-preflight, then rechecks before every start/creation. They are never chowned/chmodded/deleted
or restore targets. Backups omit them unless explicitly included; restores always create managed
workspaces. Checks are snapshots, not protection from a socket/mount introduced later.

Host Git uses a private manager-written `GIT_DIR` with only storage-format settings, snapshot HEAD/
index and data links to objects/refs. Workspace config/hooks/drivers/includes never execute.
Refuse gitlinks, unsupported split indexes and unsafe `.git` structures/links/alternates/grafts;
disable lazy fetch. Live object data has a documented read-only race, not a snapshot guarantee.
Transfer preflight refuses new escaping links; existing base-commit links stay as they were.
Sandbox-derived output is escaped, never rendered as terminal controls/markup. Exports/bundles/
backups cannot target any environment's workspace, including through symlinks.

Cold backups have manifests/checksums, workspace/home archives and optional system image, including
a derived layer with no container. Validate before publication; report omitted sockets/FIFOs.
Extract regular files exclusively before links, never through a link; reject traversal, duplicate/
noncanonical names, special files and unsafe hardlinks. Preserve symbolic targets verbatim.
Restore creates a new journalled environment through staging volumes, supports explicit resume/
rollback, re-labels loaded system images for the restoring data directory and retains original
custom-image provenance. Home/workspace data is not undone by a system-layer rollback.

## OpenCode, image builds and discovery

`distros.REGISTRY` owns distribution-specific assets/tools/smoke checks. Debian 13/revision 2 and
Arch rolling/revision 1 are verified against `/etc/os-release`, tools and the actual OpenCode
binary. Existing/derived/restored layers retain inherited provenance; never describe them with
today's registry OS/tool promises. Unknown/offline labels stay unknown, not an invented current OS.

OpenCode is `@opencode/cli` 2.x only; self-update is disabled. Supported stable `latest` is resolved
fresh to an exact target **before consent**, never silently replaced afterward. Manual policy
suppresses unsolicited notices, not requested comparisons; pins constrain creation/update.
Environment update requires a stopped owned network-enabled container, checkpoints its entire
system layer, journals installation/verification and finishes stopped. Failure/recovery restores
the checkpoint; rollback first snapshots the present layer. A successor recreation failure retains
`runtime-recreate` and points to `config recover`, not blindly back to `update-recover`.

Base build consent binds daemon, definition/assets, current immutable image or proven absence,
target, mode and retention. Build a unique candidate, verify its immutable ID, then revalidate
consent/candidate tags before publication. Cached builds reuse eligible layers; explicit refresh
uses `--pull --no-cache`, never cache prune. `update-base`/TUI retain replaced bases; CLI `build`
deliberately permits no-copy replacement and discloses it. No existing container migrates.
Rollback groups aliases by full image ID: select automatically only for one distinct copy, otherwise
require an explicit listed tag/full ID even with `--yes`. Dates/order are not replacement history.
Verify current-definition OS/tools/binary, preserve the replaced base, consume only selected aliases;
already-current is a verified no-op. Unknown/changed identities refuse, not deletion permission.

Actual version observations bind source/time, endpoint, environment/container/creation-image IDs
and lifecycle history in private disposable `update-cache/` files. Reinspect around probes; stopped
environments retain dated history or Unknown, never build labels as installed proof. Replacement,
restore/update history and pending journals invalidate/qualify observations. Failures do not turn
old evidence into fresh success. Cache format 1 is not metadata/journal authority; bounded no-follow
private storage failures are misses, not path repair or normal-operation failure.

Daily discovery is dashboard-only and defaults off. Each npm/GitHub source durably claims an
attempt before HTTP under a private source/data-directory flock; overlapping callers share its
result/failure. Success and attempt history stay separate. An automatic failure/interruption still
consumes 24 hours; future clock claims retain throttles, not freshness. Explicit checks may run
early but honor Retry-After/GitHub reset. Unsafe storage disables automatic requests; manual bounded
uncached fallback loses persistent coordination, never mutation safety. No discovery lock crosses
consent/mutation, and no cache grants installation or clears a journal.

Manager release discovery accepts exact published full `vX.Y.Z` releases, canonical URLs and valid
past times; numeric highest, no draft/prerelease/implicit downgrade. A full 100-entry page refuses
as incomplete. Notes are bounded plain text, not executable instructions. The quiet `Updates (N)`
indicator counts qualified Notify environments and a newer manager release without Docker/network;
Manual/Pinned/Unknown/pending recovery do not generate unsolicited environment counts.

## Sessions and initial configuration

Managed `run` uses `opencode --standalone` so one session cannot retain a previous client's provider
environment. `shell` gets the same profile; arbitrary `exec` does not. A per-session token/watchdog
hangs up the exact session after manager death. Defer callable launch signals only until client PID
and watchdog ownership exist, then deliver inside cleanup; never inherit a blocked signal mask or
use threaded `preexec_fn`. Reap forced termination and restore the attached input tty in `finally`.

Agent Context is a read-only directory mount at `/run/ocs-agent/`; the system OpenCode configuration
adds `instructions: ["/run/ocs-agent/context.md"]` without replacing user configuration. Atomic
refreshes are visible live; regenerate before run/shell from configured/observed settings and base
provenance. A failed inspection yields a qualified preview, not verification of the saved file.
Custom images without the system instruction entry get a warning, not fallback injection.

Initial integrations use `opencode mcp add --global` only at the first start and only if no existing
global config exists: the upstream command can overwrite same-name entries or corrupt unparseable
files. Persist `applying` before the attempt; record success/failure/skip and never automatically
retry/reapply, including after restore. Context7 is the default, not a promise it works offline.

## Updates UI

`v` opens independent Manager/Base Images/Environment OpenCode views. Opening renders local/cached
facts before bounded inspections; it does not discover, probe binaries or start environments.
Explicit Check and Details keep source/local errors separate, bind selection/generation and reject
late results. Shared `ReportScreen` is titled plain scrollable text, not component-specific logic.

Read-only planning is screen-owned/cancellable; approved mutations belong to the app and retain
its operation slot through screen Close. Conflicting operations/normal Quit refuse until completion;
killing the manager still requires journals. Exact Cancel-first plans bind live metadata/policy/
object identities and revalidate in existing handlers. No universal updater or mutation Cancel.
Recovery Center rereads authoritative journals, routes OpenCode/configuration recovery to their
handlers and retains CLI guidance for other journals. Small-terminal forms use bounded text;
dashboard notices are disclosed in Details rather than covering 80x24 controls.

Base build output drains continuously into a 32 KiB tail with throttled UI publication and explicit
truncation, no percentage or build deadline. After process death, inspect actual images/copies/
named candidates: there is no new durable base-build recovery journal.

## Manager update and independent recovery

### Review and source proof

Public Updates → Manager → Update and `manager update --tag` require a strict newer published tag,
a fresh exact review and original foreground terminal. `manager_installation.classify()` reconciles
the running package, own-user no-follow PEP 610/pipx metadata, version/source/tag/commit, Python,
standard launcher/exposed symlink, invocation and PATH without executing pipx. Only recognized
wire formats 0.5/0.6/0.12/default options are supported; unknown/custom/foreign/editable/shadowed
installs require manual preservation, not conversion, metadata repair or launcher takeover.

`manager_tools` assesses existing independent external Python/pipx, complete symlink routes and
declared dependency closure from raw RECORD inventories (including absent/lazy paths). Preserve
literal recorded source-Python spelling and recognized custom pipx locations. Reject unsafe or
target-dependent tools/stdlib/import/namespace/metadata routes. Only inspected pipx 1.18.7 is
supported. Isolated stdlib diagnostics precede fixed version-only external probes; tools/site/build
code remain trusted host code, not sandboxed, content-authenticated or frozen dependencies.

Exact GitHub HTTPS source reads validate release ID/tag/notes/publication, ref, zero-to-four
annotated tags and the full commit object; strict SHA-1 OIDs/URLs/types, no cycles/duplicate or
non-finite JSON. Fresh release/ref reads bracket the graph; revalidation fetches **the same target**,
never latest/cache fallback or `target_commitish`. Bounds: eight seconds including source-lock wait,
128 KiB per response. Shared rate-limit coordination does not store a target/grant or survive into
mutation. TLS graph agreement is not signed-code attestation or a remote atomic lock; later tag
movement still requires checking the actual installed commit.

Review binds the exact source, installation/tools/settings, hashed HOME/PATH/XDG selections,
critical-record bytes and complete observed routes. Files/symlinks bind identity/stat; directories
bind identity/owner/mode, not timestamps, so unrelated cache creation is allowed. Public-default
installer policy is explicit: detected pip/Git/uv/Python/loader/proxy/CA/SSH-agent/index/custom
credential configuration requires manual preservation without reading values or silently stripping
settings. The scrollable modal defaults Cancel and requires exact target/public-network acceptance.
Its in-memory Approval is not an executable capability or durable mutation grant. Revalidate local
observations around fresh source reads while retaining the origin's shared lease.

### Frozen handoff and independent execution

App admission counts actual worker bodies/queued workers and entire attached-session lifetime,
not canceled Textual task status. Handoff refuses active work/open consent, seals admission and
lets Textual fully close. CLI verifies its original stream/device/inode/foreground process group,
exact termios and Linux driver input/output shutdown before helper launch/arming; failed launch/
restoration cancels and reaps that exact helper. No headless/custom-driver bypass.

`manager_handoff.BUNDLE` freezes 18 stdlib modules into private single-link 0600 artifacts in a
unique 0700 directory under canonical pipx home's `.opencode-sandbox-updates/operations/`, outside
the replaceable venv. Validate content hashes/inodes and fsync files/new directory entries. The
external `-I -B -S` helper imports no replaceable application code. Authenticated seqpacket, origin
pidfd and directory descriptors bind live intent/UID/PID; no installation lease crosses exec.
Arming, EOF, main return and terminal restoration are **not process death**. Only actual origin
pidfd death permits one non-waiting exclusive attempt; another supported instance returns busy.

Under exclusion, frozen local replay checks critical records/routes without executing the target;
capsule context is data, never an applied arbitrary environment. Bounds: 1 MiB input, 512 KiB
binding, 128 KiB critical records, 2048 routes with bounded link traversal. Replay alone is neither
fresh tool/source/policy validation nor health/success. `manager_execution` independently checks
external runtime/dependencies/settings, published graph and effective pip/Git configuration. Known
config paths must be absent; actual shared pip and unsuppressed/fixed Git keys must match public
PyPI/HTTPS-only/no-redirect/no-proxy/no-credential-helper policy. Git discovery ceilings prevent
ancestor project configuration. This controls standard clients, not arbitrary host build/site code.
Preflight is 60 seconds overall; the 30-second non-mutating fixture lifetime is not an install limit.

### Durable admission, result and recovery

Immutable format-1 `operation.json` binds nonce, prefix, previous/target source/tag/commit/version,
settings, literal source Python, tools/helper/digest and installer-policy inputs. Print independent
recovery instructions before mutation. Authoritative format-1 state at
`<canonical-pipx-home>/.opencode-sandbox-updates/<sha256(canonical-prefix)>.json` survives venv/helper
loss and product overrides. Only the actual kernel-exclusive owner advances prepared → installing
→ verifying → complete/manual-recovery. Unknown/corrupt/unsafe/other-version state stays preserved
and blocks startup; caches cannot repair/reset/migrate it.

The independent installer child parks under parent-death SIGKILL before external/site code.
Persist its exact PID/start/group **before GO**; it independently authenticates the live parent's
kernel-exclusive ownership through its own unlocked witness, validates operation inputs, closes
the witness and execs only existing pipx `install --force` with exact official tag/source Python.
No shell, interpreter fetch/switch, latest substitution, automatic retry or exported lock descriptor.
Reserve the unreaped group leader against PID reuse; helper subreaper/pidfd/actual-parent checks
own adopted/escaped descendants. Unknown quiescence remains blocked; legitimate builds/installation
have no short diagnostic deadline. Lost stdout redirects only the broken helper output fd; private
phase/result records still persist.

`manager_result` independently checks exact pipx/PEP 610/distribution records, settings/source Python,
standard launcher/exposed symlink and all raw RECORD routes inside the prefix. Fresh fixed clients
separately query version/prefix/module and construct the actual CLI/help graph. They never dispatch
normal commands/callbacks, Docker or caller-selected code. Frozen stdlib bootstraps validate peer
UID/PID/pidfd and live owner flock fdinfo, set parent-death protection before target site startup,
and pass only an independent unlocked O_RDONLY witness, not exclusion. Clients close it before
target queries (health bootstrap before site initialization); nonce/kernel message credentials bind
responses to the actual fresh PID. Normal CLI still refuses under exclusion. Unsupported Linux
pidfd/fdinfo/parent-death/subreaper facilities have no unsafe fallback.

Verify expected target and previous installations independently, never from installer exit/cache.
Durable outcomes are target-verified, previous-verified, target-unverified or unavailable/interrupted.
Result plus final owner-quiescence evidence precede verified completion/startup reopening; no new
child starts after that final phase. Completed records are historical, not ongoing health checks.
The original frozen external `recover` mode only verifies with matching operation/helper identity,
dead prior owner and fresh exclusion/results. Same-boot recovery requires never-admitted preparation
or durable known final quiescence; hard helper death plus an empty old group is insufficient.
A different boot proves old descendants gone; no automatic reboot/reset or stale-PID signaling.
Previous-tag reinstall is manual guidance, not automatic rollback, identical dependencies or an
offline guarantee. Environment data/configuration, images, pins and OpenCode settings are separate.

Non-mutating fixtures remain testable without installing: they share the real death/exclusion/
terminal boundary but their results grant no update or startup bypass. Installed tests declare
private Git/loopback transports; these are not public-release authentication. Scope and the still
unverified post-reboot recovery path are recorded in BASELINE/CAMPAIGN.

## Cleanup and packaging

Product cleanup re-inventories eligible labelled objects under coordinator/owner/base guards,
removes only confirmed still-eligible keys and never forces. Preserve existing environments,
direct workspaces, exports/bundles/backups, current base images, foreign data and shared build cache.
Superseded cleanup may remove unused runtime/checkpoint/base-copy objects, including daemon-shared
copies another data directory might later want. Reference checks are local, not future-intent locks.

The MIT package uses setuptools >=77; sdist/wheel contain image assets and no retired host installer
or private test injector. The sdist omits tests, which need the checkout. Python >=3.11 is declared
once in `pyproject.toml`; no version-specific application path. User installation is pipx from an
official version tag; uninstall retains data. Host setup belongs to upstream Docker/distribution
documentation, never a replacement wizard. Existing unidentified launchers/installations are not
removed or adopted automatically. CI/release gates and lint/error-reporting rules are unchanged.
