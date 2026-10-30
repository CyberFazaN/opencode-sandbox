# Security policy

## Supported versions

Only the latest release receives fixes. Upgrade by installing the newest tag
([docs/install.md](docs/install.md#upgrade-or-change-the-version)).

| Version | Supported |
|---|---|
| 6.0.x | yes |

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's private vulnerability reporting: the
repository's **Security** tab, then **Report a vulnerability**.

Include the version (`opencode-sandbox --version`), the output of `opencode-sandbox doctor`, the
steps to reproduce, what happens and what you expected. Remove keys, tokens and private paths.

This is a project maintained by one person in their own time. Reports are acknowledged and
investigated on a best-effort basis; there is no bug bounty. A confirmed vulnerability is fixed in
a new release, and a GitHub security advisory describes it once the fix is available. Please give
the maintainer a reasonable time to fix it before you disclose it.

## Scope

In scope: ways in which OpenCode Sandbox itself fails to keep a boundary it claims
([docs/security.md](docs/security.md)), for example:

- the daemon identity check accepts a daemon that is not the user's own rootless daemon;
- an environment gets host access beyond its documented workspace and mounts;
- credentials leak into logs, metadata, process listings, exports or backups;
- the `changes` commands let the sandbox's repository run code on the host or write outside the
  target repository;
- a backup restore writes outside its target, or `disk cleanup` removes objects it does not own.

Out of scope: the limitations documented in [docs/security.md](docs/security.md#what-it-does-not-give-you),
for example container escapes through kernel or Docker bugs, network access in `bridge` mode, the
agent reading the credentials mounted into its own container, the effects of a direct workspace,
and labels forged by processes that can use the same Docker daemon. Vulnerabilities in OpenCode,
Docker, the base images or the distributions' packages belong to those projects.
