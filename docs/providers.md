# Provider profiles

A provider profile is a named set of credentials (environment variables such as
`OPENROUTER_API_KEY`) that OpenCode uses to reach a model provider.

```sh
opencode-sandbox providers set work --key OPENROUTER_API_KEY   # hidden prompt
opencode-sandbox providers list                                # names only
opencode-sandbox create webapp --source ~/code/webapp --profile work
```

- `providers set NAME --key VAR` reads the value at a hidden prompt (it needs a terminal) and
  stores it in `~/.config/opencode-sandbox/profiles/NAME.json` with mode `0600`. A profile can
  hold several variables; run the command once for each.
- `providers list` shows profile and variable names, never the values.
- `create --profile NAME` refuses a profile that does not exist. Without `--profile` the
  environment uses the profile `default`, which may be absent (no credentials).
- Executable `.env` profiles of older tools are refused, never sourced; symlinked files, wrong
  permissions and invalid JSON are refused too.
- `OPENCODE_CONFIG_CONTENT`, `OPENCODE_CONFIG` and `OPENCODE_CONFIG_DIR` are reserved and
  rejected, including in existing/manually edited profiles and the container launcher. Use native
  OpenCode config files or [OpenCode Configs](opencode-configs.md), not provider variables, to
  select configuration. Other valid provider variables, including unrelated `OPENCODE_*` keys,
  remain usable. Errors never show credential values. `providers list` marks such a profile as
  unusable; remove the reserved key from its `0600` JSON file with an editor.

## How a profile reaches OpenCode

The selected profile file is mounted read-only at `/run/secrets/ocs-provider.json` **when the
container is created**, and `run` and `shell` load it into the OpenCode process.

- Another profile for an existing environment: `config apply NAME --profile OTHER --yes`. It
  recreates the container so that it mounts the new profile (the system layer, `/workspace` and
  `/root` are kept); a restart alone keeps the previously mounted profile. `status`, `run` and
  `shell` warn while the container still uses a different profile.
- After changing a key of the same profile, a **restart** is enough (`stop`, then `run`): the
  running container keeps the old file until it restarts. `check NAME` reports a profile changed
  after the container started.
- A deleted profile file blocks `start` with an explanation; restore the file, or run
  `container recreate NAME --yes` to continue without it.
- Generic `exec` and direct `docker exec` shells do not load the profile. Both base images
  provide the executable `ocs-opencode`: it reads/validates the mounted JSON safely and launches
  `opencode --standalone`, preserving arguments. For example:

  ```sh
  opencode-sandbox exec NAME -- ocs-opencode --version
  ```

  Interactive Bash shows a brief hint only when a mounted profile has not already been loaded.
  The manager's `shell` has already injected it and does not show the misleading missing-profile
  hint. No aliases, shell evaluation or sourcing of credential JSON are involved.
  Local diagnostic subcommands that reject OpenCode's `--standalone` flag (for example
  `debug paths` in 2.2.0) use plain `opencode`; they do not start a provider server.
  Older retained environment layers may lack `ocs-opencode`; rebuilding a base affects future
  containers, not those layers. Managed `run`/`shell` use the current manager's shared launcher.

## Choosing a model

Choose the model in OpenCode (`/models`) or in the environment's
`~/.config/opencode/opencode.json` (in the home volume), for example
`{"model": "openrouter/z-ai/glm-5.3-flash"}`. The network mode must be `bridge`; with `none` no
provider is reachable.

## What to keep in mind

- The agent runs as root in its container and **can read the mounted credentials**. Use scoped,
  budget-limited keys.
- Credentials created inside the container (for example OpenCode's own login) live in the home
  volume and are part of backups. Profiles are not part of backups.
- The project's automated tests use a fake OpenAI-compatible provider and dummy keys. One
  real provider was tested with OpenCode 2.2.0: OpenRouter (`OPENROUTER_API_KEY`,
  `openrouter/z-ai/glm-5.3-flash`), including that the key stays out of process listings,
  the container definition, the home volume and backups. Other providers are untested.
