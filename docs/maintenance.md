# Maintenance: checks, recovery, disk space

## Readiness checks

- `doctor` checks the host: Python, Git, the Docker CLI, the daemon identity, resource-limit
  support, the base-image definitions,
  free space in Docker's data root and the build cache. It is read-only, works without Docker,
  and its exit status names the problem ([troubleshooting.md](troubleshooting.md#exit-status)).
- `check NAME` is a comprehensive **read-only** check of one environment; nothing is started,
  stopped or changed. It covers the daemon identity, a pending operation, the workspace, the
  image (and a pin), container and home-volume ownership, daemon-reported limit support and
  container limit configuration, the network mode and
  published ports (configured versus what Docker reports, with the recreation command when they
  differ; a server listening on `127.0.0.1` only is flagged), the **measured network
  reachability** ([settings.md](settings.md#network-modes)), the provider profile (permissions,
  the mounted profile, a key changed after the container started), the Agent Context file and its
  delivery, the OpenCode version and the self-update switch, and Docker storage.

Each result of `check` is `passed`, `warning`, `failed`, `not checked` (with the reason, for
example a stopped container) or `not applicable`; the exit status is 1 if any check failed. The
report is cached: `status NAME` and the dashboard show its summary without asking Docker again.

### Resource-limit support

`doctor`, `check NAME` and the dashboard share a read-only daemon support
check, after daemon identity verification. It checks cgroup version/driver and the exact
boolean support flags for CPU quota/period, memory and PID limits. Rootless resource limits
need the setup described in
[Docker's resource-limit guide](https://docs.docker.com/engine/security/rootless/tips/#limiting-resources).
No host files are read or changed to repair delegation, and no service commands run.

- `passed` means **Docker reports** cgroup v2/systemd and the required capabilities. Kernel
  enforcement has not been measured by the diagnostic.
- `warning` means a known unsupported configuration or required capability is reported;
  limits may be ignored. Follow upstream/distribution guidance rather than bypassing checks.
- `not checked` means the query failed or evidence is missing, malformed or unrecognized.
  Unknown support is not a pass. Unrelated cpuset, I/O or swap warnings do not imply that this
  manager's CPU-quota, memory or PID settings are unsupported.

The query has a five-second budget and cooperative cancellation. Dashboard notices are
advisory and run off-thread at startup/explicit Refresh; they preserve an operation's status.
`doctor` exit 0 still means host programs and daemon identity passed, not that every advisory
passed. The per-container "Resource limits" result compares Docker configuration values and
explicitly does not claim measured enforcement.

### Base-image definitions

`doctor` compares each managed base tag's `image-revision` label with the image definition in
the installed manager. The dashboard runs the same checks at startup and explicit Refresh, after verifying the
daemon, and shows non-blocking notices with the same details and hints.

- **Older revision**: rebuild explicitly with the suggested command, for example
  `opencode-sandbox build --distro debian`. Nothing rebuilds automatically.
- **Missing or inconsistent labels**: the revision cannot be verified. Review the image at
  that tag before deciding to rebuild it; a familiar name alone does not identify an image.
- **Newer revision**: the image is ahead of this manager's definition. Check the manager version
  and release notes; do not rebuild merely to remove the warning, which could replace it with
  an older definition.
- **Inspection failed**: `not checked`, with the reason. Check Docker's status and permissions;
  this is not evidence that the image is missing. A confirmed missing image instead names the
  build command.

These are global base-tag checks, not an assessment of an existing container's operating
system or its private/restored system image. They do not block existing environments, edit
metadata or require migration. Rebuilding a base image does **not** upgrade the OS of an
existing container. A current definition means the labels match, not that its OS packages or
OpenCode are the latest available. `doctor` keeps its existing exit codes: image warnings or
`not checked` results do not by themselves make a verified host exit nonzero; read the report.

## Recovery

Operations that change containers (settings changes, recreation, OpenCode updates, restores)
are journalled. If one is interrupted, the environment stays in an error state and the next
command says how to finish it:

| Interrupted | Finish with |
|---|---|
| settings change | `config recover NAME` |
| container recreation | `container recreate-recover NAME` |
| OpenCode update | `opencode update-recover NAME` (rolls back) |
| restore | `backup restore-resume NAME` or `backup restore-rollback NAME --yes` |
| deletion | `delete NAME --yes` |

`check NAME`, `status NAME` and the dashboard's Recovery Center (`F8`) name the right command.

- `repair NAME` and `repair --all` reconcile the recorded state with Docker without deleting
  data, for example after a container was stopped outside the manager.
- `repair NAME --cleanup` removes only a container that never started or is dead; a used stopped
  container is refused (its system layer would be lost). A first start whose `docker run` fails
  removes the container Docker created for it; after an interrupted first start,
  `repair NAME --cleanup` does that.
- Interrupting a command with Ctrl+C, `SIGTERM` or a closed terminal runs its cleanup. After
  `SIGKILL` or a power loss a `.backup-*` temporary directory may remain in the default backup
  directory; `disk cleanup` removes it (in other destinations, delete it yourself).

## Disk usage

```sh
opencode-sandbox disk usage                  # read-only
opencode-sandbox disk cleanup                # preview
opencode-sandbox disk cleanup --yes          # remove the listed objects
opencode-sandbox disk cleanup --superseded   # also older versions, see below
```

Commit, update and build operations refuse to start with less than 2 GiB free in Docker's data
root (`OPENCODE_SANDBOX_DOCKER_RESERVE_BYTES`).

`disk usage` lists what the manager owns, with approximate sizes (Docker's estimates; image
layers shared between images are counted once per image, "own" means unshared): each
environment's directory, container, home volume and images; base images and rollback copies;
leftovers; host data (exports, change bundles, backups); and objects that look like the
manager's but are **not managed by this data directory**. Those are listed and never removed.

`disk cleanup --yes` removes: containers, volumes and images of environments that no longer
exist in this data directory (including untagged earlier layers that a removal exposes),
stopped helper containers, a restored system image no environment uses, a base image build
candidate left by an interrupted build, and unfinished `.backup-*` directories.
`--superseded` adds update checkpoints and runtime images that existing environments no longer
use, base image rollback copies and replaced untagged base images.

- Every object is checked again just before its removal, under the lock of its owner; busy
  objects and objects that changed meanwhile are reported as `Skipped:`, and only `Not removed:`
  makes the command fail. A removal is never forced; an interrupted cleanup can simply run again.
- Never removed: environments (use `delete`), snapshots of existing environments, base images,
  direct workspaces, exports, backups, anything of another data directory.
- Exception: base images, their rollback copies and replaced untagged base images are shared by
  every data directory on the daemon, so `--superseded` in one data directory can remove a
  rollback copy that another one would use for `opencode rollback-base` (Docker refuses only while
  a container uses it).

## The Docker build cache

Building both base images leaves about 13 GB of build cache. The cache belongs to the whole
daemon, and Docker does not record which builds created it, so `disk usage` reports it but
`disk cleanup` never removes it. `docker builder prune` removes the unused build cache of **all**
builds on this daemon; the next image build then downloads and rebuilds everything.
