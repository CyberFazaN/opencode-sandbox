# Installation

Installing OpenCode Sandbox has two separate parts:

1. **The application**: a Python program that you install with pipx straight from the GitHub
   repository. It writes only its own pipx environment and the launcher
   `~/.local/bin/opencode-sandbox`.
2. **Docker**: your own rootless Docker daemon and the base images the environments start from.
   You set up the daemon yourself. The manager checks it before every use, but it never
   installs or configures anything on the host: no packages, services, `/etc` files, firewall
   rules or Docker contexts.

You can install the application first and prepare Docker afterwards: `opencode-sandbox doctor`
tells you what is still missing.

## Requirements

| Requirement | Notes |
|---|---|
| Linux | Any distribution that meets the requirements below is meant to work. Tested with real Docker: Arch Linux only; see [the tested environment](../README.md#tested-environment). |
| Python 3.14 or newer | For pipx. If your distribution ships an older Python, install 3.14 alongside it and name it with `--python` (below). |
| pipx and Git | From your distribution's packages, for example `sudo pacman -S python-pipx git` on Arch Linux. |
| Network access during installation | pipx downloads the source from GitHub and the Python dependencies (Typer, Textual and theirs) from PyPI. |
| Docker in rootless mode | Your own rootless daemon; see [Prepare Docker](#prepare-docker). |
| Kernel and system support for rootless Docker | Subordinate UID and GID ranges for your user and `newuidmap`/`newgidmap`; unprivileged user namespaces (some distributions restrict them by policy, for example AppArmor on recent Ubuntu releases; Docker's rootless guide describes what to allow); cgroup v2 with the `cpu`, `memory` and `pids` controllers delegated to your user, because the manager sets CPU, memory and process limits on every container. Steps 2 and 4 of [Prepare Docker](#prepare-docker) check them. |
| Disk space | Each base image is about 2.2 GB (Debian) or 2.4 GB (Arch); a build also leaves several GB of Docker build cache. |

The base images (Debian 12 or Arch Linux) are the distribution inside the containers. Choose
either one on any host; they are independent of the distribution your host runs.

## Install the application

```sh
pipx install git+https://github.com/CyberFazaN/opencode-sandbox.git@v6.0.0
opencode-sandbox --version
```

The `@v6.0.0` at the end selects a release tag; the available releases are on the project's
GitHub releases page. Dependencies are resolved at install time within the version ranges the
project declares; there is no lock file.

If pipx runs on a Python older than 3.14, the installation fails. Name a newer interpreter:

```sh
pipx install --python python3.14 \
  git+https://github.com/CyberFazaN/opencode-sandbox.git@v6.0.0
```

`opencode-sandbox --help`, `--version` and `doctor` work without Docker.

## Prepare Docker

The manager only uses **your own rootless Docker daemon**, reached through a Docker context
(default name `rootless`). It refuses rootful daemons, other users' daemons, socket proxies and
remote (`tcp://`, `ssh://`) endpoints; [security.md](security.md#daemon-identity) explains the
check.

These steps change your system. Read each one before running it; the ones with `sudo` need an
administrator.

1. **Packages.** Install Docker and its rootless tools (`dockerd-rootless.sh`,
   `dockerd-rootless-setuptool.sh`, `rootlesskit` and a network driver such as `slirp4netns`).
   Package names differ between distributions; Docker's rootless guide
   (<https://docs.docker.com/engine/security/rootless/>) lists them for the distributions it
   covers. On Arch Linux, the tested host:

   ```sh
   sudo pacman -S docker slirp4netns fuse-overlayfs
   ```

   There, `dockerd-rootless.sh` and `dockerd-rootless-setuptool.sh` are not in the official
   repositories. Get them from the AUR package `docker-rootless-extras`, or take the two
   scripts from the upstream Docker release that matches `docker --version` and put them in
   `~/.local/bin`.

2. **Subordinate IDs.** `/etc/subuid` and `/etc/subgid` need a range for your user (for example
   `you:100000:65536`). Check with `grep "^$USER:" /etc/subuid /etc/subgid`. If a range is
   missing, an administrator adds one that does not overlap existing ranges, for example
   `sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 "$USER"`.

3. **The rootless daemon.** Follow Docker's rootless guide for your version
   (<https://docs.docker.com/engine/security/rootless/>). Usually:

   ```sh
   dockerd-rootless-setuptool.sh install
   systemctl --user enable --now docker
   ```

   The setup tool creates a user service and a Docker context named `rootless`. If your setup
   created no context, add one yourself:

   ```sh
   docker context create rootless \
     --docker "host=unix://$XDG_RUNTIME_DIR/docker.sock"
   ```

   On a host without systemd, start the daemon the way Docker's guide describes for your setup;
   the manager only needs the context. You don't need to switch your default context
   (`docker context use`); the manager picks the context `rootless` itself. To use a context with another name, set
   `OPENCODE_SANDBOX_DOCKER_CONTEXT`. On recent kernels the daemon may need the `nf_tables`
   module (`sudo modprobe nf_tables`). Keeping the daemon running after you log out
   (`loginctl enable-linger`) is optional.

4. **Check.** Run the manager's diagnostics:

   ```sh
   opencode-sandbox doctor
   ```

   It must print `Daemon identity: verified`. Otherwise it says what is wrong, and the exit
   status tells the cases apart ([troubleshooting.md](troubleshooting.md#exit-status)).

   `doctor` does not check cgroup delegation. Check it yourself; the output must contain `cpu`,
   `memory` and `pids`:

   ```sh
   u=$(id -u); d=/sys/fs/cgroup/user.slice/user-$u.slice
   cat "$d/user@$u.service/cgroup.controllers"
   ```

   systemd's own user service unit delegates them (measured with systemd 262 on the tested Arch
   Linux host); otherwise Docker's rootless guide ("Limiting resources") shows how to enable it.

5. **Base images.** Build the image for each distribution you want to use:

   ```sh
   opencode-sandbox build                # Debian 12, the default
   opencode-sandbox build --distro arch  # Arch Linux, optional
   ```

   A build downloads the distribution's base image from Docker Hub, operating-system packages,
   and OpenCode (npm package `@opencode/cli`: the release npm marks as latest, or the 2.x
   version you pass with `--opencode-version`; only OpenCode 2.x is installed). The Arch build also builds the AUR helper `paru`. A build takes a few
   minutes and installs packages only inside the image, never on your host. Afterwards
   `opencode-sandbox doctor` lists the base images.

Continue with [getting-started.md](getting-started.md).

## Upgrade or change the version

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
`opencode-sandbox disk cleanup --superseded --yes`, then delete the data and configuration
directories ([concepts.md](concepts.md#where-things-live)) and, if you want, the base images
(`docker --context rootless image rm opencode-sandbox:debian opencode-sandbox:arch`).

## Install from a source checkout

For development, or to run a version that is not tagged, a checkout of the repository has its
own installer. Use either pipx or `install.sh`, not both: they write the same launcher
`~/.local/bin/opencode-sandbox` and do not replace each other's. pipx warns
"Not modifying" and still reports success; `install.sh` refuses and names
`pipx uninstall opencode-sandbox`. Uninstall one before installing the other, and check which
one runs with `command -v opencode-sandbox`.

```sh
git clone https://github.com/CyberFazaN/opencode-sandbox.git
cd opencode-sandbox
./install.sh doctor              # read-only diagnostics
./install.sh install --dry-run   # show the plan, write nothing
./install.sh install             # asks before every write
```

- Run it as your normal user, never with `sudo`. It needs a terminal for its confirmations.
- It runs the command `python`, not `python3`. Where only `python3` exists (Debian and Ubuntu
  without the `python-is-python3` package, for example), use pipx instead.
- It creates a versioned virtual environment under
  `~/.local/share/opencode-sandbox-manager/releases/` (`$XDG_DATA_HOME/opencode-sandbox-manager/`
  if set), points `current` at it and offers the launcher. It refuses foreign launchers and
  symlinked target directories.
- `./install.sh setup-rootless` walks through the Docker preparation above and shows what is
  missing; it changes nothing without asking, never runs `sudo` itself and leaves `/etc/subuid`,
  `/etc/subgid`, the setup tool, lingering and firewalls to you. `--dry-run` only shows the
  checks. It suggests Arch Linux packages and offers only a systemd user service. The package
  check and `./install.sh install --offer-packages` (which asks before `sudo pacman -S` for
  missing packages from the enabled repositories) work on Arch Linux only; on other
  distributions `install.sh` prints a warning and skips them. `--build-image` asks before
  building the Debian image.
- `./install.sh update` installs a new release and switches `current`; a failed update leaves the
  previous release active.
- After a Python minor upgrade of the host (for example 3.14 to 3.15) the installed release no
  longer starts, because its virtual environment was built for the previous Python: run
  `./install.sh update` (`./install.sh doctor` reports it).
- Rollback has no command:
  `cd ~/.local/share/opencode-sandbox-manager && ls releases`, then
  `ln -sfn releases/<previous> .current.tmp && mv -Tf .current.tmp current`.
  Old releases are never pruned automatically; to remove old releases, delete their
  directories under `releases/` except the one `current` points to (`readlink current`).
- `./install.sh uninstall` removes the releases, `current` and the launcher only; environments,
  backups, profiles and Docker data are kept.
