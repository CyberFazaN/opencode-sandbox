# OpenCode Configs

## Profiles and creation

Put named, user-maintained directories in `~/.config/opencode-sandbox/opencode-configs/`
(`OPENCODE_SANDBOX_CONFIG` changes the parent). Names use 1–64 ASCII letters, digits, `.`, `_`
and `-`, beginning with a letter/digit. A symlink at a profile root may point elsewhere:

```sh
mkdir -p ~/.config/opencode-sandbox/opencode-configs
ln -s ~/my-opencode-config ~/.config/opencode-sandbox/opencode-configs/work
opencode-sandbox opencode-configs list
opencode-sandbox create webapp --opencode-config work
```

The main dashboard's **OpenCode Configs** button (`O`) lists profiles and their directory.
Manage sources yourself with host tools: the application never rewrites, edits or normalizes them.
Profiles can contain credentials, executable plugins and MCP commands; read-only import does not
make them safe. No code from a profile executes on the host manager.

New → More options offers **Local** (default, no import) and **Copy** (requires a selected
profile). An empty profile list does not block Local. Copy validates/snapshots the whole source
before persistent environment changes, imports into a genuinely fresh home volume before any
OpenCode launch, and fails creation safely if copying fails. Later source changes/removal do not
affect the environment. Its original profile identifier is only a future Reload convenience.
Normal image-provided home files are retained. If an image already seeds a nonempty global
config directory, initial Copy refuses rather than merging/overwriting it; use Local, then an
explicit Reload if replacement is wanted. Later transfer helpers never re-seed the home volume.

## What is copied

Every operation covers the **entire global/local `/root/.config/opencode/` tree**, including files
beyond `opencode.json(c)`, `cli.json`, plugins/dependencies and runtime-generated files. Reload
and Empty can therefore lose credentials or local state stored **in this tree**.

It is **not the complete effective configuration**. `/etc/opencode/`, project `.opencode/`,
project config/`AGENTS.md`, environment variables and native OpenCode precedence/merging still
matter. The manager does not resolve effective config. Other OpenCode home data, state, caches
and auth outside this boundary are never cleared. Use `opencode debug paths` inside a sandbox
to see that OpenCode version's actual locations.

Directories, regular-file bytes, permission/executable bits and symlink link text are preserved;
regular hard links become independent files. Internal symlinks are never followed or archived
recursively. Absolute host links may mean something different or be broken inside the container;
their usefulness is your responsibility. Sockets, FIFOs, devices and other unsupported entries
fail the operation clearly, never silently disappear from a purported whole copy.

Large profiles take time. Progress identifies copying/validation without printing file contents.
Transfers stream to private file-backed archives, with a default 64 GiB regular-file byte ceiling,
2,000,000 entries, bounded archive/metadata overhead, filesystem-space headroom and a 30-minute
helper safety deadline. Limits are documented
in [concepts](concepts.md#environment-variables); the filesystem must support Linux atomic
directory exchange. Custom images need Python and GNU timeout.
Images declaring additional volumes overlapping this global tree are refused: otherwise a helper
could export a different anonymous volume instead of the environment's persistent home data.

## OpenCode Config Editor

Environment Settings (`t`) → **OpenCode Config Editor** is a **file-transfer screen**, not an
embedded editor. It displays **No export** or **Export available**, its exact host path and actions:

1. **Export Config** makes an editable host snapshot. Replacing an existing export requires
   confirmation that existing host edits will be lost; Cancel preserves it. Failed export leaves
   the old workspace intact, never a half-written replacement.
2. Edit files with your host tools at the displayed path.
3. **Apply Export** stages a consistent snapshot and replaces the entire container global tree.
   It compares the current **container** tree with the baseline from the last successful
   Export/Apply—not with your edited export. Changes in the container offer exactly **Cancel**
   and **Overwrite Anyway**. A further change requires new consent; no automatic merge occurs.
   Successful Apply keeps the export and advances its baseline to the actual installed tree.
4. **Delete Export** always confirms loss of unapplied host edits. Only the validated host export
   is deleted; the container tree is untouched.

CLI equivalents (the status command shows the exact editable path):

```sh
opencode-sandbox opencode-configs status NAME
opencode-sandbox opencode-configs export NAME
opencode-sandbox opencode-configs apply NAME
opencode-sandbox opencode-configs apply NAME --overwrite
opencode-sandbox opencode-configs delete-export NAME --yes
```

`export --yes` accepts replacement of an existing export. Apply's `--overwrite` explicitly
accepts the observed container drift; it never bypasses validation, final rechecking or recovery.
Without it a noninteractive conflict cancels with an error; interactive overwrite defaults Cancel.

Exports live under a validated own-UID `0700` namespace in `/tmp`, keyed by manager data-root
identity and the stable environment ID, not the Docker container ID or environment name. Rename
or recreation finds the same export; deleting/reusing a name does not attach it to a new environment.
Ownership/identity/baseline metadata lives outside editable `config/`; changing files there cannot
alter the saved baseline. Unsafe collisions, symlinked or foreign-owned/non-private workspaces
are refused, never adopted or deleted. An own private export whose marker or `config/` is missing
or invalid shows **Invalid export** with its path: Apply is disabled (drift detection is never
bypassed); a confirmed Export replaces it or Delete Export removes it. No export path is stored in
persistent application state.

Closing the editor never deletes the export. A reminder explains that it can be reopened while
the directory remains, but reboot or `/tmp` cleanup may remove it. A missing directory simply
means No export; there is no missing-export monitoring or cross-reboot recovery promise. Treat
exports as sensitive: `0700` excludes other ordinary users, not host root or same-UID processes.
Environment deletion does not silently delete unapplied host exports; it reports a retained
export's path. Delete Export first if wanted. Read-only directories copied from the container
(for example `0555` package directories) do not block replacement or deletion.

## Reload or Empty

Settings → **Reload Config** is separate from the editor. Choose a currently discoverable profile
or **Empty**; the original creation choice is preselected only while available. Local environments
default to Empty. Confirm replacement of the entire global config directory, not a JSON merge.
Empty keeps the directory present but completely clears its local configuration.

```sh
opencode-sandbox opencode-configs reload NAME --profile work --yes
opencode-sandbox opencode-configs reload NAME --empty --yes
```

Without either selection option, the CLI chooses the original profile, or Empty for a Local
environment, and discloses that choice before confirmation. If the original profile is no longer
available, it refuses and asks for `--profile` or `--empty`. Reload is a new independent
copy, not a live link. Existing exports remain available; a later Apply can detect the reload
as container drift. Neither Reload nor Apply stops/restarts the container or inspects sessions.
Only running containers get the active-OpenCode warning; no hot-reload guarantee is made.

## Failure and recovery

Replacement stages on the home volume, validates the source and destination, preserves the old
tree, atomically exchanges directories, verifies installed bytes/modes and durably commits.
Failed/interrupted transfers block normal lifecycle work with the existing operation journal:

```sh
opencode-sandbox opencode-configs recover NAME
```

The editor offers **Recover transfer** when needed. Recovery retains a durably committed new
tree or restores the old one for an uncommitted switch; an unknown/unsafe transaction is preserved
for manual inspection, not guessed away. Recovery does not invent a new export baseline: re-export
or review subsequent drift. Container helpers serialize on a volume lock even if their host client
dies. If Docker is unavailable, wait for the named helper to end and retry recovery; do not manually
remove volume transaction files or locks while it may still run.
The private transaction boundary is `/root/.config/.ocs-occonfig-transaction/`, outside the editable
global tree. Its identity/commit marker is retained until old-tree cleanup finishes, so interrupted
cleanup can resume too; an unmarked, empty reserved stage contains no user data and is safely removed.

Manager locks coordinate manager actions, **not OpenCode or arbitrary in-container writers**.
Stable sampling and final digest checks detect concurrent changes but cannot freeze a malicious
same-UID process. Prefer applying/reloading while stopped. Existing `/root` backups include the
independent global tree; source profiles and temporary exports are not included.
