# Release test matrix

The matrix every release is checked against before it is tagged (`RELEASING.md`). Each row is a
risk to verify; together the rows cover the installer, the daemon boundary, the environment
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

## Legend

- Priority (P): **P0** critical, **P1** high, **P2** medium.
- Layers: **real** = real rootless Docker; **OpenCode** = real OpenCode binary; **pty** = real
  terminal (pyte); **pilot** = Textual headless; **host** = real files and Git without Docker;
  **unit** = mocked Docker; **review** = reading code and documents; **sudo** = run with real
  `sudo` on the test VM (privileged rows, `OCS_TEST_PRIVILEGED=1`).
- Status: **PASS** (layer of the evidence), **PASS in part** (what is missing is named),
  **BLOCKED** (reason and next step; accepted risk), **NOT TESTED**.

## A. Inventory and code

| ID | P | Row | Covered by | Status 6.0.0 |
|---|---|---|---|---|
| A01 | P0 | Platform inventory: host, kernel, Python, Git, Docker, Python dependencies and OpenCode versions recorded | `BASELINE.md` ("Supported environments"); `opencode-sandbox doctor` at the start of every campaign run (`conftest.py`) | PASS (real) |
| A02 | P0 | Code map: `ARCHITECTURE.md` matches the modules, and the code was reviewed against the product contract | Review of `src/opencode_sandbox/` against `ARCHITECTURE.md`; documentation checks are row I05 | PASS (review; not repeated in the latest run) |
| A03 | P1 | Unit suite passes; every command's `--help` works | `pytest` without `OCS_TEST_DOCKER` (unit, host, pilot); `tests/test_cli_structure.py` | PASS (unit) |
| A04 | P1 | Package build and install | `python -m build` and `twine check --strict`; wheel installed into a fresh venv with PyPI dependencies (`--version`, `doctor` verifies the daemon and both images); `tests/test_package_metadata.py`; pipx rows B09–B12 | PASS (real) |
| A05 | P1 | Static security review; linters clean | `tests/test_quality.py` (`ruff check src tests .github/scripts`, shellcheck on the four shell scripts; D-034) | PASS (review, unit) |

## B. Installer

| ID | P | Row | Covered by | Status 6.0.0 |
|---|---|---|---|---|
| B01 | P0 | Root refusal; doctor and dry run write nothing | `test_60_installer.py`, `test_70_privileged.py` (`sudo install.sh install/--dry-run/doctor/update/uninstall` and `sudo setup-rootless.sh [--dry-run]` refused, `/root` unchanged; the manager run as root refuses the user's daemon as another user's and creates no container); `tests/test_installer.py` | PASS (real, sudo) |
| B02 | P0 | Missing dependencies, `--offer-packages` | `test_70_privileged.py`: the missing package is simulated by a `pacman -Q` shim; offered; `n` runs no sudo; `y` runs exactly `sudo pacman -S -- fuse-overlayfs`, declined at pacman's own prompt (no package is actually installed), packages unchanged | PASS (real, sudo, real pacman) |
| B03 | P0 | First install in a throw-away HOME, launcher, doctor | `test_60_installer.py`; `tests/test_installer.py` (doctor reports a release that no longer starts) | PASS (real, pty) |
| B04 | P0 | Update; a failed update keeps the release | `test_60_installer.py` (failure = unreachable package index) | PASS (real, pty) |
| B05 | P0 | Manual rollback as documented | `test_60_installer.py` | PASS (real) |
| B06 | P1 | Uninstall keeps data; a foreign launcher is refused | `test_60_installer.py`; `tests/test_installer.py` | PASS (real) |
| B07 | P1 | No TTY fails safely | `test_60_installer.py`; `tests/test_installer.py` | PASS (real) |
| B08 | P1 | `setup-rootless.sh` changes nothing implicitly | `test_70_privileged.py`: `--dry-run`; answered yes, `systemctl --user enable --now` leaves the running daemon as it was (same main PID), hello-world smoke test, READY; `tests/test_installer.py` | PASS (real, pty) |
| B09 | P0 | pipx from a Git tag (D-042): clean install in a private HOME/PIPX_HOME, the installed package runs (not the source tree), every image asset installed, `--help`, `doctor` verified | `test_65_pipx.py` (a `git+file` clone with local test tags) | PASS (real) |
| B10 | P0 | The pipx installation creates, starts and uses an environment; a full image build and verification from the installed package's assets | `test_65_pipx.py`; the image build with `OCS_TEST_PIPX_BUILD=1` (into an `ocs-test-` tag, removed afterwards); the campaign run through the pipx launcher with `OCS_TEST_MANAGER` (`test_10_lifecycle.py`, `test_35_prerequisites.py`, `test_40_opencode.py`, `test_50_tui.py`) | PASS (real) |
| B11 | P0 | Upgrade and downgrade between tags: `pipx upgrade` and `pipx reinstall` keep a tag spec, `pipx install` without `--force` refuses, `pipx install --force <spec>@<tag>` moves to the other tag and back; environments survive | `test_65_pipx.py` | PASS (real) |
| B12 | P1 | `pipx uninstall` removes the launcher and keeps environments, containers and volumes; pipx does not replace a working `install.sh` launcher (warns 'Not modifying'); `install.sh` refuses a pipx launcher and names `pipx uninstall opencode-sandbox` | `test_65_pipx.py`; `tests/test_installer.py` (a custom PIPX_HOME) | PASS (real) |

## C. Rootless Docker and images

| ID | P | Row | Covered by | Status 6.0.0 |
|---|---|---|---|---|
| C01 | P0 | Daemon really rootless and the user's own | `test_20_security.py` (a socket proxy to the user's daemon is refused as an unverified proxy), `test_70_privileged.py` (a real rootful `dockerd` in private directories refused by `doctor`, `start` and `install.sh doctor`, nothing created on it; firewall rules and interfaces unchanged); `tests/test_runtime_identity.py`. Accepted limitation: another user's daemon is represented by a socket served by another user (UID 65534), refused at the peer-UID check, which precedes every other check, so another user's real dockerd takes the same path | PASS (real, sudo) |
| C02 | P0 | Images build, tools present | `opencode-sandbox build` and `opencode-sandbox opencode update-base` for both distributions; `tests/test_distros.py`, `tests/test_arch_image.py`, `tests/test_opencode_versions.py` (the image's OS and tools are verified) | PASS (real) |
| C03 | P0 | Container boundaries: unprivileged, no-new-privileges, dropped capabilities (incl. `NET_RAW`, `MKNOD`), labels, mounts, owner mapping | `test_10_lifecycle.py`, both distributions; `tests/test_version.py` (labelled objects) | PASS (real) |
| C04 | P0 | Network `none` is offline; `bridge` behaves as documented (the LAN is reachable) | `test_10_lifecycle.py` (measured reachability); `tests/test_readiness.py` | PASS (real) |
| C05 | P1 | Limits applied; omitted settings kept | `test_10_lifecycle.py`, `test_50_tui.py` (dashboard), `test_80_combinations.py`; `tests/test_config_plan.py`, `tests/test_runtime_host.py` | PASS (real) |
| C06 | P1 | Name squatting and spoofed objects are not adopted | `test_20_security.py` (an unlabelled container with the environment's name is refused and never removed by delete), `test_80_combinations.py`; `tests/test_recovery.py`, `tests/test_transactions.py`. Accepted limitation: label forgery by a process that uses the same daemon (`docs/security.md`) | PASS (real) |
| C07 | P2 | A failed image update keeps the previous image | `tests/test_opencode_versions.py` (failure paths of `build` and `update-base`); a real failed build was observed when an upstream release broke the build | PASS (real; not repeated in the latest run, the failure path is unit-tested) |
| C08 | P1 | First start fails (published host port taken): no container is left, `config apply` fixes the port, start works | `test_26_port_and_snapshot.py` (Debian; the port is held by a socket of the test) | PASS (real) |
| C09 | P1 | Host prerequisites diagnosed (D-042, D-043): no Docker CLI, a context that does not exist, a missing socket, a file instead of a socket, a TCP endpoint, no Git, no terminal; `--help`/`--version`/`list` work without Docker; distinct exit codes 5–8 and 2; the dashboard opens without Docker and says so | `test_35_prerequisites.py`, the missing-context row of `test_30_faults.py`; `tests/test_prerequisites.py`, `tests/test_runtime_identity.py`; test contexts only in a private `DOCKER_CONFIG`, the user's Docker configuration unchanged | PASS (real, pty) |

## D. Lifecycle, persistence, concurrency

| ID | P | Row | Covered by | Status 6.0.0 |
|---|---|---|---|---|
| D01 | P0 | Create, list, status, start, stop, shell, exec, delete | `test_10_lifecycle.py`, `test_20_security.py`, `test_50_tui.py`; `tests/test_core.py`, `tests/test_lifecycle.py` | PASS (real) |
| D02 | P0 | Import: committed files only, names, modes, symlinks | `test_10_lifecycle.py` (spaces, leading dash, non-ASCII, executable bit, an escaping committed symlink kept as a link); `tests/test_core.py`, `tests/test_profile_and_import_safety.py` | PASS (real) |
| D03 | P0 | Workspace, home, system layer and packages persist | `test_10_lifecycle.py`: Debian `apt`, Arch `pacman` and AUR (`ocs-aur`) | PASS (real) |
| D04 | P0 | Recreation keeps everything | `test_10_lifecycle.py`, `test_30_faults.py`, `test_80_combinations.py`; `tests/test_recreate_consistency.py` | PASS (real) |
| D05 | P0 | Crash at every recreation step; recovery | `test_30_faults.py`: SIGKILL through a docker shim after the stop, before and after the commit, after the removal, before and after `run -d`; recovery refuses an old container that was started again; `tests/test_recreate_faults.py`, `tests/test_journals.py` | PASS (real) |
| D06 | P1 | Repair; an interrupted delete | `test_30_faults.py` (a delete killed after the container removal can be repeated); `tests/test_lifecycle.py`, `tests/test_transactions.py`, `tests/test_recovery.py` | PASS (real) |
| D07 | P1 | Concurrent operations | `test_30_faults.py`: two recreations, a settings change and a stop at once; the same name created three times at once; refusals say to wait for the running operation; `tests/test_journals.py`, `tests/test_recovery.py` (cross-process lock) | PASS (real) |
| D08 | P1 | Quick sessions: promote, keep | `test_15_integrations_quick.py`; `tests/test_core.py` | PASS (real, pty) |
| D09 | P2 | Space reserve, unreadable files, daemon restart, reboot | `test_30_faults.py` (space reserve, an unreadable workspace file), `test_70_privileged.py` (`systemctl --user restart`, stop/start — what shutdown and boot do to the containers — and a SIGKILL of the whole daemon unit with an environment running: data intact, `start` and `check` work); `tests/test_disk_space.py`, `tests/test_unreadable_workspace.py` | PASS in part (real): a host reboot is **BLOCKED** — it cannot be driven from inside the test session; accepted risk (the daemon stop/start covers the container side); next step: reboot, then `opencode-sandbox start NAME` and `opencode-sandbox check NAME` on a test environment |
| D10 | P0 | Lookup by name or ID: an empty key, a short or stale prefix and ID-shaped names never select another environment | `tests/test_resolve.py`; the lookup logic is tested at the unit layer by design, the real CLI was checked once on an isolated data directory with the real daemon | PASS (unit; real CLI) |
| D11 | P2 | Two default snapshots in one second get two tags; an existing tag is never moved | `test_26_port_and_snapshot.py` (Debian: two tags, both present); `tests/test_snapshot_tag.py` (same second with a fixed clock, the OpenCode rollback path) | PASS (real) |

## E. Backup, restore, Git

| ID | P | Row | Covered by | Status 6.0.0 |
|---|---|---|---|---|
| E01 | P0 | Backup and restore to a new name, byte-level compare | `test_10_lifecycle.py` (both distributions, with the system image, packages, an AUR package, a venv-style absolute symlink, modification times, the restored image's label), `test_80_combinations.py`; `tests/test_backup.py`, `tests/test_staged_restore.py` | PASS (real) |
| E02 | P0 | Interrupted backup or restore; resume and rollback | `test_30_faults.py`: SIGKILL during a backup (leaves a temporary directory, removed by `disk cleanup`), SIGTERM (cleanup runs), restore killed at volume creation and before the image load → rollback and resume; `tests/test_restore_resume.py`, `tests/test_staged_restore.py`, `tests/test_transactions.py` | PASS (real) |
| E03 | P0 | Archive traversal, symlink escapes, decompression bombs | `tests/test_backup.py`, `tests/test_backup_hardening.py`, `tests/test_archive_paths.py`, `tests/test_home_archive_paths.py`, `tests/test_restore_settings.py` (bomb); crafted archives against the real extractor, links are never written through (D-022); host layer by design | PASS (host, unit) |
| E04 | P1 | Backup of a stopped and a running environment, `--no-system`, verify, prune | `test_10_lifecycle.py`, `test_30_faults.py`, `test_50_tui.py` (dashboard backup), `test_80_combinations.py`; prune (per environment ID and by recorded creation time): `tests/test_backup_hardening.py`, `tests/test_backup_restore_edge_cases.py` | PASS (real); prune: unit (an earlier real run, not repeated) |
| E05 | P1 | Snapshot versus backup behave as documented | `test_10_lifecycle.py` (backup), `test_26_port_and_snapshot.py` (snapshots); `tests/test_snapshot_tag.py`; documented in `docs/backup.md` ("Snapshots and recreation") | PASS (real) |
| E06 | P0 | Changes: show, bundle, inspect, stage, branch-diff, unstage | `test_10_lifecycle.py` (incl. `changes bundle` of a restored Git project), `test_50_tui.py`; `tests/test_gitflow_roundtrip.py` | PASS (real) |
| E07 | P1 | Dirty source and unsafe links refused | `test_10_lifecycle.py` (the source's base-commit link `../../../etc/hostname` is kept by the tracked-link check); `tests/test_gitflow_roundtrip.py`, `tests/test_review_flow.py`. By design, untracked absolute or escaping symlinks are refused by change transfer | PASS (real) |
| E08 | P0 | Host Git never uses the workspace repository's configuration (nested repository, a change after the check, gitlink refused, storage formats) | `test_80_combinations.py` (a clean filter, a diff textconv and fsmonitor set by root in the container are not run by `changes show/export/bundle/inspect`, `check`, `backup create`; control: plain host Git in that workspace runs them); `tests/test_git_boundary.py`, `tests/test_untrusted_workspace.py` (links below the top level of `.git`: unit only); accepted residuals D-025..D-034 | PASS (unit, host; real container) |
| E09 | P0 | A backup without a container keeps the derived system layer; names starting with `-` round-trip; sockets and FIFOs are left out and reported; restore keeps installed packages | `test_10_lifecycle.py` (both distributions); `tests/test_backup_completeness.py` | PASS (real) |
| E10 | P1 | Restore into a second data directory on the same daemon: the image is labelled for that directory, the first directory's cleanup leaves it, its own cleanup removes it; after the backed-up environment is deleted, the first directory's cleanup exits 0 and the restored environment still starts | `test_10_lifecycle.py` (both distributions); `tests/test_image_provenance.py`, `tests/test_cleanup_untagged_parents.py` | PASS (real) |
| E11 | P1 | Custom-image environment: the original image is kept through reconfiguration, backup `--no-system` and restore | `test_10_lifecycle.py` (`ubuntu:24.04`); `tests/test_image_provenance.py` | PASS (real) |
| E12 | P0 | Review flow: sandbox text escaped in the CLI and the dashboard; tracked links leaving the repository refused; attention list; executable bits kept | `tests/test_review_flow.py`, `tests/test_tui_text.py`; real: `test_10_lifecycle.py` (rows E06, E07), `test_50_tui.py` (the dashboard's Changes view) | PASS (unit, host; real) |

## F. Secrets and security

| ID | P | Row | Covered by | Status 6.0.0 |
|---|---|---|---|---|
| F01 | P0 | Hostile values are not executed; profiles are 0600 | `test_20_security.py`: a value with `$()`, backticks, quotes and a newline is delivered byte for byte and never executed; a 0644 profile is reported by `check` and not mounted into new containers; `tests/test_profile_and_import_safety.py`, `tests/test_profile_mounts.py`; dummy keys only | PASS (real, pty) |
| F02 | P0 | Legacy executable `.env` profiles refused; values never shown | `test_20_security.py`; `tests/test_cli_robustness.py`, `tests/test_core.py` (redaction) | PASS (real) |
| F03 | P0 | Profile change and isolation between environments | `test_20_security.py`; `tests/test_profile_mounts.py` | PASS (real, pty) |
| F04 | P0 | No privileged mode, Docker socket, devices or extra mounts | `test_10_lifecycle.py` | PASS (real) |
| F05 | P1 | The user's OpenCode configuration is respected | `test_40_opencode.py` (row G06), `test_80_combinations.py` | PASS (real OpenCode) |
| F06 | P1 | No secrets in inspect output, processes, metadata, logs, backups or requests | `test_10_lifecycle.py`, `test_20_security.py`, `test_40_opencode.py` | PASS (real) |

## G. OpenCode and Agent Context

| ID | P | Row | Covered by | Status 6.0.0 |
|---|---|---|---|---|
| G01 | P0 | Versions are read from the binaries | `test_40_opencode.py`; `tests/test_opencode_versions.py`, `tests/test_hardening.py` | PASS (real OpenCode) |
| G02 | P0 | Registry lookup without host npm; pinned policy | `test_30_faults.py`, `test_40_opencode.py` (the pinned policy refuses other versions without downloading anything); `tests/test_opencode_versions.py` | PASS (real) |
| G03 | P0 | Base and environment update, rollback, failure | `test_30_faults.py` (SIGKILL after the checkpoint, before the start and before the install exec → rolled back), `test_80_combinations.py` (update to 2.1.4 and rollback to 2.2.0); `tests/test_opencode_lifecycle.py`, `tests/test_opencode_versions.py` | PASS (real) |
| G04 | P0 | The first prompt receives the guidance | `test_40_opencode.py` on Debian and Arch with OpenCode 2.2.0: the complete guidance verbatim in the first agent request, network `none`; `fake_llm.py` is the model provider inside the container. Accepted limitation: a real model provider is not tested (no credentials; `README.md`); `tests/test_agent_context_integration.py` | PASS (real OpenCode, pty) |
| G05 | P0 | Agent Context refreshed without recreation; settings reflected | `test_10_lifecycle.py`, `test_40_opencode.py`, `test_80_combinations.py` (`check` compares the mounted Agent Context with the host file, both distributions); `tests/test_agent_context.py`, `tests/test_hardening.py` | PASS (real) |
| G06 | P1 | Existing OpenCode configuration preserved | `test_40_opencode.py`, `test_80_combinations.py` | PASS (real OpenCode) |
| G07 | P1 | `exec` is not managed (no provider profile) | `test_20_security.py` | PASS (real) |
| G08 | P1 | `agent-context show` and `verify`; no secrets or host paths | `test_40_opencode.py`; `tests/test_agent_context.py` | PASS (real) |
| G09 | P2 | Version check on demand only | `test_50_tui.py` (`v`); `tests/test_opencode_versions.py` | PASS (real, pty) |
| G10 | P0 | Initial integrations applied exactly once | `test_15_integrations_quick.py` (Context7 added once, then the user's), `test_80_combinations.py`; `tests/test_integrations.py` | PASS (real) |

## H. Dashboard

| ID | P | Row | Covered by | Status 6.0.0 |
|---|---|---|---|---|
| H01 | P0 | Starts, empty state, quits restoring the terminal | `test_50_tui.py`; `tests/test_tui.py` | PASS (pty, real) |
| H02 | P0 | Keyboard-only navigation and dialogs | `test_50_tui.py`; `tests/test_tui.py` | PASS (pty) |
| H03 | P0 | Create (incl. direct), start, shell, OpenCode, check, settings, changes, backup, restore, versions | `test_50_tui.py` | PASS (pty, real) |
| H04 | P0 | Long operations are asynchronous | `test_50_tui.py` (backup and restore from the dashboard); `tests/test_tui.py` | PASS (pty) |
| H05 | P1 | Return from sessions; sessions end when the dashboard is killed | `test_50_tui.py`, `test_40_opencode.py`, `test_80_combinations.py`; `tests/test_run_hangup.py` | PASS (pty, real) |
| H06 | P1 | 80x24, 100x30, 120x40 | `test_50_tui.py` (100x30), `test_35_prerequisites.py` (80x24 without Docker); `tests/test_tui.py` (all three sizes); the dashboard and keys panel at 80x24 and 120x40 and the direct-workspace consent dialog at 80x24 (complete; Cancel creates nothing) are scripted pty checks with `pty_term.py` in isolated data directories, not a campaign test | PASS (pty) |
| H07 | P1 | Pilot tests | `tests/test_tui.py` | PASS (pilot) |
| H08 | P2 | Texts, empty state, refresh after CLI changes | `tests/test_tui.py`, `tests/test_tui_text.py`; `test_50_tui.py` | PASS (pilot, pty) |

## I. Reliability and release

| ID | P | Row | Covered by | Status 6.0.0 |
|---|---|---|---|---|
| I01 | P0 | Fault injection | `test_30_faults.py`, `test_70_privileged.py`; see D05, D06, D09, E02, G03 | PASS (real) |
| I02 | P1 | No leaks | The campaign's session end (`conftest.py`, `campaign.py`): the run's environments deleted, the product's `disk cleanup --yes` behind a guard, nothing left with the run's data-directory label, tagged images unchanged, no session processes; `test_70_privileged.py` (firewall ruleset and interfaces unchanged) | PASS (real) |
| I03 | P1 | Performance baseline | Median durations per command from the campaign log (every command is logged with its duration); small test workspaces; no targets defined | PASS (real; durations recorded in the run log, no targets) |
| I04 | P0 | Full regression at the release revision | The whole real campaign: `OCS_TEST_DOCKER=1 OCS_TEST_PRIVILEGED=1 OCS_TEST_PIPX_BUILD=1 pytest tests/integration`, both distributions, on the tree of the initial public commit (49 tests, 495 checks); plus `test_10`, `test_35`, `test_40`, `test_50` through a pipx installation of a test tag (193 checks); 0 failed (`BASELINE.md`, "Verification") | PASS (real) |
| I05 | P0 | Documentation matches the code: every command and option named in the product, `README.md` and `docs/` exists; relative links and anchors resolve; code blocks fit 80 columns; the install commands name the release tag; active documents are English; new instructions in the guides were measured | `tests/test_cli_structure.py`, `tests/test_user_docs.py`, `tests/test_language.py`, `tests/test_disclosure.py`; review of `README.md`, `CHANGELOG.md` and the guides against the code and `--help` | PASS (review, unit) |
| I06 | P0 | Release decision: every P0 and P1 row PASS with real evidence or BLOCKED with accepted risk (`RELEASING.md`) | This matrix and `BASELINE.md` | PASS (review): every P0 and P1 row PASS; 6.0.0 is recommended for release as Beta on Arch Linux |

## J, K, L. Readiness and cleanup, distributions, direct workspaces

| ID | P | Row | Covered by | Status 6.0.0 |
|---|---|---|---|---|
| J01 | P1 | Readiness checks are read-only and accurate | `check` in `test_10_lifecycle.py`, `test_30_faults.py`, `test_50_tui.py`, `test_80_combinations.py`; `tests/test_readiness.py` | PASS (real) |
| J02 | P0 | Cleanup removes only this data directory's leftovers; never base images or the build cache | `test_80_combinations.py`, the campaign's session end (cleanup exits 0, nothing left); `tests/test_cleanup.py`, `tests/test_cleanup_untagged_parents.py` | PASS (real) |
| K01 | P0 | Arch image, AUR through `ocs-aur` | `test_10_lifecycle.py`, `test_80_combinations.py`; `tests/test_arch_image.py`, `tests/test_distros.py` | PASS (real) |
| L01 | P0 | Direct workspace checks, consent, preflight; the folder is never deleted | `test_50_tui.py` (the consent text complete at 100x30), `test_80_combinations.py`; the consent dialog at 80x24 by a scripted pty check (row H06); `tests/test_direct_workspace.py`, `tests/test_disclosure.py` | PASS (real, pty) |
| L02 | P0 | A direct workspace is re-checked at every start: the folder replaced by a symlink while stopped → `start` refuses and the container stays stopped; restored → `start` works; delete leaves both folders | `test_25_direct.py` (Debian); `tests/test_direct_restart.py` (also recreation recovery, a restarting settings change, an OpenCode update) | PASS (real) |

## M. Combinations

| ID | P | Row | Covered by | Status 6.0.0 |
|---|---|---|---|---|
| M01 | P1 | Arch + AUR + direct workspace + recreation: the AUR build writes nothing into the folder, container-root files are owned by the user, recreation keeps the package and remounts the folder, delete leaves it | `test_80_combinations.py` (Arch) | PASS (real) |
| M02 | P1 | Backup and restore of a direct-workspace environment: by default the folder is left out and the restore gets an empty managed workspace with a warning; `--include-workspace` brings the files back as a managed copy; the folder is never touched | `test_80_combinations.py` (Debian) | PASS (real) |
| M03 | P1 | OpenCode update (2.1.4) and rollback (2.2.0) with the user's OpenCode configuration and Context7 written at the first start: configuration byte-identical, integrations not re-applied, Agent Context current | `test_80_combinations.py` (Debian) | PASS (real OpenCode) |
| M04 | P1 | Settings change during an open shell session: an in-place change keeps it; a recreating change (network `none`) is announced by the plan and ends the session (exit 137), the manager returns, a new session works, data kept | `test_80_combinations.py` (Debian) | PASS (real, pty) |
| M05 | P0 | Cleanup next to objects it does not own: unlabelled containers, volumes and images named like manager objects and objects of another data directory are neither offered nor removed; this directory's orphan volume is; base images kept | `test_80_combinations.py` | PASS (real) |
| M06 | P1 | An interrupted operation and its recovery (recreation, settings, restore, OpenCode update, delete killed at each step) | `test_30_faults.py` (rows D05, D06, E02, G03) | PASS (real) |

## Counts

90 rows.

| Priority | Rows | PASS | PASS in part | BLOCKED | NOT TESTED | FAIL |
|---|---|---|---|---|---|---|
| P0 | 50 | 50 | 0 | 0 | 0 | 0 |
| P1 | 35 | 35 | 0 | 0 | 0 | 0 |
| P2 | 5 | 4 | 1 | 0 | 0 | 0 |
| All | 90 | 89 | 1 | 0 | 0 | 0 |

- PASS in part: D09 (the host reboot is BLOCKED with accepted risk and a next step).
- I04 and I06 were re-established on the tree of the initial public commit; a later release
  repeats them on its own revision (`RELEASING.md`).
- PASS rows that rest on review, unit, host or pilot evidence by design: A02, A05, I05, I06
  (review), A03 (unit), D10 (lookup logic), E03 (crafted archives against the real extractor),
  H07 (pilot).
- PASS rows with an accepted limitation inside the row: C01 (another user's daemon represented
  by another user's socket), C06 (label forgery through the same daemon), G04 (a fake model
  provider, no real one).
- Accepted product limitations: `docs/security.md` ("Known limitations"); accepted residuals:
  `DECISIONS.md` D-025..D-034.
