# Troubleshooting

Start with:

```sh
opencode-sandbox --version
opencode-sandbox doctor
```

`doctor` is read-only and works without Docker. It lists Python, Git and the Docker CLI, the
daemon identity with its reason and a hint, the base images and the free space.

## Exit status

The same codes come from `doctor` and from every command that needs the daemon or a host program,
so scripts can tell the cases apart.

| Code | Meaning | What to do |
|---|---|---|
| 0 | Success; `doctor`: ready | |
| 1 | A check failed (`check NAME`), you declined a confirmation, or you pressed Ctrl+C ("Aborted.") | Read the failed lines |
| 2 | Usage or operation error, for example an unknown environment, an invalid option, or a confirmation without a terminal | Read the message; in scripts, confirm with `--yes` |
| 3 | unverified-proxy: the Docker socket is served by a proxy | Point the context at the daemon's own socket |
| 4 | mismatch: not your own rootless daemon | Use your own rootless daemon |
| 5 | unavailable: the daemon is not reachable | Start it |
| 6 | unsupported: a remote or TLS endpoint | Use a local `unix://` socket |
| 7 | missing: a required program is not installed (the Docker CLI, or Git for the commands that use it) | Install it |
| 8 | not-configured: the Docker context does not exist or has no endpoint | Create the context |

A command ended by `SIGTERM` or `SIGHUP` (a closed terminal) runs its cleanup and exits with 128
plus the signal number (143 for `SIGTERM`).

## Daemon identity results

`doctor` prints `Daemon identity: <result>`, a `reason:` line and a `hint:` line. The check
itself is described in [security.md](security.md#daemon-identity).

- **missing**: `docker` is not installed or not on `PATH`. Install Docker and its rootless
  tools ([install.md](install.md#prepare-docker), step 1).
- **not-configured**: the context `rootless` (or the one named by
  `OPENCODE_SANDBOX_DOCKER_CONTEXT`) does not exist. `docker context ls` lists the contexts;
  create the context ([install.md](install.md#prepare-docker), step 3) or set the variable.
- **unavailable**: the socket is missing, refuses connections or does not answer. Start the
  daemon with `systemctl --user start docker` and look at
  `journalctl --user -u docker` if it fails. `docker context inspect rootless` shows the
  endpoint the manager uses.
- **mismatch**: the socket belongs to a rootful daemon or another user's daemon, or the engine
  does not report rootless mode. The manager refuses it on purpose: such a daemon would own the
  files and containers created for you. Point the context at your own rootless daemon.
- **unverified-proxy**: the process behind the socket is not `dockerd` (for example `socat` or a
  socket proxy), so the daemon behind it is unknown. Point the context at the rootless daemon's
  own socket, usually `unix://$XDG_RUNTIME_DIR/docker.sock`.
- **unsupported**: the context uses `tcp://`, `ssh://` or TLS. Only a local socket is supported.

## Common problems

**`opencode-sandbox: command not found` after `pipx install`.** pipx's launcher directory
(`~/.local/bin`) is not on your `PATH`. Run `pipx ensurepath` and open a new terminal.

**pipx refuses the installation because of the Python version.** OpenCode Sandbox needs Python
3.14 or newer; name one with `pipx install --python python3.14 …`
([install.md](install.md#install-the-application)).

**An old version keeps running after an upgrade.** `pipx upgrade` keeps the installed tag; use
`pipx install --force …@vX.Y.Z` ([install.md](install.md#upgrade-or-change-the-version)). If
`command -v opencode-sandbox` does not point into pipx's directories, a launcher from the
source-checkout installer is in the way: run `./install.sh uninstall` in that checkout first.

**`Image opencode-sandbox:debian missing`.** Build the base image: `opencode-sandbox build`
(or `build --distro arch`).

**`No terminal to confirm …`, or `… needs an interactive terminal`.** Without a terminal the
manager never waits for an answer. Commands that ask for confirmation take `--yes`. `run`,
`shell`, `quick`, `tui` and `providers set` need a terminal; in scripts use `create` and
`exec NAME -- COMMAND`.

**`Provider profile 'NAME' not found`.** Create it with
`opencode-sandbox providers set NAME --key VARIABLE`, or check the spelling with
`providers list`.

**OpenCode cannot reach the model provider.** Check that the environment has network `bridge`
(`config show NAME`), that the container mounts the profile you expect (`status NAME` warns
otherwise) and that you restarted it after changing a key ([providers.md](providers.md)).

**A published port does not answer.** The server in the container must listen on `0.0.0.0`, not
`127.0.0.1`; `check NAME` flags this. On the host, connect to `127.0.0.1:HOSTPORT`.

**`docker run` fails because a port is taken.** Choose another host port with
`config apply NAME --publish HOST:CONTAINER`.

**Not enough space.** Commits, updates and builds need 2 GiB free in Docker's data root.
`disk usage` shows what the manager owns, `disk cleanup` removes leftovers
([maintenance.md](maintenance.md#disk-usage)).

**The dashboard shows `running` for a stopped container.** It shows the recorded state; press `R`
(Repair) or run `opencode-sandbox repair NAME`.

**An operation was interrupted.** The environment stays in an error state; `status NAME` names
the command that finishes it ([maintenance.md](maintenance.md#recovery)).

**The rootless daemon does not start on a recent kernel.** It may need the `nf_tables` module:
`sudo modprobe nf_tables` (usually loaded automatically after a reboot).

**`ocs-aur` fails in an Arch environment after `pacman -Syu`.** pacman's libalpm changed;
environments created from a rebuilt base image work again
([workspaces.md](workspaces.md#arch-linux-environments)).

## Reporting a problem

Open an issue on GitHub with the output of `opencode-sandbox --version` and
`opencode-sandbox doctor`, the command you ran and its full output, your Linux distribution and
its version, and your Docker and OpenCode versions. Remove keys, tokens and private paths first.
Arch Linux is the tested host; reports from other distributions are welcome and answered on a
best-effort basis. Security
problems: [SECURITY.md](../SECURITY.md), not a public issue.
