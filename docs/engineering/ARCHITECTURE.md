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
advisories while preserving operation status. UP-07/UP-08 add disposable identity-bound version
evidence, compatible stable discovery and explicit policy comparisons. UP-10 adds the manual/
cached compact Updates interface; UP-09 adds default-off dashboard discovery; UP-11 binds explicit
environment actions and recovery to existing handlers. UP-12/UP-13 bind base actions and explicit
cached/full-refresh builds; UP-14/UP-15 add read-only manager discovery/classification.
UP-16's first safety checkpoint adds early process-lifetime usage/exclusive coordination. Its
second checkpoint adds independent external-tool/runtime prerequisite facts. Its third stages
an independent stdlib helper with a non-mutating process-exit fixture. Its fourth adds a dedicated
fixed read-only fresh runtime query under helper exclusion. Its fifth adds an internal restored-
terminal handoff/refusal fixture. UP-17's first checkpoint adds internal read-only exact published
release/tag/commit resolution and fresh same-target revalidation. Its second adds internal exact
origin review/consent and fresh origin-side revalidation. Its third adds frozen post-exit/exclusive
replay of approved local file/route observations only. Later internal checkpoints add durable
incomplete-operation startup blocking, independent frozen tool/dependency/source/effective-client-
policy diagnostics and exact installed-file/launcher checks plus separate runtime and fixed
CLI-help construction queries. These are non-mutating prerequisites, not a replacement/recovery
engine or public updater. Manager Update is disabled.

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
| `launcher.py`, `installation_locks.py` | Stdlib-only console bootstrap/canonical-prefix process-lifetime usage/internal exclusion; unlocked read-only witness for dedicated fixed verifier, never a lease export, ordinary-startup exemption or early-release API | D-056, D-057 |
| `manager_tools.py`, `manager_tool_probe.py` | Explicit internal dated external-tool prerequisite assessment and self-contained isolated diagnostic source; only known existing pipx version/runtime/settings checks, no helper/handoff/executor or automatic consumer | D-056, D-057 |
| `manager_handoff.py`, `manager_helper.py` | Private frozen stdlib artifact/bounded non-mutating pidfd fixture, optional fixed runtime query and internal restored-terminal boundary; no public action/command/startup trigger or installation executor | D-056, D-057 |
| `manager_verifier.py` | Frozen external fixed-query launcher/parent-death bootstrap and dedicated installed read-only client; kernel descriptor/channel/pidfd checks, no normal CLI dispatch or source/launcher/installation-success grant | D-056, D-057 |
| `build_output.py`, `base_updates_tui.py` | Scoped base-build output/phase feedback with a bounded tail, target/mode and explicit rollback-copy forms, immutable consent; no mutation cancellation or universal executor | D-056, D-057 |
| `manager_releases.py`, `manager_installation.py` | Independent published-full-release discovery/claims and local-only conservative pipx provenance/settings reconciliation; no pipx execution or installation authorization | D-056, D-057 |
| `manager_targets.py` | Internal explicit exact published release/ref/peeled-commit observation and fresh same-target revalidation; fixed GitHub HTTPS authority, no cached target grant, install consent or executor | D-056, D-057 |
| `manager_review.py`, `manager_review_tui.py` | Internal immutable exact origin installation/tool/source/public-default network review, explicit scrollable consent receipt and fresh origin-side revalidation; no public route, executor, independent exclusive check, durable grant or helper payload | D-056, D-057 |
| `manager_observations.py` | Shared stdlib bounded critical-record/route primitives and frozen approved-local-observation replay under real helper-owned exclusion; no target import, fresh tool/source/network execution, installer or recovery authority | D-056, D-057 |
| `installation_state.py` | Private durable incomplete-operation barrier outside the replaceable pipx venv, strict format-1 transitions and own-exclusive-owner writes; unknown/pending state blocks ordinary bootstrap, never repaired or cleared by a cache | D-056, D-057 |
| `manager_source.py`, `manager_process.py`, `manager_network.py`, `manager_pip_probe.py`, `manager_execution.py` | Shared stdlib published-graph semantics and independently frozen bounded external-runtime/dependency/effective pip/Git/source diagnostics; refuse custom settings rather than read/strip them, no installer or cached authority | D-056, D-057 |
| `manager_records.py`, `manager_result.py`, `manager_health.py` | Shared conservative pipx record semantics, exact expected source/commit/version/settings/launcher/in-prefix RECORD checks and separate authenticated fixed CLI-help construction under exclusion; no normal command dispatch, startup exemption or operation completion authority | D-056, D-057 |
| `diagnostics.py`, `http_probe.py`, `probes.py` | Bounded captured host diagnostics, isolated stdlib HTTP child, container-side probe limits and invocation-owned image-helper cleanup; not long-mutation/session executors | D-056 |
| `distros.py` + `assets/images/` | Registry of managed distributions (Debian 13 default/revision 2, Arch Linux with `paru`/`ocs-aur`), Dockerfiles, validated image provenance, OpenCode install script | D-005, D-006, D-016, D-017, D-051 |
| `opencode_versions.py` | Registry lookup without host npm, policies (notify/manual/pinned; OpenCode 2.x only), journalled base and environment updates, rollback | D-007, D-019, D-033 |
| `update_cache.py` | Bounded private disposable evidence/attempt files, optional durable replacement and secure source-scoped exclusion; no metadata/journal authority or mutation locks | D-056 |
| `update_discovery.py` | Dashboard-only independent optional daily GitHub/npm attempts and Docker-free qualified cached availability; no component executor | D-056 |
| `updates.py`, `updates_tui.py`, `environment_updates_tui.py` | Read-only base inventory, compact local/cached-first Updates views, independent checks and owned cancellation; environment target/policy forms and immutable consent invoke existing component handlers, not a universal mutation engine | D-056, D-057 |
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
| `tui_runtime.py` | Thread-worker adapter for scoped diagnostics/cancellation/publication and app-local actual-body admission barrier for internal handoff; no UI retry loop or installation quiescence shortcut | D-052, D-056 |

`tui.ReportScreen` is the shared plain-text, scrollable read-only report for Agent Context,
Updates Details, readiness and cleanup results. Its title is a required explicit keyword argument,
rendered without markup; there is no versions-specific default. Agent Context uses
`Agent Context — NAME`. A failed container inspection is displayed with the configured-settings
fallback, and the saved guidance is not verified against that unobserved preview. Successful
inspection retains the existing file comparison. Neither path writes guidance or starts a
container; lifecycle generation and CLI verification remain unchanged.

## Exact manager source evidence (UP-17 first checkpoint)

`manager_targets.resolve` is internal and explicit, with no startup/status/discovery/CLI/TUI
consumer. It accepts a strict exact full stable tag and a version comparison input, requires a
strictly newer target, and never selects latest or downgrades/reinstalls implicitly. The caller's
installed-version string is not installation identity proof. Local pipx classification and cached
availability do not supply source authenticity or consent.

The authority is the fixed official repository's GitHub HTTPS API, using standard TLS trust, no
redirects, authentication/cookies, ambient token/proxy/loader/site/index settings or Git execution.
Separate isolated stdlib HTTP children and parent ownership bound the entire read-only graph to
eight seconds, including source-lock wait, with 128 KiB per response. That is not an installation
deadline. The exact published full release must have the requested tag, canonical official URL,
positive release ID and valid publication time. The exact `refs/tags/vX.Y.Z` must resolve through
zero to four annotated-tag objects to a commit; validate every OID, object type and canonical
repository object URL, reject cycles/unknown types/foreign or malformed identities, and check the
commit object. Only the inspected 40-character lower-case GitHub SHA-1 format is supported. Do
not use release `target_commitish` (which can be a branch), pagination/latest caches, abbreviated
hashes or URL data as executable instructions. Duplicate/non-finite JSON refuses.

Fresh release/ref reads bracket the graph; observed changes refuse. This is not a remote lock or
an atomic GitHub snapshot, and a tag can still move later. The frozen in-memory target includes
release ID/tag/version/publication, bounded printable notes, a hash of the full bounded notes,
and the complete tag-OID/commit chain. `revalidate` fetches that same exact target afresh, ignoring
timestamps for equality, refusing changes (including a replacement tag object pointing at the same
commit, edited notes beyond the displayed prefix or recreated release). It never substitutes a
newer release or falls back to old success after HTTP failure. The source observation is neither
signed-tag/commit-signature verification nor proof the source builds the expected package.

Source requests reuse the GitHub discovery source guard, but write a separate disposable durable
attempt-before-request record with no target, grant, installation or recovery data. No automatic
source-resolution scheduling exists; each explicit call/revalidation makes fresh requests, even
after waiting for another caller. GitHub Retry-After/rate-reset claims from either path block both
paths; source success/failure never overwrites latest-release success or its daily attempt claim.
Unsafe claim/coordination storage refuses this internal gate without repair. Ordinary discovery
retains its existing manual fallback/default-off daily policy. Cache corruption can remove
throttling evidence but can never authorize installation or supply a target. No source guard is
held across an installation mutation.

The helper bundle, verifier and terminal fixtures are unchanged: this module is not frozen into
an updater or connected to handoff/exclusive execution yet. Origin-side exact review/consent is
described below; the future executor must independently revalidate the approved exact target and
installation/tool/network settings under exclusion,
perform exact-tag replacement, verify actual expected version/source/commit/exposed launcher/basic
CLI, and independently prove external recovery records/instructions and interrupted/partial states.
Remote tag movement between revalidation and pipx fetch remains a risk requiring installed-commit
verification, not a claim that source resolution alone makes replacement safe. Manager Update
stays disabled. Private Git/loopback API tests prove parser/installed behavior, not public authenticity.

## Internal exact origin review (UP-17 second checkpoint)

`manager_review.prepare` accepts only a strict exact release tag, not caller-supplied classifier,
tool or cache facts. It rejects unsupported installer/network environment, freshly classifies the
actual running official-tag pipx installation/launcher, and retains the originating installation's
shared usage lease. It assesses the supported external pipx/Python runtime and recognized effective
locations using the existing fixed version-only diagnostics, then freshly resolves published source.
Local evidence is inspected again around the source reads; unexpected change refuses rather than
mixing identities. No usage release, conversion or exclusive attempt occurs in this origin path.

The frozen in-memory Review binds exact source, previous local release/commit/version, canonical
installation and actual launcher, recognized settings, external tool/runtime facts and a hashed
context of HOME/PATH/XDG/recognized pipx selections. It hashes bounded critical records (pipx,
PEP 610, distribution metadata/entry points/raw RECORD, package version module, application script
and pyvenv configuration) and observes every component of selected executable, Python, location,
critical-record and observed external module routes, including symlink spelling/identity and
absent configuration paths. File/symlink device/inode/owner/mode/size/mtime/ctime/link count are bound;
directories bind identity/ownership/mode, not timestamps, so unrelated cache/log/pyc creation does
not invalidate a review. Special/uncontrolled/cyclic paths and bounded-inventory overflow refuse.
This is a dated change detector for these observations, **not code authentication or an immutable
inventory of every installed or external lazy-loaded file**. External tools/site code remain
trusted local code; the future independent execution validator must re-establish its prerequisites.

The initial supported network policy is **public defaults only**. Existing nonempty pip/Git/uv/
Python/loader, proxy/CA, SSH agent/askpass and related installer configuration variables refuse
with a static manual-preservation reason, never their values. Known system/user/XDG Git/pip,
credential files (including netrc/Git credential storage), application/shared/external pip runtime
configuration paths must be absent; existence, including an unreadable file or dangling symlink,
requires manual preservation without reading contents, deletion or repair. No custom settings
are silently dropped to make review succeed. This intentionally conservative support is additional
to local pipx classification; a recognized install can still require manual update. The form
explains direct GitHub/PyPI/build-dependency downloads and trusted package/build code running on
the host as this user, not sandboxed by Docker. A later executor must separately implement and
prove the effective public-default network policy (including its Git/pip/config/credential
behavior), rather than assume these presence observations enforce it. No installer environment,
argv, new Git tool assessment or network-policy execution is introduced here.

`ManagerReviewScreen` has no product action/key/button/command/environment entry point. It displays
only an already prepared immutable review in a read-only scrollable TextArea, bounded plain release
notes and a visible impact/identity review. Cancel is initially focused; confirmation is disabled
until the exact target/public-network policy is explicitly accepted. Escape/Cancel returns no
receipt. Confirm returns an in-memory Approval holding that exact Review, **not a bool, executable
capability, serialization format or durable grant**. It performs no preparation, revalidation,
staging, helper launch/arming, worker cancellation or installation itself. Opening the modal still
blocks the existing dashboard handoff gate. A future public consumer must retain all active-body/
session/consent refusals and revalidate after consent; the receipt alone is never idle/exclusion proof.

`revalidate` requires the same origin PID/canonical installation and compares fresh local snapshots
and the same freshly revalidated source, with another local inspection after the source reads.
Changed installation/version/records/launcher/routes, observed tools/settings/context, network or
source refuse and require a new review. It keeps usage held and does not acquire exclusive access.
This is origin-side proof only. The frozen helper, terminal handoff, verifier and lease protocols
are unchanged; no review is passed into them and no updater/recovery payload exists. Independent
post-origin-death exclusive installation/tool/source/network revalidation, enforced network policy,
actual replacement/expected installed source/commit/version/launcher/basic CLI and failure recovery
remain separate UP-17 gates. Manager Update stays disabled.

Test-only installed-console injection exercises the actual launcher/bootstrap and all identity,
tool/source/file checks with an owned private Git/loopback API, real dashboard/terminal/consent and
fresh origin revalidation. Six scenarios per actual default/custom-space pipx layout cover both
sizes, default Cancel, explicit approval, an owned changed-launcher fault, custom index environment
and credential-file presence refusal without reading contents. No source/classification/lock/terminal
reply is mocked. This is automated installed/private-transport evidence, not public-release
authentication, human observation, actual replacement or an independent exclusive/recovery proof.

## Frozen approved-local-observation replay (UP-17 third checkpoint)

Origin-side revalidation cannot run after origin death: it imports the application and owns a
shared usage lease. The new `manager_observations` module contains only stdlib critical-record
and complete observed-route primitives shared by the origin and the frozen helper. Origin review
wraps its static refusal reasons without changing public classification, source/tool discovery,
policy or UI. This is a scoped extraction, not an independent copy of the review's checks.

`manager_handoff.prepare_review_fixture` accepts only an exact internal Approval receipt, freshly
revalidates its review in the origin, and stages a source-identical helper plus private `review.json`
outside the target. Nothing starts just by staging. The bounded format-1, fixture-only input carries
the reviewed target as opaque identity-bound data, original PID/prefix/version/review identity,
bounded observation binding and only the reviewed HOME/PATH/XDG/recognized pipx context. It is
not a raw environment/credential dump, executable capability, updater consent schema or recovery
record. Context is **data only**, never an applied execution environment. Input size is at most
1 MiB; the original binding remains at most 512 KiB, each critical record 128 KiB, routes at most
2048 with bounded symlink traversal. No metadata/backup schema or migration is introduced.

Artifact inventory binds input digest/identity and own private single-link file inode; tampered
permissions/content/inode, symlink/hardlink/special input and unfamiliar extra files refuse or are
preserved rather than repaired/deleted. Descriptor-relative helper reads use the original private
directory fd. Capsule parsing rejects unknown format/top-level fields, duplicate/non-finite JSON,
origin/prefix/version/context/identity mismatch and non-exact critical-record inventories. Critical
reads are restricted to the approved own installation's known records; this is not an arbitrary
file-read or command interface. Target/review hashes are dated identity agreement, not code or
published-source authenticity. Cleanup recognizes only this staged fixture's exact owned inventory.

The helper's only entry remains the bounded non-mutating process-exit fixture. The private request
adds only capsule digest/review identity/file identity, not commands, callbacks or normal startup
flags. It still inherits exactly its control socket, origin pidfd and directory fd, no lease.
Arming/EOF/main return/terminal restoration never substitute for actual origin termination. Only
pidfd-proven death permits the existing **one non-waiting exclusive attempt**. A live supported
participant returns busy, expiration while the origin lives returns expired, and neither replays
the approved input. No shared-to-exclusive conversion or early usage release exists.

Under exclusion, replay independently checks its own exact live kernel flock using an independent
unlocked witness, never exporting a guard or starting a child. It validates the private capsule,
compares all approved observed routes, hashes the exact critical records, then compares routes
again. Directory timestamps remain excluded; file/symlink identities/ownership/modes/metadata,
complete observed symlink spelling and absent configuration paths remain bound. A static success
records only `ok` plus review identity. Failure is `review-failed` with a static non-secret reason;
no late runtime query follows a failed local replay. The optional existing dedicated runtime query
can still run after successful replay, but remains a separate fixed observation, not expected-result
verification. All prior no-review fixture semantics and strict result/discard checks are retained.

This deliberately limited result is **not fresh independent classification, tool/dependency graph,
published-source or installer-network-policy validation**, runtime/launcher/basic-CLI health or
permission to install. No target package/runtime, tool, network, shell or installer is executed by
local replay. Its 30-second lifetime is still a fixture budget, not a future install deadline;
bounded byte/route counts and between-operation deadline checks do not preempt an unresponsive
filesystem. It is not a complete lazy-file inventory. A real test deliberately adds an owned late
startup hook that makes target Python exit 73: local replay still succeeds because the approved
observations did not change and no target code is run. The hook is then removed. This proves both
independence and why replay alone cannot enable Manager Update.

Test-only installed-console injection extends the actual origin consent/worker/admission/driver/
terminal boundary before arming; an observer records helper identity only after the real completion
call. Actual default/custom-space pipx packages test both sizes, non-daemon drain, unchanged and
changed post-arming observations, exact child adoption/reaping and unavailable target startup.
Host cases separately cover private-input faults, real kernel exclusion, other live usage and
expiration. Private Git/API/synthetic host identities remain explicit fixtures, not public or
installation-success proof. Manager Update stays disabled. Fresh independent tool/dependency/
source/network validation and effective installer network policy, actual replacement/expected
installed result and independent failure recovery remain the next gates.

## Early installation access (D-056, UP-16 first checkpoint)

The packaged console entry point is `opencode_sandbox.launcher:main`. It imports only stdlib and
the stdlib-only `installation_locks` module before taking shared access; no Typer/core/TUI import
or product-directory creation precedes exclusion. `cli.main()` also takes/reenters that lease
before dispatch, preserving current-code older console wrappers and module invocation. Merely
importing/calling the internal Typer app or Python library is not a supported entry point and
does not acquire a lease. The package version remains an inert constant, not an import-time lock.

The fixed own-user 0700 `/tmp/opencode-sandbox-locks-<UID>/` namespace is shared with base guards;
there is no HOME/TMPDIR/XDG/data/config override or fallback. A distinct `installation-<hash>.lock`
is keyed by the canonical absolute Python prefix, not the shared interpreter binary or the venv
inode (which replacement can change). Aliases converge and separate environments do not merge.
No-follow directory-relative opens validate own UID/exact 0600 regular file/one link, parent
ownership/sticky writability, and directory/file inode agreement after acquisition. Unsafe paths
are refused, never repaired, unlinked or regarded as stale. This stdlib bootstrap validation is
deliberately independent of the core-dependent base implementation; neither imports the other.

Non-waiting shared flock permits concurrent CLI/dashboard processes. Internal exclusive flock
refuses with any shared/exclusive holder, including the requesting process's own lease: no
shared-to-exclusive upgrade or release/reacquire gap. Normal startup (help/version included)
refuses exclusive access with a static error/exit 2, before dispatch. A process-global mutex makes
usage acquisition idempotent across callers/threads. The shared guard remains referenced until
process exit, **not** main/dashboard return: non-daemon/thread-pool shutdown cannot leave a live
worker operating after release. No production early-release API is provided at this checkpoint.
All directory/lock descriptors default to CLOEXEC; fork-only children close their copies without
LOCK_UN, so they neither unlock the parent nor keep its lock after it exits. Entry in a forked
child must acquire a new lease. The dedicated verifier receives only an unlocked read-only
witness, never a lease or exclusive descriptor. Process death releases the
guard; persistent inodes remain.

Installation access is acquired before data coordinator/environment/base guards. A small
context-local data-lock observation in core complements the existing base-held observation;
new installation access inside either refuses reverse ordering, while an already-held usage
lease may reenter without reacquisition. Data/base mutation semantics and diagnostic timing are
unchanged. Library callers, older managers, manual external pipx/Docker and escaped daemon-side
work after a killed client do not honor this protocol; it is not a same-user security boundary
or proof that orphaned work stopped. Provenance classification recognizes both standard old and
bootstrap console templates, without claiming that an older installed program implements locks.

This independently verified startup checkpoint is only part of UP-16. The internal non-mutating
terminal handoff is described below; no replacement consumer, recovery record or automatic restart
exists. Those remain separate gates; exclusive access alone never authorizes mutation.
Manager Update remains disabled. Any future mutating handoff must preserve the actual process-exit
boundary rather than close this lease while Textual workers could still be alive; no generic
environment-variable/CLI bypass is present.

### External-tool prerequisites (UP-16 second checkpoint)

`manager_tools.assess()` consumes dated recognized local classification but never treats it as
consent or a durable grant. No startup, CLI status, discovery or UI path calls it. It neither
holds installation-exclusive access nor changes installed code/configuration. A PATH candidate
alone proves nothing: inspect a bounded standard pipx console script and literal Python shebang
or exact pip shell trampoline as data, never shell-evaluate it. Reject ambiguous wrappers/env
shebangs, wrong owners, writable files/parents and tools/interpreters inside the target. Check
every symlink-route component, not only the final binary: an external alias that passes through
the replaceable venv still depends on that venv. Identity/stat and script hash are reread after
both child probes; a changed candidate cannot publish supported prerequisite facts.

The diagnostic source is sent in memory to the already-existing external interpreter, not
imported from the replaceable environment. First run stdlib-only with `-I -B -S`; require Python
3.11+, independent executable/prefix/base/stdlib/search paths. Then run `-I -B` with the actual
recognized pipx script's fixed `--version` argv. Only inspected pipx **1.18.7** and its expected
entry point are supported; its version exit precedes logging/directories/listing/metadata repair.
No list, environment, install, Python fetch, shell, host npm or Docker call is added. Existing
diagnostics own a finite eight-second/128 KiB budget **per child**, including DNS-free startup,
pipe draining, cancellation and process-group reaping. These are not updater/build deadlines.

The pipx child validates declared dependency closure using its existing packaging dependency,
including active environment markers/default extras, installed versions, metadata file inventory,
all observed import/namespace/search paths and resolved locations. Read bounded raw CSV RECORD
files from recognized filesystem dist-info (512 KiB/8192 rows per distribution, 64 distributions/
16384 rows overall), never CPython 3.14's missing-file-filtered `Distribution.files`; unknown
metadata/provider formats refuse. Declared paths into an absent target must not disappear from
the proof. Unsafe/foreign/writable or
target-dependent routes refuse even when pipx itself is external or a dependency is lazy/not
imported by --version. File inventories qualify paths, not content authenticity or future
installability; their digest is local evidence, never attestation. The diagnostic itself has
stdlib top-level imports only. Imported external pipx/dependency code is the user's existing
trusted tooling, not sandboxed or cryptographically authenticated by this inspection.

Only classified effective HOME/BIN/MAN/COMPLETION/SHARED locations and the **recorded source
interpreter path** are passed explicitly; validate the external pipx resolves them as expected.
Keep the requested source-Python spelling (a venv path may share a binary), validate its complete
route, and report the observed canonical endpoint separately. Do not canonicalize away target
dependencies or silently replace the selection. Refuse settings under the replaceable prefix
and unknown PIPX settings rather than guess preservation. Children receive only these settings,
HOME/PATH and fixed locale/no-bytecode controls; ambient Python, loader, pip/index/proxy/provider
credentials are not forwarded, logged or persisted. Future installation network/environment
consent is separate; this is not a promise to preserve arbitrary custom options or dependencies.

Results are timestamped in-memory prerequisite facts, independent of release caches and recovery
state. Probe output/import/metadata errors are not echoed, because they can contain secrets;
unsupported cases receive static manual guidance. Cancellation propagates rather than publishing
a late result. Successful assessment is still **execution unavailable**. Independent helper
materialization/process-exit coordination and narrow runtime-verifier access are described below.
The internal restored-terminal fixture is described below, followed separately by pending UP-17
consent, source authentication/revalidation, replacement and success/failure recovery.

### Frozen helper/process-exit fixture (UP-16 third checkpoint)

`manager_handoff.prepare()` freshly reassesses the existing external tools, then freezes source
copies of `manager_helper.py` (zipapp entry), `installation_locks.py`, `manager_tool_probe.py` and
`manager_verifier.py`
under a unique own-UID/mode-0700 directory in an explicitly supplied, controlled parent outside
the target. The zipapp and small inventory are private single-link mode-0600 files. Creation is
exclusive, content deterministic and SHA-256-bound; neither discovery cache nor recovery state
authorizes it. No process starts on preparation. The bundled diagnostic's only helper use is
its stdlib path-route primitive; its optional pipx diagnostic main is not entered. No package,
Typer, Textual, installed distribution or external pipx dependency is imported by the helper.
This is local artifact identity, not code signing or public-source authentication.

`start_fixture()` requires the originating installation identity, checks lock order, acquires/
retains ordinary process-lifetime usage and rechecks artifact/interpreter identity. It does not
upgrade or release that lease. An already-existing external Python runs the artifact with
`-I -B -S`. Only three explicitly selected descriptors cross exec: a private Unix seqpacket control
channel, an origin pidfd, and the artifact directory; the helper marks them non-inheritable again.
No usage/exclusive lock descriptor, caller
terminal, credential/proxy/index/Python environment, arbitrary argv, Docker or shell is passed.
The existing signal-launch guard keeps ownership if a callable INT/TERM/HUP handler interrupts
spawn; every failed start/cancel reaps its exact child. No fallback to PID polling or socket EOF
exists on kernels without usable pidfds. This is Linux process-lifetime coordination, not a new
daemon or general process supervisor.

The frozen entry accepts only the non-mutating fixture protocol. It validates peer UID/PID against
the inherited pidfd, request shape/bounds, isolated stdlib runtime/search/symlink routes, artifact
hash/ownership/directory inode, and absence of inherited installation guards. Readiness and explicit
fixture arming are separate. Before arming, lost origin/control means abandoned; after arming,
socket EOF alone never proves exit. Actual origin termination is required, including non-daemon/
thread-pool shutdown after main returns. Only then does the helper try the unchanged exclusive
guard once. Another live shared/exclusive holder yields busy; no retry or shared-to-exclusive
conversion. It can optionally run the dedicated fixed read-only verifier below, writes one bounded
private fixture result, releases its own guard and exits.
Even SIGKILL after fixture arming can produce only this non-mutating result, not consent or a
terminal-restoration claim. The fixture has a maximum **30-second lifetime** and an eight-second
initial request/readiness bound; neither becomes a future installation deadline.

While the origin lives, it owns explicit cancel/reap; after an armed origin exits, the helper owns
its remaining finite lifetime. Explicit artifact discard refuses a live child or changed/unfamiliar
files, ownership, inode, bytes or records. After origin exit the private artifact/result are retained
for the caller/supervisor's evidence, never scavenged by generic cleanup. Test-only subreapers adopt
and reap the exact orphaned fixture child without relying on PID 1 or signalling a reaped PID.
No automatic dashboard restart, ordinary CLI bypass or install command exists. The fifth
checkpoint's CLI/TUI fixture boundary below adds active-session/work refusal and independently
observed terminal restoration; none of these fixtures is permission to mutate. Manager Update
stays disabled until the independent UP-17 replacement and recovery gates pass.

### Dedicated fresh runtime verifier (UP-16 fourth checkpoint)

Only the non-mutating helper fixture's explicit verification choice invokes this query, after
actual origin exit and acquisition of the existing exclusive guard. `installation_locks._verification()`
requires that process's matching exclusive guard and correct lock order; shared usage cannot issue
it. It opens an **independent unlocked O_RDONLY witness** for the same private persistent inode,
alongside the number of the owner's actual exclusive descriptor. The exclusive description never
crosses exec. Witnesses default to CLOEXEC and are tracked for fork-only close-without-LOCK_UN.
No usage lease is released, upgraded or exempted; `acquire_usage()` and both ordinary
entry points ignore verifier capabilities and still refuse under exclusion, including help/version.

`manager_verifier.py` is bundled with the helper and installed for its dedicated fixed client.
The single-threaded external owner launches a frozen stdlib-only `-I -B -S` bootstrap with only
control, unlocked witness and owner-pidfd descriptors. It authenticates peer UID/PID/parent/liveness,
canonical prefix and live peer's kernel lock record, sets Linux PR_SET_PDEATHSIG/SIGKILL, rechecks the parent
race, then execs only that prefix's existing Python and the dedicated client with `-I -B`.
This avoids preexec_fn and any relaxation of at-fork descriptor-dropping rules, keeping process
setup out of threaded application code. Parent-death protection exists **before
target site initialization**, not just after the installed verifier imports; a killed helper
therefore stops the direct verifier even in an early site hook. A startup descendant retaining
the read-only witness cannot retain exclusion: it has no flock. Arbitrary site hooks remain
trusted local code, not sandboxed/authenticated or a promise to stop their escaped work. Tests
explicitly supervise/clean their deliberately spawned descendants.

The installed dedicated entry accepts only its three descriptors, never commands or user-selected
callbacks. It checks isolation/no-bytecode flags, peer UID/PID/parent/pidfd and one fresh nonce-bound
request. Kernel message credentials also bind replies to the actual fresh PID, not an inherited
channel's startup descendant. The witness must name the private persistent inode for its own
canonical prefix; the **live peer's fdinfo**, not the witness's, must identify the owner's named
descriptor as a full-file exclusive flock for that inode. A guessed busy inode, wrong owner-fd,
shared/POSIX/foreign-owner lock,
changed path, wrong prefix, arbitrary environment flag or descriptor passed to a normal entry point
cannot satisfy this protocol. The client **closes the unlocked witness before querying
the package**, then reports only observed version, canonical prefix and package module location.
There is no CLI/core/Docker/configuration/discovery import or normal app dispatch. Owner liveness
is checked again before the bounded response; no global verified/bypass state is installed.

The external owner validates shape/nonce/fields, retains the guard, waits for successful fresh
process exit, and only then accepts these **runtime facts**, not replacement success. It reserves
the process-group leader with WNOWAIT until group termination/reap to prevent PID-reuse signalling.
The fixed read-only query has an eight-second/4096-byte message bound, further limited by the
remaining fixture budget; neither changes build/install/session deadlines. Raw child streams and
environment are not published. Failure yields static unavailable facts, not success, cache/journal
authority, source authentication or a health claim. No persistent process or automatic restart.

This gate requires usable Linux pidfds, proc flock fdinfo and parent-death protection with no unsafe
fallback. Ordinary manager startup does not gain a new prerequisite. Expected release/source/commit,
actual exposed launcher, basic CLI health and post-replacement result/recovery verification remain
UP-17 gates. Independent restored-terminal transfer/refusal proof uses the fifth checkpoint below,
not inference from a runtime result. Manager Update remains disabled; no public verifier/helper command.

### Internal restored-terminal handoff (UP-16 fifth checkpoint)

Both implicit and explicit dashboards now use `cli._dashboard()`. Ordinary startup/quit does not
prepare tools/artifacts, start a helper or request an installation. An internal-only dashboard
method can accept one already prepared, unused own-installation artifact for the **non-mutating
fixture**. There is no product key, button, command, flag, environment trigger or installation
payload. Exact release/source consent and exposure of Manager Update remain UP-17.

The request must run on the live UI thread with no attached session, pending operation, approved
mutation or open sub-screen/consent. Attached-session lifetime is now explicit through the entire
suspend/interactive/resume path, cleared in finally even on failure; the old pending-operation flag
alone was false while attached. The shared worker adapter counts actual executing bodies, not
Textual tasks that may already say canceled/finished. All wrapped workers and the existing app-
owned configuration recovery use the same mutex-protected admission barrier. Requests refuse
running bodies and queued live workers, never cancel them. Once sealed, even a canceled queued
thread entering later cannot start application work. Screen-owned workers remain screen-owned;
approved configuration recovery remains app-owned and survives closing Recovery Center. No
existing mutation/session deadline or cancellation/recovery semantics change.

The internal request seals admission and exits Textual with a matching one-use typed result; it
does not start/arm a helper or release usage. The CLI accepts only that exact result after clean
return, zero return code, and full local Linux driver shutdown: no headless/inline/custom-driver
fallback, no live input/output thread. Before dashboard entry it observes all three original
streams on one real foreground tty. After return it checks stream/descriptor/device/inode,
foreground process group, process/thread ownership and **exact original termios**, without
repairing changed modes. Unsupported observation does not break ordinary dashboard use; it only
refuses the internal fixture. Visual teardown is Textual's responsibility; real-pty assertions
independently require alternate-screen exit, shown cursor and disabled mouse before handoff output.

Only after those checks does the CLI flush a plain non-mutating handoff notice, launch the existing
fixed helper and recheck the terminal before arming. Failed start/restoration/arming cancels/reaps
that exact helper. After acknowledged arming the origin closes its private control channel without
cancellation; the external fixture owns its bounded remainder. The shared usage lease **still lasts
until actual process exit**, including residual non-daemon/executor shutdown; the pidfd, not the
restored terminal or main return, permits the helper's one non-waiting exclusive attempt. A second
supported live manager still yields busy, not a retry or bypass. The helper inherits no terminal
or lease. No automatic dashboard restart, network/install/source executor, persistent recovery
record or change to the frozen helper/verifier/installation-lock protocol is introduced. The
30-second fixture lifetime is not a future updater deadline.

Test-only pty injection supplies a temporary F9 binding and an owned artifact without shipping a
user action. Installed default/custom-space pipx packages exercise actual CLI/App/driver shutdown,
fresh verifier, both terminal sizes, live shutdown draining, refused live/canceled lifecycle
workers that subsequently complete real Debian/Arch starts, actual attached Docker shell clients,
changed tty modes, and another actual installed dashboard. Loopback/private Git source transport
remains a declared fixture, not public release authentication. UP-17 must keep all these boundaries
when it adds exact source/target consent, replacement and independently verified recovery.

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
with an eight-second total parent budget and an 8 MiB abbreviated-metadata response limit, including slow DNS/body
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
per-call budgets; Updates publishes local/selected evidence and independent discovery without
waiting for every source to finish.

`UpdatesScreen` retains UP-10's `v` and one compact table
shared by Manager/Bases/Environment subviews, stable selection, plain selected summaries and
generic scrollable Details. Manager installed version is local; installation/release eligibility
is not guessed. UP-14/UP-15 implement read-only manager evidence below; execution remains disabled.
UP-11 binds Environment OpenCode actions; UP-12/UP-13 bind Base Images below.

Opening renders metadata and Docker-free `environment_history` first (explicitly identity-
unverified), then independent bounded local base/environment inspection workers. The new
`environment_version(check=False)` option never executes OpenCode or writes attempts; default
CLI/readiness behavior stays active. Base inventory validates immutable IDs, distinguishes
missing/foreign/unknown/older/newer/different definition provenance and reads actual image
evidence without helpers. Build labels do not become binary evidence. Check explicitly starts
separate selected-object and shared-per-screen npm work; partial failure, rate limits and prior
dated successes remain visible. Stopped/never-created environments are not started. Pending
recovery remains qualified even without a container.

Each screen owns its worker references and per-item generation tokens. A newer Check invalidates
older local inventory publication; Cancel/Close cancels only owned read-only work and refuses
queued/late results without treating cancellation as mutation rollback. Per-screen UI waiters
coalesce across both OpenCode views; UP-09 also coordinates the shared source below. Its local
cache/notice timer never calls Docker/network and adopts completed background/other-caller evidence
without retimestamping it.
Dashboard notifications/advisories remain intact, but Updates collapses its toast rack to zero
height and discloses a count/full messages in Details so notices cannot cover 80x24 controls.
Leaving the screen preserves dashboard notification/status ownership.

UP-11 adds one environment-only compact action row and target/policy forms. Review requests are
not eligibility grants from inventory strings, observations, cached discovery or readiness. A
screen-owned cancellable read-only worker resolves exact targets and prepares immutable consent
before a scrollable, Cancel-first modal. It verifies that displayed metadata still matches the
prepared plan; late/canceled plans cannot push consent after Close or over another screen.
The existing update plan additionally fingerprints current metadata and checks volume ownership.
Start uses an optional `core.start` precondition under its existing environment lock; ordinary
CLI Start is unchanged. Policy plans bind the exact mode/pin, data-directory identity and current
metadata; `set_policy` revalidates under its existing lock. No policy change installs anything.

Checkpoint plans bind action, metadata, endpoint/data identity, actual container identity/running
state, immutable checkpoint ID and any retained derived-image ID before consent. Optional plan
arguments to `rollback_environment`/`update_recover` compare the same evidence under their existing
lock before snapshots, stops or removal. The existing restore handler receives the confirmed full
image ID; the normal `image`/`last_snapshot` string fields can hold that Docker reference, while the
original named checkpoint stays in the update record for retention/cleanup. No new metadata schema,
parallel journal, component executor or cache authority. Missing immutable derived images retain
the existing data-salvage guidance. Present system-layer preservation, pin restrictions, direct
workspace checks, binary verification and final stopped state remain existing lifecycle behavior.

Restoration failures now persist `last_error` without clearing the current journal. If removal
has begun, that journal is `runtime-recreate`; failure messages and UI routing name `config recover`
instead of blindly repeating `update-recover`. Updates metadata adoption/Details reread authoritative
local records independently of delayed Docker inventory, qualify version evidence after lifecycle/
journal changes, and lead with operation results/recovery reasons. Recovery Center preselects a
routed environment and uses the same confirmed OpenCode recovery handler. Its existing configuration
recovery accepts a metadata/data precondition rechecked inside the original lock, not a new recovery
algorithm. Other journal types keep their existing command guidance.
Recovery Center's bounded read-only TextArea retains full results/errors and unsupported-journal
guidance even with toasts collapsed; long messages cannot expand past the 80x24 controls.

Approved environment operations are app-owned, non-exclusive/replacement workers, distinct from
screen-owned checks/planning. The dashboard reserves its existing operation slot before launch,
refuses conflicting actions and normal Quit, and suppresses cooperative UI cancellation inside the
approved mutation without removing bounded diagnostic budgets. Close/Cancel check cannot cancel
that work; completion publishes a result only while the app is running, then refreshes local
metadata/inventory. Killing the process still requires the existing durable journals. Configuration
recovery routed from these views has the same app ownership. No short timeout is added to install,
commit or other mutations. Toast racks are collapsed only on these forms, Recovery Center and
class-marked Updates Details; notification objects remain intact and disclosed through Details.

UP-12/UP-13 reuse `update_base` and `rollback_base`, not another update executor. `BaseBuildPlan`
is read-only: resolve exact target outside base guards, then inspect proven managed current image
(or confirmed absence) under publication. Consent binds canonical endpoint, image namespace/ID,
current provenance/build-version label, the immutable distro record, build-asset content digest,
target, refresh mode and retention choice. `update_base(plan=...)` accepts that exact target,
rechecks the plan under build/publication before build and before publication, and retains the
existing daemon-wide build/short-publication lock ordering. Unknown/foreign ownership refuses;
old/newer definitions are disclosed rather than treated as permission from availability strings.

Cached remains the default. Only explicit `refresh=True` supplies Docker `--pull --no-cache`;
neither path prunes cache or migrates environments. `core.build_image` returns the built immutable
ID. Its public default still verifies; `update_base` requests build-only, records the returned ID
and invokes the same current-definition OS/tool/binary verifier on that ID outside publication.
Publication checks that the candidate tag still names the verified ID. Cleanup checks that same
known ID, refuses an unconfirmed/retagged candidate, and reports removal errors instead of hiding
them. Content-equivalent candidates still verify and report unchanged without swapping/copying.
Rollback uses the existing alias-consolidated inventory/immutable plans and original handlers;
multiple images require explicit copy selection. No new schema, journal or base-policy/history
service. Failure/process death requires inspection of actual images/copies/candidates, not a
cache-based recovery guess. Existing containers/layers/home/workspace/configuration/integrations
stay unchanged; future creation/file-only restores and not-yet-created pin checks use the base.

CLI `opencode update-base` and `build` share plan/description and explicit `--refresh`. The former
confirms and retains a copy, including `--yes` noninteractive use; the latter preserves its existing
noninteractive no-copy capability and discloses it before mutation. The TUI always retains a copy.
Its target/mode, explicit multi-copy selection and Cancel-first scrollable consent are separate
base forms, fit 80x24/larger and retain advisory ownership without toast overlays. Screen-owned
read-only planning/cancellation is separate from app-owned approved base workers using the same
operation slot/Quit refusal as environment actions; closing/reopening Updates retains phases,
bounded build-output tail and result. No percentage or mutation Cancel is invented.

`build_output.listen` is a scoped ContextVar used only by the base worker. Only `docker build`
opts into its merged stdout/stderr client path in `core.call`; other CLI/mutation/diagnostic paths
are unchanged. It drains continuously into a 32 KiB byte tail with explicit truncation, throttles
UI publication (first output, phases and completion always published), closes/reaps the direct
client, and never imposes a build/output deadline. Output is plain and bounded in app memory,
not written over Textual. Short verification/inspection budgets remain unchanged. This does not
promise daemon-build termination if a client/manager dies or coordinate manual Docker/old managers.

UP-09's `daily_discovery` boolean preference defaults false, including old/invalid preference
values. Only a running dashboard schedules npm and manager discovery: at startup, after saving Preferences,
and on a 60-second consideration timer. Explicit CLI/Updates/latest-target resolution uses the
same source coordinator but does not gain unsolicited network work. UP-14 adds an independent
GitHub provider/worker, not a manager check inferred from npm or a universal executor.

`opencode_versions.latest(automatic=True)` checks the most recent attempt, not just successful
evidence. Under a source-keyed private `flock` in that data directory's `update-cache/`, persist/
fsync an attempt ID/time and incomplete result before HTTP. The guard covers only metadata
request/cache publication, never Docker, mutation locks, journals, consent or installation.
It is released before target execution. Fresh threads/processes that overlap wait cancellably
(10-second bounded source wait) and reuse the completed attempt, failures included; only the
owner uses the existing eight-second HTTP request budget. Success and attempts stay independent.
Lock files are no-follow, private own-UID single-link regular files, descriptor-relative with
post-acquisition namespace/inode checks, never unlinked/repaired. Source keys include npm URL
and supported major; the data-directory boundary is intentional, not a daemon-wide/global cache.

An automatic attempt consumes 24 hours from its persisted start, whether successful, failed or
interrupted. Backward clock changes retain future throttle claims without treating future success
as fresh evidence. Explicit refresh can run early but honors persisted numeric/date Retry-After,
including long pauses. Cancellation of a waiter cannot cancel an owner; owner interruption leaves
an incomplete claim and no new success. Unsafe/unwritable coordination or failed durable claims
disable automatic HTTP. Manual discovery keeps the original bounded uncached fallback; without
usable storage cross-process exclusion/rate persistence is unavailable. Cache clearing/corruption
can reset disposable throttles, never authorize a mutation or clear a journal. Other observation
writes remain ordinary disposable replacements; durable fsync is only requested for discovery.

The dashboard uses one stable `Updates (N)` label, no availability toasts or operation-status
writes. Its Docker-free count uses qualified dated environment history against npm evidence,
Notify policy, and no pending journal; Manual/Pinned/Unknown do not yield unsolicited newer-version
counts. A newer published manager release adds one independent count, never an execution grant.
Explicit comparisons are unchanged. Tooltip/Details qualify stale/cached source evidence;
Details also shows scheduling failures. Disabling cancels owned automatic workers and suppresses
the indicator, not the manual screen. No probes, temporary starts, installs, service or schema change.

UP-14's `manager_releases` uses only the official GitHub releases endpoint (no token/login, no
runtime override). The isolated stdlib HTTP child selects the GitHub Accept header and refuses
redirects; npm retains its existing header/redirect behavior. The parent owns the same finite
eight-second diagnostic client/process-group budget with a 4 MiB manager body bound. One page
of up to 100 entries is bounded; a full page refuses as incomplete instead of claiming a latest
release from truncated history. Filter exact published/non-draft/non-prerelease booleans, valid
past publication timestamps, canonical official release URLs and strict `vX.Y.Z` tags (no leading
zero, prerelease/build suffix or command text). Choose numeric highest, never npm/checkout version
or GitHub's mutable target_commitish. Notes are plain/truncated at 8192 characters, never executed.
Local version comparison never offers a downgrade. Public tag-to-commit verification is explicitly
not established by release metadata, caches or the local classifier; it belongs to execution gates.

Manager discovery has a distinct source key/evidence shape and selected release record. Its own
coordination preserves the same attempt-before-HTTP/coalescing/daily/failure/cancellation/clock
contract as npm, also honoring HTTP 403/429/503 Retry-After or GitHub rate reset. Cached records
are revalidated/sanitized, retain independent failed attempts and never authorize replacement.
Unavailable safe storage disables automatic manager requests only; explicit bounded discovery
still works without persistence while honoring readable rate limits. Separate app-owned read-only
dashboard workers publish npm/GitHub independently. Source failures and enabling/disabling work
do not change operation status, local installed facts, journals or another caller's request.

UP-15's `manager_installation.classify()` is local-only and never invokes/imports pipx. It reconciles
one actual running distribution/version/entry point, installed module path, bounded no-follow
own-user regular PEP 610/pipx records, exact official Git URL and requested version tag/commit,
actual venv/module/distribution/interpreter, pipx source interpreter/Python version and application
path. Only recognized pipx wire formats 0.5/0.6/0.12 with default options, pip backend, no injections/
pins/suffix/custom exposure/resources are supported; dependency executable inventory is data, not
an exposure setting. Unknown fields/settings are manual review, not metadata migration. Normal
pip console scripts and its exact long/space-path trampoline are inspected, not shell-evaluated;
unrecognized/special-quoting launchers refuse. The own-user exposed symlink, actual invocation and
PATH must select that same executable. Explicit custom HOME/BIN/MAN/COMPLETION/SHARED locations
and matching default Python are recorded; mismatched home/interpreter or unknown PIPX settings
refuse rather than guess. System/foreign/editable/shadowed/ambiguous metadata also refuses. Metadata
and option values that might contain credentials are never echoed on refusal; no paths are repaired.

Classification is timestamped local provenance agreement, not authenticated GitHub commit identity,
future mutation permission, dependency restoration or proof an external pipx/helper is independent.
The record hash/paths/source/commit/settings evidence is in-memory inspection, not a durable
authoritative grant. `manager status [--check]` and the Manager Updates view expose independent
local/discovery evidence without Docker or pipx execution. Opening runs only local classification,
not network. Explicit Check starts independent owned workers, preserves version/prior evidence
on either failure, and Cancel/Close rejects late results. Details includes bounded plain release
notes/manual guidance, and manager Update stays disabled. UP-16's early installation usage/
exclusion, independent helper, fixed runtime access and internal non-mutating terminal handoff/
refusals are implemented above. UP-17's exact target/source consent/revalidation, actual replacement,
expected installed-result verification and independent failure recovery remain pending.

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
  `readiness.json`), `exports/`, `changes/`, `backups/`, `locks/`, disposable `update-cache/`. Configuration
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

Supported entry points acquire installation usage first, then only needed data coordinator ->
environment IDs in stable order -> base build -> base publication. The base guard tracks its
execution context and refuses reverse/recursive base acquisition; `core.lock` refuses data/
environment acquisition inside a base guard. New installation access inside data/base guards
also refuses reverse order. Build/rollback hold build
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
not a new update executor or concurrent discovery service. Only running containers are queried
for their binary version; stopped ones retain qualified last verification or Unknown.

UP-07/UP-08 evidence is structured value/source/time/identity, separate from authoritative
metadata and operation state. Runtime probes target full container IDs, after existing ownership
checks plus an identity/ownership inspection, and recheck identity/lifecycle after probing.
Identity includes environment, data directory, verified endpoint, container and creation-image
IDs plus a fingerprint of creation/derived-image/update history. Stop/status/policy changes retain
dated evidence; replacement, restore (new environment ID), rollback, update history and pending
journals invalidate or qualify it without metadata hooks or schema additions. Inaccessible Docker
may expose history only as unverified against the current container; failed fresh checks never
make readiness pass. Update success/no-install verification is recorded from the actual probe,
after journal completion, with its original observation time. Labels are build provenance only.

Image evidence binds the verified endpoint and immutable image ID. Local-only image observation
reads labels/cache without helpers; explicit image verification uses an immutable, bounded helper.
Retagging selects another object's cache; rollback to the identical image may reuse dated real
evidence. No creation-image label becomes an environment's installed fact.

`update-cache/` uses hashed per-source/object filenames, format 1 (disposable file format, not an
environment/backup schema), 128 KiB per-file limits, private owner/mode checks and no-follow,
descriptor-relative reads/replacement. Invalid/future-time/unsafe/missing/unwritable cache entries
are misses, not permission to repair paths or fail an otherwise successful operation. Success and
latest attempt stay separate. No cache lock is held while taking mutation locks. Observations
are per-key last-completion-wins; UP-09 coordinates discovery requests/attempt claims separately.
A stale cache can lose an
observation but cannot authorize a mutation, clear a journal or prove current runtime state.

npm discovery reads one bounded abbreviated packument, semantically selects the greatest stable
supported-major version, and persists only that selected result and attempt, not the response.
Prereleases are excluded by default; strict compatible explicit alternatives remain possible.
Fresh failures preserve dated prior discovery, surface explicit errors and never fall back to
cached `latest` installation. Retry-After for HTTP 429/503 is persisted and respected. Manual and
Pinned allow explicit comparisons, while unsolicited comparison filtering and locked execution
eligibility remain separate. CLI environment/base confirmations receive exact resolved targets;
environment plans bind immutable identity and revalidate under the existing environment lock.
No target is replaced by a newer lookup after consent; pins/network/pending journals still refuse.

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
