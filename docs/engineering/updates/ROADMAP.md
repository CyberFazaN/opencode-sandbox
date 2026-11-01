# Updates — approved architecture, implementation roadmap and handoff

## Status and authority

- **UP-00..UP-16 and PERF complete. UP-17 partial: source/origin-consent, frozen post-exit/exclusive local replay, durable startup barrier, independent tool/dependency/source/effective public-default client-policy diagnostics, and separate expected-file/runtime/CLI-health primitives verified. Actual replacement, post-replacement results and failure/interruption recovery remain pending. Manager Update stays disabled.**
  PERF measures/optimizes test-local repeated work, not product behavior or verification gates.
  UP-00 persisted the plan; UP-01 fixes report
  subjects/Agent Context presentation; UP-02 preserves independent local/registry inventory
  results; UP-03 implements shared base guards; UP-04 implements identity-bound explicit rollback
  selection; UP-05 bounds short diagnostics and owns client/probe cleanup; UP-06 replaces/clears
  category-owned advisories without erasing active progress; UP-07/UP-08 add identity-bound
  evidence, disposable caches, compatible stable resolution and exact targets/comparisons.
  UP-10 delivers the manual/cached compact Updates UI; the approved package is split after
  this verified checkpoint because of its UI/real-terminal scope. UP-09 now completes optional
  default-off daily npm discovery, durable attempt claims, shared requests and quiet indicators.
  UP-11 adds explicit environment actions/immutable consent and verified checkpoint recovery;
  UP-12/UP-13 add base build/rollback and explicit cached/full-refresh modes with verified
  publication/copies and terminal ownership. UP-14/UP-15 add independent read-only published
  manager discovery/local pipx classification; manager Update remains disabled.
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
| Versions is only a report (inventory fixed in UP-10) | At UP-00 it queried npm on opening and offered only Close | Now three compact local/cached-first views, independent explicit checks and Details; component mutation bindings remain later packages |
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

UP-00..UP-16 and the one-time PERF checkpoint are complete. UP-16 has verified startup/exclusion,
external tools, frozen helper/lifetime, dedicated runtime verifier and restored-terminal fixture/refusals;
UP-17's source and internal origin review/consent checkpoints are verified; independent exclusive
execution validation, effective installer network policy, replacement/failure recovery and UP-18
remain pending. D-057 consolidates closely related remaining
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
**nine remaining cycles at consolidation approval instead of thirteen** (UP-10 now split from
UP-09; two later packages remain after completing UP-16), not
a quota or permission to combine
unrelated risks. Read-only manager discovery can be developed independently of base refresh;
manager execution remains later and must not delay the earlier component workflows. UP-18 is
not release preparation. UP-00..UP-16 are DONE; UP-17 is PARTIAL and UP-18 remains PENDING.
Continue UP-17's independent replacement/verification and failure-recovery gates;
UP-11's independent environment recovery gate is verified. UP-03's initially DNS-blocked
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
| UP-10 | DONE: compact manual/cached Updates inventory; approved split checkpoint | UP-01, UP-06, UP-07 + UP-08; **no UP-09 dependency** | Three local/cached-first views, independent manual checks/errors/progress, Details and keyboard/focus/Cancel at 80x24/larger; no network/probe on opening or premature manager execution. 39 new default-suite cases, four complete compatibility suites and real terminal/Docker/OpenCode evidence below. Component mutations stay pending |
| UP-09 | DONE: optional background discovery | UP-07 + UP-08; delivered UP-10/preferences for presentation | Default-off dashboard-only npm discovery, durable attempt-based 24-hour claims including failure/restart/interruption, cross-caller/process source coalescing, numeric/date/long Retry-After and quiet policy-filtered indicators. No start/probe/install; manual UI stays usable when off/unavailable. 42 new default-suite cases, four full compatibility suites and 12 affected real tests/200 checks; evidence below |
| UP-11 | DONE: environment actions and independent recovery gate | UP-10, UP-07 + UP-08 | Existing Check/Start/Policy/Update/Rollback/Recover handlers, immutable exact consent/locked revalidation, live refusals, app-owned non-cancelable mutations, persistent journal/recovery routing. Four full suites (1471 passed/78 skips each), 18 affected real tests/400 checks including actual update/full-layer rollback and independent missing/failed/successful recovery on both distributions. Evidence below; no base/manager bundling |
| UP-12 + UP-13 | DONE: base actions and explicit cached/full-refresh rebuild | UP-03, UP-04, UP-07 + UP-08; UP-10 for TUI binding only; **no UP-11 dependency** | Build/Rebuild/Check/Rollback, identity/target/definition/mode consent, candidate-ID verification/guarded publication, retained copies and explicit multi-copy selection; cached versus pull/no-cache refresh, no prune/migration. Four complete suites (1525 passed/80 skips each), 24 affected real tests/581 checks, both distributions including separate cached/full-refresh package builds, concurrency/pinned creation, failed candidates, retained layers and 80x24/larger terminal ownership. Evidence below |
| UP-14 + UP-15 | DONE: read-only manager discovery/local installation classification | UP-05; UP-07 + UP-08 for shared cache; UP-10 for TUI binding only; **no UP-13 dependency** | Official published-full-release provider, strict tags/numeric comparison/no downgrade, independent failures and local evidence, separate daily GitHub source/claims. Local actual package/VCS/pipx/Python/options/invocation/launcher/custom-location agreement; manual guidance for foreign/editable/shadowed/ambiguous/unsupported settings. 86 new default cases, four full suites (1611 passed/82 skips each), 26 affected real tests/637 checks including default/custom-space pipx and real manager terminals. Local provenance is not public commit authentication or an execution grant; Update disabled. Evidence below |
| UP-16 | DONE: independently verified non-mutating handoff/exclusion/access boundary | UP-14 + UP-15, UP-05 | Startup/process-lifetime usage/exclusion (`2e6d2d0`), independent existing tools/full routes/raw RECORD/source-Python (`462d8fe`), frozen stdlib helper/actual origin exit with target absent (`35c035a`), dedicated runtime query/unlocked witness/live owner proof/parent-death safety (`14112de`), then internal restored-terminal fixture/refusals. Actual-body tracking survives task cancellation, sessions/operations/open consent refuse, full Linux driver shutdown and exact original foreground tty checked before arming; origin still leased until actual death. Four complete suites (1861 passed/84 skips each, 1945 identical ordered outcomes), 29 affected real tests/872 checks, installed pipx/real tty/both-distro mutation/session/other-manager evidence. No public trigger, updater, source/target consent or replacement/recovery exposed; Manager Update stays disabled |
| UP-17 | PARTIAL: exact source and internal origin review/consent checkpoints verified; exclusive validator/replacement/recovery pending | UP-16 | Exact release/ref/peeled-commit/fresh same-target observation and separate source/discovery claims, then immutable origin installation/tool/source/public-network review, explicit 80x24/larger consent and fresh origin-side revalidation. Second gate: 79 new default cases, four complete suites (2038 passed/84 skips each, 2122 identical ordered outcomes), same affected 29 real tests/954 checks with both installed pipx layouts/real pty/refusals. Still requires independent post-exit/exclusive installation/tool/source/network validation, effective installer network policy, actual replacement and expected source/version/commit/launcher/basic-CLI verification. Independent failure/interruption/private recovery record/instructions gate; no automatic restart or inferred backup/rollback safety |
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

### UP-10 — 2026-10-30 — independently useful manual/cached Updates UI

- Resumed clean `work/updates` at `cacffea`; read contract/local permissions, TODO, BASELINE,
  ARCHITECTURE, D-056/D-057 and the running roadmap. Verified own-rootless daemon: no containers
  or volumes, same four original full image IDs. No unrelated user changes or new host authority.
- The approved UP-10/UP-09 package is **split at UP-10**. This screen/data/worker integration and
  its real-terminal findings are substantial enough to warrant an independently verified commit.
  No scheduling/preference was started. UP-09 is next, not silently marked complete, and the
  manual UI remains useful with it absent. UP-11/recovery and manager/base action packages remain
  distinct; no mutation handler is bypassed or represented as implemented UI.
- Minimal reproducer: changed `test_no_registry_call_until_requested` to assert that opening `v`
  does not invoke npm: **2 failures** before implementation, both observed an unwanted request.
  Root cause: old action awaited one combined active inventory/npm report before presentation.
- New `updates_tui.py`: Manager/Base Images/Environment OpenCode subviews, retained `v`/toolbar,
  stable per-view selection, one compact responsive table and selected summary, explicit Check,
  full plain read-only Details, keyboard focus/Enter/Tab/Esc and owned Cancel/Close. Installed
  manager version is local; release/installation eligibility is explicitly not assessed. Disabled
  mutation controls explain the staged limit; Details retains existing CLI capabilities/guidance.
  Metadata state is not actual Docker state; base labels are not binary evidence or OS freshness.
- `environment_history` reads qualified cache without Docker; `environment_version(check=False)`
  inspects state/identity/cache without executing OpenCode or recording attempts. Defaults preserve
  active CLI/readiness checks. Small consumer defect reproduced/fixed: a pending journal stays
  visible even if its container is absent. No executor, journal, schema or lifecycle rewrite.
  `updates.py` reads immutable base identity, declared OS/revision/build provenance and qualified
  image evidence without helpers. Missing/foreign/unknown/old/newer/different definitions do not
  authorize replacement. Selected explicit base Check uses the existing bounded immutable helper.
- Base/environment local inspections publish independently from npm. Explicit Check runs one
  selected-object probe and a separate npm request, coalesced only while in flight in this screen;
  both views share the result. Fresh/cached/failed source facts stay distinct, successful evidence
  retains its original time, full failures/empty-inventory discovery remain accessible in Details.
  Never starts stopped/never-created containers. Policy comparisons remain explicit information,
  not execution authority. Cancel/Close use UP-05 cancellation plus screen liveness and per-object
  generation tokens; no queued late/old inventory result replaces a newer Check/replacement screen.
- Real terminal found an actual UI defect absent from default headless pilots: existing dashboard
  advisory toasts covered lower controls (and Manager detail at 80x24). Updates now collapses only
  its toast-rack geometry, shows a compact notice count and full messages in Details, retaining
  notification/advisory objects and dashboard status ownership. The notice-count timer is UI-only;
  it does not perform discovery or touch Docker. Regression explicitly enables the production
  toast rack, rather than clearing advisories or assuming headless tests represent a real terminal.
- Failure/rerun trail: first affected run 5 failed/49 passed (four old report-shape assertions and
  an import-order lint failure), next 1 failed/111 passed (unused imports/test variable lint),
  then 50 passed. First full suite **1 failed/1360 passed/68 skipped**, 151.38 s: existing
  no-distribution-branches gate matched a new `for distro in` loop; renamed to surrounding `d`
  convention, with no weakened gate. Lowest-endpoint affected subset **181 passed**, 90.70 s.
  Toast reproduction iterations first exposed omitted pilot toast rack, then toolkit inline
  display overriding the first CSS approach; assertions stayed, geometry-based fix passes.
  Final reviewed UI/data/diagnostic/quality/docs subset **151 passed**, 61.92 s, before full matrix.

  | Final product-code layer | Result |
  |---|---|
  | Complete Python 3.11/current | 1365 passed, 68 opt-in skips, 153.47 s |
  | Complete Python 3.11/lowest | 1365 passed, 68 opt-in skips, 148.59 s; two known Typer deprecations |
  | Complete Python 3.14/current | 1365 passed, 68 opt-in skips, 152.04 s |
  | Complete Python 3.14/lowest | 1365 passed, 68 opt-in skips, 147.78 s; two known Typer deprecations |
  | Final scoped real Docker/OpenCode/terminal | **8 passed/136 logged checks**, no skips/deselections, `up10-verified`, 193.19 s |

  Full commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q --tb=short
  --junitxml=.work/up10/final-<label>.xml --basetemp=/tmp/opencode/up10-final<label>`;
  venv/labels `venv311/311`, `venv311low/311low`, `venv314/314`, `venv314low/314low`.
  Serial foreground, Python 3.11.18/3.14.8, pytest 9.2.0, current Typer 0.27.3/Textual 8.2.8,
  lowest 0.16.0/4.0.0, all four `pip check` runs clean. **1433 ordered IDs/outcomes exactly match**.
  39 new default-suite cases; prior assertions migrated for selected explicit checks/independent
  ordering rather than removed. Four new opt-in terminal cases explain 68 rather than 64 skips.
- Real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up10-verified
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_43_diagnostics.py
  tests/integration/test_44_version_evidence.py tests/integration/test_51_updates.py
  --junitxml=.work/up10/real-verified.xml --basetemp=/tmp/opencode/up10-verified-real`.
  First `up10-terminal`: four bodies completed but **4 teardown errors**, 34 passed/30 failed
  checks, 440.96 s. Besides overlays, the terminal harness sent Escape+next key together (an Alt
  sequence); split events, retaining every check. `up10-terminal-proof`: **4 passed/64 checks**,
  36.23 s. Reviewed-product `up10-final`: **8 passed/136 checks**, 162.51 s. Final harness review
  then added test-prefix/label/manifest recording for transient Check helpers, following test_43;
  no product change or source mock. Reran all eight in `up10-verified` above, with every helper
  manifested. No failed check is suppressed or inferred from a completed test body.
- Terminal source harness substitutes npm's URL with a real loopback HTTP server and names/labels/
  manifests transient probe resources. No public npm/GitHub or paid provider is contacted in
  terminal rows; HTTP transport/owned child and Docker/probes are real. Both retained distributions
  at 80x24/120x40 verify immediate Manager state, no request on opening/view changes, selected
  stopped history/comparison, visible primary controls, Details, cached success after HTTP 503,
  independent progress and keyboard Cancel, exact final stopped/StartedAt/byte-identical metadata,
  no helper leaks, normal Close/Q and terminal restoration. Lifecycle/probe rows retain actual
  2.2.0 -> explicit 2.1.4 -> checkpoint rollback, same-version verification, SIGKILL recovery,
  recreation/file-only restore invalidation, data/configuration markers and owned bounded cleanup.
  Inputs are retained Debian 12/revision 1 and Arch/revision 1, not rebuilt current definitions.
- Logs/XML in `.work/up10/`; all real manifests/logs `.work/logs/up10-{terminal,terminal-proof,
  final,verified}*`. Guarded product cleanup/leak checks ran in every attempt, failed or successful.
  Ending verified inventory has zero containers/volumes, no run helpers and the same four original
  full tagged-image IDs. Only test-owned snapshot/checkpoint/runtime resources were removed by
  guarded product cleanup. Backup/cache/terminal scripts/logs remain in ignored `.work/`.
- README/guide/Unreleased/engineering facts updated; dashboard illustration regenerated using
  the existing fake-data script. Legacy `test_50_tui.py` expectations now enter Environment view
  after `v`, but its complete broader workflow is not rerun in this scope. No new full campaign,
  fresh base build, installed pipx/manager, privileged/socket/service, provider/paid call or manual
  observation evidence. Version/assets/schemas/dependencies/CI/release gates unchanged. No release,
  version bump, merge, push or upload. Checkpoint locally and STOP after final package/doc checks.
- Final packaging: local `python -m build --no-isolation` sdist/wheel, strict twine and
  `.github/scripts/check_dist.py` pass; all four changed/new modules (`opencode_versions.py`,
  `tui.py`, `updates.py`, `updates_tui.py`) match wheel bytes. Hashes:
  `.work/up10/verified-source-sha256.json`; final artifacts `.work/up10/package-final/`.
  Final engineering/document/CLI/quality follow-up **41 passed**, 3.03 s, after the test-only
  helper-manifest extension; final prose-only follow-up separately recorded in the local log.
  No product changes after the full matrix; focused repeats are not extra complete suites.
  `git diff --check` clean. Core lifecycle, runtime identity, base locks, diagnostics/probes,
  worker adapter, cache storage, preferences, image assets, versions, schemas, dependencies,
  CI, AGENTS and RELEASING are byte-unchanged from `cacffea`.

### UP-09 — 2026-10-31 — optional daily metadata discovery

- Resumed clean `work/updates` at `8aa7df5`; read repository/local contract, TODO, BASELINE,
  ARCHITECTURE, D-056/D-057 and active handoff. Verified own-rootless inventory: no containers/
  volumes, unchanged four original full tagged-image IDs. No new authority, release work or
  unrelated task. Completed UP-09 only; UP-11 retains a separate cycle/recovery acceptance gate.
- Minimal daily success/failure tests **2 failed** before implementation: `latest` had no automatic
  attempt mode. Code investigation confirmed that per-screen npm sharing and per-key cache
  replacement could not exclude concurrent CLI/background/process requests. Existing failure and
  Retry-After records were retained, not replaced with a success-only freshness throttle.
- `latest(automatic=True)` now uses the same source coordinator as explicit lookup/target
  resolution. Source key includes npm URL and supported major; coordination is per configured
  data directory, not daemon/global state. A private persistent `flock` serializes only metadata
  requests and cache publication. Threads/processes arriving during an attempt reuse its result
  or failure, never a prior success after failure. Waits are bounded/cancellable; a canceled waiter
  cannot cancel its owner. Guards are released before any confirmation/executor/mutation lock.
- Under that guard, persist/fsync an attempt ID/start time and incomplete result before HTTP.
  The automatic 24-hour gate uses attempts, including failed/interrupted ones and future claims
  after clock rollback; future success still cannot become fresh installed/registry evidence.
  Explicit Check may refresh early but respects numeric/date Retry-After, including pauses longer
  than seven days. No early retry/clamp. Requests retain UP-05's actual eight-second bounded child
  transport, body/output limits and owned cancellation/reaping. No host npm/Node or model provider.
- `update_cache.write` can return persistence success and optionally fsync; ordinary runtime/image
  evidence remains disposable, without new fsync work. Source lock descriptors are private own-UID
  no-follow single-link regular files, descriptor-relative with post-acquisition namespace/inode
  checks; product never deletes/repairs lock files. Unsafe/unwritable lock/claim storage disables
  automatic HTTP. Existing explicit discovery keeps its bounded fallback without persistence;
  cross-process coalescing/throttles are not promised without usable storage. Cache clearing or
  corruption can reset disposable discovery history, never authorize mutation or clear recovery.
- `daily_discovery` boolean preference defaults off for old/missing/invalid values. Compact
  Preferences at 80x24/larger explains npm-only metadata/no probes/start/install and unimplemented
  manager discovery. Dashboard considers enabled work on startup/save and every 60 seconds,
  never installs a service or adds unsolicited network to short CLI commands. Turning it off
  cancels its owned worker and suppresses the optional indicator; manual Updates remains usable.
- `update_discovery.py` is only the npm dashboard adapter and Docker-free availability count,
  not a generic executor. Later GitHub/manager discovery must implement its source/attempt contract
  in UP-14; there is no speculative request or fake manager check. One stable `Updates (N)` label
  compares dated environment history only for Notify policy and no pending recovery. Manual/
  Pinned/Unknown/current/newer rows do not generate general newer-version indicators. No per-row
  or repeated availability toasts and no operation-status writes. Tooltip/Details qualify dated/
  stale discovery; schedule failures remain accessible in Details. Explicit comparisons stay
  policy-independent. Opening a screen does not trigger Check; its local-only timer adopts other
  callers' completed cache facts, preserves source time/Retry-After and shows truthful progress.
- Regression/review: **42 new default-suite cases**, no deleted/weakened existing assertions.
  Real private files/locks, actual HTTP child and loopback server, fresh subprocesses, SIGKILL
  after claim/before HTTP, overlapping threads/processes with shared success/failure, bounded/
  canceled waits, cancellation/reaping, clocks, numeric/date/long 429/503 pauses, unsafe/hardlinked/
  unwritable/fsync-failed storage, explicit fallback, guard release before exact-target execution,
  compatible preferences, policy filtering/deduplication/status ownership, open-screen adoption,
  no short-CLI network and compact pilot save/cancel/enable/disable. Initial focused iterations
  caught lint/import issues and a snapshot alias that could erase a mocked explicit UI result;
  fixed without weakening checks. Lowest affected run **1 failed/156 passed**, 45.35 s: existing
  internal-reference vocabulary gate matched a new test's recording variable/prose; renamed,
  not exempted. Reviewed subset **158 passed**, 48.39 s, before the initial complete suites.
  Work began 2026-10-30 and completed across midnight on 2026-10-31.

- Final review after an initial four-way **1406 passed/72 skipped** matrix (166.45/160.13/164.48/
  160.66 s) and **12 passed/200 checks** real gate (`up09-final`, 200.32 s) caught a freshness edge:
  cached-only background daily consideration also acquires a source guard. Contention alone is
  not proof of an in-flight HTTP attempt; explicit Check/target resolution must not reuse old
  successful evidence just because it waited behind that local read. Narrowed coalescing to a
  changed attempt or waited-on incomplete claim; added a deterministic real-lock regression.
  Post-correction focused review **56 passed**, 13.96 s. No target/consent fallback was added.
- The final-code Python 3.11/current full run passed. Next lowest run hit `/tmp` tmpfs inode
  exhaustion: **1 failed/1027 passed/72 skipped/379 setup errors**, 107.20 s. Filesystem had free
  bytes but only two free inodes. Retained full log/XML (`verified-311low.*`), manifested and
  removed only this conversation's exact UP-09 pytest basetemps (`temp-roots.json`/`temp-cleanup.txt`)
  to free 118k inodes. No older run, user project/data, image or Docker object was deleted.
  Reran remaining three complete suites and removed each completed own manifested basetemp;
  no product/test assertion/CI gate was changed or failure waived. Final-code results:

  | Final complete layer | Result |
  |---|---|
  | Python 3.11/current | **1407 passed, 72 opt-in skips**, 166.42 s |
  | Python 3.11/lowest | **1407 passed, 72 opt-in skips**, 160.50 s; two known Typer deprecations |
  | Python 3.14/current | **1407 passed, 72 opt-in skips**, 164.65 s |
  | Python 3.14/lowest | **1407 passed, 72 opt-in skips**, 159.91 s; two known Typer deprecations |
  | Scoped real Docker/OpenCode/terminal | **12 passed/200 logged checks**, no skips/deselections, `up09-verified`, 178.60 s |

  Full commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q --tb=short
  --junitxml=.work/up09/<prefix>-<label>.xml --basetemp=/tmp/opencode/up09-verified<label>`;
  venv/labels `venv311/311`, `venv311low/311low`, `venv314/314`, `venv314low/314low`.
  Prefix `verified` for 311, `verified-retry` for the other three final complete runs.
  Serial foreground, Python 3.11.18/3.14.8, current Typer 0.27.3/Textual 8.2.8, lowest
  0.16.0/4.0.0, pytest 9.2.0, four clean `pip check` runs. All **1479 ordered IDs/outcomes match**.
  Four new opt-in terminal rows account for 72 rather than 68 skips. No test gate is bypassed.
- Real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up09-verified
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_43_diagnostics.py
  tests/integration/test_44_version_evidence.py tests/integration/test_51_updates.py
  tests/integration/test_52_discovery.py --junitxml=.work/up09/real-verified.xml
  --basetemp=/tmp/opencode/up09-verified-real`. New test_52 uses the actual dashboard/Preferences,
  loopback HTTP and read-only Docker argv recording, with no mutation/transport/CLI mocks.
  Both retained distributions at 80x24/120x40 prove keyboard opt-in/out, persisted preference,
  single indicator, new dashboard processes after success/failure, explicit early refresh,
  default-off no network, no probes/starts/installs/other mutation in discovery rows, actual
  stopped/startup-time/metadata preservation and restored terminals on every normal quit.
- First new terminal run `up09-terminal-repro`: **1 body passed but 1 teardown error**, 13 passed/
  3 failed checks, 68.54 s. Unescaped `(1)` in `Term.wait_for` was a regex group, not literal text;
  corrected escaping without removing assertions. `up09-terminal-proof`: **4 passed/64 checks**,
  29.02 s; all four rerun again in final 12-case affected gate. Existing tests_43/44/51 retain real
  bounded probes, 2.2.0 -> 2.1.4 -> checkpoint rollback, interrupted recovery, recreation/file-only
  restore invalidation, preserved data/configuration, explicit manual image checks and terminal
  cancellation. Terminal HTTP fixtures are loopback-only, not public npm/GitHub/provider calls.
  Lifecycle rows use actual OpenCode installation; no fresh current-definition base build is claimed.
- All four real attempts have isolated roots, manifests/logs under `.work/logs/up09-*`, guarded
  product cleanup and leak checks, including the failed run. Final own-rootless inventory: zero
  containers/volumes/run helpers, same four original full tagged-image IDs. Only run-owned
  snapshots/checkpoints/runtime objects removed. File-only backups/cache/logs/scripts remain ignored.
  Tests use fresh short `/tmp/opencode/up09-*` basetemps; artifacts/logs/XML in `.work/up09/`.
- User/current-state records updated. No changed core lifecycle, identity proof, base guards,
  diagnostic/probe executors, worker adapter, manager version, schemas, assets, dependencies,
  AGENTS, CI or release gates. No full campaign, broad legacy test_50 workflow, fresh bases,
  installed pipx/manager, privileged/socket/service, model-provider/paid-call or manual-observation
  evidence. No version bump, merge, push, tag, upload or publication. Package/checkpoint locally,
  then STOP; UP-11's environment action/recovery gate is next, not part of this commit.
- Final packaging/source gate: local sdist/wheel, strict twine and packaged-content checks pass;
  all seven changed/new product modules match wheel bytes and their post-verification SHA-256
  manifest (`.work/up09/verified-source-sha256.json`). Final document/CLI/quality subset **41 passed**,
  3.01 s; not another complete suite. Artifacts `.work/up09/package/`, final documentation-bearing
  rebuild `.work/up09/package-final/`. No product changes after the final matrix/real gate.
  `git diff --check` clean; manager version, core lifecycle, identity, base guards, diagnostics/
  HTTP/probe executors, worker adapter, image assets, schemas, dependencies, AGENTS, CI and
  RELEASING are byte-unchanged from `8aa7df5`.

### UP-11 — 2026-10-31 — environment actions and independent recovery

- Resumed clean `work/updates` at `1aca6ca`; recovered repository/local instructions, roadmap,
  TODO, BASELINE, ARCHITECTURE and D-056/D-057. Verified own-rootless daemon: zero containers/
  volumes, original four tagged-image IDs. Only this package and the owner's explicit pre-work
  cleanup request; no base/manager package, release or unrelated performance work.
- Owner-requested temporary cleanup came first. `/tmp` had 118622 free inodes (89% used).
  Inspected **159** old Updates/performance pytest roots, their own-UID fixture-only contents,
  process descriptor/cwd references, active UNIX sockets and nested mounts. Recorded exact root
  paths/device/inode identities and counts in `.work/up11/tmp-cleanup-manifest.json`; rechecked
  before safe non-symlink-following removal. Freed **929919 inodes** and 1587982336 allocated
  bytes (~1.48 GiB); ended at **35 used/1048541 free**. All other `/tmp` files, the persistent
  `/tmp/opencode-sandbox-locks-1000` protocol namespace, prior `.work` logs/XML/packages and
  Docker/user data remained untouched. No system-wide cleanup rule, service or sudo. Ignored
  result/script: `tmp-cleanup-result.json`, `cleanup_tmp.py`; later tests use manifested fresh
  `up11-*` short roots and retain logs separately, not another inode-exhaustion workaround.
- Investigated existing policy/status/update plans, update/install/probe/stop, checkpoint rollback,
  `_restore_checkpoint`, update-recover/config-recover and dashboard confirmation/worker ownership.
  Minimal new checkpoint-plan test **1 failed** before implementation: no immutable rollback/
  recovery consent plan existed. Existing component handlers/journals were retained, not replaced.
- Environment Updates now exposes Start (`s`), Update (`u`), Policy (`p`), Rollback (`r`), Recover
  (`e`) plus existing Check/Details. One extra compact environment-only row, separate target/policy
  forms and a scrollable Cancel-first exact-consent modal fit 80x24/larger. Review buttons request
  read-only preparation; no eligibility grant comes from inventory strings, availability, cached
  versions, readiness or labels. Late/canceled plans cannot publish consent after Close or over
  another screen. Selection/metadata are captured by identity, never re-read from the cursor at
  execution; changes during plan preparation refuse misdescribed consent.
- Existing update plans now include a metadata fingerprint and owned-volume preflight/recheck.
  Latest supported stable is resolved before consent; the exact target is passed unchanged to
  `update_environment`. Existing stopped/network/pin/ownership/direct-workspace restrictions,
  complete checkpoint, installation/real binary verification, failure rollback and final stopped
  state remain. No implicit Stop, network/policy change, temporary start/probe/stop, automatic
  installation, generic executor, Update All or schema migration. Start uses a read-only identity/
  metadata plan and optional precondition under `core.start`'s original lock; it remains running
  and fresh Check is separate. Policy/pin has its own explicit metadata/data-bound consent and
  locked revalidation; it never installs or lifts execution/first-creation restrictions.
- Immutable checkpoint plans bind action, metadata, endpoint/data identity, actual container ID/
  image/running state, checkpoint full image ID and any retained derived-image ID. Optional
  plan arguments to the existing rollback/recover handlers revalidate inside the environment
  lock before snapshots, stops or removal. Restoration uses that exact full ID, not a subsequently
  substituted tag; it occupies existing `image`/`last_snapshot` string fields while the named
  checkpoint remains referenced in `opencode_update` for retention/cleanup. Missing ID references
  retain the existing data-salvage guidance. Successful rollback preserves the entire present
  system layer first, including later changes. Home/workspace/configuration are not rolled back;
  binary rollback cannot undo application-data changes or guarantee backward compatibility.
- Defect found in recovery: failed restoration did not persist its reason and the combined-update
  failure always named update-recover even after the journal had advanced to runtime-recreate.
  Restoration now records `last_error` without clearing the actual journal, and failure guidance
  names its actual recovery route. Updates completion/Details and later inventory publication
  reread authoritative local journal metadata without waiting for Docker inventory or relying on
  cache authority; lifecycle/journal changes qualify version evidence immediately. Details leads
  with operation results and current recovery guidance. Missing checkpoints refuse with safe data
  export/restore guidance, never guessing that npm completed or erasing intent.
- Recover handles interrupted OpenCode updates directly in Updates or Recovery Center; successor/
  other journals route to the existing Recovery Center with the environment preselected. Its
  existing configuration recovery gets an optional metadata/data precondition under its original
  lock; no parallel recovery algorithm. Approved environment and routed config recovery workers
  belong to the app, not the screen, reserve the operation slot and are not exclusive/replaced.
  Normal Quit/conflicting operations refuse while they run; Close/Cancel check only cancels owned
  read-only checks/planning. Once approved, cooperative UI cancellation is not propagated into a
  partial mutation; bounded diagnostics remain bounded, installs/commits keep existing timing.
  Process death still relies on durable journals. No fake success/automatic retry/rollback engine.
- Real/pilot review found notification racks covering operation forms/Updates Details, and delayed
  inventory allowing a stale journal in Details. Collapsed racks only on the affected forms/
  Recovery Center/class-marked Updates Details; notification objects/advisory ownership remain
  intact and full text stays available. Metadata refresh above fixes the stale routing. Lowest
  Textual also exposed late/subscreen table events reaching the hidden/unmounted dashboard;
  restricted dashboard events to its mounted own table and stopped Updates event bubbling.

  | Final complete layer | Result |
  |---|---|
  | Python 3.11/current | **1471 passed, 78 opt-in skips**, 194.60 s |
  | Python 3.11/lowest | **1471 passed, 78 opt-in skips**, 189.41 s; two known Typer deprecations |
  | Python 3.14/current | **1471 passed, 78 opt-in skips**, 191.32 s |
  | Python 3.14/lowest | **1471 passed, 78 opt-in skips**, 187.48 s; two known Typer deprecations |
  | Affected real Docker/OpenCode/terminal | **18 passed/400 logged checks**, no skips/deselections, `up11-verified`, 489.49 s |

  Full commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q --tb=short
  --junitxml=.work/up11/<prefix>-<label>.xml --basetemp=/tmp/opencode/up11-<base><label>`;
  labels/venvs `311/venv311`, `311low/venv311low`, `314/venv314`, `314low/venv314low`.
  Prefix/base `verified-retry` for 311 and `verified` for the other three combinations.
  Python 3.11.18/3.14.8, current Typer 0.27.3/Textual 8.2.8, lowest 0.16.0/4.0.0, pytest 9.2.0;
  four clean pip checks, serial foreground, inode-capacity preflight. All **1549 ordered test IDs/
  outcomes identical**. No inode failure this package. **64 new default cases**: 38 backend,
  25 pilot and one quality-module parameter; six new opt-in terminal cases explain 78 skips.
  All old assertions remain: three UP-10 unavailable-action cases now exercise read-only review/
  cancellation without mutation, appropriate to delivered actions; volume/configuration fakes
  provide new preflight responses without bypassing ownership or disk assertions.
- Regression layers: real private files/locks and existing fake Docker backend; exact consent
  revalidation for changed checkpoint IDs, container/image/state, metadata/pins/journals, endpoint,
  data directory and volume ownership, before any mutation; existing handlers execute under the
  original lock and restore the confirmed ID. Explicit Start, live stopped/network/pin/absent
  refusals, policy/pin consent, missing checkpoint salvage, persistent failed restoration/successor
  routing, configuration preconditions and missing immutable image guidance. Pilots at 80x24/
  120x40 prove full consent/control bounds, focused Cancel, keyboard target entry, unchanged target
  despite later discovery, selection changes, canceled late planning, app-owned mutation after
  Close/Cancel, normal Quit/conflict refusal, production toasts intact/no overlay and event isolation.
- Intermediate unit failure trail retained: first selected run **4 failed/65 passed** (old unavailable
  expectations/new checkpoint fake missing `.Id` response), first new pilot set **7 failed/111
  passed** (tests observed queued Button/Screen events before mounting/completion; fixed condition
  synchronization, no product assertion weakened). First full run **3 failed/1455 passed/72 skips**,
  186.38 s (two fakes lacked volume responses, Recovery row clipped); corrected and **184 passed**,
  88.78 s. Later reviewed **90 passed**, 55.22 s. Lowest affected **1 failed/141 passed**, 57.36 s,
  exposed the event-ownership defect above; narrow fix/new regression, **143 passed**, 56.86 s,
  before the final four complete suites. XMLs remain in `.work/up11/`, not last-failed deselection.
- Real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up11-verified
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_43_diagnostics.py
  tests/integration/test_44_version_evidence.py tests/integration/test_51_updates.py
  tests/integration/test_52_discovery.py tests/integration/test_53_environment_updates.py
  --junitxml=.work/up11/real-verified.xml --basetemp=/tmp/opencode/up11-real-verified`.
  Earlier 12 real rows retain diagnostics/probe cancellation, actual binary/lifecycle/restore
  checks and manual/daily discovery terminals without implicit starts. New four action terminals
  exercise both retained distributions at 80x24/120x40: explicit Start stays running, exact pin/
  refused incompatible target/Manual unpin require consent, exact 2.2.0 -> 2.1.4 installs keep the
  container and finish stopped, Cancel never installs, whole-layer rollback restores 2.2.0 in a
  new container and preserves user configuration/home/workspace. Later system changes are absent
  from the restored checkpoint but present with the updated binary in the retained snapshot,
  proven by actual named/labeled no-network/no-mount one-shot containers, manifested before use.
- Independent recovery gate is real, not inferred from successful update tests. New two distro
  rows SIGKILL the actual manager before npm installation; missing checkpoint tag refuses without
  changing running container/journal (a run-owned temporary alias preserves/restores that image).
  A shell shim fails only removal of the named run-owned container; all other Docker operations
  are real. Failure persists runtime-recreate plus reason and stops safely; Details names config
  recover, existing Recovery Center finishes after the fault is removed, and actual binary/data/
  configuration are checked. A second interruption/new dashboard at 120x40 independently invokes
  direct OpenCode recovery through Recovery Center, succeeds/closes its journal and restores the
  actual original binary. Every normal terminal quit in both success/failure workflows restores
  terminal state. No paid/model-provider call, base replacement or fake mutation/verification.
- Real failure/proof trail (all manifests/logs retained and guarded cleanup executed):
  `up11-terminal-first`: **1 failed body/1 teardown error**, 7 passed/4 failed checks, 368.52 s.
  A burst of terminal editing controls/text left a blank target; the refusal was correct, but
  later harness keys reached the dashboard and opened the container's OpenCode UI. No prompt/
  credential was submitted; this is not model-provider or manual-observation evidence. Harness
  now separates controls and stops immediately if exact consent is absent. `up11-keyboard-repro`:
  **1 failed body/1 teardown error**, 6 passed/1 failed check, 37.52 s, retained snapshots.
  `up11-terminal-proof`: **1 passed/26 checks**, 53.93 s. Recovery iterations: `up11-recovery-first`
  **1 body passed/1 teardown error**, 17 passed/2 failed checks, 47.24 s; `up11-recovery-proof`
  **1 body passed/1 teardown error**, 18 passed/1 failed check, 39.76 s; `up11-recovery-verified`
  **1 body passed/1 teardown error**, 26 passed/2 failed checks, 52.91 s. These exposed Details
  overlays/stale journal publication and a wrapped-text matcher; fixed product publication/
  presentation and matching, without removing checks. `up11-recovery-finalproof`: **1 passed/28
  checks**, 26.10 s. Initial **18 passed/400 checks**, `up11-final`, 463.93 s, reran all affected real rows on both
  distributions, including expanded policy/snapshot/direct-recovery assertions.
- Final review after that first four-way **1469 passed/78 skips** matrix (193.10/187.56/191.71/
  185.54 s) and initial real gate found older Recovery paths reporting only through now-collapsed
  toasts. Added bounded read-only scrollable Recovery results, persistent repair/unsupported-journal
  errors and two pilots proving full long messages, unchanged journals and unclipped controls.
  Focused **78 passed**, 27.31 s. First complete rerun **1 failed/1470 passed/78 skips**, 195.23 s:
  an existing text assertion searched only Static widgets, not the new TextArea. Extended text
  collection while retaining the terminal-guidance assertion and adding read-only verification.
  The final four complete suites and **18 passed/400 checks**, `up11-verified`, 489.49 s, above
  include this correction. Earlier XMLs/logs stay retained; nothing is waived. A documentation
  subset also caught a commit ID in public BASELINE (**1 failed/41 passed**); removed that prose
  reference, never changed the public-record gate; corrected subset **42 passed**, 3.13 s.
- All nine real attempts used isolated `.work/<run>/data`/config, manifests/logs under
  `.work/logs/up11-*`, named resources and guarded product cleanup. Ending actual own-rootless
  inventory has zero containers/volumes/helpers and the same four original full image IDs:
  Debian `d5905c3f5026...`, Arch `418889644792...`, Arch input `3cbf69d2d595...`, custom Ubuntu
  `68ee22004a91...` (full IDs in run evidence). Only run-owned snapshots/checkpoints/aliases/
  runtime objects were removed; file-only backups/cache/logs/scripts remain ignored. Original
  inputs are retained Debian 12/revision 1 and Arch/revision 1; no new current-definition base
  build/freshness claim. User/engineering records updated. Seven product hashes are frozen in
  `.work/up11/final-source-sha256.json`; no product change after final full/real verification.
  Versions, schemas, image assets, runtime identity, base guards, diagnostic/HTTP/probe executors,
  scheduler/cache/preferences, worker adapter, dependencies, AGENTS, CI/RELEASING unchanged.
  No complete campaign, legacy broad test_50 workflow, fresh base, installed-pipx/manager,
  privileged/socket/service, paid-provider or manual-observation evidence is established here.
  No version bump, merge, push, tag, release, upload or publication. Package/checkpoint locally,
  then STOP at UP-11; next is UP-12 + UP-13, not another recovery/manager task.
- Final checkpoint gates: local sdist/wheel build, strict twine and packaged-content validation
  pass; all seven changed/new product modules match final-code hashes and wheel bytes.
  Final document/CLI/quality subset **42 passed**, 3.08 s, not another full suite. Artifacts/logs:
  `.work/up11/package-final/`, `package-final-build.log`; final hashes `final-source-sha256.json`.
  After preserving XML/logs, rechecked/removed only **32 exact manifested current-cycle completed
  pytest roots** with no live process/socket/mount references. `/tmp/opencode` is empty again;
  **1048541 free inodes**, all other `/tmp` entries and persistent locks intact. Cleanup evidence
  `.work/up11/cycle-cleanup-*.json`; no Docker operation or old evidence deletion. Prose-only
  follow-up checks are separate from the final complete suites. Review intended diff, commit
  locally on `work/updates`, leave a clean tree and STOP; nothing merged/pushed/released.

### UP-12 + UP-13 — 2026-10-31 — base actions and explicit refresh

- Resumed clean `work/updates` at `a5843d6`, verified own-rootless identity, zero containers/
  volumes and the unchanged original four image IDs; `/tmp/opencode` empty/1048541 free inodes.
  Read repository/local instructions, TODO, BASELINE, architecture, D-056/D-057 and base package
  handoff. Local instructions' old no-effort state is superseded by this live record/Git, not a
  reason to touch main. Scope is the approved grouped base package, not manager/release work.
- Investigated existing build/update-base, candidate verification/publication, rollback inventory/
  plans, distribution assets, pin creation and base guards. Minimal read-only `prepare_base_build`
  reproducer **1 failed**, absent API. Existing `update_base` only captured the current base after
  consent, offered no full refresh, and ordinary Docker build output would write over Textual.
  Retained the handlers/verification/guards; no universal executor, parallel journal or schema.
- `BaseBuildPlan` binds canonical daemon endpoint, namespace/tag/current full ID or known absence,
  current distribution provenance/build-version label, exact target, immutable distro record and
  build-asset content digest, refresh mode and retention choice. Preparation resolves latest to
  exact supported stable outside base/discovery guard overlap, then only inspects under publication.
  The executor never re-resolves a consented target and rechecks the same evidence under build/
  publication before building and again before publication. Changed/unmanaged/uninspectable bases
  refuse, including an image appearing after a first-build preview. Missing/old/newer provenance
  does not become overwrite authority from an availability string; consent discloses the actual
  current and proposed definitions. No persistent base-version policy/history service.
- Default cached builds retain existing eligible-layer reuse. Explicit `refresh=True` supplies
  exactly `--pull --no-cache`; no cache prune and no package-freshness/security/reproducibility
  claim. Public `core.build_image` still verifies by default and returns the built immutable ID;
  `update_base` requests the build-only stage, records that ID and invokes the same current OS/
  tool/OpenCode verifier on it outside publication. Final publication checks the candidate tag
  still names the verified ID. Cleanup checks that recorded identity, refuses a retagged/unconfirmed
  candidate and reports removal failures rather than silently claiming cleanup. Failed verification
  leaves the original base/copies intact. Content-equivalent candidates verify/report unchanged
  without swap or redundant copy. TUI replacements always retain the old image; the deliberately
  no-copy CLI `build` remains available and discloses the distinction before mutation.
- CLI `build` and `opencode update-base` share plan/description and explicit `--refresh`; existing
  target options remain. Update-base confirms exact existing ID, exact version and mode, including
  `--yes` bypass without target substitution. Base Images adds Build/Rebuild (`b`/`u`) and Rollback
  (`r`), separate target/mode form, explicit multi-copy selector and scrollable Cancel-first consent
  at 80x24/120x40. A single distinct copy can proceed to consent; multiple images start unselected,
  aliases consolidated, and require an explicit immutable choice. Uses existing rollback plan/
  current-definition verifier/revalidation/swap and retained-current-copy path. Old copies remain
  visible even when incompatible with current verification. No implicit downgrade or migration.
- App-owned approved base workers reserve the existing operation slot and refuse normal Quit/
  conflicts. Screen-owned read-only plans/Check are cancelable; Close/Cancel check never cancels
  approved build/rollback, and reopening Updates retains phase/result/output. `build_output` is
  a scoped ContextVar only for this worker: only `docker build` opts into merged-pipe streaming,
  continuously drained to a **32 KiB byte tail**, explicit truncation, first-output/phase/final
  publication and throttled intermediate UI updates. Direct client closed/reaped; no short build
  or output-limit termination, and client death is not proof the daemon build ended. CLI streaming,
  arbitrary exec, installs/commits and bounded inspection/probe paths are unchanged. No invented
  percentage/mutation Cancel. Details is plain/scrollable; notification objects remain intact.
- Existing containers/OS/writable layers, home/workspace/configuration, environment policies and
  one-time integrations are unchanged. Future base-based creation/file-only restores use the
  new base; not-yet-created pin enforcement still gates creation. No new base recovery journal:
  inspect actual base/copies and named leftover candidates after failure/process death.

  | Final complete layer | Result |
  |---|---|
  | Python 3.11/current | **1525 passed, 80 opt-in skips**, 213.93 s |
  | Python 3.11/lowest | **1525 passed, 80 opt-in skips**, 206.99 s; two known Typer deprecations |
  | Python 3.14/current | **1525 passed, 80 opt-in skips**, 209.79 s |
  | Python 3.14/lowest | **1525 passed, 80 opt-in skips**, 206.44 s; two known Typer deprecations |
  | Affected real Docker/OpenCode/terminal | **24 passed/581 logged checks**, no skips/deselections, `up1213-reviewed`, 928.47 s |

  Complete commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q --tb=short
  --junitxml=.work/up1213/reviewed-<label>.xml --basetemp=/tmp/opencode/up1213-reviewed<label>`;
  labels/venvs `311/venv311`, `311low/venv311low`, `314/venv314`, `314low/venv314low`.
  Python 3.11.18/3.14.8; current Typer 0.27.3/Textual 8.2.8, lowest 0.16.0/4.0.0; pytest 9.2.0,
  clean pip checks, serial foreground/inode-capacity preflight. **1605 ordered IDs/outcomes match**.
  **54 new default cases**: 38 backend/CLI, 12 pilots, three actual host clients and one quality
  module parameter. Two new opt-in distro cases explain 80 skips. Existing assertions retained;
  hardening/CLI mocks now answer actual preflight/immutable-candidate-return contracts instead
  of omitting those operations. Existing real race build wrapper forwards verification options
  and returns the real candidate ID; no real verification is mocked out.
- Unit/host coverage includes pre/post-build base/absence/ownership, daemon/namespace, target/mode/
  retention/definition/assets consent races, latest exactness, no-cache flags/no prune, no-copy
  CLI disclosure, candidate-ID probes and retagged-candidate cleanup refusal, actual binary mismatch
  refusal, same-content verified no-op and cached/full-refresh failed-candidate safety. Actual
  host output clients exceed tail capacity without being killed, stream stdout/stderr privately,
  return errors/reap, and ignore diagnostic cancellation/deadline paths. Pilots exercise both
  sizes, exact target/mode/copy consent, live ownership refusal despite misleading cached rows,
  explicit multi-copy choice, changed selected copy, late canceled plans, preserved notifications,
  Close/Quit/conflicts, app-owned bounded Details and priority of a live operation over an old result.
- Real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up1213-reviewed
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_42_base_coordination.py
  tests/integration/test_43_diagnostics.py tests/integration/test_44_version_evidence.py
  tests/integration/test_51_updates.py tests/integration/test_52_discovery.py
  tests/integration/test_53_environment_updates.py tests/integration/test_54_base_updates.py
  --junitxml=.work/up1213/real-reviewed.xml --basetemp=/tmp/opencode/up1213-real-reviewed`.
  `test_42` repeats both packaged Debian 13/revision 2 and Arch/revision 1, plus retained-OS
  fixtures: multiprocess/different-data/context/socket-alias build/rollback exclusion, active
  candidate/copy cleanup refusal, creation during build and publication spanning pin-check/create,
  current-definition verification, exact CLI copy selection/revalidation and retained running layers.
  All 18 existing diagnostics/lifecycle/restore/manual/daily/environment-recovery terminal rows
  rerun, including immutable-ID recovery, missing checkpoint, failed restoration and successor
  config recovery, actual restored binary/configuration/data and normal terminal restoration.
- New real `test_54` independently proves cached and full-refresh behavior on each distro. It uses
  the established test-only manager image namespace, never a production override. Copies packaged
  assets with **only the external FROM hostname** changed to explicit official Docker Hub
  `registry-1.docker.io/library/...`; exact source equivalence after reversing that hostname is
  asserted. This prevents `--pull` from moving the retained original Arch upstream tag. New
  upstream aliases are known absent before creation/pull, manifested and untagged afterward;
  downloaded source tags are not inferred managed objects and no cache is pruned. All build,
  OS/tool/real binary and rollback handlers remain product code; no package/tool gate is weakened.
  First and repeated cached builds prove actual `CACHED` layers, verified unchanged and no
  redundant swap. Full refresh proves real `--pull --no-cache`, non-cached package RUN steps,
  distinct verified image and retained previous ID. Actual running retained container/image/
  policy/metadata/writable-layer marker remain unchanged. A fresh pinned container uses the exact
  new base. Failure is injected **after actual candidate build and verification**; old current/
  copies remain and only the candidate is cleaned. This is safety fault injection, not an observed
  upstream package failure or a synthetic Docker result.
- New real base terminals at 80x24 and 120x40 select and cancel full-refresh consent (no build),
  approve a cached exact-target build and pause the handler **after the actual build** with
  run-owned ready/release files. Details exposes bounded real output, Close stays responsive,
  normal Quit refuses, reopen adopts completion, and selected rollback really verifies/swaps
  exact IDs. Multiple copies explicitly select the intended full image; no newest/date/default
  guess. A current content-equivalent image is not fabricated as a rollback copy: the harness
  explicitly chooses the known alternate copy when appropriate. Both original cached and refreshed
  targets are exercised; retained containers/layers stay intact and every normal quit restores
  terminal state. This is automated pty evidence, not human manual observation. Approved full
  refresh runs through the real CLI; TUI full-refresh flag execution is also covered by pilots.
- Intermediate failures/proofs are retained, not waived: first focused **1 lint failure/163
  passed**, 33.75 s. New focused **3 failed/230 passed**, 49.66 s: first output was throttled until
  another chunk/phase, Select's deprecated blank sentinel differed across supported versions, and
  one test inspected queued Button work too early. Fixed first-output publication and membership-
  based explicit selection, synchronized the queued test; **63 passed**, 13.42 s. First complete
  primary **1 failed/1518 passed/78 skips**, 213.93 s, found the old CLI mock missing new inspection/
  plan args; extended while preserving exact-target assertion. A later focused quality run found
  an unbound test loop variable (**1 lint failure/55 passed**); bound it, no gate change. Lowest
  affected **186 passed**, 15.92 s, only known Typer warnings. Documentation **1 failed/42 passed**,
  3.13 s, caught a >80-column example; wrapped it without altering its gate.
- `up1213-debian-proof`: **1 failed body/1 teardown error**, 119.79 s, **23 passed/1 failed checks**:
  the harness called its intentionally destructive short exit-wait helper while expecting a live
  application. Replaced that call with non-destructive kernel `waitid(WNOWAIT)`; all real builds/
  candidate/pin/layer checks had passed. `up1213-builds-proof`: **2 passed/86 checks**, 422.48 s,
  both distro builds and terminals before expanding terminal rollback. Initial full matrix
  **1524 passed/80 skips each**, 211.42/207.09/209.49/205.06 s, 1604 identical ordered outcomes.
  `up1213-verified`: **23 passed/1 failed**, 940.32 s, **573 passed logged checks**, no failed
  boolean check hidden; assertion expected the initial ID in rollback copies although the correct
  content-equivalent cached result had left it current. Harness now explicitly selects the known
  alternate immutable copy in that state, preserving exact-ID/swap assertions. `up1213-final`:
  **24 passed/581 checks**, 947.00 s. Final review then reproduced a saved base result masking a
  different active operation (**1 failed**, .86 s); priority corrected/new pilot, lowest affected
  UI/ownership **97 passed**, 75.16 s. Final four complete suites and the full **24 passed/581
  checks** affected real gate above include that product correction, no focused substitute.
- All five real attempts used isolated `.work/<run>/` data/config/copied contexts/scripts and
  `.work/logs/<run>-manifest.txt`, named/labeled owned resources and guarded product cleanup,
  including failures. Ending verified own-rootless inventory: no containers/volumes/helpers,
  no test manager/upstream aliases and the unchanged four full original tagged-image IDs:
  Debian `d5905c3f5026...`, Arch `418889644792...`, Arch input `3cbf69d2d595...`, Ubuntu custom
  `68ee22004a91...` (full values retained in logs). Shared build cache intentionally remains.
  Seven product modules frozen in `.work/up1213/reviewed-source-sha256.json` before final suites/
  real gate. Versions/schemas, distro revision/image assets, daemon identity, shared base locks,
  diagnostics/HTTP/probes, cache/discovery/preferences, worker adapter, AGENTS, dependencies and
  CI/release gates are unchanged from UP-11. No full campaign/legacy broad test_50, installed
  pipx/manager, paid-provider, privileged/socket/service or manual-observation evidence. No
  version bump, merge, push, tag, release, upload or publication. Package/review/commit locally,
  then STOP at UP-12/UP-13; next is UP-14/UP-15 read-only manager discovery/classification.
- Final package/document checkpoint: sdist/wheel, strict twine/content validation and equality
  of all seven changed/new product modules with verified source hashes/wheel bytes pass; artifacts
  `.work/up1213/package-final/`, `package-final-build.log`. Document/CLI/quality subset **43 passed**,
  3.23 s (`docs-verified.xml`), not another complete suite. Earlier `docs-final.xml` **1 failed/42
  passed**, 3.49 s: the public-record guard interpreted prose `publication/` as a retired internal
  path; reworded prose, no gate change. User/engineering records now describe only implemented
  behavior and actual evidence/limits. After artifact preservation, rechecked/removed only **25
  exact manifested completed current-cycle pytest roots** (own UID, no process/socket/mount refs),
  not logs/XML/contexts/packages or persistent protocol locks. `/tmp/opencode` empty again,
  **1048541 free inodes**; ignored cleanup evidence `.work/up1213/cycle-cleanup-*.json` and exact
  root manifest. Any final prose-only test scratch is equally manifested/guarded and removed after
  its run. No product change after the final complete/real gates. Review intended diff, commit
  locally on `work/updates` and STOP at this verified package; nothing merged/pushed/released.

### UP-14 + UP-15 — 2026-10-31 — read-only manager discovery/classification

- Resumed clean `work/updates` at `997a7d8`, read local/repository instructions, TODO, BASELINE,
  architecture, D-056/D-057 and the handoff. Verified own-rootless identity, zero containers/
  volumes and unchanged four original tagged image IDs. `/tmp/opencode` empty/1048541 free
  inodes. The local file's pre-effort state is historical, not permission to change main. Scope
  is this grouped read-only package; UP-16/UP-17 remain separate and no replacement is exposed.
- Investigated actual installed editable/distribution metadata, pyproject/CLI entry point,
  install guide and real pipx smoke, pipx 1.18.7 source/metadata/paths/self-managed defaults and
  listing behavior, existing bounded HTTP/cache/source coordination, dashboard scheduling and
  generation/Cancel ownership. pipx listing can take locks and normalize legacy records; the
  classifier therefore never runs/imports pipx. Missing-provider minimal reproducer **collection
  error**; no prior manager provider/installation evidence implementation existed.
- `manager_releases.py` adds only the official GitHub published-release source, independent of
  OpenCode/npm. Strict `vX.Y.Z`, no leading-zero/prerelease/build/shell suffix, exact official
  release URL, false draft/prerelease booleans and valid published timestamp. Choose numeric
  highest, never a mutable GitHub latest/date/target_commitish or the unchanged checkout version;
  comparisons explicitly refuse implicit downgrade. Bounded plain notes (8192 characters and
  truncation) are data, not rendered markup/commands. One bounded 100-entry page: a full page
  fails closed as incomplete/manual review, not a claim of exhaustive latest discovery. No
  speculative tag/commit resolution or authenticated target grant from release metadata.
- Standalone stdlib `http_probe.py` adds the explicit GitHub Accept/no-redirect mode. No token/
  login/header credential, required GitHub integration or host package manager. Existing npm
  headers/behavior remain unchanged. Existing parent short diagnostic runner bounds total
  DNS/TLS/body/client lifetime to eight seconds, manager body to 4 MiB, owns process-group
  cancellation/reaping; no change to long builds/installs/commits/arbitrary exec or Docker/probe
  timing. HTTP error diagnostics do not echo arbitrary URL/proxy text that can contain secrets.
- Separate manager source key retains validated selected-release evidence and failed attempts.
  Private source exclusion never spans mutation locks. Persist/fsync an incomplete claim/ID/time
  before HTTP; optional requests throttle by start for 24h including failures/interruption/restart
  and backward clocks. Concurrent callers share actual requests/failures, not cached-only lock
  contention. Explicit refresh may run early but honors Retry-After and GitHub rate reset for
  403/429/503, even if a readable cache survives unavailable lock storage. Automatic unsafe/
  unwritable storage fails closed; explicit uncached bounded discovery remains possible. Waiter
  cancellation cannot cancel another owner; owner interruption retains the incomplete claim.
- `manager_installation.py` performs dated local-only inspection: exactly one running distribution,
  version/entry point/module location, bounded no-follow own-UID regular PEP 610/pipx records,
  exact official Git URL/versioned requested tag/full commit ID, actual venv and interpreter,
  recorded source Python/version, app path, own executable/standard script template, exposed
  symlink, actual invocation and PATH all agree. Recognizes default options in wire formats
  0.5/0.6/0.12; only actual current pipx execution is claimed. Its default environment-name field
  and non-exposed dependency inventory are ordinary evidence, not custom installation options.
  No conversion, metadata repair, launcher takeover, pipx execution or Python install/switch.
- Unknown metadata/fields, custom pip/venv/backend/resources/exposure options, injections/pins/
  suffixes, relative/mismatched pipx locations or default Python, editable/foreign sources and
  missing/shadowed/ambiguous launchers yield static manual guidance. Unsupported values/URLs/
  OS diagnostics are never dumped, because they can contain secrets. Explicit HOME/BIN/MAN/
  COMPLETION/SHARED locations and source Python are retained as evidence. Standard pip simple
  shebang and long/space-path trampoline are recognized as exact data, not shell-evaluated;
  special/unrecognized quoting is unsupported. Local record hash/paths/source/commit are not a
  public-source authenticity proof or mutation authority; external updater independence and
  published tag-to-commit identity remain unassessed UP-16/UP-17 prerequisites.
- Added only read-only `manager status [--check]`, available without Docker/pipx execution. Manager
  Updates opens with local version/cached release evidence and independent local inspection,
  never a request. Check starts independent release/classification workers; source/row failures
  retain the version and other result. Read-only Cancel/Close rejects late results and cannot
  mutate/install. Compact summary/Details disclose provenance, timestamp, plain notes/errors/
  manual guidance at 80x24/larger. Existing generation protection prevents old inventory from
  replacing a newer explicit check. Manager Update is disabled even for recognized installs;
  no consent/executor/helper/exclusion/replacement/recovery mechanism is prematurely exposed.
- Existing default-off preference now schedules GitHub/npm through separate owned workers with
  independent status/claims, not sequential source failure coupling or a universal engine. A
  newer manager release adds one quiet cached count; npm still counts only qualified Notify
  histories without pending journals. No extra operation-status writes/toasts, Docker, runtime
  probes, starts or service. Disabling cancels owned automatic requests and hides indicators,
  without disabling manual Check. Old npm-only pilot tests isolate the new external source;
  their real npm provider/assertions are retained, and the new manager provider/worker has its
  own real-loopback tests. Existing real daily terminals point the manager URL to a separate
  loopback fixture too; no accidental public API in tests, npm request assertions remain intact.

  | Final complete layer | Result |
  |---|---|
  | Python 3.11/current | **1611 passed, 82 opt-in skips**, 225.64 s |
  | Python 3.11/lowest | **1611 passed, 82 opt-in skips**, 219.72 s; two known Typer deprecations |
  | Python 3.14/current | **1611 passed, 82 opt-in skips**, 220.54 s |
  | Python 3.14/lowest | **1611 passed, 82 opt-in skips**, 216.29 s; two known Typer deprecations |
  | Affected real Docker/OpenCode/pipx/terminal | **26 passed/637 logged checks**, no skips/deselections, `up1415-final`, 981.42 s |

  Complete commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q --tb=short
  --junitxml=.work/up1415/final-<label>.xml --basetemp=/tmp/opencode/up1415-final<label>`;
  labels/venvs `311/venv311`, `311low/venv311low`, `314/venv314`, `314low/venv314low`.
  Python 3.11.18/3.14.8; current Typer 0.27.3/Textual 8.2.8, lowest 0.16.0/4.0.0; pytest 9.2.0,
  clean pip checks, serial foreground with inode preflight. All **1693 ordered IDs/outcomes match**.
  **86 new default cases**: 43 release provider/coordination, 33 installation and 10 CLI/pilots.
  Two new real pipx-layout cases explain 82 opt-in skips. No assertion/skip/CI/release gate relaxed;
  CLI structure adds the actual read-only group but retains the top-level cap/existing command
  checks. The old disabled-Check assertion/real Manager text now checks implemented local evidence
  and still asserts Update disabled; no mutation claim is substituted.
- Provider tests use actual loopback HTTP/isolated stdlib child: no credential header even with
  dummy GITHUB_TOKEN, strict invalid/draft/prerelease/foreign/duplicate/future/full-page rejection,
  numeric/no-downgrade/plain notes, body/deadline and no redirect, independent cache, daily success/
  failure, clock/restart/coalescing/cancellation, 403/429/503 Retry-After/rate-reset and unsafe
  storage. Installation tests use real private files/symlinks/FIFO/modes plus synthetic runtime
  identity, default/custom settings/wire variants, interpreter/source/options/launcher ambiguity
  and dummy-secret non-disclosure. Pilots independently verify remote/local failure, no network
  on opening, disabled Update, 80x24/larger Details/controls, late Cancel/Close, daily quiet counts/
  restart, actual overlapping request identity and disabled-HTTP-child reaping/incomplete claims.
- Real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up1415-final
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_42_base_coordination.py
  tests/integration/test_43_diagnostics.py tests/integration/test_44_version_evidence.py
  tests/integration/test_51_updates.py tests/integration/test_52_discovery.py
  tests/integration/test_53_environment_updates.py tests/integration/test_54_base_updates.py
  tests/integration/test_66_manager_inventory.py --junitxml=.work/up1415/real-final.xml
  --basetemp=/tmp/opencode/up1415-real-final`.
  All 24 prior affected packaged/retained base-race, owned-probe, lifecycle/restore, manual/daily,
  environment action/recovery and cached/full-refresh base terminal rows pass again. Original
  candidate/rollback/pin/retained-layer/recovery assertions remain, no Docker result substitution.
- New real `test_66` creates tagged sources from this exact working package, private HOME/pipx/
  Git config and default or custom-space locations, invokes real external pipx and the actual
  installed console launcher (without PYTHONPATH/source shadowing), and uses actual PEP 610/
  pipx/Python records. A **declared private Git URL rewrite** maps the official URL spelling to
  a run-owned local tag/commit: transport/provenance-shape evidence, **not public-release commit
  authenticity**. No source-check replacement/mock or production override exists. Inspection
  bytes of records/executable stay unchanged; exact recorded tag/commit and paths agree. Real
  options/pins/suffixes refuse manual preservation, foreign exposed launcher and PATH shadow
  refuse without taking over/deleting the foreign target. The default layout additionally really
  uninstalls/reinstalls from a foreign local VCS spec and an editable tree; both get manual guidance.
  Every private install is uninstalled through pipx; no user launcher/install/Python is touched.
- Installed-manager terminals at 80x24/120x40 use a test-installed .pth file **only** for the
  loopback release URL; package/interpreter/source records, invocation, launcher and Docker remain
  actual. Opening makes no request, Check discovers a higher full release, independent local
  classification remains visible after HTTP 503, cached release remains dated, Details is usable,
  Update key cannot install and normal exit restores terminal. Final pre/post installation-record/
  executable bytes match. No automatic handoff/replacement/recovery, public commit authentication,
  old pipx execution or human observation claim is inferred from these tests.
- Independent unauthenticated official public GitHub GET, isolated `.work/up1415/live-data`/
  config: discovered **v6.1.0**, published `2026-10-30T09:12:11Z`; unchanged checkout 6.1.0 is
  not presented as a new release. This development tree has multiple editable/generated metadata
  records and accurately receives manual review, not supported installation authority. Evidence
  `.work/up1415/official-release-check.json`; no token/login/credential or replacement used.
- Intermediate failures/evidence retained: missing-provider reproducer collection error. First
  selected **3 failed/92 passed**, 33.52 s: invalid-type test fixture concatenation (two cases)
  and new CLI group expected-set update; fixed fixtures/expected group, existing count cap intact.
  Focused **1 lint failure/116 passed**, 38.42 s; combined **1 lint failure/135 passed**, 50.34 s;
  removed unused imports, normalized style, no gate change. Lowest affected **145 passed**, 49.66 s;
  final extended lowest/docs **165 passed**, 51.22 s (only two known Typer deprecations). Early
  full primary **1601 passed/82 skips**, 224.02 s, predates ten final regressions and is historical,
  not final evidence. User-doc subset **1 failed/42 passed**, 3.12 s, overlong example comment;
  shortened prose without changing 80-column assertion. Final four complete gates above include it.
- `up1415-pipx-proof` **1 failed**, 1.47 s, before any install: missing required harness `check`
  argument. `proof2` and `proof3` each **1 failed/1 teardown error**, 14.57 s: conservative default
  metadata assumptions refused the real environment-name field and dependency inventory. Corrected
  defaults using source/real records, not relaxing custom-options refusal. `proof4` **1 passed/10
  checks**, 15.47 s. `up1415-pipx-terminal` **1 passed/1 failed/1 teardown error**, 34.17 s,
  **27 passed/1 failed checks**: actual space-path trampoline uses double quotes, not the presumed
  single-quoted form. Recognize actual pip's standard template as data (unusual quoting still
  refuses). `up1415-real-proof` **10 passed/182 checks**, 103.45 s. Final 26-test/637-check real gate
  expands foreign/editable sources and includes all product corrections; nothing waived/deselected.
- All seven real attempts used isolated roots/private installations/names/manifests, product pipx
  uninstall and guarded campaign cleanup/leak checks, including failures. Ending verified own-
  rootless inventory has zero containers/volumes/helpers and unchanged four original tagged
  images: Debian `d5905c3f5026...`, Arch `418889644792...`, Arch input `3cbf69d2d595...`, custom
  Ubuntu `68ee22004a91...` (full IDs in ignored evidence). Shared build cache intentionally remains.
  Eight product modules frozen in `.work/up1415/final-source-sha256.json` before final complete/
  real gates. Manager version, schemas, image definitions/assets/revisions, runtime identity,
  core lifecycle/base guards, cache implementation, diagnostic/probe executors, worker adapter,
  dependencies and CI/release gates unchanged. No complete campaign/broad legacy test_50,
  paid-provider, privileged/socket/service or manual-observation evidence; no release-readiness
  claim, version bump, merge, push, tag, upload or release. Package, review and commit locally,
  then STOP at UP-14/UP-15. Next is independently verified UP-16 exclusion/helper/terminal handoff,
  **not** premature UP-17 replacement or a manager installation button.
- Final package/document checkpoint: sdist/wheel, strict twine/content validation and equality of
  all eight product modules with frozen full/real source hashes/wheel bytes pass, ignored artifacts
  `.work/up1415/package/`, `package-build.log`. Final document/CLI/quality subset **43 passed**,
  3.10 s (`docs-verified.xml`), not another complete run; preceding `docs-final.xml` **1 failed/42
  passed**, 3.27 s, public-record guard matched a slash-separated publication phrase as a retired
  internal path. Reworded prose, no gate change. User/current-state records now describe only
  implemented read-only behavior/evidence/limits and the UP-16 handoff. After evidence preservation,
  guarded removal of **20 exact manifested completed current-cycle pytest roots** (own UID, no
  process/socket/mount references), never logs/XML/private source fixtures/package artifacts or
  persistent lock files. `/tmp/opencode` empty again/**1048541 free inodes**; cleanup manifest and
  result stay ignored under `.work/up1415/`. Final prose-only scratch is separately manifested and
  guarded after its run. No product change after final complete/real gates; review, local commit on
  `work/updates` and STOP. Nothing merged, pushed, tagged, bumped, uploaded or released.

### UP-16 first safety checkpoint — 2026-10-31 — early process-lifetime usage/exclusion

- Resumed clean `work/updates` at `f1cb9ce`; local/repository instructions, TODO, BASELINE,
  D-056/D-057, architecture and handoff reconciled. Own-rootless daemon verified: no containers/
  volumes, original Debian/Arch/Arch-input/Ubuntu image IDs unchanged. `/tmp/opencode` empty at
  entry. No user launcher/install/credential or Docker/service setting touched.
- Investigated actual console entry point/CLI dispatch, data/base lock order, provenance and
  metadata/script recognition, dashboard operation/session ownership, Textual worker shutdown,
  attached-session watchdog/signal handling, package/entry-point gates and real pipx/pty fixtures.
  The old entry point imports CLI/core/Typer before main; a context released on main/dashboard
  return would also permit exclusion before worker/thread-pool shutdown. These are separate
  startup safety risks, so **split UP-16 at an independently runnable verified checkpoint** under
  D-057, not completion of the helper/handoff gate or consolidation with UP-17. Missing-lock-module
  reproducer failed collection; no existing installation-usage protocol was present.
- New `launcher.py` is a minimal stdlib console bootstrap; `installation_locks.py` imports no core,
  Typer or application dependencies. Acquire shared usage before importing the CLI. Current-code
  `cli.main()` acquires/reenters before dispatch for existing generated wrappers and module
  invocation too. No import-time package side effects; direct Python library/Typer-app calls are
  not a supported startup route. Help/version/empty invocation are not lock bypasses.
- One fixed `/tmp/opencode-sandbox-locks-<UID>/` private namespace, shared with existing base
  protocols but distinct `installation-<hash>.lock` files. Key is canonical absolute application
  Python prefix, independent of product data/config, HOME, TMPDIR, XDG and pipx overrides; aliases
  converge, separate venvs using one Python binary do not merge. Prefix path, not venv inode,
  survives replacement. No-follow/relative opens check parent ownership/sticky writability,
  exact own-UID 0700 directory and 0600 regular single-link file, inode agreement after acquisition
  and on usage reentry. Unsafe namespace/files are refused without repair or fallback. Persistent
  files are never deleted, treated as stale or keyed by live PID. Exit/death releases flock,
  without replacing inodes. Bootstrap validation is deliberately independent of core-dependent
  base guards; no speculative shared-lock refactor or dependency cycle.
- Normal processes take non-waiting shared flock; an internal exclusive guard refuses any live
  shared/exclusive holder, including its own process. No upgrade/release/reacquire trick or
  production early-release API. Concurrent ordinary instances/readers still work. Busy normal
  startup exits 2 with static guidance before dispatch/data creation. A process-global mutex makes
  repeated/threaded startup idempotent. The lease is deliberately retained until **process exit**,
  not main/dashboard return, covering non-daemon and thread-pool draining. Five product modules
  and the packaging configuration/checker were frozen before final complete/real gates.
- All namespace/lock fds are CLOEXEC; exec'd helpers/clients inherit none even with close_fds=False.
  At-fork hooks serialize descriptor ownership and close the child's copies without LOCK_UN, so
  fork-only children neither unlock the live parent nor retain its lease after parent death.
  Child manager entry reacquires its own lease. New installation acquisition refuses inside
  context-local data/environment/base guards; small core lock observations add that order check
  without changing mutation semantics/timing. An already-held usage lease can reenter safely.
- Provenance classifier recognizes both existing standard `cli:main` and new `launcher:main`
  records/scripts, including pip's long/space wrapper; this does not claim old installed code
  participates in locks or that local provenance grants execution. Strict package entry-point
  validation now requires the **new exact** target, and both bootstrap modules must be present
  in wheel/sdist. Prior metadata/license/assets/tests/retired-installer checks remain; no CI/release
  workflow, dependency bounds, manager version, metadata/backup schema or image assets changed.
- **No independent helper or external-tool validation, narrow fresh-verifier capability, terminal
  handoff, manager consent/replacement/recovery or automatic restart exists here.** No generic
  environment/CLI bypass permits normal startup under exclusive access. Manager Update remains
  disabled. UP-16 must still prove external interpreter/pipx independence/settings preservation,
  self-contained helper lifetime, controlled verifier access without inherited-descriptor leaks,
  operation/session quiescence and terminal restoration **before** any future mutation. Existing
  restored-terminal tests prove ordinary exits only, not that pending handoff gate. Older managers,
  direct library use, external pipx/Docker and orphaned daemon work after manager death do not
  honor this advisory protocol; a same-user hostile process is outside the boundary.

  | Final complete layer | Result |
  |---|---|
  | Python 3.11/current | **1655 passed, 84 opt-in skips**, 231.41 s |
  | Python 3.11/lowest | **1655 passed, 84 opt-in skips**, 219.66 s; two known Typer deprecations |
  | Python 3.14/current | **1655 passed, 84 opt-in skips**, 222.74 s |
  | Python 3.14/lowest | **1655 passed, 84 opt-in skips**, 218.99 s; two known Typer deprecations |
  | Affected real Docker/OpenCode/pipx/pty | **29 passed/702 logged checks**, no skips/deselections, `up16a-final`, 1047.39 s |

  Complete commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q --tb=short
  --junitxml=.work/up16a/final-<label>.xml --basetemp=/tmp/opencode/up16a-final<label>`;
  `311/venv311`, `311low/venv311low`, `314/venv314`, `314low/venv314low` serial foreground,
  clean pip checks/inode preflight. Python 3.11.18/3.14.8, current Typer 0.27.3/Textual 8.2.8,
  lowest 0.16.0/4.0.0. All **1739 ordered IDs/outcomes identical**. New **44 default cases**:
  41 real host/process installation-lock cases, one bootstrap classifier template and two package
  content regressions. Two new real distro session cases account for 84 opt-in skips. No passing
  layer is inferred from those skips or from the historical 6.1.0 release.
- Real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up16a-final
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_42_base_coordination.py
  tests/integration/test_43_diagnostics.py tests/integration/test_44_version_evidence.py
  tests/integration/test_51_updates.py tests/integration/test_52_discovery.py
  tests/integration/test_53_environment_updates.py tests/integration/test_54_base_updates.py
  tests/integration/test_65_pipx.py tests/integration/test_66_manager_inventory.py
  tests/integration/test_67_installation_exclusion.py --junitxml=.work/up16a/real-final.xml
  --basetemp=/tmp/opencode/up16a-real-final`.
  The prior 26 affected rows rerun, assertions retained: packaged/retained base races, diagnostics/
  probes, observations/lifecycle/restore, manual/daily discovery, environment update/rollback and
  independent recovery, exact base cached/full refresh/candidate/copy/retained-layer/terminal rules.
  Actual held base mutations now also demonstrate exclusive installation refusal.
- Real installed default/custom-space pipx launchers run the new bootstrap, preserve actual source/
  VCS/Python/options/invocation/PATH classification and ordinary 80x24/120x40 terminal behavior.
  An independent non-mutating external test guard targets only the run-owned installed prefix:
  version/help/create startup refuses across alternate data/config paths, which stay absent.
  A live installed dashboard permits another shared CLI reader but refuses exclusive access;
  ordinary dashboard exit restores the terminal/releases usage. Guard processes are manifested/
  reaped; private installations uninstalled. The existing explicitly declared private Git URL
  rewrite/loopback release hook is not public-source authentication, helper independence or an
  updater. Product records/executable bytes stay unchanged by inspection/exclusion.
- `test_67` proves real retained Debian/Arch attached shells and long Docker exec hold the source
  manager's installation lease while active and release it after completion, without imposing a
  short deadline or changing attached-client/watchdog behavior. Private environment IDs/names,
  process handles and release files belong to the run; product cleanup handles failures as well.
- `test_65` adds full real pipx install/upgrade/reinstall/force upgrade/downgrade/uninstall,
  installed basic CLI/assets, environment/data retention and foreign/legacy launcher assertions.
  Its old fixture cloned published tags and attempted to create the same version tag; additionally
  it installed stale HEAD, not the package under review. Corrected **only the fixture**: no-tags
  private clone overlaid/committed with the current package, two tags created only there. Source/
  published history is untouched. Production version stays 6.1.0; the fixture's next-patch version
  is only a private upgrade-test input. Direct real Docker probes use the existing real markers,
  never weaken the unit suite's no-host-Docker guard. Optional installed-asset image build not run.
- Failure trail: collection reproducer as above. Selected **77 passed**, 1.40 s; expanded **1 lint
  failure/130 passed**, 3.67 s; lowest affected **1 lint failure/177 passed**, 12.28 s, two known
  deprecations. Replaced test fork error handling with explicit exit-status/finally semantics and
  fixed import/string style; no lint/assertion waiver. Static **89 passed**, 2.22 s; final host/
  package/document/quality subset **140 passed**, 4.13 s. Final four full suites include all fixes.
- `up16a-proof`: **3 failed/2 passed/1 teardown error**, 53.53 s, **91 passed/1 failed checks**.
  Existing local v6.1.0 tag collided in the private pipx fixture; new session row lacked real-Docker
  markers, and direct release hit the no-real-Docker unit guard. Its unfinished real exec correctly
  kept a lease that blocked the next row until campaign cleanup. Corrected fixtures and ensured
  owned clients are always reaped. `up16a-proof2`: **1 failed/4 passed**, 83.90 s, **112 passed
  checks**: old pipx row also needed the real markers for its direct container/volume retention
  check after reaching uninstall. Added those markers; no product check suppressed/deselected.
  Final 29-test/702-check gate reruns all failed rows and their original lifecycle/launcher assertions.
- Final hashes, XML and logs `.work/up16a/final-source-sha256.json`, `final-*.xml`, `real-final.xml`;
  real manifests/check logs `.work/logs/up16a-*`. All attempts have isolated product/pipx/source/
  launcher roots and manifested owned resources, guarded product cleanup/uninstall/leak checks.
  Final own-rootless inventory: no containers/volumes/test image tags, original Debian
  `d5905c3f5026...`, Arch `418889644792...`, Arch input `3cbf69d2d595...`, Ubuntu `68ee22004a91...`
  unchanged (full IDs in ignored inventory evidence). Shared build cache and persistent protocol
  lock inodes intentionally remain. No user install, launcher, Python selection, credential,
  public API or paid-provider use; no complete campaign/broad legacy TUI, privileged/socket/service,
  human observation or pending helper/handoff/replacement claim. Finish packaging/current records,
  review and commit this first UP-16 checkpoint locally, then STOP. Next remains **UP-16**, not
  UP-17. No bump/merge/push/tag/upload/publication or release work.
- Final package/document/resource checkpoint: sdist/wheel build, strict twine/content validation,
  exact bootstrap entry point and equality of all five product modules to their frozen complete/
  real hashes and wheel bytes pass. Private instructions/evidence are absent from the sdist.
  Document/CLI/quality subset **43 passed**, 3.18 s (`docs-final.xml`); later prose-only follow-up
  does not substitute for another full run. All product/packaging hashes remain unchanged after
  final full/real gates. No remaining manager/guard/watchdog Python process found. Guarded cleanup
  removed only **13 exact manifested completed pytest roots** (own UID, no live process/socket/
  mount references); `/tmp/opencode` empty, **1048529 free inodes**. Additional intentional fixed-
  namespace installation lock inodes remain persistent, not stale files to delete. Ignored result
  `.work/up16a/cycle-cleanup-*.json`; logs/XML/private fixtures/package artifacts/shared build cache
  and prior evidence retained. Final prose-only scratch is separately manifested/guarded after
  its run. Review intended diff, commit locally on `work/updates` and STOP at this verified first
  UP-16 checkpoint. Do not mark UP-16 complete or begin UP-17 from this evidence.

### UP-16 second trust checkpoint — 2026-10-31 — independent external-tool prerequisites

- Resumed clean `work/updates` at `2e6d2d0`; repository/local instructions, TODO, BASELINE,
  architecture, D-056/D-057 and the first-checkpoint handoff reconciled. Own-rootless daemon
  verified: no containers/volumes, four original image IDs unchanged, `/tmp/opencode` empty.
  Startup/exclusion is implemented, but neither that lock nor local provenance is an updater
  grant. Scope remains UP-16, not UP-17 replacement or release work.
- Investigated actual external pipx console/entry point, 1.18.7 dispatch/setup/paths/interpreter
  source and dependency metadata, current local classification/source-Python evidence and bounded
  diagnostic runner. Its --version path exits before logging/directory creation/listing/metadata
  normalization; do not invoke pipx list/environment as a read-only shortcut. A binary and console
  outside the target can still load target-dependent paths, so external-runtime prerequisites are
  an **independent trust checkpoint** before helper/verifier/terminal ownership transfer. Split at
  that boundary under D-057; **UP-16 is still partial**, no handoff fixture or updater exposed.
- New internal `manager_tools.assess(classification)` returns dated in-memory prerequisite facts
  only. It has **no startup/status/discovery/UI caller or public command** and does not hold an
  exclusive installation lock, stage a helper, bypass startup or mutate installation/configuration.
  Unsupported classifications cannot trigger tool execution. No caching, schema, recovery-record
  or automatic-install behavior. Future execution must independently revalidate all facts/consent.
- Inspect a bounded own/root-controlled standard pipx script and literal interpreter/shebang or
  exact pip shell trampoline as data. No env-shebang/PATH-Python guessing, arbitrary wrapper or
  shell evaluation. Validate executable/parent ownership/modes and every symlink-route component,
  not merely the shared binary endpoint: outside aliases through the replaceable prefix still
  depend on it. Refuse loops, ambiguous paths, target-owned scripts/interpreters, FIFO/oversized/
  unsafe files and unknown settings. Re-read script hash/stat/interpreter identity after probes;
  changed evidence cannot report support. Local path/record agreement is not tool authentication
  or protection against malicious same-user tooling.
- `manager_tool_probe.py` is standalone diagnostic source passed in memory to the existing
  external Python, not imported from the replaceable venv. First `-I -B -S` proves stdlib-only
  Python 3.11+/executable/prefix/base/stdlib/search identity outside the target. Second `-I -B`
  runs only the recognized actual script with fixed --version argv. Support only inspected pipx
  **1.18.7**/expected entry point and filesystem dist-info records; unknown versions/provider/egg/
  wrapper formats receive manual fallback, never automatic tool/Python installation or conversion.
  No package dependency is added to the manager; packaging is an existing external pipx dependency
  used only by that child to evaluate declared requirements, environment markers/default extras
  and installed version constraints.
- Validate declared dependency file inventories even for lazy/not-imported or presently absent
  paths, all observed module/namespace/search origins, ownership/writability/symlink routes and
  effective pipx locations. Bounded raw CSV RECORD is intentional: **CPython 3.14 filters missing
  entries from Distribution.files**, which cannot prove independence while the target is absent.
  Read known filesystem dist-info directly (512 KiB/8192 rows per distribution, 64 distributions/
  16384 rows overall); unknown/missing/malformed/oversized records refuse, no migration/repair.
  The path inventory digest is local evidence, not content attestation or future installability.
  Executed external imports remain trusted existing user tooling, not a sandboxed/security-certified
  package or an authenticated public manager release.
- Explicit recognized effective HOME/BIN/MAN/COMPLETION/SHARED settings and the **original recorded
  source-Python selection** are carried forward. Do not replace a venv Python path with its shared
  binary or erase a target-dependent alias by early resolve. Validate the complete requested route
  and compare/report the external tool's effective canonical endpoint separately. Refuse target-
  dependent locations or unknown PIPX settings rather than guess preservation. Children get only
  these settings, HOME/PATH and fixed locale/no-bytecode controls: no arbitrary Python/loader,
  pip/index/proxy/provider credential environment or raw stdout/metadata/error dump. Future actual
  installation network/environment consent remains separate. No option/injection/pin/suffix
  preservation beyond the existing recognized local-classification contract is claimed.
- Existing diagnostic runner owns each external child/process group: eight-second and 128 KiB
  **per-child** budget, bounded pipe draining, cancellation and forced reaping, no abandoned reader
  thread. These limits do not become build/install/session deadlines. Cancellation propagates
  without publishing a result. Success still explicitly says **execution unavailable**; no
  independent helper artifact/lifetime/ownership transfer, fresh-verifier capability, restored-
  terminal handoff, target/source consent, replacement/recovery or automatic restart exists here.

  | Final complete layer | Result |
  |---|---|
  | Python 3.11/current | **1702 passed, 84 opt-in skips**, 227.97 s |
  | Python 3.11/lowest | **1702 passed, 84 opt-in skips**, 227.03 s; two known Typer deprecations |
  | Python 3.14/current | **1702 passed, 84 opt-in skips**, 227.23 s |
  | Python 3.14/lowest | **1702 passed, 84 opt-in skips**, 223.80 s; two known Typer deprecations |
  | Affected real Docker/OpenCode/pipx/pty | **29 passed/714 logged checks**, no skips/deselections, `up16b-final`, 1222.86 s |

  Final complete commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q --tb=short
  --junitxml=.work/up16b/final-<label>.xml --basetemp=/tmp/opencode/up16b-verified<label>`;
  labels/venvs `311/venv311`, `311low/venv311low`, `314/venv314`, `314low/venv314low`, serial
  foreground with inode preflight/clean pip checks. Python 3.11.18/3.14.8; current Typer 0.27.3/
  Textual 8.2.8, lowest 0.16.0/4.0.0. All **1786 ordered IDs/outcomes identical**. **47 new default
  cases**: 45 external-tool host/process cases and two package-content gates. Existing exact
  console/metadata/license/assets/tests/retired-installer gates remain; required new modules also
  checked in wheel/sdist. No CI/release workflow, dependency bounds, CLI/UI or mutation assertion relaxed.
- Unit/host fixtures use synthetic pipx package/metadata with real isolated processes/files, not a
  mock subprocess result. Cover stdlib/helper runtime, real literal/space/symlink console parsing,
  dependency/search/import/namespace/metadata routes, target absence, lazy/missing declared paths,
  raw inventory bounds/shape, unsafe files/parents, unsupported versions/entry points/settings,
  exact source-Python spelling, effective custom locations, changed candidate and unknown options.
  Dummy credential/Python/loader environment is not forwarded or leaked; real timeout/noisy/cancel
  children are reaped. Synthetic tool packages do **not** substitute for the real pipx gate below.
- Real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up16b-final
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_42_base_coordination.py
  tests/integration/test_43_diagnostics.py tests/integration/test_44_version_evidence.py
  tests/integration/test_51_updates.py tests/integration/test_52_discovery.py
  tests/integration/test_53_environment_updates.py tests/integration/test_54_base_updates.py
  tests/integration/test_65_pipx.py tests/integration/test_66_manager_inventory.py
  tests/integration/test_67_installation_exclusion.py --junitxml=.work/up16b/real-final.xml
  --basetemp=/tmp/opencode/up16b-real-final`.
  All prior 29 affected rows/assertions rerun: base races/guards, owned diagnostics/probes,
  lifecycle/restore/evidence, discovery, environment update/rollback/independent recovery, base
  modes/candidates/copies/retained layers, pipx install/upgrade/downgrade/uninstall/data retention/
  foreign launcher, live dashboard/session/exec/base-mutation exclusion and ordinary terminal
  restoration at 80x24/larger. No subprocess/Docker result substituted or assertion weakened.
- `test_66` retains actual installed default/custom-space source/Python/options/invocation/PATH
  records and declared private Git URL rewrite/loopback release hook. New probes use actual external
  test-venv pipx 1.18.7/Python/dependencies, preserving recorded home/bin/man and source-Python
  selection. Temporarily rename **only the manifested owned application venv**, prove tools still
  work while it is absent, and always restore it before product uninstall. A test-only pipx script
  copy under that venv refuses despite its outside shebang, then the exact copy/directory is
  removed. Installation record/executable bytes remain unchanged. These are tool-independence
  facts, **not a staged helper/handoff/verification or public release-authentication proof**.
- Failure/evidence trail: missing-module reproducer collection error; direct ruff found one import
  style issue, corrected, no waiver. Early **33 passed**, 2.04 s; lowest affected **124 passed**,
  4.47 s, known warnings; early real proof **2 passed/90 checks**, `up16b-proof`, 47.85 s. Expanded
  route/mode tests **129 passed**, 4.65 s. The two source-Python preservation/alias reproducers
  **2 failed**, 0.33 s (38 unrelated cases deselected only for this minimal reproducer); fixed
  premature normalization, preserving requested selection/full route and observing canonical
  endpoint separately. Lowest extended **152 passed**, 5.09 s (known warnings).
- Initial full matrix **1699 passed/84 skips** on both 3.11 variants, 228.02/222.54 s; 3.14 current
  **1 failed/1698 passed/84 skips**, 227.40 s, and fourth variant not started. The existing declared-
  target-file fixture intentionally lacks the file: CPython 3.14's metadata file list dropped it.
  **Kept that assertion/fixture unchanged**, read bounded unfiltered raw RECORD instead and added
  malformed/empty/oversized record cases. Python 3.14 focused **80 passed**, 4.72 s. All four full
  suites rerun on corrected source and final real gate above passes; no focused result promoted
  as complete regression. Original pass/fail XML/logs/hashes retained as `pre-record-fix-*` before
  final outputs were written. No failure suppressed, assertion relaxed or campaign row deselected.
- `.work/up16b/` retains all XML/logs/source hashes/inventory; `.work/logs/up16b-*` retains real
  manifests/commands/checks. Two new product modules and packaging checker frozen before final
  complete/real gates. CLI/TUI, core/lifecycle/identity, startup/base/source locks, caches/discovery,
  metadata/backup schemas, manager version, image assets, dependencies and CI/release workflows
  unchanged from `2e6d2d0`. Both real attempts use isolated private installs/data/config/source/
  launchers, manifest temporary owned paths, restore hidden venvs, uninstall through pipx, and
  guarded product cleanup/leak checks. Final own-rootless inventory: no containers/volumes/test
  tags; original Debian `d5905c3f5026...`, Arch `418889644792...`, Arch input `3cbf69d2d595...`,
  Ubuntu `68ee22004a91...` unchanged (full IDs ignored inventory). Persistent protocol inodes,
  build cache and prior evidence retained. No user install/launcher/Python/credential, public API
  or paid-provider use; no complete campaign/optional installed-asset build/broad legacy TUI,
  privileged/socket/service, human observation, helper/handoff/replacement or release-readiness
  claim. Finish package/current records, review and commit this second UP-16 trust checkpoint
  locally, then STOP. Next remains independent helper/verifier/terminal handoff within **UP-16**,
  not UP-17; no bump/merge/push/tag/upload/publication/release work.
- Final package/document/resource checkpoint: sdist/wheel, strict twine/content validation and
  equality of both new product modules to frozen full/real hashes and wheel bytes pass, with no
  private instructions/evidence in the sdist. Document/CLI/quality subset **43 passed**, 3.25 s,
  `.work/up16b/docs.xml`, not another complete run. No remaining manager/probe/guard/watchdog Python
  process found. Guarded removal of only **16 exact manifested completed pytest roots** (own UID,
  inode agreement, no live process/socket/mount references); `/tmp/opencode` empty/**1048524 free
  inodes**. Added fixed-namespace installation lock inodes are intentional persistent protocol
  state, never stale cleanup candidates. `.work/up16b/cycle-cleanup-*.json` retains evidence;
  all XML/logs/failed matrix/source hashes/private fixtures/package artifacts/build cache/prior
  records remain intact. Final prose-only scratch is separately manifested/guarded after its run.
  No product/checker change after final complete/real gates; review, local commit on `work/updates`
  and STOP at this second verified UP-16 trust checkpoint, **not completion of UP-16**.

### UP-16 third artifact/lifetime checkpoint — 2026-10-31 — frozen non-mutating helper

- Resumed clean `work/updates` at `462d8fe`; reconciled instructions/local permissions, TODO,
  BASELINE, architecture, D-056/D-057 and the running handoff. Own-rootless identity verified:
  no containers/volumes, same four original full image IDs, `/tmp/opencode` empty. Owner reiterated
  **nothing goes to the public repository**. All work/evidence/commits local only: no upload,
  remote change, project tag, merge, push or publication. Local instructions' pre-effort state is
  historical, not a competing task or new permission. No UP-17 execution/recovery or release work.
- Investigated actual bootstrap/CLI/TUI/session and worker/lock lifetimes. Main/dashboard return
  is not process quiescence: non-daemon and thread-pool shutdown can still hold code/data work.
  The shared lease remains process-lifetime; no release, conversion or in-process reacquire
  shortcut is added. Under D-057, split at the now-verified **actual artifact and process-exit
  ownership boundary**, not a mock handoff or promise about a future verifier. **UP-16 stays
  partial**; narrow fresh-verifier access and restored-terminal handoff remain the next package.
- `manager_handoff.prepare()` is internal, with no startup/CLI/status/discovery/TUI caller. It
  freshly reuses the conservative external-tool assessment; support is never install consent.
  Freeze source copies of `manager_helper.py`, unchanged `installation_locks.py` and unchanged
  `manager_tool_probe.py` into a deterministic zipapp under a unique private own-UID 0700 directory
  in an explicitly chosen controlled parent outside the target. Zip/inventory files are single-
  link own-UID 0600, created exclusively and fsynced with the directory; local SHA-256 and inode
  identity are rechecked. This is not public-source authenticity, content attestation, a discovery
  cache, recovery journal or mutation grant. Partial artifacts are preserved rather than repaired.
- The helper entry imports only stdlib and its two frozen local copies; the diagnostic module's
  only helper use is its stdlib symlink-route primitive, not its optional pipx diagnostic main.
  No application, distribution inventory, Typer/Textual or external pipx dependency is required
  at helper runtime. Run the artifact from the already-assessed external interpreter `-I -B -S`.
  Preserve exact recorded Python spelling/routes and previous raw RECORD/tool refusal contracts;
  no tool/Python installation or switch, shell evaluation or external metadata normalization.
- `start_fixture()` requires the origin's installation identity and proper lock order, acquires/
  retains usage until true process exit, validates artifact/interpreter again and launches one
  **non-mutating fixture**. Only explicit seqpacket control, origin pidfd and artifact-directory
  descriptors cross exec; they are non-inheritable again inside the helper. No guard, terminal,
  arbitrary command, provider/pip/index/proxy/loader/Python environment or installation authority.
  Existing callable-signal launch guard prevents interruption between spawn and child ownership;
  failed starts and explicit cancel reap their exact child. No PID polling/EOF fallback when
  Linux pidfds are unavailable. No new host setup or public/default startup prerequisite.
- Frozen entry validates peer UID/PID against pidfd, request shape/bounds/protocol, stdlib flags/
  runtime/search/routes, artifact hash/private ownership/directory inode and no inherited protocol
  locks. Readiness and fixture arming are separate. Before arming, lost origin/channel abandons;
  after arming, channel EOF alone is never quiescence. Wait on **actual origin termination**, not
  main return, thread cancellation, lease release or guessed PID liveness. Then try unchanged
  installation-exclusive access once. Another live shared/exclusive holder produces busy without
  waiting/retry; otherwise write one bounded private fixture result under exclusion, release the
  helper's guard and exit. No verifier/ordinary CLI bypass, install/pipx/Docker/network dispatch,
  automatic dashboard restart or persistent process/service. Even SIGKILL after fixture arming
  can only produce a non-mutating result, never terminal-restoration proof or future consent.
- Fixture protocol has a maximum 30-second budget and eight-second request/readiness bound;
  these are **not installation/mutation deadlines**. The living origin owns cancel/reap; once an
  armed origin exits, the helper owns its remaining finite lifetime and retained private artifact/
  result. Explicit discard refuses a live child or changed/unfamiliar bytes, records, ownership,
  inode or files. Tests use a scoped subreaper to adopt/reap the exact orphan, restore its prior
  supervisor state, and never signal a reaped PID. No generic disk scavenger or new recovery store.

  | Final complete/real layer | Result |
  |---|---|
  | Python 3.11/current | **1763 passed, 84 opt-in skips**, 238.53 s |
  | Python 3.11/lowest | **1763 passed, 84 opt-in skips**, 232.91 s; two known Typer deprecations |
  | Python 3.14/current | **1763 passed, 84 opt-in skips**, 242.52 s |
  | Python 3.14/lowest | **1763 passed, 84 opt-in skips**, 232.26 s; two known Typer deprecations |
  | Affected real Docker/OpenCode/pipx/pty | **29 passed/732 logged checks**, no skips/deselections, `up16c-verified`, 1032.84 s |

- Full commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q --tb=short
  --junitxml=.work/up16c/verified-<label>.xml --basetemp=/tmp/opencode/up16c-verified<label>`;
  `venv311/311`, `venv311low/311low`, `venv314/314`, `venv314low/314low`, serial foreground,
  inode preflight/four clean pip checks. Python 3.11.18/3.14.8, current Typer 0.27.3/Textual 8.2.8,
  lowest 0.16.0/4.0.0. All **1847 ordered IDs/outcomes identical**. **61 new default cases**: 59
  actual host/process helper cases plus two required-module package gates. Existing mocked,
  host/files/Git/process, pilot/terminal, security/lifecycle/recovery and static assertions retained.
- New host cases cover private deterministic artifact/source equality, staging outside/symlink
  routes, unsafe/missing/relative parents, changed artifact bytes/inodes/permissions/hardlinks/
  symlinks/directory and unfamiliar inventory/result/files preservation. Actual independent
  process control, peer/pidfd/channel/protocol/boolean/large/malformed/oversized/duplicate requests,
  no generic helper dispatch, no inherited guards or credential/Python environment, fork-origin
  refusal, single use, lock order, required pidfd and no descriptor leak, expiry/cancel/readiness
  failure and INT/TERM/HUP at spawn with exact reaping. Actual normal/killed armed/unarmed origins,
  main return with non-daemon or thread-pool shutdown, socket EOF without process death and another
  supported live shared instance. Synthetic external pipx metadata is real-process boundary
  coverage, not substituted for the actual installed-package proof below.
- Real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up16c-verified
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_42_base_coordination.py
  tests/integration/test_43_diagnostics.py tests/integration/test_44_version_evidence.py
  tests/integration/test_51_updates.py tests/integration/test_52_discovery.py
  tests/integration/test_53_environment_updates.py tests/integration/test_54_base_updates.py
  tests/integration/test_65_pipx.py tests/integration/test_66_manager_inventory.py
  tests/integration/test_67_installation_exclusion.py --junitxml=.work/up16c/real-verified.xml
  --basetemp=/tmp/opencode/up16c-real-verified`. Prior 29 rows/assertions all rerun, including
  both packaged/retained base races/rollback/pins/layers, diagnostics/real binary/lifecycle/
  restore/discovery, environment update and independent recovery, cached/full refresh, pipx
  lifecycle/data retention/foreign launchers, active dashboard/session/exec/base-mutation exclusion
  and 80x24/larger ordinary terminal restoration. No Docker/mutation/verification response mocked.
- Extended actual default/custom-space `test_66` without replacing existing assertions. An origin
  runs from the **installed application's own Python/package**, leases before application imports
  and freezes helper source from that package, explicitly asserting it is not the source checkout.
  An actual non-daemon worker keeps the origin/usage live after main returns; helper result remains
  absent and exclusive access refuses. Manifest and temporarily rename only that owned venv,
  close the origin's input so process shutdown completes, then prove the frozen stdlib helper
  observes actual death and acquires exclusion while target is absent. Supervisor adopts/reaps
  the exact child. Restore the venv in finally, assert original source/launcher bytes unchanged
  and original manager operational, then product/pipx cleanup. Staged helper/result retained as
  evidence. This is **not a restored-terminal handoff or public release-authentication proof**;
  private Git URL rewriting and loopback discovery fixtures remain declared exactly as before.
- Failure trail: absent-module collection reproducer; first helper feedback **1 failed/31 passed**
  then KeyboardInterrupt (new AST assertion included the bundled diagnostic's unused optional
  imports; test spawn wrapper also intercepted its later exclusion child). Scoped AST checks to
  the actual import boundary, leaving helper/lock imports strict and real `-S`/absence proof;
  restore test wrapper before its later child. Next selected **4 failed/141 passed**, 11.76 s:
  three origin fixtures used input() at communicate EOF, plus import/fixture-alias lint. Corrected
  test driving to read EOF/imports without changing exit/reaping/refusal assertions. Lowest
  selected **145 passed**, 12.22 s; expanded helper/static **70 passed**, 10.05 s; package/helper/
  static **91 passed**, 10.16 s. Early real proof **2 passed/108 checks**, `up16c-proof`, 50.21 s.
- First full matrix **1761 passed/84 skips each**, 238.63/234.82/242.35/235.69 s; first affected real
  **29 passed/732 checks**, `up16c-final`, 1022.21 s. Final review added two huge-integer budget
  reproducers: **2 failed/57 unrelated cases deselected**, 0.32 s. Calling math.isfinite converted
  a bounded-wire large integer to float and raised OverflowError instead of static refusal.
  Direct bounded numeric comparison rejects it and NaN/infinity without conversion. **Kept both
  assertions unchanged**. Python 3.14 affected **182 passed**, 16.68 s; then all four complete
  suites and all 29 affected real rows reran on corrected code, results above. Original final-*/
  real-final evidence and pre-budget-fix source hashes retained, not overwritten or promoted as
  final-code proof. No skipped/waived failure, softened refusal or focused-as-full claim.
- Final `.work/up16c/final-source-sha256.json` freezes both new product modules/checker with the
  unchanged bundled lock/probe/tool source before final complete/real gates. CLI/launcher/TUI,
  startup usage/lock implementation, assessment/source-Python/raw RECORD contracts, caches/
  discovery, lifecycle/identity/recovery/journals, version/schemas, assets, dependencies and CI/
  release workflows unchanged from `462d8fe`. No fresh-verifier bypass or ordinary CLI dispatch
  under an environment/argument override. Active-operation/session refusal and terminal ownership
  handoff remain independent pending gates; UP-17 target/source authentication/revalidation,
  consent, actual replacement and pre/during/post recovery guidance remain separate.
- All three real attempts used isolated manifested private installs/data/config/sources/launchers,
  guarded product cleanup/leak checks, exact helper supervision and finally-restored venvs.
  Final own-rootless inventory has no containers/volumes/test tags and exactly the previous four
  full original image IDs (`final-inventory.json`). Shared build cache, prior evidence and all
  persistent protocol inodes retained; run-owned helper artifacts/results remain ignored evidence.
  No user install/launcher/Python/credential, host service/default context, paid API/provider or
  host OpenCode V2 execution. No complete campaign, optional installed-asset build, broad legacy
  TUI, privileged/socket/service, human manual-observation, actual helper terminal-handoff,
  replacement/recovery or release-readiness claim. Finish final package/docs/resources, review,
  local commit on `work/updates` and STOP at this verified artifact/lifetime boundary; **UP-16 is
  still partial**. Nothing is merged, pushed, uploaded, tagged in the project or published.
- Final package/resources: no-isolation sdist/wheel, strict twine/content validation and equality
  of all five bundled/orchestrating product modules to frozen full/real source and wheel bytes
  pass. No private local instructions/evidence in sdist. Document/CLI/quality subset **43 passed**,
  3.25 s (`docs.xml`), not another complete suite. No remaining manager/helper/probe/guard/watchdog
  Python process found. Removed only **19 exact manifested completed pytest roots** after own-UID/
  inode and live process/socket/mount checks; `/tmp/opencode` empty, **1048170 free inodes**. All
  real staged helper/results, XML/logs/failed runs/source hashes/packages/prior evidence/build
  cache preserved; added fixed-namespace protocol inodes are persistent, never stale cleanup.
  Evidence `.work/up16c/cycle-cleanup-*.json`. Any final prose-only scratch is separately manifested
  and guarded; no product/checker change followed the final four complete suites/real gate. Review,
  local commit and STOP at this artifact/lifetime boundary; next narrow verifier/terminal handoff,
  **not UP-16 completion or UP-17 replacement**.
- Prose-only follow-up: **27 passed**, 1.86 s, `.work/up16c/prose.xml`; language/links/CLI only,
  not replayed full/real verification. Final documentation-bearing artifacts are retained under
  `.work/up16c/package-final/`. Review intended source/test/current-record diff, then local commit
  on `work/updates` and STOP. No publication operation is authorized or performed.

### UP-16 fourth verifier-access checkpoint — 2026-10-31 — fixed read-only runtime access

- Resumed clean `work/updates` at `35c035a`, verified own-rootless identity/no containers or
  volumes/original four images unchanged, read instructions/local permissions/current records.
  Owner's no-public-repository constraint remains absolute; no push/upload/remote operation,
  project tag, merge, release or version change. Scope is narrow verifier access, not UP-17.
- Added internal fixed `manager_verifier.py`, optional non-mutating helper verification and
  installation-scoped **unlocked read-only witness** issuance under an existing own-process
  exclusive guard. No normal startup exemption or ordinary CLI dispatch. A private channel,
  owner pidfd and nonce bind the query; kernel credentials identify actual packet senders.
  The client's witness names the private persistent inode, but has no flock. The live peer's
  own descriptor/fdinfo must prove full-file exclusive ownership. No exclusive description is
  passed to the fresh process. Close witness before fixed observed version/prefix/module facts;
  no core/CLI/Docker/config/discovery work, source/launcher authentication or replacement-success
  grant. Freeze the module with the independent helper, require it in wheel/sdist. No UI consumer.
- External stdlib bootstrap checks the live peer/witness before execing only the target venv's
  existing Python/dedicated module, setting PR_SET_PDEATHSIG/SIGKILL before target site hooks.
  No preexec_fn or weakened at-fork rules. Reserve direct leader with WNOWAIT through group
  termination/reap. Query is eight-second/4096-byte bounded, further limited by remaining fixture
  budget; never an install/build/session deadline. Parent holds exclusive through result/child
  cleanup. Exact transient witnesses are non-inheritable by default and fork-cleaned without
  unlock; existing normal shared/process-lifetime usage is untouched. Test teardown now asserts
  no leaked witness registry; it does not silently clear failures.
- Missing-capability reproducer **1 failed**, 0.02 s. First selected feedback **2 failed/141
  passed**, 17.28 s: replaced-inode fixture correctly also refused on context exit, and two unused
  test imports; corrected test driving/imports, no waiver. Lowest selected **179 passed**, 17.83 s;
  extended **224 passed**, 20.29 s. Early real **2 passed**, `up16d-proof`, 53.53 s, is retained as
  **pre-witness-design evidence**, not the final implementation proof.
- Review found an actual flaw in the first uncommitted design (borrowed locked descriptor): an
  early target site hook could spawn a descendant with close_fds=False and retain exclusion
  after helper/direct-verifier death. Real-process minimal reproducer **1 failed/44 unrelated
  cases deselected**, 0.30 s, `descendant-repro.xml`. Kept that test unchanged. Replaced lock
  export with an independent unlocked O_RDONLY witness and live peer fdinfo proof; no lease
  descriptor crosses exec at all. Witness process set/fork cleanup replaces the earlier draft
  borrowed set. Kernel per-message credentials prevent startup-descendant replies impersonating
  the actual fresh PID. This is advisory coordination, not security against malicious same-user
  tooling; arbitrary site hooks remain existing trusted code, with no promise to stop escaped work.
- Post-fix host/lock/helper/static **161 passed**, 17.75 s; actual default/custom-space pipx
  **2 passed**, `up16d-witness-proof`, 50.22 s. Real negative startup hooks now deliberately spawn
  a manifested descendant, kill/reap the helper and direct verifier, prove exclusion is free
  **while the descendant still lives**, then kill/reap that exact descendant. Actual original
  installation bytes/records/launcher remain unchanged and operational; all previous real
  classification/tool/helper-absence/terminal assertions retained. Python 3.14 final focused
  verifier/helper/locks/tools/package/static **237 passed**, 24.04 s. Sources/checker frozen in
  `.work/up16d/final-source-sha256.json` before complete gates; no product change since.
- First complete matrix: **1818 passed/84 opt-in skips** on Python 3.11/current (246.50 s),
  3.11/lowest (241.36 s) and 3.14/current (244.62 s); 3.14/lowest **1 failed/1817 passed/84 skips**,
  239.63 s. Existing `test_diagnostics.dead()` caught ENOENT but not ESRCH when a task vanished
  between procfs open and read. The actual descendant had disappeared; keep its termination/
  deadline assertions unchanged. Deterministic new helper tests: **1 failed/3 passed/49 unrelated
  deselected**, 0.06 s, `procfs-repro.xml`. Catch only FileNotFoundError/ProcessLookupError, not
  arbitrary OSError. Add explicit PermissionError propagation and actual-live-PID negative
  assertions. Lowest Python 3.14 affected **223 passed**, 22.97 s, known Typer warnings only.
  Initial XML/logs are preserved separately from the corrected final gates below; no failed
  result suppressed or focused run presented as complete.
- Final compatibility: **1822 passed/84 opt-in skips in each of four serial foreground runs**,
  Python 3.11/current **245.63 s**, 3.11/lowest **239.45 s**, 3.14/current **243.72 s**, 3.14/lowest
  **239.39 s**. Python 3.11.18/3.14.8, current Typer 0.27.3/Textual 8.2.8, lowest 0.16.0/4.0.0;
  four clean pip checks, inode preflight, only two known lowest-Typer deprecations. **1906 ordered
  IDs/outcomes identical**. Commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest
  -q --tb=short --junitxml=.work/up16d/verified-<label>.xml
  --basetemp=/tmp/opencode/up16d-verified<label>`; venv/label pairs `venv311/311`, `venv311low/311low`,
  `venv314/314`, `venv314low/314low`. Initial first matrix remains `final-*`, corrected `verified-*`;
  hashes before procfs correction retained as `pre-procfs-fix-source-sha256.json`.
- **59 new default cases**: 54 verifier host/process, four diagnostic helper observations, one
  required-module package gate. Positive fresh target runtime via minimal no-pip actual CPython
  venv/package fixtures (no distribution/provenance/installability claim), no CLI/core/data/
  config/Docker work; kernel witness/owner/namespace/mode/shape/refusal and actual process/nonce/
  credential limits, no generic helper/module/CLI bypass. Shared/unheld/POSIX/wrong-owner/prefix/
  inode misuse, correct lock order, read-only/CLOEXEC/fork hygiene, unchanged parent exclusive,
  real timeout and helper/direct-verifier/early-descendant interruption. Fixed-runtime hook proves
  witness already closed during query while ordinary launcher remains excluded. Unexpected
  SCM_RIGHTS are closed/rejected, kernel actual sender PID is checked, raw diagnostics/dummy
  secrets not leaked, malformed/unknown records preserved. Strict test witness-set assertions
  never clear a leak to hide failure. Previous real host/terminal/pilot/security/lifecycle/Git/
  backup/recovery assertions stay intact; four new diagnostic cases narrow observation semantics,
  not termination deadlines or acceptance.
- Final affected real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up16d-final
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_42_base_coordination.py
  tests/integration/test_43_diagnostics.py tests/integration/test_44_version_evidence.py
  tests/integration/test_51_updates.py tests/integration/test_52_discovery.py
  tests/integration/test_53_environment_updates.py tests/integration/test_54_base_updates.py
  tests/integration/test_65_pipx.py tests/integration/test_66_manager_inventory.py
  tests/integration/test_67_installation_exclusion.py --junitxml=.work/up16d/real-final.xml
  --basetemp=/tmp/opencode/up16d-real-final`: **29 passed/762 logged checks**, no skips/deselections,
  **996.24 s**. All earlier 29 rows/assertions retained, including both-distro packaged/retained
  base races/rollback/pins/layers, real bounded diagnostics/binary/lifecycle/restore, discovery,
  environment actions and independent recovery, cached/full refresh, pipx install/upgrade/downgrade/
  uninstall/data/foreign-launcher, actual attached session/exec/base mutation exclusion and ordinary
  80x24/larger terminal restoration. No Docker/installation/verification response substituted.
- Both real `test_66` layouts retain original classification/source/Python/settings/launcher,
  tool independence and helper-from-installed-package/target-absence assertions. New query uses
  actual installed target Python/module, reports exact version/prefix/module under exclusive
  helper, then reaps without deadlock. Negative real startup hook spawns a manifested descendant
  with close_fds=False; kill/reap helper and direct verifier, prove exclusion is free **while that
  descendant lives**, then terminate/reap it. Normal installed startup remains refused while
  helper holds exclusive, unchanged original package/record/executable still works afterward.
  Exact hook files removed in finally, helper artifacts/results retained as ignored evidence.
  Private Git URL rewrite/loopback hooks are declared, not public source authentication. Real
  proofs: pre-witness **2/134 checks**, corrected **2/138 checks**; final **29/762 checks** above.
- Final own-rootless inventory matches the previous complete four image IDs exactly; no
  containers/volumes/test tags remain. All deliberate helper/verifier/descendant processes are
  adopted/reaped, no user installation/launcher/Python/credential or host service/default context
  changed. `.work/up16d/` and `.work/logs/up16d-*` retain all failed/pass evidence, commands,
  manifests/source hashes; final product/checker/diagnostic-helper/fixture sources frozen before
  corrected four complete suites and real gate. Persistent protocol inodes/prior evidence/build
  cache preserved. No complete campaign, optional installed-asset build, broad legacy TUI,
  privileged/socket/service, real provider/paid use, human observation, actual restored-terminal
  handoff/replacement/recovery or release-readiness claim. No bump/merge/push/upload/remote change/
  project tag/publication. Finish package/docs/guarded scratch review, local commit, then STOP at
  this verified witness-access safety boundary; it does not complete UP-16 by inference.
- UP-16 remains **partial**. Stop at the verified descriptor/witness-access safety boundary once
  final gates finish; restored-terminal transfer/active mutation/session refusal remain next.
  Runtime facts are not UP-17 expected source/commit/launcher/basic-CLI/result/recovery evidence.
  Manager Update stays disabled. No CLI/launcher/TUI/core/identity/cache/journal/schema/asset/
  dependency/release workflow change or general package executor is authorized.
- Final package/resources: no-isolation sdist/wheel, strict twine/content and byte equality of five
  product modules to frozen full/real source and wheel pass; private local instructions/evidence
  absent from sdist. Document/CLI/quality subset **43 passed**, 3.20 s (`docs.xml`), not another
  complete run. No remaining manager/helper/verifier/probe/guard/watchdog Python process found.
  Guarded removal of **21 exact manifested completed pytest roots**, with own-UID/inode/live
  process/socket/mount checks; `/tmp/opencode` empty/**1047461 free inodes**. All real staged helper/
  result evidence, failed/pass XML/logs/source hashes/artifacts/prior records/build cache retained.
  Added fixed-namespace lock inodes are persistent protocol state, never stale cleanup. Exact
  cleanup evidence `.work/up16d/cycle-cleanup-*.json`. Final prose-only scratch is separately
  manifested/guarded; no product/checker/test-helper change after final complete/real gates. Review,
  local commit on `work/updates` and STOP; next restored-terminal ownership handoff, **not UP-17**.
- Prose-only follow-up **27 passed**, 1.84 s, `.work/up16d/prose.xml`; language/links/CLI only,
  distinct from complete/real gates. Final documentation-bearing artifacts under
  `.work/up16d/package-final/`. Review intended diff, commit locally and STOP at this verified
  witness boundary; nothing published and no actual manager replacement enabled.

### UP-16 fifth terminal-handoff checkpoint — 2026-10-31 to 2026-11-01 — complete non-mutating handoff

- Resumed clean `work/updates` at `14112de`; own-rootless inventory equals the previous four
  full image IDs, no containers/volumes. No-publication/local-only constraints retained. Scope:
  internal non-mutating restored-terminal handoff and active operation/session refusals, not UP-17.
- Investigation: both CLI dashboard entry paths directly discarded App.run results. Textual's
  Linux driver restores termios and enqueues visual teardown, then its close joins the writer;
  worker task cancellation is not actual thread completion. Dashboard `_attach_ready` clears
  `_operation_pending` before suspend/interactive, requiring explicit session lifetime. No early
  lease release or in-process exclusive upgrade is safe. Missing request reproducer **1 failed**,
  .31 s (`repro.xml`). Added only an internal method/typed unused-artifact fixture request; no
  public UI/key/command/env trigger, source/target/install payload or automatic staging/probing.
- CLI `_dashboard` now unifies implicit/explicit entry, observes original foreground tty/streams/
  identity/modes, and accepts only exact matching request after zero-code full Linux driver exit
  and input/output thread shutdown. Exact termios/foreground/descriptor checks, no repair or
  headless/inline/custom-driver fallback. Flush static non-mutating output, start existing helper,
  recheck terminal, then arm/close control; any failed start/check/arm cancels/reaps exact child.
  Usage remains held through real process exit. Existing pidfd/non-waiting exclusion and fixed
  verifier/unlocked witness code unchanged. 30-second fixture limit is not an updater deadline.
- App-local actual-body admission barrier refuses live work and queued tasks, prevents late
  canceled queue entry after sealing, never cancels a live operation. Existing app-owned config
  recovery stays app-owned (review caught a provisional screen-owned decorator; corrected before
  final gates with explicit ownership/body-tracking regression). Session lifetime covers suspend/
  interactive/resume and finally. Open screens/consents, invalid/used/foreign artifacts, off-UI
  callers refuse without sealing/exit/helper. Ordinary quit never reuses a refused request.
- Focused feedback **113 passed**, 68.98 s. First host/helper/static **2 failed/91 passed**,
  24.53 s: test harness treated explicit Typer SystemExit(0) as failure; static import/noqa/class
  annotations. Correct test-only exit accounting/formatting; helper already correctly armed.
  Lowest host/helper/static **1 static import failure/92 passed**, 14.98 s, then lowest Python
  3.14 terminal/static **45 passed**, 9.01 s. Extended Python 3.14 UI/helper/verifier/static
  **245 passed**, 103.24 s. Latest lowest 3.11 terminal/tools/classification/static **134 passed**,
  13.03 s, known two Typer deprecations only. These are focused, not complete-suite evidence.
- Installed real proof `up16e-proof` **2 failed**, 97.52 s at real worker completion, not waived.
  Improved fixture output pumping/captured pty bytes and explicit worker-error evidence; removed
  duplicate super.on_mount invocation (Textual already dispatches inherited handlers). Second
  `up16e-proof2` **2 failed**, 38.41 s, exposed actual root cause: isolated HOME hid rootless Docker
  contexts, and product identity correctly refused. Retain read-only existing DOCKER_CONFIG exactly
  as the established installed-pipx lifecycle row; no context/daemon/default/identity response or
  credential copied/changed. Third `up16e-proof3` **2 passed**, 75.36 s: both actual installed pipx
  layouts/terminal sizes, helper/fresh verifier, shutdown drain, live/canceled approved work then
  real Debian/Arch start, actual attached shell/client refusal and return, changed real tty modes,
  second installed dashboard refusal. All earlier assertions retained. Failed and corrected
  attempts preserve evidence/guarded cleanup; no unexecuted rows claimed.
- First complete checkpoint: **1861 passed/84 opt-in skips each**, Python 3.11/current 257.21 s,
  3.11/lowest 248.81 s, 3.14/current 254.04 s, 3.14/lowest 255.94 s. All **1945** ordered outcomes
  identical; real affected **29 passed/872 checks**, `up16e-final`, 1013.47 s. Final review fixed
  only default-test optional `pyte` guards and import-path teardown (monkeypatch); no assertion,
  timeout or product change. Absence of optional host renderer is explicit skip, never exercised
  in these gates; real campaign requires it. Keep `full-*`/`real-final.xml` and pre-refinement
  `pre-test-isolation-source-sha256.json` separate from final gates, not overwritten or suppressed.
- Final compatibility: **1861 passed/84 opt-in skips each**, Python 3.11/current **253.43 s**,
  3.11/lowest **248.04 s**, 3.14/current **256.13 s**, 3.14/lowest **249.14 s**. Four clean pip
  checks/inode preflight, Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest
  0.16.0/4.0.0. All **1945 ordered IDs/outcomes identical**, only two known lowest-Typer warnings.
  Commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q --tb=short
  --junitxml=.work/up16e/verified-<label>.xml --basetemp=/tmp/opencode/u16e-v<label>`;
  venv/label pairs `venv311/311`, `venv311low/311low`, `venv314/314`, `venv314low/314low`, serial foreground.
- **39 new default cases**, all executed (no new skip in the final matrix): operation/session/
  open consent/UI-thread/stale/foreign request refusals; no seal/helper on refusal; real canceled-
  live body versus task status, queued/sealed admission, exception cleanup, config recovery app
  ownership after Close, successful UI request without launch, CLI abnormal return, failed
  restore/arm exact cancellation. Primitive tty mode/foreground/stream/closed/reuse/thread tests
  use real pty files/modes and supplied foreground observations; **six actual host-pty cases**
  independently use real process/session/driver/terminal/leases/helper with no such patch. Both
  terminal sizes/entry paths, canonical/echo and alternate-screen/cursor/mouse teardown before
  flushed handoff output, armed/main-return versus actual shutdown death, live/canceled-worker
  refusal, ordinary quit/no reused request, and changed-mode refusal. Host diagnostics are disabled
  only in host-only layer; actual installed real tests retain real daemon/operations/session clients.
- Final affected real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up16e-verified
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_42_base_coordination.py
  tests/integration/test_43_diagnostics.py tests/integration/test_44_version_evidence.py
  tests/integration/test_51_updates.py tests/integration/test_52_discovery.py
  tests/integration/test_53_environment_updates.py tests/integration/test_54_base_updates.py
  tests/integration/test_65_pipx.py tests/integration/test_66_manager_inventory.py
  tests/integration/test_67_installation_exclusion.py --junitxml=.work/up16e/real-verified.xml
  --basetemp=/tmp/opencode/u16e-verified`: **29 passed/872 logged checks**, no skips/deselections,
  **1183.76 s**. All earlier 29 rows/assertions retained: packaged/retained base guards/races,
  pins/rollback/layers, bounded diagnostics/lifecycle/binary/restore, default-off discovery,
  environment actions and independent recovery, cached/full refresh, pipx install/upgrade/
  downgrade/uninstall/data retention/foreign launcher, live session/exec/mutation exclusion and
  ordinary terminal restoration. No Docker/verifier/install reply replaced by a mock.
- Each actual default/custom-space installed pipx package adds **seven real terminal scenarios**,
  test-only F9 injection (never a product key). Exact real CLI/App/driver/terminal/helper/verifier
  path; implicit 80x24 and explicit 120x40, non-daemon shutdown drain (origin still leased and
  helper has no result), live and canceled actual body then real Debian/Arch start without cancel,
  actual attached Docker shell/client refusal and return, changed real tty modes refused before
  helper launch, second real installed dashboard busy refusal. Every successful helper performs
  fixed runtime access after actual origin exit; not expected source/launcher/replacement proof.
  Original package records/executable unchanged and operational; no automatic restart.
- Final product/checker/test fixture hashes retained in `.work/up16e/final-source-sha256.json`;
  no source/helper/test change after final complete/real gates. Own-rootless inventory equals
  original four full image IDs, no containers/volumes/test tags. No remaining owned manager/
  helper/verifier/terminal/probe/guard/watchdog Python process. Preserve private fixture Git
  transport qualification, all failed/pass evidence/artifacts, shared cache and persistent lock
  inodes. UP-16 is **complete only for non-mutating handoff**, Manager Update stays disabled.
  No UP-17 expected source/target consent, actual replacement/success/launcher/CLI verification
  or failure recovery implied. No full campaign, human/manual observation, privileged/socket/
  service, provider/paid API or release-readiness claim. No bump/merge/push/upload/remote change/
  project tag/publication. Finish package/docs/guarded scratch review, local commit and STOP.
- Package/static/resource follow-up: no-isolation sdist/wheel, strict twine/content validation and
  eleven frozen product-file/wheel byte comparisons pass; no private local instructions/evidence
  in sdist. Document/CLI/quality **43 passed**, 3.35 s (`docs.xml`), not a complete suite replay.
  No owned manager/helper/verifier/terminal/probe/guard/watchdog Python processes remain. Guarded
  removal of **21 exact manifested completed pytest roots**, checking own UID/inode, live process/
  socket/mount references; **960 host fixture records/artifacts** archived before removal. All
  actual installed helper/results/pty bytes, failure/pass evidence/hashes/packages, prior records,
  shared build cache and persistent protocol inodes preserved. `/tmp/opencode` empty/**1046809
  free inodes**; prose-only scratch separately manifested/guarded. No product/checker/test change
  after final four complete/real gates. Review intended diff, commit locally and STOP; next UP-17.
- Final prose-only language/link/CLI follow-up **27 passed**, 2.06 s (`prose.xml`), not complete
  regression. Final documentation-bearing artifacts `.work/up16e/package-final/`; all final
  product/checker/test hashes intact. Commit locally on `work/updates` and STOP at completed UP-16,
  with Manager Update disabled; UP-17 replacement and independent recovery remain the next package.

### UP-17 first exact-source checkpoint — 2026-11-01 — verified read-only source boundary

- Resumed clean `work/updates` at `6b99ccd`; own-rootless inventory matches UP-16's four original
  full image IDs, no containers/volumes. All prior evidence/cache/persistent protocol inodes
  preserved. No public trigger or updater exists. This cycle isolates source identity, not the
  much larger installation-consent/replacement/failure-recovery package (D-057 safety split).
- Investigation: local classification only reconciles installed records and cannot authenticate
  a remote tag. Discovery accepts published release metadata, but `target_commitish` is not an
  exact commit (may be a branch). No later executor may treat either as a source/consent grant.
  Reproducer for missing exact-source API **1 failed**, .02 s (`.work/up17a/repro.xml`).
- New internal `manager_targets` observes the exact official published full release by tag,
  release ID/publication/notes and exact Git ref. Validate canonical official URLs, full lower-
  case 40-character OIDs, zero to four annotated tags and exact commit; cycles/unknown types/
  duplicates/non-finite JSON/foreign or mixed identities refuse. Bracket the graph with fresh
  ref/release reads; a frozen in-memory Target preserves the entire OID chain and full bounded
  notes hash. `revalidate` fetches the same target, compares all consent-relevant source fields
  except observation time, and never substitutes latest or reuses cache success after failure.
  Target is evidence, **not consent**. GitHub HTTPS/API trust is not signed-tag authentication,
  a remote lock/atomic snapshot or proof source builds the expected package. Later tag movement
  still requires actual installed-commit verification. No caller/consumer/install payload yet.
- Whole read-only graph (including source-lock wait) has an eight-second diagnostic budget and
  128 KiB per-response bound. Actual isolated stdlib HTTP children, no redirects, token/cookie/
  proxy credential/loader/site/index environment or Git execution. Only strict newer versions;
  no implicit reinstall/downgrade. No mutation, process-lifetime lease, frozen helper/verifier or
  driver changes. Independent install/environment/proxy/index consent remains pending, not
  silently inferred from the source probe's minimal environment.
- Separate durable disposable attempt-before-request record contains no target/consent/recovery
  state. Same GitHub source guard, no mutation while held; exact calls serialize but always make
  fresh requests. Retry-After/rate-reset from either exact-source or discovery paths blocks both;
  source success/failure never overwrites latest-release success/daily claims. Unsafe claim/source
  storage refuses without repair; default-off daily discovery remains unchanged.
- Feedback **2 failed/142 passed**, 15.08 s: test fixture reused one annotated-tag OID for two
  different tag payloads (fixed to distinct immutable objects), and a static exception-type
  warning. Python 3.14/lowest source/release/terminal/quality **188 passed**, 27.58 s, only known
  Typer warnings. Subsequent primary source/release/package/docs/static **1 documentation failure/
  202 passed**, 17.62 s: prose slash looked like an internal path to the public-reference guard;
  reworded, no guard weakened. New actual cancellation/cache-separation/transport-boundary tests
  and required-package-module check added before final source freeze/full gates.
- Affected installed proof `up17a-proof`: **2 passed**, 76.83 s, both default/custom-space actual
  pipx packages, all prior helper/verifier/terminal/lifecycle assertions retained. Added actual
  installed source module, private annotated Git source/OIDs, fresh separate-process same-target
  reads, moved target refusal, HTTP 429 and persistent source/discovery throttling, unchanged
  installed records/launcher and operation. Private Git/loopback API is explicitly a test transport,
  **not public GitHub authentication**, installation/expected-build verification or replacement.
- Initial complete primary suite **1 lint failure/1958 passed/84 opt-in skips**, 265.47 s; one
  nested test-context style warning in the final added source-lock budget test. No runtime
  assertion failed and no other preliminary complete combination run. Combined the same contexts
  without altering assertion/lock order/budget, then focused source/quality **113 passed**, 12.28 s
  (`static.xml`). Preserve `full-311.xml`/log and `pre-static-source-sha256.json` separately.
- Final complete matrix: **1959 passed/84 opt-in skips each**, Python 3.11/current **264.68 s**,
  3.11/lowest **261.97 s**, 3.14/current **267.11 s**, 3.14/lowest **263.63 s**. Four clean pip
  checks/inode preflight, serial foreground; Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual
  8.2.8 and lowest 0.16.0/4.0.0. All **2043 ordered IDs/outcomes identical**, only two known
  lowest-Typer warnings. No new skip. Commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python
  -m pytest -q --tb=short --junitxml=.work/up17a/verified-<label>.xml
  --basetemp=/tmp/opencode/u17a-v<label>`; venv/label pairs `venv311/311`, `venv311low/311low`,
  `venv314/314`, `venv314low/314low`. All final product/checker/test inputs frozen in
  `.work/up17a/final-source-sha256.json`; no such input change after these complete/real gates.
- **98 new default cases**: 97 source validation/real HTTP and child/cache/refusal/concurrency
  cases plus one required-source-module wheel/sdist gate. Lightweight and nested annotated tags,
  canonical release/ref/object/commit identities and strict newer versions; cycles/depth/mixed
  OID type/foreign or malformed/duplicate/non-finite data; observed source changes during graph
  bracketing; release ID/publication/full notes hash changes; same target, not latest or cached
  fallback; real total budget and inflight cancellation, queued source-lock budget/cancellation;
  source/discovery serialization and independent success claims; numeric/date-rate parser reuse,
  status 403/429/503 with Retry-After/reset in both directions, process restart/unsafe-storage
  refusal and no path/secret echo. Fixed HTTP children only, no Docker/tool/handoff work.
- Final affected real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up17a-final
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_42_base_coordination.py
  tests/integration/test_43_diagnostics.py tests/integration/test_44_version_evidence.py
  tests/integration/test_51_updates.py tests/integration/test_52_discovery.py
  tests/integration/test_53_environment_updates.py tests/integration/test_54_base_updates.py
  tests/integration/test_65_pipx.py tests/integration/test_66_manager_inventory.py
  tests/integration/test_67_installation_exclusion.py --junitxml=.work/up17a/real-final.xml
  --basetemp=/tmp/opencode/u17a-real`: **29 passed/888 logged checks**, no skips/deselections,
  **1135.62 s**. All prior 29 rows/assertions retained, including full source/pin/base concurrency,
  both-distro diagnostics/lifecycle/update/rollback/recovery, cached/full refresh, actual pipx
  lifecycle/foreign launcher, fixed verifier/early descendant death, real terminal modes/drivers/
  active and canceled mutation/session refusals/shutdown drain and other-manager exclusion.
  First real proof also recorded **264 checks**. No substituted Docker/verifier/install replies.
- Both actual installed pipx layouts add exact-source private annotated Git OIDs and commit,
  fresh same-target requests from separate actual installed processes, moved-tag/commit refusal,
  actual HTTP 429 then durable throttling across installed source/discovery process restarts,
  unchanged installed records/executable and operational original launcher. Private fixture tag/
  source version changes exist only under the manifested `.work` Git transport, never in the
  project or user install. This is not public network-source authentication or replacement.
- Final own-rootless inventory matches UP-16's four original full image IDs; no containers,
  volumes/test tags or owned manager/helper/verifier/terminal/HTTP/probe/guard/watchdog processes
  remain. Preserve all failed/pass logs/XML/source hashes/staged helper/results/pty evidence and
  build cache/persistent protocol inodes. Finish packaging/docs/static/guarded scratch review,
  commit locally and stop at this source-trust boundary. UP-17 remains partial; installation/
  tool/network consent/exclusive revalidation, actual replacement/expected result and independent
  failure recovery remain pending. Manager Update disabled. No human/manual/full-campaign/
  privileged/socket/service/provider/paid API/release-readiness claim. No version bump/merge/
  push/upload/remote change/project tag/publication. Evidence `.work/up17a/`, `.work/logs/up17a-*`.
- Final package/docs/resource follow-up: no-isolation sdist/wheel, strict twine/content validation
  and **42 frozen product module/wheel byte comparisons pass**; private local instructions/evidence
  absent from sdist. Package artifacts `.work/up17a/package/`. First document/CLI/quality follow-up
  **1 prose-reference failure/42 passed**, 3.43 s (`docs.xml`), same public guard's slash ambiguity
  in BASELINE, reworded; corrected **43 passed**, 3.24 s (`docs-final.xml`), focused not a complete
  replay. No guard weakened. Own-rootless inventory/original four full image IDs unchanged,
  no owned manager/helper/verifier/terminal/HTTP/probe/guard/watchdog process/container/volume/test-tag
  leaks. Guarded removal of **14 exact manifested completed pytest roots**, own UID/inode and live
  process/socket/mount references checked; **480 host fixture records/artifacts** archived first.
  All real source-target/staged helper/result/pty records, failed/pass evidence/source hashes/
  packages, prior evidence, shared build cache and persistent protocol inodes preserved.
  `/tmp/opencode` empty/**1046485 free inodes**; prose-only scratch separately manifested/guarded.
  No final product/checker/test input change. Review/stage intended changes only, commit locally
  and STOP at this verified read-only source boundary. Next: installation/tool/network consent,
  independent exclusive installation/tool/source revalidation, then actual replacement/expected-
  result and independent failure recovery. UP-17 partial and Manager Update stays disabled.
- Final prose-only language/link/CLI **27 passed**, 1.96 s (`prose.xml`), not complete regression;
  final complete/real product/checker/test hashes intact. Commit locally and stop; no further
  implementation or release action in this cycle.

### UP-17 second exact-origin review checkpoint — 2026-11-01 — verified origin-consent boundary

- Resumed clean `work/updates` at `7e4865c`; own-rootless inventory matches the original four full
  image IDs, no containers/volumes. Read source/tool/classification/handoff/terminal/lock ownership
  before design. Reproducer for absent exact-review API **1 failed**, .02 s (`up17b/repro.xml`).
  Scope: origin review/explicit internal consent/fresh origin revalidation, not independently
  exclusive post-exit validation, installer network execution, replacement or failure recovery.
- New `manager_review` prepares only a strict exact tag from fresh own runtime classification,
  canonical-prefix process-lifetime usage, actual exposed launcher and external pipx/Python facts,
  recognized locations, critical record hashes and complete observed executable/Python/module/
  location/config routes. Preserve symlink spelling/identity, inode/owner/mode and file metadata,
  hash HOME/PATH/XDG/pipx selection context. Directory timestamps excluded so unrelated cache/pyc/
  log creation is not replacement. Re-inspect local facts around exact published-source reads;
  no cached classification/Target construction/receipt is an installation capability. Reject
  special/cyclic/uncontrolled/oversized paths. Not code authenticity or a full lazy-file inventory.
- Initial policy: public defaults only. Nonempty known pip/Git/uv/Python/loader/proxy/CA/SSH-agent/
  related environment and known system/user/XDG/shared/application Git/pip/credential config
  presence require manual preservation; never read credential contents, echo values, modify/delete
  settings, or silently drop them to pass. Only a future independently tested executor can enforce
  effective public-default network behavior; this review does not construct an installer argv/env
  or assess new Git execution. Explain exact source/downloads and host package/build-code trust,
  no Python switch, user-data/config preservation, existing-instance boundaries, no automatic
  restart, force-not-backup and previous-tag recovery-not-identical-dependencies limits.
- Internal `ManagerReviewScreen` has no public entry or enabled Manager Update path. Scrollable
  read-only plain text at 80x24/larger, Cancel default, explicit exact target/network checkbox
  before Confirm. Escape/Cancel yields no receipt; Confirm yields an in-memory Approval for that
  exact immutable review, not a bool/durable grant/serialized capability. No helper preparation/
  launch/arming, revalidation or mutation happens from the form. Open consent refuses existing
  terminal handoff. Origin `revalidate` requires own PID/prefix/version, same fresh local binding
  around the same fresh source. No usage release/conversion/exclusive attempt; helper/verifier/
  driver/locks unchanged and no review payload is passed to the frozen fixture.
- Early focused **1 import-style failure/68 passed**, 13.54 s, then lowest Python 3.14 source/
  review/terminal/static **1 import-style failure/115 passed**, 30.10 s. Primary broader source/
  review/package/static **1 import-style failure/277 passed**, 33.55 s. Corrected formatting only;
  explicit Ruff **all checks passed**. No runtime assertion suppressed or weakened.
- First actual installed proof `up17b-proof` **2 failed/2 teardown errors**, 129.96 s: the real
  fixture observed the header before controls rendered and sent policy selection plus Tab/Enter
  in one input batch before Textual's Changed message enabled Confirm. The form correctly did
  not approve. Captured exact pty/state evidence; split key steps after rendered controls/policy
  processing, retained all assertions/budgets and added keyboard-only pilot regressions. Lowest
  Python 3.14 review/UI/static **79 passed**, 24.08 s. Corrected `up17b-proof2` **2 passed**, 99.87 s,
  both actual installed pipx layouts, all prior helper/source/terminal/lifecycle assertions retained.
- Six installed terminal scenarios per layout: implicit actual console/bootstrap/identity/tool/
  source preparation and review, 80x24/120x40 explicit target+policy approval and fresh origin
  revalidation; default Cancel without another source call; owned changed actual launcher after
  display refuses before another source request; custom secret-bearing index environment and
  credential-file presence refuse without secret output or source request. All exit normally/
  restore terminal with no helper/automatic restart. Private Git/API and owned site injection
  only, not public authentication or expected-build/install/exclusive-revalidation evidence.
- Final review added special-path/strict-tag/version guard, broader explicit credential-environment
  refusal, credential storage presence and unrelated directory-cache regression before final
  source freeze. Next: all four complete compatibility suites, the same full 29-row affected real
  gate with new review assertions, packaging/docs/static/resource review, exact manifested scratch
  cleanup, local commit and stop at the origin-consent boundary. Keep all evidence/cache/lock
  inodes, no version/schema/image change, bump/merge/push/upload/remote change/project tag/release.
  UP-17 partial; Manager Update disabled. Independent post-exit/exclusive validator, actual
  installer network policy/replacement/expected-result and failure recovery still require proofs.
- Final focused origin/UI/package/docs/static **145 passed**, 25.03 s (`final-focused.xml`). Final
  complete matrix **2038 passed/84 opt-in skips each**: Python 3.11/current **287.80 s**, 3.11/lowest
  **284.12 s**, 3.14/current **295.38 s**, 3.14/lowest **288.44 s**. Four clean pip checks/inode
  preflight, serial foreground, Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and
  lowest 0.16.0/4.0.0. All **2122 ordered IDs/outcomes identical**, only two known lowest-Typer
  warnings. No new skips. Commands: `env PYTHONPATH="$PWD/src" .work/<venv>/bin/python -m pytest -q
  --tb=short --junitxml=.work/up17b/full-<label>.xml --basetemp=/tmp/opencode/u17b-<label>`;
  venv/label pairs `venv311/311`, `venv311low/311low`, `venv314/314`, `venv314low/314low`. All final
  product/checker/test inputs frozen in `.work/up17b/final-source-sha256.json`; no change after
  these complete and real gates. No full-suite failure in this checkpoint.
- **79 new default cases**: 66 origin review/refusal/host route/critical-file/environment/context/
  source-change cases (synthetic own-runtime identity with actual synthetic external version-only
  diagnostics/real HTTP children, not actual pipx installation proof), 10 current/lowest Textual
  pilot cases at both sizes including keyboard-only approval, two required-module package gates,
  one new UI error-reporting contract case. All earlier source/helper/verifier/lease/terminal/body/
  session/ownership/recovery/both-distribution assertions retained. No cache grants or UI-only
  inference replaces actual file/process/HTTP and installed real evidence.
- Final affected real command: `env PYTHONPATH="$PWD/src" OCS_TEST_DOCKER=1 OCS_TEST_RUN=up17b-final
  .work/venv311/bin/python -m pytest -q -rA --tb=short tests/integration/test_42_base_coordination.py
  tests/integration/test_43_diagnostics.py tests/integration/test_44_version_evidence.py
  tests/integration/test_51_updates.py tests/integration/test_52_discovery.py
  tests/integration/test_53_environment_updates.py tests/integration/test_54_base_updates.py
  tests/integration/test_65_pipx.py tests/integration/test_66_manager_inventory.py
  tests/integration/test_67_installation_exclusion.py --junitxml=.work/up17b/real-final.xml
  --basetemp=/tmp/opencode/u17b-real`: **29 passed/954 checks**, no skips/deselections,
  **1103.14 s**, all previous 29 rows/assertions retained. Actual installed default/custom-space
  pipx packages each run six new console/pty review scenarios above; no product identity/terminal/
  lock/Docker response mocked. Initial failed installed proof logged **196 passing/2 failed
  checks** plus two main failures/two teardown errors; corrected focused installed proof logged
  **330 passing checks**, final full real **954**. No failure suppressed or assertion weakened.
- Final own-rootless inventory matches all four original full image IDs, no containers/volumes/
  test tags or owned manager/helper/verifier/terminal/review/HTTP/probe/guard/watchdog Python
  processes remain. No source/tool/classification/cache/lease/helper/verifier/driver/public UI/
  version/schema/image/dependency/workflow change. Only new internal review modules/fixtures and
  required-package-module contract; no helper payload, installer argv/env or Git execution added.
  Finish packaging/docs/static/guarded scratch cleanup, preserve all evidence/cache/persistent
  protocol inodes, commit locally and STOP. UP-17 remains partial; Manager Update disabled.
  Next independent post-exit/exclusive validator/effective installer network policy, followed
  separately by replacement/expected installed result and failure recovery. No public-source/
  signed-tag/human/manual/full-campaign/privileged/provider/paid-API/release-readiness claim.
- Final package/docs/resource follow-up: no-isolation sdist/wheel, strict twine/content validation
  and **44 frozen product module/wheel byte comparisons pass**, private instructions/evidence
  absent from sdist. Artifacts `.work/up17b/package/`. Document/CLI/quality **44 passed**, 3.35 s
  (`docs.xml`), focused rather than another complete replay. Own-rootless inventory retains all
  original four full image IDs, no owned process/container/volume/test-tag leaks. Guarded removal
  of **14 exact manifested completed pytest roots**, own UID/inode and live process/socket/mount
  references checked; **388 host fixture records/artifacts** archived first. All actual installed
  review/source/helper/results/pty records, failed/pass evidence/hashes/packages, prior evidence,
  shared build cache and persistent protocol inodes preserved. `/tmp/opencode` empty/**1046221
  free inodes**; prose-only scratch separately manifested/guarded. No final product/checker/test
  input change. Review/stage intended diff, commit locally and STOP. Independent post-exit/
  exclusive validator/effective installer network policy, replacement/expected installed result
  and failure recovery remain the next separate verified gates. Manager Update stays disabled.
- Final prose-only language/link/CLI follow-up **27 passed**, 1.98 s (`prose.xml`), not complete
  regression. Final product/checker/test hashes intact. Commit locally on `work/updates` and stop;
  no independent second task, public updater enablement or release action in this cycle.

### UP-17 third local-observation replay checkpoint — 2026-11-01 — verification in progress

- Resumed clean `work/updates` at `9a01a01`; own-rootless inventory matches all four original
  full image IDs, no containers/volumes. Investigation: origin revalidation imports the target
  application and assumes a living origin/shared lease, so it cannot be reused after death under
  helper exclusion. Split this gate at **approved local observations**, not fresh tools/source/
  network or installation authority. Missing stdlib validator reproducer **1 failed**, .02 s.
- Extracted one stdlib `manager_observations` critical-record/route implementation shared by
  origin and source-identical frozen helper. No target/package import in replay. Explicit internal
  `prepare_review_fixture` requires an exact Approval, fresh origin revalidation, private outside-
  target helper/input, digest/review identity/inode inventory. No automatic consumer, ordinary CLI
  bypass, installer argv/env, fresh tool/source/network process or recovery state. The private
  format-1 input is bounded fixture data, not a durable grant: reviewed PID/prefix/version/source/
  observation identity and selected HOME/PATH/XDG/pipx context only, never raw credentials/provider
  environment; context is not applied as an execution environment. 1 MiB input/512 KiB binding/
  128 KiB critical record/2048 route bounds, strict JSON/shape/known record boundaries.
- Preserve actual pidfd origin-death proof, one non-waiting exclusive attempt, three inherited
  descriptors, all lease/fork/exec/witness/driver/admission semantics and 30-second fixture bound.
  Only under helper-owned exclusion, prove the own exact kernel flock with an unlocked witness,
  validate private input, compare routes, hash exact approved critical records, compare routes
  again. No child/target code runs. Fail static `review-failed`, never follow failed local replay
  with a runtime query. Existing optional fixed verifier remains independent, unchanged in meaning.
  Directory timestamps ignored, complete observed symlink routes/file metadata/absence bound.
  Unknown/corrupt/unfamiliar artifacts preserved; no repair/unlink of persistent protocol inodes.
- First primary observation/review/helper/static **171 passed**, 42.31 s. Lowest Python 3.14 broad
  helper/observation/review/UI/verifier/terminal/package/static **1 failed/302 passed**, 78.98 s:
  test supervisor tried to reap an expired helper while its originating parent was still alive.
  Correct ownership: observe expiration/no replay while origin lives, have that exact origin reap
  its child and report PID/status before it exits. Busy/quiescent paths still adopt/reap after
  actual origin death. Cleanup checks unreaped child ownership before signals, never signals a
  reaped/reused PID. No product assertion/budget weakened. Subsequent primary broad focused
  **308 passed**, 75.53 s (`final-focused.xml`). Initial Ruff unused-name findings fixed before
  focused runtime gates; current Ruff all checks pass.
- Actual installed proof `up17c-proof`: **2 passed**, 118.96 s, both default/custom-space layouts,
  all prior rows/assertions retained. Adds three actual console/consent/admission/terminal/handoff
  local-replay scenarios per layout, 80x24/larger, post-main non-daemon drain still leased/no helper
  result, actual death and independent own exclusion, unchanged success, changed post-arming real
  launcher refusal, and an owned late site hook causing target Python to exit 73 while local replay
  still succeeds. Exact hook/fault restoration, child adoption/reaping, no extra network or target
  runtime/verifier execution; no installation-health or fresh-tool/source/network conclusion.
- Host tests separately use explicit synthetic local identity/actual synthetic version probes
  and real HTTP/frozen processes, not real pipx authenticity. Cover strict input/context/identity/
  prefix/version/JSON, known critical read boundaries, real exclusion requirement, private staging/
  discard preservation, actual shutdown drain and post-death replay, record/launcher/route/config
  changes, input bytes/mode/inode/symlink/hardlink/FIFO faults, another supported lease and origin-
  alive expiration. Existing frozen-source byte equality/import-whitelist gate includes the new
  stdlib module; previous rows/assertions retained, not replaced by this local proof.
- Next: freeze final inputs, run four complete compatibility suites and same full 29 affected
  real rows with added replay checks, packaging/docs/static/resource review, exact manifested
  scratch cleanup, local commit and STOP. UP-17 partial; Manager Update disabled. No actual
  replacement/expected installed result, fresh independent tool/dependency/source/network execution
  or effective installer network-policy/failure-recovery proof. No full campaign/manual/privileged/
  public-authenticity/provider/paid-API/release-readiness claim. Preserve all evidence/cache/
  persistent locks; no bump/merge/push/upload/remote change/project tag/publication.
- Owner workflow correction arrived after the four local-replay compatibility runs: continue
  autonomously through the whole approved roadmap, no per-item/commit STOP, focused development
  checks and meaningful risk-based real checkpoints; final complete regression after remaining
  implementation. Do not repeat the unchanged 29-row campaign for this minor boundary. Keep
  all assertions/CI/release gates; no release/push/tag/publication, branch migration or unrelated
  documentation/test-suite audits. Current local-replay evidence: **2076 passed/84 opt-in skips
  each**, four serial full suites **315.85/309.31/325.18/318.64 s**, clean pip checks, fixed final
  `.work/up17c/final-source-sha256.json`; installed focused proof **2 passed**, 118.96 s. These
  are current-block evidence, **not final roadmap verification**. Stage/commit this coherent
  local-replay block, then continue tool/source/network validation, replacement/expected-result
  and independent recovery, with final consolidated records/report only when complete or a
  genuine blocker/context handoff is necessary.

### Remaining-roadmap implementation — incomplete-operation startup barrier (work in progress)

- Owner's immediate workflow correction above remains controlling: no per-item STOP or repeated
  complete suites/campaigns; continue the entire approved roadmap, focused development and final
  integration verification. The local-observation block is committed as `5adfc2b`; no final
  roadmap verification or completion is claimed.
- Added stdlib `installation_state.py` (format 1) and installation coordination protocol 2:
  authoritative private operation state is in the canonical pipx home's
  `.opencode-sandbox-updates/<prefix-hash>.json`, outside the replaceable venv, independent of
  HOME/data/config overrides and durable across venv removal. Normal usage acquisition checks it
  before dispatch; pending/unknown/corrupt/unsafe state fails closed and keeps process-lifetime
  usage held. No automatic repair/reset or cache/journal inference. Only a real own-kernel
  exclusive owner may advance strict operation/source/process identities and transitions;
  completed records require a verified target/previous marker and remain retained. This is the
  substrate only, **not the yet-unimplemented updater or complete recovery verification**.
- Real minimal reproducer `.work/up17d/state-reproducer.json`: after the actual isolated writer
  exits, old `5adfc2b` lock code permits normal startup despite pending update (exit 0); current
  bootstrap refuses it (exit 2). Old source and named fixture remain manifested under `.work/up17d/`.
  Focused primary state/leases/helper/verifier/package/static **221 passed**, 19.46 s. Broader
  Python 3.14/lowest state/leases/observations/helper/verifier/terminal/CLI/package/static
  **313 passed**, 61.64 s (two known Typer warnings). No complete suite replay after owner correction.
- Meaningful changed-bootstrap real checkpoint `up17d-proof`: actual default/custom-space pipx,
  all previous test-66 assertions plus frozen independent state writer/dead-owner startup blocking,
  override resistance, no early dispatch/data creation, dedicated fixed previous-runtime query
  under exclusion and explicit completed-state ordinary-startup reopening: **2 passed**, 121.27 s.
  Private state survives test uninstall as manifested evidence; no installer or full recovery claim.
  A later constant-only FORMAT extraction is covered by the focused compatibility run, not another
  expensive real repeat. Frozen bundle/import whitelist/content requirements include the state module.
- Next implementation must finish the **full** independent external tool/dependency/source/network
  validator and effective installer policy, exact pipx replacement, expected version/source/commit/
  exposed-launcher/basic-CLI verification, private pre/during/post result/recovery records and
  interruption/failure recovery. Do not enable Manager Update before those independent gates pass.
  Then connect the approved internal consent/terminal handoff, finish UP-18 and run final broad
  verification/consolidated records/report. No release/tag/push/publication, branch migration or
  unrelated documentation/test-suite audit. Current shared/startup changes require meaningful final
  regression; the earlier full local-replay matrix is not final evidence for these newer changes.
- Continuation engineering notes (not completed gates): the current fixed runtime verifier must
  keep its three-field read-only query and ordinary startup must never gain an argument/env
  exemption. Expected installed PEP 610/pipx/source/launcher checks can be frozen filesystem logic;
  basic CLI health needs a separate fixed read-only health query or another design preserving
  unconditional normal usage leasing, not ordinary dispatch under borrowed exclusion. Existing
  pipx 1.18.7 force reuses the venv/ignores a Python switch and can unlink launchers; verify every
  outcome rather than infer backups. A helper crash can leave ordinary installer descendants:
  the durable pending-state barrier is required even when the flock disappears. Future recovery
  must prove owned child/group quiescence or retain manual-recovery state, never blindly signal
  reused PIDs or clear an interrupted record from cache/exit code. Keep pre/during/post private
  records and printed independent instructions outside the venv; no automatic rollback or
  dependency-restoration promise. Effective public-default pip/Git/credential policy still has no
  executor and needs actual subprocess/network tests. Private Git rewrites used by existing
  installed tests are declared transport fixtures, not public source authentication or authority
  to weaken policy. Final UI enablement and UP-18 remain pending, with one consolidated completion
  report only after actual roadmap completion; a necessary context handoff is not completion.

### Remaining-roadmap implementation — independent frozen execution diagnostics

- Added shared stdlib published-source graph/console-route primitives; origin and frozen readers
  use the same exact-release/ref/tag-chain/commit semantics without application imports. Separate
  frozen `manager_execution` runs fresh external Python/pipx/dependency/settings probes after actual
  origin death and own non-waiting exclusion; replay alone remains insufficient. Detected custom
  environment/configuration still refuses, never reads secrets or repairs files. Fixed public
  pip/Git settings are independently inspected by actual external shared-pip and Git processes;
  recognized pipx locations and literal source-Python selection are retained. No installer exists
  yet and no diagnostic success is durable consent, completion/recovery authority or code attestation.
- Added bounded stdlib diagnostic capture/group cleanup. The leader remains unreaped until owned
  group cleanup, and host regressions explicitly adopt/reap its actual descendant. Optional internal
  restored-terminal diagnostic fixture now freezes the new modules; no public updater is enabled.
- Primary affected regressions **416 passed**, 77.86 s before the Git-ceiling correction; final
  changed/new cases **20 passed**, 11.10 s. Python 3.14/lowest affected run **416 passed/1 failed**,
  90.04 s: an invalid new test compared unrelated pytest HTTP-thread lifetimes. Replaced that
  assertion with exact diagnostic leader/descendant reaping (not a suppressed failure); corrected
  compatibility cases **20 passed**, 13.62 s, two known Typer warnings. Complete-suite verification
  remains reserved for final integration, per the owner's workflow correction.
- Actual installed `up17e-proof` failed six assertions across both layouts (2 teardown errors):
  Git inherited the ancestor checkout's local configuration when the private helper was staged in
  `.work/`. Minimal host reproducer retained; fixed by a derived explicit Git discovery ceiling at
  the private directory's parent, with a regression proving ancestor config is excluded but a
  repository inside the helper directory still refuses. Repeated technically affected installed
  checkpoint `up17e-proof2`: **2 passed / 448 checks**, 146.88 s, default/custom-space pipx, all prior
  assertions plus actual frozen runtime/dependency/effective shared-pip/Git/fresh-source checks,
  late independent pip-policy and published-source faults, real terminal restoration and origin
  drain/death. Endpoint substitution is test-only frozen-source transport, not a product setting
  or public-authenticity proof. Neither installed checkpoint replaced an application.
- Separate real official HTTPS check observes v6.1.0 at commit
  `9ec7f7eedc634d847270d4a520b10aa61d74ed21`, annotated tag
  `064ae1b83e79b24b0939aabfc33bfef3f20039b1`, then independently rereads the same published graph
  successfully (`.work/up17e/public-source/result.json`). No mutation or signed-tag claim follows.
- Continue the remaining approved roadmap autonomously: expected-result/basic-CLI verification,
  exact pipx replacement with durable pre/during/post state, interruption/failure recovery, then
  public consent/terminal hookup and UP-18 final broad verification/consolidation. Preserve prior
  evidence, shared cache and persistent lock inodes. No version bump/merge/tag/push/publication.

### Remaining-roadmap implementation — expected files, runtime and fixed CLI health

- `68ac828` commits the independent execution-diagnostic block above. Continued directly into
  independent expected-result primitives, not another per-item STOP or complete-suite replay.
- Added frozen stdlib `manager_records` shared with the local classifier; `manager_result`
  checks exact expected source/tag/commit/distribution version, recognized pipx defaults/source
  Python, venv version/isolation, exact standard executable template, exposed launcher and the
  entire raw manager RECORD's in-prefix routes/critical inventory. It never imports target code
  and its filesystem result alone does not prove runtime health or authenticate code bytes.
- Added **separate** fixed `manager_health` query. External frozen -S bootstrap proves a live
  helper's own kernel exclusion with an unlocked witness, establishes parent-death protection,
  and closes the witness before initializing target site hooks. It constructs/renders only the
  CLI command graph using the command's own context class; never calls CLI/launcher/main/invoke,
  root/version callbacks, Docker or any caller-selected command. Ordinary entry remains refused.
  The existing three-field version/prefix/module `manager_verifier` query is unchanged.
  `manager_result.verify` brackets these two fresh processes with filesystem checks; it returns
  facts only and cannot mark an operation complete or prove an installer stopped.
- Focused verification: initial files/classifier/helper **116 passed**, 9.84 s; first broad
  expected-result run **180 passed/1 failed**, 18.17 s (new test used nonexistent package `-m`
  entry instead of the real launcher module; fixed the test command, preserved refusal assertion).
  Subsequent primary affected **234 passed**, 20.54 s. Installed `up17f-proof` then correctly
  failed both layouts: a clean current Typer installation has no standalone Click dependency,
  while the new help query had incorrectly imported it. Retained private same-fixture reproducer
  `.work/up17f/debug-manifest.json`/`debug-health.log`; same run-owned source reinstalled then
  uninstalled again, original pending state/evidence preserved. Fixed query to use the command's
  own context implementation, with a target-context regression and no new dependency.
- Final compatibility affected subset **234 passed**, 22.44 s, Python 3.14/lowest (two known Typer
  warnings). Installed `up17f-proof2`: **2 passed / 448 checks**, 146.35 s, both actual pipx layouts,
  all earlier rows plus explicit wrong-target refusal while pending, exact previous records/source/
  commit/settings/launcher, unchanged fixed runtime and separate fresh CLI-help checks before the
  explicit fixture reopening. No application replacement or full recovery workflow is claimed.
  Primary integration-focused checks **137 passed**, 28.01 s after the context fix.
- Final source review also found an unquoted-metacharacter/triple-quote gap in standard-looking
  shell console trampoline parsing. Tightened external pipx parsing before any subprocess and
  installed launcher template checks; ordinary safe/space-containing templates remain supported.
  Seven new data-only regressions refuse shell/Python quoting ambiguity without evaluating it.
  Directly affected tools/files/health/frozen-source/static primary **162 passed**, 15.93 s. The
  earlier installed positive templates are unchanged; this refusal-only tightening does not claim
  a new real malicious-path execution test. No complete unit-suite replay or full campaign yet.
  Final language/link/CLI/package-contract focused checks **63 passed**, 2.73 s; Ruff and
  `git diff --check` clean. Actual package/complete compatibility consolidation remains UP-18.
- Current read-only daemon reconciliation: original four image IDs unchanged, no containers or
  volumes (`.work/up17f/current-inventory.json`). No user installation/data/configuration changed;
  owned failed/pass artifacts, isolated state, shared cache and persistent lock inodes retained.
- Next coherent block is the **actual updater and independent recovery**. Use exact argv pipx
  replacement only after the above fresh gates and replay. Persist private immutable recovery
  inputs and authoritative prepared state before launch; a parked external child must not enter
  pipx until its exact process/group identity and installing state are durable. Never reuse the
  30-second fixture or eight-second diagnostic budgets as installation deadlines. Keep the
  installer leader unreaped until group cleanup, prove owned child/group quiescence or retain
  manual-recovery state, and never signal a reused PID. Verify target and previous results
  independently, not from pipx status; only verified completion plus quiescence can reopen normal
  startup. A frozen explicit verification/recovery path must work with a broken launcher/venv;
  previous-tag reinstall is manual guidance, not a backup, exact dependency restore or guaranteed
  offline recovery. Public consent/terminal integration remains disabled until both real success
  and failure/interruption gates pass. Finish UP-18 and one final consolidated report afterward.
  Owner's autonomous workflow correction remains controlling; no routine milestone approval,
  version bump, branch migration, unrelated audit, merge/tag/push/upload/publication is authorized.

## Resume and context-compaction handoff

1. Read repository/local instructions, TODO, BASELINE, D-056/D-057 and this entire record. Use
   ARCHITECTURE for implemented behavior, not proposed functionality. Check Git status, branch,
   log and scoped Docker state; preserve unfamiliar changes and reconcile them before editing.
2. Expected branch: `work/updates`, UP-00 `3552f67`, UP-01 `d7d6a1f`, UP-02 `4ea5050`, UP-03
   `40211ab`, UP-04 `8291e9c`, UP-05 `32861c6`, consolidation `fae56f3`, UP-06 `d7e587e`,
   PERF `6b53f46`, UP-07/UP-08 `cacffea`, UP-10 `8aa7df5`, UP-09 `1aca6ca`, UP-11 `a5843d6`,
   UP-12/UP-13 `997a7d8`, UP-14/UP-15 `f1cb9ce`, UP-16 startup/exclusion `2e6d2d0`, then the second
   UP-16 external-tool prerequisite `462d8fe`, frozen helper/lifetime `35c035a`, then the fourth
     dedicated runtime-access `14112de`, restored-terminal/refusal `6b99ccd`, then UP-17's first
     exact-source read-only `7e4865c` and second exact-origin review/consent checkpoint.
   Recover PERF's measured verification cadence from
   BASELINE; it does not reduce the shared/high-risk or real gates for the next package.
    Shared base guards, immutable explicit rollback, short diagnostic/probe bounds/ownership and
     category-owned advisory clearing, identity-bound evidence/discovery, exact targets and
      compact Updates UI, default-off independent daily GitHub/npm discovery, explicit environment
   actions/recovery, base actions/explicit refresh, read-only manager release/pipx evidence and
   early process-lifetime installation usage/internal exclusion and internal dated external-
   tool/runtime/dependency/settings prerequisite assessment and a frozen non-mutating helper/
    process-exit fixture with optional dedicated fixed fresh runtime access and internal-only
    restored-terminal handoff/refusals
   are implemented. Image assets, manager
   version and schemas still match the seed.
   Resolve actual Git state; later evidence takes precedence. Shared private lock files are
   persistent protocol state, not stale files to delete. Retained bases are unchanged. The
   packaged-definition DNS gate is resolved by UP-04 evidence, not still blocked.
3. Continue **UP-17**, independent post-origin-death/exclusive installation/tool/source/network
   validation and effective installer network policy, then actual replacement/expected-result
   verification and independently verified failure recovery. **UP-16 is DONE for non-mutating
   handoff only**, not install authority. Keep Manager Update disabled until all UP-17 gates pass.
   The first UP-17 source boundary is now independently verified: `manager_targets.resolve`
   observes the exact published full release/ref/bounded annotated-tag chain/commit from fixed
   GitHub HTTPS authority, and `revalidate` fetches that same target afresh. It is not signed-tag
   authentication, a remote lock/atomic snapshot, installation identity or consent, build/version
   proof, expected installed result or an execution grant. It has no public startup/status/
   discovery/update/helper consumer and no install payload. The internal
   origin review below is now its sole consumer. Source records contain no durable target/consent;
   only independent disposable attempts/rate claims share the GitHub source guard with discovery.
   Do not promote cache success/local classification/Target construction to authorization. Keep
   strict newer targets, complete OID chain and full bounded notes hash, canonical official URLs,
   response/whole-graph bounds and no redirects/credential forwarding. Revalidate target under
   the future executor's exclusive guard without holding a source guard across mutation. A tag
   can move after any read: installed expected-commit verification is still essential. Source
   minimal-environment diagnostics are not consent to discard installer proxy/index settings.
   The second UP-17 checkpoint now independently verifies origin review and explicit internal
   consent: `manager_review.prepare` takes an exact tag, obtains fresh own classification/tools/
   source, retains usage and binds critical records/observed full routes/context around source
   reads. `ManagerReviewScreen` displays an immutable review, Cancel default, explicit target/public-
   network acknowledgement before Confirm; returns only an in-memory exact Approval receipt.
   It has no public entry and performs no preparation/revalidation/staging/arming/install itself.
   `manager_review.revalidate` requires same origin PID/prefix/version and fresh same local/source
   binding. No release/upgrade/exclusive attempt or helper payload. The receipt is not a durable
   grant, serialization contract or executable capability. An open consent blocks the existing
   terminal gate; future consumers must retain actual-body/session/refusal boundaries rather than
   infer idle/exclusion from consent. Known custom installer/credential environment/configuration
   requires manual preservation without reading file contents, value disclosure, silent removal or
   repair. The conservative public-default policy is **reviewed, not executed/enforced** here;
   independently implement/verify effective pip/Git/network/credential behavior before enabling
   any installer. Observed tool/file/route hashes are dated change detection, not code authenticity
   or a complete lazy-file inventory. External/site code remains trusted local code. A future
   frozen independent validator must re-establish installation/tool/source/policy facts after
   actual origin death under exclusive ownership, without importing the replaced application.
   Inspect actual bootstrap/CLI/TUI/
   session ownership and lock order, new local provenance evidence, current pipx behavior/defaults
   and the frozen helper/verifier plus restored-terminal boundary before adding any updater payload.
   UP-14/UP-15 classification is **local record agreement**, not public tag-to-commit authenticity,
   updater independence or permission to mutate. In real tests its official URL was deliberately
   mapped to private fixture sources; do not mistake that for public release authentication.
   Manager Update stays unavailable until UP-17's independent success/failure recovery gates pass.
   Preserve the new canonical-prefix process-lifetime shared usage/non-waiting exclusive protocol,
   acquired before data/environment/base guards across all data/config overrides. Other supported
   live instances block exclusive access; normal startup always refuses it, with **no bypass**.
   No production early release is safe merely because Dashboard.run returns: worker/thread-pool
   draining can continue. Prove quiescence/process lifetime before future helper ownership; no
   in-process upgrade or release/reacquire shortcut. Implement only narrowly scoped fresh
   verification, not ordinary CLI dispatch under an environment/argument bypass. Preserve new
   CLOEXEC/at-fork close-without-unlock semantics, fixed secure namespace/inode checks,
   source-lock separation and existing session/mutation ownership. The strict package entry point
   is now launcher:main; current-code cli.main still leases older wrappers/module invocation.
   Old managers and arbitrary external pipx/Docker do not honor new locks; disclose that boundary.
   The helper is a frozen stdlib artifact outside the target, independently proven from the actual
   installed package with that venv absent. Its **only entry is a bounded non-mutating fixture**,
   optionally running the dedicated fixed read-only runtime query. Do not treat fixture arming/
   runtime result or PID death as terminal-restoration/consent
   evidence, and do not turn it into a generic command executor. Preserve the origin's usage
   lease to actual process exit, pidfd proof (no EOF/PID-poll fallback), narrow inherited descriptor
   set/non-inheritance, private artifact identity/ownership and exact child reaping. Its 30-second
   fixture bound is not an install deadline. The artifact/result are not recovery authority or
   discovery caches. Preserve the narrow verifier: only an independent unlocked O_RDONLY witness
   crosses exec, never an exclusive descriptor. Check the live owner pidfd, exact peer fdinfo/
   persistent inode, nonce and kernel actual responder PID; keep close-before-query and default
   CLOEXEC/fork hygiene. Do not regress to borrowed-lock export: a real early-site descendant
   disproved that design. Parent-death protection precedes target site initialization, and group
   leader identity stays reserved through cleanup/reap. This is runtime access, not UP-17 expected
   source/commit/launcher/basic-CLI or replacement success. Keep ordinary startup unconditionally
   leased; no global/argument/environment exemption. Preserve actual-body admission/sealing,
   explicit session lifetime and app-owned recovery. `cli._dashboard` requires an exact matching
   clean result, zero code, complete supported local Linux driver/input/output shutdown and original
   foreground tty/streams/device/inode/exact termios before the flushed handoff notice and helper
   start/arming; recheck after launch and cancel/reap on failed check/arm. No custom/headless/
   inline fallback, no inferred restoration from process death. Do not turn app-local admission
   into installation quiescence or release usage early. Reuse/revalidate dated external-tool facts,
   never infer a grant from supported=True or PATH. Only pipx 1.18.7/standard console/filesystem
   dist-info is inspected; unsupported variants get manual guidance, not automatic tool installs.
   Preserve the original recorded source-Python path/full symlink route, not a resolved binary
   substitute. Never use CPython 3.14's missing-file-filtered Distribution.files to prove declared
   dependency independence; retain raw bounded RECORD checks and all refusal tests. Probe source
   is a read-only diagnostic, not a general executor/helper installer; its sanitized version-only
   environment is not consent to discard installation proxy/index/network settings. Keep future
   network/source/target/recovery consent in UP-17, not the handoff fixture. No Python installation/switch, installer revival,
   shell evaluation, foreign-launcher takeover or force-as-backup assumption. Close Textual cleanly
   and restore the real terminal before any future mutation; no automatic restart. Existing
   handoff remains a non-mutating fixture until UP-17 adds independently verified consent,
   source/target/revalidation and replacement/recovery payloads. Preserve exclusion across
   processes/data dirs, active mutations/sessions/refusals, helper independence/lifetime, verifier
   access without deadlock, no leaked descriptors and real pty terminal restoration. Keep UP-17
   exact-target/source consent and execution-time revalidation, pre/during/post recovery record/
   printed commands, actual replacement and fresh-process success/failure states separate, each
   independently verified. Preserve all delivered component behavior, complete compatibility/
   affected real gates, default-off source claims/Retry-After and 80x24 progressive disclosure.
   No universal executor/Update All, schema/version/image change, release work, unrelated host/
   performance task or user install mutation. Use isolated run-owned pipx sources/launchers only;
   original four images, shared build cache and persistent lock inodes remain read-only/preserved.
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
