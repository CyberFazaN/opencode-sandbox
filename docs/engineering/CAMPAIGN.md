# Release test matrix

The matrix every release is checked against before it is tagged (`RELEASING.md`). Each row is a
risk to verify; together the rows cover pipx installation, the daemon boundary, the environment
lifecycle, backups and Git transfer, secrets, OpenCode and the Agent Context, the dashboard,
fault injection and the combinations of these. The real rows run on a disposable Arch Linux VM
against the user's own rootless Docker daemon, never in hosted CI: they create, kill and delete
containers, volumes and images, and the privileged rows use `sudo` and restart the daemon.
Arch Linux is therefore the only host with real evidence; the matrix has no rows for other host
distributions (D-046).

How to run the unit suite and the real campaign: `BASELINE.md` ("Commands") and
`CONTRIBUTING.md`. Results of the latest pre-release run, with the platform versions:
`BASELINE.md` ("Verification"). Unless noted otherwise, test files named without a directory are
in `tests/integration/` (the real campaign: every check is logged with the row ID it belongs
to); files under `tests/` are the unit, host and Textual pilot suite.

After D-048 and the startup gate C10 (D-052), 84 rows are active. Installer-only rows B02–B08
are retired, not passed or renumbered; their original evidence remains in the released 6.0.0
record in Git history and BASELINE. Unless a later verification is stated, PASS means the
historical 6.0.0 evidence for the retained behaviour; "6.1.0 candidate" marks evidence from the
complete verification of the 6.1.0 implementation. I04 and I06 must be re-established on the
release tree. B01 retains the manager's refusal of another user's daemon when run as
root; retiring installer checks does not retire that boundary.

## Legend

- Priority (P): **P0** critical, **P1** high, **P2** medium.
- Layers: **real** = real rootless Docker; **OpenCode** = real OpenCode binary; **pty** = real
  terminal (pyte); **pilot** = Textual headless; **host** = real files and Git without Docker;
  **unit** = mocked Docker; **review** = reading code and documents; **sudo** = run with real
  `sudo` on the test VM (privileged rows, `OCS_TEST_PRIVILEGED=1`).
- Status: **PASS** (layer of the evidence), **PASS in part** (what is missing is named),
  **BLOCKED** (reason and next step; accepted risk), **NOT TESTED**.

## A. Inventory and code

| ID | P | Row | Covered by | Latest evidence |
|---|---|---|---|---|
| A01 | P0 | Platform inventory: host, kernel, Python, Git, Docker, Python dependencies and OpenCode versions recorded | `BASELINE.md` ("Supported environments"); `opencode-sandbox doctor` at the start of every campaign run (`conftest.py`) | PASS (D-049 Python 3.11.18/3.14.8; images/OpenCode unchanged) |
| A02 | P0 | Code map: `ARCHITECTURE.md` matches the modules, and the code was reviewed against the product contract | Review of `src/opencode_sandbox/` against `ARCHITECTURE.md`; documentation checks are row I05 | PASS (review; not repeated in the latest run) |
| A03 | P1 | Unit suite passes; every command's `--help` works | `pytest` without `OCS_TEST_DOCKER` (unit, host, pilot, local-process); `tests/test_cli_structure.py` | PASS (6.1.0 candidate: four full 3.11/3.14 current/lowest-direct suites, 969 passed/56 opt-in skips each; pip check; Arch-host local userland equivalent; hosted jobs unexecuted) |
| A04 | P1 | Package build and install | `python -m build` and `twine check --strict`; fresh installations with PyPI dependencies; `tests/test_package_metadata.py`; pipx rows B09–B12 | PASS (6.1.0 candidate: both-endpoint isolated build/strict metadata/content/source-free pipx and 27-file installed payload comparison; real pipx lifecycle at both endpoints) |
| A05 | P1 | Static security review; linters clean | `tests/test_quality.py` (`ruff check src tests .github/scripts`, shellcheck on the three remaining shell scripts; D-034/D-048) | PASS (review, unit) |

## B. Application installation

| ID | P | Row | Covered by | Latest evidence |
|---|---|---|---|---|
| B01 | P0 | Manager as root refuses the user's daemon; no container and nothing under `/root` changed | `test_70_privileged.py`: `test_root_is_refused`; installer-only assertions removed, manager assertions retained | PASS (6.1.0 candidate real, explicitly authorized sudo; installed manager refused, root tree/container/source ownership assertions passed) |
| B09 | P0 | pipx from a Git tag (D-042): clean install in a private HOME/PIPX_HOME, selected Python used by the installed application (not the source tree), every image asset installed, `--help`, `doctor` verified | `test_65_pipx.py` (a `git+file` clone with local test tags) | PASS (D-049 real on 3.11/3.14; interpreter asserted, six assets installed) |
| B10 | P0 | The pipx installation creates, starts and uses an environment; a full image build and verification from the installed package's assets | `test_65_pipx.py`; the image build with `OCS_TEST_PIPX_BUILD=1` (into an `ocs-test-` tag, removed afterwards); the campaign run through the pipx launcher with `OCS_TEST_MANAGER` (`test_10_lifecycle.py`, `test_35_prerequisites.py`, `test_40_opencode.py`, `test_50_tui.py`) | PASS (6.1.0 release tree: installed-pipx image build and whole 56-test/513-check campaign, both-image first prompts; candidate: real create/start/exec at both endpoints) |
| B11 | P0 | Upgrade/downgrade between tags: `pipx upgrade` and `pipx reinstall` keep a tag spec, including interpreter repair with `reinstall --python`; `pipx install` without `--force` refuses, `pipx install --force <spec>@<tag>` moves to the other tag and back; environments survive | `test_65_pipx.py` | PASS (D-049 real on 3.11/3.14) |
| B12 | P1 | `pipx uninstall` removes its launcher and keeps environments, containers and volumes; a foreign/legacy launcher and its target are neither replaced nor deleted; after the test removes its own legacy launcher a working pipx launcher can be installed | `test_65_pipx.py`; the transition from a legacy source installation is documented, not automatic | PASS (D-049 real on 3.11/3.14; volume presence and foreign target contents checked) |

## C. Rootless Docker and images

| ID | P | Row | Covered by | Latest evidence |
|---|---|---|---|---|
| C01 | P0 | Daemon really rootless and the user's own | `test_20_security.py` (socket proxy refused as unverified), `test_70_privileged.py` (real rootful `dockerd` refused by manager `doctor` and `start`, nothing created on it; firewall and interfaces unchanged); `tests/test_runtime_identity.py`. Another user's daemon is represented by a socket served by UID 65534, refused at the peer-UID check before talking to it | PASS (6.1.0 candidate actual own/rootful/other-UID/proxy refusal, post-D-052 installed manager; both endpoint CI scripts measured real private-rootful exit 4; firewall/interfaces unchanged) |
| C02 | P0 | Images build, tools present | `core.build_image` packaged assets and verification, lifecycle package installation; `tests/test_distros.py`, `tests/test_arch_image.py`, `tests/test_opencode_versions.py` | PASS (6.1.0 candidate both actual packaged builds: Debian 13/revision 2 and Arch/revision 1/OpenCode 2.2.0, OS/tools/tar and real package/AUR checks; originals preserved, cached OS freshness not certified) |
| C03 | P0 | Container boundaries: unprivileged, no-new-privileges, dropped capabilities (incl. `NET_RAW`, `MKNOD`), labels, mounts, owner mapping | `test_10_lifecycle.py`, both distributions; `tests/test_version.py` (labelled objects) | PASS (real) |
| C04 | P0 | Network `none` is offline; `bridge` behaves as documented (the LAN is reachable) | `test_10_lifecycle.py` (measured reachability); `tests/test_readiness.py` | PASS (real) |
| C05 | P1 | Limits applied; omitted settings kept; reported support distinct from configuration/enforcement | `test_37_resource_support.py` (real cgroup files), `test_10_lifecycle.py`, `test_50_tui.py` (dashboard), `test_80_combinations.py`; `tests/test_resource_support.py`, `tests/test_config_plan.py`, `tests/test_runtime_host.py` | PASS (D-053: 1 real test/8 checks; reported capabilities, actual cpu.max/memory.max/pids.max before/after changes, markers/cache preserved; other lifecycle/settings evidence retained) |
| C06 | P1 | Name squatting and spoofed objects are not adopted | `test_20_security.py` (an unlabelled container with the environment's name is refused and never removed by delete), `test_80_combinations.py`; `tests/test_recovery.py`, `tests/test_transactions.py`. Accepted limitation: label forgery by a process that uses the same daemon (`docs/security.md`) | PASS (real) |
| C07 | P2 | A failed image update keeps the previous image | `tests/test_opencode_versions.py` (failure paths of `build` and `update-base`); a real failed build was observed when an upstream release broke the build | PASS (real; not repeated in the latest run, the failure path is unit-tested) |
| C08 | P1 | First start fails (published host port taken): no container is left, `config apply` fixes the port, start works | `test_26_port_and_snapshot.py` (Debian; the port is held by a socket of the test) | PASS (real) |
| C09 | P1 | Host prerequisites diagnosed (D-042, D-043): no Docker CLI, a context that does not exist, a missing socket, a file instead of a socket, a TCP endpoint, no Git, no terminal; `--help`/`--version`/`list` work without Docker; distinct exit codes 5–8 and 2; the dashboard opens without Docker and says so | `test_35_prerequisites.py`, the missing-context row of `test_30_faults.py`; `tests/test_prerequisites.py`, `tests/test_runtime_identity.py`; test contexts only in a private `DOCKER_CONFIG`, the user's Docker configuration unchanged | PASS (D-049 real, pty on 3.11; earlier D-048 real 3.14; shared checks unchanged) |
| C10 | P1 | Cold Rootless Docker/socket activation: bounded secure readiness, fast warm path, transient/permanent distinction, responsive CLI/TUI progress/cancel | `test_36_socket_activation.py` (explicit separate-user-unit opt-in), `tests/test_docker_readiness.py`, identity/prerequisite/pilot regressions; design: D-052 | PASS (6.1.0 release-tree and candidate full installed-pipx campaigns each re-established all four cases on the isolated inherited listener; existing-daemon restart is separately D09, not cold-start evidence; D-052 source/wheel evidence retained) |

## D. Lifecycle, persistence, concurrency

| ID | P | Row | Covered by | Latest evidence |
|---|---|---|---|---|
| D01 | P0 | Create, list, status, start, stop, shell, exec, delete | `test_10_lifecycle.py`, `test_20_security.py`, `test_50_tui.py`; `tests/test_core.py`, `tests/test_lifecycle.py` | PASS (real) |
| D02 | P0 | Import: committed files only, names, modes, symlinks | `test_10_lifecycle.py` (spaces, leading dash, non-ASCII, executable bit, an escaping committed symlink kept as a link); `tests/test_core.py`, `tests/test_profile_and_import_safety.py` | PASS (real) |
| D03 | P0 | Workspace, home, system layer and packages persist; other metadata schemas are not migrated | `test_10_lifecycle.py`, `test_12_image_compatibility.py`; Debian apt, retained binary markers/config and schema-boundary fixture; Arch/AUR rows | PASS (6.1.0 candidate both-image and retained Debian 12 data/packages/configuration, no implicit OS upgrade/schema migration; base-change old/new/pinned preservation) |
| D04 | P0 | Recreation keeps everything | `test_10_lifecycle.py`, `test_12_image_compatibility.py`, `test_30_faults.py`, `test_80_combinations.py`; `tests/test_recreate_consistency.py` | PASS (6.1.0 candidate normal/settings recreation on both images/retained 12 and complete fault/recovery cases, exact markers preserved) |
| D05 | P0 | Crash at every recreation step; recovery | `test_30_faults.py`: SIGKILL through a docker shim after the stop, before and after the commit, after the removal, before and after `run -d`; recovery refuses an old container that was started again; `tests/test_recreate_faults.py`, `tests/test_journals.py` | PASS (real) |
| D06 | P1 | Repair; an interrupted delete | `test_30_faults.py` (a delete killed after the container removal can be repeated); `tests/test_lifecycle.py`, `tests/test_transactions.py`, `tests/test_recovery.py` | PASS (real) |
| D07 | P1 | Concurrent operations | `test_30_faults.py`: two recreations, a settings change and a stop at once; the same name created three times at once; refusals say to wait for the running operation; `tests/test_journals.py`, `tests/test_recovery.py` (cross-process lock) | PASS (real) |
| D08 | P1 | Quick sessions: promote, keep | `test_15_integrations_quick.py`; `tests/test_core.py` | PASS (real, pty) |
| D09 | P2 | Space reserve, unreadable files, daemon restart, reboot | `test_30_faults.py` (space reserve, an unreadable workspace file), `test_70_privileged.py` (`systemctl --user restart`, stop/start — what shutdown and boot do to the containers — and a SIGKILL of the whole daemon unit with an environment running: data intact, `start` and `check` work); `tests/test_disk_space.py`, `tests/test_unreadable_workspace.py` | PASS in part (real): a host reboot is **BLOCKED** — it cannot be driven from inside the test session; accepted risk (the daemon stop/start covers the container side); next step: reboot, then `opencode-sandbox start NAME` and `opencode-sandbox check NAME` on a test environment |
| D10 | P0 | Lookup by name or ID: an empty key, a short or stale prefix and ID-shaped names never select another environment | `tests/test_resolve.py`; the lookup logic is tested at the unit layer by design, the real CLI was checked once on an isolated data directory with the real daemon | PASS (unit; real CLI) |
| D11 | P2 | Two default snapshots in one second get two tags; an existing tag is never moved | `test_26_port_and_snapshot.py` (Debian: two tags, both present); `tests/test_snapshot_tag.py` (same second with a fixed clock, the OpenCode rollback path) | PASS (real) |

## E. Backup, restore, Git

| ID | P | Row | Covered by | Latest evidence |
|---|---|---|---|---|
| E01 | P0 | Backup and restore to a new name, byte-level compare | `test_10_lifecycle.py`, `test_12_image_compatibility.py`, `test_80_combinations.py`; `tests/test_backup.py`, `tests/test_staged_restore.py` | PASS (6.1.0 candidate both images; pre-change manager's 12 system backup restores 12, explicit no-system restores workspace/home on 13, binary/config markers retained; direct-workspace backup/restore unchanged) |
| E02 | P0 | Interrupted backup or restore; resume and rollback | `test_30_faults.py`: SIGKILL during a backup (leaves a temporary directory, removed by `disk cleanup`), SIGTERM (cleanup runs), restore killed at volume creation and before the image load → rollback and resume; `tests/test_restore_resume.py`, `tests/test_staged_restore.py`, `tests/test_transactions.py` | PASS (real) |
| E03 | P0 | Archive traversal, symlink escapes, decompression bombs | `tests/test_backup.py`, `tests/test_backup_hardening.py`, `tests/test_archive_paths.py`, `tests/test_home_archive_paths.py`, `tests/test_restore_settings.py` (bomb); crafted archives against the real extractor, links are never written through (D-022); host layer by design | PASS (host, unit) |
| E04 | P1 | Backup of a stopped and a running environment, `--no-system`, verify, prune | `test_10_lifecycle.py`, `test_30_faults.py`, `test_50_tui.py` (dashboard backup), `test_80_combinations.py`; prune (per environment ID and by recorded creation time): `tests/test_backup_hardening.py`, `tests/test_backup_restore_edge_cases.py` | PASS (real); prune: unit (an earlier real run, not repeated) |
| E05 | P1 | Snapshot versus backup behave as documented | `test_10_lifecycle.py` (backup), `test_26_port_and_snapshot.py` (snapshots); `tests/test_snapshot_tag.py`; documented in `docs/backup.md` ("Snapshots and recreation") | PASS (real) |
| E06 | P0 | Changes: show, bundle, inspect, stage, branch-diff, unstage | `test_10_lifecycle.py` (incl. `changes bundle` of a restored Git project), `test_50_tui.py`; `tests/test_gitflow_roundtrip.py` | PASS (real) |
| E07 | P1 | Dirty source and unsafe links refused | `test_10_lifecycle.py` (the source's base-commit link `../../../etc/hostname` is kept by the tracked-link check); `tests/test_gitflow_roundtrip.py`, `tests/test_review_flow.py`. By design, untracked absolute or escaping symlinks are refused by change transfer | PASS (real) |
| E08 | P0 | Host Git never uses the workspace repository's configuration (nested repository, a change after the check, gitlink refused, storage formats) | `test_80_combinations.py` (a clean filter, a diff textconv and fsmonitor set by root in the container are not run by `changes show/export/bundle/inspect`, `check`, `backup create`; control: plain host Git in that workspace runs them); `tests/test_git_boundary.py`, `tests/test_untrusted_workspace.py` (links below the top level of `.git`: unit only); accepted residuals D-025..D-034 | PASS (unit, host; real container) |
| E09 | P0 | A backup without a container keeps the derived system layer; names starting with `-` round-trip; sockets and FIFOs are left out and reported; restore keeps installed packages | `test_10_lifecycle.py`, `test_12_image_compatibility.py`; `tests/test_backup_completeness.py` | PASS (6.1.0 candidate both-image lifecycle plus retained 12 no-container derived-image backup, OS/markers/packages preserved) |
| E10 | P1 | Restore into a second data directory on the same daemon: the image is labelled for that directory, the first directory's cleanup leaves it, its own cleanup removes it; after the backed-up environment is deleted, the first directory's cleanup exits 0 and the restored environment still starts | `test_10_lifecycle.py` (both distributions); `tests/test_image_provenance.py`, `tests/test_cleanup_untagged_parents.py` | PASS (real) |
| E11 | P1 | Custom-image environment: the original image is kept through reconfiguration, backup `--no-system` and restore | `test_10_lifecycle.py` (`ubuntu:24.04`); `tests/test_image_provenance.py` | PASS (real) |
| E12 | P0 | Review flow: sandbox text escaped in the CLI and the dashboard; tracked links leaving the repository refused; attention list; executable bits kept | `tests/test_review_flow.py`, `tests/test_tui_text.py`; real: `test_10_lifecycle.py` (rows E06, E07), `test_50_tui.py` (the dashboard's Changes view) | PASS (unit, host; real) |

## F. Secrets and security

| ID | P | Row | Covered by | Latest evidence |
|---|---|---|---|---|
| F01 | P0 | Hostile values are not executed; profiles are 0600 | `test_20_security.py`: a value with `$()`, backticks, quotes and a newline is delivered byte for byte and never executed; a 0644 profile is reported by `check` and not mounted into new containers; `tests/test_profile_and_import_safety.py`, `tests/test_profile_mounts.py`; dummy keys only | PASS (real, pty) |
| F02 | P0 | Legacy executable `.env` profiles refused; values never shown | `test_20_security.py`; `tests/test_cli_robustness.py`, `tests/test_core.py` (redaction) | PASS (real) |
| F03 | P0 | Profile change and isolation between environments | `test_20_security.py`; `tests/test_profile_mounts.py` | PASS (real, pty) |
| F04 | P0 | No privileged mode, Docker socket, devices or extra mounts | `test_10_lifecycle.py` | PASS (real) |
| F05 | P1 | The user's OpenCode configuration is respected | `test_40_opencode.py` (row G06), `test_80_combinations.py` | PASS (real OpenCode) |
| F06 | P1 | No secrets in inspect output, processes, metadata, logs, backups or requests | `test_10_lifecycle.py`, `test_20_security.py`, `test_40_opencode.py` | PASS (real) |

## G. OpenCode and Agent Context

| ID | P | Row | Covered by | Latest evidence |
|---|---|---|---|---|
| G01 | P0 | Versions are read from the binaries | `test_40_opencode.py`; `tests/test_opencode_versions.py`, `tests/test_hardening.py` | PASS (real OpenCode) |
| G02 | P0 | Registry lookup without host npm; pinned policy | `test_30_faults.py`, `test_40_opencode.py` (the pinned policy refuses other versions without downloading anything); `tests/test_opencode_versions.py` | PASS (real) |
| G03 | P0 | Base and environment update, rollback, failure | `test_12_image_compatibility.py`, `test_30_faults.py`, `test_80_combinations.py`; scoped Campaign base verification in BASELINE; `tests/test_opencode_lifecycle.py`, `tests/test_opencode_versions.py` | PASS (6.1.0 candidate actual environment replacement/rollback on 12/13, complete faults; 13 additional base-workflow checks on both images, exact base-ID rollback, old/new/pinned data/configuration and actual old-OS refusal) |
| G04 | P0 | The first prompt receives the guidance | `test_40_opencode.py`: complete guidance verbatim and explicit current base OS in the first agent request, network none, fake in-container provider; `tests/test_agent_context_integration.py`. Real provider: OpenRouter `z-ai/glm-5.3-flash` through the installed manager (BASELINE "6.1.0 release tree"); other providers untested | PASS (6.1.0 release tree: real OpenCode 2.2.0/pty on Debian 13 and Arch with full guidance/first-request OS, dummy provider and unchanged user configuration; the real OpenRouter model answered the Debian 13 base OS from the guidance in its first prompt) |
| G05 | P0 | Agent Context refreshed without recreation; settings and retained base provenance reflected | `test_10_lifecycle.py`, `test_12_image_compatibility.py`, `test_40_opencode.py`, `test_80_combinations.py`; `tests/test_agent_context.py`, `tests/test_environment_definition.py`, `tests/test_hardening.py` | PASS (6.1.0 candidate both images/current 13/retained 12, restored/derived/checkpoint layers and first requests; metadata-only/offline unknown cases unit/pilot) |
| G06 | P1 | Existing OpenCode configuration preserved | `test_12_image_compatibility.py`, `test_40_opencode.py`, `test_80_combinations.py` | PASS (6.1.0 candidate real prompts, system/no-system restores, actual environment/base version workflows and rollback; user configuration bytes unchanged) |
| G07 | P1 | `exec` is not managed (no provider profile) | `test_20_security.py` | PASS (real) |
| G08 | P1 | `agent-context show` and `verify`; no secrets or host paths | `test_40_opencode.py`; `tests/test_agent_context.py` | PASS (real) |
| G09 | P2 | Version check on demand only | `test_50_tui.py` (`v`); `tests/test_opencode_versions.py` | PASS (real, pty) |
| G10 | P0 | Initial integrations applied exactly once | `test_15_integrations_quick.py` (Context7 added once, then the user's), `test_80_combinations.py`; `tests/test_integrations.py` | PASS (6.1.0 candidate real once-only setup, user's changes/removal survive stop/start/recreation/settings and version rollback; no reapplication) |

## H. Dashboard

| ID | P | Row | Covered by | Latest evidence |
|---|---|---|---|---|
| H01 | P0 | Starts, empty state, quits restoring the terminal | `test_50_tui.py`; `tests/test_tui.py` | PASS (pty, real) |
| H02 | P0 | Keyboard-only navigation and dialogs | `test_50_tui.py`; `tests/test_tui.py` | PASS (pty) |
| H03 | P0 | Create (incl. direct), start, shell, OpenCode, check, settings, changes, backup, restore, versions | `test_50_tui.py` | PASS (pty, real) |
| H04 | P0 | Long operations are asynchronous | `test_50_tui.py` (backup and restore from the dashboard); `tests/test_tui.py` | PASS (pty) |
| H05 | P1 | Return from sessions and terminal restoration; signal/killed-manager cleanup | `test_50_tui.py`, `test_40_opencode.py`, `test_80_combinations.py`; `tests/test_run_hangup.py`, `tests/test_session_signals.py` | PASS (D-054: launch-ownership race traced/fixed, terminal raw-mode defect reproduced/fixed; 6 installed-wheel real tests/83 checks, both-image OpenCode exits, dashboard SIGKILL, CLI SIGTERM/SIGHUP client/token/terminal checks, settings-session returns; deterministic host-process/pty regressions, not an isolated-rerun waiver) |
| H06 | P1 | 80x24, 100x30, 120x40 | `test_50_tui.py` (100x30), `test_35_prerequisites.py` (80x24 without Docker); `tests/test_tui.py` (all three sizes); the dashboard and keys panel at 80x24 and 120x40 and the direct-workspace consent dialog at 80x24 (complete; Cancel creates nothing) are scripted pty checks with `pty_term.py` in isolated data directories, not a campaign test | PASS (pty) |
| H07 | P1 | Pilot tests | `tests/test_tui.py` | PASS (pilot) |
| H08 | P2 | Texts, empty state, refresh after CLI changes | `tests/test_tui.py`, `tests/test_tui_text.py`; `test_50_tui.py` | PASS (pilot, pty) |

## I. Reliability and release

| ID | P | Row | Covered by | Latest evidence |
|---|---|---|---|---|
| I01 | P0 | Fault injection | `test_30_faults.py`, `test_70_privileged.py`; see D05, D06, D09, E02, G03 | PASS (real) |
| I02 | P1 | No leaks | The campaign's session end (`conftest.py`, `campaign.py`): guarded cleanup, checked inventory, labels/tags/processes; `test_70_privileged.py`; `tests/test_campaign_safety.py` | PASS (6.1.0 candidate full real/extra sessions and final six-directory checks; failed inventory cannot certify empty state; failed-run cleanup completed after explicit host recovery; only manifested test resources removed) |
| I03 | P1 | Performance baseline | Median durations per command from the campaign log (every command is logged with its duration); small test workspaces; no targets defined | PASS (real; durations recorded in the run log, no targets) |
| I04 | P0 | Full regression at the release revision | The whole current real campaign, both distributions and packaged image build; retained privileged rows with consent; campaign through a pipx installation of a test tag. Evidence: `BASELINE.md` | PASS (6.1.0 release tree: complete campaign through a pipx installation of a local `v6.1.0` test tag, both base images built from the installed package into a test-only namespace, privileged and C10 rows with consent, published `v6.0.0` as the legacy manager: 56 tests, 513 checks, 0 failed, 0 skipped; plus no-cache builds of both images and one real model provider) |
| I05 | P0 | Documentation matches the code: every command and option named in the product, `README.md` and `docs/` exists; relative links and anchors resolve; code blocks fit 80 columns; the install commands name the release tag; active documents are English; new instructions in the guides were measured | `tests/test_cli_structure.py`, `tests/test_user_docs.py`, `tests/test_language.py`, `tests/test_disclosure.py`; review of `README.md`, `CHANGELOG.md` and the guides against the code and `--help` | PASS (review, unit) |
| I06 | P0 | Release decision: every P0 and P1 row PASS with real evidence or BLOCKED with accepted risk (`RELEASING.md`) | This matrix and `BASELINE.md` | NOT TESTED (version 6.1.0 and Beta decided, D-055; waits for I04 on the release tree and the owner's publication decision) |

## J, K, L. Readiness and cleanup, distributions, direct workspaces

| ID | P | Row | Covered by | Latest evidence |
|---|---|---|---|---|
| J01 | P1 | Readiness checks are read-only and accurate, including managed base-definition revisions and unknown inspection results | `check` in `test_10_lifecycle.py`, `test_30_faults.py`, `test_50_tui.py`, `test_80_combinations.py`; `tests/test_readiness.py`, `tests/test_image_readiness.py` | PASS (6.1.0 candidate real environment checks, both images, retained OS, failure/recovery/daemon-down/cold scenarios; shared revision/resource negative matrix retained at unit/pilot layers) |
| J02 | P0 | Cleanup removes only this data directory's leftovers; never base images or the build cache | `test_80_combinations.py`, the campaign's session end (cleanup exits 0, nothing left); `tests/test_cleanup.py`, `tests/test_cleanup_untagged_parents.py` | PASS (real) |
| K01 | P0 | Arch image, AUR through `ocs-aur` | `test_10_lifecycle.py`, `test_80_combinations.py`; `tests/test_arch_image.py`, `tests/test_distros.py` | PASS (real) |
| L01 | P0 | Direct workspace checks, consent, preflight; the folder is never deleted | `test_50_tui.py` (the consent text complete at 100x30), `test_80_combinations.py`; the consent dialog at 80x24 by a scripted pty check (row H06); `tests/test_direct_workspace.py`, `tests/test_disclosure.py` | PASS (real, pty) |
| L02 | P0 | A direct workspace is re-checked at every start: the folder replaced by a symlink while stopped → `start` refuses and the container stays stopped; restored → `start` works; delete leaves both folders | `test_25_direct.py` (Debian); `tests/test_direct_restart.py` (also recreation recovery, a restarting settings change, an OpenCode update) | PASS (real) |

## M. Combinations

| ID | P | Row | Covered by | Latest evidence |
|---|---|---|---|---|
| M01 | P1 | Arch + AUR + direct workspace + recreation: the AUR build writes nothing into the folder, container-root files are owned by the user, recreation keeps the package and remounts the folder, delete leaves it | `test_80_combinations.py` (Arch) | PASS (real) |
| M02 | P1 | Backup and restore of a direct-workspace environment: by default the folder is left out and the restore gets an empty managed workspace with a warning; `--include-workspace` brings the files back as a managed copy; the folder is never touched | `test_80_combinations.py` (Debian) | PASS (real) |
| M03 | P1 | OpenCode update (2.1.4) and rollback (2.2.0) with the user's OpenCode configuration and Context7 written at the first start: configuration byte-identical, integrations not re-applied, Agent Context current | `test_80_combinations.py` (Debian) | PASS (real OpenCode) |
| M04 | P1 | Settings change during an open shell session: an in-place change keeps it; a recreating change (network `none`) is announced by the plan and ends the session (exit 137), the manager returns, a new session works, data kept | `test_80_combinations.py` (Debian) | PASS (real, pty) |
| M05 | P0 | Cleanup next to objects it does not own: unlabelled containers, volumes and images named like manager objects and objects of another data directory are neither offered nor removed; this directory's orphan volume is; base images kept | `test_80_combinations.py` | PASS (real) |
| M06 | P1 | An interrupted operation and its recovery (recreation, settings, restore, OpenCode update, delete killed at each step) | `test_30_faults.py` (rows D05, D06, E02, G03) | PASS (real) |

## Counts

84 active rows, including the P1 startup/socket-activation gate C10 (D-052). Seven
installer-only rows retired by D-048: B02–B05 (four P0) and B06–B08
(three P1). Their removal is not a PASS and does not change the historical 6.0.0 totals.

| Priority | Rows | PASS | PASS in part | BLOCKED | NOT TESTED | FAIL |
|---|---|---|---|---|---|---|
| P0 | 46 | 45 | 0 | 0 | 1 | 0 |
| P1 | 33 | 33 | 0 | 0 | 0 | 0 |
| P2 | 5 | 4 | 1 | 0 | 0 | 0 |
| All | 84 | 82 | 1 | 0 | 1 | 0 |

- PASS in part: D09 (the host reboot is BLOCKED with accepted risk and a next step).
- C10 was re-established in the complete installed-pipx campaigns of the 6.1.0 candidate and
  of the release tree, not just host sockets or warmed direct Docker.
- I04 passed on the 6.1.0 release tree (56 tests/513 checks). I06 waits for the release
  decision report and the owner's publication decision.
- H05: an intermittent session-test failure was traced to a launch-ownership race and fixed
  (D-054); the first real run also found a terminal-restoration defect, retained as failing
  evidence and fixed before the successful scoped rerun.
- PASS rows that rest on review, unit, host or pilot evidence by design: A02, A05, I05, I06
  (review), A03 (unit), D10 (lookup logic), E03 (crafted archives against the real extractor),
  H07 (pilot).
- PASS rows with an accepted limitation inside the row: C01 (another user's daemon represented
  by another user's socket), C06 (label forgery through the same daemon), G04 (one real model
  provider, OpenRouter; the automated rows use a fake one).
- Accepted product limitations: `docs/security.md` ("Known limitations"); accepted residuals:
  `DECISIONS.md` D-025..D-034.
