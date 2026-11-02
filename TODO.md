# Roadmap and backlog

OpenCode Sandbox is Beta. The priorities remain dependable existing workflows, data safety,
recovery, compatibility and usable diagnostics, not feature expansion. Follow
[task execution](CONTRIBUTING.md#task-execution) and [risk-based verification](CONTRIBUTING.md#verification-policy):
group related work, use meaningful checkpoints, and respect assignment-specific STOPs (D-059).
Ordinary work belongs on `develop`; `main` is published stable source/docs. Release integration
and separate publication authorization follow [the branch workflow](CONTRIBUTING.md#branch-workflow)
and [RELEASING](docs/engineering/RELEASING.md) (D-058). This backlog is not work authorization.

## Completed: Updates architecture and UX (unreleased)

The approved D-056/D-057 roadmap **UP-00..UP-18 and PERF is complete on develop**, after the
published 6.1.0 release. Its transient working record is retired under D-045. Durable behavior,
verification, failure trails and explicit limits are consolidated in
[ARCHITECTURE](docs/engineering/ARCHITECTURE.md#manager-update-and-independent-recovery),
[BASELINE](docs/engineering/BASELINE.md#updates-final-integration) and
[CAMPAIGN](docs/engineering/CAMPAIGN.md#updates-final-integration).

- Three independent local/cached-first Updates views retain `v`; optional daily GitHub/npm
  discovery defaults off, never installs automatically and never authorizes mutation from cache.
- Environment actions preserve pins, ownership, data/configuration and existing journals/checkpoints.
  Base actions provide explicit cached/full-refresh builds, immutable consent and retained rollback
  copies without migrating existing containers or pruning shared cache.
- Explicit manager review/update now uses the real terminal/process-death boundary and an
  independent frozen exact-tag pipx executor. Durable admission/state, fresh expected-result checks
  and verify-only recovery remain separate from availability/consent and normal startup leasing.
  Unknown hard-interruption quiescence stays blocked; previous-tag reinstall is manual guidance,
  not guaranteed dependency/offline restoration. Support remains conservative and Beta.
- Final integration: 2220 passed/86 real opt-in skips per selected complete compatibility result,
  changed-component reruns on all four endpoints, and 31 affected real tests/1146 checks, including
  both distributions, public terminal flows and real pipx replacement/recovery. Scope and unexecuted
  layers are explicit in BASELINE; this is not a release-readiness recommendation.

Manager remains **6.1.0**; environment metadata **2**, backup **3**, image definitions unchanged.
The D-058 branch migration preserves this work on `develop` without changing stable `main` or
creating a release. Publishing the development branch is not stable publication or release
readiness. No version bump, release, project tag or remote `main` change is part of the migration.
The broader user-documentation and test-suite reviews remain separate from this instruction-only
workflow improvement. The optional/deferred backlog below is not new implementation permission.

## Delivered in 6.1.0

Simplified Rootless Docker guidance, pipx as the only installation method, the Python 3.11
floor, base-image revision diagnostics, the Debian 13 default with retained-OS provenance,
bounded readiness with socket-activation identity, resource-limit support diagnostics and the
session-termination fix. Details: [CHANGELOG.md](CHANGELOG.md); evidence:
[BASELINE.md](docs/engineering/BASELINE.md); decisions D-047 to D-055.

### Existing evidence to retain, not reimplement

- pipx clean install, tag-based upgrade/downgrade, uninstall and packaged image assets are
  verified; keep these tests.
- Unit CI tests Python 3.11 and 3.14 with the current and lowest direct dependencies (Textual
  4.0 and Typer 0.16) and the Arch userland; do not add a second CI framework.
- Journals, backup validation, ownership checks and cleanup boundaries have unit, host and
  real-campaign evidence. Rerun affected paths after changes; do not replace them with new
  abstractions merely for stabilization.

## Optional Polish

Useful when a concrete usability problem or maintenance saving justifies a small task; not a
reason to postpone the required objectives:

- Recovery Center buttons for the remaining journals that name a working CLI recovery command
  (container recreation, restore resume/rollback and delete). OpenCode update recovery is already
  delivered by Updates. Share existing handlers, not a parallel recovery mechanism.
- A warning before starting a second managed OpenCode session, after reproducing the UX problem.
- A real campaign on another Linux host (for example Debian, Ubuntu or Fedora), if a disposable
  host is available. Record it before calling that host tested; Arch remains the only real-tested
  host otherwise, with the limitation visible.
- Dockerfile linting if a lightweight check adds useful findings beyond build verification.
- A short terminal recording of the verified first-run workflow.
- Signed commits/tags only after the owner chooses and prepares keys.
- Host-process signal tests: count only the test's own session watchdogs (a real session or a
  concurrent suite on the same host makes them fail), and start the child processes with the
  default SIGINT disposition (they fail when pytest runs as a background job that ignores it).
- `status NAME` prints its distribution line only after the daemon is verified; show the
  metadata-only description when Docker is unavailable.
- A readiness deadline reached just before the Docker CLI starts is reported as a CLI failure
  (the classification is correct, the message is not).

## Deferred

Worth keeping, but not needed for a dependable stable release:

- **Environment presets/templates:** built-in or user-defined reusable creation settings. Needs
  the existing validated settings model (D-010/D-021), distribution/integration registries and a
  strict boundary between manager settings and user-owned OpenCode configuration; no template
  framework now.
- **Configuration export/import:** share manager-owned settings, not projects or credentials.
  Needs a versioned schema, validation shared with creation and explicit handling of direct host
  paths, ports and profile names. Never silently import host access.
- **Prebuilt images:** registry trust, signing and package licence obligations are more work than
  their current benefit; keep local builds.
- **An AUR package:** pipx from GitHub remains the recommended application installation method;
  do not create another distribution path during stabilization.
- **Further capability drops** (for example `AUDIT_WRITE`, `SETFCAP`): only after measuring package
  installs on both images; do not trade compatibility for unmeasured hardening (D-033).
- **A dependency constraints/lock file:** existing dependency-range CI is the present regression
  guard; reconsider a lock only for a demonstrated reproducibility problem.
- **Hosted rootless Docker CI:** retain the local release campaign; avoid runner/daemon setup
  infrastructure without a clear maintenance owner and practical benefit.
- **Documentation website and code of conduct:** separate project/community needs, not product
  reliability blockers. Markdown documentation remains the source of truth.
- **Reusable workflow self-repository syntax:** leave the currently linted release call alone
  until actionlint supports GitHub's `uses: $/...` syntax; no stabilization value in churn.

## Retired ideas

Do not port the old installer's package-manager detection, release-pruning option or rootless
setup prompts into a replacement installer/wizard. Removing that installation path eliminates
those tasks; prerequisite diagnostics belong to the application, host setup to upstream and
distribution documentation.
