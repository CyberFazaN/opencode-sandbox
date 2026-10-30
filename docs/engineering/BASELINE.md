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

## Verification

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
| `TODO.md` | Roadmap: what 6.1.0 delivered, optional polish and deferred features |
| `docs/engineering/BASELINE.md` | This file: current state |
| `docs/engineering/ARCHITECTURE.md` | Current design and module map |
| `docs/engineering/DECISIONS.md` | Decisions D-001..D-055 with rationale |
| `docs/engineering/ISSUES.md` | Known issues and accepted limitations |
| `docs/engineering/CAMPAIGN.md` | Release test matrix: 84 active rows, seven installer-only rows retired; historical evidence distinguished from the release tree's pending gates |
| `docs/engineering/RELEASING.md` | Release checklist and tag procedure |
