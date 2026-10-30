# Roadmap and backlog

OpenCode Sandbox is Beta. The priorities remain dependable existing workflows, data safety,
recovery, compatibility and usable diagnostics, not feature expansion. Work proceeds one
coherent task per cycle: investigate, implement, verify, document, commit on a topic branch,
merge when verified, then stop.

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

- Recovery Center buttons for the journals that currently name a working CLI recovery command
  (container recreation, restore resume/rollback, OpenCode update and delete). Share existing
  handlers; do not introduce a parallel recovery mechanism.
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
