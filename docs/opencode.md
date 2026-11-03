# OpenCode in the sandbox

## Sessions

`run NAME` starts OpenCode V2 as root in `/workspace` with the provider profile's variables:
`opencode --standalone`, a private OpenCode server per launch. (The V2 background service would
keep the environment of whichever client started it first, so the provider keys of later
launches would be ignored.) `shell NAME` opens a root bash with the same variables; OpenCode
started from there, or from `exec`, also reads the Agent Context, but `exec` does not load the
provider profile.

If the terminal closes or the manager process ends (also by `SIGKILL`, through a per-session
watchdog), the manager hangs up the session inside the container, like a real terminal would;
jobs started with `nohup` survive.

Your own OpenCode configuration is left alone: `~/.config/opencode/` in the home volume,
project `opencode.json` and `AGENTS.md` files, and an `OPENCODE_CONFIG_CONTENT` value in the
provider profile. The manager writes OpenCode's configuration only once, for the
[initial integrations](workspaces.md#initial-integrations).

## Agent Context

The manager writes guidance for each environment that tells OpenCode about the sandbox. It
states only what the manager configures or verifies:

- **Container, user and privileges:** the image; container root (UID 0) mapped by rootless
  Docker to your host user (custom images: the image defines the user); `no-new-privileges`
  (sudo and setuid cannot raise privileges); no Docker socket, host services or host package
  managers; host files only at `/workspace` (plus read-only manager files under `/run`).
- **Workspace and persistence:** the environment's name and kind; whether `/workspace` is a copy
  of a host directory, started empty, or a host directory mounted directly (every change is
  immediate in your files, no undo, not in backups by default; the host path is never named);
  quick sessions are disposable; what survives stop and start, recreation, settings changes and
  restores.
- **Network and resources:** the network mode, published ports (host loopback only; servers must
  listen on `0.0.0.0`), CPU, memory and process limits. When the container exists, the values
  come from Docker; if they differ from the configuration, the guidance reports the container's
  values and says that the configuration applies after recreation.
- **Operating system:** the base OS version from the owned container's inherited build labels,
  or the selected image when no container exists; never guessed from today's registry or an
  image name. Derived/restored images retain their base provenance. Only a matching current
  definition gets its verified tool list/notes; an older definition does not inherit new tool
  promises. Missing/offline provenance is unknown. Labels describe the base, not later changes
  inside the container; inspect `/etc/os-release` only when needed. Custom images get no OS or
  tool claims.
- **Initial integrations:** the names requested at creation and the recorded outcome of the
  one-time setup (or "not done yet"), always followed by "may have been changed or removed
  since"; never what is configured now.
- **Working behaviour:** start with the task, no system inventory, follow the project's
  `AGENTS.md`; OpenCode's own update check is off, so do not run `opencode upgrade`.

**Delivery.** The guidance lives on the host in the environment's `agent-context/` directory,
which every container mounts read-only at `/run/ocs-agent/` (file `context.md`). The managed
images contain the system configuration `/etc/opencode/opencode.json` with only
`"instructions": ["/run/ocs-agent/context.md"]`. OpenCode combines `instructions` from all its
configuration files, so the guidance is added to your configuration, never replaces it. A
custom image without that file gets no guidance; `run` warns.

**Freshness.** `run` and `shell` regenerate the guidance from current metadata and the
container's settings before every launch, and a refresh is visible in a running container at
once. Commands:

```sh
opencode-sandbox agent-context show NAME     # preview
opencode-sandbox agent-context verify NAME   # compare with the container
opencode-sandbox agent-context refresh NAME  # rewrite now
```

They fall back to the configured settings (with a note) when Docker cannot be asked, with an
unknown OS version rather than today's default. The dashboard's Agent Context preview (`a`)
also explains this fallback and leaves the on-disk guidance unverified when container inspection
fails; a configuration-only preview cannot establish that saved observed guidance is outdated.
The guidance is descriptive, not a security policy. It was verified with OpenCode 2.1.4 and 2.2.0 on
Debian and Arch by capturing the first model request of a managed `run` with a fake provider,
and with one real provider: OpenRouter (`z-ai/glm-5.3-flash`, OpenCode 2.2.0, Debian 13)
answered from the guidance in the first prompt.

## Versions

Only OpenCode 2.x (npm package `@opencode/cli`) is installed or pinned. `latest` selects the
highest supported stable version even if npm's latest tag moves to another major; prereleases
are excluded by default. An exact compatible alternative, including a prerelease, can be selected
with `--version`. Unsupported majors are never installed. OpenCode in a sandbox is installed and updated only by the manager:
every container runs with `OPENCODE_DISABLE_AUTOUPDATE=1`, so OpenCode's own update check and
self-update (also `update: auto` in your OpenCode configuration) are off. The upstream updater
has left unsafe permissions/caches and broken the Arch binary; use the manager's update commands.

`opencode rollback-base` verifies a copy against the installed manager's current OS definition.
A Debian-13 manager therefore refuses a Debian-12 base rollback copy; this is not an in-place
OS downgrade tool. Retained Debian 12 containers and backups with their system image still
work independently of the new base definition. Per-environment OpenCode update/rollback keeps
that environment's OS and system layer.

| Command | Does |
|---|---|
| `opencode check [--distro ID]` | Compares a base image's version with the npm registry (over HTTPS, no host npm, no background checks) |
| `opencode versions [--check]` | Running versions or dated last verification/Unknown for stopped containers; `--check` compares every policy with npm's latest supported stable release |
| `opencode status NAME` | One environment's actual/last-verified version, source, time and immutable object identity |
| `opencode policy NAME`, `opencode policy-set NAME notify\|manual\|pinned [--version X]` | The update policy |
| `opencode update NAME [--version X] [--update-system-packages] --yes` | Update a stopped environment; optionally upgrade its system packages first |
| `opencode rollback NAME --yes` | Undo its last update |
| `opencode update-recover NAME` | Finish an interrupted update (rolls back) |
| `opencode update-base [--version X] [--distro ID] [--refresh]` | Build/rebuild a base image, keep a rollback copy; every build upgrades system packages, refresh also pulls/bypasses cache |
| `opencode rollback-base [--distro ID] --list` | List distinct managed rollback images, full IDs and tag aliases (read-only) |
| `opencode rollback-base [--distro ID] [--copy TAG_OR_FULL_IMAGE_ID] [--yes]` | Verify and swap the selected copy; default only when there is one distinct image |

**Partial results.** `opencode versions --check` keeps available local version/policy rows when
npm discovery fails; a failed discovery is not an up-to-date result. Registry results also
remain available if local inventory fails. Per-environment inspection, policy or formatting
errors are reported without hiding other environments. Available rows go to stdout, errors to
stderr; any report error gives exit status 2. Without `--check`, the command never queries npm.
Neither mode starts stopped or not-yet-created containers, changes policy, or installs updates.
The dashboard's [Updates views](dashboard.md#updates), opened with `v`, are separate from this
CLI report: opening them reads local/cached information only. **Check** explicitly queries npm
and checks the selected object; stopped existing containers are temporarily started and restored.
Check All confirms stopped targets. Ordinary CLI version reports still never start containers. Base labels, installed
runtime evidence, registry discovery and recovery state remain distinct.

**Evidence and cache.** Successful runtime checks record the version, source, time, environment,
daemon, immutable container and creation-image IDs in disposable files under the data directory's
`update-cache/`, separate from metadata and recovery journals. Stopped containers show **last
verified** with its time, or **Unknown**; creation labels and old update records do not verify the
present binary. Replacement, restore, rollback and update journals invalidate or qualify earlier
observations. A failed probe retains older evidence with its original time, never a fresh success.
If Docker cannot be inspected, history is explicitly unverified against the current container.
For a fresh stopped-container check without leaving it running, use the dashboard's explicit Check.

npm success and the latest attempt are stored separately. Without `--check`, an existing cached
comparison is visibly dated and no network request is made. Explicit discovery failures still
exit 2, even if cached information survives. Invalid, unsafe, missing or unwritable caches do not
block normal operations and are not installation authority. An explicit `latest` update requires
a successful fresh lookup; it cannot silently use a cached target after failure. HTTP rate limits
with Retry-After are retained and respected by later explicit requests. No daily scheduling or
automatic updates are enabled by this cache.

**Bounded checks.** Short Docker inventory/inspect calls have an eight-second per-call deadline
and a 1 MiB combined output limit. The npm check has one eight-second total budget, including DNS,
TLS and abbreviated package-metadata reading (8 MiB maximum), without host npm/Node. A running-container version
probe has a five-second container-side limit; the host client gets three extra seconds for Docker
transport/completion. Image definition/tool verification has a separate 30-second probe limit.
Timeout or unavailable tooling is not a verified version, a missing image, or an up-to-date result.

Container probes require compatible GNU `timeout` (present in managed images); missing tooling
never permits an unbounded probe. Cancellation stops owned host checks, not necessarily remote exec
immediately; container timers and label/full-ID helper cleanup remain responsible. An unreachable
daemon can leave a named unconfirmed helper. [Readiness/cleanup limits](maintenance.md#readiness-checks)
apply; they never impose short deadlines on builds, installs, commits or interactive commands, or
mean an approved mutation was canceled/rolled back.

**Concurrent base operations.** Builds and rollback share daemon/distribution guards across
data directories and context aliases. A long build does not block creation from the current
base; publication waits for a pin check and container creation to finish. Rebuild and rollback
recheck image identity and managed distribution labels before replacement, refuse unexpected
changes or colliding candidate/copy tags, and never treat a failed inspection as a missing image.
These advisory guards do not coordinate older managers or manual Docker commands. They do not
change existing containers, their writable layers, policies or user configuration.

**Policies.** Explicit version comparisons show newer compatible versions for all policies.
`manual` suppresses unsolicited notices, not requested information. `pinned` also suppresses
general newer-version notices, but retains pin-mismatch reporting; availability does not change
the pin or authorize an update. It refuses updates to other versions, refuses to create a
container from a base image built with another version, and reports a version changed outside
the manager.

**Environment updates.** `opencode update` works on a **stopped** environment with network. It
resolves an exact latest-supported-stable target **before confirmation**, then revalidates that
same target, container identity, policy, network and pending operation under the environment lock.
It never substitutes a newer release after consent. It commits a checkpoint
`ocs-checkpoint:<id>-*` of the container's system layer, journals the update, and on any
failure replaces the container with one created from the checkpoint (the system layer exactly
as before; `/root` and `/workspace` are not touched). It also repairs a broken installation.

`--update-system-packages` (off by default; **Update system packages** in the dashboard) first
upgrades the environment's installed packages inside that same checkpointed update: Debian runs
`apt-get update` and `apt-get upgrade` (no removals or new packages, so such upgrades are held
back; changed configuration files are kept), Arch runs `pacman -Sy archlinux-keyring` and a full
`pacman -Su`. A failed upgrade stops **before** OpenCode is touched and restores the checkpoint.
After the upgrade, OpenCode is verified again and reinstalled if the upgrade broke it; an already
current OpenCode then keeps the checkpoint as the rollback point. Custom-image environments
refuse the option: their package manager is unknown. Package upgrades are **not fully
reversible**: rollback restores the checkpointed system layer, but not changes outside it (the
`/root` home volume, `/workspace`) or data and configuration that upgraded programs migrated.
On Arch, AUR/foreign packages such as `paru` are not rebuilt (see the libalpm limitation).
Without the option, packages are left unchanged.
`opencode rollback` undoes the last successful update the same way, keeping the current system
layer as an `ocs-snapshot:*` image first; the last update's checkpoint is kept as the rollback
point (`disk cleanup --superseded` keeps it).

**Base images.** `opencode update-base` builds and verifies a candidate and keeps the replaced
image as `opencode-sandbox:<distro>-previous-<hex>` (not for identical rebuilds);
`opencode rollback-base` verifies a selected rollback image and swaps it in (the replaced image
becomes a rollback copy, so you can swap back). Use `opencode rollback-base --list` first; aliases
of the same immutable image count as one copy. With several distinct images, supply an exact
listed tag or full `sha256:...` image ID using `--copy`, even with `--yes`. Short image-ID prefixes
are not accepted. `--yes` bypasses confirmation, not selection. Creation dates, version precedence
and list order do not describe replacement history and are never used to guess a target.

The preview identifies the selected copy, its build provenance and the current base. A changed
or missing selected alias/current base refuses execution; review and select again. Existing
copies with older provenance remain visible, but the selected image must still pass the current
definition's OS, tool and OpenCode verification. The verified immutable image is published, its
selected rollback aliases are removed, and the replaced base is retained under a new rollback
tag. If the selected image is already current, verification reports unchanged without moving
or removing tags. A failed/unverifiable inventory is an error, not permission to replace images.

Build consent names the existing immutable image (or missing first build), distribution/definition,
exact OpenCode target and mode. These are rechecked under the existing shared guards before a
build and publication; a changed base requires a new review, never silent target substitution.
The candidate's immutable ID passes OS/tool/binary verification before publication. Failed
verification leaves the current base intact; cleanup removes only the known candidate. If its
identity or cleanup cannot be confirmed, inspect the named leftover and actual base/copies before
retrying `disk cleanup`. This is not a durable base-build journal or an automatic recovery engine.

Choose the mode explicitly:

- **Cached rebuild** (default): reuse the local upstream image and the eligible Docker layers
  before the package step, with the selected definition and exact OpenCode version. It is not
  an offline build.
- **Refresh & Rebuild** (`--refresh`): request current upstream inputs and bypass the build cache
  (`--pull --no-cache`). This can take substantially longer and use more disk, and **never prunes
  the shared build cache**. Repositories and upstream tags can change during a build; this is not
  reproducibility, a security certification or a separate upstream-freshness assessment.

**Every build upgrades system packages**, in both modes and for the `build` command too: a
per-build value forces the package layer to run with fresh indexes, so it and the later layers
are never reused from the cache. Debian runs `apt-get update` and `apt-get upgrade`; Arch runs a
full `pacman -Syu` (never a partial upgrade) and therefore also rebuilds `paru`. A repeated build
publishes a new image even with the same OpenCode version. There is no option to skip this.

```sh
opencode-sandbox opencode update-base --distro debian --version 2.1.4 --yes
opencode-sandbox opencode update-base --distro arch --version 2.1.4 \
  --refresh --yes
```

The dashboard [Base Images view](dashboard.md#base-image-actions) offers both modes and always
keeps a rollback copy on replacement. The existing `build` command deliberately keeps **no**
rollback copy, discloses that distinction, and also accepts `--refresh` (its target option remains
`--opencode-version`). Base changes affect future base-based container creation and file-only
restores, not existing containers, writable layers, home/workspace/configuration or integrations.
Not-yet-created pinned environments must still match the new base. To upgrade packages in an
existing environment, use `opencode update NAME --update-system-packages` or the environment's
package manager.
