# Roadmap and backlog

Priorities: dependable existing workflows, data safety, recovery, compatibility and clear
diagnostics. This backlog is not implementation permission. Execution and verification follow
[CONTRIBUTING.md](CONTRIBUTING.md#task-execution); ordinary work belongs on `develop`, not stable
`main`. Current capabilities are in [ARCHITECTURE](docs/engineering/ARCHITECTURE.md); verification
and release blockers are in [BASELINE](docs/engineering/BASELINE.md) and
[CAMPAIGN](docs/engineering/CAMPAIGN.md). There is no active multi-session roadmap.

## Maintenance and usability

- Verify manager recovery after an authorized reboot of a named hard-interrupted test operation
  (CAMPAIGN B15); same-boot unknown-quiescence refusal is not post-boot recovery proof.
- Offer Recovery Center buttons for remaining journals with working CLI handlers: container
  recreation, restore resume/rollback and deletion. OpenCode/configuration recovery already exists;
  reuse those handlers rather than introducing a parallel mechanism.
- Consider a second managed-session warning after reproducing the usability problem.
- Isolate host-process signal tests from unrelated watchdogs and background-job SIGINT settings;
  suites currently must run serially in the foreground.
- Show metadata-only distribution details in `status NAME` when daemon verification fails.
- Improve the readiness error when the deadline expires just before the Docker CLI starts;
  classification is correct, but the message suggests a CLI failure.
- Run the real campaign on another Linux distribution when a disposable host is available;
  until then, real Docker/OpenCode host evidence remains limited to Arch Linux.
- Add Dockerfile linting or a short first-run terminal recording only for a concrete benefit.
- Signed commits/tags require the owner's key and trust decisions first.

## Deferred options

Revisit only for a demonstrated need, not as stabilization requirements:

- **Environment presets:** reuse validated settings/registries and preserve the separation from
  user-owned OpenCode configuration; no new template framework without a concrete use case.
- **Configuration export/import:** manager settings only, not projects/secrets; validate schema,
  direct paths, ports and profile names, with explicit consent before importing host access.
- **Prebuilt images or an AUR package:** require a distribution/trust/licensing/maintenance plan;
  pipx release tags and local image builds remain the supported path.
- **Further capability drops:** measure real package/AUR/OpenCode compatibility on both images.
- **Dependency locking:** current/lowest-dependency CI is the present guard; add constraints only
  for a demonstrated reproducibility problem.
- **Hosted real-Docker CI:** needs an owner and practical benefit; retain the local release campaign.
- **Documentation website/community policy:** separate community needs, not release reliability gates.
- **Reusable-workflow syntax:** keep the linted release call until actionlint supports `uses: $/...`.
