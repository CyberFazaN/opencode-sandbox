# Decisions

Essential rationale and current constraints. IDs stay stable for code/test references and are not
reused; fully superseded entries with no remaining constraint are omitted. Git retains their detail.
[ARCHITECTURE](ARCHITECTURE.md) explains implementation; [BASELINE](BASELINE.md) and
[CAMPAIGN](CAMPAIGN.md) record evidence. A contract change needs a new superseding decision, not
an undocumented change to an old rationale.

## D-001 Separate versions, single sources

Manager version is the literal `src/opencode_sandbox/__init__.py:__version__`, read by packaging.
Manager, OpenCode runtime version, distribution/version, image revision, metadata and backup schema
are independent identifiers; advancing one must not imply the others changed.

## D-002 No schema migration

Unsupported metadata is reported and left untouched; incompatible backup schemas are refused.
No modification/deletion or compatibility layer: parallel migration/recovery logic would increase
the risk of silently taking ownership of unknown data.

## D-003 Own rootless Docker endpoint

Accept only the user's authenticated rootless daemon through a local Unix socket, never remote,
rootful, foreign or proxied Docker. Resolve the configured context once, pin its canonical endpoint
and reverify it for explicit acquisition; drop Docker environment overrides. Names/socket ownership
are not proof and there is no override flag. D-052 defines response-sender authentication; a
same-user socket replacement between check and use remains an accepted residual risk.

## D-004 Container execution identity

Run as container UID 0, mapped to the host user by rootless Docker: package management works and
bind-mounted files remain owned by that user. Non-root container IDs map to subordinate IDs and
cannot generally write host-owned directories. Read the actual namespace map; no host chown or
`--user`/`--userns` workaround.

## D-005 Declarative distribution registry

`distros.REGISTRY` owns distribution-specific image names/assets, tools, smoke checks and labels;
other manager modules consume records rather than branch on distribution names. Build a unique
candidate, verify its immutable OS/tools/OpenCode, then publish. Image labels describe build
provenance, not an existing environment's live binary or packages (D-051/D-056).

## D-006 AUR helper and build identity

`ocs-aur` runs pinned paru as `aurbuild` outside `/workspace`. `no-new-privileges` prevents sudo,
so a short-lived root broker executes only paru's own pacman requests. Require peer UID `aurbuild`
and direct-child relationship to the started paru; PKGBUILD descendants are refused (Yama ptrace
restrictions are part of this assumption). Pass argv/cwd/streams, never shell text.

Reject pacman root/db/config/hook/keyring/sysroot/cache/log redirection, short `r`/`b` clusters and
abbreviations of refused long options; allow only `/etc/pacman.conf`. Refuse wrapper-managed helper
options and any build path/argument under `/workspace`. This prevents a package build from using
the host-bound workspace or broker as a general privilege API, not malicious installed packages:
package scripts run as container root. A libalpm soname upgrade breaks linked paru until rebuild.

## D-007 OpenCode V2 only

Install npm `@opencode/cli`, major 2 only, once per container. Unsupported majors require a manager
release, including when npm's `latest` moves. Provider credentials belong to the session/server
environment; never rely on a background server's previously captured environment.

## D-008 Agent Context delivery and session isolation

Per-environment system configuration includes `/run/ocs-agent/context.md` when enabled (D-065); a
read-only directory bind mount makes atomic host refresh visible. User/project configuration is
not replaced for context delivery. Managed `opencode --standalone`
avoids a background server retaining another launch's provider key. A per-launch token identifies
the exact session to hang up after abnormal manager exit. Real first-prompt evidence is required.

## D-009 Retired initial integration provisioning

Superseded by D-064. Catalogs, provisioning controls and metadata are removed, without compatibility
handlers. Existing user-authored MCP/global config is not proactively edited or erased.

## D-010 Shared settings plan

One CLI/TUI planner/executor binds consent and re-plans under lock. Saved settings apply at first
creation; CPU/memory/PIDs are dynamic, lowering live memory restarts to avoid OOM, network/ports/
profile recreate to avoid inconsistent network state. Preserve the system layer and previous
running state, journal before mutation, and set swap to twice memory so Docker does not retain
an incompatible old swap limit. Only the shared executor writes runtime/profile fields.

## D-011 Conservative cleanup

Ownership is managed labels plus resolved data-directory hash and environment/helper identity,
not names. An environment directory counts as an owner even with unreadable metadata; inventory
Docker before owners, and record owners before creating objects. A moved directory's objects
become foreign, safely. Re-inventory confirmed keys under locks, recheck eligibility/ownership/
references, skip busy resources, never force; interruption is repeatable.

Default cleanup covers orphaned objects, stopped helpers, unused restored images/candidates and
default-destination `.backup-*` remnants. Superseded cleanup adds unused runtime/checkpoint/base
copies and identifiable untagged replaced bases. Never remove existing environments/snapshots,
direct workspaces, exports/bundles/backups, current bases, foreign data or shared build cache.
Sizes are approximate; base copies are daemon-shared, so removal can affect another directory's
future rollback intent. D-056 supplies shared base guards, not a future-intent registry.

## D-012 Direct workspaces are externally owned

Explicit `workspace: {mode, path}` is required; malformed metadata must never default to managed.
No deletion/chown/chmod/restore/recursive modification of a direct path. Require explicit consent,
non-overlapping own-user safe directories, no system/home/data/config/runtime/Docker-root overlap,
unsafe parents/hidden components/sockets/devices/foreign mounts, and a same-user container write
preflight. D-030 rechecks before every mount/start. Backups exclude direct content unless requested;
restores are managed, change transfer refuses direct mode. Host-tool execution remains the user's risk.

## D-013 English active text

Documents, messages, comments and tests are English. Intentional non-ASCII filename fixtures have
explicit allowlists; `tests/test_language.py` is a lightweight guard, not a grammar checker.

## D-014 Local scratch is separate from instructions

Large logs, tools, venvs and run artifacts belong in ignored `.work/`; backlog is `TODO.md`.
Active substantial-work records use D-045/D-059. Generated does not mean safe to delete: nested
repositories, installs and recovery records require purpose/ownership/use checks (D-060).

## D-015 Honest network modes

Only `bridge` and `none`. Measured slirp4netns with disabled host loopback blocks host 127.0.0.1
through its gateway, not the host LAN address or LAN. No egress/LAN isolation claim; checks report
reachability in the actual setup, not a universal network guarantee.

## D-016 Explicit distribution/custom-image metadata

Metadata schema 2 requires registry `distro`, or null with a custom image; backup schema 3 records
both distro and original `custom_image`. Distribution is fixed at creation. Invalid/missing fields
are unsupported, not guessed. Custom images are explicit per-environment choices; managed image
names use `--distro`, not custom-image shortcuts. D-026 preserves original provenance.

## D-017 Registry build verification

Verify registry `/etc/os-release` constraints, every promised executable and smoke command under
the normal no-new-privileges container boundary. Debian pins VERSION_ID 13; Arch pins ID/BUILD_ID
`rolling`, not its changing dated VERSION_ID. This catches broken linked tools such as paru.

## D-018 Guidance reports configured/observed facts

Guidance describes privileges, persistence, workspace mode (never host path), network/resources,
base provenance, not current user configuration or security
enforcement. Observed runtime wins and differences are qualified; failed inspection falls back
with a note, not verification. Network none omits ports. D-051 governs OS/tool provenance;
Focused rendering tests protect these facts, and real first-prompt tests establish delivery.

## D-019 Manager-owned OpenCode lifecycle

Disable OpenCode self-update: it left unsafe permissions/caches and broke the Arch binary.
Explicit manager updates resolve a compatible target before consent, enforce pins/network/stopped
ownership and journal a full-layer checkpoint; identical versions verify without reinstalling.
Failure/interruption restores the checkpoint, never guesses npm completion. Rollback snapshots
the current layer first; home/workspace are preserved, not rolled back. Notify/Manual/Pinned
filter availability separately from execution. D-056 defines base-copy selection and discovery.

## D-020 Read-only readiness and measured reachability

Shared doctor/check/dashboard results are passed/warning/failed/not checked/not applicable;
exceptions are not checked, never success. No environment starts/mutations; only a private cached
report and temporary host-loopback listener. Container probes measure TLS internet connectivity,
token-confirmed host loopback and LAN/gateway response, and compare exact loopback-bound ports.
A profile inode change needs restart. D-050/D-053 distinguish image/resource advisories from
identity; full configured limits and reported support are not measured enforcement.

## D-021 CLI/dashboard share behaviour

Grouped commands, common creation validation/defaults, same terms and underlying handlers; no
parallel TUI implementation. Docker-free metadata/list remains available without a daemon.
Sessions use a per-session watchdog/token for abnormal manager-exit hangup. Commands/options/help,
keyboard/focus, asynchronous operations and small-terminal behaviour have explicit tests; D-054
owns launch signals and terminal restoration.

## D-022 Backup links are data

Store symbolic links verbatim, including absolute/escaping targets; refusing them would reject
ordinary venvs without stopping an agent creating those links live. Extraction never follows them:
exclusive regular files first, links last; reject traversal, special files, duplicate/noncanonical
names, unsafe hardlinks and members beneath non-directories/links. Change transfer has a separate
host-repository constraint (D-028).

## D-023 Current-state engineering records

Records describe supported design/state and applicable evidence, not an action log. D-045 defines
ownership/location, D-059 proportional updates, D-060 removal of obsolete detail.

## D-025 Host Git ignores workspace configuration

Use a private manager-written `GIT_DIR`, HEAD/index snapshots and data-only objects/refs links;
read only storage-format settings without includes. Refuse gitlinks (Git reads nested repository
configuration even without `.gitmodules`), commondir/alternates/config.worktree and unsafe `.git`
structures. Disable lazy fetch. An allowlist cannot cover nested config or check/read races.
Previews need no Docker, at the cost of extra Git processes/index copy; split indexes fail closed.
Live object-store reads retain the read-only race documented in D-033.

## D-026 Preserve image provenance on restore

`custom_image` remains the original choice; `image` may become a derived/restored system image.
File-only restore uses the original custom reference and may pull on first start; managed images
use pull never. Loaded system images are re-labelled for the new environment/data directory via
a never-started labelled container commit, preventing another directory's cleanup claiming them.
Superseded runtime tags are removed only without local environment references.

## D-027 Stop before recreation

Recreation ends running, so stopping automatically avoids a needless manual step and preserves
system-layer consistency. Stop precedes the journal: interruption there leaves a stopped unchanged
container. Never force-remove an externally restarted old container; recovery compares replacement
image identity and refuses until the user stops the conflicting container.

## D-028 Safe host change transfer and display

New tracked/untracked links may enter the source repository only if their targets stay inside;
existing links from the base commit remain unchanged. Validate the patched preflight clone.
Refuse rather than provide an unsafe bypass; users can create needed links after review. Highlight
host-tool/config paths and new executables. Escape sandbox controls/format characters and markup;
never let displayed filenames/content execute terminal/UI instructions.

## D-029 Disclose host-side effects

CLI/TUI direct consent names future host-tool risks (Git/editor/direnv/build files); users must
review before executing those tools. Guidance discloses LAN reachability, and maintenance docs
disclose daemon-shared bases/copies. Consent must fit 80x24, not disappear in clipped prose.

## D-030 Recheck direct paths before every start

Recheck before creation/start, restarting settings changes, recreation recovery and OpenCode
update, before any state change. A changed/unsafe recorded path leaves the container stopped and
no new journal. Dynamic non-restarting updates do not remount. This is a snapshot at start, not
protection against later host sockets/mounts added under the directory.

## D-031 Journals belong to their operation

Recheck state under the environment lock; failure handlers re-mark only their own journal, never
another operation's. Restore/rollback preconditions and initial operation-created metadata carry
the proper journal. Delete removes metadata last so interruption remains visible/retryable.
Configuration merges only planned changes into fresh locked state and restarts only what it stopped.

## D-032 Validated backup metadata and recoverable UX

Require typed manifests and timezone-aware times; pruning groups by environment ID/name and never
deletes invalid-time backups. Restore preserves mtimes and no source path. Remove a failed first
start's never-used container, never a used stopped layer. Snapshot tags have randomness and never
move existing tags. Recovery errors remain full plain text with the correct handler/CLI next step.

## D-033 Hardening and accepted residuals

No symlinks below Git objects/refs/reftable/info and no grafts at each host command. Concurrent
object-data link replacement can affect read-only data; copying whole stores was rejected for cost.
New data/subdirectories are private; existing data-root permissions are not rewritten. Drop NET_RAW/
MKNOD only after measured package compatibility; further drops need evidence. Refuse output inside
any workspace. Missing-image errors retain salvage options, not implicit deletion; failed start
reconciliation prevents managed launch. Shared base guards are D-056.

## D-034 Quality and visible errors

Ruff checks src/tests/GitHub scripts; shellcheck covers `pacman-retry`, `install-opencode.sh` and
`pipx_smoke.sh` when tools are installed. TUI broad catches must report via `core.error_text`;
other broad catches need narrow reasons, not silent conversion of defects into empty results.
Known SandboxError text is shown; unexpected errors include type. Tool absence is an explicit
skip, not a claim those checks ran; Dockerfile RUN instructions are not shellchecked.

## D-036 Package identity

MIT `opencode-sandbox`, repository `CyberFazaN/opencode-sandbox`, independent of OpenCode.
PEP 639 licence metadata/assets ship in wheel/sdist; tests need the checkout and stay out of
sdist. User distribution is pipx release tags (D-042), not an index or host installer.

## D-037 AI provenance disclosure

README prominently states the AI tool provenance, minimal human review, security implications and
evidence limits. AI-assisted contributions remain reviewed and attributable; no unsupported quality
claim substitutes for actual verification.

## D-038 Public scope

Status Beta. Public docs describe supported/current behaviour, not private task narratives;
stable decision/matrix IDs connect design to tests. User guides stay task-oriented. English,
reference and content checks enforce this separation; public release history belongs in CHANGELOG.

## D-039 Local image distribution

Base images are built locally, not published. A separate prebuilt-image distribution needs a
trust/signing/licensing/maintenance decision. Manager, image definition and OpenCode versions
remain separate; D-042 owns application distribution.

## D-040 CI and release gates

Hosted CI covers mocked-Docker/host/pilot/process tests, dependency endpoints, Arch userland,
packaging/pipx and workflow lint. It does not establish real Docker/OpenCode behaviour: the real
release campaign runs on an authorized disposable host. Version tags validate version/CHANGELOG,
run CI and tag-pipx checks, then create a draft release for human publication. No package uploads.
Least privilege: default empty permissions, read-only jobs except draft creation, pinned actions,
no persisted checkout credentials. Weekly image verification publishes no images. RELEASING owns
the complete gates; D-058 owns branch integration, not publication authorization.

## D-041 Task-oriented Markdown documentation

README links guides indexed in `docs/README.md`; `--help` is the command reference. Published daemon
hints point to the setup guide. `docs/images/dashboard.svg` is a deliberate generated user asset
from fake data, not disposable build output. Check links/anchors, commands/options, 80-column
user-guide code blocks, guide indexing and stable-tag examples.

## D-042 pipx release tags, no package index

Install the official GitHub repository at `vX.Y.Z` with pipx; no PyPI, release wheels or second
application installer. Pipx handles interpreter/venv creation and dependencies. Build artifacts are
validation only. Prerequisite diagnostics never install/configure host software, Docker or services.
Uninstall leaves environments, backups, profiles and Docker data intact.

## D-043 Shared prerequisite diagnostics

Identity exit codes: verified 0, proxy 3, mismatch 4, unavailable 5, unsupported 6, missing program 7,
missing context 8; failed/declined check 1, usage/operation error 2. CLI/dashboard/doctor use one
classification. Verify before Docker-operation consent; no-terminal confirmation refuses and names
`--yes`. TUI/profile prompts need a terminal. Missing Git disables previews honestly; it does not
turn a repository into an empty diff or invoke a wizard.

## D-044 Explicit pipx version changes

Pipx upgrade/reinstall retains the recorded tag; changing release requires explicit `install --force`
with another tag. `--python` selects the application's already-installed interpreter independently
of pipx's own. Source-free installs carry image assets. Never overwrite/delete a foreign or
unidentified launcher; inspect collisions and follow trusted old-source uninstall guidance if needed.
Data retention and foreign-launcher safety have real tests (CAMPAIGN B09–B12).

## D-045 Engineering record ownership

Current records are BASELINE (state/evidence/gaps), ARCHITECTURE (implementation), DECISIONS
(rationale), ISSUES (accepted limitations), CAMPAIGN (release risks) and RELEASING (procedure).
New defects use GitHub issues with authorization/private vulnerability reporting. Temporary agent
plans/handoffs live outside tracked docs under ignored `.work/agents/<task>/` (D-061); only durable
findings enter the records above. No routine per-action document updates (D-059/D-060).

## D-046 Host compatibility and evidence

Intended for Linux with own local rootless Docker, namespace/subordinate-ID support, delegated
cgroup v2 CPU/memory/PIDs, Python >=3.11, pipx, Git and an interactive terminal where needed.
Arch Linux is the development/real-test host, not a product prerequisite. Hosted Ubuntu/Arch
userland tests do not establish another host's real Docker compatibility; label untested hosts
honestly. Container distributions are independent of host distribution.

## D-048 Upstream-owned host setup

No application/Rootless Docker setup scripts or replacement wizard. Link upstream Docker and
distribution guidance; diagnose in the shared application without package/service/context/UID or
host-policy changes. Keep root/foreign/proxy refusal and container-local installation assets.
Do not automatically remove legacy installs/user data. Python-minor venv repair belongs to pipx;
legacy launcher removal needs identification and the trusted old release's sources.

## D-049 Python floor and compatibility endpoints

Python >=3.11 is declared by packaging with no application compatibility shim. CI covers
3.11/3.14 current and lowest direct dependencies, package/pipx at both endpoints and rolling
unprivileged Arch. Python 3.12/3.13 are accepted but not separately tested; declared bounds are not
transitive dependency locks. Full real Docker/OpenCode is a release-host gate, not per-Python CI.
Published older tags keep their own metadata; never rewrite them to fit today's interpreter.

## D-050 Advisory base-definition checks

Compare managed distro/revision/version labels with registry definitions without probes/writes.
Old/unknown labels warn; newer definitions need compatibility review, not blind downgrade.
Only an explicit missing-image response proves absence; other errors are not checked and cannot
hide another base's result. Shared doctor/dashboard notices do not gate existing containers or
certify package freshness, and never overwrite active operations.

## D-051 Retain actual base provenance

Debian definition is 13 (`node:24-trixie`); Arch remains rolling. Definition revisions follow the
registry (later package-step and launcher/context changes are D-063/D-065). New base
builds never upgrade existing/derived/restored system layers. Read inherited managed labels from
the owned container/selected image, never infer OS from today's mutable base tag or metadata.
Unknown stays unknown; old definitions do not inherit current tool promises. File-only restore
deliberately chooses the current local base and discards the old layer. Base rollback verifies
the current definition and refuses a Debian-12 copy; retained 12 containers/system backups remain.

## D-052 Bounded authenticated readiness

SO_PEERCRED alone identifies systemd for a valid inherited listener. Therefore enable SO_PASSCRED
before connect and authenticate **every response byte** with one own-user dockerd SCM_CREDENTIALS
sender, executable/start-time/namespace proof and exact rootless option. Never whitelist a service
or trust forwarded HTTP text. Strict bounded protocol validation closes received rights and
refuses malformed/mixed credentials. Recheck process identity to catch PID reuse.
One 10-second context/transport budget retries only typed transient transport failures, never
identity/configuration errors or Docker mutations. Overlapping acquisition may coalesce, not
later explicit verification. Progress/cancel remain responsive; no service/context repair or monitor.
Detailed protocol/cleanup bounds are in ARCHITECTURE, and activation permission is separate.

## D-053 Capability is not enforcement

Rootless identity and Docker accepting limit settings do not prove kernel enforcement. Shared
bounded read-only daemon info checks exact cgroup v2/systemd and CPU quota/period/memory/PID
flags; false warns, missing/malformed/unfamiliar is not checked. Preserve advisory/doctor exits,
no host-policy repair or mandatory systemd query. Container settings are labelled configuration;
real C05 separately reads actual kernel cgroup values on the tested host, not all hosts.

## D-054 Own interactive clients before signal delivery

A catchable signal during Popen return can leave an unowned running child. Defer callable
INT/TERM/HUP only through client-reference/watchdog registration; restore/deliver inside cleanup.
No inherited blocked mask, threaded preexec_fn, worker handler changes or generic wait deferral.
Reap forced termination; restore the original attached input tty in finally, without drain/flush
or substituting another tty. Restoration failure must not replace the original error/exit.
This is not a SIGKILL/power-loss or unavailable-daemon cleanup guarantee.

## D-055 Beta status

Keep Beta: real host evidence is limited to Arch and there has been no independent human
security review. A completed implementation or unit PASS does not imply production readiness;
each release needs applicable evidence and accepted blockers under RELEASING.

## D-056 Independent component updates and recovery

Keep observation/discovery, consent and operation state separate. No universal update engine,
Update All, automatic start/install/restart, configuration reapplication or schema migration.
Base locks are daemon-wide with build/publication separation; immutable rollback selection never
guesses from dates/precedence. Bounded diagnostics/cancellation do not become mutation deadlines.
Environment recovery reuses journals/checkpoints and preserves pins/home/workspace/configuration.

Manager mutation requires exact fresh published source/installation/tool/public-policy consent,
actual origin process death/restored terminal, independent frozen execution under exclusion,
durable child admission, expected installed-result proof and independent recovery. No early lease
release, normal-CLI bypass, cache authority, external interpreter installation/switch or foreign-
launcher takeover. Public TLS/RECORD observations are not signed-code attestation, host build
sandboxing or identical dependency rollback. Unknown descendant quiescence keeps startup blocked;
manual previous-tag reinstall and explicit frozen verification stay separate. ARCHITECTURE owns
the full protocol; CAMPAIGN B13–B15 requires real success/failure/interruption/recovery evidence.

## D-058 Stable main, ongoing develop

`main` holds published stable source/docs; ordinary work/topic branches and next-release records
belong on `develop`. Check/preserve branch/worktree before edits/commits. Review/validate release
candidates before protected integration into main, then separately authorized tags/publication.
Stable hotfixes return to develop. No force push, published-history rewrite, bypassed protection or
inferred remote permission. Stable-tag install guidance and source-matching branch docs remain.

## D-059 Proportional engineering workflow

AGENTS owns the product/permission entry point; CONTRIBUTING owns task execution, risk-based
verification and resumption. Finish small tasks continuously, group related work and use meaningful
integration/risk checkpoints, not per-item STOP/commit/full-suite rules. Focused feedback is not
complete correctness; high-risk boundaries need broader/real proof when warranted. Reuse only
applicable unchanged evidence with honest scope. One lightweight local record suffices for substantial
ongoing work; ordinary tasks need none. Explicit assignment STOPs, dangerous-operation approval,
blocker/decision handoffs, failure investigation, CI and full release gates remain mandatory.

## D-060 Current-state records and selective artifact retention

Owner-authorized consolidation, 2026-11-02. Refines D-045/D-059 record retention: keep current
constraints/rationale, known limitations, recovery requirements and applicable reproducible test
evidence, not every intermediate plan/run narrative. Remove obsolete/superseded detail from active
docs without creating archives; Git retains it. IDs are not renumbered or reused. Disposable local
copies/caches may be removed only after purpose, ownership, references and active use are checked;
unknown repositories, persistent data, credentials, recovery state/inputs and protocol lock inodes
are preserved. This changes no product behaviour, test assertion, CI/release gate or permission.

## D-061 Local-only agent working context

Supersedes D-045's tracked working-record location. Agent plans, investigations, handoffs and
temporary verification records belong in ignored `.work/agents/<task>/`, never tracked Markdown.
Only durable current knowledge belongs in permanent docs; CONTRIBUTING owns the concise hygiene,
completion cleanup and unfinished-work/recovery retention rules. No new framework or routine records.

## D-062 Explicit temporary version checks and running-update consent

Refines D-019/D-056: dashboard Check may temporarily start an existing stopped container solely
for a bounded version probe; passive inventory, CLI version reports and automatic discovery never
start it. Check All confirms stopped targets. Retain lifecycle exclusion through restoration,
including an independent parent-death guard; do not invoke interactive launch/global import or create
missing containers. Unconfirmed cleanup stays visible with exact-identity recovery evidence.
Originally-running targets stay running. A running environment update requires explicit stop
caution before checkpoint/install and finishes stopped, never an implicit restart. Existing
ownership, pin, checkpoint, journal and user-configuration boundaries remain in force.

## D-063 System package upgrades

Every base build upgrades installed packages (Debian `apt-get update` + `upgrade`, Arch full
`pacman -Syu`); a per-build value keeps that layer out of the cache in both modes, so there is no
opt-out and repeated builds publish new images. Existing environments upgrade only on explicit,
default-off request, as the first step inside the journalled OpenCode-update checkpoint: failure
restores it before OpenCode changes. Commands come from the distribution registry; custom images
refuse. Never present rollback as a full undo of package upgrades: changes outside the system
layer and migrated data remain.

## D-064 Explicit whole-global-config transfers

User-maintained profile directories/root symlinks are read-only inputs, never live mounts or
automatically synchronized. Initial Copy requires a fresh volume; later explicit Reload/Empty
and Export/Apply cover the entire global config tree, not effective config, system, project or
other home auth/state. Preserve internal symlink text, modes and file bytes; reject unsupported
entries. Private deterministic /tmp exports bind UID/data-root/stable environment identity and a
validated external marker, not a stored path/session. Baselines hash original/current container
trees, never host edits; overwrite consent binds one observed digest and retains final checks.
Same-volume staging, atomic directory exchange, durable commit/recovery and manager/volume locks
protect replacement across process death. No blanket transaction guarantee against arbitrary
OpenCode writers or hostile same-UID processes is claimed.

## D-065 Optional context activation and one provider launcher

Base system configs are neutral. Persist default-on per-environment activation; always keep the
context generated/mounted and reconcile only its exact system instruction on every managed start,
including recreation/update/temporary checks. Preserve unrelated JSON/list order; malformed configs
fail without resetting them. Stopped changes reconcile at next start; active sessions are never
interrupted. Native user references remain possible. Reserve exactly the three config path/content
provider variables at host and container validation boundaries, with no broad OPENCODE_* ban.
The same stdlib validator powers managed launches and both images' discoverable `ocs-opencode`
executable; private-server semantics, safe JSON/argv handling and conditional interactive hints
replace shell aliases/evaluation or duplicated credential rules.
