# Settings: resources, network, ports

Every environment has CPU, memory and process limits, a network mode, published ports and a
provider profile and optional specialized Agent Context. All change through one shared plan.

```sh
opencode-sandbox config show NAME     # configured and actual values
opencode-sandbox config plan NAME --memory 8g --cpus 4    # no changes
opencode-sandbox config apply NAME --memory 8g --cpus 4   # asks if needed
opencode-sandbox container usage NAME # current usage from Docker
```

| Option | Values | Default |
|---|---|---|
| `--cpus` | CPU limit | min(8, host CPUs) |
| `--memory` | memory limit, e.g. `8g` | `16g` |
| `--pids` | process limit | 2048 |
| `--network` | `bridge` or `none` | `bridge` |
| `--publish HOST:CONTAINER[/udp]` | published ports; repeatable; replaces all mappings | none |
| `--no-ports` | remove all published ports | |
| `--profile` | provider profile ([providers.md](providers.md)) | `default` |
| `--agent-context` / `--no-agent-context` | automatic specialized context inclusion | enabled |

Omitted options keep their current values. `config plan --json` prints the plan for scripts.
`config show` also reports the environment kind, managed/direct workspace record, and how the
workspace was initialized. The import method is unknown for older copies that did not record it.

## Docker backend

Rootless Docker is the default. To use a configured local rootful daemon, enable
**Allow rootful Docker environments** in Manager Settings or run the first command below.
Build the base on that daemon before creating the environment.

```sh
opencode-sandbox config global --allow-rootful
opencode-sandbox --docker-backend rootful build --distro debian
opencode-sandbox create example --distro debian --backend rootful
opencode-sandbox start example
```

In the dashboard, select **Rootful** under **More options** when creating an environment.
**Disk** uses the selected environment's backend. **Updates → Base Images** has its own Docker backend selector.
The CLI's global `--docker-backend` option selects the daemon for maintenance such as
`build`, `doctor`, and `disk cleanup`. Named environment operations use the saved backend.
Rootful `disk cleanup` keeps shared base-image artifacts because another manager or data
directory may still need them.

The backend is fixed at creation. Turning the setting off preserves metadata and visibility
and blocks new rootful Docker operations. Stop rootful environments before disabling access
if you also want their processes to stop. Existing sessions and containers otherwise continue
to run. Backups keep their backend. Rootful restore requires the original username, UID and
primary GID. Rootful environments use managed distribution images.

Rootful sessions run with the host username, UID and primary GID. Files created by ordinary
commands have the host user's ownership. Supplementary host groups are excluded, so paths
that rely on supplementary group access may fail the direct workspace preflight. The home
volume is mounted at `/home/ocs` and follows the environment across recreation. Review the
security implications before enabling rootful. [Security model](security.md#rootful-docker)

## How a change is applied

- Without a container, settings are only saved.
- Agent Context activation changes only its exact system-config instruction, without interrupting
  sessions. The file stays mounted. Stopped containers reconcile the saved choice on their next
  managed start; running OpenCode may need a new launch to observe a change.
- CPU, memory and process limits change in place (`docker update`, running or stopped, no
  restart), except that **lowering memory on a running container** stops, updates and starts it:
  a limit below the current usage would make the kernel kill the whole container.
- **Network, ports and the provider profile** need a new container. `apply` stops it if it runs
  (sessions end), commits the system layer to an `ocs-runtime:*` image, replaces the container
  (`/workspace`, the persistent home volume and installed packages are kept) and starts it again if it was
  running; the superseded runtime image is untagged.
- Changes that stop or recreate a container ask for confirmation; scripts pass `--yes`.
- Interrupted changes are journalled; `start` and `repair` refuse until
  `config recover NAME` finishes them.

Global OpenCode configuration has separate **OpenCode Config Editor** and **Reload Config**
actions in these same environment Settings; CLI equivalents live under `opencode-configs`.
These whole-directory file transfers never replace the system config, change resource settings,
or restart anything. See [the config guide](opencode-configs.md).

## Network modes

- **`bridge`** (default): internet **and** your local network. The agent can reach services on
  the host's LAN address and other machines on your network. There is no LAN or egress firewall.
- **`none`**: no external network, so network-hosted model providers, MCP servers and OpenCode
  updates are unavailable. Processes in the container can still use its own loopback.

`check NAME` measures reachability from inside the running container and states only what it
measured:

- the internet: a verified TLS handshake with `registry.npmjs.org`;
- the host's `127.0.0.1` on the supported rootless path: a short-lived loopback-only listener
  must receive a token through rootlesskit's host address `10.0.2.2`. The test is observed on
  the host; rootful and other known rootless drivers report this part as not checked;
- the host's primary LAN address and the default gateway: answered or not (a refused connection
  counts as reached).

The other results come from a process in the container, which the agent could influence.
Measured with the tested rootless setup (rootlesskit with slirp4netns, host loopback disabled,
the builtin port driver): internet and the host's LAN address reachable, host loopback not.
Registry images have `python3` for the probe; other custom images report `not checked`.

## Published ports

- Ports always bind to `127.0.0.1` on the host, host ports 1024 and above.
- A server in the container must listen on `0.0.0.0`; one that listens on `127.0.0.1` only cannot
  be reached through a published port (`check` flags it).
- Conflicts with other environments are detected; conflicts with other host processes are not.
  When `docker run` fails because a host port is taken, the container Docker created for it is
  removed, so you can change the port with `config apply` right away.

## Container hardening

Both backends drop `NET_RAW` and `MKNOD`. Rootless also sets `no-new-privileges`; managed
rootless images run as container root mapped to the host user. Rootful starts as the host UID/GID
and permits container-local sudo. See the [security model](security.md).
