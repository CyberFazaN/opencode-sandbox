# OpenCode Sandbox

[![CI](https://github.com/CyberFazaN/opencode-sandbox/actions/workflows/ci.yml/badge.svg)](https://github.com/CyberFazaN/opencode-sandbox/actions/workflows/ci.yml)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

Run [OpenCode](https://github.com/anomalyco/opencode) coding agents in per-environment containers on **your own
rootless Docker daemon**, from a command line or a terminal dashboard. Each environment has its
own workspace, home volume, settings and credentials; the agent's changes reach your repository
only when you transfer them, for example as a review branch.

OpenCode Sandbox is an independent open-source project. It is not affiliated with or endorsed by
the OpenCode project, and it is unrelated to other projects with similar names.

> [!IMPORTANT]
> **Beta, written by an AI agent.** Version 6.0.0 is the first public release. Its code, tests
> and documentation were written with OpenCode and Claude Opus 5.5, with minimal human review.
> The evidence for its behaviour is the automated test suite and a test campaign on real rootless Docker,
> run on Arch Linux only (see [Tested environment](#tested-environment)); there has been no
> independent human security review. Expect defects, read the [security model](docs/security.md),
> and do not rely on it as your only protection against code you consider hostile.

![The dashboard](docs/images/dashboard.svg)

## Is it for you?

It fits if you run OpenCode on a Linux workstation and want each project's agent in its own
container: the agent can install packages and run builds as root inside it, while your files,
keys and host stay out of reach except for what you hand over.

Consider something else if:

- you need a hard isolation boundary for untrusted code: use a virtual machine;
- you need network isolation with internet access: there is no egress filtering, only `bridge`
  (internet and local network) or `none`;
- you are on macOS or Windows: the manager needs a Linux host with rootless Docker;
- you want a general container or dev-container manager: this manages OpenCode environments
  only. Dev containers, a plain `docker run`, or OpenCode directly on your host may suit you
  better.

## Features

- **Environments**: scratch (empty), project (a Git clone or a filtered copy of a folder) and
  disposable quick sessions; Debian 12 or Arch Linux images (AUR through `ocs-aur`), or a
  custom image.
- **Managed workspaces** by default, never your original folder; direct host workspaces only with
  explicit consent and checks (not recommended).
- **Change review**: export, bundle, inspect and stage the agent's changes as a review branch;
  host Git never uses the sandbox's Git configuration or hooks.
- **Provider profiles**: named credentials, stored with mode `0600`, mounted read-only.
- **Settings** for CPU, memory, processes, network and published ports (`127.0.0.1` only)
  through one change plan.
- **Backups and recovery**: verified cold backups, restores into new environments, snapshots,
  and journalled operations with explicit recovery commands.
- **OpenCode versions** managed per base image and environment: update policies, updates with
  automatic rollback on failure; OpenCode's self-update is off.
- **Agent Context**: OpenCode is told what the sandbox is (user, workspace, network, limits,
  operating system); one-time initial integrations (Context7 by default).
- **Diagnostics**: `doctor` for the host, read-only `check NAME` per environment including
  measured network reachability, disk usage and conservative cleanup.

## Security in brief

- The agent is **root inside its container**. Container root maps to your user on the host, not
  to the host's root; rootless Docker reduces the damage of an escape but does not prevent one.
- The manager verifies that Docker is **your own rootless daemon** before every use and refuses
  rootful, other users', proxied and remote daemons.
- The default network mode `bridge` reaches the internet **and your local network**; only the
  host's loopback is blocked. `none` has no network.
- The agent **can read the provider keys** mounted into its container: use scoped,
  budget-limited keys.
- A direct workspace gives the agent your folder itself, with no undo.
- Backups are not encrypted.

Details: [docs/security.md](docs/security.md).

## Tested environment

| Component | Tested |
|---|---|
| Host, real rootless Docker | Arch Linux, kernel 7.2: the full test campaign |
| Host, hosted CI only | Ubuntu 26.04 (GitHub's runner): unit tests with a simulated Docker, pipx installation |
| Python | 3.14.8 and, in CI, 3.14.9 (3.14 or newer required) |
| Docker | 29.9.2, rootless, slirp4netns |
| pipx | 1.18.7 |
| Typer, Textual | 0.27.3, 8.2.8 |
| OpenCode | 2.1.4 and 2.2.0 (npm `@opencode/cli`; 2.x only) |
| Images (inside the containers) | Debian 12 (`node:24-bookworm`, the default) and Arch Linux (`archlinux:base-devel`) |

The manager is meant to run on any Linux distribution that meets the
[requirements](docs/install.md#requirements): rootless Docker with its kernel prerequisites,
Python 3.14 or newer with pipx, and Git. Real-world testing has been done on Arch Linux only;
other distributions are untested, so compatibility with them is expected but not guaranteed. The
image you choose for an environment is the distribution inside its container and does not depend
on your host's distribution.

Debian 12 has received LTS security support only since 2026-07-11 (until 2028-06-30); a move of
the default image to Debian 13 is on the list of deferred work ([TODO.md](TODO.md)). No real
model provider has been tested with OpenCode 2.x; the tests use a fake OpenAI-compatible
provider.

## Install

You need Linux with Python 3.14 or newer, pipx and Git, from your distribution's packages (on
Arch Linux: `sudo pacman -S python-pipx git`). Install the application from a release tag:

```sh
pipx install git+https://github.com/CyberFazaN/opencode-sandbox.git@v6.0.0
opencode-sandbox --version
```

To upgrade, install another tag with `--force`; `pipx upgrade` keeps the installed tag.
`pipx uninstall opencode-sandbox` removes the application and keeps your environments and data.

The application does not install or configure Docker. Prepare your rootless Docker daemon and the
base images separately, as described in [docs/install.md](docs/install.md#prepare-docker); the
manager only checks them.

## Quick start

```sh
opencode-sandbox doctor        # host, Docker daemon identity, images
opencode-sandbox build         # the Debian base image (a few minutes)
opencode-sandbox providers set work --key OPENROUTER_API_KEY
opencode-sandbox create webapp --source ~/code/webapp --profile work
opencode-sandbox run webapp    # OpenCode in the sandbox
opencode-sandbox changes bundle webapp   # prints the BUNDLE path
opencode-sandbox changes stage BUNDLE ~/code/webapp
opencode-sandbox               # the dashboard
```

`doctor` must report `Daemon identity: verified`; otherwise it says what is missing and exits
with a code that names the problem ([docs/troubleshooting.md](docs/troubleshooting.md)). The
full walk-through: [docs/getting-started.md](docs/getting-started.md).

## External services

The manager sends no telemetry. These services are contacted:

| Service | When |
|---|---|
| GitHub, PyPI | Installation and upgrades with pipx (the source, then Typer, Textual and their dependencies) |
| Docker Hub | Base image builds (`node:24-bookworm`, `archlinux:base-devel`) |
| The registry of a custom image | The first start of an environment created with `create --image` |
| Debian or Arch package mirrors | Base image builds, and packages you install in an environment |
| AUR, GitHub, crates.io | The Arch image build (the AUR helper `paru` and its sources); AUR packages you install |
| npm registry | OpenCode installs and updates; version checks (`opencode check`, `opencode versions --check`) from the host; the internet probe of `check NAME` from inside the container |
| Context7 (`mcp.context7.com`) | Configured once in every new environment by default, then used by OpenCode when the agent asks for library documentation; opt out with `create --no-integrations` |
| Your model provider | Whatever your provider profile and OpenCode configuration use |

OpenCode itself, and anything the agent runs, can contact other services when the network mode
is `bridge`.

## Documentation

- [Installation](docs/install.md): pipx, upgrades, uninstalling, preparing rootless Docker
- [Getting started](docs/getting-started.md)
- [Concepts](docs/concepts.md): terms, where data lives, environment variables
- [Environments and workspaces](docs/workspaces.md),
  [provider profiles](docs/providers.md), [settings](docs/settings.md)
- [OpenCode and the Agent Context](docs/opencode.md)
- [Backups](docs/backup.md), [change review](docs/changes.md),
  [maintenance](docs/maintenance.md)
- [Dashboard](docs/dashboard.md), [security model](docs/security.md),
  [troubleshooting](docs/troubleshooting.md)
- [Changelog](CHANGELOG.md), [deferred ideas](TODO.md), [contributing](CONTRIBUTING.md),
  [security policy](SECURITY.md)

`opencode-sandbox --help` and `COMMAND --help` describe every command and option.

## Support and contributing

Report bugs and ask questions in GitHub issues; include `opencode-sandbox --version` and the
output of `opencode-sandbox doctor` with keys and private paths removed. Report vulnerabilities
privately as described in [SECURITY.md](SECURITY.md). Arch Linux is the tested host; reports
from other Linux distributions are welcome and answered on a best-effort basis. Pull requests, AI-assisted or not, are
reviewed by the maintainer before they are merged; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT; see [LICENSE](LICENSE).
