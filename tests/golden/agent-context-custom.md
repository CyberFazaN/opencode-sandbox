# OpenCode Sandbox — environment guidance (managed)

You are running inside a Docker container, not on the host operating system.
This is context, not a security boundary. Actual access depends on Docker mounts, privileges and network configuration.

## Container, user and privileges
- Container image: example.org/team/tools:1
- The container user is defined by the custom image. Rootless Docker maps container UID 0 to the host user who owns this sandbox and other UIDs to unprivileged subordinate IDs.
- The container runs with no-new-privileges: sudo and setuid programs cannot raise privileges. Container root is not root on the host.
- There is no Docker socket and no host package manager in the container. Host files are mounted only at /workspace (plus read-only files the manager provides under /run). Do not try to manage the host, the Docker daemon, hardware or system services.
- Do not assume access to GPU, USB, cameras or audio.

## Workspace and persistence
- Environment: demo (quick). Working directory: /workspace. Work on project files here.
- /workspace started empty; it is not connected to any host project.
- This is a quick (disposable) session: when it ends, the user decides whether to export, keep, promote or delete it. Do not rely on /workspace being kept.
- /workspace is a bind mount from the host and /root a persistent Docker volume (OpenCode state, user data): both survive stopping, recreating and reconfiguring the container.
- Packages and files elsewhere live in the container's system layer: kept across stop/start, recreation and runtime changes, but lost when the user restores a backup without it. Do not assume they are permanent.
- Keep credentials out of command output, logs, source files and answers.

## Network and resources
- Networking mode: bridge
- Docker bridge networking is enabled: the internet, other machines on the local network and services on the host's network addresses may be reachable. This is not network isolation; use only the network services your task needs.
- CPU limit: 2.0
- Memory limit: 4g
- Process limit: 100

## Operating system
- Custom image: installed tools, OS and package manager are unknown; inspect only when needed.

## Working behavior
- Start with the user's task; avoid a full system inventory or repeated probing.
- If a dependency is missing, explain the required change; use container-local installation only when appropriate and permitted.
- Never attempt to bypass container boundaries or reconfigure the host.
- OpenCode's own update check is off in this container (OPENCODE_DISABLE_AUTOUPDATE=1): the sandbox manager on the host installs and updates OpenCode. Do not run `opencode upgrade`.
- Follow project AGENTS.md instructions in addition to this environment guidance.
