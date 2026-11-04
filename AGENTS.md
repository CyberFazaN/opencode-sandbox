# Instructions for coding agents

Start here for the product contract and agent permissions. [CONTRIBUTING.md](CONTRIBUTING.md)
is the authority for task execution, verification and contributor Git conventions (D-059).

**Local instructions.** If a file `AGENTS.local.md` exists in the repository root (it is ignored by
Git and never published), read it after this file. A maintainer uses it to describe their machine,
a running multi-cycle effort, or permissions for a machine they designated as a disposable test
VM. It can grant what the "Ask first" list below names only where it says so explicitly; it can
never lift the "Never" list.

## Product contract

OpenCode Sandbox is a Python >= 3.11 Typer CLI and Textual TUI that runs OpenCode V2 coding agents
in per-environment containers on the current user's **own rootless Docker daemon** (identity
verified, never assumed). Hosts: Linux distributions that meet the prerequisites (D-046); Arch
Linux is the development and real-test host. Base images come from a distribution
registry (`src/opencode_sandbox/distros.py`): Debian 13 (`node:24-trixie`, default) and Arch
Linux (`archlinux:base-devel`, AUR via `ocs-aur`); OpenCode is the npm package `@opencode/cli`
(2.x only). Preserve user files, persistent environments and configuration; never silently expand
host access. Feature/module details are in [ARCHITECTURE.md](docs/engineering/ARCHITECTURE.md),
not an instruction to inspect or retest every subsystem for every task.

Scope guard: not a general container manager; no repository or package-repository management;
the environment's OpenCode configuration (plugins, MCP servers, settings) belongs to the user —
no automatic provisioning, synchronization or re-application. Explicit config-profile Copy,
Export/Apply and Reload/Empty operate only on the global config tree; Apply detects container
drift against its export baseline. Manager-owned
configuration stays separate from OpenCode and user configuration.

Versions are separate and each has one source of truth: manager
(`src/opencode_sandbox/__init__.py`), OpenCode, distribution, image revision, metadata and backup
schemas. Data of other schema versions is not migrated, and the manager never modifies or deletes
it.

## Orientation and execution

- Read this entry point, applicable local/nested instructions and the relevant parts of
  CONTRIBUTING once per session; consult implementation and reference sections as needed.
  Do not reload the entire engineering record set for each subtask. Check Docker state only
  when the task touches it or must reconcile outstanding test resources.
- Complete small tasks in one continuous cycle; group related work and verify by risk, not by
  roadmap ID or commit count. No automatic STOP after a subtask. Follow the
  [execution and resumption policy](CONTRIBUTING.md#task-execution); explicit STOP instructions
  in the user's assignment still apply.
- Before edits or commits, verify branch and worktree status. Ordinary work belongs on `develop`
  or a topic branch based on it; `main` is published stable source/docs. Preserve unfamiliar work;
  never silently switch branches over changes at risk or discard them. Do not reset, revert or
  delete user work without authorization and scope verification. Hotfix/release integration
  follows [the branch workflow](CONTRIBUTING.md#branch-workflow).
- No rewriting published history, force-push, push, tag, release, upload or remote repository
  change without explicit human permission for that operation. Branch policy is not permission.
- `TODO.md` is the backlog, not implementation authorization. Architecture, decisions, known
  issues and evidence are references under `docs/engineering/`, not a mandatory reading/update
  checklist. [Record ownership](CONTRIBUTING.md#documentation-and-handoffs) explains when to
  update them; historical checkpoint/STOP notes are not current instructions.
- Keep temporary plans, investigations, handoffs and verification notes in ignored
  `.work/agents/<task>/`, never tracked Markdown. Keep permanent instructions concise and durable;
  follow [documentation hygiene](CONTRIBUTING.md#documentation-and-handoffs), not per-task reporting.

## Test-resource safety

Select checks under [the verification policy](CONTRIBUTING.md#verification-policy). When real
operations are needed, escalate from static/focused tests to isolated host checks, disposable
rootless resources, then authorized fault injection/end-to-end checks; this is a safety order,
not a requirement to run every layer for every task.

- Test resources: names `ocs-test-*`, label `org.opencode-sandbox.test=<run-id>` where supported,
  isolated `OPENCODE_SANDBOX_HOME`/`OPENCODE_SANDBOX_CONFIG` under `.work/<run-id>/`, and a manifest
  of created resources. Never delete anything outside that manifest. Finish with guarded product
  cleanup in the isolated data directory and verify no leaks. `tests/integration/` does this.
- Large logs, venvs and artifacts go in ignored `.work/` (short owned pytest basetemps may use
  `/tmp/opencode/`; see CONTRIBUTING). Never store or commit secrets; redact tokens, credentials
  and personal paths in reports. Reuse tooling, not mutable test state.
- Investigate failures; never bypass assertions or replace real integration proof with mocks for
  speed. Report executed layers, skips, failures and unavailable verification honestly; a focused
  PASS is not full regression or release readiness.

## Permissions

There is no blanket authorization. Without asking you may: read the source; edit code, tests and
documents in this checkout; create venvs and files in `.work/`; run the unit suite, linters and
package builds; install Python packages into a venv in `.work/` after checking their origin; use
dummy keys and fake providers.

**Ask first** (unless `AGENTS.local.md` grants it explicitly for a designated disposable VM): the
real campaign (`OCS_TEST_DOCKER=1`: it creates and deletes containers, volumes and images and
builds images on the user's daemon); privileged rows (`OCS_TEST_PRIVILEGED=1`: `sudo`, restarting
or killing the user's daemon); building or deleting base images; `sudo` or package-manager
changes; enabling or starting systemd services; anything under `/etc`, subordinate UID/GID
allocations, firewall or network settings; changing the Docker default context; deleting existing
Docker resources or home data; reboots; opening inbound ports; global installations; destructive
disk operations; real credentials or paid API use; network uploads; any irreversible operation.

**Never:** install the application as root; use `pip --break-system-packages`; mount the host Docker
socket into agent containers; use `--privileged` or host networking to bypass product boundaries;
run `docker system prune` or delete Docker resources you did not create; run `makepkg` as root or
build AUR packages in `/workspace`; open inbound (LAN) ports; chown, chmod or delete a direct host
workspace; copy real credentials into logs; delete user projects; weaken security checks to make
tests pass; silently skip or suppress failing tests.

## Release rule

For explicit release requests such as "Review develop and prepare a new release if warranted", use
the [release prompt](.github/prompts/release.md); this reference alone does not initiate a release.

A release is recommended only when every P0 and P1 row of `docs/engineering/CAMPAIGN.md` is
PASS with real evidence or explicitly BLOCKED with accepted risk and a reproducible next step
(`docs/engineering/RELEASING.md`). Never call a release production-ready because unit tests pass.
