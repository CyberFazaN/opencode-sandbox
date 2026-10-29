# Instructions for coding agents

These instructions are for AI coding agents (and the humans who direct them) working on this
repository. Human contributors: [CONTRIBUTING.md](CONTRIBUTING.md) has the same rules in short
form.

**Local instructions.** If a file `AGENTS.local.md` exists in the repository root (it is ignored by
Git and never published), read it after this file. A maintainer uses it to describe their machine,
a running multi-cycle effort, or permissions for a machine they designated as a disposable test
VM. It can grant what the "Ask first" list below names only where it says so explicitly; it can
never lift the "Never" list.

## Product contract

OpenCode Sandbox is a Python >= 3.14 Typer CLI and Textual TUI that runs OpenCode V2 coding agents
in per-environment containers on the current user's **own rootless Docker daemon** (identity
verified, never assumed). Hosts: Linux distributions that meet the prerequisites (D-046); Arch
Linux is the development and real-test host. Base images come from a distribution
registry (`src/opencode_sandbox/distros.py`): Debian 12 (`node:24-bookworm`, default) and Arch
Linux (`archlinux:base-devel`, AUR via `ocs-aur`); OpenCode is the npm package `@opencode/cli`
(2.x only). It supports scratch, project and quick environments; managed workspaces (empty or a
copy) and, not recommended, direct host workspaces; provider credential profiles; Git change
review and transfer; backup and restore; snapshots, recreation and recovery; resource, network
and port settings through one change plan; OpenCode version policies, updates and rollback;
one-time initial integrations (Context7 by default); readiness checks; disk usage and safe
cleanup; and injected sandbox guidance (Agent Context). Preserve user data and never silently
expand host access.

Scope guard: not a general container manager; no repository or package-repository management;
after the first start the environment's OpenCode configuration (plugins, MCP servers, settings)
belongs to the user — no ongoing management, drift detection or re-application. Manager-owned
configuration stays separate from OpenCode and user configuration.

Versions are separate and each has one source of truth: manager
(`src/opencode_sandbox/__init__.py`), OpenCode, distribution, image revision, metadata and backup
schemas. Data of other schema versions is not migrated, and the manager never modifies or deletes
it.

## Records

`docs/engineering/` holds the current-state maintainer records (D-045): `BASELINE.md` (state, test
commands, latest verification, unverified behaviour), `ARCHITECTURE.md`, `DECISIONS.md` (D-0xx;
changing an accepted decision needs a new entry that supersedes it), `ISSUES.md` (known issues
and accepted limitations; new issues are GitHub issues), `CAMPAIGN.md` (the release test matrix)
and `RELEASING.md`. Keep them true when the code changes. Deferred ideas go to `TODO.md`; do not
implement them unasked. User documentation: `README.md` and `docs/`.

## Working discipline

1. Read the implementation rather than trusting documentation; establish expected behaviour from
   code, `--help` and this contract, and flag conflicts.
2. For every defect: minimal reproducer -> root cause -> narrowly scoped patch -> regression test
   -> rerun. Prefer simple maintainable solutions; avoid speculative rewrites and feature creep.
3. Work on a topic branch with focused commits; never rewrite published history, force-push,
   push, tag, publish releases or change remote repositories without the human's permission.
4. Run operations in increasing risk order: static and unit tests -> isolated data and
   configuration directories -> disposable rootless containers and volumes -> destructive fault
   injection on named test resources -> dashboard and end-to-end OpenCode.
5. Test resources: names `ocs-test-*`, the label `org.opencode-sandbox.test=<run-id>` where the
   product allows it, isolated `OPENCODE_SANDBOX_HOME`/`OPENCODE_SANDBOX_CONFIG` under
   `.work/<run-id>/`, and a manifest of everything created. Never delete anything that is not on
   the manifest; finish with the product's own cleanup in the isolated data directory behind a
   guard, and verify that nothing leaked. The real campaign in `tests/integration/` does this.
6. Large logs, venvs and temporary artifacts go to the ignored `.work/`. Never store secrets;
   redact tokens, credentials and personal paths in reports.
7. Never report unexecuted tests as passed. Report layers separately: unit (mocked Docker), host
   (real files and Git), real Docker, real OpenCode, Textual pilot, real terminal (pty), manual
   observation.
8. Active documents and messages are English (`tests/test_language.py`); every command and option
   named in the product, README or `docs/` must exist (`tests/test_cli_structure.py`); links and
   anchors in the documents resolve (`tests/test_user_docs.py`).

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

**Never:** run the installer as root; use `pip --break-system-packages`; mount the host Docker
socket into agent containers; use `--privileged` or host networking to bypass product boundaries;
run `docker system prune` or delete Docker resources you did not create; run `makepkg` as root or
build AUR packages in `/workspace`; open inbound (LAN) ports; chown, chmod or delete a direct host
workspace; copy real credentials into logs; delete user projects; weaken security checks to make
tests pass; silently skip or suppress failing tests.

## Technical risks to validate

- `install.sh` install/update/uninstall/doctor/verify/setup-rootless, symlink ownership, atomic
  release switch and manual rollback; non-interactive behaviour; root refusal; consent for writes.
  pipx installation from a tag, upgrade by tag, uninstall (`tests/integration/test_65_pipx.py`).
- Daemon identity (`runtime_identity.py`: own UID, `dockerd` peer, user namespace, `rootless`
  option; proxies, rootful, other users' and remote daemons refused), container ownership and
  data-directory labels, collision safety, no privileged host access, network `bridge` versus
  `none` and the measured reachability claims.
- Data boundaries: managed and direct workspaces, the persistent home volume, the container's
  system layer, `docker commit` limitations; recreation, settings changes and crash recovery
  through journals.
- Provider JSON permissions, rejection of executable `.env` profiles, key injection and shell
  safety, secret leakage to process listings, logs, metadata and backups.
- OpenCode installation in both images, latest-version lookup without host npm, per-environment
  update and rollback, pinned policy, base rollback copies, disabled self-update, and real
  first-prompt Agent Context delivery; respect existing OpenCode configuration.
- Initial integrations applied exactly once; readiness checks read-only; cleanup never touches
  objects of another data directory, base images or the build cache.
- Git change export, bundles, staging and apply: symlinks, file names, uncommitted files,
  permissions, conflicts; backup archive traversal and symlink checks and restore transaction
  safety.
- Dashboard keyboard navigation, focus, modals, confirmations, asynchronous operations, errors,
  80x24 and larger terminals, and returning from interactive OpenCode and shells (sessions hung
  up, also when the manager is killed).

## Release rule

A release is recommended only when every P0 and P1 row of `docs/engineering/CAMPAIGN.md` is
PASS with real evidence or explicitly BLOCKED with accepted risk and a reproducible next step
(`docs/engineering/RELEASING.md`). Never call a release production-ready because unit tests pass.
