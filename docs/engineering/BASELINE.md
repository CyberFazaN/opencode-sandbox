# Baseline — OpenCode Sandbox 6.1.0

Current checkout state and applicable recorded evidence, not a development diary. Commands and
test-selection policy: [CONTRIBUTING](../../CONTRIBUTING.md#verification-policy). Design:
[ARCHITECTURE](ARCHITECTURE.md). Release gates: [CAMPAIGN](CAMPAIGN.md) and [RELEASING](RELEASING.md).
The checks below predate this documentation cleanup; none is claimed as newly executed.

## Version

| Item | Current state |
|---|---|
| Manager | `6.1.0`, Beta; source: `src/opencode_sandbox/__init__.py` |
| Branches | `main`: published stable source/docs; `develop`: unreleased changes (D-058) |
| Distribution | MIT `opencode-sandbox`; pipx from versioned GitHub tags, no package index |
| Schemas | Environment metadata 2, backup 3; other schema versions are refused, never migrated/deleted |
| Images | Debian 13/default (`node:24-trixie`, revision 2); Arch rolling (`archlinux:base-devel`, revision 1) |

The checkout includes unreleased component Updates views, optional default-off daily discovery,
environment/base actions and independent manager update/recovery. These are implemented, not a
pending roadmap. Manager version, schemas and image definitions have not changed. Availability,
consent, mutation and recovery remain separate; no Update All or automatic manager restart/rollback.
No release recommendation follows: B15's post-reboot recovery risk is not accepted.

## Supported environments

- Intended host: Linux meeting [the prerequisites](../install.md#requirements); real Docker/OpenCode
  evidence is on Arch Linux only. Tested kernel 7.2.11, Git 2.56.0, own rootless Docker 29.9.2,
  RootlessKit 3.3.0/slirp4netns, overlayfs/containerd image store, cgroup v2 with CPU/memory/PIDs
  delegated by systemd 262. Foreign/rootful/remote daemons and socket proxies are refused.
- Python >=3.11: local 3.11.18 and 3.14.8; 3.12/3.13 accepted, not tested separately. Stable hosted
  CI used Ubuntu 26.04, Python 3.11.17/3.14.9, plus an unprivileged rolling Arch userland job.
- Current Typer/Textual 0.27.3/8.2.8; lowest direct versions 0.16.0/4.0.0. Test environment:
  pytest 9.2.0, pyte 0.8.2, Ruff 0.17.3, shellcheck 0.11.0; pipx 1.18.7.
- OpenCode `@opencode/cli` 2.x only, tested 2.1.4 and 2.2.0 on both image distributions.

## Verification

### Current code checkpoint — 2026-11-02

The branch-workflow change added three CI/release contract tests without changing application
source, dependencies or image assets. Evidence: `.work/branch-migration-20261101/` (XML, source
comparison, package proof and manifests) and `.work/logs/branch-migration-pipx-20261102*`.

| Layer | Executed result and scope |
|---|---|
| Complete default suite, Python 3.11/current | **2223 passed / 86 real opt-in skips**, 360.61 s |
| Complete default suite, Python 3.14/current | **2223 passed / 86 real opt-in skips**, 373.72 s; same 2309 ordered outcomes |
| Lowest dependencies | **91 focused workflow/release/docs/language/CLI/quality tests passed** at each endpoint, 4.07/3.26 s; not complete lowest-dependency regression |
| Real Docker/installed pipx | `test_65_pipx.py`: **1 passed / 21 checks**, 40.92 s, no skips; tag installation/replacement/data retention/foreign-launcher/uninstall, no image-build opt-in |
| Packaging, both endpoints | Tracked-input sdist/wheel, strict twine and `check_dist.py` passed; 63 product files byte-identical to source, no private instructions/injectors shipped |
| Static/security | Ruff/shellcheck, actionlint, offline zizmor, tracked-tree/history gitleaks and four dependency `pip check` results clean; existing documented lint exceptions unchanged |

Full commands used the endpoint venv's `python -m pytest -q -rs`, absolute source PYTHONPATH,
serial foreground execution, fresh short external basetemps and separate JUnit results. The
focused files were `test_python_ci.py`, `test_release_scripts.py`, `test_user_docs.py`,
`test_language.py`, `test_cli_structure.py`, `test_quality.py`. Real pipx used
`OCS_TEST_DOCKER=1 OCS_TEST_RUN=branch-migration-pipx-20261102` with only `test_65_pipx.py`.
Packaging used `build --no-isolation`, `twine check --strict`, `.github/scripts/check_dist.py`.
Product cleanup/leak checks passed and the original four full image IDs were unchanged.

Full lowest-dependency suites and the complete real release campaign were **not** rerun at this
checkpoint. Later instruction/security-table edits are documentation only, not new runtime proof.

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

- **B15 post-reboot manager recovery:** actual execution is unverified and risk is **not accepted**.
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
- pipx versions other than 1.18.7, Python 3.12/3.13 separately, Textual 4.0 in a real terminal,
  other terminal emulators, other real model providers and a real provider on Arch. Execute the
  corresponding installed/terminal/provider checks; mocks/pilots are not a substitute.
- Actual post-change full release campaign, real public-network manager replacement, human
  observation, a kill inside `docker commit`, and scheduled GitHub image-build execution.
  Each needs fresh evidence; no passed development subset closes these gaps.
- Typer 0.16.0/Click 8.5 emits deprecations for helpers removed in Click 9. Keep the lowest-bound
  CI check; re-evaluate bounds when that version resolves, not by suppressing warnings/assertions.
- Performance beyond small recorded workspaces has no targets. Current complete suites were
  about 360–388 s; the older 1201-test timing is not a current benchmark.

Known limitations: [ISSUES](ISSUES.md); classified work: [TODO](../../TODO.md). No historical PASS,
focused result or mocked Docker run establishes release readiness on a changed candidate.
