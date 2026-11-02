# Contributing

Thank you for helping. Bug reports, documentation fixes and focused pull requests are welcome.
Security problems: please follow [SECURITY.md](SECURITY.md) instead of opening an issue.

## Scope

OpenCode Sandbox runs OpenCode coding agents in containers on the user's own rootless Docker
daemon, on Linux hosts; Arch Linux is the development and test host (D-046). It is deliberately not
a general container manager, does not manage repositories or package repositories, and leaves an
environment's OpenCode configuration to the user after the first start. Please open an issue to
discuss a larger change or a new feature before writing it; deferred ideas are collected in
[TODO.md](TODO.md).

## Development setup

```sh
git clone --branch develop https://github.com/CyberFazaN/opencode-sandbox.git
cd opencode-sandbox
git status --short --branch
python -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pip install ruff shellcheck-py pyte   # quality gates, terminal tests
.venv/bin/python -m pytest -q
```

Python 3.11 or newer is required. Run your checkout with `.venv/bin/opencode-sandbox`; the local
editable venv is for development only. For normal application installation, use pipx from a
GitHub release tag ([docs/install.md](docs/install.md#install-the-application)). There is no
host/application setup script or replacement wizard in the repository.

## Branch workflow

- `main` represents the latest published stable release, including its matching source and
  documentation. Do not use it for ordinary development.
- Develop all new features, fixes, refactoring and documentation for future releases on `develop`
  or short-lived topic branches based on it. Open ordinary pull requests against `develop`;
  reviewed topic branches are integrated with merge commits. There is no additional permanent
  release branch.
- Before editing project files or creating commits, check `git branch --show-current` and
  `git status --short --branch`. Never silently switch branches if uncommitted work is at risk;
  preserve it and agree on a safe next step instead.
- Review and validate a release candidate from `develop` before integrating the approved work
  into `main`. Stable publication then uses an annotated version tag through the existing
  [release workflow](docs/engineering/RELEASING.md). A temporary `release/X.Y.Z` branch may hold
  candidate preparation; it is not another development line.
- Urgent stable-release hotfixes may use a temporary branch from `main`. Review and validate the
  fix through the same release gates, then integrate it back into `develop` so it is not lost.
- CI validates pushes and pull requests targeting both long-lived branches. Ordinary branch
  pushes do not trigger release automation; that workflow accepts version tags only. The weekly
  image workflow continues to use the repository's default branch and publishes no images.
- Agents need explicit human authorization for remote pushes, remote changes, tags and releases
  (`AGENTS.md`). Only the maintainer creates release tags. Do not bypass branch protection or use
  force pushes; the branch model itself grants no publication permission.

User guides on `develop` evolve with the next release; the matching stable guides remain on
`main` and version tags. Keep release status in `CHANGELOG.md` and engineering records, not
temporary per-release banners throughout user guides. Keep normal installation guidance pinned
to stable version tags, without recommending development installs to ordinary users.

CI runs the unit/host/Textual-pilot/local-process suite with current and lowest direct
dependencies on Python 3.11 and 3.14, plus the current rolling Arch Python as an unprivileged
user. Package and pipx jobs cover both endpoints too. Python 3.12/3.13 have not been separately
tested; full real-Docker/OpenCode verification remains the release campaign, not a per-Python
CI requirement. The 3.11 floor applies from 6.1.0; the 6.0.0 tag still requires Python 3.14.

## Test layers

| Layer | What it is | How to run |
|---|---|---|
| Unit, host, Textual pilot | Mocked Docker (`tests/conftest.py`); real files and Git; the dashboard headless | `pytest -q` (no daemon is contacted) |
| Quality | `ruff check src tests .github/scripts` and `shellcheck` on the shell scripts (`tests/test_quality.py`); skipped when the tool is missing | part of `pytest -q` |
| Real identity and sessions | Tests marked `real_identity` and `real_session` run the daemon-identity verifier and session watchdogs as real local processes (against fake sockets and a fake `docker`) | part of `pytest -q` |
| Real campaign | Real rootless Docker, both base images, real OpenCode, real terminals, fault injection (`tests/integration/`) | see below |

For local iteration, start with the regression and affected modules, then run the complete suite
at a completed code-package checkpoint. Shared/security/data-lifecycle changes need the broader
compatibility and real layers; focused runs are not full regression. The measured costs and
[risk-based cadence](docs/engineering/BASELINE.md#recommended-development-time-cadence) explain
selection and reporting. Reuse verified unchanged venvs, not mutable fixtures; run host-process
suites serially in the foreground. CI and release verification requirements are unchanged.

The real campaign creates and deletes containers, volumes and images on your rootless daemon,
kills and interrupts operations on purpose, and needs both base images, network access and
`pyte`. **Run it only on a disposable machine, such as a VM set aside for testing**, never on a
machine whose Docker data you care about:

```sh
OCS_TEST_DOCKER=1 .venv/bin/python -m pytest -rA tests/integration
```

It works in its own data directory under `.work/`, names everything `ocs-test-*`, writes a
manifest of what it created to `.work/logs/` and removes it again. Variables:

| Variable | Effect |
|---|---|
| `OCS_TEST_DOCKER=1` | Enable the real campaign (otherwise its tests are skipped) |
| `OCS_TEST_DISTROS` | Distributions to test (default `debian arch`) |
| `OCS_TEST_RUN` | Run id, used in names and log files |
| `OCS_TEST_PRIVILEGED=1` | Add the rows that use `sudo` and restart or kill your daemon; read the docstring of `tests/integration/test_70_privileged.py` first |
| `OCS_TEST_SOCKET_ACTIVATION=1` | Explicit permission for C10's separate rootless daemon and temporary `ocs-test-act-*` user units; read `test_36_socket_activation.py`; never restarts the existing daemon |
| `OCS_TEST_PIPX_BUILD=1` | Let the pipx test also build an image from the installed package (downloads a base image) |
| `OCS_TEST_MANAGER` | Run the campaign against an installed launcher (for example a pipx installation) instead of the source tree |
| `OCS_TEST_LEGACY_MANAGER` | Separate pre-change launcher using a retained Debian 12 base, for the old-container/backup compatibility row; without it that row explicitly skips |

The pipx test (`test_65_pipx.py`) needs pipx in the venv (`.venv/bin/pip install pipx`). Hosted CI
(`.github/workflows/ci.yml`) runs only what a hosted runner can show: the unit suite with the
current and the lowest supported dependencies, on Ubuntu and in an Arch Linux container; the
package build and its contents; a pipx installation from the checkout; actionlint and zizmor on
the workflows. The real campaign is run by the maintainer before each release
([docs/engineering/RELEASING.md](docs/engineering/RELEASING.md)). Unit tests alone do not show that
the manager works with real Docker: say in your pull request which layers you ran.

## Making a change

- Keep a change focused, with a regression test for every fix. Read the code rather than the
  documentation to find the expected behaviour.
- User-visible text is English (`tests/test_language.py`). Commands and options named in the
  product, README or `docs/` must exist (`tests/test_cli_structure.py`); links and anchors must
  resolve (`tests/test_user_docs.py`).
- Update the user documentation (`README.md`, `docs/`) and `CHANGELOG.md` ("Unreleased") in the
  same pull request. Regenerate the dashboard screenshot with
  `python tests/dashboard_screenshot.py` when the dashboard's layout changes.
- Changing an accepted design decision needs a new entry in
  [docs/engineering/DECISIONS.md](docs/engineering/DECISIONS.md) that supersedes the old one.
- Never weaken a security check to make a test pass, and never commit real credentials; tests use
  dummy keys and a fake model provider.
- Commit messages: a short summary, optionally with a type prefix (`fix(cli): …`, `docs: …`,
  `test: …`).

## AI-assisted contributions

This project itself was written with an AI coding agent, and AI-assisted contributions are
welcome on the same terms as any other:

- Say in the pull request that an AI tool was used, and which.
- You are responsible for the change: you have read it, understand it, can explain it in review,
  and have run the tests you report.
- No large generated changes without a prior issue, and no unreviewed bulk output (mass
  reformatting, speculative rewrites, generated documentation that nobody checked).
- Instructions for coding agents working in this repository are in [AGENTS.md](AGENTS.md).

Every pull request is reviewed by the maintainer before it is merged.

## Licence

By contributing you agree that your contribution is licensed under the project's MIT licence
([LICENSE](LICENSE)).
