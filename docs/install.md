# Installation

Installing OpenCode Sandbox has two separate parts:

1. **The application**: a Python program that you install with pipx straight from the GitHub
   repository. It writes only its own pipx environment and the launcher
   `~/.local/bin/opencode-sandbox`.
2. **Docker**: a supported local daemon (rootless by default) and the base images the
   environments start from. You set up the daemon yourself. The manager verifies it, but never
   installs or configures Docker or host OS packages/services, `/etc` files, firewall rules or
   Docker contexts. Explicit application updates affect only its own user-level pipx installation.

You can install the application first and prepare Docker afterwards: `opencode-sandbox doctor`
tells you what is still missing.

## Requirements

| Requirement | Notes |
|---|---|
| Linux | Any distribution that meets the requirements below is meant to work. Tested with real Docker: Arch Linux only; see [the tested environment](../README.md#tested-environment). |
| Python 3.11 or newer | For the application's venv (tested: 3.11 and 3.14). pipx can run on a different Python; select the application's interpreter with `--python`. |
| pipx and Git | Install them using your distribution's official documentation. pipx installs the application, not Docker. |
| Network access during installation | pipx downloads the source from GitHub and the Python dependencies (Typer, Textual and theirs) from PyPI. |
| Docker | Your own rootless daemon by default. A configured local rootful daemon can be used with [explicit opt-in](settings.md#docker-backend). |
| Kernel and system support for the default rootless backend | Subordinate UID and GID ranges for your user and `newuidmap`/`newgidmap`; unprivileged user namespaces (some distributions restrict them by policy); cgroup v2 with the `cpu`, `memory` and `pids` controllers delegated to your user's daemon, because the manager sets CPU, memory and process limits on every container. See [Prepare Docker](#prepare-docker) for upstream guidance and the limits of the application's checks. |
| Disk space | Debian is about 2.2 GB and Arch about 2.4 GB. Kali rolling varies with the upstream packages. A build can also leave several GB of Docker build cache. |

The base images supply the distribution inside the containers: Debian 13, Arch Linux rolling
or Kali Linux rolling. Kali adds OpenCode and basic development tools to the official Kali
image, not Kali tool metapackages. The container's distribution is independent of your host's.

## Install the application

```sh
pipx install git+https://github.com/CyberFazaN/opencode-sandbox.git@v6.5.0
opencode-sandbox --version
```

The suffix after `@` selects a tag from the
[releases page](https://github.com/CyberFazaN/opencode-sandbox/releases). Dependencies are resolved
at install time within the declared version ranges; there is no lock file.

pipx normally uses its own interpreter for the application venv. If that is older than the
selected release supports, installation fails. Name an installed interpreter explicitly when
needed:

```sh
pipx install --python python3.11 \
  git+https://github.com/CyberFazaN/opencode-sandbox.git@v6.5.0
```

`opencode-sandbox --help`, `--version` and `doctor` work without Docker.

### Startup coordination

Supported manager CLI/dashboard processes hold shared installation access for their entire
lifetime, including attached sessions and worker shutdown. The packaged launcher takes this
lease before importing the CLI; existing wrappers invoking the current CLI also take it before
dispatch. Other normal instances may run together. Internal exclusive installation access refuses
while any supported instance is alive, even with different data/configuration overrides. A normal
startup during exclusive access reports **Manager installation busy** (exit 2), including help
and version commands; close the other instance or wait for its operation to finish, then retry.

Coordination uses private persistent files in `/tmp/opencode-sandbox-locks-<UID>/`, keyed by the
canonical application Python environment path, not by HOME, TMPDIR, XDG or product overrides.
Unsafe/unwritable lock paths fail closed without repairs or a fallback. **Never delete a lock
file because it appears stale:** a live process may hold that inode; process exit releases the
lock without removing the file. The protocol is advisory, not protection against another process
with the same user's access. Older manager versions, direct Python library use and arbitrary
external pipx/Docker commands do not honor it. Stop other manager instances/sessions before a
manual pipx replacement; these locks cannot make an external replacement safe automatically.

An approved manager update waits for **actual process exit**, not just dashboard return or a
restored terminal, before one non-waiting exclusive attempt. Other supported instances prevent
replacement. An independent frozen helper revalidates the installation, existing external tools,
exact published source and effective installer policy; normal startup never gains a bypass.

An incomplete update also blocks startup **after the helper dies**, even if its lock was released.
Private authoritative state and recovery inputs live below the canonical pipx home's
`.opencode-sandbox-updates/`, outside the replaceable venv and independent of HOME/product
overrides. Pending, unknown or unsafe records are preserved without repair or migration. Only
explicit independently verified completion/recovery may reopen startup; never delete these files.

## Prepare Docker

The default is **your own rootless Docker daemon**, reached through a Docker context (default
name `rootless`). That context cannot point to a rootful daemon or to another user's daemon.
Rootful Docker is a separate, explicitly [opted-in backend](settings.md#docker-backend) using
`/run/docker.sock`; for its readiness report, use `opencode-sandbox --docker-backend rootful doctor`.
Both backends refuse proxies and remote endpoints; see [daemon identity](security.md#daemon-identity).

### Set up the daemon separately

For the default backend, use [Docker's official Rootless mode installation guide](https://docs.docker.com/engine/security/rootless/)
and your Linux distribution's official documentation for the packages and setup procedure that
match your system. Arch Linux users should also consult the
[ArchWiki Rootless Docker daemon section](https://wiki.archlinux.org/title/Docker#Rootless_Docker_daemon):
Arch may have its own packaging and setup conventions rather than Docker's upstream setup tool.
This guide deliberately does not duplicate those host installation procedures.

The resulting setup must meet the [requirements above](#requirements): a daemon running as your
normal user, subordinate UID/GID mappings, working unprivileged user namespaces, and cgroup v2
with `cpu`, `memory` and `pids` delegated for container resource limits. Docker's
[resource-limit guidance](https://docs.docker.com/engine/security/rootless/tips/#limiting-resources)
explains the required cgroup support and how to check it. Without that support, Docker may
ignore resource-limit flags. Follow upstream and distribution guidance rather than changing
host security policy just to bypass an error.

### Select the context and check readiness

The manager uses the context named `rootless` by default. You do not need to switch your Docker
default context. `docker context ls` lists existing contexts; if yours has another name, set
`OPENCODE_SANDBOX_DOCKER_CONTEXT` to that name. The context must point to the daemon's own local
Unix socket. `DOCKER_HOST` and `DOCKER_CONTEXT` are ignored by the manager, so setting those
variables alone is not enough.

Run the application's shared CLI/dashboard diagnostics after setup:

```sh
opencode-sandbox doctor
```

It lists Python, Git and the Docker CLI, checks daemon identity, and reports resource-limit
support, base images and Docker storage. It must print `Daemon identity: verified`; otherwise read the reason and hint.
The [exit status](troubleshooting.md#exit-status) distinguishes a missing program, missing
context, unavailable daemon and refused endpoint. These checks never install packages, issue
service-start commands or configure Docker. Connecting can trigger a socket-activated daemon
that you already configured. Readiness waits up to 10 seconds for a slow response, with a
waiting notice and cancellation; a ready daemon causes no retry delay. The dashboard reports
daemon, resource-support and base-image problems at startup; daemon checks run again before
Docker operations.

**A verified identity does not prove that resource limits can be enforced.** `doctor`
separately reports cgroup version/driver and Docker-reported CPU quota, memory and PID
limit support. Missing capabilities produce a warning; unavailable or unrecognized evidence is
`not checked`, not success. This is not a measurement of kernel enforcement or a host policy
verification. Daemon identity checks namespace identity separately; neither check certifies your
host's namespace policy. Use the upstream resource-limit and
[rootless troubleshooting guidance](https://docs.docker.com/engine/security/rootless/troubleshoot/)
for those prerequisites. A successful `doctor` exit is not a complete host-setup certification;
resource/image/storage warnings and unknown checks may accompany exit 0. Nothing repairs host
settings or blocks existing environments automatically.

### Build the sandbox images

A missing base image is expected on first run: `doctor` warns and names the build command.
It also warns about old or unverifiable image-revision labels; a newer image needs review,
not a blind rebuild. These [base-image checks](maintenance.md#base-image-definitions) never
change or block existing environments, and image warnings do not change `doctor`'s exit status.
Build the image for each distribution you want to use:

```sh
opencode-sandbox build              # Debian 13
opencode-sandbox build --distro arch  # Arch Linux, optional
opencode-sandbox build --distro kali  # Kali rolling, optional
```

A build downloads the distribution's base image from Docker Hub, operating-system packages,
and OpenCode (the newest supported stable `@opencode/cli` 2.x, or the exact 2.x version you
pass with `--opencode-version`). Run the build on the backend that will use the image; a tag on
one daemon is not available on the other. The Arch build also builds
the AUR helper `paru`. A build takes a few minutes and installs packages only inside the image,
never on your host. Afterwards `opencode-sandbox doctor` lists the base images. Once you have
an environment, `opencode-sandbox check NAME` checks its readiness without starting or changing
it; some checks require an already running container.

If `doctor` reports an older definition, rebuild the affected base with the command it suggests.
Manager upgrades and base rebuilds do not add image files to existing environments or upgrade
their OS. Stop/start, recreation and backups that include the system layer keep the environment's
OS. See [base images and OS changes](workspaces.md#distributions-and-images).

Continue with [getting-started.md](getting-started.md).

## Upgrade or change the version

Read-only evidence is available without Docker or running pipx:

```sh
opencode-sandbox manager status          # local provenance and cached releases
opencode-sandbox manager status --check  # query official GitHub releases
```

The dashboard's [Manager view](dashboard.md#manager-release-and-installation-checks) exposes the
same evidence with independent errors. These commands never replace the installation, touch a
launcher, convert an editable/foreign install, install/switch Python or start unsolicited discovery.
A verified official-tag pipx classification means local records agree, not public commit
authentication or permission to update.
For unrecognized options, injections, pins, suffixes or ambiguous/shadowed launchers, inspect your
existing configuration and follow the matching manual workflow; do not assume a generic force
command preserves custom settings. A missing/unrecognized record is not permission to repair it.

### Explicit reviewed manager update

In **Updates → Sandbox Manager**, Check releases, then Update to prepare a fresh exact source/
installation/tool review. At 80x24 or larger, read the scrollable impact, release notes and exact
tag/commit, accept the public-default policy, then choose **Update & close**. Cancel is focused
first. Active operations/sessions must finish; approved staging closes the dashboard only when
actual worker bodies finish and the local Linux terminal driver/foreground tty are restored.

The equivalent explicit CLI entry requires a real foreground terminal and defaults to Cancel:

```sh
opencode-sandbox manager update --tag vX.Y.Z
```

Choose a strictly newer published full release. Discovery/cached availability never authorizes an
install; the same target is resolved and revalidated afresh through the official GitHub HTTPS API.
This is not signed-tag authentication. Only recognized official-tag pipx installations with default
options and the inspected external **pipx 1.18.7** are supported. Existing source Python and explicit
pipx locations are preserved; no tool/Python is installed, switched or converted. Detected custom
pip/Git/proxy/index/credential configuration requires manual preservation, without reading secrets
or silently discarding settings. The initial managed policy uses public GitHub/PyPI defaults.

The independent helper uses exact-tag pipx force replacement. **Source/build code runs on the
host as your user, not inside a sandbox.** Force is not a backup. After installation it separately
checks expected version/source/commit, records/options, launcher, fresh runtime and fixed CLI-help
construction; Docker readiness is not an installation-success requirement. No image rebuild,
environment migration, configuration reapplication, automatic rollback or automatic restart occurs.

The initiating command exits after handoff, not as proof of installation success. **Wait for the
helper's final result before restarting**. It prints private recovery paths before mutation, and
retains records even if the terminal disappears. Do not run another external installer meanwhile.

### Failed or interrupted manager update

The result distinguishes a verified target, an operational verified previous installation, target
records with failed verification, and an unavailable/unverified installation/launcher. The last two
retain the startup barrier. An external frozen **verify-only** command printed with the private
operation record works independently of the application launcher and venv; it never installs or
automatically rolls back. Locate the operation through `.opencode-sandbox-updates/` in the pipx
home if the terminal output was lost, and use the recorded external Python/helper paths.

For an unavailable installation, the record includes a manually reviewed previous-tag pipx
reinstall command retaining the recognized locations/source Python. This is recovery guidance,
**not identical dependency restoration or guaranteed offline recovery**. Finish that external
command, then explicitly run the frozen verifier; a cache, successful exit or deleting a record
cannot reopen startup. Custom settings still need manual preservation.

A handled interruption cleans/reaps owned installer descendants before verification. A hard-killed
helper cannot prove escaped descendants stopped: unconfirmed same-boot state stays blocked, even
if the original process group is empty. A reboot supplies independent old-process quiescence before
explicit frozen verification. No reboot, signal to an old PID, reset or repair is performed for you.

### Manual version change

Install the other release tag with `--force`; this is also how you go back to an older release:

```sh
pipx install --force \
  git+https://github.com/CyberFazaN/opencode-sandbox.git@vX.Y.Z
opencode-sandbox --version
```

Replace `vX.Y.Z` with the release you want. `pipx upgrade opencode-sandbox` and
`pipx reinstall opencode-sandbox` do **not** move to a newer release: they keep the tag you
installed. `pipx install` without `--force` refuses because the application is already
installed. `pipx list` shows the installed version.

Environments, backups, provider profiles and images are kept across upgrades. The application
version is separate from the base images and from OpenCode inside the environments; those are
updated with `opencode-sandbox build`, `opencode update-base` and `opencode update`
([opencode.md](opencode.md)). Read the release notes before upgrading.

## Uninstall

```sh
pipx uninstall opencode-sandbox
```

This removes the application and its launcher only. Your environments, their containers,
volumes and images, backups, exports and provider profiles stay. To remove those too, do it
**before** uninstalling: `opencode-sandbox delete NAME` for each environment, then
preview `opencode-sandbox disk cleanup --superseded` on each backend you used. Add `--yes`
only after reviewing the list. Delete the data and configuration directories only if you no
longer need them ([concepts.md](concepts.md#where-things-live)). Base tags and shared rootful base
artifacts are not removed by cleanup. If you also want to remove an image, verify the daemon,
tag and other users' dependencies before removing it with Docker.

Install the application with pipx from a GitHub release tag. Configure Docker separately.

## Moving from a legacy source installation

A launcher from a legacy `install.sh` installation can shadow pipx. If pipx warns "Not modifying"
yet reports a successful installation, inspect what runs:

```sh
command -v opencode-sandbox
pipx list
```

A legacy launcher normally points into
`~/.local/share/opencode-sandbox-manager/current/bin/` (or the corresponding `XDG_DATA_HOME`
location), not pipx's venv. Inspect that launcher's symlink target before changing anything.

If it is the legacy application, use the trusted source checkout that installed it. From that
checkout only, run
`./install.sh uninstall` as your normal user and review its confirmation. The old uninstaller
removes its application releases and launcher, not environments, backups, profiles or Docker
objects. If you no longer have the sources, obtain them from a trusted tag before proceeding.

Then follow [Install the application](#install-the-application). If pipx was already installed
behind the legacy launcher, repeat its release-tag installation with `--force` to create the
launcher, then check `command -v opencode-sandbox`, `pipx list` and
`opencode-sandbox --version`. No environment migration or base-image rebuild is needed for
this installation-path change.

If the launcher belongs to another program or you cannot identify it safely, **do not delete**
it or any data directories; resolve the collision before installing. The application does not
take over foreign launchers or automatically remove old installations.
