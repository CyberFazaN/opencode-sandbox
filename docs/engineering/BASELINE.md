# Baseline — OpenCode Sandbox 6.1.0

The current state of the project: version, supported environments, how to test, the latest
verification, known issues and what is not verified. Update it whenever one of these changes
(`AGENTS.md`, D-045).

## Version

| Item | Value |
|---|---|
| Manager version | `6.1.0` (single source: `src/opencode_sandbox/__init__.py`), Beta (D-055); 6.0.0 was the initial public version |
| Distribution | `opencode-sandbox`, installed with pipx from the GitHub repository at a version tag (D-042, D-044); MIT (`LICENSE`), owner CyberFazaN (D-036) |
| Branch | `main`; topic branches are merged with merge commits; releases are annotated tags `vX.Y.Z` (`RELEASING.md`) |
| Schemas | environment metadata 2, backup 3; other schema versions are not migrated (D-002) |

## Unpublished Updates work

D-056 approves the Updates architecture and UX effort after the published 6.1.0 release.
[TODO](../../TODO.md#active-updates-architecture-and-ux) is the entry point; the
[working roadmap](updates/ROADMAP.md) contains tasks, acceptance criteria, evidence and handoff.
UP-00 persisted the plan; UP-01 implements explicitly titled generic reports and the Agent
Context heading/capitalization and inspection-fallback correction. UP-02 preserves independent
local/registry version results, isolates failed rows and reports partial failure in both CLI and
TUI. UP-03 implements daemon-wide base build/publication guards, cleanup/creation coordination
and locked image revalidation. UP-04 adds alias-consolidated rollback inventory, explicit copy
selection and immutable consent/revalidation. UP-05 bounds short host/network diagnostics and
container probes, owns client/helper cleanup and prevents late canceled read-only UI results.
UP-06 replaces/clears category-owned daemon/resource/image advisories and readiness notices,
with explicit status ownership preserving active operations and cleanup-safe completion results.
UP-07 + UP-08 add structured identity-bound runtime/image observations and disposable source
caches, compatible stable npm discovery, explicit comparisons for Manual/Pinned, and exact target
confirmation/revalidation. Stopped environments retain dated evidence or Unknown; failed checks
never become readiness success. UP-10 replaces the Versions report with manual/cached-first
Updates views, independent explicit checks and full Details; opening runs no network discovery,
OpenCode binary or image helper. UP-09 completes the split package with optional default-off
dashboard-only daily npm discovery, persisted attempt claims, cross-caller/process source
coalescing and a quiet policy-filtered cached-availability indicator. No automatic runtime/image
probe, start, install or service; explicit checks still work with scheduling off/unavailable and
respect Retry-After. UP-11 binds explicit environment Start/Update/Policy/Rollback/Recover with
immutable consent, locked revalidation and the existing handlers/journals. Recovery Center can
also review interrupted OpenCode updates; failed restoration persists its actual successor journal
and error. Approved mutations are app-owned and not canceled by Close/Cancel check. UP-12/UP-13
add Base Images build/rollback, identity/target/definition/mode consent, cached versus explicit
pull/no-cache refresh, retained copies and bounded app-owned build feedback. UP-14/UP-15 add
read-only official manager release discovery/local pipx provenance classification and independent
default-off daily GitHub metadata work. UP-16's first verified checkpoint adds early process-lifetime
installation usage/internal exclusion and a stdlib-only console bootstrap. Manager Update stays
disabled; UP-16 is partial, with helper/external-tool validation, narrow fresh-verifier access and
terminal handoff still pending before UP-17 replacement/recovery.
No image-definition, metadata/backup schema or manager-version change was made.

UP-01..UP-15 and the first UP-16 checkpoint's verification is below; commands, failures and
handoff are in the roadmap.
Release evidence remains historical evidence for 6.1.0, not verification of pending Updates work.
No release preparation or publication is authorized by this effort.
D-057 consolidates the remaining work into related packages with technical-only dependencies;
it changes workflow, not delivered product behavior or the independent recovery verification gates.

## Supported environments

- Host: Linux with the prerequisites of D-046; real evidence on Arch Linux only (kernel 7.2.11
  at the 6.1.0 release; hosted CI adds the fake-Docker unit suite and a pipx installation on
  Ubuntu 26.04). Python >= 3.11 (tested
  3.11.18 and 3.14.8; 3.12/3.13 accepted, not tested separately; the 6.1.0 hosted CI used 3.11.17
  and 3.14.9);
  Git (tested 2.56.0); the user's own rootless Docker daemon (tested 29.9.2,
  rootlesskit, slirp4netns, overlayfs, containerd image store; cgroup v2 with `cpu memory pids`
  delegated by systemd 262).
  Rootful, other users' and remote daemons and socket proxies are refused by design.
- Python dependencies: Typer (tested 0.27.3), Textual (tested 8.2.8). Installation: pipx (tested
  1.18.7). Tests: pytest; real terminal tests: pyte 0.8.2; quality gates: ruff 0.17.3, shellcheck
  0.11.0 (`shellcheck-py`).
- Sandbox definitions: Debian 13 (`node:24-trixie`, default, revision 2) and Arch Linux (`archlinux:base-devel`,
  AUR via `ocs-aur`/paru), each with OpenCode `@opencode/cli` 2.x (tested 2.1.4 and 2.2.0).

## Commands

```sh
# development venv and unit/host/Textual-pilot tests (fake Docker; no daemon contacted)
python -m venv .venv && .venv/bin/pip install -e '.[test]'
.venv/bin/pip install ruff shellcheck-py pyte   # optional: quality gates and real-terminal tests
.venv/bin/python -m pytest -q                   # includes ruff and shellcheck (skipped if missing)
.venv/bin/python tests/dashboard_screenshot.py  # regenerate docs/images/dashboard.svg (fake data)

# package (sdist + wheel) and metadata check; packaging validation only, nothing is uploaded (D-042)
.venv/bin/pip install build twine
.venv/bin/python -m build --outdir dist . && .venv/bin/twine check --strict dist/*

# real campaign: real rootless Docker, OpenCode, terminals, fault injection (about 10 minutes);
# only on a disposable machine; needs both base images, network and pyte
OCS_TEST_DOCKER=1 .venv/bin/python -m pytest -rA tests/integration
# plus the rows that use sudo -n and restart/SIGKILL the user's daemon (read the docstring first)
OCS_TEST_DOCKER=1 OCS_TEST_PRIVILEGED=1 .venv/bin/python -m pytest -rA tests/integration
# the pipx rows (test_65) need pipx in the venv; OCS_TEST_PIPX_BUILD=1 adds an image build
# from the installed package (downloads the base image); OCS_TEST_MANAGER=<launcher> runs the
# campaign against an installed manager, e.g. a pipx installation of a local test tag
.venv/bin/pip install pipx
```

The campaign works in `.work/<run-id>/` with `ocs-test-*` names, writes
`.work/logs/<run-id>.log` (every command and PASS/FAIL check) and a manifest, and ends with the
product's cleanup behind a guard and a leak check. `OCS_TEST_DISTROS` selects distributions;
`test_30`/`test_40` expect OpenCode 2.2.0 in the base images; `test_10`/`test_80` use the local
image `ubuntu:24.04` for the custom-image rows. Variables: `CONTRIBUTING.md`.

Run the unit suites serially, in the foreground, with a short `--basetemp` outside the
checkout (for example under `/tmp/opencode/`, created by and owned by that run): a temp
directory under `.work/` is a hidden path inside a Git repository, which the direct-workspace
and import guards rightly refuse, and deep paths exceed the 108-byte Unix socket limit. Use an
absolute `PYTHONPATH` so test subprocesses import the checkout. The retained-OS row, the
test-only image namespace for new base images and the socket-activation opt-in are described
in `RELEASING.md` ("Verify").

## Test performance and local verification

One-time investigation after UP-06, before UP-07/UP-08 (2026-10-30). No application, CI,
dependency or release-gate changes. Commands/evidence:
[working checkpoint](updates/ROADMAP.md#perf--2026-10-30--test-performance-investigation).

### Measurements and findings

Arch Linux VM, kernel 7.2.11, four available CPUs; existing editable venvs, no installation or
environment rebuild. Primary timing: Python 3.11.18, pytest 9.2.0, Typer 0.27.3, Textual 8.2.8,
Ruff 0.17.3, shellcheck 0.11.0, pyte 0.8.2. Serial foreground runs used fresh short basetemps,
absolute PYTHONPATH and JUnit phase timings. External wall time includes startup/finalization,
not agent reasoning or tool transport.

| Measurement | Before | After test-only changes |
|---|---|---|
| Complete default suite, external wall, two runs | 108.08 / 107.26 s | 99.36 / 98.95 s |
| Pytest session time, same runs | 107.18 / 106.37 s | 98.48 / 98.10 s |
| Results, every full run | 1201 passed, 62 opt-in skips | Identical 1263 ordered test IDs/outcomes |
| CLI-structure module, two standalone runs | 4.56 / 4.63 s | 0.60 / 0.62 s; same 8 tests |
| OpenCode-version module, two standalone runs | 5.46 / 5.46 s | 2.05 / 2.04 s; same 40 tests |
| Collection only | 0.50 / 0.59 s wall; pytest collection 0.29 / 0.32 s | Not a bottleneck |
| Instrumented baseline phases | Setup 1.59 s, call 99.76 s, teardown 4.78 s | Diagnostic, not an optimized benchmark |

The default "unit suite" mixes mocked Docker with real host files/Git, HTTP/UNIX sockets,
processes, host-terminal fixtures and Textual pilots. The 62 opt-in skips prove no real-Docker
behavior. Largest baseline modules, phase totals across two runs: `test_tui.py` 36.11–36.49 s,
`test_readiness.py` 8.54–8.61 s, `test_version_inventory.py` 8.37–8.47 s,
`test_opencode_versions.py` 5.27 s, `test_advisory_tui.py` 5.09–5.24 s and
`test_cli_structure.py` 4.55–4.77 s. Slowest individual tests: document-command validation
3.74–3.92 s, external-CLI dashboard refresh 3.15–3.27 s, create-form choices 2.79–2.90 s,
dialog Escape 2.42–2.54 s and direct-workspace consent 2.09–2.13 s.

Priorities, benefits and risks:

1. **Implemented, low risk:** fresh command graph per CLI-structure test, passed to read-only
   helpers: 1328 helper constructions become seven; all help invocations remain. All 708 ordered
   command/option queries and results match before/after. No cross-test cache/shared mutable state.
2. **Implemented, low risk:** function-scoped HTTP fixture shutdown polling 0.01 s instead of
   0.5 s, plus explicit thread join/socket close. Seven teardowns fall from 0.45–0.50 s to
   0.004–0.007 s. The real HTTP/error/body checks, 0.3 s client deadline and 1.5 s delayed response
   are unchanged; the timeout case still takes 1.22 s in teardown. No real verification became a mock.
3. **Workflow, greatest potential benefit:** avoid replaying identical full checks after each
   subtask/prose edit; use the cadence below. UP-06's four full combinations consumed 420.82 s
   of recorded pytest time, plus focused/document repeats. Different dependency combinations are
   distinct evidence, not duplicates, but need not be four feedback loops per small edit.
4. **Deferred:** the 50-test TUI module makes 39 `settle` calls: 12.7 s explicit delay, 14.86 s
   including pilot pauses. Replace only individually proven unnecessary waits with bounded
   worker/condition completion. Timers/unchanged-state intervals/negative observations must remain.
   Prerequisite pilots also wait 20 iterations unconditionally (about two seconds explicit delay
   across two cases). Needs repeated current/lowest-Textual and loaded-host evidence; no guaranteed
   saving. No global sleep reduction, parallel runner or larger infrastructure rewrite now.

Mean full wall time improved **107.67 -> 99.16 s (7.9%)**; changed modules explain about 7.4 s
standalone saving, with normal variation in the remainder. A roughly 100-second mixed-layer
suite for 1201 tests is already practical. Global isolation/safety fixture setup totals about
0.11 s across 1201 tests; `tmp_path` setup 0.11 s; largest Git fixture setup total 0.57 s. Keep
function isolation. The instrumented parent launched 2044 Git clients (about 2.35 s launch/blocking
time); real Git/filesystem tests are not the main bottleneck. Retain the real 1 GiB archive-size
safety fixture (about 1.1 s), durability checks, signal/lock deadlines and race repetitions.

Prepared-tool costs are small: Ruff/shellcheck child execution about 0.02/0.03 s inside the suite;
no-isolation sdist+wheel 0.68 s, strict twine 0.15 s, content check 0.05 s, workflow lints below
0.10 s each (single-run indications). Repeated post-change language/link/CLI runs take 1.84–1.90 s
wall for 27 tests. Existing-venv `pip check`: 0.21 s; Python startup: 0.007 s. Cold downloads/
installations, hosted CI provisioning, real campaign runtime and agent/tool latency were not
benchmarked; do not charge them to test execution. Async task/sleep durations overlap and must
not be added as wall time. Diagnostic instrumentation is separate from baseline comparisons.

### Recommended development-time cadence

This applies the existing risk-appropriate verification contract, not a substitute for full
regression. CI and [release verification](RELEASING.md#2-verify) stay unchanged.

| Point / change | Verification and reporting |
|---|---|
| Fast feedback | Reproducer/new test, then its whole module and direct consumers. Name selected paths/IDs; never describe a focused or last-failed run as the complete suite |
| Completed code package | At least one complete default suite on final code plus focused regressions; review changes since that run. Related subtask commits need not replay identical full runs mechanically |
| Prose/evidence-only follow-up | Language/links/CLI checks; quality checks for changed code/scripts. Cite prior full code verification and label the new run focused; no unchanged UI/process or package replay solely for prose |
| UI presentation / test-local helper | Affected pilots/helpers/CLI consumers at 80x24/larger and relevant current/lowest Textual/Typer endpoints; complete primary suite at code-package completion. Common workers/fixtures/action routing need broader verification |
| Shared/high-risk code or infrastructure | Complete Python 3.11/3.14 × current/lowest suites at integration checkpoints, not just endpoint samples; adversarial/concurrency/fault/recovery tests and affected real scenarios separately |
| Before release | Full final regression/compatibility matrix, package/installed-pipx checks and real campaign/P0/P1 evidence or accepted blockers under RELEASING/CAMPAIGN; no focused/mock/historical substitute |

Broader gates must cover security/ownership/daemon identity and diagnostics, lock ordering/
concurrency, host filesystem/Git safety, profiles/credentials, backup/archive/restore, cleanup,
lifecycle/journals, rollback and recovery. Observation/version changes affecting identity, pins or
update eligibility, including UP-07/UP-08, belong here. Run affected disposable real-Docker/
OpenCode paths on both distributions, and pipx/terminal handoff/fault paths for installation
changes, under existing permissions/manifests/cleanup rules. Full default-suite PASS is not real
integration evidence. Preserve negative cases, real processes/files and both-distribution evidence.

Representative test families (paths under `tests/`; not an exhaustive automatic selector):

| Category | Existing coverage to retain together when affected |
|---|---|
| Identity, security, diagnostics | `test_runtime_identity.py`, `test_docker_readiness.py`, `test_diagnostics.py`, `test_hardening.py`, profile safety/mount tests; real sockets/processes are not live-daemon proof |
| Concurrency, lifecycle, rollback/recovery | Base lock/coordination/rollback, lifecycle, config-plan, journals, recreate faults/consistency, transactions, recovery, OpenCode lifecycle and session-signal/hangup tests |
| Filesystem/Git/data boundaries | Direct/unreadable/untrusted workspace, Git boundary/roundtrip/review, archive/home-archive paths, backup hardening/completeness, staged restore/resume/settings and cleanup tests |
| CLI and UI consumers | CLI structure/robustness, TUI/text/advisory/diagnostic pilots, readiness, version inventory, Agent Context and affected management screens |
| Static/package/contracts | Quality, language, user docs, package metadata, installation, release scripts and Python/CI structure tests; these do not replace runtime or installed-package checks |
| Real opt-in integration | `integration/`: identity/prerequisites, both-distribution lifecycle/security/direct access, faults, OpenCode, base races/probes, TUI terminals, pipx, privileged and combination rows; permissions and manifests still apply |

Reuse unchanged editable venvs after version/`pip check` verification, not container/fixture state.
Record source checkpoint, commands, selected scope, dependencies, counts, skips, failures/reruns
and unexecuted layers. Ruff/shellcheck/docs checks already passed in a full run need not be
replayed on identical inputs; changed inputs must be checked again. Package/workflow checks
remain required for affected inputs and final checkpoints. No automatic broad deselection,
xdist or session-scoped mutable fixtures: global watchdog counts, signals and filesystem/kernel
races require isolation. Review any future parallelism/caching proposal separately.

## Verification

### Unpublished UP-16 first safety checkpoint — 2026-10-31

| Layer | Result |
|---|---|
| Complete unit/host/pilot suites | **1655 passed, 84 opt-in skips in each of four serial foreground runs**, Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0; clean pip checks. 231.41/219.66/222.74/218.99 s; all **1739 ordered IDs/outcomes identical**. Only two known lowest-Typer deprecations |
| New default regressions | **44 new cases**: 41 real host/process installation-lock cases, one bootstrap-template classifier case and two missing-bootstrap package-content gates. Cross-data/config/HOME/XDG/TMPDIR convergence, prefix aliases/separate environments, concurrent shared readers, exclusive/startup refusal including help/version, exclusion before dependency import/data creation, process-lifetime worker-drain protection, threaded idempotence, reverse lock order, unsafe parent/owner/modes/symlink/hardlink/FIFO/inode replacement refusal, persistent modes/inodes, process death and fork-only/exec descriptor ownership. Existing classifier/command/package assertions retained |
| Affected real Docker/OpenCode/pipx/terminal | **29 tests/702 logged checks passed**, no skips/deselections, `up16a-final`, 1047.39 s. All prior 26 affected rows plus real pipx lifecycle and two real shell/exec rows. Actual default/custom-space pipx bootstrap launchers refuse exclusive startup across data/config overrides without creating those paths. Live installed dashboards permit other shared CLI readers but block exclusive access; normal exit releases it. Both distributions' attached shell and long real Docker exec hold leases. Approved real base mutations block exclusive access. Prior base races, rollback/retained layers, diagnostics, version evidence, discovery, environment update/recovery and terminal restoration assertions rerun |
| Scope and limits | **UP-16 is partial**, split at the independently verified startup safety boundary under D-057. No independent helper/external interpreter/pipx validation, narrow fresh-verifier capability, terminal handoff, manager replacement or recovery is implemented or claimed. Manager Update remains disabled. Locks do not coordinate older manager code, direct library calls, arbitrary external pipx/Docker or orphaned daemon work after manager death. No automatic release of the lease at main/dashboard return, generic bypass, shared-to-exclusive upgrade, installer, restart, schema/image/version change or host setup |

The console target changes to the minimal stdlib `launcher:main`; current-code `cli.main()` still
acquires/reenters the lease for old generated wrappers and module invocation. Strict distribution
validation now requires that exact bootstrap target and both bootstrap modules, retaining existing
metadata/assets/license/tests/legacy-installer gates; no CI/release workflow or dependency bound
changed. Small core context-local lock observations enforce installation-before-data/base ordering
without changing mutation behavior or timeouts. Provenance inspection recognizes old and new
standard templates but does not imply older installed code participates in the protocol.

Failure trail retained: missing-lock-module reproducer failed collection. First selected **77
passed**, 1.40 s; expanded **1 lint failure/130 passed**, 3.67 s, then lowest affected **1 lint
failure/177 passed**, 12.28 s (two known deprecations). Corrected test-only fork exit handling and
import/string style, no assertion/lint-gate waiver. Static follow-up **89 passed**, 2.22 s; final
extended host/package/docs/quality subset **140 passed**, 4.13 s. The first real proof **3 failed/2
passed/1 teardown error**, 53.53 s (**91 passed/1 failed checks**): the old pipx fixture imported an
already-existing release tag and tried to recreate it, and the new session test omitted real-Docker
markers, so its direct release call hit the unit Docker guard. The unfinished test exec correctly
blocked another exclusive attempt until campaign cleanup. The second proof **1 failed/4 passed**,
83.90 s (**112 passed checks**) caught the same missing marker in the old pipx row after reaching
uninstall. Fixed only fixtures/markers; no product check weakened or failure deselected. The pipx
fixture now uses a private no-tags clone and a committed current-package overlay, testing reviewed
code rather than stale HEAD, without changing published/source tags. Final 29-test gate passes all
those rows, including full pipx upgrade/downgrade/uninstall/data-retention/foreign-launcher checks.

Final XML/logs and frozen five product modules plus packaging configuration/checker hashes are
under `.work/up16a/`; manifests/command/check logs are `.work/logs/up16a-*`. All attempts use isolated
run-owned resources, private installations, guarded product cleanup/uninstall and leak checks.
Ending verified own-rootless inventory has no containers/volumes/test tags and the original four
image IDs unchanged. Persistent lock files and shared build cache remain intact. Existing test_66's
declared local Git URL rewrite proves real provenance/launcher shapes, not public-release commit
authenticity; no new public API, token or paid-provider use. No complete campaign, optional installed-
asset image build, broad legacy TUI, privileged/socket/service, human observation, helper/handoff or
manager-replacement evidence is claimed. No version bump, merge, push, tag, publication or upload.

Final package checks pass: sdist/wheel build, strict twine/content validation, exact bootstrap
entry point and frozen-source/wheel equality for all five changed/new product modules; private
instructions and evidence are absent from the sdist. Document/CLI/quality subset **43 passed**,
3.18 s (`docs-final.xml`), not another complete suite. No remaining manager/guard/watchdog Python
process found. Removed only **13 exact manifested completed pytest roots** behind own-UID/inode/
process/socket/mount guards. `/tmp/opencode` empty, **1048529 free inodes**; intentional additional
fixed-namespace installation lock files are preserved as protocol state, not leaks to delete.
Logs/XML/private fixtures/package artifacts/build cache/prior evidence stay intact. A final
prose-only check's manifested scratch follows the same guard after its run.

### Unpublished UP-14 + UP-15 — 2026-10-31

| Layer | Result |
|---|---|
| Complete unit/host/pilot suites | **1611 passed, 82 opt-in skips in each of four serial foreground runs**, Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0. Clean pip checks; only two known lowest-Typer deprecations. 225.64/219.72/220.54/216.29 s; all **1693 ordered IDs/outcomes identical** |
| New independent regressions | **86 new default cases**: 43 release provider/coordination, 33 local provenance/settings and 10 CLI/pilot cases. Real bounded loopback HTTP, strict published-release/tag/URL/version filters, no downgrade, plain notes, unauthenticated headers/redirect refusal/size/deadline, independent caches, Retry-After/rate-reset, claims/restart/clock/coalescing/cancellation/unsafe storage. Actual private file/symlink/FIFO/permissions and synthetic runtime identity prove conservative source/interpreter/options/launcher refusal without leaking dummy secrets. Pilots prove independent source failures, network-free opening, daily quiet counts/restart, shared requests, canceled-child reaping, compact controls/Details and permanently disabled manager Update. Two new opt-in installed-pipx layouts |
| Affected real Docker/OpenCode/pipx/terminal | **26 tests/637 logged checks passed**, no skips/deselections, `up1415-final`, 981.42 s. All 24 prior affected base-race/diagnostic/lifecycle/restore/discovery/environment-recovery/base-mode terminal rows rerun. New isolated real pipx installs from tagged run-owned sources reconcile actual PEP 610/pipx/Python/launcher records at default paths and custom paths with spaces. Unknown options/pins/suffixes, foreign/PATH-shadowed launchers, actual foreign VCS and editable sources refuse without takeover. Real installed-manager terminals at 80x24/120x40 independently check loopback releases, preserve cached/local evidence after GitHub failure, keep Update unavailable and restore the terminal |
| Public read-only source smoke | One isolated unauthenticated official GitHub GET discovered **v6.1.0**, published 2026-10-30. The unchanged running checkout version is not a new release; development/ambiguous distribution metadata receives manual review. No GitHub login/token or installation/replacement used |
| Boundaries | pipx source tests explicitly map the official URL spelling to a local tagged fixture using a private Git config; they prove real record/launcher behavior, **not authenticity of a public release commit**. Only current pipx 1.18.7 was executed; wire formats 0.5/0.6/0.12 are recognized/tested as local evidence. Local provenance agreement never grants execution; authenticated source-commit resolution, external updater/helper independence, cross-instance exclusion, handoff, actual replacement and recovery remain unimplemented. No complete campaign/legacy broad TUI workflow, paid-provider, privileged/socket/service or manual-observation claim; CI/release gates, manager version/schemas/image assets remain unchanged |

Failure trail: the missing-provider reproducer failed collection. First selected run **3 failed/92
passed** (33.52 s): two invalid-type test fixtures concatenated non-string tags, and CLI structure
needed the new read-only group. Corrected fixtures and added the group without changing the
top-level count cap or existing command assertions. Focused **1 lint failure/116 passed** (38.42 s)
and combined **1 lint failure/135 passed** (50.34 s); import/template style fixes, no gate change.
Lowest affected **145 passed** (49.66 s), then extended lowest/docs subset **165 passed** (51.22 s).
An early full primary suite **1601 passed/82 skips** (224.02 s) predates ten added final regressions,
not the final checkpoint above. Documentation **1 failed/42 passed** (3.12 s) caught an overlong
command comment; shortened it, preserving the 80-column gate.

Real proof attempts were retained and cleaned: first failed before installing because the harness
omitted a required argument; next two each failed with a recorded refusal/teardown error, exposing
the current default environment-name field and non-exposed dependency-executable inventory. Both
are now recognized as actual default evidence rather than misclassified custom settings; custom
exposure/options remain refused. Next **1 passed/10 checks** (15.47 s). Expanded terminals **1
passed/1 failed/1 teardown error** (34.17 s; 27 passed/1 failed checks) caught pip's double-quoted
space-path trampoline, not the assumed single-quoted form. Recognized the actual standard template
as data, without executing shell text; default/custom layouts plus previous Updates/daily terminals
then **10 passed/182 checks** (103.45 s). Final expanded 26-test gate above includes real foreign/
editable installs and all source fixes; no failed check was waived or deselected.

Final XML/logs/hashes: `.work/up1415/final-*.xml`, `real-final.xml`, `final-source-sha256.json`;
campaign manifests/logs `.work/logs/up1415-*`. Eight changed/new product modules were frozen before
the final complete/real gates. Each real attempt used isolated roots, manifests, run-owned pipx
installs and guarded product cleanup/uninstall. Ending verified own-rootless inventory has no
containers/volumes/helpers, no test tags and the unchanged four original image IDs. Shared build
cache and persistent locks remain intact. No user launcher, installation, credential or Python
was changed; no version bump, schema/image revision, upload, merge, push, tag or release.

Final sdist/wheel, strict twine/content checks and byte equality for all eight changed/new
product modules pass. Final document/CLI/quality subset **43 passed**, 3.10 s (`docs-verified.xml`),
not another complete suite. Its preceding **1 failed/42 passed**, 3.27 s, caught public-record
prose resembling a retired internal path; reworded prose without changing the gate. After
retaining logs/XML/installed-source evidence/package artifacts, removed only **20 exact
manifested completed pytest roots**, with no live process/socket/mount references. `/tmp/opencode`
is empty again with **1048541 free inodes**; persistent protocol locks and prior evidence are
untouched. A final prose-only check's manifested scratch follows the same guard before removal.

### Unpublished UP-12 + UP-13 — 2026-10-31

| Layer | Result |
|---|---|
| Complete unit/host/pilot suites | **1525 passed, 80 opt-in skips in each of four serial foreground runs**, Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0. Clean pip checks; only two known lowest-Typer deprecations. 213.93/206.99/209.79/206.44 s; all **1605 ordered IDs/outcomes identical** |
| New/retained regressions | **54 new default cases**: 38 base backend/CLI, 12 pilots, three actual host-output clients and one module quality parameter; two new opt-in both-distribution cases. Pre/post-build changed image/absence/ownership, endpoint/namespace, target/mode/retention, definition/assets, no moving-latest substitution, immutable candidate verification/retagged cleanup refusal, same-content no-op and failed-candidate safety. Exact CLI/TUI consent, no-copy CLI disclosure, explicit multi-copy selection, cancellation/Close/Quit and late-plan ownership, bounded output/retained notifications, and active operation priority over a saved result. Old assertions retained; two old mocks extended for actual preflight/immutable candidate return |
| Scoped real Docker/OpenCode/terminal | **24 tests/581 logged checks passed**, no skips/deselections, `up1213-reviewed`, 928.47 s. `test_42` packaged and retained fixtures on both distributions proves cross-directory/context races involving build, rollback, cleanup, publication and pinned creation. Existing diagnostics/lifecycle/restore/discovery/environment-recovery terminals rerun. New `test_54` separately proves repeated cached reuse/verified unchanged and full-refresh pull/no-cache package-layer execution, immutable publication and retained copies, real candidate verification followed by injected refusal, pinned future creation and unchanged running containers/metadata/layers. Base mode consent/cancel, output Details, Close/Quit ownership, exact single/multi-copy rollback and terminal restoration at 80x24/120x40 |
| Boundaries | New full-refresh evidence uses packaged Debian 13/revision 2 and Arch/revision 1 assets under isolated namespaces; only copied upstream FROM hostnames use an explicit official Docker Hub registry alias to avoid moving the retained original upstream tag. OS/tools/binary checks are unchanged, and downloaded aliases are removed. Real environment evidence still uses retained Debian 12/revision 1 and Arch/revision 1. No full campaign/legacy broad TUI workflow, installed-manager/pipx, paid-provider, privileged/socket/service or manual-observation evidence; no release-readiness claim. Image assets/revisions, versions/schemas, identity/base-lock/probe executors and CI/release gates unchanged |

Failure trail/evidence: the initial missing-plan reproducer failed. First selected run **1 lint
failure/163 passed**; new focused **3 failed/230 passed** caught an early output publication gap,
a deprecated Select blank sentinel differing across supported versions and a queued-button test
race. Fixed the stream's first output publication and explicit selection validation, synchronized the test;
**63 passed**, then lowest affected **186 passed**. First full suite **1 failed/1518 passed/78
skips**: an old CLI mock omitted the new inspection/plan arguments; extended it while retaining
the exact-target assertion. Documentation initially **1 failed/42 passed** on an overlong example;
wrapped it without changing the gate. First real Debian run failed in the harness: its short
exit-wait helper deliberately kills a still-running process; replaced with non-destructive
`waitid(WNOWAIT)`, then **2 distro tests/86 checks passed**. Initial complete matrix **1524 passed/
80 skips each** and real **23 passed/1 failed**: a real Arch content-equivalent cached rebuild
correctly left the initial image current, not a rollback copy. Corrected only the test's explicit
alternate-copy choice, preserving exact-ID and swap assertions; real **24 passed/581 checks**.
Final UI review reproduced a prior base result hiding another active operation (**1 failed**);
active work now takes priority, lowest UI/ownership subset **97 passed**, then final complete/real
gates above rerun on the final seven-module source hashes. No failed test was waived or deselected.

Logs/XML/manifests: `.work/up1213/`, `.work/logs/up1213-*`; final complete XMLs `reviewed-*.xml`,
real `real-reviewed.xml`, hashes `reviewed-source-sha256.json`. Each real attempt uses isolated
product roots, run-owned names/labels/manifests, guarded product cleanup and leak checks. Ending
verified own-rootless inventory: no containers/volumes/helpers and exactly four original tagged
images with unchanged full IDs. Shared build cache remains intact, not pruned. No manager-version,
metadata/backup schema, distribution revision or production image-asset change; no upload/install,
merge, push, tag or release. Next is read-only manager discovery/classification, not execution.

Final sdist/wheel, strict twine/content validation and byte equality for all seven changed/new
product modules pass. Final document/CLI/quality subset **43 passed**, 3.23 s, not another complete
suite. Its earlier **1 failed/42 passed** caught public-record prose resembling a retired internal
path; reworded the prose without changing the gate. After retaining logs/XML/package artifacts,
removed only **25 exact manifested completed pytest roots** with no live process/socket/mount
references. `/tmp/opencode` is empty again with **1048541 free inodes**; persistent protocol locks
and all prior evidence are untouched. Cleanup result is ignored under `.work/up1213/`.

### Unpublished UP-11 — 2026-10-31

| Layer | Result |
|---|---|
| Complete unit/host/pilot suites | **1471 passed, 78 opt-in skips in each of four serial foreground runs**: Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0. Clean pip checks, only the two known lowest-Typer deprecations; 194.60/189.41/191.32/187.48 s. All **1549 ordered IDs/outcomes identical** |
| New/retained regressions | **64 new default-suite cases** (38 backend, 25 pilots, one quality-module parameter), six new opt-in terminal rows. Exact checkpoint/container/daemon/data/policy/metadata consent races, live eligibility/ownership refusals, locked start/policy/configuration-recovery preconditions, missing-checkpoint salvage, persistent successor-journal errors, full-layer preservation, explicit Start remains running, cancellation/Close/normal-Quit semantics, late-plan rejection, policy/pin consent, current metadata before Details, current/lowest UI, production toast ownership and scrollable Recovery errors with unclipped controls. Existing assertions retained; UP-10's three unavailable-action expectations now assert review without mutation/confirmation instead. Existing volume/config fakes extended to answer new preflights, not to bypass checks |
| Scoped real Docker/OpenCode/terminal | **18 tests/400 logged checks passed**, no skips/deselections, `up11-verified`, 489.49 s. Both retained distributions: existing bounded diagnostics, binary/lifecycle/restore evidence, manual Updates and daily discovery terminals; new 80x24/120x40 explicit Start, pin/refused target/Manual consent, actual 2.2.0 -> 2.1.4 update/final stopped state, whole-layer rollback and a retained snapshot that really contains later system changes/the updated binary. Independent recovery rows cover actual SIGKILL, missing checkpoint refusal without mutation, failed owned removal, persisted `runtime-recreate`/reason, existing config recovery, direct Recovery Center update-recover success, restored actual binary/configuration/data and terminal restoration |
| Failure trail | Initial absent checkpoint-plan reproducer failed. First broader full run **3 failed/1455 passed/72 skips**: two old fakes lacked volume inspection and Recovery controls clipped at 80x24. Focused **184 passed** after correction. Initial terminal sequence batched editing keys and did not supply its intended exact target; harness now separates controls and stops immediately on missing consent. Real runs also exposed advisory overlays on forms/Details and delayed inventory supplying an old journal to Details; fixed in product, not hidden by test changes. Retained intermediate failures/proofs are detailed in the roadmap. Lowest focused run **1 failed/141 passed** caught subscreen/late table events reaching the hidden dashboard during teardown; narrowed event ownership, added regression, **143 passed** on rerun before final full matrix |
| Boundaries | Environment actions/recovery only; no universal engine/Update All, automatic start/install, temporary start/probe/stop, network/policy auto-change, new schema or base/manager executor. Full image IDs are valid existing image-reference strings; original checkpoint names remain retained in update records. No new full campaign/legacy broad TUI workflow, fresh base build, installed-manager/pipx, privileged/socket/service, paid-provider or manual-observation evidence. CI/release gates unchanged; not a release-readiness claim |

Before work, the owner requested old temporary-test cleanup. Inspected/manifested **159 completed
pytest roots** from earlier Updates/performance cycles: own UID, only fixture trees, no live
process references, active UNIX sockets or nested mounts. Removed only those exact roots without
following symlinks: **929919 inodes** and about **1.48 GiB allocated space** freed. `/tmp` inode
use fell from 89% to 35 used/1048541 free. All other `/tmp` entries, persistent Sandbox locks,
retained `.work` logs/XML/artifacts, user data and Docker objects stayed untouched. Ignored
manifest/result: `.work/up11/tmp-cleanup-*.json`; no recurring system cleanup was installed.

Final evidence lives under `.work/up11/` and `.work/logs/up11-*`. All real attempts used isolated
roots/manifests and guarded product cleanup, including failed runs. Ending verified own-rootless
inventory: no containers/volumes/helpers and unchanged four original full tagged-image IDs.
Seven changed/new product modules are hash-frozen after the final matrix/real gate. Image assets,
versions/schemas, identity proof, base guards, diagnostic/HTTP/probe executors, scheduler/cache/
preferences, worker adapter, dependencies, AGENTS and CI/release gates are unchanged from the
UP-09 checkpoint.

Final review after an initial four-way **1469 passed/78 skips** matrix and **18 passed/400 checks**
real gate found older Recovery paths relying on now-collapsed toasts. Their messages now persist
in a bounded read-only scrollable result pane, including long errors and unsupported-journal next
steps; controls stay visible. Added two pilot cases and reran the final complete/real gates above.
First rerun **1 failed/1470 passed/78 skips**: an existing text test searched only Static widgets;
extended it to include the new TextArea, preserving the terminal-guidance assertion and adding
read-only verification. A final documentation subset initially **1 failed/41 passed** because of
a commit ID in a public record; removed that reference without changing the contract test.
Final sdist/wheel, strict twine/content validation and byte equality for all seven product modules
pass, without installation/upload. Final document/CLI/quality subset **42 passed**, 3.08 s,
not another complete suite; final-code hashes `.work/up11/final-source-sha256.json`. After evidence
preservation, removed only this cycle's **32 exact manifested completed pytest roots**; `/tmp`
again has **1048541 free inodes**. No old evidence or persistent protocol locks were discarded.

### Unpublished UP-09 — 2026-10-31

| Layer | Result |
|---|---|
| Complete unit/host/pilot suites | **1407 passed, 72 opt-in skips in each of four serial foreground runs**: Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0. Clean pip checks; only the two known lowest-Typer deprecations. Times 166.42/160.50/164.65/159.91 s; all **1479 ordered IDs/outcomes identical** |
| New regressions | **42 new default-suite cases**, no removed/weakened prior assertions: real private files/locks and loopback HTTP; attempt persisted before request, successful/failed/interrupted restart, actual process death before HTTP, thread/process overlap and shared failures, bounded/canceled waits, cached-only contention still requires a fresh explicit request, canceled HTTP child reaped, forward/backward clock changes, numeric/date/long Retry-After, unsafe/unwritable/fsync-failed storage, explicit fallback, exact-target guard release, old/invalid preferences, 80x24/larger Save/Cancel/enable/disable, Notify/Manual/Pinned/Unknown/recovery filtering, quiet deduplication/status ownership, open-screen cache adoption and no unsolicited short-CLI network work |
| Real Docker/OpenCode/terminal | **12 tests/200 logged checks passed**, no skips/deselections, `up09-verified`, 178.60 s. Retained both-distribution diagnostics and actual binary/lifecycle recovery rows plus existing Updates terminals; new daily-discovery terminal workflow at 80x24/120x40 exercises real keyboard Preferences, loopback HTTP, new dashboard processes after success/failure, cached comparisons and opt-out. Docker argv recording proves no runtime/image probes or mutations in these discovery rows; actual stopped state/start time/metadata unchanged, all normal quits restore terminals |
| Failure trail | Two initial automatic-daily tests failed before implementation. Focused iterations exposed import/lint errors and an aliased cached-snapshot regression (fixed, not weakened); reviewed subset **158 passed**, 48.39 s. Lowest focused run **1 failed/156 passed**: new test variable/prose used an existing forbidden internal-reference word; renamed without touching the gate. First new real terminal run: **1 teardown error, 3 failed/13 passed checks** because unescaped `(1)` was a regex group in the harness matcher. Corrected literal matching; four-case proof **4 passed/64 checks**, then the final 12-case affected real gate above |
| Boundaries | Metadata-only optional npm scheduler, not GitHub or component mutation UI. Safe durable source storage required for automatic requests; manual bounded fallback cannot promise cross-process throttle without it. Cache clearing/corruption can reset disposable history, never installs/journals. Same retained Debian 12/revision 1 and Arch/revision 1 inputs; no fresh base build, full campaign/legacy broad TUI workflow, installed-manager/pipx, paid/provider, privileged/socket/service or manual-observation evidence. CI/release gates unchanged; not a release-readiness claim |

Evidence/commands and next-package handoff are in the working roadmap; logs/XML are ignored
under `.work/up09/`, real manifests/logs under `.work/logs/up09-*`. All real attempts, failed or
successful, used isolated product roots and guarded product cleanup. Ending verified own-rootless
inventory: zero containers/volumes/run helpers and unchanged four original full tagged-image IDs.
No changes to manager version, metadata/backup schemas, image assets, core lifecycle/identity/
base guards, bounded diagnostic/probe implementations, worker adapter, dependencies or release gates.

Final review after an initial four-way **1406 passed/72 skipped** matrix and 12-case real gate
caught a freshness edge: waiting behind a cached-only background consideration must not let
explicit Check reuse old success. Narrowly corrected coalescing; new regression, **56 passed**
focused review, and the final complete/real results above. During rerun, `/tmp` tmpfs inode
exhaustion produced **1 failed/1027 passed/72 skipped/379 setup errors** in lowest 3.11; preserved
log/XML, manifested/removed only this conversation's UP-09 pytest roots, then reran all remaining
complete suites cleanly. Final-code 3.11/current had already passed and matches all final outcomes.
No source/test assertions/gates changed to resolve infrastructure exhaustion; older runs, user
data and Docker objects were not deleted. Product source is unchanged after final verification.
Local sdist/wheel, strict twine/content checks and source/wheel equality for all seven changed/new
product modules pass; no install/upload. Final document/CLI/quality subset **41 passed**, 3.01 s,
not another complete suite. Seven source hashes are retained in `.work/up09/verified-source-sha256.json`.

### Unpublished UP-10 — 2026-10-30

| Layer | Result |
|---|---|
| Complete unit/host/pilot suites | **1365 passed, 68 opt-in skips in each of four serial foreground runs**: Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0; pip checks clean, only the two known lowest-Typer deprecations. Times 153.47/148.59/152.04/147.78 s; all **1433 ordered IDs/outcomes identical** |
| New/retained regressions | **39 additional default-suite cases**, plus updated prior CLI/TUI assertions for explicit selected Check, partial source/row failures and policy comparisons. New cases cover Docker-free history, inspect-without-probe/cache-writes, absent-container journal visibility, base provenance/freshness, current/lowest Textual keyboard/focus/resize/80x24/larger, independent/coalesced source progress, stale errors, canceled/late-generation results, long Details/empty inventory and notification ownership with production toast rack enabled |
| Real terminal/Docker/OpenCode | **8 tests/136 checks passed**, no skips/deselections, `up10-verified`, 193.19 s: scoped diagnostics/version lifecycle/Updates cases on both retained distributions. Real terminal at 80x24/120x40 includes actual bounded loopback HTTP success/failure/cancellation, explicit immutable base probes, stopped no-start/metadata checks, full visible controls and restored terminal. Lifecycle retains actual 2.2.0 -> 2.1.4 -> checkpoint rollback, interrupted recovery, restore/recreation invalidation and user data/configuration preservation |
| Failure trail | Initial two no-network-on-opening tests reproduced the old behavior. First full run: 1 failed/1360 passed/68 skips due to a new registry-loop variable matching the existing no-distro-branches gate; renamed without changing the gate. Initial terminal run: 4 test bodies completed but **4 teardown errors / 30 failed checks** (34 passed checks), exposing advisory overlays plus a test Escape/next-key sequence error. Corrected/rerun; proof 4 passed/64 checks at both sizes/distributions. Production toast rack is now explicitly enabled in the pilot regression; no advisory objects are cleared to make the test pass |
| Scope/boundaries | Manual UP-10 checkpoint only, not UP-09. No new scheduler/preference, automatic install/start, universal executor, schema, core lifecycle, worker adapter, identity proof, image asset, dependency or CI/release-gate change. Legacy broad `test_50_tui.py` Updates expectations adjusted but that entire test is not rerun; new dedicated real terminal rows cover this changed workflow. No fresh base build, installed-manager/pipx, full campaign, paid/provider, privileged/socket/service or manual-observation evidence; not a release-readiness claim |

Final code is unchanged after the full compatibility matrix. A subsequent test-only harness
follow-up added named/labeled transient-helper manifest capture, then reran all eight real cases
as `up10-verified`. Final source/wheel checks cover all four changed/new product modules;
local sdist/wheel and strict metadata/content checks pass, without install/upload. The final
document/CLI/quality subset passed **41 tests** (3.03 s), not an additional full suite.
All four real attempts used isolated product roots/manifests and guarded product cleanup;
ending own-rootless inventory: zero containers/volumes/run helpers and unchanged four original
full tagged-image IDs. Retained file-only backups, caches and logs are ignored local artifacts.

### Unpublished UP-07 + UP-08 — 2026-10-30

| Layer | Result |
|---|---|
| Complete unit/host/Textual-pilot/local-process suites | **1326 passed, 64 opt-in skips in each of four serial foreground runs**: Python 3.11.18/3.14.8, Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0; pytest 9.2.0, pip checks clean. Only known lowest-Typer/Click deprecations. Includes Ruff/shellcheck, language/links/CLI and existing host terminal coverage |
| New mocked/host/HTTP/pilot coverage | 125 additional default-suite cases: strict semver/compatible selection despite another latest major, prereleases/explicit alternatives, source errors/size/deadline, cache privacy/corruption/non-finite/future times/expiry, Retry-After including long delays, canceled-attempt retention, immutable identity/lifecycle invalidation, stopped/unknown/unverified history, pin/network/journal refusals, exact-target consent/revalidation, readiness not passing stale evidence and explicit Manual/Pinned reports at 80x24/100x30 |
| Scoped real Docker/OpenCode | **4 tests/72 checks passed**, no skips/deselections, `up0708-final`, 150.84 s: retained Debian 12/revision 1 and Arch/revision 1, OpenCode 2.2.0 -> explicit 2.1.4 -> checkpoint rollback; same-version/no-install, stopped dated evidence with byte-unchanged metadata/StartedAt, pin/network-none refusals, SIGKILL/update-recover, recreation and file-only restore invalidation, system/home/workspace/user-config preservation; bounded probes, canceled-client/helper cleanup and missing-timeout refusal/restoration still pass |
| Public npm read | Bounded packaged HTTP child selected supported stable **2.2.4** from live abbreviated metadata (measured response 2,061,815 bytes); isolated cache stored source/time/attempt. No model/provider call, host npm or host OpenCode. Major-rollover and outage/rate-limit behavior use controlled real-loopback HTTP/mocks, not a claim of a public-service outage |
| Failures/review | Four original regressions failed before patch. Intermediate runs exposed mock identity assumptions, readiness consumers, import/style errors and a missing real-test marker; corrected/rerun, never suppressed. Final review hardened non-finite cache data and removed premature Retry-After clipping; all four final complete suites include these corrections. First real attempt: 2 passed/2 harness failures; corrected run 4 passed/68 checks, then final restore-extended 4 passed/72 checks |
| Package/resources/boundaries | Local 6.1.0 sdist/wheel, strict metadata/content and byte-identical changed-module checks; no upload/global install. Three real runs manifested resources and finished with guarded product cleanup/leak checks. Final own-rootless inventory: zero containers/volumes, unchanged four original full tagged-image IDs; no run helpers remain. No new full real campaign, fresh base build, privileged/socket/service change, paid provider, installed-pipx, report-specific real terminal or manual observation evidence; no release-readiness claim |

After the full suites, three future-time parameter IDs were given stable names (no values,
assertions or product changes), and engineering evidence was finalized. The entire new-test
plus quality/language/links/CLI subset then passed **165 tests in each of four combinations**.
Those are focused repeats, not additional full-suite runs. The final wheel matches all six
changed/new product modules; the actual full-suite outcomes agree across combinations after
normalizing only those three former import-time timestamp IDs.

### One-time performance checkpoint after UP-06 — 2026-10-30

- Two unchanged baselines, one diagnostic full run and two post-change full runs: **1201 passed,
  62 opt-in skips each**, Python 3.11/current. Exact ordered IDs/outcomes matched.
- Focused CLI/version/quality/language/document subset: **80 passed** in each other compatibility
  combination (3.11/lowest, 3.14/current, 3.14/lowest); only known lowest-Typer deprecations.
  These are not new full-suite results for those combinations.
- Local build/strict twine/content/workflow checks passed. No application/CI/version/schema change,
  dependency installation, new real Docker/OpenCode/pipx/manual evidence or release work. Original
  safety checks, negative cases and release requirements remain intact.

### Unpublished UP-06 and roadmap consolidation — 2026-10-30

| Layer | Result |
|---|---|
| Full unit/host/Textual-pilot/local-process suite, Python 3.11.18 and 3.14.8, current/lowest dependencies | **1201 passed, 62 opt-in skips in each of four serial foreground runs**; Typer 0.27.3/Textual 8.2.8 and 0.16.0/4.0.0. Only the two known lowest-Typer/Click deprecations. Includes Ruff/shellcheck, language/links/CLI checks and existing host terminal fixtures |
| New advisory pilot cases | **26 cases**, mocked checks/Docker and real isolated metadata: original missing-image warning then successful Refresh at 80x24/100x30; same-turn and repeated warning/unknown/success transitions; overlapping categories; unrelated same-title notices; expired notice cleanup; active mutation progress and completion/recovery result preservation; overlapping readiness waits; phase-error attribution; skipped categories not guessed successful; Docker-free metadata refresh; replaced worker cannot publish late warnings |
| Reproductions and reruns | Original regression **2 failed**, 1.51 s, before patch. New same-turn readiness notification regression **2 failed/79 passed**, exposing a queued toast after cleanup; fixed with owned synchronous notification registration. Two focused iterations also found single Ruff nested-if failures (167 and 191 passed respectively); corrected with no suppression. All four final suites pass |
| Package | Python 3.11 local 6.1.0 sdist/wheel, strict twine and `check_dist.py` passed; changed product module `tui.py` byte-identical in wheel. No upload/global installation/installed-manager run |
| Resources / real layers | Read-only own-rootless inventory before/after: zero containers/volumes, unchanged four original full tagged-image IDs. No Docker resources created/changed/deleted; no cleanup needed. No new real Docker mutation, real OpenCode, isolated pipx, advisory-specific real-terminal or manual observation evidence claimed; UP-05's scoped real results remain historical for UP-06 |
| Planning | D-057 and the roadmap consolidation checkpoint group related work and remove artificial dependencies without reducing acceptance gates. The planning-only language/links/CLI subset passed **27 tests** before UP-06. UP-00..UP-06 complete; next UP-07 + UP-08 together; no release work |

### Unpublished UP-05 — 2026-10-30

| Layer | Result |
|---|---|
| Full unit/host/Textual-pilot/local-process suite, Python 3.11.18 and 3.14.8, current/lowest dependencies | **1175 passed, 62 opt-in skips in each of four serial foreground runs**; Typer 0.27.3/Textual 8.2.8 and 0.16.0/4.0.0. Only the two known lowest-Typer/Click deprecations. Includes Ruff/shellcheck, language/links/CLI checks and existing host terminal fixtures |
| New host/mocked/HTTP/pilot cases | 51 cases: finite read-only allowlist versus unbounded mutations, timeout/cancel/overflow/interrupt reaping, retained pipes/descendants, reserved PGID and launch-signal ownership, no output/argument leakage on bound failures, total DNS/slow-drip HTTP bounds, label/full-ID helper cleanup/refusals, timeout-tool errors on both output streams, 80x24 responsive cancellation and no late publication |
| Scoped real Docker/OpenCode | `test_42_base_coordination.py` plus new `test_43_diagnostics.py`: final **6 passed, 106 logged checks, no skips/deselections**, `up05-final`, 87.01 s. Four packaged/retained base-race variants retain immutable selection/pins/layers; two diagnostic cases use retained Debian 12/revision 1 and Arch/revision 1, OpenCode 2.2.0, network none. Real exec/image deadlines, canceled-host-client bounds, immutable label-checked helper removal, missing timeout-tool refusal/restoration, no stopped-container startup, byte-identical stopped-check metadata and writable-layer preservation |
| Real defect/rerun | First diagnostic-only real attempt: **2 failed**, Docker's missing-executable message appeared on stdout rather than stderr. Classification now checks both; host regression added. Diagnostic rerun **2 passed/28 checks**, then combined runs **6 passed/106 checks** before and after final PGID-reservation review. No failure suppressed, no unbounded fallback added |
| Package | Python 3.11 local sdist/wheel 6.1.0, strict twine and `check_dist.py` passed; all eight added/changed product modules byte-identical in wheel, including standalone HTTP child. No upload, global installation or fresh pipx run |
| Resources | Four real runs used manifests, test helper names/labels, guarded product cleanup and leak checks. Ending verified daemon: zero containers/volumes, same four original full tagged-image IDs, no run-labelled helpers. Test-only timeout-tool renames restored before environment deletion. Shared base lock files/build cache retained; no daemon/network/host service changes |
| Not re-established / boundaries | No full real campaign, new real-terminal/manual observation, privileged restart/socket activation, model-provider use, installed-manager/pipx execution or public npm outage/discovery. HTTP failure evidence uses real loopback transport and a controlled DNS-blocking child. Full reports can consume multiple per-call budgets. Bounds are not a hostile-container or daemon-liveness guarantee; inaccessible cleanup is explicitly unconfirmed. Long mutations/user sessions remain unbounded by these diagnostic limits; existing journals/recovery stay authoritative |

### Unpublished UP-04 — 2026-10-30

| Layer | Result |
|---|---|
| Full unit/host/Textual-pilot/local-process suite, Python 3.11.18 and 3.14.8, current/lowest dependencies | **1124 passed, 60 opt-in skips in each of four serial foreground runs**; Typer 0.27.3/Textual 8.2.8 and 0.16.0/4.0.0. Only the two known lowest-Typer/Click deprecations. Includes Ruff/shellcheck, docs/CLI structure and existing host terminal fixtures |
| New mocked-Docker/host regressions | 49 cases for cached-build/creation-time order and ties, explicit downgrade, alias consolidation/consumption, exact tags/full IDs, changed/missing copies/current base before and after verification, ownership/inspection failures, daemon/distribution binding, late-arriving copies, legacy provenance/no version label, immutable probes, no-op, collision/verification refusal, lock scope, CLI list/choice/confirmation/cancel/no-terminal/yes |
| UP-03 packaged-definition gate | **RESOLVED** after DNS recovered. Before the UP-04 patch: **2 passed, 24 logged checks, 2 retained-fixture cases deselected**, `up04-packaged-retry`, 481.35 s. Debian 13/revision 2 and Arch/revision 1 built with OpenCode 2.2.0 under disposable tags, real OS/tool/binary verification and races; package download/build steps executed. No host network change or cache prune |
| Scoped real Docker/OpenCode and CLI | All four packaged/retained variants of `test_42_base_coordination.py`: **4 passed, 76 logged checks, no skips/deselections**, final `up04-proof` (61.93 s). Adds real CLI alias-consolidated listing, ambiguous `--yes` refusal, retag-after-consent refusal, explicit immutable-ID selection, exact verified publication and replaced-image preservation. Existing cross-directory/context races and running-container/writable-layer marker checks still pass. Packaged builds may reuse cache; retained fixtures remain explicitly Debian 12/revision 1 and Arch/revision 1, not package-refresh evidence |
| Package/static | Local Python 3.11 sdist/wheel, strict twine and `check_dist.py` passed; three changed product modules byte-identical in wheel. Manager remains 6.1.0. No upload/global installation/fresh pipx run |
| Resources | All three real runs manifested/cleaned their test resources; final verified daemon inventory has zero containers/volumes and exactly the four original tagged-image IDs. No final-run labelled images or socket aliases remain. Shared lock files and build cache intentionally retained |
| Not re-established | Full real campaign, privileged restart/socket activation, new real-terminal/manual UI observation, model-provider use or installed-manager/pipx execution. No full-refresh/no-cache/pull claim; that product operation remains UP-13. Diagnostic deadlines/probe cleanup remain UP-05; no release-readiness inference |

### Unpublished UP-03 — 2026-10-30

| Layer | Result |
|---|---|
| Full unit/host/Textual-pilot/local-process suite, Python 3.11.18 and 3.14.8, current/lowest dependencies | **1075 passed, 60 opt-in skips in each of four serial runs**; current Typer 0.27.3/Textual 8.2.8, lowest 0.16.0/4.0.0; only the two known lowest-Typer/Click deprecations. Includes Ruff/shellcheck, documents, CLI structure and existing host terminal fixtures |
| New host/mocked-Docker regressions | 60 cases: cross-data/config/HOME/TMPDIR/runtime/context process convergence, daemon/distribution separation, lock order, crash release, exec descriptor closure, unsafe ownership/modes/symlink/hardlink/FIFO/path replacement, participant guards, changed/failed image inspection, local references, colliding image tags and first-build safety |
| Final test-only strengthening | Descriptor noninheritance now directly inspects the exec child's open file identities, not just reacquisition after unlock. Base-lock/static subset **35 passed** in each of the four combinations after that assertion change; no product change after the full suites |
| Scoped real Docker/OpenCode version verification | `test_42_base_coordination.py -k local-fixture`: **2 passed, 24 logged checks, 2 packaged-definition cases deselected**, final run `up03-proof` (22.30 s). Separate data directories, real context aliases including a socket symlink, build/rollback/cleanup/creation races, pin check through creation, immutable swaps and writable-layer markers. Explicit network-free fixtures derived from retained Debian 12/revision 1 and Arch/revision 1 with OpenCode 2.2.0; tool/OS/binary verification still runs, not new-package installation or current-definition freshness evidence |
| Fresh packaged-definition variant | **Initially BLOCKED, not passed in UP-03**: initial attempt had 2 failures (104.30 s), Debian at Docker Hub DNS resolution for `node:24-trixie`, Arch at mirror DNS resolution during pacman. Both failed before publication and cleaned up. No networking/security changes or silent skips. Resolved by the UP-04 retry above, not relabelled as a UP-03 pass |
| Package | Python 3.11 sdist/wheel built locally with unchanged version 6.1.0; strict twine and `check_dist.py` passed, new `base_locks.py` byte-identical in the wheel. Not uploaded/installed globally; no fresh pipx or installed-manager race run |
| Resources | Each real run has a manifest and guarded product cleanup; final run has zero objects with its data/test labels, unchanged original tagged images, socket aliases removed. Shared private lock files remain intentionally (never unlinked); build cache was not pruned |
| Not re-established | Full real campaign, fresh Debian 13/Arch package builds, privileged daemon restart/socket-activation rows, real model provider, or new real-terminal/manual UI observation. Earlier release evidence remains historical; no release-readiness inference |

### Unpublished UP-02 — 2026-10-30

| Layer | Result |
|---|---|
| Full unit/host/Textual-pilot/local-process suite, Python 3.11.18, current dependencies | 1015 passed, 56 opt-in skips (real-campaign, privileged and socket-activation rows); mocked Docker, no live daemon mutations |
| Affected regression subset, Python 3.11.18 and 3.14.8, current/lowest dependencies | 220 passed, no skips in each of four serial runs; Typer 0.16.0/Textual 4.0.0 and current 0.27.3/8.2.8; only the known lowest-Typer/Click deprecations; final 3.11-current run includes updated engineering records |
| New report coverage | Mocked offline/timeout/HTTP/invalid-response and unexpected registry failures, failed local source, both-source failures, malformed policy/ownership refusal/formatting errors with surviving rows, CLI stdout/stderr/exit 2, 80x24 pilots, metadata unchanged, no stopped/created starts, no network without explicit check, unchanged policy comparisons |
| Static/documents | Ruff/shellcheck, English, links/anchors and CLI structure passed in the suite; broad report handlers are checked for typed error presentation, with narrowly documented BLE001 annotations rather than a blanket exclusion |
| Not re-established | Report-specific real terminal/manual observation, live npm outage/discovery, real Docker/OpenCode, package build or pipx updates; existing loopback HTTP and host-process fixtures are not evidence of a live service outage |

### Unpublished UP-01 — 2026-10-30

| Layer | Result |
|---|---|
| Full unit/host/Textual-pilot/local-process suite, Python 3.11.18, current dependencies | 982 passed, 56 opt-in skips (real-campaign, privileged and socket-activation rows); mocked Docker, no live daemon operations |
| Affected regression subset, Python 3.11.18 and 3.14.8, current/lowest dependencies | 198 passed, no skips in each of four serial runs; lowest Typer 0.16.0/Textual 4.0.0 and current 0.27.3/8.2.8; only the two known lowest-Typer/Click deprecations; final 3.11-current run includes updated records and regenerated illustration |
| Report-specific pilot coverage | Agent Context observed/missing/offline/current/outdated, preserved saved file, Versions success/failure, readiness and cleanup titles, required title, literal markup, scrolling/focus/Close/Esc, 80x24 and larger |
| Static/documents | Ruff and shellcheck passed in the suite; English, links/anchors and CLI structure passed; dashboard illustration regenerated with fake data |
| Not re-established | Report-specific real terminal/manual observation, real Docker/OpenCode or pipx update/package verification; the existing host-process terminal tests in the full suite are not live-Docker evidence |

### 6.1.0 release tree — 2026-10-30

Release branch `release/6.1.0`: version, CHANGELOG, documents and records only; product
modules other than `__version__`, image assets and schemas are identical to the verified
candidate below. Everything in this table ran on the release tree itself.

| Layer | Result |
|---|---|
| Unit, host, Textual pilot, local processes | 969 passed, 56 opt-in skips in each of four serial suites (3.11.18 and 3.14.8, current and lowest direct dependencies); skips per suite: 49 real-campaign, 3 privileged and 4 socket-activation opt-ins, nothing else |
| Static | Ruff, shellcheck (in the suites), actionlint and offline zizmor clean |
| Package | sdist and wheel 6.1.0 on both endpoints; `twine check --strict` and `check_dist.py` passed; `release_check.py v6.1.0` accepts the dated CHANGELOG section |
| pipx (CI-equivalent) | Installation of the branch from a `git+file` URL into isolated pipx directories on 3.11.18 and 3.14.8: `pipx_smoke.sh` passed (version, installed package and assets, `doctor` exit 8 for a missing context); 27 installed files byte-identical to the tree; read-only `doctor` against the real daemon exit 0, identity verified, resource support passed, the retained revision-1 Debian base warned as expected, no data directory written |
| Repeated in a fresh clone | The four suites (same counts), Ruff/actionlint/offline zizmor, both-endpoint package and release checks, `git+file` pipx on both endpoints with a byte-identical payload and real read-only `doctor` exit 0 |
| Real Docker, scoped | `test_20_security`, `test_35_prerequisites` and `test_65_pipx` (pipx tag install/upgrade/downgrade/uninstall from a disposable clone) on 3.14.8: 4 tests, 66 checks passed, 0 failed; guarded cleanup, no containers or volumes left, image inventory unchanged |
| Full real campaign (I04) through an installed pipx manager | `pipx install git+file://…@v6.1.0` of a local test tag (in a disposable clone of the branch) on Python 3.14.8 as `OCS_TEST_MANAGER`; both base images built from the installed package's assets into a test-only `ocs-test-610` namespace (Debian 13 revision 2, Arch revision 1, OpenCode 2.2.0); the published `v6.0.0` installed from GitHub as `OCS_TEST_LEGACY_MANAGER` against the retained Debian 12 base; `OCS_TEST_PRIVILEGED=1`, `OCS_TEST_SOCKET_ACTIVATION=1`, `OCS_TEST_PIPX_BUILD=1`: 56 tests, 513 checks passed, 0 failed, 0 skipped (11 min 2 s). Nothing left with the run's data-directory label, tagged images unchanged, C10 units and runtime tree removed, the user's daemon active after the privileged restarts |
| Harness setup found by the first I04 attempt | The runner venv lacked pipx (`test_65`) and the volatile `$XDG_RUNTIME_DIR/systemd/user` did not exist after a reboot (C10's fixture refuses to start without it); both provided, then the complete rerun above. No product failure |
| Base images without the layer cache | The product's `build_image`/`verify_image` with `--no-cache` (not `--pull`, which could move the user's base tag) from the installed package: Debian 13 (52 s) and Arch (213 s) built every `RUN` step against current upstream packages and passed verification |
| Real model provider | Installed 6.1.0 manager, isolated data: `providers set` at a hidden pty prompt (not echoed; 0600 profile; `providers list` names only), a Debian 13 `ocs-test-610` environment with network bridge, the user model `openrouter/z-ai/glm-5.3-flash`; the managed `run` opened the real OpenCode 2.2.0 TUI and the model answered `BASEOS=Debian 13` from the injected guidance without tools; terminal restored. The key was in no host process argument list, not in the container definition, home volume, workspace, `/tmp`, data directory, configuration (other than the profile) or the backup: 13 checks passed |
| Pre-tag scans (RELEASING) | `gitleaks git` and `gitleaks dir` clean; `detect-secrets scan --all-files` (1.5.0) reports only the tests' deliberate dummy values; no home path, user or host name, private network address or e-mail address other than `example.invalid`/`example.org` |
| Release decision (I06) | READY WITH ACCEPTED RISKS: every P0 and P1 row of `CAMPAIGN.md` PASS; the accepted risks are D09's host reboot and the items under "Unverified behaviour" |
| Hosted CI on GitHub (release pull request, first runs of the revised matrix) | The first run failed one job: the Arch Linux userland container has no Docker CLI, and three configuration-change tests reached the real `docker` binary through the guidance refresh (elsewhere that call failed quietly against the fake endpoint). Fixed in the tests; an autouse fixture now makes any uncaught Docker CLI call behave as without a CLI on every host, so the local suites reproduce that job. Second run, all 10 jobs passed: Ubuntu 26.04 runners, unit suites on 3.11 and 3.14 with current and lowest direct dependencies 969 passed, 56 skipped each; Arch Linux userland (rolling Python, unprivileged user) 968 passed, 57 skipped (also `/run/user` missing in the container); package build and content and pipx installation from the checkout on 3.11.17 and 3.14.9; workflow lint |
| Publication (2026-10-30) | The `main` ruleset's required checks set to the ten job names of the revised matrix; the release pull request merged with a merge commit (tree identical to the verified release tree); CI on `main` passed; annotated tag `v6.1.0` on the merge commit; the release workflow passed (tag and CHANGELOG check, the CI jobs against the tag, pipx installation of the tag on 3.11 and 3.14) and created the draft, whose notes equal the CHANGELOG section; published as the latest release. pipx from GitHub (`git+https://…@v6.1.0`) in isolated directories on 3.11.18 and 3.14.8: version 6.1.0, 27 installed files byte-identical to the tag, real read-only `doctor` exit 0 |
| Not run on this tree | A host reboot (D09) |

### 6.1.0 candidate — 2026-10-29–30

Complete verification of the 6.1.0 implementation (D-047..D-054) before the version and
document changes. Platform: Arch Linux, kernel 7.2.11, Python 3.11.18 and 3.14.8, Git 2.56.0,
Docker 29.9.2 rootless (RootlessKit 3.3.0, slirp4netns), Typer 0.27.3 and Textual 8.2.8 (lowest
direct: 0.16.0 and 4.0.0), pyte 0.8.2, pipx 1.18.7, OpenCode 2.2.0 in both base images (2.1.4
for the update rows).

| Layer | Result |
|---|---|
| Unit, host, Textual pilot, local processes | 969 passed, 56 opt-in skips in each of four serial suites: 3.11 and 3.14, current and lowest direct dependencies; `pip check` clean; only the two known Typer/Click deprecations with the lowest dependencies. Repeated independently on 2026-10-30 with the same result |
| Static | Ruff, shellcheck, actionlint and offline zizmor clean; existing documented exclusions unchanged |
| Package | sdist and wheel on both endpoints; `twine check --strict` and `check_dist.py` passed; 27 installed source and asset files byte-identical to the candidate |
| pipx | Source-free installation from local Git tags on both endpoints; tag upgrade/downgrade, `reinstall --python`, uninstall with data retention and foreign-launcher safety: 1 test/21 checks on each endpoint; the CI smoke script measured exit 8 (missing context) and exit 4 (a private rootful daemon) on both |
| Base images | Both packaged definitions built under test tags: Debian 13/revision 2 and Arch/revision 1 with OpenCode 2.2.0; OS, tools, tar and package/AUR checks passed. The user's base tags were never replaced |
| Full real campaign through an installed pipx manager | 56 tests, 513 checks, 0 failed, 0 skipped (10 min 22 s), with the privileged rows and the C10 socket-activation units explicitly authorized, the image build from the installed package and a separately installed pre-change manager for the retained Debian 12 rows |
| Base version workflows | 13 real checks on both test bases: update, rollback to the exact base ID, old/new/pinned environments preserved, a Debian 12 base copy refused on the Debian 13 definition |
| Scoped real rows | C10 4 tests/14 checks from source and from an installed wheel (cold activation, warm path, overlapping start, stalled deadline, quit/Ctrl+C, own-user proxy refused); C05 1 test/8 checks reading `cpu.max`, `memory.max` and `pids.max`; H05 6 tests/83 checks (real OpenCode on both images, dashboard SIGKILL, CLI SIGTERM/SIGHUP, terminal restoration) |
| Secrets and personal data | gitleaks: no leaks in the tree or history; detect-secrets: seven reviewed dummy test values; no personal paths outside fixtures |
| Cleanup | Every data directory ended with the product's guarded cleanup; no containers, volumes, session clients, private daemons or test units left; original image tags and IDs unchanged. The build cache grew from real builds and was not pruned |

Failures found during verification, fixed with regression tests and rerun (never waived):

- A catchable signal between fork/exec and `Popen` storing the PID left the session client
  unowned (4 of 80 concurrent runs); fixed by D-054. The first real rerun then found terminal
  echo/canonical mode left off after SIGTERM/SIGHUP; the manager now restores its terminal.
- The campaign's crash row raced systemd's automatic restart and hit the start limit, and
  failed inventory queries could look like an empty inventory. The harness now waits for the
  automatic restart, restores the daemon in teardown and refuses failed inventory queries.
- The first activation run lacked the rootless launcher directory on the test's `PATH`.

Not verified in this round: hosted execution of the revised CI matrix, a real model provider,
a host reboot (D09), other host distributions and manual observation.

### Released 6.0.0 evidence

Release verification of 6.0.0 (2026-10-29) on the tree of the initial public commit; the release
commit changes only this file, `CAMPAIGN.md` and the CHANGELOG date. The privileged rows ran on
2026-10-28 on an earlier tree, which differed in the hosted-CI test fixes, the host-scope
documents (D-046), a comment in `install.sh`, one help text in `setup-rootless.sh` and the text of
two host hints. Platform: Arch Linux, kernel 7.2.11,
Python 3.14.8, Git 2.56.0, Docker 29.9.2 rootless (slirp4netns), Typer 0.27.3, Textual 8.2.8,
pyte 0.8.2, pipx 1.18.7, OpenCode 2.2.0 in both base images (2.1.4 for the update rows).

| Layer | Result |
|---|---|
| Static | `ruff check src tests .github/scripts` 0 findings; shellcheck on `install.sh`, `setup-rootless.sh`, `pacman-retry`, `install-opencode.sh`, `.github/scripts/pipx_smoke.sh` 0; `actionlint` (with shellcheck on the `run:` scripts) 0; `zizmor --offline` 0, also `--pedantic` (two documented ignores) |
| Unit, host, Textual pilot | 791 passed, 49 skipped with `pyte` installed, 37 without it (the terminal modules then skip as a whole); every skipped test is a real-campaign test |
| Real campaign: every module, both distributions, and the pipx rows with the image build from the installed package (`OCS_TEST_PIPX_BUILD=1`) | 44 tests passed, 451 checks passed, 0 failed (9 min 26 s); the 5 privileged tests skipped (not requested for this run); nothing left with the run's data-directory label; tagged images and the network interfaces unchanged; the build cache pruned back to its size before the run |
| Privileged rows (`OCS_TEST_PRIVILEGED=1`), on the earlier tree described above | the full campaign including them: 49 tests, 495 checks passed, 0 failed (8 min 39 s); the firewall ruleset unchanged |
| Real campaign through a pipx installation of a local test tag (`OCS_TEST_MANAGER`) | `test_10_lifecycle`, `test_35_prerequisites`, `test_40_opencode` (first prompt and Agent Context, both distributions), `test_50_tui`: 7 tests, 193 checks passed, 0 failed |
| Hosted CI on GitHub (`ci.yml`, first runs before publication) | Ubuntu 26.04 runner, Python 3.14.9: unit suite with the current and with the lowest direct dependencies 790 passed, 38 skipped each; the Arch Linux job (`archlinux:base-devel` container, unprivileged user, umask 022) 789 passed, 39 skipped; skip reasons listed (`-rs`): real-campaign modules, the root-refusal test where the runner blocks unprivileged user namespaces, and `/run/user` missing in the container; package build and content check; pipx installation from the checkout with `pipx_smoke.sh`: `doctor` exit 8 for a missing context and exit 4 (`mismatch`) for the runner's rootful daemon; actionlint and zizmor 0. The first run found two environment dependencies in tests (Typer's forced colour terminal under `GITHUB_ACTIONS`, the runner's 2 CPUs), fixed in the tests |
| CI rehearsal (before the first hosted run) | the same jobs run locally in fresh venvs and an `archlinux:base-devel` container; `release_check.py` refuses the undated section and passes a dated one; `build_image.py debian` built and verified the image against the rootless daemon |
| Package | sdist and wheel built from the public tree, `twine check --strict` and `check_dist.py` passed; pipx installation of the tree from a `git+file` URL: `pipx_smoke.sh` passed, `doctor` verified the daemon and both images |
| Publication smoke (recorded after the release) | Release workflow passed and created the draft; release published by the owner. pipx from GitHub over `git+https` at `v6.0.0` passed in isolated pipx directories (`--version`, `doctor`, `pipx_smoke.sh`, uninstall). Not repeated during stabilization |
| Secrets and personal data | gitleaks 8.30.1 (`git` and `dir` modes): no leaks; detect-secrets 1.5.0: 6 findings, all deliberate dummy values in tests; no home paths, user or host names, private addresses (only rootlesskit's documented `10.0.2.2`) or personal e-mail addresses |
| Real terminal, scripted | dashboard at 80x24 and 120x40, direct-workspace consent dialog at 80x24 |
| Documents | README rendered at 80 columns and read; commands, options, links and anchors checked by tests |

Release matrix: `CAMPAIGN.md` (90 rows): P0 50 PASS, P1 35 PASS, P2 4 PASS and 1 PASS in part
(D09: host reboot BLOCKED, accepted); no FAIL, no NOT TESTED. Run logs stay on the test machine
(`.work/logs/`) and are not part of the repository. The campaign prints `DeprecationWarning`s of
Python's `pty.forkpty()` (the test process has threads when it opens a terminal); no effect was
observed.

## Known issues

Known issues and limitations accepted by design: `ISSUES.md`. Small open items, including two
test-isolation limitations of the host-process signal tests: `TODO.md` ("Optional Polish").

## Unverified behaviour

- Real model providers other than OpenRouter with `z-ai/glm-5.3-flash` (OpenCode 2.2.0,
  Debian 13, verified at the 6.1.0 release tree), and a real provider on the Arch image; the
  automated first-prompt rows use a fake OpenAI-compatible provider inside the container.
- A host reboot (daemon restart, stop/start and a SIGKILL of the daemon unit were tested). Next
  step: reboot, then `opencode-sandbox start NAME` and `check NAME` on a test environment.
- Another user's real rootless dockerd (another user's socket and a real rootful dockerd were
  refused).
- pipx versions other than 1.18.7; Python 3.12/3.13 separately; interpreters below 3.11
  (outside the declared range).
- The scheduled image build on GitHub (`images.yml`).
- Other distributions' packaged socket units and activation variants (an isolated user
  listener with a separate rootless daemon was verified on Arch, also through pipx). Another
  user's actual rootless dockerd is represented by another user's socket, not provisioned.
- Typer 0.16.0 with Click 8.5 warns that Click 9 removes helpers it imports: the lower bound may
  have to rise when Click 9 is released (the lowest-dependencies CI job shows it).
- Real rootless Docker on hosts other than Arch Linux (D-046), a host without systemd, and a host
  without delegated cgroup controllers; Textual 4.0 (the declared lower bound) in
  a real terminal (its unit and pilot tests pass);
  terminal emulators other than pyte; a kill inside `docker commit` itself; Dockerfile linting;
  performance beyond the recorded baseline (CAMPAIGN I03, no targets).

## Documentation entry points

| Document | Role |
|---|---|
| `README.md` | Overview: status and AI disclosure, fit, features, security summary, tested environment, install, quick start, external services |
| `docs/README.md` | Index of the user guides (`install.md` … `troubleshooting.md`); `docs/images/dashboard.svg` is generated by `tests/dashboard_screenshot.py` |
| `CHANGELOG.md` | Changes per release |
| `CONTRIBUTING.md`, `SECURITY.md` | Contribution rules and test layers; vulnerability reporting and scope |
| `AGENTS.md` | Instructions and permission boundaries for coding agents |
| `TODO.md` | Roadmap: active Updates effort, what 6.1.0 delivered, optional polish and deferred features |
| `docs/engineering/BASELINE.md` | This file: current state |
| `docs/engineering/ARCHITECTURE.md` | Current design and module map |
| `docs/engineering/DECISIONS.md` | Decisions D-001..D-056 with rationale and implementation status |
| `docs/engineering/ISSUES.md` | Known issues and accepted limitations |
| `docs/engineering/CAMPAIGN.md` | Release test matrix: 84 active rows, seven installer-only rows retired; historical evidence distinguished from the release tree's pending gates |
| `docs/engineering/RELEASING.md` | Release checklist and tag procedure |
