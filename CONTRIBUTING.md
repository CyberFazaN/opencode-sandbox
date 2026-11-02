# Contributing

Thank you for helping. Bug reports, documentation fixes and focused pull requests are welcome.
Security problems: please follow [SECURITY.md](SECURITY.md) instead of opening an issue.

This is the authoritative task-execution and development-verification policy. Agents start with
[AGENTS.md](AGENTS.md) for the product contract and concrete permission/safety boundaries.
Engineering records provide design and evidence, not additional routine execution checklists.

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
.venv/bin/python -m pytest -q tests/test_user_docs.py  # example focused check
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

## Task execution

- Keep changes focused and maintainable; avoid speculative rewrites or unrelated work. Read the
  affected implementation and establish expected behaviour from code, `--help` and the
  product contract; flag conflicts. For a defect: reproduce -> find root cause -> narrow patch ->
  regression test -> rerun. A prose typo needs review, not a new application test.
- Complete small, low-risk tasks in one continuous cycle. No formal plan is needed when the
  requirements and approach are clear. Combine related subtasks that share context, dependencies
  and verification; split large/risky work at meaningful implementation, design or validation
  boundaries, not at every roadmap item. Do not repeatedly replan unchanged requirements.
- Checkpoint at a useful integration boundary; it need not end the session. Stop/request input
  for a decision needing approval, an operation needing authorization, missing information, a
  useful milestone handoff, actual context recovery/compaction, or a user-requested stop. Explicit
  STOP requirements in an individual assignment take precedence; general autonomy never expands
  the approved scope or authorizes independent backlog work.
- Make coherent, reviewable commits when requested or agreed. One commit can cover a small task
  or related subtasks; no commit-per-trivial-edit rule. Before committing, review the diff and
  verification scope. Use a short summary, optionally prefixed (`fix(cli): …`, `docs: …`, `test: …`).

### Documentation and handoffs

Update a document only when its owned facts change, not because a commit happened:

- User guides and `CHANGELOG.md` ("Unreleased"): changed user-visible behaviour; neither needs an
  entry for internal process edits or every test-only change. Regenerate the dashboard screenshot
  with `python tests/dashboard_screenshot.py` when its layout changes.
- `docs/engineering/ARCHITECTURE.md`: current design/module boundaries. `DECISIONS.md`: essential
  rationale and constraints for current decisions; append a superseding decision when the contract
  changes. Remove obsolete implementation narratives; Git retains superseded detail (D-060).
- `docs/engineering/BASELINE.md`: changed supported state, meaningful verification checkpoints
  and unverified limits. `CAMPAIGN.md`: affected release-risk evidence/status, not a duplicate
  development log. `ISSUES.md`: accepted limitations; new defects go to GitHub issues (private
  reporting for vulnerabilities). Do not create/upload issues without the required permission.
- `TODO.md`: changed backlog/completion status. For substantial multi-session work, keep **one**
  working record in a subdirectory of `docs/engineering/` (D-045). Keep scope/decisions, completed
  and pending work, relevant verification/limits, outstanding resource manifests and the next
  meaningful step. Update at integration/handoff points, not after every action. Link evidence
  once rather than copying it into a roadmap, baseline and separate handoff. When complete,
  consolidate only durable facts into their owning records and retire the working record. Retain
  applicable verification and unresolved-failure/recovery evidence; Git holds completed plans and
  obsolete history. Inspect ownership, references and active use before deleting generated local
  artifacts. `.work/` is not automatically disposable: it may contain repositories, installations,
  recovery inputs or persistent test data. Never delete it wholesale or remove protocol lock files.

Routine work needs no persistent plan/progress file: a clear commit (when requested) and concise
completion summary with checks and limits suffice. On resumption, read AGENTS and applicable local
instructions, the relevant policy sections and the single active handoff if one exists; check
branch/status and changes since its checkpoint. Reconcile outstanding test resources if relevant.
After compaction, refresh missing/changed instructions and evidence only; do not reread all large
reference files or replay tests solely because the session resumed. Historical stage/STOP notes
describe earlier assignments, not standing orders.

## Test layers

| Layer | What it is | How to run |
|---|---|---|
| Unit, host, Textual pilot | Mocked Docker (`tests/conftest.py`); real files and Git; the dashboard headless | `pytest -q` (no daemon is contacted) |
| Quality | `ruff check src tests .github/scripts` and `shellcheck` on the shell scripts (`tests/test_quality.py`); skipped when the tool is missing | part of `pytest -q` |
| Real identity and sessions | Tests marked `real_identity` and `real_session` run the daemon-identity verifier and session watchdogs as real local processes (against fake sockets and a fake `docker`) | part of `pytest -q` |
| Real campaign | Real rootless Docker, both base images, real OpenCode, real terminals, fault injection (`tests/integration/`) | see below |

`pytest -q` is the complete default suite, not the required command for every local task. It mixes
mocked Docker with real host files/Git, sockets, processes and terminal fixtures; it is not live
Docker/OpenCode proof. For selection, use the [verification policy](#verification-policy) below.

Run host-process suites serially in the foreground: watchdog counts and SIGINT handling are
host-sensitive. Use a fresh, short, run-owned `--basetemp` outside the checkout (under
`/tmp/opencode/` on the test VM), and absolute `PYTHONPATH` for source subprocesses. Hidden paths
inside the checkout trigger direct-workspace/import guards; deep paths exceed Unix socket limits.
Keep logs and manifests under ignored `.work/`; never remove other runs' resources.

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

## Verification policy

Select checks by impact, uncertainty and realistic failure modes, including consumers and trust
boundaries, not just changed file names. Focused tests are development feedback, **not proof of
complete project correctness**. CI and [release gates](docs/engineering/RELEASING.md#2-verify) are
unchanged; do not disable coverage, weaken assertions, suppress failures or substitute mocks for
real verification to save time.

| Change / checkpoint | Local verification |
|---|---|
| Prose/typo/instruction-only | Review the diff and relevant links/anchors/language checks; run CLI-document contracts if command examples change. No full application suite, Docker campaign, image rebuild or packaging replay just for prose |
| Ordinary bug fix / localized UI change | Reproducer/new regression, directly affected tests and neighboring modules/consumers; targeted formatting/static checks. Use relevant pilots/CLI checks, 80x24/larger and current/lowest UI dependencies where rendering/event behaviour is affected. Finish coherently, without an automatic full suite |
| Substantial feature/block, related subsystem integration, shared/public interface change, uncertain impact or accumulated unverified changes | Run the full default suite at this meaningful checkpoint, plus affected integration/compatibility checks. Batch related work; a minor subtask or commit is not itself a full-suite trigger |
| High-risk boundary (below) | Broaden immediately when the failure modes warrant it: full regression/compatibility, adversarial/fault/concurrency tests and affected real scenarios. Do not defer necessary safety proof to a later generic checkpoint |
| Release candidate | Complete regression/compatibility matrix, package/installed-pipx checks, real campaign and every P0/P1 gate or explicitly accepted blocker under RELEASING/CAMPAIGN; no focused or historical substitute |

High-risk selection checklist (apply the affected rows, not every row to every change):

| Boundary | Failure modes / evidence to cover |
|---|---|
| Rootless daemon identity/isolation | Own UID, authenticated `dockerd` peer/user namespace/rootless option; refuse proxies, rootful/foreign/remote daemons; ownership/data-dir labels/collisions; measured `bridge`/`none` reachability, not assumed isolation |
| Filesystem/direct workspaces and host Git transfer | Symlink/traversal/unsafe paths and permissions, hostile Git configuration, uncommitted files/conflicts, export/stage/apply boundaries and preservation of user data |
| Secrets/profiles | JSON permissions, executable `.env` refusal, safe argv/key injection; no leakage in processes, logs, metadata or backups; dummy credentials/fake providers unless explicitly authorized |
| Lifecycle/configuration, locking/concurrency | Creation/start/recreate/cleanup races and lock order, journals/crash consistency, home/workspace/system-layer boundaries, once-only integrations, read-only readiness and no cross-data-directory/base/cache cleanup |
| Backup/restore/rollback/recovery | Archive/link validation, interrupted/staged restore, retained checkpoints/copies, failed recovery and data/configuration preservation; no unsupported-schema migration |
| Manager self-update/destructive operations | pipx tag install/upgrade/downgrade/uninstall/data retention, foreign-launcher refusal, independent helper/terminal handoff, exact installed-result verification and interruption/recovery, not success-path-only checks |
| OpenCode/images/session boundaries | Both affected distributions, supported-major/pin/update/rollback policy, disabled self-update, real first-prompt Agent Context and user-owned configuration; keyboard/focus/confirmation/async errors and terminal/session return or manager death when affected |

Use the Python 3.11/3.14 × current/lowest matrix for shared/security/compatibility integration
checkpoints when those surfaces are affected; choose targeted endpoint checks for narrower risks.
Affected real-Docker/OpenCode paths need both distributions where applicable, and installed pipx/
terminal/fault paths for installation changes. Obtain the permissions in AGENTS first; if unavailable,
report the gap and residual risk, not a PASS. A full default-suite PASS is not real integration proof.

### Avoid redundant checks

- Reuse a result only while the relevant implementation, tests, dependencies, configuration and
  test environment still apply. Review changes since the verified checkpoint and run the checks
  those changes invalidate. Different dependency combinations are distinct evidence, not duplicates.
- Do not replay overlapping commands or identical full suites after every edit/commit, prose-only
  evidence update, compaction or handoff. After a correction, rerun the failure and affected
  neighbors; expand if it reveals broader uncertainty. Investigate failures rather than hiding them
  with retries. A result from earlier code is not a full pass on changed final code: label reused
  full results and new focused checks separately, and state what remains unverified.
- Reuse unchanged verified venvs/tools; check versions/dependency health after setup or dependency
  changes or when uncertain. Do not reuse mutable fixtures/containers. Rebuild images for changed
  build inputs, required refresh/build-path proof or release gates, not for unrelated docs edits.
- Keep verification evidence brief: command/scope, source checkpoint, relevant environment,
  result (including skips/failures) and unexecuted layers. A completion summary suffices for routine
  work; substantial checkpoints may link logs in the single working record or BASELINE. No new
  result-cache framework, parallel runner or shared mutable fixtures are needed for this policy.

Active text is English (`tests/test_language.py`); documented commands/options must exist
(`tests/test_cli_structure.py`) and links/anchors resolve (`tests/test_user_docs.py`). Report layers
accurately: mocked unit, real host files/Git/processes, Textual pilot, real Docker, real OpenCode,
scripted terminal (pty), and manual observation. Never describe an unexecuted layer as passed.

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
