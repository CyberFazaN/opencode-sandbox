# Deferred features (backlog)

These features are explicitly **out of scope for 6.0.0**. Do not implement them unless an
existing architectural defect requires it. They are recorded with their prerequisites so a
later release can pick them up without guessing.

## Environment presets and reusable templates

Possible capabilities:
- Built-in presets for common use cases (e.g. "offline review", "web development").
- User-defined presets.
- Reusable resource, network, distribution and integration selections.
- Creating an environment from a template in one step.

Architectural prerequisites (already in place, not a template framework):
- One validated settings model for creation parameters (distribution, workspace mode,
  runtime limits, network, ports, provider profile, initial integrations) — produced by the
  central change plan (D-010) and the creation flow (D-021).
- The declarative distribution registry (D-005) and integration catalog (D-009).
- A clear separation between manager-owned settings and OpenCode-owned configuration, so a
  template never claims to manage OpenCode's current plugins/MCP servers.

## Configuration export and import

A related extension of the template system.

Possible capabilities:
- Export an environment's manager-owned configuration without project data.
- Import it to create an equivalent environment.
- Share reusable configurations.
- Exclude secrets by default (provider profiles are never exported; only profile names).
- Validate schema and compatibility (metadata `schema`, distribution ids, manager version).

Prerequisites: the same settings model as templates; a documented, versioned export schema;
validation shared with `create`; explicit handling of host-specific values (direct workspace
paths, published host ports) that must not be imported silently.

## Images and OpenCode

- `doctor` warns when a base image was built from an older image definition than the installed
  manager ships (`org.opencode-sandbox.image-revision` lower than the registry's revision).
  Required before the first release that changes an image definition.
- Default image on Debian 13: Debian 12 (`node:24-bookworm`) has had LTS-only security support
  since 2026-07-11 (until 2028-06-30). Needs a new image revision and a full campaign run.
- Containers: drop further capabilities (e.g. `AUDIT_WRITE`, `SETFCAP`) once measured against
  package installs on both images (D-033).
- Lint the Dockerfiles (hadolint).
- Prebuilt base images on a registry (today every host builds them locally; publishing would
  need registry trust, image signing and licence compliance for the bundled packages).

## Distribution and installation

- An AUR package for Arch Linux.
- Host portability (D-046): `install.sh` finds `python3` as well as `python`, and its package check
  covers other package managers or is dropped in favour of the documentation; `setup-rootless.sh`
  without Arch-specific suggestions; `doctor` checks cgroup controller delegation and reports a
  user-namespace restriction.
- Real test campaigns on other host distributions (for example Debian, Ubuntu, Fedora), recorded
  in `BASELINE.md` and `CAMPAIGN.md` before they are called tested.
- Retire `install.sh` once the pipx installation from GitHub has proven itself (D-042).
- Until then: an installer option to prune old releases, and a constraints/lock file for the
  Python dependencies (D-033).
- A Python requirement below 3.14, if a real test campaign on that Python passes.

## Testing and project infrastructure

- Run the suite against the declared lower bounds (Textual 4.0, Typer 0.16).
- A rootless Docker integration job on hosted CI runners (today the real campaign runs only on
  the maintainer's Arch Linux VM); it would also give real evidence on Ubuntu (D-046).
- A documentation website, if the Markdown documentation outgrows GitHub's rendering.
- A terminal recording of a typical session; a code of conduct; signed commits and tags.

## Dashboard and sessions

- Recovery Center actions for every journal (container recreate-recover, backup restore-resume
  and restore-rollback, opencode update-recover, delete retry). Today the dashboard offers repair
  and the settings-change recovery and names the CLI command for the others (D-032).
- Warning at `run` when a managed OpenCode session is already running in the container.
- Workflows: use GitHub's self-repository syntax (`uses: $/...`) for the reusable CI call in
  `release.yml` once actionlint accepts it (zizmor recommends it; it is ignored inline until then).
