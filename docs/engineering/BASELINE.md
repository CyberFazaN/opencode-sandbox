# Baseline — OpenCode Sandbox 6.2.0

Current checkout state and applicable recorded evidence, not a development diary. Commands and
test-selection policy: [CONTRIBUTING](../../CONTRIBUTING.md#verification-policy). Design:
[ARCHITECTURE](ARCHITECTURE.md). Release gates: [CAMPAIGN](CAMPAIGN.md) and [RELEASING](RELEASING.md).
The current checkpoint below records fresh verification; older sections retain their stated scope.

## Version

| Item | Current state |
|---|---|
| Manager | `6.2.0`, Beta; source: `src/opencode_sandbox/__init__.py` |
| Branches | `main`: published stable source/docs; `develop`: unreleased changes (D-058) |
| Distribution | MIT `opencode-sandbox`; pipx from versioned GitHub tags, no package index |
| Schemas | Environment metadata 2, backup 3; other schema versions are refused, never migrated/deleted |
| Images | Debian 13/default (`node:24-trixie`, revision 2); Arch rolling (`archlinux:base-devel`, revision 1) |

The release includes component Updates views, optional default-off daily discovery,
environment/base actions and independent manager update/recovery. These are implemented, not a
pending roadmap. Schemas and image definitions have not changed. Availability,
consent, mutation and recovery remain separate; no Update All or automatic manager restart/rollback.
The owner accepted B15's unverified post-reboot recovery risk for 6.2.0 on 2026-11-02 and explicitly
declined a reboot. Acceptance is not verification; original frozen recovery inputs remain retained.

## Supported environments

- Intended host: Linux meeting [the prerequisites](../install.md#requirements); real Docker/OpenCode
  evidence is on Arch Linux only. Tested kernel 7.2.11, Git 2.56.0, own rootless Docker 29.9.2,
  RootlessKit 3.3.0/slirp4netns, overlayfs/containerd image store, cgroup v2 with CPU/memory/PIDs
  delegated by systemd 262. Foreign/rootful/remote daemons and socket proxies are refused.
- Python >=3.11: local 3.11.18 and 3.14.8; 3.12/3.13 accepted, not tested separately. Stable hosted
  CI used Ubuntu 26.04, Python 3.11.17/3.14.9, plus an unprivileged rolling Arch userland job.
- Python 3.15 is stable ([upstream status](https://devguide.python.org/versions/)) and accepted by
  the declared range, but not qualified here. The explicit CI endpoint remains 3.14 pending
  current/lowest, installed-package/process verification and review of the required-check transition.
- Current Typer/Textual 0.27.3/8.2.8; lowest direct versions 0.16.0/4.0.0. Test environment:
  pytest 9.2.0, pyte 0.8.2, Ruff 0.17.3, shellcheck 0.11.0; pipx 1.18.7.
- OpenCode `@opencode/cli` 2.x only, tested 2.1.4 and 2.2.0 on both image distributions.

## Verification

### Published 6.2.0

[6.2.0](https://github.com/CyberFazaN/opencode-sandbox/releases/tag/v6.2.0) was published on
2026-11-02 as the latest stable GitHub release (not a draft or prerelease, no binary assets).
Annotated `v6.2.0` targets protected [PR #3](https://github.com/CyberFazaN/opencode-sandbox/pull/3)
merge commit `e343e35c1aff2d7d6e2754427abc960f3821bb47`; its product/test bytes match the
qualification below. All ten [final PR checks](https://github.com/CyberFazaN/opencode-sandbox/actions/runs/41470002579)
and ten [main checks](https://github.com/CyberFazaN/opencode-sandbox/actions/runs/41471779232)
passed. All 14 [release-workflow jobs](https://github.com/CyberFazaN/opencode-sandbox/actions/runs/41473435213)
passed, including both Python tag installations, before review/publication of the automated draft.
Published notes match CHANGELOG; no package-index or container-image upload was performed.

Fresh **public GitHub-tag** pipx installations on Python 3.11.18 and 3.14.8 passed version/help,
installed-asset and missing-context checks, and actual rootless `doctor` (exit 0). PEP 610 records
identify the official source/tag/merge commit; all **63 installed product files** match the tag,
with no test hooks. Doctor verified the user's own rootless daemon and reported the expected older
retained Debian-base revision warning; neither existing base was rebuilt. This is installation
proof, not real public-network manager self-replacement, reboot recovery or a production-readiness
claim. B15 remains BLOCKED with the owner's accepted risk.

### 6.2.0 candidate qualification

Local candidate qualification on 2026-11-02, from the approved `develop` tree. Detailed commands,
input hashes, failed/pass XML, package comparisons and scan reviews are under ignored
`.work/agents/release-6.2.0/`; real manifests/logs are `.work/logs/r62a*`, `r62b*` and `r62c*`.

| Layer | Executed result and scope |
|---|---|
| Complete default suite, Python 3.11/lowest direct | **2205 passed / 86 real opt-in skips**, 331.12 s |
| Complete default suite, Python 3.11/current | **2205 passed / 86 real opt-in skips**, 342.55 s |
| Complete default suite, Python 3.14/lowest direct | **2205 passed / 86 real opt-in skips**, 352.74 s |
| Complete default suite, Python 3.14/current | **2205 passed / 86 real opt-in skips**, 358.18 s |
| Packaging and installed pipx | Both endpoints: isolated sdist/wheel build, strict twine/content checks, fresh private-tag pipx install/help/version/doctor; all **63 product files** match the candidate source |
| Complete real installed-manager campaign | `r62b`: **86 tests / 1643 checks passed**, 0 failures/errors/skips, 2115.33 s; both distributions, retained Debian 12, packaged/cached/full-refresh builds, real OpenCode/fake-provider first prompts, terminals, native manager replacement/recovery, privileged and isolated socket-activation rows |
| Python 3.11 installed-manager floor | `r62c`: **7 tests / 563 checks passed**, 0 failures/errors/skips, 337.96 s; actual pipx lifecycle, both-layout native manager update/recovery and both-distribution session exclusion, not a second complete campaign |
| Static and privacy | Ruff/shellcheck and four dependency checks pass; actionlint/offline zizmor pass with existing exceptions. Gitleaks history/tree: 0 findings; offline detect-secrets: 11 reviewed deliberate test fixtures, no real secret identified; personal-data candidates reviewed |

The matrix uses the selected existing endpoint venvs, not a claim of four fresh resolutions.
Fresh pipx installations resolved Typer 0.27.3/Textual 8.2.8, matching the current matrix. Lowest
Typer emits two known Click deprecations. The Python 3.14 real harness emits 91 multi-threaded
`forkpty` deprecation warnings; these were not suppressed or treated as application failures.

Version preparation exposed synthetic fixtures tied to the checkout's 6.1.0 version; they now use
explicit consistent old/new identities or genuinely newer targets. The initial complete real run
`r62a` recorded 86 completed bodies but four teardown errors from six failed checks: one negative
source fixture advertised the wrong tag, and session exclusion checked the runner's prefix rather
than the separate installed manager. Only fixtures were corrected, with an additional unrelated-
installation control; the fresh complete `r62b` run passed. No application safeguard was weakened.
The four default matrices/package checks precede those two integration-only corrections; their
production/unit inputs are unchanged. Later evidence-only edits receive focused document checks.

Guarded cleanup and final inventory checks restored the original four image tags/full IDs, with
no container/volume leaks. Only five manifested test tags and the created empty runtime unit
directory were removed. Persistent protocol locks and original frozen hard-interruption recovery
inputs remain. No reboot, real credential or paid-provider call was performed; the earlier real
OpenRouter observation is retained evidence only, not a new candidate result.

Hosted qualification supplements these local results: all ten jobs passed on the approved
`develop` tree and on [release PR #3](https://github.com/CyberFazaN/opencode-sandbox/pull/3)
([candidate CI](https://github.com/CyberFazaN/opencode-sandbox/actions/runs/41468038565)).
The owner authorized the protected merge, annotated tag and publication. CAMPAIGN I06's reviewed
decision is **READY WITH ACCEPTED RISKS**, retaining B15 as BLOCKED, not PASS. Evidence-only edits
do not change the qualified product/test bytes. The required final-tree PR, `main` and tag checks
and automated draft review subsequently passed as recorded above; this is not a
production-readiness claim.

### Test-quality checkpoint before 6.2.0 preparation

At this earlier checkpoint, application source, dependency declarations and image assets were
unchanged. The test-quality checkpoint strengthens behavioral/security oracles and fixture
isolation, consolidates duplicate coverage, and keeps the complete CI/release selections.
Local policy is in CONTRIBUTING; current
and minimum direct dependencies are resolved together with the project in CI, not a later downgrade.
Evidence: versions, final four XMLs, timing profile, mutation controls and removal-to-retained-test
rationale under ignored `.work/agents/`; real resource manifests and logs under `.work/logs/`.

| Layer | Executed result and scope |
|---|---|
| Complete default suite, Python 3.11/lowest direct | **2244 passed / 86 real opt-in skips**, 331.78 s |
| Complete default suite, Python 3.11/current | **2244 passed / 86 real opt-in skips**, 338.79 s |
| Complete default suite, Python 3.14/lowest direct | **2244 passed / 86 real opt-in skips**, 354.38 s |
| Complete default suite, Python 3.14/current | **2244 passed / 86 real opt-in skips**, 360.22 s; passive timing instrumentation only |
| Real Docker/security/backup | **1 test / 20 checks passed**, 14.91 s: real sessions, external-profile isolation and decompressed workspace/home backup canaries on the retained Debian base |
| Real Docker/diagnostics | **2 tests / 30 checks passed**, 13.08 s: retained Debian and Arch, deadlines, cancellation, missing tooling, owned helper cleanup and persistence |
| Failure-detection controls | Original restore-space test accepted compressed-size substitution; strengthened test rejects that, ignored reserve and exact-fit rejection (**3/3 targeted in-memory mutants**), not broad mutation coverage |
| Static/dependencies | Ruff/shellcheck, actionlint, offline zizmor and four `pip check` results clean; existing lint exceptions and all mandatory jobs retained |

Commands used each endpoint venv's `python -B -m pytest -q -rs -p no:cacheprovider`, absolute source
PYTHONPATH, serial foreground execution, fresh short external basetemps and separate JUnit results.
Earlier failures exposed the real campaign inheriting unit fakes, path-sensitive socket/launcher
fixtures and a parked-installer EOF/parent-death race. They were investigated and corrected before
the final four passes; no retry waiver or relaxed signal/security assertion. Lowest Typer still
emits the two known Click deprecations. Product cleanup passed, original four full image IDs were
unchanged, and no current-run Docker resources leaked; persistent protocol lock inodes are retained.

Affected execution time (summed JUnit case phases, not full-suite wall time) fell **23.63 -> 6.79 s**
for 35 -> 28 cases with retained behavioral coverage. Total collection changed **2328 -> 2330**:
2242 -> 2244 default cases, the same 86 real cases. The final four suites total about **23.1 min**;
the normal local checkpoint pair takes **11.5 min**, not a CI/release reduction. Historical full
timings are not a controlled before/after benchmark. Global fixture setup is not a useful
optimization target (about 0.24 s combined in the primary profile).

Retained unchanged-package evidence: `.work/branch-migration-20261101/` passed both-endpoint
build/twine/content checks with 63 source-identical product files; `branch-migration-pipx-20261102`
passed the real installed-pipx lifecycle (1 test/21 checks, 40.92 s). These were not rerun for
test-only changes. The complete real release campaign, privileged/socket/reboot rows, real OpenCode
first prompts, fresh image builds and hosted CI were **not** renewed by this checkpoint. Final
record edits are documentation only, with focused document/contracts verification, not new runtime proof.

### Updates final integration

Applicable cross-layer evidence for the unreleased implementation: `.work/up18/` (final source
hashes, all failed/pass XML, reproducers and package proof), `.work/up17g/` (native updater proof)
and `.work/logs/up18-final*` (commands/manifests). Earlier intermediate checkpoint narratives are
in Git; they do not describe today's capabilities.

| Layer | Executed result and scope |
|---|---|
| Complete unit/host/pilot compatibility | **2220 passed / 86 opt-in skips** in each selected result; same 2306 ordered outcomes. Python 3.11/current 374.60 s, 3.11/lowest 365.27 s, 3.14/current 387.19 s, final 3.14/lowest 387.76 s; four clean dependency checks |
| Final correction and reruns | Initial 3.14/lowest: **2216 passed / 4 failed / 86 skipped**. Fixed an interruption-fixture partial PID marker with atomic readiness/owned-family cleanup, and a real base-plan bug by verifying the daemon before latest-version npm discovery. **124 affected tests passed at all four endpoints**; the failed complete combination then passed. Unchanged complete/real results were reused, not relabelled as reruns |
| Real Docker/OpenCode/terminal/pipx | **31 tests / 1146 checks passed**, no skips/deselections, 1381.67 s, `up18-final`: packaged/retained both-distribution races, bounded diagnostics, real binary/lifecycle evidence, 80x24/larger Updates/discovery/environment/base actions, cached/full-refresh builds, installed pipx and public manager replacement/recovery |
| Packaging/static | Sdist/wheel, strict twine/content checks passed; all 63 product files, including the 18-module frozen helper inventory, matched source. Ruff/shellcheck, actionlint, offline zizmor and tree/history secret scans passed. Focused final contracts: **83 passed** |

The real file set under `tests/integration/` was `test_42_base_coordination.py`,
`test_43_diagnostics.py`, `test_44_version_evidence.py`, `test_51_updates.py`,
`test_52_discovery.py`, `test_53_environment_updates.py`, `test_54_base_updates.py`,
`test_65_pipx.py`, `test_66_manager_inventory.py`, `test_67_installation_exclusion.py`,
`test_67_manager_update.py`, with `OCS_TEST_DOCKER=1 OCS_TEST_RUN=up18-final`.

Native manager evidence covers actual pipx force replacement in default/custom-space layouts,
Cancel-first public CLI/TUI, real terminal restoration and process-lifetime drain, exact expected
installed source/commit/version/launcher/runtime/CLI health, failed-health startup blocking,
manual previous-tag reinstall plus independent frozen recovery, handled interruption/escaped-child
cleanup, hard-kill same-boot refusal even with an empty old group, and lost-terminal durable results.
Private Git/loopback API transports are explicit fixtures, **not public-release authentication**
or a host build sandbox. Separate official HTTPS reads observed the published 6.1.0 graph; that
is not signed-code attestation or an actual public-network replacement test.

Guarded product cleanup passed; original image IDs were retained and no current-run containers,
volumes or owned processes leaked. Frozen recovery inputs, including the incomplete hard-kill
case, and persistent lock inodes remain. This was not the complete release campaign; no privileged,
socket-activation, reboot, paid-provider or manual-observation result was renewed.

### 6.1.0 release tree

Evidence on the release tree, 2026-10-30; relevant to retained behaviour only:

- **969 passed / 56 opt-in skips** in each of four Python/dependency suites; repeated in a fresh
  clone. Static/workflow checks, both-endpoint packaging and source-free pipx smoke passed.
- Full real campaign through an installed local test tag: **56 tests / 513 checks**, no failures
  or skips, 11 min 2 s. Both packaged images built into a test-only namespace; published 6.0.0
  supplied retained-Debian-12 compatibility. Privileged, socket-activation and installed-package
  build opt-ins were explicitly authorized. Both no-cache image builds also passed.
- One real OpenRouter `z-ai/glm-5.3-flash` session (Debian 13/OpenCode 2.2.0) received the base OS
  in its first prompt; 13 credential/terminal checks passed. Automated first-prompt tests use a
  fake provider on both images. Real credentials are not retained in evidence.
- Hosted release PR/main/tag CI passed all ten jobs, including the endpoint matrices, Arch
  userland, packaging, pipx and workflow lint. Public-tag pipx smoke passed on both local Python
  endpoints. The initial Arch CI isolation failure was fixed in tests before those passing runs.
- Pre-tag secret/personal-data scans passed with only deliberate dummy test values; cleanup left
  original image tags intact and no owned test resources. The host reboot was not executed.

The release decision accepted D09's reboot limitation. It does **not** accept B15's new manager
recovery risk or verify the later Updates implementation. Detailed release evidence is retained
in the tagged Git tree; [CAMPAIGN](CAMPAIGN.md) keeps the applicable row-level scope and limits.

## Unverified behaviour

- **B15 post-reboot manager recovery:** actual execution is unverified; the owner **accepted the
  release risk for 6.2.0 on 2026-11-02**, with no reboot authorized. Same-boot hard-interruption
  refusal passed at both Python endpoints; original frozen inputs are retained, not reset/deleted.
  On an explicitly authorized disposable VM, retain a named hard-interrupted operation and its
  original frozen recovery inputs, reboot, manually repair only if needed, run that frozen
  verifier and confirm startup/data retention. Never delete state/locks or infer success from an
  empty old group, cache or installer exit.
- **Host reboot generally (D09):** accepted at the stable release, not executed. Daemon restart,
  stop/start and daemon-unit SIGKILL passed. Next: authorized reboot, then `start NAME` and
  `check NAME` on a manifested test environment; do not equate this with B15's separate proof.
- Real rootless Docker on other Linux distributions, without systemd or without delegated
  controllers; other distributions' packaged socket-activation units. Provision a disposable host
  and run the affected/full campaign before claiming it tested.
- Another user's actual rootless dockerd: refusal was shown with another UID's socket, not a
  provisioned foreign rootless engine. Test only with separately authorized resources.
- pipx versions other than 1.18.7, Python 3.12/3.13/3.15 separately, Textual 4.0 in a real terminal,
  other terminal emulators, other real model providers and a real provider on Arch. Execute the
  corresponding installed/terminal/provider checks; mocks/pilots are not a substitute.
- Real public-network manager replacement, human observation, a kill inside `docker commit`,
  and scheduled GitHub image-build execution.
  Each needs fresh evidence; no passed development subset closes these gaps.
- Typer 0.16.0/Click 8.5 emits deprecations for helpers removed in Click 9. Keep the lowest-bound
  CI check; re-evaluate bounds when that version resolves, not by suppressing warnings/assertions.
- Performance beyond small recorded workspaces has no targets. Current complete suites were
  about 360–388 s; the older 1201-test timing is not a current benchmark.

Known limitations: [ISSUES](ISSUES.md); classified work: [TODO](../../TODO.md). No historical PASS,
focused result or mocked Docker run establishes release readiness on a changed candidate.
