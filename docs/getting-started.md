# Getting started

This walk-through assumes the application is installed and Docker is prepared
([install.md](install.md)). The terms are explained in [concepts.md](concepts.md).

## 1. Check the host

```sh
opencode-sandbox doctor
```

The daemon identity must be `verified`; read any resource, image or storage warnings too. Exit 0
does not certify every advisory or measured resource enforcement. See
[troubleshooting.md](troubleshooting.md) for failures. Build a base image if `doctor` reports none:
`opencode-sandbox build`.

## 2. Store a provider key

OpenCode needs credentials for a model provider. Store them in a named provider profile; the
value is read at a hidden prompt and never displayed again:

```sh
opencode-sandbox providers set work --key OPENROUTER_API_KEY
```

Use a scoped, budget-limited key: the agent runs as root inside its container and can read it.
Details: [providers.md](providers.md).

## 3. Create an environment

An empty workspace:

```sh
opencode-sandbox create demo --profile work
```

Or a copy of a project: a Git repository is cloned (committed only by default), any other folder is
copied without hidden files. The original folder is never mounted or changed.

```sh
opencode-sandbox create webapp --source ~/code/webapp --profile work
```

For in-progress Git work, add `--include-working-changes`: preview and import staged/unstaged
changes and non-ignored untracked files, preserving the source. The dashboard offers the same
**Git import** choice in New. Ignored untracked files stay out; non-ignored secrets do not.
See [Git import modes and limits](workspaces.md#git-import-modes).

`create` prints its choices and the next command. OpenCode config defaults to **Local** (no
initial import); `--opencode-config PROFILE` copies a user-maintained directory once. Specialized
Agent Context defaults on; `--no-agent-context` disables automatic inclusion without removing
the file. See [OpenCode Configs](opencode-configs.md), [workspaces.md](workspaces.md) and
`create --help` for other choices.

## 4. Work with OpenCode

```sh
opencode-sandbox run webapp
```

This starts the container if needed and opens OpenCode in `/workspace`. Choose a model with
`/models` in OpenCode. When you quit OpenCode, the container keeps running; the workspace,
OpenCode's sessions and anything you installed stay until you delete the environment.

Other ways in:

```sh
opencode-sandbox shell webapp            # a root shell in the container
opencode-sandbox exec webapp -- ls -la   # one command (no provider profile)
opencode-sandbox stop webapp             # stop the container
```

Inside a project folder you can leave out the name: `run` and `shell` pick the environment that
was created from that folder.

## 5. Take the changes back

The agent works on a copy, so its changes reach your repository only when you transfer them:

```sh
opencode-sandbox changes show webapp
opencode-sandbox changes bundle webapp
opencode-sandbox changes stage BUNDLE ~/code/webapp
```

`changes stage` creates a review branch `ocs/review-<id>` in your repository without touching
your working tree. Review it like any other branch. [changes.md](changes.md) explains the
bundle, the checks and the alternatives.

## 6. The dashboard

```sh
opencode-sandbox
```

Without arguments in a terminal, the manager opens the dashboard: the environments, their state
and settings, and keys for every common action (`?` lists them). See
[dashboard.md](dashboard.md).

## 7. Disposable sessions

```sh
opencode-sandbox quick --source ~/code/webapp
```

`quick` creates a throw-away environment and opens OpenCode in it. When you leave, it asks
what to do: export the changes and delete, keep it as a scratch environment, delete, or keep it
as a quick session (the default). It needs a terminal.

## 8. Clean up

```sh
opencode-sandbox delete demo
```

`delete` shows the environment's changes and asks you to type its name (`--export-first`
saves the changes before). It removes the container, the home volume, the workspace copy and
the metadata. `opencode-sandbox disk usage` shows what is left over and
[maintenance.md](maintenance.md) how to remove it.
