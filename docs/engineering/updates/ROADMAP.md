# Updates — approved architecture, implementation roadmap and handoff

## Status and authority

- **UP-00..UP-08 and PERF complete. Next: UP-10 + UP-09 (manual/cached UI first).**
  PERF measures/optimizes test-local repeated work, not product behavior or verification gates.
  UP-00 persisted the plan; UP-01 fixes report
  subjects/Agent Context presentation; UP-02 preserves independent local/registry inventory
  results; UP-03 implements shared base guards; UP-04 implements identity-bound explicit rollback
  selection; UP-05 bounds short diagnostics and owns client/probe cleanup; UP-06 replaces/clears
  category-owned advisories without erasing active progress; UP-07/UP-08 add identity-bound
  evidence, disposable caches, compatible stable resolution and exact targets/comparisons.
  D-057 consolidates the remaining
  packages and removes artificial dependencies, without weakening verification gates. The initially
  DNS-blocked packaged-definition gate now passes, alongside retained
  fixtures, as qualified below. Not a release proposal.
- Entry point: [TODO](../../../TODO.md#active-updates-architecture-and-ux). Durable approval:
  [D-056](../DECISIONS.md#d-056-updates-architecture-and-execution-order--accepted-for-implementation).
  Current implemented behavior/evidence: [ARCHITECTURE](../ARCHITECTURE.md) and
  [BASELINE](../BASELINE.md). Existing decisions remain unless explicitly superseded by D-056.
- Working branch: `work/updates`, created from clean `main` at `a20f1fc` (also `origin/main`).
  Manager version: 6.1.0; latest published tag: v6.1.0. No subsequent implementation work was
  present when this cycle began. The approved assumptions still match the implementation.
- One coherent work package per cycle: investigate/reproduce, implement narrowly, test, review,
  update records and commit locally, then checkpoint. The owner's consolidation approval (D-057)
  permits tightly related subtasks in the same cycle, with separate focused commits where useful;
  do not require STOP/Continue between those subtasks. Stop at the package boundary, an unsafe or
  oversized scope, or a blocker. On Continue, recover from these files and Git, not memory.
- This is the single detailed running-effort record under D-045. Do not add a parallel plan or
  task database. Retire it only after its durable facts/evidence are in the permanent records.
- No version bump, release preparation, release tag, push, package upload, remote issue creation,
  release automation or publication is authorized. Completion is not release permission.

## Reconciliation with the starting implementation

Source paths below describe the UP-00 starting point, not a substitute for reading the code
again per task. UP-01 fixes report/Agent Context presentation; UP-02 fixes inventory loss on
remote failure; UP-03 fixes base guard scope and cleanup/creation races; UP-04 removes rollback
creation-time guessing; UP-05 bounds short diagnostics/probes and canceled result publication.
UP-06 fixes category-owned advisory clearing/status; UP-07/UP-08 implement shared observations,
compatible discovery and policy/target corrections. Other staged findings remain pending.
Source inspection is not regression or real-operation evidence.

| Finding | Current implementation | Required correction |
|---|---|---|
| Wrong Agent Context heading (fixed in UP-01) | At UP-00, `tui._agent_context_worker` used `OpenCodeVersionsScreen` without a title; its default was OpenCode versions | Now `ReportScreen` with required explicit title; Agent Context heading/capitalization corrected, failed inspection is visibly unverified |
| Remote failure hides inventory (fixed in UP-02) | At UP-00, CLI and TUI queried npm before enumerating environments | Shared `versions_report` retains independent source results and per-row errors; CLI stderr/exit 2 and TUI error notice keep partial failures visible |
| Base coordination is too narrow (fixed in UP-03) | At UP-00, base locks used the selected data directory | Shared UID/canonical verified endpoint/distribution guards in a fixed private `/tmp` namespace, with no override-dependent fallback |
| Cleanup does not guard all base copies (fixed in UP-03) | At UP-00, rollback-copy cleanup had no base guard | Candidates, copies and identifiable untagged replaced bases take build then publication, rechecking identity/ownership/local references; busy/unsafe resources remain |
| Rollback guesses wrong order (fixed in UP-04) | At UP-00, `rollback_base` maximized Docker image creation time | Alias-consolidated immutable inventory, one-copy default, explicit multi-copy selection even with `--yes`, consent/current-base revalidation and current-definition verification |
| Diagnostic calls can hang (fixed for short checks in UP-05) | At UP-00, general `core.call`/version probes had no execution deadline | Finite read-only allowlist/explicit probe scopes, total HTTP child budget, bounded output/client reaping, container-side limits, label-checked helper cleanup and cancellation-safe read-only UI publication; long mutations keep their existing timing |
| Obsolete image advisories linger (fixed in UP-06) | At UP-00, `_show_image_checks` posted warnings, but successful checks were not published | Complete results replace/clear owned daemon/resource/image notices; explicit status ownership preserves active progress and cleanup-safe results; no late same-turn warning toast |
| Versions is only a report | It queries npm on opening, lists running-environment versions, and offers only Close | Compact Updates inventory/actions with independent component lifecycles |
| No manager discovery/updater | Version source and manual pipx instructions exist; no installation classification or handoff | Published-release discovery and verified official-tag pipx execution after earlier stages |
| Missing observation/discovery cache (fixed in UP-07/UP-08) | At UP-00, readiness cache was not structured version history and stopped versions were lost | Now disposable source/time/immutable-identity evidence and distinct attempts, outside metadata; replacement/journals invalidate or qualify history |
| Latest/policy semantics (fixed in UP-07/UP-08) | At UP-00, npm latest outside 2.x was refused and Manual/Pinned hid explicit comparisons | Now latest supported stable metadata selection, exact consent/revalidation and explicit comparisons without weakening policy |
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

All tasks below are pending except UP-00..UP-08 and the one-time PERF checkpoint. D-057 consolidates closely related remaining
tasks into work packages without renumbering IDs or dropping acceptance criteria. Dependencies
are technical prerequisites, not a forced serial order or a STOP/Continue requirement. Complete
tightly related subtasks in one cycle when manageable; use separate focused commits and tested
checkpoints as appropriate. Split an oversized package at a safe boundary, not by weakening tests.
Every task must reproduce the defect where applicable, add regressions, rerun affected tests,
review the diff and update user/engineering documents with actual behavior and evidence.

Default priority: finish correctness (UP-06), shared evidence/discovery (UP-07 + UP-08), compact
UI with optional background scheduling (UP-10 + UP-09), environment actions/recovery (UP-11),
base actions/refresh (UP-12 + UP-13), manager discovery/classification (UP-14 + UP-15), manager
handoff (UP-16), replacement/recovery (UP-17), then evidence consolidation (UP-18). This is
**nine remaining cycles at consolidation approval instead of thirteen** (seven after UP-07/UP-08), not
a quota or permission to combine
unrelated risks. Read-only manager discovery can be developed independently of base refresh;
manager execution remains later and must not delay the earlier component workflows. UP-18 is
not release preparation. UP-00..UP-08 are DONE; all later tasks are PENDING. The next package
is UP-10 + UP-09, implementing manual/cached UI before optional scheduling. UP-03's initially DNS-blocked
packaged-definition gate was retried successfully during UP-04; evidence is recorded below.

| ID | Stage / task | Prerequisites | Acceptance and minimum focused verification |
|---|---|---|---|
| UP-00 | DONE: persist approved plan | Owner approval | Documentation-only commit `3552f67`; decision/status links, complete scope/dependencies/test gates and resume record |
| UP-01 | DONE: generic report and Agent Context heading | UP-00 | Explicit titles for all report callers; consistent Agent Context labels/fallback wording; pilot regressions for Agent Context, Versions, readiness and cleanup, including 80x24; evidence below |
| UP-02 | DONE: preserve inventory on remote failure | UP-00 | CLI/TUI local rows survive npm failure; per-item errors isolated, explicit check failure still reported; offline/partial-result regressions without starting containers; evidence below |
| UP-03 | DONE: shared base coordination | UP-00 | Secure shared namespace and lock ordering; guarded build/swap/rollback/cleanup/creation; host multiprocess and real-Docker races across data/context aliases pass with retained fixtures; packaged-definition gate resolved during UP-04 |
| UP-04 | DONE: explicit base rollback selection | UP-03 | Alias consolidation, one-copy default, multi-copy explicit selection, immutable consent and definition verification; 49 mocked/host regressions and 4 packaged/retained real cases with CLI swap/layer preservation |
| UP-05 | DONE: bounded diagnostic execution | UP-00 | Total network/short subprocess budgets, response limits and owned cleanup/cancellation; container-side bounds; long mutations unaffected; 51 new host/mocked/pilot cases and real Docker probe/base regressions, evidence below |
| UP-06 | DONE: clear obsolete advisories | UP-00 | Category-owned warning/success/unknown replacement, status ownership and same-turn toast cleanup; 26 new mocked-check/image/readiness pilot cases at 80x24/100x30, four full compatibility suites; evidence below |
| PERF | DONE: one-time test-performance investigation | Between UP-06 and UP-07 + UP-08, by owner request; not a new product dependency | Repeat baseline/after timings and collection/fixture/process profiling; same 1263 IDs/outcomes, 708 equivalent parser queries; two test-local improvements, risk-based local cadence, unchanged CI/release gates; evidence below |
| UP-07 + UP-08 | DONE: shared observations, compatible discovery and policy comparisons | UP-02, UP-05 | Structured source/time/identity, private disposable local/remote cache, stopped history/Unknown, lifecycle qualification and partial Docker results; bounded stable supported-major selection, exact confirmed targets, Manual/Pinned explicit comparisons and shared eligibility. 125 new default-suite cases, four complete compatibility suites, scoped real Debian/Arch update/rollback/recovery/restore/probe checks; evidence below. Scheduler/Updates UI remain pending |
| UP-10 + UP-09 | Compact Updates inventory, then optional background discovery | UP-01, UP-06, UP-07 + UP-08; **no UP-10 dependency on UP-09** | UP-10 independently delivers three local/cached-first subviews, manual Check, independent loading/errors, Details and keyboard/focus at 80x24/larger, with no network on opening and no premature manager execution. UP-09 adds default-off scheduling, attempt-based 24-hour persistence including failures/restarts, coalescing/rate limits and quiet deduplication, with no start/probe/update side effects. Separate UI/pilot/terminal and cache/preferences/scheduler gates; stop after verified UP-10 if the combined package is too large |
| UP-11 | Environment actions and recovery | UP-10, UP-07 + UP-08 | Existing Check/Start/Policy/Update/Rollback/Recover handlers with exact consent and locked revalidation; pin/network/running-state refusals, stopped final state and recovery; real Docker/OpenCode and terminal tests. Recovery is an independent gate, not bundled with base or manager work |
| UP-12 + UP-13 | Base actions and explicit cached/full-refresh rebuild | UP-03, UP-04, UP-07 + UP-08; UP-10 for TUI binding only; **no UP-11 dependency** | Inventory, Build/Rebuild/Check/Rollback, rollback-preserving replacement and exact target/state/mode consent; explicit cached versus Refresh & Rebuild in CLI/TUI, pull/no-cache without prune. Verify both distributions under isolated tags, failed-candidate safety, CLI/TUI parity, pinned creation and unchanged retained containers/layers; cached and full-refresh results are separate evidence |
| UP-14 + UP-15 | Manager release discovery and verified installation classification | UP-05; UP-07 + UP-08 for shared cache; UP-10 for TUI binding only; **no UP-13 dependency** | Bounded official published-full-release discovery, strict tags/semver/no implicit downgrade, local inventory retained on GitHub failure; actual official-tag pipx identity including custom paths/interpreter/source/launcher, safe manual guidance otherwise. Separate provider and real isolated pipx/foreign/shadowed-launcher tests. Optional daily-source hookup only if UP-09 exists; neither discovery nor classification requires it or exposes execution |
| UP-16 | Installation exclusion and terminal handoff | UP-14 + UP-15, UP-05 | Supported instances coordinate across data directories; safe self-contained helper/interpreter/external pipx, clean TUI exit before mutation, startup exclusion and narrow verification path; process and pty tests |
| UP-17 | Manager replacement, verification and failure recovery | UP-16 | Exact confirmed target and revalidation, actual fresh-process verification, no automatic restart. Independently verify (1) replacement/success and (2) failure/interruption states, private recovery record and instructions before/during/after install. Separate focused commits/checkpoints for these gates; isolated pipx and real terminal evidence, never inferred backup/rollback safety |
| UP-18 | Cross-layer verification and record consolidation | UP-01..UP-17 | Run affected/full regressions, required real combinations, dependency endpoints, docs/CLI/packaging checks; record evidence/limits, promote durable facts and retire the effort record when complete; no release work |

### Consolidation rationale and safe checkpoints

- **UP-07 + UP-08:** observation identity, disposable cache and comparison semantics are a shared
  data contract. Implement/test it together instead of publishing a provisional model in one cycle
  only to reshape it in the next. Local observations and remote discovery remain independent
  sources; invalidation and failed-attempt tests are mandatory. No scheduler or screen dependency.
- **UP-10 + UP-09:** share presentation/preferences integration in one package if manageable, but
  implement and verify manual/cached UI first. UP-10 must run with scheduling absent or disabled;
  UP-09 uses the shared provider/cache contract, not the Updates screen as its execution engine.
  If split for scope, UP-10 is a deliverable checkpoint, not blocked by pending UP-09.
- **UP-12 + UP-13:** one base-action/confirmation path should select cached/full-refresh behavior,
  rather than a UI rewrite in the next cycle. Environment journals/recovery do not participate in
  base builds, so remove UP-13 -> UP-11. Candidate verification, immutable consent, rollback-copy
  preservation and both-distribution real tests remain gates, not optional polish.
- **UP-14 + UP-15:** manager availability and installation eligibility form one read-only summary,
  but can fail independently and must be tested separately. Remove UP-14 -> UP-13: GitHub/pipx
  inspection does not consume a base build. Shared cache and UI hookups are explicit integration
  dependencies only. Installation classification is not authorization to replace it.
- **Do not consolidate UP-11, UP-16 or UP-17 with adjacent packages.** Environment recovery,
  installation exclusion/terminal handoff, replacement and failure recovery each require runnable,
  independently evidenced checkpoints. UP-17's success and failure gates may share a cycle only
  when both fit; split before higher-risk fault injection if necessary. Restore/rollback safety,
  lock ordering, pre-replacement recovery instructions and fresh-process verification are unchanged.

Every checkpoint records completed and pending IDs/subtasks, commands/results, limitations,
resources and exact next gate so context compaction is safe even inside a grouped package.
Do not stop mechanically after a related subtask commit; do not continue into an independent
package merely because tests pass. A blocker in optional scheduling or one component must not
block independent usable work or be hidden as success. Historical UP-00..UP-05 STOP instructions
below describe those past cycles, not a renewed one-ID-per-cycle constraint.

No implementation task is complete because it appears in this table. Manager scope is included
now, but must not delay the earlier component workflows. Do not add predicted commands/options to user-facing docs
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

No unresolved product decision blocks UP-07 + UP-08. The following are implementation proofs to resolve
in the named task, not permission to reopen settled UX or add infrastructure. If evidence needs
a materially different architecture, record the blocker and ask the owner before proceeding.

| Risk / question | Resolve in | Required proof or safe fallback |
|---|---|---|
| Secure shared lock root on hosts with/without a usable runtime directory | Resolved in UP-03 | Fixed `/tmp/opencode-sandbox-locks-<UID>/`; no runtime/HOME/TMPDIR fallback; ownership/no-follow/inode checks, process/alias convergence, legacy-manager boundary documented |
| Scope/order of base cleanup guards and publication identity checks | Resolved in UP-03/UP-04 | Base participants guarded; immutable copy/current-base consent rechecked before verification/publication; host and packaged/retained real races pass; failed/changed inspect refuses mutation |
| Container-side probe deadline tools and cleanup on missing/custom tooling | Resolved in UP-05 within documented trust/liveness limits | GNU timeout required, no unbounded fallback or stopped-container start; owned client reaping and label/full-ID helper removal; real Debian/Arch timeout/cancellation/missing-tool/leak checks pass; inaccessible daemon means unconfirmed cleanup |
| Cache location, invalidation and compatible npm metadata size | Resolved in UP-07/UP-08 | Private data-root `update-cache/`, 128 KiB per entry, eight-second/8 MiB abbreviated metadata; source/time/immutable identity and separate attempts; lifecycle qualification without metadata migration or readiness-string parsing |
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

### UP-03 — 2026-10-30 — daemon-wide base coordination

- Recovered instructions, the complete roadmap/current-state records and clean `work/updates`
  at UP-02 `4ea5050`. Local permissions still allow scoped disposable rootless tests, not
  privileged rows or deleting retained bases. Starting daemon identity was verified, with zero
  containers/volumes and the same four retained image tags/IDs as UP-02. No competing work.
- Reproduced cross-directory divergence with two fresh Python processes and isolated `.work/`
  data/config directories: while one held `base-tag-debian`, the other acquired its nominal
  counterpart immediately. Root cause: authoritative daemon-shared tags used `core.lock`'s
  per-data-directory namespace; rollback-copy cleanup additionally had no base guard at all.
- Inventoried participants: `core.build` delegates to `update_base`; `update_base` holds build
  through candidate build/verification, replacement and its own candidate cleanup; `rollback_base`
  holds build through selection/verification/swap/removal; `core.start` holds environment then
  publication across the pin check and container creation. Cleanup holds its data coordinator
  then the item's needed environment locks or base build/publication, one item at a time.
  No source participant still uses `base-image-*`/`base-tag-*` data-directory locks.
- Added the focused `base_locks.py` module and `core.base_lock` adapter. Chosen namespace:
  `/tmp/opencode-sandbox-locks-<UID>/`, SHA-256 keys over own UID, pinned canonical verified
  endpoint and distribution, with separate build/publication files. It deliberately ignores
  product data/config, HOME, TMPDIR and XDG settings. There is **no runtime-directory fallback**:
  using two conditionally usable roots could split participants. An unsafe/unusable fixed root
  refuses the operation. Reboot clears temporary state only after processes/locks are gone;
  daemon PID/restart is not part of the key. No host services or configuration were changed.
- Namespace proof: no-follow descriptor-relative creation/open, validated temporary parent,
  own-user 0700 directory, own-user regular 0600 single-link files, final inode/path recheck,
  non-inheritable descriptors, stable files never chmodded/unlinked/recreated by the manager.
  Host tests cover foreign ownership, permissions, symlink/hardlink/FIFO/directory substitutions,
  path replacement, fresh-process convergence, daemon/distribution separation, exec descriptor
  noninheritance and process-death release without changing the inode. Unit roots are isolated
  under pytest's private paths; real runs retain the shared lock namespace as protocol state.
- Acquisition order is executable, not just prose: execution-context base tracking refuses
  reverse/recursive base acquisition (and unstable same-level distribution order); `core.lock`
  refuses earlier data/environment acquisition inside base guards. Needed order remains data
  coordinator -> stable environment IDs -> build -> publication; future installation usage
  precedes them but is not added in this task. Long build/verification does not hold publication.
- Added full image identity/ownership inspection at mutation boundaries. Known missing-image
  evidence alone permits a first build. Existing base identity is captured before the build and
  rechecked at publication; unexpected replacement/removal, invalid/failed inspect or foreign
  labels refuse changes. Publication tags immutable IDs. Candidate and rollback-copy tag
  collisions are refused without overwriting/deleting the colliding object. Rollback rechecks
  its selected copy and current base after verification. No explicit copy-choice behavior yet:
  `max(..., .Created)` is deliberately retained for UP-04.
- Cleanup now guards candidates, copies and identifiable untagged replaced bases with build then
  publication, nonblocking. It rechecks image identity, managed distribution labels, untagged
  status and local metadata references while guarded; failures/changes leave the resource alone.
  Unlabelled/foreign/unknown-distribution names are not ownership permission. Busy reasons remain
  visible; unsafe namespace errors are not disguised as ordinary contention. Shared locks still
  cannot promise another data directory's future rollback or coordinate old managers/manual
  Docker. No cleanup may delete current base tags or shared build cache.
- Added 60 host/mocked cases in `test_base_locks.py`/`test_base_coordination.py` and updated the
  existing base/pin/cleanup fakes for full identity labels and shared guards. No security check
  was weakened and no blanket lint exclusion was added. One old pin test used stale pre-policy
  metadata and accidentally hit public npm; reloading its saved record and explicitly forbidding
  lookup makes the existing pin-first behavior deterministic, without a product policy change.
- Failures and corrections, not waived: first focused run 129 passed/2 failed (new ownership
  test also intercepted its parent, and an old mock indexed a formatted call on raw inspection);
  fixed test scoping/response shape. Next 166 passed/1 failed exposed the stale pin test above.
  First full run 1069 passed/1 lint failure/56 skips exposed imported-fixture name shadowing;
  import the fixture through its module. A later full run 1074 passed/1 doc failure/60 skips
  found the public-record gate interpreting `publication/cleanup` as an internal branch name;
  reworded that prose. All are covered by the clean final suites below.
- Serial full suites on the final product code, absolute PYTHONPATH, pytest 9.2.0 (the final
  descriptor-test assertion strengthening and its four-endpoint rerun are recorded below):

  | Interpreter / direct dependencies | Result / basetemp |
  |---|---|
  | Python 3.11.18, Typer 0.27.3/Textual 8.2.8 | **1075 passed, 60 opt-in skips**, 95.50 s; `/tmp/opencode/up03-current311-clean` |
  | Python 3.11.18, Typer 0.16.0/Textual 4.0.0 | **1075 passed, 60 opt-in skips**, 106.60 s; `/tmp/opencode/up03-low311` |
  | Python 3.14.8, Typer 0.27.3/Textual 8.2.8 | **1075 passed, 60 opt-in skips**, 115.15 s; `/tmp/opencode/up03-current314` |
  | Python 3.14.8, Typer 0.16.0/Textual 4.0.0 | **1075 passed, 60 opt-in skips**, 118.04 s; `/tmp/opencode/up03-low314` |

  Commands use `PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q --basetemp=<above>`
  with `venv311`, `venv311low`, `venv314`, `venv314low`. Only the two known lowest-Typer/Click
  deprecations. The 60 skips are opt-in real/privileged/socket-activation rows, including the
  four new real cases; not silent suppression of a failure. Ruff/shellcheck, language, docs,
  CLI/help and existing host-process/terminal fixtures are included. Earlier full current-3.11
  run before the final small additions: 1070 passed/58 opt-in skips (114.40 s); final focused
  base/quality subset: 185 passed (7.97 s).
- Final review strengthened the descriptor test: reacquisition after explicit unlock alone
  does not prove the child closed an inherited descriptor, so it now inspects the exec child's
  open device/inode identities with `close_fds=False`. No product change. Re-ran
  `tests/test_base_locks.py tests/test_quality.py` serially across all four endpoint combinations:
  **35 passed/no skips each**, 1.83/1.81/1.97/1.88 s, using `venv311`, `venv311low`, `venv314`,
  `venv314low` with basetemps `/tmp/opencode/up03-fd311`, `up03-fd311low`, `up03-fd314`,
  `up03-fd314low` respectively (last three share the `/tmp/opencode/` parent). The full suites
  precede this test-only assertion change; the final product code was covered by all four.
- Added `integration/test_42_base_coordination.py`, reusing the campaign/manifests/guarded cleanup.
  Real worker processes share one verified daemon through two context aliases, one via a socket
  symlink, with independent product data/config directories. Stage rendezvous pauses real
  build/verify/start handlers; Docker responses, image verification and container creation are
  not mocked. Explicit test labels and namespaces restrict every image/removal to the manifest.
- **Fresh packaged-definition variant BLOCKED, not passed**: initial `up03-races` attempt had
  2 failures in 104.30 s, Debian at Docker Hub DNS for `node:24-trixie`, Arch at mirror DNS during
  pacman retries. Both failed before publication and completed guarded cleanup; tagged-image
  inventory was unchanged. No DNS/firewall/service/security changes were attempted. The
  failing online scenarios are retained as a separate `packaged` variant, not silently skipped.
- Separately added an explicit network-free `local-fixture` variant, deriving disposable images
  from the retained Debian 12/revision-1 and Arch/revision-1 bases with real OpenCode 2.2.0. A
  test-only fixture registry uses that retained OS definition; it does not pretend Debian 12
  satisfies the production Debian 13 definition or skip any promised tool/OS/binary verification.
  It does not reinstall OpenCode or refresh OS packages. This is real race evidence, not fresh
  packaged-definition build, model-provider or release evidence.
- `local-fixture` results: `up03-local` 2 passed/2 deselected (22.21 s), `up03-final` repeated
  after collision/guard refinements 2 passed/2 deselected (20.59 s), final `up03-proof` with real
  writable-layer markers and the final product code **2 passed, 24 logged checks, 2 packaged
  cases deselected**, 22.30 s. Cases prove rebuild/rollback exclusion across overrides, creation
  during build, active-candidate cleanup exclusion, publication exclusion across pin/creation,
  rollback-copy cleanup exclusion during verification/swap, immutable restoration and retained
  running containers/layer markers. Final logs/manifests: `.work/logs/up03-proof*`.

  ```sh
  OCS_TEST_DOCKER=1 OCS_TEST_RUN=up03-proof PYTHONPATH="$PWD/src" \
    .work/venv311/bin/python -m pytest -q tests/integration/test_42_base_coordination.py \
    -k local-fixture --basetemp=/tmp/opencode/up03-real-proof
  # Still BLOCKED by DNS; use a new run ID and fresh basetemp when network prerequisites work:
  OCS_TEST_DOCKER=1 OCS_TEST_RUN=up03-packaged-retry PYTHONPATH="$PWD/src" \
    .work/venv311/bin/python -m pytest -q tests/integration/test_42_base_coordination.py \
    -k packaged --basetemp=/tmp/opencode/up03-packaged-retry
  ```

- Each real run removed only its manifested test tags/environments, with guarded product cleanup
  and leak checks. The product cannot remove a current base, so final fixture teardown explicitly
  inspects the run label/immutable ID/manifest before untagging its test-only base. Original base,
  upstream/custom-image tags and IDs are unchanged; no containers/volumes/test-labelled images
  remain; temporary socket aliases removed; Docker default context unchanged. Shared lock files
  remain intentionally and build cache was not pruned. No retained rollback copy was touched.
- Local package verification on Python 3.11: `python -m build --no-isolation --outdir
  .work/up03-package`, strict twine and `.github/scripts/check_dist.py` all pass; the new module
  is byte-identical in the wheel. No upload or fresh pipx installation. Other unexecuted layers:
  full real campaign, privileged daemon restart/socket activation, real model provider and new
  real-terminal/manual UI observation. Historical release evidence is not relabelled as current.
- Updated Unreleased, OpenCode/security/maintenance guides, architecture, baseline, campaign,
  decision implementation status and TODO. Version 6.1.0, schemas, image definitions, policies,
  existing CLI options and independent environment lifecycle/configuration remain unchanged.
  Final document/static subset: **40 passed, no skips**, 7.18 s, Python 3.11.18:
  `tests/test_language.py tests/test_user_docs.py tests/test_cli_structure.py tests/test_quality.py`
  with `/tmp/opencode/up03-docs-review` and the same absolute PYTHONPATH/venv311 command form.
  Reviewed product/new test/guide diffs and lock participants; whitespace checks are clean.
  Final read-only daemon inventory is verified, zero containers/volumes and exactly the starting
  four full tagged-image IDs. No version/assets/schema/runtime-identity/dependency/workflow changes.
  Final language/link/CLI-document repeat after the evidence updates: **27 passed, no skips**,
  5.46 s, same three documentation modules and venv311, `/tmp/opencode/up03-docs-final`.
  Planned local commit: `fix: coordinate base images across data directories`; resolve its
  actual hash from Git. **UP-03 implemented and focused races verified; STOP after the local
  commit. Next UP-04 only**, with the fresh-definition race variant retained as a blocked gate.

### UP-04 — 2026-10-30 — explicit identity-bound base rollback selection

- Recovered instructions, TODO, D-056, architecture/baseline and the full working record. Git
  was clean on `work/updates` at UP-03 `40211ab`. The verified own rootless daemon again had no
  containers/volumes and exactly the same four original full tagged-image IDs. Local permission
  remains scoped to disposable resources, not privileged/network changes or retained-image deletion.
- Reproduced the defect before patching: three mocked-daemon cases with several distinct copies
  (earlier/later/equal creation times) all **failed** because rollback silently selected/mutated
  instead of refusing ambiguity. Root cause: `.Created` is image-build time, not tag replacement
  history; caching, downgrades and equal dates cannot establish the last replaced base.
- The owner reported restored connectivity. Retried the existing blocked gate on unchanged UP-03
  product code before implementing UP-04: `up04-packaged-retry`, **2 passed, 24 checks, 2 retained
  cases deselected**, 481.35 s. Debian 13/revision 2 and Arch/revision 1 built the packaged
  definitions with actual package downloads/build steps and OpenCode 2.2.0. Both passed real
  OS/tool/binary verification and the coordination races. DNS required no host changes. The old
  UP-03 DNS failures remain historical failures, not retroactively passed; the gate is now resolved.

  ```sh
  OCS_TEST_DOCKER=1 OCS_TEST_RUN=up04-packaged-retry PYTHONPATH="$PWD/src" \
    .work/venv311/bin/python -m pytest -q tests/integration/test_42_base_coordination.py \
    -k packaged --basetemp=/tmp/opencode/up04-packaged-retry
  ```

- Added frozen, in-memory `BaseRollbackCopy`, `BaseRollbackInventory` and `BaseRollbackPlan`
  records in the existing versions module, not a history store/schema or universal executor.
  `base_rollback_inventory` uses publication for a consistent read-only image inventory; it
  neither starts helpers nor queries npm. Full managed distribution inspection proves ownership;
  tags only identify candidates. It consolidates exact managed copy aliases by full immutable ID,
  retaining old-definition provenance/missing creation history. Version labels are labelled build
  evidence, not fresh binary verification. Invalid/failed/foreign inventory fails closed.
- Pure `select_base_rollback` defaults only for one distinct image. With several, an exact listed
  tag or full `sha256:` ID is required; no date/version/list-order inference or short-ID guess.
  CLI adds `opencode rollback-base --list` and `--copy TAG_OR_FULL_IMAGE_ID`. `--yes` bypasses
  confirmation only; it never picks among several. The ambiguity error lists choices and the
  read-only command. `--list` is noninteractive and does not need confirmation; list+copy refuses.
- CLI previews current and selected immutable IDs, copy aliases, build provenance/version and
  required definition, then confirms that exact replacement with the existing Cancel-default
  confirmation. It explains future base-based creation/file-only restore effects, existing
  container/layer preservation, pin enforcement and replaced-base retention. Without a terminal
  it still requires `--yes`. Existing command capabilities remain, with ambiguity now intentionally
  refused rather than guessed; the Versions TUI remains unchanged until its scheduled tasks.
- Execution takes build then publication. A plan binds daemon, distribution, expected current
  base (including known absence), selected full ID and alias identities. Recheck before probing
  and again before publication; changed/missing aliases, changed/new/missing current base, failed
  inspection/foreign ownership or another daemon/distribution refuse stale consent. A newly
  arriving unrelated copy does not substitute the selected target. All probes/verification and
  publication use the immutable ID, retaining current OS/tool/OpenCode/major checks. Long
  verification holds build, not publication; UP-03 order/namespace protections are unchanged.
- Publication keeps the replaced current immutable image under a collision-checked new rollback
  tag, publishes the selected image, then consumes only the selected aliases. Other images/aliases
  remain. Selecting an already-current image verifies and reports unchanged without tag changes.
  No replacement history, migration, schema/version/image definition change, automatic update or
  background discovery was added. Cleanup's old "uses the newest" hint now points to selectable copies.
- Added **49** mocked-Docker/host cases in `test_base_rollback.py`: creation-time order/ties,
  cached older builds and explicit downgrade, aliases, exact selectors, before/after-verification
  identity/ownership/missing/inspect failures, daemon/distribution binding, new unrelated copies,
  missing/current no-op cases, old provenance/no version label and immutable probes, guards,
  failed definition/major/collision protection, list/confirmation/cancel/noninteractive/yes.
  Updated the old automatic-newest regression to verify the one-copy path, full immutable probe
  target and unchanged other-distribution exclusion; existing old-OS refusal still passes.
- Corrections, not waived failures: first affected run **175 passed/2 failed** (new import order,
  and the old empty-inventory fake returned human text for raw current-image JSON). Fixed test
  responses/import grouping; rerun **177 passed**, 11.51 s. First full run **1123 passed/1 failed/
  60 opt-in skips**, 95.57 s: the static distribution-branch detector mistook generic
  `plan.distro != d.id` identity comparison for distro-specific branching. Reversed the same
  comparison operands, with no check suppression/product behavior change; focused base rollback,
  distribution and quality checks **73 passed**, 1.55 s, then all full runs below passed.

  | Full suite / venv | Result / basetemp |
  |---|---|
  | Python 3.11.18, current Typer 0.27.3/Textual 8.2.8, `venv311` | **1124 passed, 60 opt-in skips**, 95.51 s; `/tmp/opencode/up04-final311` |
  | Python 3.11.18, lowest Typer 0.16.0/Textual 4.0.0, `venv311low` | **1124 passed, 60 opt-in skips**, 93.75 s; `/tmp/opencode/up04-final311low` |
  | Python 3.14.8, current, `venv314` | **1124 passed, 60 opt-in skips**, 93.78 s; `/tmp/opencode/up04-final314` |
  | Python 3.14.8, lowest, `venv314low` | **1124 passed, 60 opt-in skips**, 93.16 s; `/tmp/opencode/up04-final314low` |

  All serial foreground: `PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q
  --basetemp=<above>`. pytest 9.2.0; only the two known lowest-Typer/Click deprecations.
  Includes Ruff/shellcheck, document/CLI checks, unit/mocked Docker, real host files/processes,
  existing Textual pilots/host terminal fixtures. The 60 opt-in skips are explicitly real,
  privileged or socket-activation cases, not suppressed failures.
- Extended the same scoped real race harness, not a new campaign framework. After real rollback,
  create manifested aliases across two immutable images; actual CLI `--list` consolidates them,
  `--yes` refuses ambiguity, a retag after consent refuses without moving current, and explicit
  full-ID `--copy --yes` verifies/publishes that exact image while preserving replaced current.
  Existing process/data-directory/context-alias exclusions, current-definition verification,
  pinned creation, running-container image identities and writable-layer markers still pass.
- All four packaged/retained variants passed twice: `up04-real` **4 passed/76 checks**, 61.80 s;
  final `up04-proof` after final CLI preview wording **4 passed/76 checks, no skips/deselections**,
  61.93 s. Packaged cases use Debian 13/revision 2 and Arch/revision 1; retained network-free
  fixtures remain Debian 12/revision 1 and Arch/revision 1, both with actual OpenCode 2.2.0.
  Later packaged builds reuse eligible cache; none of these is the future pull/no-cache full
  refresh or a model-provider test. Evidence/manifests: `.work/logs/up04-proof*`.

  ```sh
  OCS_TEST_DOCKER=1 OCS_TEST_RUN=up04-proof PYTHONPATH="$PWD/src" \
    .work/venv311/bin/python -m pytest -q tests/integration/test_42_base_coordination.py \
    --basetemp=/tmp/opencode/up04-proof
  ```

- All three real runs used test-only namespaces/labels, manifests, run-label/immutable-ID checks,
  guarded product cleanup and leak checks. Final own-rootless inventory: zero containers/volumes,
  no final-run-labelled images, exactly the starting four tagged-image IDs; socket aliases removed.
  No retained base/upstream/custom tag or rollback copy touched; shared lock files and build cache
  intentionally retained. No host networking/service/default-context changes or privileged rows.
- Packaging on Python 3.11: `python -m build --no-isolation --outdir .work/up04-package`, strict
  twine and `check_dist.py` passed; `cli.py`, `cleanup.py` and `opencode_versions.py` byte-identical
  in the wheel. No uploads/global installation/fresh pipx. Not re-established: full real campaign,
  installed-manager/pipx execution, privileged restart/socket activation, new real-terminal/manual
  observation or model-provider use. Existing pty/pilot tests do not prove new manual observation.
- Updated OpenCode guide/Unreleased, TODO, architecture, baseline, campaign and D-056 status.
  No version/assets/schema/core/base-lock/runtime-identity/dependency/workflow changes.
  Reviewed all three changed product modules, new/updated tests, real manifest/cleanup outcomes
  and user/current-state guides; no stale newest-copy execution hint remains. Final regression/
  language/link/CLI/static subset after the evidence updates: **89 passed, no skips**, 7.41 s,
  `tests/test_base_rollback.py tests/test_language.py tests/test_user_docs.py
  tests/test_cli_structure.py tests/test_quality.py` with venv311 and
  `/tmp/opencode/up04-docs-review`. Whitespace checks are clean.
  Planned local commit: `fix: require explicit base rollback selection`; resolve its actual hash
  from Git. **UP-04 complete; STOP after local commit. Next UP-05 only.**

### UP-05 — 2026-10-30 — bounded diagnostics and owned probe cleanup

- Recovered repository/local instructions, TODO, baseline, architecture, D-056 and the full effort
  record. Clean `work/updates` at UP-04 `8291e9c`; own rootless daemon verified, zero containers/
  volumes, same four original tagged-image IDs. No later work invalidated the task. Disposable
  rootless tests remain authorized; privileged/service/network/retained-image changes are not.
- Reproduced cancellation before patching with a real sleeping fake Docker executable: canceled
  `image inspect` waited for its client and returned normally (**1 failed**, 1.02 s). Root cause:
  `core.call` used plain unbounded `subprocess.run`, worker cancellation only reached readiness,
  version `exec`/image helpers had no container-side timer, and urllib's socket timeout did not
  bound the entire DNS/TLS/slow-body operation. Canceled thread status was not process ownership.
- Inventoried finite Docker metadata/usage calls, host-version checks, npm lookup, running-image/
  environment versions, update verification, full image verification, comprehensive readiness
  execs and read-only TUI workers. Kept the existing daemon identity/resource support budgets,
  rootless proof, base guards, immutable rollback plans, journals/install script and user exec.
- Added the focused stdlib `diagnostics.py` runner. One monotonic budget covers client execution
  and pipe draining; nonblocking selectors enforce a combined 1 MiB output bound. It owns a new
  process session/group, polls cancellation, kills only that group and reaps the direct client
  with a bounded wait. No abandoned downloader/reader thread. `waitid(WNOWAIT)` reserves the
  exited leader's PID/group identity until cleanup signals are sent, avoiding a reused-group
  signal. Reused the existing callable-signal launch guard so SIGINT/TERM/HUP cannot unwind
  creation before the client reference is registered; no inherited mask or worker signal changes.
- `core.call` opts in only with an explicit timeout; `core.docker` automatically bounds a finite
  allowlist of inspect/list/info/system-df/stats-no-stream calls (eight seconds). Arbitrary
  run/exec, build, install, commit, start/stop and user sessions retain their old timing. A narrow
  context scopes individual owned probes and cleanup calls, never a whole mutation. Bound
  failures do not echo argv or captured configuration output, and do not become object absence.
- npm still uses the existing latest endpoint/resolution policy, but a standalone stdlib
  `http_probe.py` child under `python -I -B` now gives the parent a total eight-second request
  budget, including DNS/TLS/body reads, cancellation and a 64 KiB response bound. No host npm,
  persistent service, new discovery source/cache, automatic lookup or retry loop. Existing HTTP
  errors/malformed JSON/version failures remain visible as registry errors; local rows survive.
- `probes.exec` applies GNU timeout only to diagnostic commands: five seconds for OpenCode
  versions, ten for readiness probes. `probes.image` uses a unique name/token, manager/data/helper
  labels, network none, pull never and container-side timeout (version five; OS/tool verification
  30 seconds); host clients get three seconds' transport/completion grace. Custom/missing timeout
  tooling fails rather than falling back unbounded. A canceled Docker client may leave its exec
  briefly active, but its ordinary process group remains container-timed. This is not protection
  against hostile modified tools/detached processes or a promise while the container cannot run.
- Interrupted image-helper cleanup gets uncancelled bounded inspect/removal calls (three seconds
  each), requires invocation/manager/data/helper labels and full immutable container ID, then
  removes only that helper. Foreign/malformed/failed inspection refuses removal. If the daemon
  is inaccessible, report the named helper and unconfirmed cleanup for later normal labelled
  cleanup after it stops, not a removal claim. No existing environment is stopped. Base candidate
  cleanup gets its own uncancelled inspection after an interrupted probe; guard order stays intact.
- Read-only prerequisite/readiness/Versions/usage/disk/Agent Context workers publish through a
  small `tui_runtime.publish` gate that checks worker cancellation and app liveness before queueing
  and again on the UI thread. This prevents obsolete results after canceled/replaced work. It
  does not add mutation Cancel, advisory-category clearing, partial discovery rendering or an
  Updates UI. A worker canceled during an existing mutation still relies on existing journals/
  recovery; killing its diagnostic client is not a claim that its mutation stopped/rolled back.
- Added **51** host/mocked/loopback/pilot cases: `test_diagnostics.py` (49) and
  `test_diagnostic_tui.py` (2). Covers deadlines/cancel/output/interrupt, pipe-holding descendants,
  reaping, reserved group identity, signal-at-spawn ownership, sanitized bound errors, finite
  allowlist versus untouched long mutations, DNS-blocking child and slow-drip HTTP, helper label/
  immutable-ID ownership/refusals, missing tools and 80x24 responsive cancellation/late results.
  Updated Docker fakes to recognize the timeout wrapper without weakening their underlying
  version/ownership/policy assertions. Unit autouse guards now block unmocked Docker `Popen` as
  well as `run`; unit/pilot tests cannot accidentally reach the host daemon through the new path.
- Corrections/reruns, not waived: first affected run **129 passed/45 failed**, 21.64 s, exposed
  old fake-command shapes and old subprocess interception; adjusted those test boundaries and
  retained explicit new wrapper/runner tests. Next **197 passed/2 failed**, 27.26 s, found one
  remaining repair fake prefix and an unused lint annotation; fixed. Early host subset **56
  passed/2 failed** found a pre-canceled preflight in the mutation-path test plus import/escape
  lint mistakes. Early pilot subset **60 passed/2 failed** found its missing optional metadata
  key assertion and lambda-style lint. Corrected tests, not product checks. Intermediate full
  run **1169 passed/60 opt-in skips**, 97.34 s. Later full run **1173 passed/1 lint failure/62
  opt-in skips**, 99.01 s: invalid label type raised ValueError rather than TypeError; corrected
  the explicit type error. All final runs below pass with no suppression/blanket lint exclusions.
- First diagnostic-only real run `up05-probes`: **2 failed**, 9.24 s. Both reached the missing
  timeout-tool case after the preceding probe checks, but Docker returned its OCI missing-tool
  message on **stdout**, not stderr. The command was not run unbounded; the error was misclassified.
  Check both streams for unavailable tooling and add a host regression. Normal tooling was
  restored and environments deleted even on failure. `up05-probes-rerun`: **2 passed, 28 checks**,
  10.78 s. No failed scenario was skipped or weakened.

  | Final full suite / venv | Result / basetemp |
  |---|---|
  | Python 3.11.18, current Typer 0.27.3/Textual 8.2.8, `venv311` | **1175 passed, 62 opt-in skips**, 98.84 s; `/tmp/opencode/up05-final311` |
  | Python 3.11.18, lowest Typer 0.16.0/Textual 4.0.0, `venv311low` | **1175 passed, 62 opt-in skips**, 97.96 s; `/tmp/opencode/up05-final311low` |
  | Python 3.14.8, current, `venv314` | **1175 passed, 62 opt-in skips**, 99.14 s; `/tmp/opencode/up05-final314` |
  | Python 3.14.8, lowest, `venv314low` | **1175 passed, 62 opt-in skips**, 98.13 s; `/tmp/opencode/up05-final314low` |

  Commands are serial foreground `PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q
  --basetemp=<above>`, pytest 9.2.0. Only the two known lowest-Typer/Click deprecations. Includes
  mocked Docker, real host files/processes/loopback HTTP, Textual pilots/existing host-terminal
  fixtures, Ruff/shellcheck, English, document links and CLI/help consistency. The 62 skips are
  opt-in real/privileged/socket-activation cases (including the two new real cases), not waived failures.
- New real `test_43_diagnostics.py` runs on disposable network-none environments from retained
  Debian 12/revision 1 and Arch/revision 1 (actual OpenCode 2.2.0). Proves running/image version
  checks, container-side exec/image deadlines, ordinary descendant termination, host cancellation
  with client reaping, timer survival after host-client termination, invocation-labelled helper
  removal, missing timeout-tool refusal/restoration, no stopped-environment start, byte-identical
  stopped-check metadata, explicit healthy restart and preserved writable-layer marker. It does
  not imply new-package installation, a live model/provider call or hostile-container isolation.
- Extended UP-03/04's existing real base harness only to manifest/name/label the newly owned
  probe helpers. All four packaged/retained races and immutable CLI selection/pins/layer tests
  still pass with bounded verification. Combined `up05-proof`: **6 passed/106 checks**, 85.99 s;
  after final process-group reservation review, `up05-final`: **6 passed, 106 logged checks,
  no skips/deselections**, 87.01 s. Packaged cases use current Debian 13/revision 2 and Arch/
  revision 1 with eligible build cache, not full refresh. Final evidence `.work/logs/up05-final*`.

  ```sh
  OCS_TEST_DOCKER=1 OCS_TEST_RUN=up05-final PYTHONPATH="$PWD/src" \
    .work/venv311/bin/python -m pytest -q tests/integration/test_42_base_coordination.py \
    tests/integration/test_43_diagnostics.py --basetemp=/tmp/opencode/up05-final
  ```

- All four real runs manifested their test resources and used guarded product cleanup/leak
  checks. Ending own-rootless inventory is verified, zero containers/volumes, exactly the four
  starting full tagged-image IDs, no helpers carrying any run's test label. Original base/upstream/
  custom images and retained copies unchanged; temporary timeout-tool renames restored; socket
  aliases removed; shared lock files/build cache intentionally retained. No host setup/network/
  default-context change, daemon restart, real credential or paid model use.
- Local Python 3.11 sdist/wheel built with `python -m build --no-isolation --outdir
  .work/up05-package`; strict twine and `check_dist.py` passed. All eight new/changed product
  modules are byte-identical in the wheel, including the isolated HTTP child. No upload/global
  installation/fresh pipx run. Not re-established: full real campaign, privileged daemon/socket
  activation, real-terminal/manual observation, installed-manager/pipx or public npm outage/
  discovery. Loopback/controlled DNS tests are not evidence of a live npm outage.
- Reviewed all product/test diffs and cleanup/identity/timing boundaries. Updated Unreleased,
  OpenCode/maintenance guides, architecture, baseline, campaign, D-056 status and TODO. No version,
  schema, image-definition/assets, runtime-identity proof, base-lock protocol, dependencies or
  workflow changes. Final product/early-guide diagnostic+pilot/static/docs subset: **91 passed,
  no skips**, 10.56 s, venv311, `tests/test_diagnostics.py tests/test_diagnostic_tui.py
  tests/test_quality.py tests/test_language.py tests/test_user_docs.py tests/test_cli_structure.py`,
  `/tmp/opencode/up05-review`; final full suites above include those tests. Later evidence-only
  documentation/regression repeat: **91 passed, no skips**, 10.36 s, same modules/venv311,
  `/tmp/opencode/up05-docs-final`. Whitespace checks are clean. Planned local commit:
  `fix: bound diagnostic clients and container probes`. **UP-05 complete; STOP after local
  commit. Next UP-06 only**, obsolete advisory-category clearing without losing active progress.

### Roadmap consolidation — 2026-10-30 — owner-approved work packages

- Recovered clean `work/updates` at UP-05 `32861c6`, instructions, TODO, baseline, architecture,
  D-056 and the roadmap. Verified own-rootless read-only inventory: zero containers/volumes and
  the same four original full tagged-image IDs. No resources created; no cleanup required.
- Reviewed source boundaries in `opencode_versions.py`, `preferences.py`, `tui.py` and existing
  recovery/base handlers. Observations and compatible lookup share data/comparison contracts;
  scheduling is optional to a manually checked UI; environment journals do not participate in
  base refresh; GitHub/pipx inspection does not consume base builds. These findings support the
  revised technical dependencies, not new product-operation evidence.
- Grouped UP-07 + UP-08, UP-10 + UP-09 (UI independently first), UP-12 + UP-13 and UP-14 + UP-15;
  kept all IDs and acceptance criteria, reducing planned remaining cycles from thirteen to nine.
  Removed the three artificial dependencies and blanket stage-order gating. Kept UP-11, UP-16
  and UP-17 separately scoped, with independent replacement-success/failure-recovery gates.
- D-057 records the owner's workflow revision and supersedes the older one-ID/STOP instructions
  for this effort; machine/security/publication permissions are unchanged. Updated TODO and
  BASELINE. This documentation checkpoint is followed by UP-06 in this execution cycle, not an
  unnecessary STOP. No code/schema/version change or release work.
- Verification: Python 3.11.18/current dependencies, `PYTHONPATH="$PWD/src"
  .work/venv311/bin/python -m pytest -q tests/test_language.py tests/test_user_docs.py
  tests/test_cli_structure.py --basetemp=/tmp/opencode/up-plan-revision`: **27 passed, no skips**,
  5.55 s. Document language/links/CLI checks, not a full suite or new real-operation evidence.
  Reviewed dependency/acceptance preservation; whitespace checks clean. Planned local commit:
  `docs: consolidate Updates work packages and dependencies`.

### UP-06 — 2026-10-30 — category-owned advisories and progress-safe clearing

- Continued after the owner-requested consolidation checkpoint `fae56f3`, without a redundant
  STOP/Continue. UP-06 remains a coherent UI-correctness package; observations/discovery and new
  Updates actions were not folded into this patch. Git started clean at UP-05 `32861c6` before
  the planning changes; no unrelated user changes were present.
- Reproduced a missing-image warning followed by successful explicit Refresh at 80x24 and
  100x30: **2 failed**, 1.51 s, before patching. Root cause: `_prerequisites_worker` filtered out
  passing image results and did not publish success, while `_show_image_checks` only added
  notifications. Other clearing paths guessed status ownership from rendered-text prefixes and
  removed notifications by shared title, risking unrelated notices and operation progress.
- The worker now publishes complete image results. Resource/image phase exceptions become
  `not checked` in their own category rather than a false daemon failure, and independent checks
  continue. If daemon verification fails, downstream checks remain skipped, not marked passed.
  `tui_runtime.publish` and its cancellation/app-liveness guards are unchanged.
- A small UI-local category map owns notification objects and advisory summaries. Warning/unknown
  results replace only their category; success clears it. Unknown is not a fresh success or a
  missing-image claim. Same-title unrelated notices are not owned and remain. Notice registration
  is synchronous on the UI thread using Textual's existing notification collection/refresh path,
  so same-turn warning then success cannot enqueue an obsolete toast afterward. No persistent
  cache, metadata/schema field or general notification framework was added.
- Explicit status ownership replaces prefix guessing. Active mutation progress is guarded;
  clearing cannot erase a completed operation/recovery result. If an advisory owns the line,
  clearing reveals remaining daemon, resource then image advisories, or Ready. Readiness waits
  retain per-worker messages and their own notification; the last cleanup restores a remaining
  advisory only if readiness still owned the line, never an active mutation's status. A replaced/
  canceled worker cannot publish obsolete image warnings. Metadata-only refresh stays Docker-free.
- Added **26 regressions**: two original-image reproducer cases in `test_image_readiness.py` and
  24 in `test_advisory_tui.py`. Both 80x24 and 100x30 cover repeated/same-turn warning, unknown,
  new warning and success, overlapping categories and waiters, unrelated same-title notices,
  expired/dismissed notice cleanup, mutation progress/failure-result preservation, phase-specific
  unknown/error results, skipped checks, no-Docker metadata refresh and late canceled publication.
  Tests use mocked checks/Docker, real isolated metadata and Textual pilots; worker completion
  and events make transitions deterministic rather than depending on long sleeps.
- New regression exposed an additional same-turn readiness-toast race: **79 passed/2 failed**,
  10.00 s. A queued readiness toast could appear after its cleanup had run. Applied the same
  owned-object/synchronous registration boundary to that existing notice; no unrelated toast is
  removed. Two intermediate affected runs found single Ruff SIM102 failures (**167 passed/1
  failed**, 15.03 s; **191 passed/1 failed**, 19.96 s); combined nested conditions, no suppression.
  These were rerun in all final suites, not skipped or relaxed.

  | Full suite / venv | Result / basetemp |
  |---|---|
  | Python 3.11.18, Typer 0.27.3/Textual 8.2.8, `venv311` | **1201 passed, 62 opt-in skips**, 105.94 s; `/tmp/opencode/up06-full311` |
  | Python 3.11.18, Typer 0.16.0/Textual 4.0.0, `venv311low` | **1201 passed, 62 opt-in skips**, 103.94 s; `/tmp/opencode/up06-full311low` |
  | Python 3.14.8, current, `venv314` | **1201 passed, 62 opt-in skips**, 106.52 s; `/tmp/opencode/up06-full314` |
  | Python 3.14.8, lowest, `venv314low` | **1201 passed, 62 opt-in skips**, 104.42 s; `/tmp/opencode/up06-full314low` |

  Serial foreground commands: `PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q
  --basetemp=<above>`, pytest 9.2.0. Includes mocked Docker, real host files/Git/local processes,
  Textual pilots, existing host terminal fixtures, Ruff/shellcheck, English, links/anchors and
  CLI/help consistency. Only the two known lowest-Typer/Click deprecations. The 62 skips are
  real/privileged/socket-activation opt-ins, not waived failures.
- Local Python 3.11 sdist/wheel built with `python -m build --no-isolation --outdir
  .work/up06-package` (log `.work/up06-package-build.log`); strict twine and `check_dist.py` pass.
  Changed product module `tui.py` is byte-identical in the wheel. No install or upload. Reviewed
  product/test/document diffs, notification ownership, status precedence and source-error bounds.
  Core lifecycle/runtime identity/base locks/worker publication/assets/dependencies/workflows/
  manager version and schemas are unchanged from UP-05.
- Ending read-only own-rootless inventory matches the initial inventory: zero containers/volumes,
  same four original full tagged-image IDs. No real Docker resources created/changed/deleted,
  no cleanup required. Not re-established: real-Docker mutations/OpenCode, isolated pipx, new
  advisory-specific real-terminal/pty or manual observation, privileged/socket-activation or
  provider calls. Prior real evidence is not relabelled as new UI evidence. Package checks are
  local only; no release readiness, merge, push, publication or version bump.
- Updated Unreleased, dashboard guide, TODO, architecture, baseline, campaign qualification,
  D-056 implementation status and this record. UP-16 now explicitly depends on both discovery
  and classification in the grouped UP-14 + UP-15 package (exact target plus install identity),
  not just classification. **UP-00..UP-06 complete; next UP-07 + UP-08 together.** Eight planned
  packages remain. Planned local commit: `fix: clear category-owned dashboard advisories`.
  Stop at this completed package boundary after recording final document checks and committing.
- Final evidence-document subset initially **109 passed/1 failed**, 17.22 s: a planning commit
  hash in BASELINE violated the existing public-record/internal-reference rule. Removed the hash
  from BASELINE and retained traceability here, without changing the test or its scope.
- Final repeat: **110 passed, no skips**, 17.32 s, Python 3.11.18/current dependencies,
  `PYTHONPATH="$PWD/src" .work/venv311/bin/python -m pytest -q tests/test_advisory_tui.py
  tests/test_image_readiness.py tests/test_diagnostic_tui.py tests/test_quality.py
  tests/test_language.py tests/test_user_docs.py tests/test_cli_structure.py
  --basetemp=/tmp/opencode/up06-docs-rerun`. Final whitespace checks clean. UP-06 complete;
  stop after local commit, then resume the grouped UP-07 + UP-08 package from this handoff.

### PERF — 2026-10-30 — test performance investigation

- Owner-requested one-time diagnostic/workflow task between UP-06 and UP-07/UP-08. Recovered
  clean `work/updates` at `d7e587e`, instructions, test/CI configuration, fixtures, CONTRIBUTING,
  BASELINE, release rules and recent evidence. UP work remains intact; UP-07/UP-08 did not start.
  Read-only own-rootless inventory matched UP-06: zero containers/volumes, same four full tagged
  image IDs. No real Docker mutation or new privileged/service/network permission was needed.
- Report and durable recommended cadence are in
  [BASELINE](../BASELINE.md#test-performance-and-local-verification); CONTRIBUTING links there.
  Tests remain serial/foreground, function-isolated and fully collected; no CI/release gate change,
  dependency installation, parallel runner, cross-test cache or shared mutable fixture introduced.
- Primary environment: four-CPU Arch VM, kernel 7.2.11, Python 3.11.18, pytest 9.2.0,
  Typer 0.27.3/Textual 8.2.8, Click 8.5.0/Rich 15.0.0. Reused verified venvs; `pip check` passed.
  Other endpoints: Python 3.14.8 and lowest Typer 0.16.0/Textual 4.0.0. Ruff 0.17.3,
  shellcheck-py 0.11.0.1, pyte 0.8.2; workflow tools actionlint 1.7.12/zizmor 1.31.1.
- Ignored evidence/scripts: `.work/test-perf/measure.py` records external monotonic wall time,
  child user/system CPU, maximum RSS, argv and exit status to JSON plus logs. `perf_probe.py`
  records collection, test phases, fixture setup and inclusive process/sleep/fsync observations;
  `cli_queries.py` records parser inputs/results; `analyze.py` aggregates XML. These are temporary
  diagnostic instruments, not a new test framework or shipping dependency. Profiling elapsed
  times are not mixed into the before/after sample. Artifacts stay under `.work/test-perf/`;
  test basetemps are fresh `/tmp/opencode/perf-*` paths. No uploaded logs/credentials.

  | Run labels | External wall / pytest time | Result |
  |---|---|---|
  | `baseline-a`, `baseline-b` | 108.08/107.18 s; 107.26/106.37 s | Each 1201 passed, 62 opt-in skips |
  | `probe` (diagnostic full run) | 107.82/106.88 s | 1201 passed, 62 opt-in skips; setup 1.59/call 99.76/teardown 4.78 s |
  | `collect-a`, `collect-b` | 0.50/0.29 s; 0.59/0.32 s | Each 1263 collected, no execution |
  | `tui-probe` | 35.21/34.80 s | 50 passed; 39 settle calls, 12.7 s explicit delay, 14.86 s including pilot pauses |
  | `cli-before-a/b` -> `cli-after-a/b` | 4.56/4.63 s -> 0.60/0.62 s wall | Each 8 passed |
  | `http-before-a/b` -> `http-after-a/b` | 5.46/5.46 s -> 2.05/2.04 s wall | Each 40 passed |
  | `after-a`, `after-b` | 99.36/98.48 s; 98.95/98.10 s | Each 1201 passed, 62 opt-in skips |
  | `affected311low`, `affected314`, `affected314low` | 5.16/4.93 s; 4.97/4.68 s; 4.99/4.69 s | Each 80 passed, no skips; only known lowest-Typer deprecations |
  | `docs-after-a/b` | 1.90/1.68 s; 1.84/1.63 s | Each 27 passed |

  Reproducible default-suite command (repeat with a new label/basetemp; no opt-in real flags;
  Bash's `time` reports external wall/CPU independently of pytest):

  ```sh
  time env PYTHONPATH="$PWD/src" .work/venv311/bin/python -m pytest -q --durations=40 \
    --junitxml=.work/test-perf/baseline-a.xml --basetemp=/tmp/opencode/perf-base-a
  ```

  The local wrapper invocation was `.work/venv311/bin/python .work/test-perf/measure.py
  baseline-a .work/venv311/bin/python -m pytest -q --durations=40
  --junitxml=.work/test-perf/baseline-a.xml --basetemp=/tmp/opencode/perf-base-a`.
  It explicitly disables real Docker/privileged/socket opt-ins in its child. `baseline-b` and
  `after-a/b` use corresponding labels/basetemps; collection uses `--collect-only -q`.
- Baseline source remained untouched until two full runs, fixture/process profiling, targeted
  repeat timings and CLI query capture established the bottlenecks. CLI cProfile: 1328 helper
  graph builds, 1400 total Typer graph builds including actual CLI invocation; after the patch
  seven fresh per-test graphs, 79 total. Existing help invocations and negative option tests remain.
  All **708 ordered parser query inputs/results are exactly equal**, before/after documentation
  changes. Graphs are read-only within one function-scoped test, never reused across tests.
- HTTP fixture: seven ordinary teardowns spent 0.45–0.50 s waiting for the default server shutdown
  poll. Changed only fixture poll interval to 0.01 s and joined/closed owned resources; measured
  0.004–0.007 s afterward. Request/error/oversize checks and all assertion/deadline/delay values
  remain; timeout teardown stays 1.22 s. No HTTP probe replaced with a mock or faster response.
- Compared JUnit XML: all **1263 ordered test IDs and pass/skip outcomes identical** across both
  baselines, diagnostic full run and both after runs. Mean full external wall 107.67 -> 99.16 s,
  8.51 s/7.9% observed improvement; changed modules explain about 7.4 s and the rest includes
  ordinary variability. User+system CPU means 38.38 -> 33.12 s. Collection/ordinary isolation
  setup/static tools are small, so shared fixtures/caching/parallelism are unjustified now.
- Affected endpoint command: `PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q
  tests/test_cli_structure.py tests/test_opencode_versions.py tests/test_quality.py
  tests/test_language.py tests/test_user_docs.py --basetemp=<distinct short path>`. Those three
  other combinations are focused evidence only, not new full regressions. Final primary full
  runs include original safety, host-file/process/terminal, CLI/TUI and static/document coverage.
- Ancillary measurements passed: local no-isolation build 0.68 s, strict twine 0.15 s, package
  content 0.05 s, actionlint 0.02 s, offline zizmor 0.09 s; the latter small tools are single-run
  indications, not repeated benchmarks. Python startup 0.007 s, `pip check` 0.21 s. No cold install,
  hosted provisioning or agent/tool latency measurement; no invented attribution of that time to
  test bodies. Ruff/shellcheck are already in the full suite. Avoid duplicate checks on identical
  inputs; recheck changed documents, not all unchanged behavior just to update evidence prose.
- Deferred proposals, not implementation permission: replace individually measured unnecessary
  pilot waits with bounded condition/worker completion, retain negative timing windows and real
  signal/race/archive behavior. The suite is already practical (~100 s); no global delay change,
  xdist, session-mutable fixture or automatic broad test selection. UP-07/UP-08 remains high-risk
  shared observation/policy/lifecycle work: full compatibility and affected real gates remain.
- Local package/static checks only; no new real Docker/OpenCode, installed-manager/pipx,
  model-provider, manual terminal or release evidence. Original release matrix and all completed
  UP acceptance criteria stay intact. Stop after this one-time checkpoint; next UP-07 + UP-08.
- Reviewed both test diffs and the report/cadence, retaining every original test/assertion and
  function-scoped isolation. Final affected-plus-document repeat: **80 passed, no skips**,
  Python 3.11/current, 5.03 s external/4.79 s pytest, `/tmp/opencode/perf-final-focused`.
  Product sources, schema/version/assets, pyproject, CI, AGENTS and RELEASING are byte-unchanged
  from UP-06. No failing test was suppressed; no production benchmark shortcut. Planned local
  commit: `test: remove measured verification overhead and document cadence`.
- After report/classification-only edits: **27 passed, no skips**, 1.84 s external/1.60 s pytest,
  `tests/test_language.py tests/test_user_docs.py tests/test_cli_structure.py`, primary venv,
  `/tmp/opencode/perf-final-docs`. This is focused document evidence, not a replay of the full
  suite. Ending verified daemon inventory is unchanged: zero containers/volumes and the original
  four full tagged-image IDs; no Docker resources created/changed/deleted, no cleanup needed.
  Ignored benchmark logs/XML/profiles remain local for reproducibility. Whitespace checks clean.

### UP-07 + UP-08 — 2026-10-30 — shared evidence, compatible discovery and policy comparisons

- Recovered clean `work/updates` at `6b53f46`, repository/local permissions, D-056/D-057, TODO,
  BASELINE/ARCHITECTURE and the full package acceptance gates. Own-rootless read-only inventory
  reconciled: zero containers/volumes and the four original full tagged-image IDs. PERF remains
  complete; no further performance work, scheduling, Updates screen or manager updater started.
- Reproduced **four failures** before patch in `tests/test_version_observations.py`: stopped
  history lost, explicit Manual/Pinned comparisons suppressed, incompatible npm latest metadata
  preventing supported stable selection. Root causes: runtime-only return value, notification
  policy conflated with requested information, and lookup of only the npm latest endpoint.
- `update_cache.py`: private bounded per-key atomic disposable files under `BASE/update-cache/`;
  no-follow/owner/mode/regular-file/single-link checks, no path repair, corrupt/non-finite/future
  data as misses, separate success and attempt, no mutation-lock acquisition or journal authority.
  Missing/unwritable caches cannot turn a verified operation into failure. Format 1 is a disposable
  cache record, not a metadata/backup schema. No cross-process coalescing/scheduling yet (UP-09).
- Environment observations bind source/value/time to data directory, verified endpoint, stable
  environment ID, full container/image IDs and a creation/derived-image/update-history fingerprint.
  Existing ownership is checked, the probe uses immutable ID, and post-probe identity/lifecycle is
  rechecked. Stop/policy/status changes retain dated history; replacement, restore's new ID,
  rollback, failed/interrupted update and pending journals invalidate or qualify it. No creation
  label or completed-update field is treated as current binary evidence. Docker failure may show
  only explicitly unverified history; readiness never passes a failed or merely historical check.
  Successful and same-version updates retain their actual verification time after journal closure.
- Image observations distinguish build labels from immutable real-probe evidence; ordinary
  image inventory runs no helper. Explicit helper checks bind immutable image IDs, keep UP-05
  deadlines/owned cleanup and retain original evidence on failure. No core lifecycle rewrite,
  schema change, metadata cache fields or new recovery engine was needed.
- npm uses one isolated bounded stdlib child with abbreviated package metadata, not host npm.
  Live payload measurement: **2,061,815 bytes / 1436 versions**; selected 8 MiB finite response
  limit with the existing eight-second total request budget (parent output cap allows small
  diagnostics). Semantic supported-major stable selection ignores other majors/prereleases;
  explicit compatible alternatives remain possible. Only the selected result/attempt is cached.
  Fresh failures never silently authorize cached-latest installation. Retry-After numeric/date
  pauses survive subsequent callers; final review removed an early seven-day clipping assumption
  so longer valid server delays are also respected. Unsupported/malformed targets still refuse.
- `comparison`, `update_blocker`, exact resolution and frozen environment plans are shared handler
  contracts, not a universal executor. Explicit Manual/Pinned comparisons do not change policy.
  CLI environment/base consent sees the exact resolved version, never `latest`; the environment
  executor revalidates target/identity/state/pin/network/journal under its existing lock. Base
  identity/refresh-mode consent remains UP-12/UP-13. No implicit stop, pin/network change or start
  for ordinary discovery. Existing candidate/base guards, journals, checkpoints and rollback stay.

  | Final layer | Command / result |
  |---|---|
  | Full Python 3.11/current | 1326 passed, 64 opt-in skips, 104.90 s |
  | Full Python 3.11/lowest | 1326 passed, 64 opt-in skips, 101.11 s; known two Typer deprecations |
  | Full Python 3.14/current | 1326 passed, 64 opt-in skips, 103.97 s |
  | Full Python 3.14/lowest | 1326 passed, 64 opt-in skips, 100.65 s; known two Typer deprecations |
  | Scoped real final | `test_43_diagnostics.py test_44_version_evidence.py`: 4 passed, 72 logged checks, no skips/deselections, 150.84 s, `up0708-final` |

  Full commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q --tb=short
  --junitxml=.work/up0708/verified-<label>.xml --basetemp=/tmp/opencode/up0708-verified<label>`;
  venv/label pairs `venv311/311`, `venv311low/311low`, `venv314/314`, `venv314low/314low`.
  Ran serially, foreground; logs/XML under `.work/up0708/`. Python 3.11.18/3.14.8, pytest 9.2.0,
  current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0; all four `pip check` runs clean.
  New default-suite cases: **125**; original mocked, real-host/files/Git/process/terminal,
  concurrency/security/lifecycle/backup and static/doc assertions retained. 64 skips are the
  prior 62 opt-ins plus the two added real-Docker cases, not waived failures.
- Regression iteration remains visible: first affected iterations 6 failed/107 passed and
  3 failed/142 passed exposed identity mocks/expected policy output and import/type lint issues;
  first full run 4 failed/1201 passed/62 skipped exposed readiness and a rollback mock. Corrected
  without weakening product checks. A later 250-case focus and 1385-item full run each found one
  import-order lint failure (249/1320 passed respectively); corrected. Final cache review added
  non-finite/serialization/expiry cases and a restore extension; its focus found one test-only
  archive-selection lint issue (163 passed), fixed. Four complete suites were rerun on each
  reviewed product checkpoint; only the final 1326-result matrix above is final-code evidence.
- Real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up0708-final
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_43_diagnostics.py
  tests/integration/test_44_version_evidence.py --junitxml=.work/up0708/real-final.xml
  --basetemp=/tmp/opencode/up0708-final-real`. Initial run `up0708-real`: **2 passed/2 failed**,
  new test lacked the existing real-session/identity marker opt-outs from unit isolation; fixed
  locally, no isolation fixture was relaxed. `up0708-proof`: **4 passed/68 checks**, 156.73 s;
  final restore-extended run above **4 passed/72 checks**. The final subsequent source-only
  Retry-After correction does not change these real paths and is covered by the final four
  suites' actual loopback HTTP long-delay case.
- Both real distributions used retained bases (Debian 12/revision 1, Arch/revision 1), not fresh
  definitions/builds. Actual 2.2.0 -> explicit 2.1.4 install -> checkpoint rollback, no-install
  same-version, SIGKILL before install/recovery, runtime recreation and file-only backup/restore,
  no stopped startup and pin/network-none refusal passed. System/home/workspace markers and
  user configuration survive; actual version evidence, not inherited labels, follows updates.
  Diagnostic deadlines/cancellation/missing-tool restoration/owned-helper leak checks still pass.
- Live bounded `latest()` in isolated `.work/up0708/npm-data` selected **2.2.4**, source/time/
  successful attempt retained. Public major rollover, outage and rate limits were not observed;
  those use mocked metadata or real loopback HTTP. No credentials/provider/paid API use.
- Three real manifests/logs: `.work/logs/up0708-{real,proof,final}*`; guarded product cleanup and
  leak assertions passed each time, including failed attempts. Ending verified daemon has zero
  containers/volumes, no run helpers and unchanged original full tagged-image IDs. Test checkpoints,
  snapshots and runtime images removed only through guarded cleanup. Logs, isolated caches and
  two manifested file-only backup directories stay in ignored `.work/`; no upload or host changes.
- User guide/README/Unreleased and ARCHITECTURE/BASELINE/CAMPAIGN/D-056/TODO updated for delivered
  behavior and limits. No new real-terminal/manual UI, full real campaign, fresh base, installed
  pipx/manager, privileged/socket/service or release verification claimed. Same-user external
  Docker changes cannot be excluded by cache/locks; no scheduling/coalescing yet. At the tested
  package boundary, commit locally and STOP. Next is UP-10 + UP-09; implement manual/cached UI
  first, independent of optional scheduling. No release, version bump, merge, push or publication.
- Final packaging: `.work/venv311/bin/python -m build --no-isolation --outdir
  .work/up0708/package-final`; strict twine and `.github/scripts/check_dist.py` passed. All six
  changed/new modules byte-identical in the wheel: `cli.py`, `opencode_versions.py`,
  `http_probe.py`, `probes.py`, `readiness.py`, `update_cache.py`; hashes recorded in
  `.work/up0708/verified-source-sha256.json`. No install/upload. Core lifecycle, identity proof,
  base-lock protocol, diagnostics runner, image assets, version, schemas, dependencies, CI,
  AGENTS and RELEASING are byte-unchanged from the prior checkpoint.
- Final review of the outcome XML found three future-time tests had import-time timestamps in
  their parameter IDs; gave them stable `future` IDs without changing values/assertions. All
  1390 full-suite outcomes agree across the four combinations after normalizing only those three
  old IDs. New-test + quality/language/links/CLI repeats on the final test/document tree:
  **165 passed** per combination, 8.60/8.49/8.60/8.43 s (311/311low/314/314low), no skips;
  exact ordered IDs/results identical. Earlier prose-only quality/document subset: 40 passed,
  2.97 s. These are focused follow-ups, not newly claimed full suites. Logs/XML:
  `.work/up0708/focused-<venv>.*`; selected all four new default-suite modules plus
  `test_quality.py test_language.py test_user_docs.py test_cli_structure.py` with the corresponding
  verified venv and `/tmp/opencode/up0708-doc-<venv>` basetemp. Whitespace checks clean.

## Resume and context-compaction handoff

1. Read repository/local instructions, TODO, BASELINE, D-056/D-057 and this entire record. Use
   ARCHITECTURE for implemented behavior, not proposed functionality. Check Git status, branch,
   log and scoped Docker state; preserve unfamiliar changes and reconcile them before editing.
2. Expected branch: `work/updates`, UP-00 `3552f67`, UP-01 `d7d6a1f`, UP-02 `4ea5050`, UP-03
   `40211ab`, UP-04 `8291e9c`, UP-05 `32861c6`, consolidation `fae56f3`, UP-06 `d7e587e`,
   PERF `6b53f46`, then the UP-07/UP-08 package commit. Recover PERF's measured verification cadence from
   BASELINE; it does not reduce the shared/high-risk or real gates for the next package.
    Shared base guards, immutable explicit rollback, short diagnostic/probe bounds/ownership and
    category-owned advisory clearing, identity-bound evidence/discovery and exact targets are
    implemented. Image assets, manager
   version and schemas still match the seed.
   Resolve actual Git state; later evidence takes precedence. Shared private lock files are
   persistent protocol state, not stale files to delete. Retained bases are unchanged. The
   packaged-definition DNS gate is resolved by UP-04 evidence, not still blocked.
3. Select **UP-10 + UP-09**, implementing UP-10's independently useful manual/cached Updates UI
   first: replace Versions with three compact local/cached-first subviews (Manager, Bases,
   Environment OpenCode), retain `v`, explicit Check/Details, independent errors/loading, reasons
   for unavailable actions and 80x24/larger keyboard/focus/Cancel behavior. Use the implemented
   source/time/identity/discovery/eligibility contracts; do not parse readiness strings or use
   build labels/history as runtime proof. Opening the new screen must not query the network.
   Avoid image helpers for ordinary inventory and never start stopped containers implicitly.
   Manager discovery/classification/execution and component action packages remain separate;
   do not present pending capabilities as working or bypass existing handlers/recovery journals.
   Only after the manual/cached UI is verified, add optional default-off UP-09 scheduling if the
   cycle remains manageable: at most one attempt per source/24h including failures/restarts,
   persisted attempts, coalescing/rate limits and quiet deduplication, no daemon/install/start.
   Cache is per-key atomic storage, not yet an in-flight coordinator. No discovery-cache lock
   may be held while acquiring mutation locks. If split, stop after tested UP-10, not on an
   unverified combined UI/scheduler. Preserve UP-05 publication/bounds, UP-06 status ownership,
   exact plans, schemas, pins, base guards and journals. No new host/service/network permission.
4. Follow task-local reproducer -> root cause -> narrow patch -> regression -> rerun. Update user
   docs and current-state records only for what actually changed; record exact evidence and
   outstanding layers here, with any needed new decision entry rather than editing history.
5. Review/stage only intended changes; commit locally. Record task status, test results, blockers
   and the next unblocked package/gate in this file before committing, so the commit is self-contained.
   Related subtasks may continue within the approved package after a focused commit. At the package
   or safety boundary leave a clean checkpoint, summarize actual commits/tests/limitations, then STOP.
6. Never infer permission to merge, push, tag, publish, bump the version or start release work
   from Continue, task completion, passing tests or the end of this roadmap. Additional unrelated
   stabilization work is expected before a human separately considers another release.
