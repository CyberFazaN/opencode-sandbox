# Environments and workspaces

## Creating an environment

`create NAME` makes an environment with an empty persistent workspace (kind `scratch`) on the
default distribution with the default integrations. Everything else is optional;
`create --help` groups the options (workspace, distribution or image, integrations), and
`create` prints the choices it made and the next command.

```sh
opencode-sandbox create notes
opencode-sandbox create webapp --source ~/code/webapp --profile work
opencode-sandbox create tools --distro arch --no-integrations
```

### A copy of a folder (`--source`)

With `--source DIR` the kind is `project`:

- A Git repository root is **cloned**: committed files only; uncommitted and ignored files are
  not copied. A subdirectory of a repository is refused (import the root).
- Any other directory is **copied** without hidden files, symlinks, special files and
  `node_modules`, `target`, `dist`, `build` and `__pycache__`. Everything else becomes readable
  by the agent.
- `$HOME`, its parents and `/` are refused.
- `--kind scratch` with `--source` is refused (a scratch environment starts empty);
  `--kind quick --source DIR` makes a disposable copy.

The copy is the agent's: your original folder is never mounted or changed. Bring changes back
with `changes` ([changes.md](changes.md)). Do not run host Git, editors or build tools inside a
managed workspace directory (`environments/<id>/workspace` in the data directory): its `.git` and
tool configuration are the agent's, and host tools would act on them.

### Quick sessions

```sh
opencode-sandbox quick [--source DIR] [--shell]
```

A disposable session. When it ends, choose: export the changes and delete, promote to a scratch
environment, delete, or keep it as a quick session (the default). Interrupted sessions are
preserved. `promote NAME scratch|project` keeps a quick session later. `quick` needs a terminal.

## Direct workspaces (not recommended)

```sh
opencode-sandbox create NAME --workspace-mode direct --workspace DIR
```

**Not recommended — direct access to host files.** `/workspace` is your existing directory
itself, not a copy: the agent reads, changes and deletes your files immediately, as your user,
with no review step and no undo. Only for kinds `project` and `scratch` (not `quick`);
`--source` does not apply. The manager never deletes, chowns, chmods, restores into or rewrites
the directory; `delete` removes only the container, the volume and the metadata.

- **Refused directories:** a missing path or a non-directory; `/` and system trees (`/etc`,
  `/usr`, `/var`, `/run`, `/opt`, `/srv`, …); your home directory or a parent of it; the
  manager's data and configuration directories, `$XDG_RUNTIME_DIR` and Docker's data root (being,
  containing or lying inside them); any hidden path component (`~/.config/...`); a directory not
  owned by you; a parent owned by another user, owned by root below one of your directories, or
  writable by others without the sticky bit; sockets, device nodes or other mounted filesystems
  inside it (Docker bind mounts are recursive). Symlinks are resolved and the target is recorded.
  Two environments cannot use overlapping directories.
- **Consent:** the command shows what this means and asks (`--yes` for scripts). Then a
  **preflight** starts a throw-away container of the environment's image (no network, the same
  user as the environment) that writes, checks and deletes one file `.ocs-preflight-<random>` in
  the directory; creation continues only if that file appeared on the host as yours. A preflight
  interrupted by a crash leaves that file; the next attempt removes it if its content proves it
  is the manager's.
- **Checked again:** Docker mounts the directory again at every container start, so the checks
  are repeated before every start and creation of the container (`start`, `run` or `shell` of a
  stopped environment, `container recreate` and its recovery, network, port and profile changes,
  a memory change that restarts the container, an OpenCode update); `config plan` reports a
  failing directory as a blocker. A recorded directory that has been replaced by a symlink is
  refused and the container stays stopped. The checks are a snapshot: a socket or mount added
  later inside the directory is visible to the running container.
- **Host tools:** the agent can also write files that programs on your host run or act on when
  you later use them in the directory: Git hooks, Git configuration, editor, direnv and build
  configuration. Review such files (`git status`, `git diff`, `.git/hooks`, `.git/config`) before
  running Git, an editor or a build tool there.
- **Changes and backups:** `changes` does not apply (use Git in the directory). `backup create`
  leaves the directory out unless `--include-workspace`; `backup restore` always creates a
  managed environment (empty, or with the archived copy) and never writes into the directory.

## Distributions and images

| `--distro` | Base image | Built from | Notes |
|---|---|---|---|
| `debian` (default) | `opencode-sandbox:debian` | `node:24-trixie` (Debian 13) | Image revision 2 since 6.1.0; 6.0.0 built Debian 12 (revision 1) |
| `arch` | `opencode-sandbox:arch` | `archlinux:base-devel` (rolling) | AUR packages through `ocs-aur` |

Build the base image first (`opencode-sandbox build --distro ID`). The distribution is recorded
at creation and cannot change later. `create NAME --image REF` uses a custom image instead: the
Agent Context then makes no claims about its operating system or tools, the image needs
`python3` for `run` and `shell`, and it is pulled at the first start if it is not present.

The distribution family is fixed, not the OS of a future rebuilt base tag. Installing a newer
manager does not rebuild images. Rebuilding a base affects future containers created from
that base, **not existing containers**. Stop/start, settings recreation, snapshots and backups
with the system layer retain the old OS and packages. A Debian 12 environment is still 12
after the manager's default definition becomes 13; Debian 12 has LTS-only support until
2028-06-30.

For the new default, first explicitly run `opencode-sandbox build --distro debian`; `doctor`
compares its revision with the installed definition. Then create a new environment and transfer
your work, or explicitly restore with `backup restore BACKUP NEW --no-system`. The latter keeps
workspace/home files but discards the old system layer and installed packages, using the local
current base. A backup that includes its system image instead keeps its old OS. Do not delete
the old environment until you have checked the new one.

`status NAME` reports the base OS from the owned container's inherited build labels, or from
the selected image when no container exists. Derived/restored images retain those labels.
Unavailable/malformed labels are unknown, never guessed from the current definition. The
metadata-only dashboard and `create` output do not probe Docker to invent an OS version;
their version is marked uninspected. Build labels describe the base, not OS upgrades you made
inside a container; inspect `/etc/os-release` there when an exact current version matters.

### Arch Linux environments

- Repository packages: `pacman -Syu --needed PACKAGE` (Arch has no partial upgrades).
- AUR packages: `ocs-aur -S PACKAGE`, as the container's root (the default user). `ocs-aur` runs
  the AUR helper `paru` as the unprivileged user `aurbuild` in `/var/lib/aurbuild` (never in
  `/workspace`) and performs paru's `pacman` calls as root through a broker that exists only
  while `ocs-aur` runs and only accepts `pacman` from paru itself, not from PKGBUILD code.
  `makepkg` and `paru` refuse to run as root, and `sudo` cannot work under `no-new-privileges`.
- Review PKGBUILDs first (`ocs-aur -Gp PACKAGE`): installed packages run as root inside the
  container. `aurbuild` maps to a subordinate UID on the host; container root maps to you.
- Packages live in the system layer ([concepts.md](concepts.md#where-things-live)).
- If a `pacman -Syu` inside an environment installs a pacman with a new libalpm version,
  `ocs-aur` stops working in that environment until it is created again from a rebuilt base
  image (`opencode-sandbox build --distro arch`).

## Initial integrations

By default every new environment (also `quick` and the dashboard's) asks for the **Context7**
remote MCP server: current library documentation, public, no key, needs network. Options of
`create`:

| Option | Effect |
|---|---|
| `--no-integrations` | No integrations |
| `--integration NAME` | Choose from the catalog (`create --help`); repeatable; replaces the default |
| `--mcp-remote NAME=URL` | A custom remote MCP server |
| `--mcp-local "NAME=COMMAND ARGS"` | A custom local MCP server |

Custom servers take no headers or secrets; add keys yourself later. At the **first start** the
manager runs `opencode mcp add --global` in the container, which writes
`/root/.config/opencode/opencode.json` in the home volume. If any global OpenCode configuration
already exists there, nothing is written ("skipped").

The outcome is recorded once (`status`, and the Agent Context says "configured", never
"working"; with network `none` remote servers are marked as unable to work offline) and is
**never applied again**: not on later starts, recreation, settings changes, updates or restores,
and no drift is checked. After the first start the configuration is yours. A failure does not
stop the start; `start` and `status` print the `opencode mcp add` commands to run yourself.

## Everyday commands

| Command | Does |
|---|---|
| `list` | All environments |
| `status NAME` | Metadata, container state, configured and actual network, published ports, the last readiness result |
| `check NAME` | Read-only readiness check ([maintenance.md](maintenance.md#readiness-checks)) |
| `start NAME`, `stop NAME` | Start or stop the container |
| `run NAME` | OpenCode in `/workspace` with the provider profile ([opencode.md](opencode.md)) |
| `shell NAME` | A root bash |
| `exec NAME -- CMD` | One command, for scripts: no provider profile, and the Agent Context is not regenerated |
| `delete NAME [--export-first] [--yes]` | Show the changes, optionally export them, delete |
| `promote NAME scratch\|project` | Keep a quick session |
