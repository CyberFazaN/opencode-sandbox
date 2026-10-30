# Concepts

## Terms

- **Environment**: one named sandbox: a container `ocs-<id>`, its `/workspace`, its home volume
  and its settings. Kinds: **scratch** (an empty workspace), **project** (a copy of a folder)
  and **quick** (a disposable session, see `quick`).
- **Workspace** (`/workspace`): **managed** (the default): kept in the manager's data directory,
  empty or a copy of a folder, never your original; or **direct** (not recommended): your
  existing folder itself. See [workspaces.md](workspaces.md).
- **Distribution**: the family selected at creation: Debian (`debian`, the default) or Arch
  Linux (`arch`); or a custom image. The current Debian base definition is 13. The container's
  base OS version comes from the image actually used, not the latest registry definition;
  retained containers may still use Debian 12. It is independent of your host's distribution.
- **Provider profile**: a named set of model-provider credentials on the host, mounted read-only
  into the container ([providers.md](providers.md)).
- **Settings**: CPU, memory and process limits, the network mode, published ports and the
  provider profile, changed through one change plan (`config`, [settings.md](settings.md)).
- **Initial integrations**: MCP servers written once into the environment's OpenCode
  configuration at its first start (default: Context7). Afterwards they are yours.
- **Agent Context**: guidance the manager gives OpenCode about the sandbox: user, workspace,
  network, limits, operating system ([opencode.md](opencode.md#agent-context)).
- **OpenCode version**: installed and updated only by the manager, per base image and per
  environment, with a policy (notify, manual, pinned).
- **Data directory**: where the manager keeps metadata, workspaces, exports and backups. Several
  data directories can share one Docker daemon; each one only manages its own objects.

## Where things live

| What | Location | Survives stop/start | Survives `container recreate` / `config apply` | In `container snapshot` | In `backup create` |
|---|---|---|---|---|---|
| Workspace (`/workspace`), managed (default) | host directory `~/.local/share/opencode-sandbox/environments/<id>/workspace` | yes | yes | no | yes |
| Workspace (`/workspace`), direct (not recommended) | your own directory, mounted as it is | yes | yes | no | only with `--include-workspace` |
| Home (`/root`: OpenCode sessions, its own logins, npm cache) | Docker volume `ocs-home-<id>` | yes | yes | no | yes |
| System layer (installed packages, files elsewhere) | the container's writable layer | yes | yes (committed to an image and used for the new container) | yes | yes, unless `--no-system` |
| Metadata, exports, change bundles, backups, locks | `~/.local/share/opencode-sandbox/` | | | | metadata only |
| Provider profiles, dashboard preferences | `~/.config/opencode-sandbox/` | | | no | **no** |

Containers keep running after a session ends; `stop` stops them. Closing the terminal of `run`
or `shell` hangs up that session inside the container (jobs started with `nohup` keep
running). The same happens when the manager process ends, also when it is killed with
`SIGKILL`: a small watchdog started with each session notices it and hangs up the session.

## Names

- Environment names: 1 to 64 ASCII letters, digits, `.`, `_` and `-`, starting with a letter
  or digit; unique; not 16 hexadecimal characters (that is the form of an environment id).
- Commands take a name or an id: an exact id first, then an exact name, then an id prefix of at
  least 6 characters that matches only one environment.
- Docker objects: container `ocs-<id>`, volume `ocs-home-<id>`, images `ocs-snapshot:*`,
  `ocs-runtime:*` (the system layer after a recreation), `ocs-checkpoint:*` (before an OpenCode
  update), `ocs-backup:*` (a restored system layer); base images `opencode-sandbox:<distro>`
  with rollback copies `opencode-sandbox:<distro>-previous-<hex>`.

## Labels and ownership

Docker objects created by the manager carry the labels `org.opencode-sandbox.managed=true` and
`org.opencode-sandbox.manager-version`. Everything except the base images also carries
`org.opencode-sandbox.data-dir` (a hash of the data directory's path), per-environment objects
carry `org.opencode-sandbox.id`, short-lived helper containers `org.opencode-sandbox.helper`.
Base images also carry `org.opencode-sandbox.distro`, `distro-version`, `image-revision` and
`opencode-version` (the version installed when the image was built; images derived from it
inherit the label, so use `opencode versions` for what a container runs).

Containers inherit their image's labels, so a container that you create yourself from a
manager image looks labelled; `disk cleanup` only treats environment containers and
helper-labelled containers as the manager's. Any process that can use your Docker daemon can
create objects with forged labels ([security.md](security.md#known-limitations)).

Metadata and backups of another schema version are not migrated: `list` reports such metadata
as unsupported, `backup restore` refuses such backups, and the manager never modifies or deletes
them.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `OPENCODE_SANDBOX_HOME` | `~/.local/share/opencode-sandbox` | Data directory |
| `OPENCODE_SANDBOX_CONFIG` | `~/.config/opencode-sandbox` | Configuration directory (provider profiles, preferences) |
| `OPENCODE_SANDBOX_DOCKER_CONTEXT` | `rootless` | Docker context of your rootless daemon |
| `OPENCODE_SANDBOX_DOCKER_RESERVE_BYTES` | 2 GiB | Free space Docker must keep for commits, updates and builds |
| `OPENCODE_SANDBOX_BACKUP_RESERVE_BYTES` | 512 MiB | Free space a backup or restore needs on top of its estimated size |
| `OPENCODE_SANDBOX_MAX_ARCHIVE_ENTRIES` | 2000000 | Largest number of entries a backup archive may have |

The manager does not use `XDG_DATA_HOME` or `XDG_CONFIG_HOME`; set the variables above instead.
It ignores `DOCKER_HOST`, `DOCKER_CONTEXT`, `DOCKER_TLS_VERIFY` and `DOCKER_CERT_PATH`
(`doctor` notes when they are set): the endpoint always comes from the context.
