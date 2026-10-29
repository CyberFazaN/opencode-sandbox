# Settings: resources, network, ports

Every environment has CPU, memory and process limits, a network mode, published ports and a
provider profile. All of them change through one change plan.

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

Omitted options keep their current values. `config plan --json` prints the plan for scripts.

## How a change is applied

- Without a container, settings are only saved.
- CPU, memory and process limits change in place (`docker update`, running or stopped, no
  restart), except that **lowering memory on a running container** stops, updates and starts it:
  a limit below the current usage would make the kernel kill the whole container.
- **Network, ports and the provider profile** need a new container. `apply` stops it if it runs
  (sessions end), commits the system layer to an `ocs-runtime:*` image, replaces the container
  (`/workspace`, the `/root` volume and installed packages are kept) and starts it again if it was
  running; the superseded runtime image is untagged.
- Changes that stop or recreate a container ask for confirmation; scripts pass `--yes`.
- Interrupted changes are journalled; `start` and `repair` refuse until
  `config recover NAME` finishes them.

## Network modes

- **`bridge`** (default): internet **and** your local network. The agent can reach services on
  the host's LAN address and other machines on your network; only the host's loopback
  (`127.0.0.1`) is blocked. There is no LAN or egress firewall.
- **`none`**: no network at all, so model providers, MCP servers and OpenCode updates inside the
  container are unavailable.

`check NAME` measures reachability from inside the running container and states only what it
measured:

- the internet: a verified TLS handshake with `registry.npmjs.org`;
- the host's `127.0.0.1`: a short-lived test listener on the host's loopback (never on a LAN
  address) must receive a token through rootlesskit's host address `10.0.2.2`; this one is
  observed on the host, so a process in the container cannot fake it;
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

Containers run with `no-new-privileges` and without the capabilities `NET_RAW` (raw sockets,
e.g. `ping`) and `MKNOD`. The user inside is root with a writable root filesystem; see
[security.md](security.md).
