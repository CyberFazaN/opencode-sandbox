# Roadmap and backlog

OpenCode Sandbox is Beta. The priorities remain dependable existing workflows, data safety,
recovery, compatibility and usable diagnostics, not feature expansion. Work proceeds one
coherent task per cycle: investigate, implement, verify, document, commit on a topic branch,
merge when verified, then stop.

## Active: Updates architecture and UX

Approved, unpublished development after 6.1.0 (D-056). The complete design, sequenced tasks,
dependencies, acceptance criteria, verification matrix and next-cycle handoff are in the
[Updates working roadmap](docs/engineering/updates/ROADMAP.md). This is the active effort;
the optional and deferred items below are not competing implementation permission.

Priority: correctness/reliability fixes -> shared observations/discovery -> compact Updates TUI
and existing operations -> explicit base refresh -> verified pipx manager self-update.
Keep the three component lifecycles independent. Manager self-update must not delay the earlier
work. D-057 groups UP-07 + UP-08, UP-10 + UP-09 (UI first; no scheduler prerequisite), UP-12 +
UP-13, and UP-14 + UP-15: nine remaining cycles at approval instead of thirteen. UP-10 is now a
verified split checkpoint; UP-09, UP-11, UP-12/UP-13, UP-14/UP-15 and UP-16 are complete too, and two later packages remain. Base refresh does not depend on environment recovery; manager discovery does not
depend on base refresh. Tightly
related subtasks may share a cycle with focused commits and tested handoffs; stop at a coherent
package or safety boundary, not mechanically after each ID. Environment recovery, manager
handoff, replacement and failure recovery retain independent verification gates. The working
roadmap is authoritative for this effort's workflow, superseding older one-task/STOP wording.

Current checkpoint: UP-00..UP-16 complete. Explicit reports, honest partial inventory, shared
base guards, identity-bound rollback and bounded diagnostics/owned probe cleanup are in place.
Packaged Debian 13/Arch races and retained-image diagnostic checks pass; long mutations keep
their existing timing. Dashboard advisories now replace/clear by category without erasing active
progress. Identity-bound disposable version evidence now retains stopped history/Unknown;
bounded compatible stable discovery, Manual/Pinned explicit comparisons and exact confirmed
targets preserve policy/lifecycle restrictions. Four complete compatibility suites and scoped
real Debian/Arch update/rollback/recovery/restore/probe checks pass (BASELINE).
UP-10 now replaces Versions with three compact local/cached-first Updates views, explicit
independent Check/Details and owned cancellation at 80x24/larger. Opening does not contact the
network or execute version probes; stopped checks never start containers. Manager discovery
now has independent read-only release/installation evidence; manager execution remains unavailable.
The approved UP-10/UP-09 package was split after the verified UI because of its scope and
real-terminal fixes.
UP-09 adds default-off dashboard-only daily npm discovery, persisted attempt claims across
failures/restarts/interruption, cross-caller/process source coalescing and a quiet policy-filtered
cached-availability indicator. Explicit refresh remains available; Retry-After still applies.
No automatic starts, runtime/image probes, installations or service. Four complete compatibility
suites and affected real lifecycle/terminal checks pass. UP-11 now binds explicit environment
Start/Update/Policy/Rollback/Recover with exact consent, locked revalidation and app-owned mutation
workers. Recovery success/failure has independent real evidence, including missing checkpoints,
failed removal and routing to configuration recovery; metadata/journals remain authoritative.
UP-12/UP-13 now bind Base Images Build/Rebuild/Rollback and explicit cached/full-refresh modes
with immutable consent, retained copies, bounded UI build output and existing handlers. Real
cached reuse and pull/no-cache package-layer rebuilds pass separately on both distributions,
alongside concurrency, pinned creation, retained layers and terminal selection/worker ownership.
Four complete compatibility suites and the affected 24-test real gate pass (BASELINE).
UP-14/UP-15 add official published-full-release GitHub discovery, source-scoped daily claims,
independent failures, strict tags/no downgrade and conservative local pipx provenance/settings
classification. Opening stays network-free, manager Update stays disabled, and unsupported/
editable/foreign/shadowed/ambiguous installations receive manual guidance. Four complete suites
(1611 passed/82 skips each) and 26 affected real tests/637 checks pass, including isolated real
pipx/source/options/launcher and manager terminals; local provenance is not public commit authentication.
UP-16's first verified safety checkpoint adds a stdlib-only early console bootstrap and canonical-
prefix process-lifetime shared usage/internal exclusive guards, across data/config overrides.
Supported live dashboards, workers, CLI sessions and commands block exclusive access; startup
refuses it before dispatch. Private persistent lock inodes, lock order and fork/exec descriptor
ownership have real-process regressions. Four complete suites (1655 passed/84 skips each) and
29 affected real tests/702 checks pass, including actual installed pipx lifecycle/launchers and
live session/mutation exclusion. This is a split checkpoint, **not completion of UP-16**.
UP-16's second verified trust checkpoint adds internal dated external pipx/Python/runtime and
dependency-inventory assessment, with literal source-Python selection and effective-location
preservation. It rejects target-dependent symlink routes, lazy/absent declared paths, unsupported
pipx/metadata and unsafe inputs without a grant. Four complete suites (1702 passed/84 skips each)
and 29 affected real tests/714 checks pass, including actual external pipx with the owned manager
venv temporarily absent. No startup/status/UI consumer or new public command executes this probe.
UP-16's third checkpoint stages a private frozen stdlib helper outside the installation and
exercises only a non-mutating process-exit fixture. A pidfd, not main return or socket EOF, proves
origin termination before a non-waiting exclusive attempt. Existing process-lifetime leases stay
intact. This is not verifier access, terminal handoff or installation authority.
UP-16's fourth checkpoint adds dedicated fixed read-only fresh runtime access under the helper's
exclusive guard, with an unlocked read-only witness, kernel owner-fd proof, close-before-query and
startup parent-death protection. No exclusive descriptor is exported. Normal CLI startup remains excluded; runtime facts are not source/launcher
authentication or replacement success. The fifth checkpoint completes UP-16 with an internal-only
CLI/TUI non-mutating handoff: active work/sessions refuse, actual worker bodies remain tracked
after task cancellation, and clean driver shutdown/exact foreground tty restoration precede
arming. The helper still waits for actual process death; no lease is released early. Four complete
suites (1861 passed/84 skips each) and 29 affected real tests/872 checks pass, including installed
pipx/real-terminal, Debian/Arch mutation and attached-session refusals. No public trigger or install
path exists. Next: UP-17 exact source/target consent, replacement verification and independently
verified failure recovery. Manager Update stays disabled. No version bump, release preparation,
merge, push or publication.
The one-time test-performance checkpoint between UP-06 and that package is complete: two
test-local improvements preserve all test IDs/results and reduce measured full wall time by
about 8%; findings and recommended verification cadence are in
[BASELINE](docs/engineering/BASELINE.md#test-performance-and-local-verification). No application
or CI/release gate changed; its cadence and all broader verification requirements remain in force.
The manager version remains 6.1.0.
Completion does not authorize a merge, version bump, release preparation, tag, push or publication.

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
  (container recreation, restore resume/rollback and delete). OpenCode update recovery belongs
  to the active Updates effort. Share existing handlers, not a parallel recovery mechanism.
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
