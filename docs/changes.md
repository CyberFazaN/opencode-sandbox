# Reviewing and transferring changes

The agent works on a copy of your project, so its work reaches your repository only when you
move it there. The `changes` commands do that without letting the sandbox's repository act on
your host.

They apply to project environments imported from Git (also after a restore of one: the restore
keeps the base commit). For a non-Git workspace, `changes export` archives the whole workspace.
A direct workspace has no `changes`: its changes are already in your directory.

```sh
opencode-sandbox changes show NAME            # commits, diffstat, working tree
opencode-sandbox changes export NAME          # .tar.gz archive in exports/
opencode-sandbox changes bundle NAME          # checksummed change bundle
opencode-sandbox changes inspect BUNDLE       # full patch, untracked files
opencode-sandbox changes review BUNDLE ~/code/repo   # validate, no writes
opencode-sandbox changes stage BUNDLE ~/code/repo    # review branch
opencode-sandbox changes branch-diff ~/code/repo ocs/review-<id>
opencode-sandbox changes unstage ~/code/repo ocs/review-<id> COMMIT
opencode-sandbox changes apply BUNDLE ~/code/repo --yes   # into the tree
```

## The recommended path

1. `changes bundle NAME` writes a bundle: the patch against the base commit, the untracked
   files, and `history.bundle` with the sandbox's commits, all checksummed.
2. `changes inspect BUNDLE` prints the complete patch and the untracked files.
3. `changes stage BUNDLE REPO` creates the review branch `ocs/review-<id>` (or `--branch`) in
   your repository. It contains the exact final sandbox tree as one commit; your working tree and
   current branch are not touched. The original commits are in `history.bundle`.
4. Review the branch (`changes branch-diff REPO BRANCH`, or your usual tools) and merge it.
   `changes unstage REPO BRANCH COMMIT` removes the branch, only if it still points to that
   commit.

`changes apply BUNDLE REPO --yes` writes the changes straight into your working tree instead. It
refuses untracked symlinks; if writing fails midway, the repository is restored to its previous
clean state.

## Checks

- The source must be a clean repository root at the exported base commit; otherwise the command
  refuses and changes nothing.
- The workspace repository is controlled by the agent, so these commands never use its Git
  configuration, hooks or drivers. Host Git runs with a private configuration written by the
  manager (only the repository's storage format is carried over).
- A workspace whose index contains a submodule entry (gitlink) is refused by every command;
  remove it inside the sandbox with `git rm --cached PATH`.
- Symlinks, tracked or untracked, are transferred only when their target stays inside the
  repository (a link the source already has at the base commit is kept); otherwise `review`,
  `stage` and `apply` refuse and name the link. A tree with such links, for example a Python
  `.venv`, should be ignored in `.gitignore` or removed.
- `inspect`, `review` and `stage` list paths to review with care: files that host tools act on
  (`.gitattributes`, `.gitmodules`, `.envrc`, CI, editor and hook-manager directories such as
  `.github/`, `.vscode/`, `.husky/`), symbolic links and files that become executable. Untracked
  files keep their executable bit.
- Text from the sandbox (commit messages, file names, patch lines) is printed with control
  characters escaped (`\x1b`, `\r`).
- Ignored files, submodules and embedded repositories are not transferred.
- No operation is atomic against other processes writing to your repository at the same time.

`changes show` needs Git on the host for Git workspaces; `changes export`, `bundle` and
`--destination` outputs go to `exports/` and `changes/` in the data directory by default.
