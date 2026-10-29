# Known issues and accepted limitations

The known issues of the current release that are not fixed, and the limitations accepted by
design. There is no open defect known to the maintainer. New problems are tracked in GitHub
issues; this file lists what remains true for the current release, with the decision or
document that describes it. User-facing statements of the same limitations are in
[docs/security.md](../security.md#known-limitations) and the guides.

## Product limitations (by design)

| Limitation | Consequence | Where |
|---|---|---|
| Ownership checks rely on Docker labels | Any process that can use the same rootless daemon can create objects with forged labels, which the manager treats as its own; name collisions with unlabelled objects are refused | D-003, D-011; `docs/security.md` |
| The daemon socket is verified, then used | Another process of the same user could replace the socket between the check and its use (`$XDG_RUNTIME_DIR` is private to the user) | D-003 |
| `bridge` reaches the host's LAN; no egress filtering | The agent reaches the internet, the local network and services on the host's LAN address; only host loopback is blocked; `none` has no network | D-015, D-020; `docs/settings.md` |
| Container root with a writable root filesystem | Packages the agent installs run as root inside the container; a kernel or runtime escape would have the host user's privileges | D-004; `docs/security.md` |
| The agent can read the mounted provider profile | Use scoped, budget-limited keys | `docs/providers.md` |
| Direct-workspace checks are a snapshot at each container start | A socket, device node or mount added later inside the directory is reachable from the running container; the checks run again before every start | D-012, D-030 |
| A provider key change reaches a running container only after a restart | The profile is a single-file bind mount and is replaced atomically (new inode); `check NAME` reports a profile changed after the container started | `docs/providers.md` |
| A settings change that recreates the container ends open sessions | Network, port and profile changes stop a running container; the change asks first | D-010 |
| Backups are cold; change transfer and backups are not transactional against concurrent writers | Stop the environment for a backup (`--stop`); do not change the target repository while `changes stage` or `apply` runs | `docs/backup.md`, `docs/changes.md` |
| `SIGKILL` and power loss cannot run cleanup | A `.backup-*` directory (removed by `disk cleanup` in the default backup directory) or `/tmp/ocs-install.*` of the source installer may remain | `docs/maintenance.md` |
| Change transfer refuses untracked symlinks with an absolute or escaping target | One Python venv outside `.gitignore` blocks the bundle, because the destination is the user's repository on the host; ignore such trees or remove the link | D-028; `docs/changes.md` |
| The dashboard shows the recorded state | A container stopped outside the manager shows `running` until `repair` or the next start or stop | `docs/dashboard.md` |
| `create` does not contact Docker | It succeeds while the daemon is unverified (no Docker object is created); the first `start` refuses | D-003 |
| Base image rebuilds reuse Docker's cached operating-system layers | `build` and `opencode update-base` refresh OpenCode, not the apt or pacman packages; update packages inside an environment, or remove the build cache (`docker builder prune`, daemon-wide) before a rebuild | D-019; `docs/opencode.md` |
| Arch: `paru` is linked against pacman's libalpm | A `pacman -Syu` inside an environment that installs a new libalpm version breaks `ocs-aur` there until the environment is created again from a rebuilt base image | D-006; `docs/workspaces.md` |
| No warning for base images older than the installed image definition | After an upgrade that changes an image definition, rebuild the base images yourself (`opencode-sandbox build`); a `doctor` warning is a deferred item | `TODO.md` |
| Tested with real Docker on Arch Linux only | Other Linux distributions are intended to work when they meet the prerequisites, but are untested; hosted CI runs only the fake-Docker unit suite and a pipx installation on Ubuntu | D-046; `README.md`, `docs/install.md` |
| `install.sh` assumes Arch Linux and `python` | The package check and `--offer-packages` use pacman and run only on Arch Linux (a warning elsewhere); the installer runs `python`, which some distributions provide only as `python3`; pipx is the primary installation | D-046; `docs/install.md` |
| `setup-rootless.sh` and the hints assume systemd | They name Arch packages as examples and offer a systemd user service; on other hosts the user follows Docker's rootless guide | D-046; `docs/install.md` |
| `doctor` does not check cgroup delegation or user-namespace policy | Without the `cpu`, `memory` and `pids` controllers delegated, the container limits cannot be applied (behaviour not measured); `docs/install.md` shows a manual check | D-046 |

## Upstream behaviour (avoided or mitigated)

| Behaviour | Effect on OpenCode Sandbox |
|---|---|
| OpenCode releases publish the main npm package before its platform packages | For some minutes the registry's `latest` cannot be installed; a build or update then fails cleanly and leaves the image untouched, and `opencode check` may report an update that cannot be built yet. Retry later or name a version |
| OpenCode's `mcp add --global` replaces a server of the same name and corrupts an unparseable global configuration | Avoided: the initial integrations are written only when no global OpenCode configuration exists (D-009) |
| `opencode upgrade` inside a container leaves world-writable files and large caches, and on Arch a broken binary | Avoided: OpenCode's self-update is disabled in every container; `opencode-sandbox opencode update NAME` repairs a broken installation (D-019) |
| pacman downloads from a mirror can stall during Arch image builds | Mitigated: the builds retry pacman three times |
| Debian 12 receives LTS security support only (since 2026-07-11, until 2028-06-30) | The default image stays on Debian 12 for 6.0.0; moving to Debian 13 is a deferred item (`TODO.md`) |

## Not verified

What has not been tested, and the next step for each: [BASELINE.md](BASELINE.md#unverified-behaviour).
