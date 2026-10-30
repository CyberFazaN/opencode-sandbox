# Updates — approved architecture, implementation roadmap and handoff

## Status and authority

- **UP-00..UP-02 complete. Next: UP-03 only.** UP-00 persisted the plan; UP-01 fixes report
  subjects/Agent Context presentation; UP-02 preserves independent local/registry inventory
  results. This record captures approved design and implementation checkpoints, not a release proposal.
- Entry point: [TODO](../../../TODO.md#active-updates-architecture-and-ux). Durable approval:
  [D-056](../DECISIONS.md#d-056-updates-architecture-and-execution-order--accepted-for-implementation).
  Current implemented behavior/evidence: [ARCHITECTURE](../ARCHITECTURE.md) and
  [BASELINE](../BASELINE.md). Existing decisions remain unless explicitly superseded by D-056.
- Working branch: `work/updates`, created from clean `main` at `a20f1fc` (also `origin/main`).
  Manager version: 6.1.0; latest published tag: v6.1.0. No subsequent implementation work was
  present when this cycle began. The approved assumptions still match the implementation.
- One coherent task per cycle: investigate/reproduce, implement narrowly, test, review, update
  records, commit locally, then STOP. On Continue, recover from these files and Git, not memory.
- This is the single detailed running-effort record under D-045. Do not add a parallel plan or
  task database. Retire it only after its durable facts/evidence are in the permanent records.
- No version bump, release preparation, release tag, push, package upload, remote issue creation,
  release automation or publication is authorized. Completion is not release permission.

## Reconciliation with the starting implementation

Source paths below describe the UP-00 starting point, not a substitute for reading the code
again per task. UP-01 fixes report/Agent Context presentation; UP-02 fixes inventory loss on
remote failure. Other findings remain present.
Source inspection is not regression or real-operation evidence.

| Finding | Current implementation | Required correction |
|---|---|---|
| Wrong Agent Context heading (fixed in UP-01) | At UP-00, `tui._agent_context_worker` used `OpenCodeVersionsScreen` without a title; its default was OpenCode versions | Now `ReportScreen` with required explicit title; Agent Context heading/capitalization corrected, failed inspection is visibly unverified |
| Remote failure hides inventory (fixed in UP-02) | At UP-00, CLI and TUI queried npm before enumerating environments | Shared `versions_report` retains independent source results and per-row errors; CLI stderr/exit 2 and TUI error notice keep partial failures visible |
| Base coordination is too narrow | `core.lock` stores locks below the chosen data directory; `update_base`, `rollback_base` and `core.base_tag_lock` use it for shared tags | One daemon-scoped lock namespace for builds, swaps, rollback, cleanup and base-based creation |
| Cleanup does not guard all base copies | `cleanup._classify_image` guards build candidates, but not rollback copies | Cover candidates, rollback copies and relevant replaced images; recheck identity/eligibility under shared guards |
| Rollback guesses wrong order | `rollback_base` maximizes Docker image creation time | Explicit choice among distinct copies, immutable identity and current-definition verification |
| Diagnostic calls can hang | `core.call` has no execution deadline; version probes use it; worker cancellation does not stop arbitrary child work | Bounded short diagnostics, owned/reaped clients and bounded or cleaned container-side probes |
| Obsolete image advisories linger | `_show_image_checks` posts warnings, but successful image checks do not clear prior image notices/status | Replace/clear the category on new evidence without overwriting active operation progress |
| Versions is only a report | It queries npm on opening, lists running-environment versions, and offers only Close | Compact Updates inventory/actions with independent component lifecycles |
| No manager discovery/updater | Version source and manual pipx instructions exist; no installation classification or handoff | Published-release discovery and verified official-tag pipx execution after earlier stages |
| No update-discovery cache | `latest` queries npm each time; readiness cache is separate and is not structured version history | Disposable observations/discovery, not authoritative environment-state additions |
| Current latest/policy semantics differ | npm latest is refused if outside 2.x; Manual/Pinned hide newer-version comparisons | Latest supported stable resolution and explicit comparisons without weakening policy enforcement |
| No full-refresh product option | `core.build_image` supplies neither pull nor no-cache; `core.build` discards a replaced base when Docker permits | Explicit cached versus full refresh; TUI replacement preserves rollback |

Keep the working mechanisms: semantic comparison and major refusal, one shared container install
script, disabled OpenCode self-update, candidate image verification, environment checkpoints and
journals, pin checks, exact recovery handlers, snapshots and ownership/rootless checks. Existing
pipx lifecycle and data-retention evidence is in BASELINE; it does not verify the new updater.

Relevant code: [versions](../../../src/opencode_sandbox/opencode_versions.py),
[core](../../../src/opencode_sandbox/core.py), [CLI](../../../src/opencode_sandbox/cli.py),
[TUI](../../../src/opencode_sandbox/tui.py),
[management screens](../../../src/opencode_sandbox/management_tui.py),
[cleanup](../../../src/opencode_sandbox/cleanup.py),
[readiness](../../../src/opencode_sandbox/readiness.py),
[worker adapter](../../../src/opencode_sandbox/tui_runtime.py),
[preferences](../../../src/opencode_sandbox/preferences.py),
[distributions](../../../src/opencode_sandbox/distros.py).

## Approved design

### Interface and component boundaries

Rename Versions to Updates; retain `v`. Use three compact tabs/subviews, not three large stacked
tables: **Sandbox Manager**, **Base Images**, **Environment OpenCode**. Show summary, selected
item and primary actions at 80x24; disclose IDs, provenance, times, checkpoints and full errors
through Details or confirmation screens. Keep keyboard focus/navigation and Cancel-first consent.

| Area | Summary | Actions when meaningful and eligible |
|---|---|---|
| Sandbox Manager | Installed version, installation classification, published release availability | Check releases, Update, release information/manual guidance |
| Base Images | Local image, base OS provenance, definition status, embedded OpenCode, freshness limitations | Check, Build/Rebuild, Rollback |
| Environment OpenCode | Identity, actual container state, observed/last-verified version, time, policy, recovery status | Check, explicit Start, Update, Policy, Rollback, Recover |

Separate version Check from the dashboard's comprehensive readiness Check. A disabled action
explains why; a confirmation names the exact component, target, affected state and recovery.
Render partial results while independent checks finish. No Update All or implicit cross-component
operation. Manager update does not build images; base rebuild does not migrate environments.

Use a generic read-only report component with required explicit title. Agent Context's heading
is `Agent Context — NAME`; preserve the content and show when observation fell back to saved
configuration. Readiness and cleanup reports use their own titles. Missing observation is not
proof that persisted guidance is stale.

### Evidence, discovery, operation state and feedback

Keep three categories distinct: installed/observed facts; remote discovery/cache; current
operation/recovery state. Reuse shared observations, comparisons, target validation and action
eligibility between CLI/TUI. Extend `opencode_versions.py` and established handlers; add focused
manager-discovery/installation/handoff code as needed. Do not reuse the settings change planner
as a universal update executor or parse human readiness strings into version evidence.

An observation records value, evidence source, time and object identity. Build labels describe
the base, not a derived environment's current binary. A never-created environment has no verified
installed version. Historical completed-update metadata is not a substitute for present runtime
verification. Tie observations to environment/container/image identity and invalidate or qualify
them after replacement, rollback, restore, failed/interrupted update or observed identity change.
Failed probes may retain dated historical evidence, never fresh verification. External changes
cannot be excluded by a cache; use honest last-verified wording.

Store caches outside authoritative metadata. Invalid/missing caches must not block ordinary
operations. Persist success and most recent failed attempt separately; retain source/time/stale
qualification. Publish local inventory independently of npm, GitHub or Docker errors wherever
local information exists. Preserve explicit-check failures and relevant CLI error semantics.

| State | Required meaning |
|---|---|
| Never checked | Availability not checked; do not imply current |
| Checking | Retain installed/local information and show progress |
| Up to date | No newer supported release found, with discovery time |
| Update available | Exact observation/installed value and target; identify affected component |
| Offline/temporarily unavailable | Keep local facts and visibly dated cached discovery |
| Check failed | Explain timeout, TLS, HTTP, rate limit or invalid response; not every failure is offline |
| Updating | Truthful phase and guarded conflicting actions, not invented percentage |
| Verified success | Verified installed result and final stopped/application state |
| Failed/partially completed | State what changed and whether rollback completed |
| Recovery required | Persistent reason and the appropriate existing recovery action |

Opening Updates does not implicitly query the network. Existing Docker-free metadata refresh
stays Docker-free. Automatic discovery defaults off; the user may enable background metadata
checks while the dashboard runs, with no persistent service. At most one attempt per source per
24 hours, including failure; persist attempts so restarts cannot turn failures into a request
loop. Coalesce in-flight work and share npm results across bases/environments. Explicit Check may
refresh sooner, but respects Retry-After/rate limits. No checks per short CLI command, automatic
installation or repeated per-environment toasts. One quiet deduplicated indicator is preferred.
Automatic discovery does not start containers or run image-verification helpers.

Replace/clear obsolete advisory categories after new evidence, without erasing another category
or an active mutation's progress. Acknowledge stale discovery rather than showing it as current.

### OpenCode version resolution and policy

Use host-side bounded npm metadata, no host npm/Node. Resolve the latest compatible stable
release (currently 2.x) even when npm latest moves to another major. Exclude prereleases from
default selection. Explicit compatible versions remain available; never install an unsupported
major. Strictly validate versions and compare precedence, not strings. Resolve a concrete target
before confirmation and revalidate it; never replace the confirmed target with a later release.

| Policy | Unsolicited newer-version notices | Explicit comparisons | Execution |
|---|---|---|---|
| Notify | Allowed only according to enabled discovery preferences | Yes | Compatible explicit target |
| Manual | Suppressed | Yes | Compatible explicit target |
| Pinned | Suppress general newer-version notices; still expose pin mismatch | May show newer versions as information | Never change pin or bypass existing restrictions |

Changing policy/pin is a separate explicit action. An available-version display is not execution
eligibility. Preserve repair of a broken installation and truthful same-version/no-install results.

### Base images

Show local image identity, OS/build provenance, definition revision versus installed manager,
embedded OpenCode evidence and build information when available. Separate old definition, old
OpenCode and **upstream OS/package freshness not assessed**. Missing/unknown/newer labels are not
permission to overwrite or downgrade a base. Never infer ownership from its name alone.

- **Cached rebuild:** reuse eligible layers, applying the selected definition and exact OpenCode
  target; it does not guarantee fresh OS packages. Definition/cache invalidation can rerun layers.
- **Refresh & Rebuild:** retrieve current upstream inputs and rebuild package layers without stale
  cache, equivalent to pull plus no-cache. Explain network/time costs; never prune shared cache.
- Default proposed OpenCode target is the latest supported stable version, exact before consent;
  permit an explicit compatible alternative. No persistent base-version policy infrastructure.
- TUI replacement of an existing base uses the rollback-preserving path. Retain current CLI
  capabilities; an operation deliberately keeping no copy must disclose that distinction.
- Confirm existing image identity, exact target, definition and refresh mode. Build a separate
  candidate; verify before publication; recheck confirmed identity under publication guard and
  refuse unexpected change. Preserve the replaced image when applicable. Report failure or an
  unchanged build accurately; cleanup only the operation's own candidate/resources.
- Existing containers, writable layers and retained OS do not change. Explain effects on future
  base-based creation, not-yet-created pinned environments and file-only restores. Preserve pin
  enforcement and current-definition rollback verification; do not reapply initial integrations.
- Rollback inventories managed copies and consolidates aliases for one image. One distinct copy
  can be selected automatically; several require explicit choice, including noninteractive CLI.
  Confirmation bypass does not choose a copy. Bind consent to immutable identity, revalidate and
  verify it, swap, and keep the replaced current image. Do not infer replacement order from
  creation time or discard legacy copies merely because their history is unknown.

Defer automatic upstream-digest notifications until trustworthy build-input provenance exists.
A changed digest is not necessarily a security update; an unchanged digest is not proof of fresh
packages. A full refresh is not bit-for-bit reproducibility or a security certification.

### Environment OpenCode

- Running: bounded runtime version query, without restart or interference with active sessions.
- Stopped: last verified observation plus time, or Unknown. Ordinary discovery never starts it.
- Never created: no runtime version is verified; do not pass off a creation-image label as one.
- Offer explicit Start for fresh verification; explain it remains running. No temporary
  start/probe/stop workflow. Do not introduce implicit Stop and Update.
- Update an eligible existing stopped network-enabled container only. Resolve exact target;
  explain network, temporary startup, checkpoint and final stopped state; confirm; revalidate
  state, ownership, policy and pending journal under its lock; use existing update/install/verify/
  stop mechanism. Do not change network settings or policy automatically.
- Reuse existing checkpoints, failure rollback and interrupted recovery. Expose eligible handlers
  in Updates/Recovery Center, not a parallel journal or recovery engine. Missing checkpoints and
  failed rollback name remaining safe actions; do not clear a journal based on a guess.
- Successful-update rollback restores the entire checkpointed system layer, with the present
  layer preserved as a snapshot first. Home/workspace data are not rolled back, and binary
  rollback does not reverse OpenCode data-format changes or promise backward compatibility.
- Preserve user OpenCode configuration, disabled self-update, one-time integrations, direct
  workspace checks and all existing lifecycle/ownership protections.

### Shared locking and owned subprocesses

Use a secure, deterministic user-private lock namespace outside product data/config overrides.
Base keys use own UID plus canonical verified daemon endpoint plus distribution, not context
alias, data directory or daemon PID. Lock location/ownership/symlink handling must fail safely;
never unlink/recreate a potentially held lock. Resolve the concrete namespace/fallback in UP-03
and demonstrate that participants using different data directories converge on the same file.

Two base guards: build (rebuild, rollback work and relevant cleanup) and short publication
(tag inspection/replacement, pin check and base-based container creation). Builds do not hold
publication throughout. All participants, including rollback-copy cleanup, use the shared guards.
Recheck image identity, ownership and eligibility under the guard, not just before taking it.

Acquire only needed levels, in this order:

```text
installation usage
-> data-directory coordinator, if needed
-> environment locks in stable ID order, if needed
-> daemon/distribution build guard, if needed
-> daemon/distribution publication guard
```

No path acquires an earlier level while holding a later one. Creation takes environment then
publication; rebuild/rollback takes build then publication. Cleanup takes relevant guards,
leaves busy resources alone with a reason and does not hold resources from previous items.
Base-held code must not call back into environment/coordinator acquisition. Discovery-cache
synchronization is independent and not held when acquiring mutation locks.

Installation usage/exclusive-update coordination is independent of selected data directories.
Supported other instances prevent manager replacement; exclude normal startup while replacing,
with narrow updater-owned read-only verification. Do not promise coordination with an older
manager or arbitrary external pipx/Docker command; warn and document that boundary.

Bound short diagnostic subprocesses/network calls, response sizes and cancellation waits. Keep
ownership of started clients and reap them; do not apply a blanket short timeout to build,
installation, commit or other legitimate long operations. Killing a Docker client may leave its
exec command running: bound container-side version probes or clean only their owned probe
resources. Handle helper containers left by timed-out image probes. A canceled Textual thread
does not mean its child or mutation stopped. Do not offer mutation Cancel without a tested
termination/recovery contract. Existing journals remain authoritative after interruption.
Capture/stream build output into bounded UI details rather than writing directly into Textual.

### Manager discovery, eligibility and self-update

Published full releases from the official GitHub repository are the availability source; ignore
drafts, prereleases and unpublished development. Strictly validate tags, compare versions and
never offer an implicit downgrade. The unchanged checkout version is not a new release.
No required GitHub login or credential use. Treat release metadata as data, not executable text.

Automatic execution supports only a verified pipx installation originating at the official
repository and a versioned release tag. Reconcile running package path, interpreter/venv,
distribution/VCS metadata, pipx's recorded environment/source, executable, actual launcher and
resolved target. Handle custom locations without guessing. Existing pipx on PATH proves nothing.
Editable/foreign/unsupported/ambiguous installations get accurate manual instructions, not
conversion or forceful takeover. Preserve recognized settings; if preservation cannot be proved,
report unsupported configuration rather than silently discard it. Do not install/switch Python.

1. Resolve published exact release/tag and expected source commit; show notes and impact.
2. Validate installation, external updater prerequisites and expected existing identity. Bind the
   confirmation to target and installation; refuse incompatible active mutations/attached sessions.
3. Record previous verified release/source and recovery steps outside the replaceable install;
   print instructions before replacement begins. No secret-bearing environment/metadata dumps.
4. Close Textual cleanly and restore terminal state. Hand off to a minimal self-contained stdlib
   helper independent of the replaceable environment and an external pipx executable, using argv.
5. Under installation-exclusive access, revalidate target/ownership and refuse unexpected changes
   or another supported live instance. No mutation is permitted merely because preflight passed.
6. Invoke the existing exact-tag pipx replacement mechanism; do not assume force protects the
   launcher or backs up the venv. Do not use plain pipx upgrade/reinstall as next-tag discovery.
7. Verify expected installed version/source/commit where available, actual launcher and basic CLI
   with fresh processes. Docker readiness is not an installation success condition.
8. Print concise verified success or actual failure state and restart/recovery command. Do not
   restart the dashboard automatically. Keep a small private recovery/result record when needed
   even if the application launcher is broken or the updater was interrupted.

Distinguish previous installation operational, target installed but verification failed, and
unavailable installation/launcher. Report partial change honestly. No elaborate automatic
rollback; reinstalling the previous Git tag is recovery guidance, not identical dependency
restoration or guaranteed offline recovery. The planning inspection of pipx 1.18.7 found force
can unlink a launcher and ordinary replacement need not preserve a backup; verify actual behavior
in isolated integration tests, not through assumptions about a successful return code.

## Implementation tasks and dependencies

All tasks below are pending except UP-00..UP-02. Stage order is mandatory; within correctness,
complete one focused task per cycle. Dependencies are technical prerequisites, not permission to run extra
tasks in a cycle. Split an oversized task into documented subcycles without changing scope.
Every task must reproduce the defect where applicable, add regressions, rerun affected tests,
review the diff and update user/engineering documents with actual behavior and evidence.

Priority stages: UP-01..UP-06 correctness first; UP-07..UP-09 shared observations/discovery;
UP-10..UP-12 Updates UI and existing actions; UP-13 base refresh; UP-14..UP-17 manager updates.
UP-18 consolidates evidence without preparing a release. UP-00..UP-02 are DONE; all other
tasks are PENDING. The next unblocked task is UP-03 only.

| ID | Stage / task | Prerequisites | Acceptance and minimum focused verification |
|---|---|---|---|
| UP-00 | DONE: persist approved plan | Owner approval | Documentation-only commit `3552f67`; decision/status links, complete scope/dependencies/test gates and resume record |
| UP-01 | DONE: generic report and Agent Context heading | UP-00 | Explicit titles for all report callers; consistent Agent Context labels/fallback wording; pilot regressions for Agent Context, Versions, readiness and cleanup, including 80x24; evidence below |
| UP-02 | DONE: preserve inventory on remote failure | UP-00 | CLI/TUI local rows survive npm failure; per-item errors isolated, explicit check failure still reported; offline/partial-result regressions without starting containers; evidence below |
| UP-03 | Shared base coordination | UP-00 | Secure shared namespace, lock ordering and build/publication guards cover build/swap/rollback/cleanup/creation; multiprocess host and real-Docker race tests across data directories/context aliases |
| UP-04 | Explicit base rollback selection | UP-03 | Alias consolidation, one-copy default, multi-copy explicit selection, immutable consent and definition verification; cached-build/downgrade/tie/changed-or-missing-copy regressions and real swap preservation |
| UP-05 | Bounded diagnostic execution | UP-00 | Network/short subprocess deadlines and owned cleanup/cancellation; container-side probe bounds; long builds/updates not assigned short diagnostic limits; real local-process/pilot and scoped Docker leak checks |
| UP-06 | Clear obsolete advisories | UP-00 | Warning-to-success/unknown/new-warning transitions replace the right category and preserve busy state; readiness/image pilot regressions |
| UP-07 | Shared local observations | UP-01..UP-06 | Structured source/time/identity, disposable cache, stopped history/Unknown, lifecycle invalidation and partial Docker results; unit/host and lifecycle regressions |
| UP-08 | Compatible discovery and policy comparisons | UP-07 | Bounded npm lookup/caching; latest supported stable despite another-major latest; exact confirmed targets; Manual/Pinned explicit comparisons; shared CLI/TUI eligibility and error tests |
| UP-09 | Opt-in background discovery | UP-08 | Off by default; per-source attempt-based 24-hour bound across restart/failure, coalescing, rate limits and quiet deduplication; no start/probe/update side effects; cache/preferences/pilot tests |
| UP-10 | Compact Updates inventory | UP-09 | Three subviews, local/cached first, independent loading/errors, selected Details, focus/navigation at 80x24 and larger; manager execution not exposed prematurely; pilot and real-terminal checks |
| UP-11 | Environment actions and recovery | UP-10 | Existing Check/Start/Policy/Update/Rollback/Recover handlers with exact consent and locked revalidation; pin/network/running-state refusals, stopped final state and recovery; real Docker/OpenCode and terminal tests |
| UP-12 | Base actions using existing safe lifecycle | UP-10, UP-03, UP-04, UP-08 | Inventory and cached Build/Rebuild/Check/Rollback, preserving replacement and exact target/state consent; CLI/TUI parity, pinned-creation and retained-layer regressions |
| UP-13 | Full base refresh | UP-11, UP-12 | Explicit cached versus Refresh & Rebuild in CLI/TUI, pull/no-cache without prune, candidate failure safety; both distributions built under isolated test tags; existing containers/layers unchanged |
| UP-14 | Manager release discovery | UP-13 | Bounded official published-full-release provider, strict tags/semver/no implicit downgrade; manager UI/CLI discovery and optional daily source integration; local inventory survives GitHub failure |
| UP-15 | Verified installation classification | UP-14 | Actual official-tag pipx identity including custom paths, interpreter/source/launcher; safe manual guidance otherwise; real isolated pipx classification and foreign/shadowed launcher tests |
| UP-16 | Installation exclusion and terminal handoff | UP-15, UP-05 | Supported instances coordinate across data directories; safe self-contained helper/interpreter/external pipx, clean TUI exit before mutation, startup exclusion and narrow verification path; process and pty tests |
| UP-17 | Manager replacement, verification and recovery | UP-16 | Exact confirmed target and revalidation, actual fresh-process verification, failure classes/recovery record/instructions, no automatic restart; isolated pipx success/failure/interruption plus real terminal evidence |
| UP-18 | Cross-layer verification and record consolidation | UP-01..UP-17 | Run affected/full regressions, required real combinations, dependency endpoints, docs/CLI/packaging checks; record evidence/limits, promote durable facts and retire the effort record when complete; no release work |

No implementation task is complete because it appears in this table. Manager scope is included
now, but must not delay UP-01..UP-13. Do not add predicted commands/options to user-facing docs
before they exist. Preserve existing CLI paths; add only necessary manager/refresh/copy-selection
capabilities and validate their final names/help through the existing CLI-structure tests.

## Verification matrix

| Layer | Required scenarios / existing starting coverage |
|---|---|
| Unit / mocked Docker | Version parsing/semver/unsupported major/prereleases; latest compatible resolver; per-source/per-row failure; malformed/oversized HTTP; cache expiry/corruption and future times; rate limits, duplicate work, default-off; all policy/eligibility branches. Start with `test_opencode_versions.py`, `test_opencode_lifecycle.py`, `test_image_readiness.py`, `test_readiness.py`, `test_hardening.py`, `test_cleanup.py` |
| Host files / processes | Cross-data/config-directory locks, aliases, order and busy paths; no symlink/permission takeover; candidate/copy identity changes; diagnostic timeout/cancel reaping; no inherited lock descriptors blocking shutdown; installation classification and exclusive access; reuse real-process testing patterns |
| Textual pilot | Explicit report titles, offline local inventory, partial loading, obsolete notices, keyboard/focus/Cancel defaults, disabled reasons, exact-target consent, opening without network, preferences/deduplication; 80x24 and larger. Extend `test_tui.py`, image/readiness/cleanup/recovery screen coverage |
| Real Docker | Both distributions; build/publish/creation/rollback/cleanup races from separate data directories; cached/full refresh; failed candidate retains old base; selected copy preserved; pinned creation; retained OS and writable layers; stopped checks cause no start; no leaked probe/helper resources |
| Real OpenCode | Version verification, repair/same-version outcomes, update failure/checkpoint/recovery, rollback snapshot and stopped final state; policy/network-none refusals; user config/integrations retained. Extend `integration/test_30_faults.py`, `test_40_opencode.py`, `test_80_combinations.py` and retained-OS coverage |
| Isolated pipx / package | Official-origin classification using controlled fixtures; custom locations, missing/incompatible tools/Python, editable/foreign/ambiguous/shadowed launchers, unsupported settings; replacement and data retention; failure before/during/after install, source/version/launcher mismatch, lost terminal and interrupted helper. Extend `integration/test_65_pipx.py` and installed-package smoke/asset coverage; do not touch the user's application |
| Real terminal (pty) | Updates at 80x24/larger, actual responsive progress and confirmations; terminal restored before manager replacement, exit/failure/restart guidance, no automatic dashboard restart; follow `integration/test_50_tui.py` and host terminal patterns |
| Static / docs / compatibility | Existing English, link/anchor, CLI/options/help, quality and package checks; Python 3.11/3.14 and lowest/current direct dependencies as appropriate; no unsupported claims from mocked/skipped evidence |

Run from lower to higher risk, with existing fixtures/campaign instead of a new CI framework.
Use isolated product/pipx homes and `.work/` logs/artifacts, short external basetemp, absolute
PYTHONPATH and serial foreground unit runs as BASELINE describes. Real resources require
`ocs-test-*` names, labels where supported, a manifest, guarded product cleanup and leak checks.
Use test-only image namespaces; do not replace/delete existing user bases or rollback copies.
Apply current machine permissions before real/privileged rows; approval of the architecture is
not new permission for services, credentials, paid calls, host setup or publication. Never run
OpenCode V2 on the host. Do not suppress failing tests or claim skipped layers passed.

Each task records exact commands, interpreter/dependencies, counts, failures/reruns, skipped or
unexecuted layers and resource outcomes. Update BASELINE/CAMPAIGN only with actual evidence,
keeping historical release PASS separate. Update README/user guides/Unreleased as actual changes
land; do not announce planned functionality as delivered in this documentation-only cycle.

## Rationale, rejected alternatives and retained limitations

- One screen is discoverable; independent executors preserve proven recovery/data boundaries.
  Reject Update All, universal update engines and an update use of the settings-change planner.
- Manual-first discovery avoids unexpected traffic. Reject forced startup checks, retry loops,
  per-environment pop-ups and persistent background services. An opt-in daily attempt is enough.
- Dated stopped observations are honest and nonintrusive. Reject deriving installed facts from
  labels/package files or automatically starting stopped environments just for a version query.
- Explicit base-copy selection removes creation-time ambiguity without a new history service.
  Replacement-order persistence was considered but is unnecessary for this iteration.
- Full refresh is explicit and local-build based. Reject cache pruning as the product workflow,
  automatic upstream-digest notices without provenance, base-policy infrastructure and claims of
  reproducible/security-certified freshness. Existing upstream package drift remains possible.
- Scoped short diagnostic bounds do not become blanket mutation deadlines. Reject treating a
  canceled worker/client as proof that container-side work finished.
- Manager handoff is a small pipx client, not a general package manager, installer or host wizard.
  Instructions-only self-update was considered; the owner explicitly requires verified execution
  in this effort. Reject modifying a running TUI's environment, automatic restart/rollback,
  unsupported-install conversion, launcher takeover or interpreter installation.
- No artifact signing/trust infrastructure is added. Official HTTPS/release/tag/source checks
  retain the existing distribution trust model; they are not cryptographic code attestation.
- npm can publish its main package before platform packages. Discovery is not installability;
  fail cleanly, preserve the old image/checkpoint and suggest retry or an explicit version.
- An environment rollback is system-layer recovery, not home/workspace recovery or guaranteed
  OpenCode data compatibility. Existing base rollback against the current OS definition remains.
- Labels/locks are not protection against a hostile process with the same user's daemon access.
  New locks do not coordinate older managers/manual Docker or external pipx. Existing cleanup
  limitations for daemon-shared rollback copies across data directories remain explicit.
- No environment migration, user-owned configuration reapplication, schema migration, channel
  change, additional host support claim, release-readiness claim or release permission follows.

## Risks and remaining implementation questions

No unresolved product decision blocks UP-03. The following are implementation proofs to resolve
in the named task, not permission to reopen settled UX or add infrastructure. If evidence needs
a materially different architecture, record the blocker and ask the owner before proceeding.

| Risk / question | Resolve in | Required proof or safe fallback |
|---|---|---|
| Secure shared lock root on hosts with/without a usable runtime directory | UP-03 | Deterministic convergence outside product overrides, ownership/no-follow checks, no split namespaces; test aliases/restarts and document legacy-manager limits |
| Scope/order of base cleanup guards and publication identity checks | UP-03/UP-04 | Enumerate all participants; multiprocess races and failed/changed inspect must not authorize deletion/publication |
| Container-side probe deadline tools and cleanup on missing/custom tooling | UP-05 | Never start stopped environments; own/reap only diagnostic resources, fail as unavailable/Unknown instead of weakening checks |
| Cache location, invalidation and compatible npm metadata size | UP-07/UP-08 | Disposable bounded data; independent sources; policy/version semantics; no readiness-string parsing or metadata migration |
| Daily throttle across failure, restart, time changes and overlapping callers | UP-09 | Attempt-based persistence, rate-limit handling, no network flood; explicit checks remain usable |
| Exact manager command names and small CLI help integration | UP-14..UP-17 | Preserve existing capabilities, share handlers and validate every documented command/option before user docs name it |
| pipx metadata/version/configuration variants and tag/commit identity | UP-15 | Test supported variants; refuse ambiguous ownership/unsupported preservation with accurate manual guidance |
| Early usage lease, helper independence and verifier access under exclusive update | UP-16 | No normal manager mutation/startup during replacement; other supported instances block; no deadlock in fresh verification, inherited descriptor leak or reliance on replaced imports |
| pipx partial replacement and helper/terminal interruption | UP-17 | Recovery guidance exists before mutation and outside the venv; classify actual result; no guaranteed backup/automatic rollback assumption |
| Real matrix permissions, tooling or network unavailable | Each task | Mark that layer unexecuted/BLOCKED with cause and reproducible next step; do not promote old PASS or change user resources to make it pass |

## Progress and checkpoint evidence

### UP-00 — 2026-10-30 — documentation-only checkpoint

- Re-read instructions, permanent records and relevant implementation. Starting Git tree was
  clean, on `main` at `a20f1fc`; no later code invalidates the approved architecture. Created
  `work/updates`; no remote operations. This document, TODO and D-056 capture the approved design;
  BASELINE/ARCHITECTURE explicitly keep current and planned behavior separate.
- Read-only daemon reconciliation: own rootless identity verified; zero containers and zero
  volumes at observation. Retained Debian base has revision 1/OpenCode 2.2.0; Arch base revision
  1/OpenCode 2.2.0. This matches the retained-base limitation, not a reason to rebuild in this
  cycle. No Docker resources were created, changed or deleted; no cleanup was needed.
- Documentation/CLI-structure subset: **27 passed, no skips**, Python 3.11.18, pytest 9.2.0,
  Typer 0.27.3, Textual 8.2.8. This checks English, links/anchors (including this working record),
  existing CLI/help and documentation consistency; Docker is mocked in the tests. Command:

  ```sh
  PYTHONPATH="$PWD/src" .work/venv311/bin/python -m pytest -q \
    tests/test_language.py tests/test_user_docs.py tests/test_cli_structure.py \
    --basetemp=/tmp/opencode/up00.TBtw1c
  ```

- `git diff --check`: clean. Reviewed the new roadmap and changes to TODO, DECISIONS, BASELINE
  and ARCHITECTURE. Product code/tests/assets/version remain unchanged. No new implementation
  regression, real Docker mutation, real OpenCode, pipx update, full unit suite, Python 3.14
  suite, real-terminal or manual UI verification is claimed by this checkpoint.
- Planned local commit: `docs: persist approved Updates implementation roadmap`. Resolve its
  actual hash from Git when resuming; do not rewrite this record merely to embed its own hash.
- UP-00 completes with that documentation-only commit. **STOP.** All implementation tasks remain
  pending; the next cycle is UP-01 only.

### UP-01 — 2026-10-30 — generic report and Agent Context presentation

- Recovered the instructions, full roadmap, current-state records and clean `work/updates` at
  UP-00 `3552f67`. Read-only daemon reconciliation matched UP-00: verified own rootless identity,
  no containers/volumes, retained Debian/Arch bases revision 1 with OpenCode 2.2.0. No later work
  invalidated the plan. Local instructions' old "no running effort" snapshot is superseded by
  TODO and this record; its permissions remain unchanged.
- Reproduced the heading defect with a pilot assertion at 80x24: both no-container and failed
  observation paths displayed `OpenCode versions (no automatic updates)` instead of
  `Agent Context — NAME` (2 failures before the patch). A second reproducer saved valid observed
  Debian 12/network-none guidance, then made inspection fail: the configuration-only comparison
  incorrectly called the saved guidance missing/outdated (1 failure before the patch).
- Root cause: four unrelated reports shared a versions-named modal with an implicit title.
  Agent Context also hid its observation fallback and compared that preview against the file
  as though it had fresh container evidence. All four callers (Versions, Agent Context,
  readiness and cleanup) now use `ReportScreen` with a required explicit keyword title and
  plain-text heading. Existing report contents, scrolling and Close/Esc remain available.
- Agent Context heading, action label, binding description and body use consistent capitalization.
  A failed observation now displays its reason and configured-settings fallback, with an
  unverified on-disk status; it does not run the misleading comparison. Successful inspection
  keeps the current/missing-or-outdated comparison. Preview remains read-only and never starts
  a container; generation, CLI verification and lifecycle behavior are unchanged.
- Added pilot regressions for observed/missing/offline/current/outdated guidance, saved-file
  preservation, all caller titles including failure results, required explicit title, literal
  markup, long heading, keyboard scrolling/focus/Close/Esc, hidden dashboard keys and 80x24/larger
  layouts. The existing readiness and cleanup workflow tests now assert their report subjects.
- Early test correction: the first focused run was 89 passed/4 failed because the new test
  assumed a public `Static.markup` property; the second had the same counts because it used an
  unbound Ctrl+End key. Inspected Textual's bindings/API; assert literal rendered content and use
  Page Down instead. All four scrolling/closing cases passed after correction; no product
  behavior was relaxed to satisfy these test mistakes. Final runs below pass those cases.
- Verification (serial foreground runs, absolute PYTHONPATH, isolated paths, pytest 9.2.0):

  | Run | Result |
  |---|---|
  | Full suite, Python 3.11.18, Typer 0.27.3, Textual 8.2.8 | **982 passed, 56 opt-in skips**, 90.56 s; unit/mocked Docker, real host files/Git/local processes and existing host terminal fixtures |
  | Affected subset, Python 3.11.18, Typer 0.16.0, Textual 4.0.0 | **198 passed, no skips**, 54.82 s |
  | Affected subset, Python 3.14.8, Typer 0.27.3, Textual 8.2.8 | **198 passed, no skips**, 56.37 s |
  | Affected subset, Python 3.14.8, Typer 0.16.0, Textual 4.0.0 | **198 passed, no skips**, 54.70 s |
  | Final affected subset including updated records/illustration, Python 3.11.18, Typer 0.27.3, Textual 8.2.8 | **198 passed, no skips**, 56.06 s |

  The lowest-dependency runs emitted only the two already documented Typer/Click deprecations.
  The full-suite skips are the real-campaign, privileged and socket-activation opt-ins, not
  waived failures. Ruff/shellcheck, language, document/link/anchor and CLI-structure checks are
  included. Commands (the subset uses each named venv and a distinct short basetemp):

  ```sh
  PYTHONPATH="$PWD/src" .work/venv311/bin/python -m pytest -q \
    --basetemp=/tmp/opencode/up01-full311
  PYTHONPATH="$PWD/src" .work/venv311low/bin/python -m pytest -q \
    tests/test_tui.py tests/test_readiness.py tests/test_cleanup.py \
    tests/test_agent_context.py tests/test_tui_text.py \
    tests/test_image_readiness.py tests/test_quality.py tests/test_language.py \
    tests/test_user_docs.py tests/test_cli_structure.py \
    --basetemp=/tmp/opencode/up01-low311
  ```

  Repeat the second command with `.work/venv314/bin/python` and basetemp
  `/tmp/opencode/up01-current314`, and with `.work/venv314low/bin/python` and basetemp
  `/tmp/opencode/up01-low314`, for the two 3.14 results above. The final repeat uses
  `.work/venv311/bin/python` and `/tmp/opencode/up01-final311`.
- README, dashboard/OpenCode guides, Unreleased, architecture, baseline, campaign qualification
  and TODO now describe only the delivered correction. Regenerated `docs/images/dashboard.svg`
  with `PYTHONPATH="$PWD/src" .work/venv311/bin/python tests/dashboard_screenshot.py
  docs/images/dashboard.svg` (fake data, not a manual UI observation).
- Reviewed the product/test/document diff and the regenerated SVG's text changes (Agent Context
  capitalization plus fresh fake IDs/time). All four report callers supply explicit titles;
  no versions-specific component/IDs or inconsistent Agent Context labels remain in source.
  `git diff --check` is clean; static gates required no exclusions or suppressions.
- Final documentation-only rerun after the evidence updates: **27 passed, no skips** (5.45 s),
  `.work/venv311/bin/python -m pytest -q tests/test_language.py tests/test_user_docs.py
  tests/test_cli_structure.py --basetemp=/tmp/opencode/up01-docs-final` with absolute PYTHONPATH.
  The ending read-only daemon check again found no containers/volumes and the same base image IDs.
- Not re-established: report-specific real-terminal/manual observation, real Docker mutations,
  real OpenCode, package build or isolated pipx updates; full 3.14/lowest suites were not run,
  only the affected subsets. No mutation or version-discovery behavior changed. Recheck the
  live-terminal reports during UP-18; do not count historical campaign PASS as new evidence.
- No Docker resource was created, changed or deleted; no cleanup was needed. No image assets,
  schemas, manager version, CLI commands or policy semantics changed. Planned local commit:
  `fix: give dashboard reports explicit subject titles`. Resolve its actual hash from Git.
- **UP-01 is complete; STOP after its local commit. Next: UP-02 only.** Remote failures still
  hide version inventory; that defect is deliberately not fixed in this report-only cycle.

### UP-02 — 2026-10-30 — preserve inventory across discovery failures

- Recovered instructions, roadmap/current-state records and clean `work/updates` at `d7d6a1f`.
  No intervening changes invalidated the design. Read-only daemon inventory again matched UP-01:
  own rootless identity verified, zero containers/volumes, retained Debian/Arch revision-1 bases
  with OpenCode 2.2.0. No Docker mutation was needed for this task.
- Minimal reproducer: three local environments (running, stopped and not created), fake Docker
  and an npm failure. Both CLI and 80x24 pilot tests failed before the patch: CLI stdout was
  empty and TUI showed only the registry error; the event trace never reached local inspection.
  Root cause was the registry-first shared failure scope, not missing local metadata.
- Added `opencode_versions.versions_report`: a small read-only composition of existing local
  inventory, lookup and row formatting. Local collection comes first; the optional registry
  lookup and each row have separate failure boundaries. It returns available lines and explicit
  errors, with source/row identity and `core.error_text` preserving unexpected exception types.
  It neither replaces an updater nor introduces observations, cache persistence or schema fields.
- CLI and TUI now share this report. CLI available rows stay on stdout, errors go to stderr and
  a failed/partial report exits 2, including failed environment rows that previously could exit
  0. The dashboard shows lines and errors together with its failure notice and retains UP-01's
  explicit Versions title. Successful discovery is labelled `npm registry` consistently in both
  interfaces. No failure is presented as current or update available without a comparison target.
- Expanded per-environment isolation to malformed policy values and ordinary unexpected errors;
  one bad row cannot discard healthy rows. Stopped/not-created inspection stays nonintrusive,
  no-check CLI never calls npm, and existing Notify/Manual/Pinned comparison behavior is retained.
  Updates, policy changes, checkpoints, ownership/rootless checks and user configuration are untouched.
- Regression coverage: 32 new inventory cases in `tests/test_version_inventory.py` use mocked
  Docker/npm and real isolated metadata. Cover offline, timeout, HTTP/rate-limit and malformed
  response errors, unexpected source errors, failed local source with successful/failed registry,
  malformed policy, ownership refusal, formatting failure, stdout/stderr/exit status, empty data,
  unchanged metadata, no stopped/created startup, policy comparisons, and 80x24 pilot results/Esc.
  Existing Versions pilot expectations now require surviving rows after registry failure.
- Static review initially flagged four broad report catches (BLE001). Keeping broad isolation at
  this read-only boundary preserves the TUI's prior protection against unexpected row failures,
  instead of narrowing catches merely to appease the linter. Added four local, reasoned BLE001
  annotations, following the module's existing error-reporting convention; no blanket config
  exclusion. Extended the existing AST quality gate to `opencode_versions.py`: every broad catch
  must report its exception through `core.error_text`. Unexpected-source/row tests prove typed
  visible errors, not swallowed failures. Ruff and the quality suite pass with that contract.
- Verification, serial foreground, pytest 9.2.0 and absolute PYTHONPATH:

  | Run | Result |
  |---|---|
  | Full suite, Python 3.11.18, Typer 0.27.3, Textual 8.2.8 | **1015 passed, 56 opt-in skips**, 99.05 s; mocked Docker, unit/host/files/Git/local-process and existing host terminal fixtures |
  | Affected subset, Python 3.11.18, Typer 0.16.0, Textual 4.0.0 | **220 passed, no skips**, 60.54 s |
  | Affected subset, Python 3.14.8, Typer 0.27.3, Textual 8.2.8 | **220 passed, no skips**, 61.51 s |
  | Affected subset, Python 3.14.8, Typer 0.16.0, Textual 4.0.0 | **220 passed, no skips**, 59.41 s |
  | Final subset including updated engineering records, Python 3.11.18, Typer 0.27.3, Textual 8.2.8 | **220 passed, no skips**, 67.11 s |

  Lowest-dependency runs emitted only the two documented Typer/Click deprecations. Skips in the
  full suite are the real-campaign, privileged and socket-activation opt-ins, not waived failures.
  Earlier focused runs also passed (109 cases, then 129 after expanding the failure matrix).
  Commands for the full suite and affected subset:

  ```sh
  PYTHONPATH="$PWD/src" .work/venv311/bin/python -m pytest -q \
    --basetemp=/tmp/opencode/up02-full311
  PYTHONPATH="$PWD/src" .work/venv311low/bin/python -m pytest -q \
    tests/test_version_inventory.py tests/test_opencode_versions.py \
    tests/test_opencode_lifecycle.py tests/test_tui.py tests/test_quality.py \
    tests/test_cli_robustness.py tests/test_prerequisites.py tests/test_language.py \
    tests/test_user_docs.py tests/test_cli_structure.py \
    --basetemp=/tmp/opencode/up02-low311
  ```

  The subset's other runs use `.work/venv314/bin/python` with
  `/tmp/opencode/up02-current314` and `.work/venv314low/bin/python` with
  `/tmp/opencode/up02-low314`; the final repeat uses `.work/venv311/bin/python` with
  `/tmp/opencode/up02-final311`. Static, language, document links/anchors and CLI checks are included.
- Updated README, dashboard/OpenCode guides, command help, Unreleased and the engineering records
  for delivered behavior. No new commands/options, manager version, image definition or schema.
  Planned local commit: `fix: preserve version inventory when discovery fails`; resolve its actual
  hash from Git. No push, merge, release preparation, tag, publication or uploads are authorized.
- Reviewed the product/test/document diff, including the new inventory tests. Whitespace checks
  are clean. Compared unchanged version/image assets/core/runtime-identity/cleanup and workflow
  paths with UP-01. The ending read-only daemon inventory again has no containers/volumes and
  the same base image IDs as the start; no user resource was touched.
- Final documentation-only check: **27 passed, no skips**, 5.47 s, Python 3.11.18; command
  `.work/venv311/bin/python -m pytest -q tests/test_language.py tests/test_user_docs.py
  tests/test_cli_structure.py --basetemp=/tmp/opencode/up02-docs-final` with absolute PYTHONPATH.
- Not re-established: report-specific real terminal/manual observation, live npm discovery or
  outage, real Docker/OpenCode, package build or pipx update. Existing loopback HTTP tests exercise
  the unchanged lookup locally, not the public npm service. Full 3.14/lowest suites were not run,
  only affected subsets. Short local diagnostics remain unbounded until UP-05, and progressive
  partial rendering/observations/caching remain later tasks; this report appears after the attempts.
- No Docker resources were created, changed or deleted; no cleanup was needed. **UP-02 complete;
  STOP after the local commit. Next: UP-03 only**, shared daemon-wide base coordination.

## Resume and context-compaction handoff

1. Read repository/local instructions, TODO, BASELINE, D-056 and this entire record. Use
   ARCHITECTURE for implemented behavior, not proposed functionality. Check Git status, branch,
   log and scoped Docker state; preserve unfamiliar changes and reconcile them before editing.
2. Expected branch: `work/updates`, UP-00 `3552f67`, UP-01 `d7d6a1f`, then the UP-02 commit.
   Product changes so far are limited to `tui.py`, `cli.py` and `opencode_versions.py` reports,
   plus related tests/documents. Image assets, manager version and schemas still match the seed.
   Resolve the latest actual commit from Git; later checkpoint evidence takes precedence.
3. Select **UP-03 only**: inventory the base lock participants in `core.py`, `opencode_versions.py`
   and `cleanup.py`, including build/tag replacement, rollback-copy/candidate cleanup and pin
   checking/container creation. Reproduce cross-data-directory divergence, then implement the
   approved secure user-private daemon/distribution build/publication guards outside product
   overrides and prove the lock order. Include host multiprocess tests and scoped real-Docker
   races using test-only tags and a resource manifest; preserve existing bases/copies. Resolve
   namespace/fallback safety from evidence. Do not also implement explicit rollback selection,
   diagnostic deadlines, observations/caching or the full Updates interface in that cycle.
4. Follow task-local reproducer -> root cause -> narrow patch -> regression -> rerun. Update user
   docs and current-state records only for what actually changed; record exact evidence and
   outstanding layers here, with any needed new decision entry rather than editing history.
5. Review/stage only intended changes; commit locally. Record task status, test results, blockers
   and the next unblocked task in this file before committing, so the commit is self-contained.
   Leave a clean checkpoint, summarize the actual commit/tests/limitations, then STOP.
6. Never infer permission to merge, push, tag, publish, bump the version or start release work
   from Continue, task completion, passing tests or the end of this roadmap. Additional unrelated
   stabilization work is expected before a human separately considers another release.
