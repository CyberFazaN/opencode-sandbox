# Baseline — OpenCode Sandbox 6.0.0

The current state of the project: version, supported environments, how to test, the latest
verification, known issues and what is not verified. Update it whenever one of these changes
(`AGENTS.md`, D-045).

## Version

| Item | Value |
|---|---|
| Manager version | `6.0.0` (single source: `src/opencode_sandbox/__init__.py`), Beta; the initial public version |
| Distribution | `opencode-sandbox`, installed with pipx from the GitHub repository at a version tag (D-042, D-044); MIT (`LICENSE`), owner CyberFazaN (D-036) |
| Branch | `main`; topic branches are merged with merge commits; releases are annotated tags `vX.Y.Z` (`RELEASING.md`) |
| Schemas | environment metadata 2, backup 3; other schema versions are not migrated (D-002) |

## Supported environments

- Host: Linux with the prerequisites of D-046; real evidence on Arch Linux only (hosted CI adds
  the fake-Docker unit suite and a pipx installation on Ubuntu 26.04). Python >= 3.14 (tested
  3.14.8, CI 3.14.9); Git (tested 2.56.0); the user's own rootless Docker daemon (tested 29.9.2,
  rootlesskit, slirp4netns, overlayfs, containerd image store; cgroup v2 with `cpu memory pids`
  delegated by systemd 262).
  Rootful, other users' and remote daemons and socket proxies are refused by design.
- Python dependencies: Typer (tested 0.27.3), Textual (tested 8.2.8). Installation: pipx (tested
  1.18.7). Tests: pytest; real terminal tests: pyte 0.8.2; quality gates: ruff 0.17.3, shellcheck
  0.11.0 (`shellcheck-py`).
- Sandbox images: Debian 12 (`node:24-bookworm`, default) and Arch Linux (`archlinux:base-devel`,
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

## Verification

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
| Secrets and personal data | gitleaks 8.30.1 (`git` and `dir` modes): no leaks; detect-secrets 1.5.0: 6 findings, all deliberate dummy values in tests; no home paths, user or host names, private addresses (only rootlesskit's documented `10.0.2.2`) or personal e-mail addresses |
| Real terminal, scripted | dashboard at 80x24 and 120x40, direct-workspace consent dialog at 80x24 |
| Documents | README rendered at 80 columns and read; commands, options, links and anchors checked by tests |

Release matrix: `CAMPAIGN.md` (90 rows): P0 50 PASS, P1 35 PASS, P2 4 PASS and 1 PASS in part
(D09: host reboot BLOCKED, accepted); no FAIL, no NOT TESTED. Run logs stay on the test machine
(`.work/logs/`) and are not part of the repository. The campaign prints `DeprecationWarning`s of
Python's `pty.forkpty()` (the test process has threads when it opens a terminal); no effect was
observed.

## Known issues

No open defect. Known issues of the release and the limitations accepted by design: `ISSUES.md`.

## Unverified behaviour

- A real model provider with OpenCode 2.x (the first prompt was verified with a fake
  OpenAI-compatible provider inside the container).
- A host reboot (daemon restart, stop/start and a SIGKILL of the daemon unit were tested). Next
  step: reboot, then `opencode-sandbox start NAME` and `check NAME` on a test environment.
- Another user's real rootless dockerd (another user's socket and a real rootful dockerd were
  refused).
- An actual package installation by `install.sh --offer-packages` (declined at pacman's prompt).
- pipx from GitHub over `git+https` before the first release (the same mechanism was measured
  with `git+file` clones and local test tags), pipx versions other than 1.18.7, and a pipx whose
  Python is older than 3.14 (expected: pip refuses the `requires-python` range).
- The release workflow on GitHub (the draft release) and the scheduled image build (`images.yml`).
- Typer 0.16.0 with Click 8.5 warns that Click 9 removes helpers it imports: the lower bound may
  have to rise when Click 9 is released (the lowest-dependencies CI job shows it).
- Real rootless Docker on hosts other than Arch Linux (D-046), a host without systemd, and a host
  without delegated cgroup controllers; Python other than 3.14.8 and 3.14.9; Textual 4.0 (the declared lower bound) in
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
| `TODO.md` | Deferred features (not implemented) |
| `docs/engineering/BASELINE.md` | This file: current state |
| `docs/engineering/ARCHITECTURE.md` | Current design and module map |
| `docs/engineering/DECISIONS.md` | Decisions D-001..D-045 with rationale |
| `docs/engineering/ISSUES.md` | Known issues and accepted limitations |
| `docs/engineering/CAMPAIGN.md` | Release test matrix (90 rows) with the 6.0.0 status |
| `docs/engineering/RELEASING.md` | Release checklist and tag procedure |
