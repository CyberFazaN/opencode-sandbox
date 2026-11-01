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

D-056/D-057's approved UP-00..UP-18 and one-time PERF work is complete, locally and unpublished.
Updates retains `v` and separates Manager, Base Images and Environment OpenCode. It preserves
independent local/registry results, identity-bound history, default-off daily GitHub/npm discovery,
exact consent and existing pins/journals/checkpoints. Environment actions, cached/full-refresh
base rebuilds and identity-bound rollback use their own handlers, not a universal update engine.

Manager Update and foreground-terminal `manager update --tag` now use Cancel-first exact review,
actual process-lifetime leases/worker drain/terminal restoration, independent frozen execution
gates, parked durable installer admission and exact pipx replacement. Fresh source/record/launcher/
runtime/CLI-health checks and owned-process quiescence determine completion. Private state and
verify-only recovery survive helper/venv loss; unknown hard-interruption quiescence stays blocked.
No Update All, automatic installation/restart/rollback, host setup, implicit migration or ongoing
user OpenCode configuration management is added. [Architecture](ARCHITECTURE.md#manager-update-and-independent-recovery)
and [user instructions](../install.md#explicit-reviewed-manager-update) describe the exact limits.

Manager remains **6.1.0**, metadata **2**, backup **3**; image definitions are unchanged. No version
bump, merge, project tag, push, upload or publication occurred. The transient working record is
retired under D-045; permanent evidence is below and earlier checkpoint details remain in Git.
This completion does not authorize release preparation or the subsequent separate reviews/migration.

## Updates final integration

Final code checkpoint: public terminal integration, followed only by the narrow prerequisite/
rendezvous fixes below and record consolidation. Evidence/source hashes/manifests: `.work/up18/`, `.work/up17g/` and
`.work/logs/up18-final*`; earlier failed/pass evidence remains preserved. No test assertions or
CI/release gates were removed, suppressed or weakened.

| Layer | Executed result and scope |
|---|---|
| Complete unit/host/pilot regression | **2220 passed / 86 real opt-in skips** in each selected complete result; **2306 ordered test IDs/outcomes identical**. Python 3.11.18/current **374.60 s**, 3.11.18/lowest **365.27 s**, 3.14.8/current **387.19 s**, final 3.14.8/lowest **387.76 s**. Current Typer/Textual **0.27.3/8.2.8**; lowest **0.16.0/4.0.0**, pytest **9.2.0**. All four pip checks clean; two known lowest-Typer deprecations |
| Final failure trail and scoped reruns | Initial 3.14/lowest complete run: **2216 passed / 4 failed / 86 skipped**, 403.78 s. One new interruption-fixture marker exposed a partial PID record; made readiness atomic and guaranteed owned-family cleanup. Three existing prerequisite exit-status assertions exposed a real base-plan bug: npm could time out before unusable-daemon refusal. Validate explicit versions locally, then verify daemon before latest discovery; existing assertions now also forbid npm. Minimal old/current order reproducer and actual isolated Docker-context refusal (exit **8**, no registry child) retained. **124 affected prerequisite/base/version/pilot/whole-update tests passed on all four endpoints**, 47.70/47.85/54.11/55.03 s. Repeated the failed complete run successfully; unchanged complete runs and positive real matrix were not mechanically repeated |
| Real Docker/OpenCode/terminal/pipx | **31 tests / 1146 logged checks passed**, no skips/deselections, **1381.67 s**, `up18-final`. All prior 29 affected rows plus new manager updater rows: packaged/retained both-distribution base races, bounded probes, actual binary/lifecycle evidence, 80x24/larger Updates/daily discovery/environment recovery/base actions, separate cached/full-refresh package builds, installed pipx lifecycle/provenance, live sessions/exec exclusion, public manager CLI/TUI replacement and independent recovery |
| New manager native combinations | Actual pipx **1.18.7** force between owned exact tagged sources, default/custom-space layouts, real Cancel-first public TUI/CLI and original terminal restoration before arming; non-daemon origin drain still leased/no prepared state. Expected target source/commit/version/launcher/runtime/CLI verified; actual broken CLI leaves startup blocked; explicit manual previous-tag reinstall plus frozen fresh recovery reopens it. Native handled interruption reaps an escaped descendant and verifies previous health; hard helper death retains pending state and refuses same-boot recovery even after the old group is empty. Lost pty still produces durable verified result. Clone-only Git and frozen loopback API transports are declared fixtures, not public-release authentication or a host build sandbox |
| Packaging/static/contracts | Staged-input sdist + wheel build, strict twine and `check_dist` pass; all **63 product files** byte-identical in both artifacts, including the **18-module** frozen inventory and image assets. No test injector/local instructions shipped. Ruff/shellcheck are included in regression; actionlint clean, offline zizmor no findings (existing one ignored/one suppressed unchanged), Git and current tracked-tree gitleaks scans clean. Final record/link/CLI/language/package/static subset **83 passed**, 4.21 s. An initial contract run (**82 passed/1 failed**) found private commit identities and a forbidden internal-reference word newly copied into permanent prose; removed those references, not the contract assertion |

The real command was the existing affected file set:
`test_42_base_coordination.py`, `test_43_diagnostics.py`, `test_44_version_evidence.py`,
`test_51_updates.py`, `test_52_discovery.py`, `test_53_environment_updates.py`,
`test_54_base_updates.py`, `test_65_pipx.py`, `test_66_manager_inventory.py`,
`test_67_installation_exclusion.py`, `test_67_manager_update.py`, with
`OCS_TEST_DOCKER=1 OCS_TEST_RUN=up18-final`, absolute source PYTHONPATH and short external basetemp.
Unit runs were serial foreground, real opt-in off, with separate `.work/up18/full-*.xml` results.

Guarded campaign product cleanup and final read-only own-rootless reconciliation retain the
original four full image IDs and leave no containers, volumes or active current-run script roots.
Removed only **29 exact manifested completed pytest roots**, after preserving **1555 bounded
unit/host operation evidence files** plus every failed/pass XML/source record. Native original
frozen recovery paths (including the intentionally incomplete hard-kill record), shared build
cache and persistent protocol lock inodes remain intact. Existing user installations, workspaces,
configuration, credentials and daemon settings were not changed; nothing was uploaded.

Earlier substantive continuation checkpoints remain scoped evidence: independent frozen tool/
dependency/source/effective-policy checks, separate expected-file/runtime/help verification, then
exact replacement/recovery. Actual private installed proofs
were **2 passed** each for `up17e-proof2` (146.88 s), `up17f-proof2` (146.35 s), `up17g-proof`
(109.49 s), then changed child-admission default-layout **1 passed**, 58.19 s. Public default
terminal proof **1 passed**, 60.39 s. Initial ancestor-Git-config and undeclared-Click failures were
fixed with regressions, not bypasses. Separate official HTTPS reads observed v6.1.0's exact
annotated tag/commit, then independently reread that same graph; the full identities are in the
private source evidence, not signed-code attestation or a public replacement claim.

**Not executed or claimed:** privileged/service/socket-activation/reboot rows, actual post-reboot
recovery, real credentials/paid model calls, human/manual observation, other host distributions,
the complete release campaign or release readiness. Hard-kill unknown-quiescence recovery is
intentionally conservative; no automatic reboot/reset or stale-PID signal is performed. Previous-tag
reinstall does not restore identical dependencies or promise offline recovery. See
[unverified behaviour](#unverified-behaviour) and [release matrix](CAMPAIGN.md).

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
the measurements and findings in this section (the transient working checkpoint is retired).

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

Current Updates completion is [above](#updates-final-integration). The dated development
checkpoints below retain their original scoped evidence/failure trails; their then-pending stages
and next-step/STOP notes are historical, not current implementation status or new work permission.

### Unpublished UP-17 second exact-origin review checkpoint — 2026-11-01

| Layer | Result |
|---|---|
| Complete unit/host/pilot/host-pty suites | **2038 passed, 84 opt-in skips each**, Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0. Four clean pip checks, serial foreground, inode preflight; **287.80/284.12/295.38/288.44 s**. All **2122 ordered IDs/outcomes identical**, only two known lowest-Typer warnings |
| New default cases | **79 cases**: **66 exact-origin review cases**, **10 Textual pilot cases** at 80x24/larger, two required wheel/sdist module gates and one new UI error-reporting contract case. Fresh local/tool/source preparation, immutable critical-record/route/context binding, strict tags and own origin/version/installation, same-endpoint route changes, changed records/settings/source during/between reads, custom network/credential configuration refusal without value/content disclosure, special/cyclic/uncontrolled path refusal, unrelated cache creation, explicit policy approval/Cancel/keyboard focus/scrolling and open-consent handoff refusal |
| Affected real Docker/OpenCode/pipx/pty | **29 tests/954 checks passed**, no skips/deselections, `up17b-final`, **1103.14 s**. All prior 29 rows/assertions retained. Both actual installed default/custom-space pipx layouts add six real console/terminal scenarios: 80x24/120x40 explicit target+policy consent and fresh origin revalidation, default Cancel, changed actual launcher after display, secret-bearing custom index environment and credential-file presence refusals. Original installed record/launcher bytes remain unchanged and operational after exact owned fault restoration |
| Boundary | **UP-17 partial**, internal origin review/consent and fresh origin-side revalidation complete. No public action/entry, installer argv/environment, new Git assessment, helper payload, post-exit/exclusive validator, actual replacement/expected-result success or failure recovery. The in-memory receipt is not an executable capability or durable grant. Manager Update remains disabled |

The new review never accepts caller-supplied classification/tool/cache evidence. It freshly
reconciles actual running pipx provenance/launcher and external tools, retains canonical-prefix
usage through process exit, hashes critical local installation records and observes selected
executable/Python/location/module/configuration routes (including symlink and file identities).
Directory timestamp changes alone do not invalidate review; unrelated cache/log/pyc creation is
not replacement. A hashed HOME/PATH/XDG/pipx context, exact source/object chain and source notes
hash are bound. Local inspection brackets fresh source reads. Origin revalidation requires the
same PID/prefix/version and fresh same local/source observations; it never releases or converts
usage, attempts exclusion or treats a receipt/cache/hash as authorization to install.

Initial network support is deliberately conservative: public defaults only. Known nonempty
pip/Git/uv/Python/loader/proxy/CA/SSH-agent/related environment and known system/user/XDG/shared/
application pip/Git/credential-file presence require manual preservation with static reasons,
without reading credential contents, echoing values or changing files. A recognized local install
can therefore remain unsupported for this review. The form explicitly describes host-trusted
package/build code and the no-backup/no-identical-dependency-recovery limits. A later executor
must independently implement and prove the effective network policy and all execution prerequisites;
presence observations/consent alone enforce nothing. The observed tool/file snapshot is not code
authentication or a complete lazy-file inventory, and external/site code remains trusted local code.

The internal modal has no product route. It displays an already prepared immutable review in
plain read-only scrollable text, with Cancel focused and Confirm disabled until exact target/public-
network acceptance. Cancel/Escape yields no receipt; explicit Confirm returns an Approval holding
that exact Review. The form itself never prepares/revalidates/stages/arms/cancels/installs anything;
open consent still blocks the existing internal dashboard handoff gate. No receipt is passed into
the frozen helper or terminal fixture. Independent post-origin-death exclusive installation/tool/
source/network validation, effective installer network policy, actual replacement/expected installed
source/commit/version/launcher/basic CLI and independent failure recovery remain pending.

Failure trail: missing API reproducer **1 failed**, .02 s. Three focused static import-format
failures with **68/115/277 passing tests**, 13.54/30.10/33.55 s, corrected without runtime/assertion
changes. Initial real `up17b-proof` **2 failed/2 teardown errors**, 129.96 s (**196 checks passed/
2 failed**): the fixture observed the header before controls rendered and batched checkbox plus
Tab/Enter before Textual enabled Confirm. It correctly did not approve. Preserved exact pty/state
evidence, waited for rendered controls and separated policy processing from navigation; no
assertion/budget dropped. Added keyboard-only pilots: lowest Python 3.14 review/UI/static **79
passed**, 24.08 s. Corrected actual installed `up17b-proof2` **2 tests/330 checks passed**, 99.87 s.
Final focused review/UI/package/docs/static **145 passed**, 25.03 s. Further route/strict-tag/version/
credential/cache regressions preceded final source freeze; all four complete and full affected
real gates above cover the final product/checker/test inputs, not just that initial proof.

Evidence `.work/up17b/full-*.xml`, `real-final.xml`, `final-source-sha256.json`, failed/focused runs
and `.work/logs/up17b-*`. Installed fixtures retain read-only Docker context-store access and use
owned private Git/loopback API plus test-only installed site injection to call the internal form
through actual console/bootstrap/identity/tools/source/driver/UI/revalidation. No identity/lock/
terminal/Docker response is mocked; public-release authenticity and human observation are not
claimed. Original version/schemas/assets/dependency bounds, CLI/dashboard public actions,
classification/source/tool/lease/frozen helper/verifier/terminal mechanisms and CI/release workflows
are unchanged. Package content validation additionally requires the two new review modules.
No full campaign, privileged/socket/service/daemon change, real credential/paid API, actual manager
replacement/failure recovery or release-readiness claim. No bump, merge, push, upload, remote
change, project tag or publication.

Final follow-up: no-isolation sdist/wheel, strict twine/content validation and **44 frozen product
module/wheel byte comparisons pass**; no private local instructions/evidence in sdist. Document/
CLI/quality follow-up **44 passed**, 3.35 s (`docs.xml`), separately focused. Own-rootless final
inventory retains all four original full image IDs, no containers/volumes/test tags or owned
manager/helper/verifier/terminal/review/HTTP/probe/guard/watchdog processes. Guarded removal of
**14 exact manifested completed pytest roots**, own UID/inode and live process/socket/mount
references checked; **388 host fixture records/artifacts** archived first. All actual installed
review/source/helper/results/pty and failed/pass XML/logs/hashes/packages, prior evidence, shared
build cache and persistent protocol inodes retained. `/tmp/opencode` empty, **1046221 free inodes**;
prose-only scratch separately manifested/guarded. No product/checker/test input change after final
complete/real gates. Commit locally and stop at the origin-consent boundary; Manager Update disabled.
Final prose language/link/CLI follow-up **27 passed**, 1.98 s (`prose.xml`), separately scoped;
final product/checker/test hashes remain intact.

### Unpublished UP-17 first exact-source checkpoint — 2026-11-01

| Layer | Result |
|---|---|
| Complete unit/host/pilot/host-pty suites | **1959 passed, 84 opt-in skips each**, Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0. Four clean pip checks, serial foreground, inode preflight; **264.68/261.97/267.11/263.63 s**. All **2043 ordered IDs/outcomes identical**, only two known lowest-Typer warnings |
| New default cases | **98 cases**: **97 exact-source cases** (real loopback HTTP/isolated child processes plus validation/cache/concurrency/cancellation/refusal tests), one required-module wheel/sdist gate. Lightweight/nested annotated tags, full official release/ref/object/commit agreement, strict newer versions, malformed/duplicate/non-finite/foreign/cyclic/mixed-OID refusal, graph bracketing, full notes hash, fresh same-target versus latest/cache/no-fallback, total budget/actual inflight cancellation, shared rate limits/restart/unsafe storage, and source-only transport boundaries |
| Affected real Docker/OpenCode/pipx/pty | **29 tests/888 checks passed**, no skips/deselections, `up17a-final`, **1135.62 s**. Same 29 rows/all prior assertions retained. Both actual installed default/custom-space pipx packages add private annotated Git source/OID resolution, fresh independent installed-process revalidation, moved-target refusal, HTTP 429/restarted source/discovery throttling and unchanged operational original launcher/records. Prior real terminal/handoff/shutdown drain, verifier/descendant interruption, actual Debian/Arch mutations/sessions and exclusion tests remain intact |
| Boundary | **UP-17 partial**, only read-only exact published source identity/revalidation complete. No public trigger, startup/status/discovery/UI consumer, helper payload or install consent; no replacement, expected installed source/launcher/basic-CLI success or failure recovery. Manager Update remains disabled. GitHub HTTPS/API evidence is not signed-tag authentication; tests use explicitly private Git/loopback API, not public release authentication |

The independent source gate does not treat a release's `target_commitish`, cached availability or
local provenance agreement as an expected commit. It validates the exact official release by tag,
publication, ID and notes plus the Git ref/zero-to-four annotated-tag chain/commit, bracketing the graph
with fresh release/ref reads. The immutable in-memory target retains the full bounded notes hash
and object chain. Revalidation compares that same exact target freshly, never substituting latest
or falling back after failure. Source observations are not remote locks/atomic snapshots, proof
source builds the expected package or consent to mutate. Tag movement after revalidation remains
a risk requiring actual installed-commit verification at the later replacement gate.

Isolated stdlib HTTP children have an **eight-second total diagnostic budget** (including source-
lock wait), 128 KiB responses, no redirects/authentication or ambient token/proxy/loader/site/index
settings. No Git/pipx execution, Python switch or installer. The source path reuses only the GitHub
source guard/rate-limit parser, with a separate durable disposable attempt-before-request claim
containing no target, grant, install/recovery state. Source success/failure does not overwrite
latest-release success/daily attempts. Both paths honor Retry-After/rate-reset; unsupported safe
storage refuses without repair. No scheduling or source lock across mutation. Independent future
installation/network/proxy/index consent is not inferred from the source child's minimal environment.

Failure trail retained: missing API reproducer **1 failed**, .02 s. First focused **2 failed/142
passed**, 15.08 s (inconsistent shared test tag-OID payload and static exception type), then lowest
3.14 source/release/terminal/quality **188 passed**, 27.58 s. Preflight **1 prose-reference failure/
202 passed**, 17.62 s (a slash in CHANGELOG looked like an internal path); reworded, guard unchanged.
Initial complete primary suite **1 lint failure/1958 passed/84 skips**, 265.47 s (nested test context
style); no other preliminary full combination run. After context-only correction focused
source/quality **113 passed**, 12.28 s. **All four complete suites and the full affected real gate
then passed on final frozen source/checker/test inputs** above. No test assertion weakened or
failure suppressed. First real installed proof **2 tests/264 checks passed**, 76.83 s; final real
gate includes all final changes. No real OpenCode manager replacement or recovery is claimed.

Evidence `.work/up17a/verified-*.xml`, `real-final.xml`, `final-source-sha256.json`, separate failed/
focused inputs/logs and `.work/logs/up17a-*`. No human/manual observation, broad complete campaign,
privileged/socket/service/daemon change, paid API/real provider credential, public network-source
authentication, release-readiness or UP-17 completion claim. Version, schemas, image assets,
dependency bounds, CLI/TUI, startup/leases, frozen helper/verifier/terminal protocol and CI/release
workflows unchanged; distribution content validation additionally requires the new source module.
No version bump, merge, push, upload, remote change, project tag or publication.

Final follow-up: no-isolation sdist/wheel, strict twine/content validation and **42 frozen product
module/wheel byte comparisons pass**; private local instructions/evidence absent from sdist.
Documentation/CLI/quality first follow-up **1 prose-reference failure/42 passed**, 3.43 s (another
slash ambiguity in this record), reworded without changing the guard; corrected **43 passed**,
3.24 s (`docs-final.xml`), explicitly focused rather than another complete regression. Guarded
cleanup removed **14 exact manifested completed pytest roots**, after own-UID/inode/live-process/
socket/mount checks; **480 host fixture records/artifacts** archived before removal. All real
source-target evidence, staged helper/results, pty captures, failed/pass XML/logs/hashes/packages,
prior evidence, shared build cache and persistent protocol inodes retained. `/tmp/opencode` empty,
**1046485 free inodes**. Only exact owned scratch removed; original four image IDs unchanged and
no owned process/container/volume/test-tag leaks. Prose-only scratch separately manifested/guarded.
No product/checker/test changes followed the final complete/real gates. UP-17 remains partial;
the next package is installation/tool/network consent and independent exclusive revalidation,
then separately proven replacement/expected-result and failure recovery. Manager Update disabled.
Final prose language/link/CLI follow-up **27 passed**, 1.96 s (`prose.xml`), separately scoped;
the final complete/real product/checker/test hashes remain intact.

### Unpublished UP-16 final terminal-handoff checkpoint — 2026-11-01

| Layer | Result |
|---|---|
| Complete unit/host/pilot/host-pty suites | **1861 passed, 84 opt-in skips each**, Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0. Serial foreground, clean pip checks/inode preflight, **253.43/248.04/256.13/249.14 s**, all **1945 ordered IDs/outcomes identical**; only two known lowest-Typer warnings |
| New default cases | **39 cases**: UI-thread, active operation/session, open screen/consent and stale/foreign request refusals; actual canceled-live worker tracking, sealed/queued admission and body-finally cleanup; configuration recovery retains app ownership through Close; no launch on request alone, abnormal CLI return and failed restoration/arming, exact tty snapshot changes without repair. Six host real-pty cases cover 80x24/120x40 implicit/explicit entry, restored modes and visual teardown before handoff output, main return/shutdown drain versus actual process death, changed modes, canceled/live worker refusal and ordinary quit without implicit reuse |
| Affected real Docker/OpenCode/pipx/pty | **29 tests/872 logged checks**, no skips/deselections, `up16e-verified`, **1183.76 s**. All previous 29 rows/assertions retained. Both actual installed default/custom-space pipx layouts pass seven added terminal scenarios each: implicit/explicit sizes, non-daemon drain, live/canceled worker then actual Debian/Arch start, actual attached Docker shell client, changed real tty modes, and second installed dashboard busy refusal. Fixed fresh verifier works after genuine terminal restoration and origin exit; original installation/records/launcher unchanged and operational |
| Boundary | **UP-16 complete for non-mutating handoff**, not an updater. No public key/button/command/env trigger, source/target/install payload, ordinary-startup bypass, early usage release, exclusive descriptor export or automatic restart. Manager Update stays disabled until separately verified UP-17 consent/replacement/expected-result and failure recovery. No human/manual observation or release-readiness claim |

The CLI uses one dashboard exit boundary. It observes original streams/foreground tty identity/
exact termios before entry; after matching clean zero-code App.run result and full supported local
Linux driver/input/output shutdown, validates exact restoration without repair, flushes the plain
non-mutating notice, launches the existing independent helper, rechecks and arms it. Failure cancels/
reaps the exact started helper. Unsupported tty observation/custom/headless/inline drivers cannot
arm the fixture but ordinary dashboard use is unchanged. Active work is not canceled to force
handoff. A mutex-protected app-local barrier counts actual bodies and refuses queued/live workers;
after sealing no late canceled thread can enter application work. Configuration recovery remains
app-owned. Explicit attached-session lifetime covers suspend/interactive/resume/finally, rather than
the old pending-operation flag that was false during a session. None of these app-local facts grants
installation exclusion: the originating usage lease persists through actual process exit, and the
existing pidfd/non-waiting helper protocol remains unchanged. No frozen helper/verifier/lock code change.

This cycle's failure/feedback trail and exact commands are in the working record. First real
installed proof **2 failed**, 97.52 s, and second **2 failed**, 38.41 s: isolated HOME hid the rootless
context store, and identity correctly refused. The first fixture lacked continuous pty draining/
explicit worker-error evidence; added both and removed duplicate inherited mount dispatch. Retain
read-only DOCKER_CONFIG as in the existing pipx lifecycle row; no context/default/identity/credential
copied or changed. Corrected real proof **2 passed/248 checks**, 75.36 s. First complete checkpoint
**1861/84 skips each** (257.21/248.81/254.04/255.94 s), real **29/872**, 1013.47 s. Review then made
the optional host-pty renderer check explicit and isolated its import-path setup; no assertion,
deadline or product code changed. **All four complete suites and all 29 real rows reran** above on
final frozen source/test inputs. Host renderer absence is an explicit optional skip, never used in
these gates; real-campaign configuration requires it. No failed product assertion suppressed.

Evidence `.work/up16e/verified-*.xml`, `real-verified.xml`, `final-source-sha256.json`; prior passes/
failures retained separately. Installed real fixtures use declared private Git source transport,
not public source/release authenticity. Test-only F9 injection calls the internal method through
actual CLI/App/driver/terminal/lease/helper/verifier code; host-only diagnostics are disabled only
in the host-pty layer, while installed real tests use actual diagnostics/clients/operations. All
default/cross-layer security, rootless identity, diagnostics, lifecycle/journals/recovery, Git,
backup, cleanup, pins, discovery and terminal assertions remain intact. Manager version/schemas,
assets/dependencies, launcher, installation locks, frozen helper/verifier and CI/release workflows
unchanged. No broad legacy TUI, privileged/socket/service/daemon change, real credential/provider/
paid API, complete campaign, actual replacement/failure recovery or release-readiness claim.

Final no-isolation sdist/wheel, strict twine/content validation and eleven frozen product-file/
wheel byte comparisons pass; private local instructions/evidence absent from sdist. Documentation/
CLI/quality follow-up **43 passed**, 3.35 s, not another complete suite. Own-rootless final inventory
matches all original four full image IDs, no containers/volumes/test tags or owned manager/helper/
verifier/terminal/probe/guard/watchdog Python processes. Guarded removal of **21 exact manifested
completed pytest roots**, own-UID/inode/live-process/socket/mount checked; **960 host fixture
records/artifacts** archived separately before cleanup. `/tmp/opencode` empty, **1046809 free inodes**.
All real staged helper/results, pty bytes, failed/pass XML/logs/source hashes/package artifacts,
prior evidence, shared build cache and persistent protocol inodes retained. Only exact owned
scratch removed; no user data/install/launcher/credentials, host context/service or original image
changed. Prose follow-up scratch separately manifested/guarded. No bump/merge/push/upload/remote
change/project tag/publication, and no product/checker/test change after final complete/real gates.
Final prose language/link/CLI follow-up: **27 passed**, 2.06 s (`prose.xml`), separately scoped;
final documentation-bearing package retained under `.work/up16e/package-final/`.

### Unpublished UP-16 fourth verifier-access checkpoint — 2026-10-31

| Layer | Result |
|---|---|
| Complete unit/host/pilot suites | **1822 passed, 84 opt-in skips each**, Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0. Four clean pip checks; serial foreground, 245.63/239.45/243.72/239.39 s. All **1906 ordered IDs/outcomes identical**; only two known lowest-Typer deprecations |
| New default regressions | **59 cases**: 54 real host/process verifier cases, four procfs-observation helper cases and one required-module package gate. Unlocked O_RDONLY/CLOEXEC witness, matching private inode and live owner's exact kernel FLOCK proof; shared/unheld/POSIX/wrong-owner/prefix/replaced-inode refusal, fork/exec hygiene, reverse order, no ordinary entry-point bypass even with a deliberately inherited real guard or fake environment flags. Fixed dedicated entry, nonce/message-credential/FD-shape refusal, unexpected descriptor closure, no credential/data-directory work, close-before-query and changed-record preservation. Actual runtime query, failure/timeout/interruption and early descendant retention proof; minimal no-pip CPython fixtures are not pipx provenance evidence |
| Affected real Docker/OpenCode/pipx/terminal | **29 tests/762 checks passed**, no skips/deselections, `up16d-final`, 996.24 s. All prior 29 rows/assertions retained. Actual default/custom-space pipx installs freeze the helper from installed source and observe version/prefix/module through the dedicated fresh process under exclusion. Normal launcher still refuses. A real early target-site hook spawns a manifested descendant; kill/reap helper/direct verifier, prove exclusion free while the descendant still lives, then terminate/reap it. Original installation/record/executable remains unchanged and operational; no automatic restart |
| Boundary | **UP-16 remains partial**. No normal CLI exemption, public verifier command, CLI/TUI/startup consumer, restored-terminal handoff or installation path. Only observed runtime facts, not expected source/commit/launcher/basic-CLI health, replacement success or recovery. Manager Update stays disabled. Usable Linux pidfds, live peer proc fdinfo and parent-death protection required for this internal fixture; no unsafe fallback or new ordinary-startup requirement |

The fixed external bootstrap sets parent-death protection before target Python site initialization,
then execs only the target venv's existing Python/dedicated module. It inherits an **independent,
unlocked read-only witness**, never the helper's exclusive description. Both bootstrap and client
check the live peer's exact exclusive fdinfo/inode; private pidfd/nonce and kernel message
credentials bind owner and actual responder. Client closes witness before reading version/prefix/
module; no CLI/core/Docker/config/discovery import or generic command/callback. Owner retains
exclusion through successful fresh exit/result and reserved-group cleanup/reap. Query budget is
eight seconds/4096-byte messages, further limited by remaining fixture time, not installation or
build timing. Raw streams/environment/nonce are not persisted. Fixed-source code is trusted local
tooling, not a sandbox, public authenticity attestation or guarantee to stop escaped site-hook work.

Failure trail: missing-capability reproducer **1 failed**, 0.02 s. Initial selected **2 failed/141
passed**, 17.28 s (replaced inode also correctly refused on context exit; two test imports). Lowest
selected **179 passed**, 17.83 s; extended **224 passed**, 20.29 s; early real **2 passed/134 checks**,
53.53 s. Review then exposed a flaw in the first uncommitted locked-descriptor design: an early site
descendant could retain exclusion after helper death. Real-process reproducer **1 failed/44
unrelated cases deselected**, 0.30 s. **Kept it unchanged**, replaced descriptor export with an
unlocked witness/live peer proof and kernel responder credentials. Post-fix **161 passed**, 17.75 s;
actual pipx proof **2 passed/138 checks**, 50.22 s. Final Python 3.14 focused **237 passed**, 24.04 s.

First complete attempt: **1818/84 skips** on both 3.11 variants and 3.14/current (246.50/241.36/
244.62 s); 3.14/lowest **1 failed/1817 passed/84 skips**, 239.63 s. Existing diagnostic helper read
procfs while an owned task disappeared and raised ESRCH/ProcessLookupError, not ENOENT. Deterministic
reproducer **1 failed/3 passed/49 unrelated cases deselected**, .06 s. Handle only those two
disappearance errors; explicitly retain PermissionError failure and live-process negative checks.
All real termination/reaping assertions, signal/deadline/output bounds remain unchanged. Lowest
3.14 affected **223 passed**, 22.97 s, then **all four complete suites and all 29 real rows rerun**
above. Original `final-*` failure evidence remains separate from corrected `verified-*`; no failure
waived, assertion relaxed or focused selection promoted as complete verification.

Evidence/hashes/XML under `.work/up16d/`; real manifests/commands/checks under `.work/logs/up16d-*`.
Four changed/new product modules, unchanged bundled path probe, checker and final test-helper/
fixture sources frozen before final gates (`final-source-sha256.json`). The stricter test teardown
asserts no leaked witness set rather than clearing it. CLI/launcher/TUI/core, daemon identity,
discovery/cache, lifecycle/journals/recovery, manager version/schemas, assets, dependency bounds
and CI/release workflows unchanged. All real attempts isolated and guarded-cleaned; final own-
rootless inventory has no containers/volumes/test tags and exactly the original four full image
IDs. All deliberately spawned helpers/verifiers/descendants explicitly reaped; no user install,
launcher, Python, credentials, services or default context changed. Private fixture Git tags/
transport are not public release authentication. Persistent protocol inodes, evidence and build
cache preserved. No complete campaign, optional installed-asset build, broad legacy TUI,
privileged/socket/service, human observation, restored-terminal handoff/replacement/recovery or
release-readiness claim. No bump, merge, push, upload, project tag, remote change or publication.

Final no-isolation sdist/wheel, strict twine/content validation and five product-file byte equality
against frozen complete/real source and wheel pass; no private instructions/evidence in sdist.
Final document/CLI/quality subset **43 passed**, 3.20 s, not another complete run. No remaining
manager/helper/verifier/probe/guard/watchdog Python process found. Guarded cleanup removed only
**21 exact manifested completed pytest roots** after own-UID/inode/process/socket/mount checks;
`/tmp/opencode` empty with **1047461 free inodes**. Real helper/results, failed/pass XML/logs,
source hashes/artifacts, prior evidence and build cache retained. Added fixed-namespace protocol
inodes are intentional persistent state. Prose-only follow-up scratch is separately manifested/
guarded; no product/checker/test-helper change after final complete/real gates.
Prose-only language/link/CLI follow-up: **27 passed**, 1.84 s (`prose.xml`), not another complete
regression. Final documentation-bearing package retained separately.

### Unpublished UP-16 third artifact/lifetime checkpoint — 2026-10-31

| Layer | Result |
|---|---|
| Complete unit/host/pilot suites | **1763 passed, 84 opt-in skips in each of four serial foreground runs**: Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0. Clean pip checks; 238.53/232.91/242.52/232.26 s. All **1847 ordered IDs/outcomes identical**; only two known lowest-Typer deprecations |
| New default regressions | **61 cases**: 59 actual host/process helper cases plus two package-content gates. Private deterministic source-identical zipapp, controlled/outside staging, changed bytes/inodes/permissions/records and unfamiliar-file preservation, fork ownership, single use, reverse lock order, pidfd requirement, descriptor/environment isolation, fixed protocol and no generic dispatch. Real cancellation/expiry/EOF/spawn signals/readiness failure/reaping, main-return/non-daemon/thread-pool shutdown, normal/killed armed/unarmed origin and another live shared instance. Synthetic tool metadata remains distinct from actual installed-package evidence |
| Affected real Docker/OpenCode/pipx/terminal | **29 tests/732 checks passed**, no skips/deselections, `up16c-verified`, 1032.84 s. All earlier 29 rows/assertions retained. Both actual pipx layouts freeze the helper from the installed package, retain the origin's lease during non-daemon shutdown, hide only that owned application venv, exit the origin and prove the external frozen helper acquires exclusion while the target is absent. Exact helper child adopted/reaped, original venv always restored before uninstall; installed records/executable unchanged |
| Scope and limits | **UP-16 remains partial**. Internal non-mutating fixture only; no CLI/TUI/startup consumer, fresh-verifier bypass, restored-terminal handoff, replacement, recovery or automatic restart. Fixed private seqpacket/pidfd/directory descriptors; no inherited installation guard, terminal or credentials. Usable Linux pidfds required with no PID/EOF fallback. Fixture arming—even followed by SIGKILL—is not installation consent or proof of terminal restoration. Manager Update remains disabled |

`manager_handoff.prepare()` freshly reuses the existing conservative external-tool assessment,
then materializes private source copies outside the replaceable prefix. `manager_helper.py` is
the zipapp entry alongside unchanged installation-lock and path-probe source; only the latter's
stdlib route primitive is imported, not its optional pipx diagnostic main. The artifact runs with
external Python `-I -B -S`, no installed package/dependency imports, and checks its local hash,
ownership/runtime/routes and control peer/pidfd. The originating process retains its ordinary
usage lease until exit. EOF/main return cannot establish quiescence; only actual process death
allows one non-waiting exclusive attempt, followed by a bounded private fixture result and exit.
No lock conversion, retry loop, shell, pipx command, Docker, network or generic executor is added.
The maximum 30-second fixture budget and eight-second readiness/request bound are not future
installation deadlines. Partial/changed/unfamiliar artifacts remain preserved; explicit discard
refuses a live helper. Test-only subreapers supervise exact children without signalling reaped PIDs.

Failure trail is retained in `.work/up16c/`: absent-module reproducer collection error; first helper
feedback stopped at **1 failed/31 passed** plus KeyboardInterrupt (new AST import-boundary assertion
and a test Popen wrapper still intercepting its later exclusion check). Next selected **4 failed/
141 passed**, 11.76 s: three origin fixtures used `input()` with communicate's EOF, plus import/
fixture-alias lint. Corrected test driving/imports, preserving the actual exit/reap/independence
assertions. Lowest selected **145 passed**, 12.22 s; expanded helper/static **70 passed**, 10.05 s;
package/helper/static **91 passed**, 10.16 s. First real proof **2 passed/108 checks**, 50.21 s.

The first complete matrix passed **1761/84 skips each** (238.63/234.82/242.35/235.69 s) and the first
affected real gate passed **29/732**, 1022.21 s. Final review then added huge-integer budget tests:
**2 failed/57 unrelated cases deselected**, 0.32 s. `math.isfinite` converted a bounded-wire but
large JSON integer to float and raised OverflowError instead of static refusal. Check the numeric
range directly, which also rejects NaN/infinity without conversion; kept both assertions unchanged.
Python 3.14 affected **182 passed**, 16.68 s, then **all four complete suites and all 29 real rows
reran** on corrected code above. Original `final-*`/`real-final.xml` and pre-budget-fix source
hashes remain separate from final `verified-*`/`real-verified.xml`; no earlier result promoted.

Two new product modules and the packaging checker are frozen with the unchanged bundled lock/
probe/tool sources in `.work/up16c/final-source-sha256.json`. CLI/launcher/TUI, installation lease
implementation, external-tool assessment, caches/discovery, lifecycle/identity/journals, version,
schemas, assets, dependency bounds and CI/release workflows remain unchanged from the prior
checkpoint. `.work/logs/up16c-*` retains manifests/commands/checks, including actual private tagged
Git transport fixtures (not public release authentication). Final own-rootless inventory: no
containers/volumes/test tags; original four full image IDs unchanged. All installed test managers
uninstalled, hidden venvs restored, helper processes explicitly reaped. No user install/launcher/
Python/credential or host service changed; persistent lock inodes, prior evidence and build cache
preserved. No complete campaign, optional installed-asset build, broad legacy TUI, privileged/
socket/service, human observation, helper terminal-handoff/replacement or release-readiness claim.
No version bump, merge, push, upload, remote change, project tag or publication.

Final no-isolation sdist/wheel build, strict twine/content checks and equality of all five bundled/
orchestrating product sources with frozen full/real hashes and wheel bytes pass. Private local
instructions/evidence absent from the sdist. Final document/CLI/quality subset **43 passed**,
3.25 s, not another complete regression. No remaining manager/helper/probe/guard/watchdog Python
process found. Guarded removal of only **19 exact manifested completed pytest roots**, checked
for own UID/inodes and no live process/socket/mount reference, left `/tmp/opencode` empty with
**1048170 free inodes**. All private staged real helper artifacts/results, failed/pass XML/logs,
source hashes, package artifacts, prior evidence and build cache remain; added fixed-namespace
protocol inodes are intentional persistent state, not stale cleanup candidates. Final prose-only
scratch is separately manifested/guarded after its run; no product/checker changes after the final
complete/real gates.
Prose-only language/link/CLI follow-up: **27 passed**, 1.86 s (`prose.xml`), distinct from complete
regression and real evidence. Final documentation-bearing package is retained separately.

### Unpublished UP-16 second trust checkpoint — 2026-10-31

| Layer | Result |
|---|---|
| Complete unit/host/pilot suites | **1702 passed, 84 opt-in skips in each of four serial foreground runs**, Python 3.11.18/3.14.8 × current Typer 0.27.3/Textual 8.2.8 and lowest 0.16.0/4.0.0; clean pip checks. 227.97/227.03/227.23/223.80 s. All **1786 ordered IDs/outcomes identical**; only two known lowest-Typer deprecations |
| New default regressions | **47 new cases**: 45 external-tool host/process cases and two package-content gates. Actual isolated child execution with synthetic pipx packages/metadata, standard/space/symlink scripts, exact source-Python selection, effective paths, target absence, dependency/search/import and whole-symlink-route independence, declared missing/lazy files, raw RECORD size/shape, unsafe paths and unsupported versions/settings. Dummy-secret environment/output non-disclosure; owned child timeout/output/cancel reaping and changed-tool refusal. These synthetic package cases are not substituted for real pipx evidence |
| Affected real Docker/OpenCode/pipx/terminal | **29 tests/714 logged checks passed**, no skips/deselections, `up16b-final`, 1222.86 s. All prior 29 rows rerun, including pipx lifecycle, shared/exclusive startup/session/exec/base-mutation coordination and 80x24/larger terminals. Actual external test-venv pipx 1.18.7/Python/dependencies preserve classified default/custom-space home/bin/man and the exact recorded source-interpreter selection. Probes still work with the run-owned application venv temporarily absent; an in-target pipx console copy is refused even with an external shebang. App records/executable bytes remain unchanged; hidden venvs always restored, owned installs uninstalled |
| Boundaries | **UP-16 remains partial**. The new API is internal in-memory prerequisite evidence, not called by startup/status/discovery/UI, not a user command or durable grant. Only inspected pipx 1.18.7 with recognized standard console scripts and filesystem dist-info RECORD inventories is supported; unsupported cases get manual guidance. Existing external code is trusted local tooling, not sandboxed/authenticated by the probe. No independent helper artifact/lifetime transfer, verifier bypass, restored-terminal handoff, manager replacement/recovery or automatic restart exists; Manager Update stays disabled |

The standalone source is sent in memory to an external interpreter, first `-I -B -S` for stdlib
identity, then `-I -B` for only the recognized pipx `--version` path. Imports/search/declared dependency
inventories and effective settings must be outside the replaceable prefix; exact source-Python
spelling and every symlink-route component are preserved/checked. External script/interpreter
identity is reread. Only explicit recognized settings, HOME/PATH and fixed locale/no-bytecode
controls are forwarded; raw pip/index/proxy/provider/loader/Python environment is not. No list,
install, metadata normalization, tool/Python installation or switch, Docker, cache/state write or
network discovery is added. Existing diagnostic runner owns the eight-second/128 KiB **per-child**
budget and process-group cleanup; long mutation/session timing is unchanged. Strict package
validation now also requires both prerequisite modules; prior gates remain and no workflow changed.

Failure trail: missing-module reproducer failed collection; a direct ruff check caught an import
style issue, corrected without a waiver. Early **33 passed**, 2.04 s; lowest affected **124 passed**,
4.47 s; early real proof **2 passed/90 checks**, 47.85 s. Additional route/permission regressions
then **129 passed**, 4.65 s. Two source-Python regressions deliberately **failed** (0.33 s, 38
unrelated cases deselected only for this reproducer): early canonicalization substituted a binary
endpoint and erased an alias through the target. Preserve the requested path, validate its full
route, and compare the observed canonical endpoint separately. Lowest extended **152 passed**,
5.09 s, with only known deprecations.

The first complete attempt passed **1699/84 skips** on both 3.11 variants (228.02/222.54 s), but
Python 3.14 had **1 failed/1698 passed/84 skips**, 227.40 s; the fourth run was not started. CPython
3.14's `Distribution.files` filters missing RECORD entries and hid a declared target-dependent
lazy path. Kept the assertion/fixture unchanged and read bounded unfiltered filesystem dist-info
CSV RECORD instead: 512 KiB/8192 rows per distribution, 64 distributions/16384 rows overall;
unknown formats refuse. Added three malformed/empty/oversized inventory cases. Python 3.14
focused **80 passed**, 4.72 s, then reran **all four complete suites** above on corrected source.
Earlier failed/pass XML/logs/hashes remain as `.work/up16b/pre-record-fix-*`; none was overwritten
or promoted as final evidence. No failed assertion was weakened, skipped or suppressed.

Final XML/hashes/inventory under `.work/up16b/`, manifests/commands/check logs `.work/logs/up16b-*`.
Two new product modules and the packaging checker frozen before final complete/real gates; CLI,
TUI, core/lifecycle/identity, startup/base/source locks, discovery/cache, schemas, manager version,
assets, dependency bounds and CI/release workflows unchanged from the first UP-16 checkpoint.
Both real attempts used isolated run-owned installs/data/config/source/launcher paths, manifested
temporary venv hiding/restoration and exact scratch cleanup, product uninstall/cleanup and leak
guards. Final own-rootless inventory has no containers/volumes/test tags; all four original image
IDs unchanged. Prior evidence, persistent protocol inodes and build cache are preserved. No user
installation/launcher/Python, real credential, public API or paid-provider use; no complete campaign,
optional installed-asset build, broad legacy TUI, privileged/socket/service, human observation,
helper/handoff/replacement or release-readiness claim. No bump/merge/push/tag/upload/publication.

Final package build, strict twine/content validation and byte equality of both new product modules
with frozen complete/real source and wheel bytes pass; no private instructions/evidence in the
sdist. Final document/CLI/quality subset **43 passed**, 3.25 s (`docs.xml`), not another complete
run. No remaining manager/probe/guard/watchdog Python process found. Guarded cleanup removed only
**16 exact manifested completed pytest roots**, with own-UID/inode/process/socket/mount checks;
`/tmp/opencode` empty, **1048524 free inodes**. Additional intentional installation-lock inodes
remain persistent protocol state. Logs/XML/failed-attempt evidence/private fixtures/artifacts/
build cache/prior records are preserved. Final prose-only scratch is separately manifested and
guarded after its run; no product/checker change followed the final full/real gates.

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

Checkpoint commands remain in Git; logs/XML are ignored
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
- Actual post-reboot manager recovery after hard helper death (CAMPAIGN B15): same-boot unknown-
  quiescence refusal is verified, but reboot was not authorized/executed and risk is not accepted.
  Next step is the named disposable-operation reboot/frozen-verify continuation in CAMPAIGN;
  never delete state/locks or treat a vanished old group/cache/exit status as completion.
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
| `TODO.md` | Completed unpublished Updates scope, what 6.1.0 delivered, optional polish and deferred features |
| `docs/engineering/BASELINE.md` | This file: current state |
| `docs/engineering/ARCHITECTURE.md` | Current design and module map |
| `docs/engineering/DECISIONS.md` | Decisions D-001..D-057 with rationale and implementation status |
| `docs/engineering/ISSUES.md` | Known issues and accepted limitations |
| `docs/engineering/CAMPAIGN.md` | Release test matrix: 87 active rows, seven installer-only rows retired; historical evidence distinguished from pending release gates, including unapproved post-reboot manager recovery |
| `docs/engineering/RELEASING.md` | Release checklist and tag procedure |
