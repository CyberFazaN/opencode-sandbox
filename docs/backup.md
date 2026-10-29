# Backup, restore and snapshots

## Backups

```sh
opencode-sandbox backup create NAME [--stop] [--no-system]
opencode-sandbox backup create NAME --include-workspace --destination DIR
opencode-sandbox backup list
opencode-sandbox backup verify PATH
opencode-sandbox backup prune --keep 5 [--yes]
```

`backup create` makes a **cold** backup: a running environment needs `--stop` (it stays
stopped). The result is a `0700` directory `*.ocsbackup` (default: `backups/` in the data
directory) with a SHA-256 manifest and:

- the workspace; a direct workspace only with `--include-workspace`;
- the home volume (`/root`), archived with GNU tar in a helper container from the environment's
  local base image (never pulled), keeping numeric owners, permissions, symlinks, ACLs and
  extended attributes;
- the system layer, unless `--no-system`: committed from the container or, when the
  environment has no container (after a network, port or profile change while stopped, an
  OpenCode rollback, or a restore that was never started), saved from the image the next
  container would use.

Details:

- Sockets and FIFOs (in the workspace and in `/root`) are left out, listed in `manifest.json`
  and named in the output. Device files and file names containing a backslash refuse the
  backup, naming the file.
- Symlinks in the workspace are stored and restored as links, verbatim, also absolute ones and
  ones pointing outside the workspace (a Python venv has `bin/python -> /usr/bin/python`); the
  manager never follows them, and a restore never writes through a link.
- Every archive is checked with the restore rules before the backup is published.
- Backups are **not encrypted**. Provider profiles are not included, but credentials created
  inside the container (in `/root`) are.
- `--destination` (also of `changes export` and `changes bundle`) is refused inside any
  environment's workspace, where the agent could change the output. Existing destination
  directories are not re-permissioned.

`backup prune --keep N` keeps the N newest **verified** backups per environment (name and
environment id, so a later environment with the same name has its own count), ordered by the
creation time recorded in the backup, not the directory's time. Without `--yes` it only shows
what it would delete. Unverifiable entries are reported and never deleted.

## Restore

```sh
opencode-sandbox backup restore BACKUP NEWNAME [--no-system]
opencode-sandbox backup restore-check NEWNAME
```

A restore always creates a **new** environment; it never writes over existing work or into a
direct workspace. It is staged, with a space check and archive validation first (path
traversal, symlink escapes, special files, entry and size limits).

- Only restore backups you trust: the system image is executable content.
- A restored system image becomes the new environment's own `ocs-backup:<id>-*` image.
- A custom-image environment records the image it was created from; a restore without the system
  layer uses that image (pulled at the first start if it is not present; the restore warns).
- `restore-check` starts the restored environment and smoke-tests OpenCode and the mounts.
- An interrupted restore stays in `error/restore`: `backup restore-resume NAME` retries it while
  its target is still empty, `backup restore-rollback NAME --yes` deletes the incomplete
  environment.

## Snapshots and recreation

```sh
opencode-sandbox container snapshot NAME [--tag TAG]
opencode-sandbox container recreate NAME --yes
```

- `container snapshot` is `docker commit`: the **system layer only**, not the workspace or
  `/root`. Without `--tag` the tag is `ocs-snapshot:<id>-<time>-<random>`. `--tag` must be a new
  tag outside the manager's repositories (`opencode-sandbox`, `ocs-snapshot`, `ocs-runtime`,
  `ocs-checkpoint`, `ocs-backup`), except `ocs-snapshot:<id>-NAME`; an existing tag is never
  moved. Images with other names are yours: `disk usage` lists them, cleanup never removes them.
- `container recreate` stops a running container (gracefully), snapshots its system layer and
  runs a new container from it; workspace and home volume stay. After an interruption,
  `container recreate-recover NAME` finishes it (it refuses while the old container still runs
  and says how to stop it).

What each of these keeps: [concepts.md](concepts.md#where-things-live).
