# Known issues and accepted limitations

Current checkout limitations and accepted design tradeoffs. New defects belong in GitHub issues;
vulnerabilities use private reporting. User-facing limits are in
[security.md](../security.md#known-limitations). BASELINE owns verification gaps; CAMPAIGN owns
release blockers. A supported design limitation is not evidence that an untested path works.

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
| `SIGKILL` and power loss cannot run cleanup | A `.backup-*` directory may remain (removed by `disk cleanup` in the default backup directory) | `docs/maintenance.md` |
| Change transfer refuses untracked symlinks with an absolute or escaping target | One Python venv outside `.gitignore` blocks the bundle, because the destination is the user's repository on the host; ignore such trees or remove the link | D-028; `docs/changes.md` |
| The dashboard shows the recorded state | A container stopped outside the manager shows `running` until `repair` or the next start or stop | `docs/dashboard.md` |
| `create` does not contact Docker | It succeeds while the daemon is unverified (no Docker object is created); the first `start` refuses | D-003 |
| Cached base rebuilds do not guarantee fresh operating-system packages | Default `build`/`opencode update-base` reuse eligible layers; explicit `--refresh` pulls upstream and rebuilds without cache, never pruning it. Neither mode certifies upstream freshness/security or changes packages in existing environments | D-056; `docs/opencode.md` |
| Arch: `paru` is linked against pacman's libalpm | A `pacman -Syu` inside an environment that installs a new libalpm version breaks `ocs-aur` there until the environment is created again from a rebuilt base image | D-006; `docs/workspaces.md` |
| Base-definition diagnostics compare labels, not an existing environment's OS | `doctor` and dashboard startup warn about old/unverifiable/newer managed base tags; they do not upgrade containers, inspect private/restored layers or certify that OS packages are current | D-050; `docs/maintenance.md` |
| Tested with real Docker on Arch Linux only | Other Linux distributions are intended to work when they meet the prerequisites, but are untested; hosted CI runs only the fake-Docker unit suite and a pipx installation on Ubuntu | D-046; `README.md`, `docs/install.md` |
| Docker readiness waits at most 10 seconds | A daemon that needs longer to start, or to answer its first request, is reported as `unavailable` with the reason; rerun the command. Exhausted or unverified probes stay fail-closed, and Docker mutations are never retried | D-052; `docs/troubleshooting.md` |
| Resource support and container settings are not measured enforcement | The shared diagnostic checks Docker-reported cgroup/CPU/memory/PID capabilities, not the full host policy or each live kernel cgroup; missing information stays unknown. User-namespace policy is not checked. Real C05 reads kernel values on the tested host, not every supported host | D-053; `docs/maintenance.md`, `docs/install.md` |

## Upstream behaviour (avoided or mitigated)

| Behaviour | Effect on OpenCode Sandbox |
|---|---|
| OpenCode releases publish the main npm package before its platform packages | For some minutes the registry's `latest` cannot be installed; a build or update then fails cleanly and leaves the image untouched, and `opencode check` may report an update that cannot be built yet. Retry later or name a version |
| OpenCode's `mcp add --global` replaces a server of the same name and corrupts an unparseable global configuration | Avoided: the initial integrations are written only when no global OpenCode configuration exists (D-009) |
| `opencode upgrade` inside a container leaves world-writable files and large caches, and on Arch a broken binary | Avoided: OpenCode's self-update is disabled in every container; `opencode-sandbox opencode update NAME` repairs a broken installation (D-019) |
| pacman downloads from a mirror can stall during Arch image builds | Mitigated: the builds retry pacman three times |
| Retained Debian 12 environments receive LTS security support only (until 2028-06-30) | The current default definition is Debian 13; manager/base upgrades do not upgrade retained containers. A system backup keeps the old OS; only an explicit new environment or no-system restore chooses the new local base |
| Base rollback verifies the installed manager's current OS definition | `rollback-base` on the Debian-13 manager refuses a Debian-12 base copy; old copies are not deleted automatically, and retained Debian 12 environments/system backups remain usable. It is not an OS downgrade mechanism |
| Manager update is conservative, not code attestation or guaranteed rollback | Only inspected pipx 1.18.7/default options/public client policy and supported Linux pidfd/flock/parent-death/subreaper/foreground-tty facilities; custom/foreign/ambiguous installs require manual preservation. Host build/site/tool code is trusted, not sandboxed. Hard-kill unknown quiescence blocks same-boot recovery even with an empty old group; actual post-reboot recovery remains unverified (B15). Previous-tag reinstall does not restore identical dependencies or promise offline recovery. External tools/old managers do not honor the locks. Exact protocol: [ARCHITECTURE](ARCHITECTURE.md#manager-update-and-independent-recovery); operation/recovery: [installation guide](../install.md#failed-or-interrupted-manager-update) |

## Not verified

What has not been tested, and the next step for each: [BASELINE.md](BASELINE.md#unverified-behaviour).
