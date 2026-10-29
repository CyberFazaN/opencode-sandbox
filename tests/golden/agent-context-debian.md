# OpenCode Sandbox — environment guidance (managed)

You are running inside a Docker container, not on the host operating system.
This is context, not a security boundary. Actual access depends on Docker mounts, privileges and network configuration.

## Container, user and privileges
- Container image: opencode-sandbox:debian
- You run as root (UID 0) in the container. Rootless Docker maps it to the host user who owns this sandbox: files you create in /workspace belong to that user on the host. Other container users map to unprivileged subordinate IDs, so files they create there may not be editable on the host.
- The container runs with no-new-privileges: sudo and setuid programs cannot raise privileges. Container root is not root on the host.
- There is no Docker socket and no host package manager in the container. Host files are mounted only at /workspace (plus read-only files the manager provides under /run). Do not try to manage the host, the Docker daemon, hardware or system services.
- Do not assume access to GPU, USB, cameras or audio.

## Workspace and persistence
- Environment: demo (project). Working directory: /workspace. Work on project files here.
- /workspace holds a copy of a host directory, made when the environment was created (Git repository: committed files only; other directories: a filtered copy). The original is not mounted: your edits reach it only when the user exports or applies them with the manager.
- /workspace is a bind mount from the host and /root a persistent Docker volume (OpenCode state, user data): both survive stopping, recreating and reconfiguring the container.
- Packages and files elsewhere live in the container's system layer: kept across stop/start, recreation and runtime changes, but lost when the user restores a backup without it. Do not assume they are permanent.
- Keep credentials out of command output, logs, source files and answers.

## Network and resources
- Networking mode: bridge
- Docker bridge networking is enabled: the internet, other machines on the local network and services on the host's network addresses may be reachable. This is not network isolation; use only the network services your task needs.
- Published port: container 8080/tcp is reachable from the host at 127.0.0.1:18080 only; a server must listen on 0.0.0.0 (not 127.0.0.1) in the container.
- CPU limit: 2.0
- Memory limit: 4g
- Process limit: 100

## Operating system (Debian 12)
- Base OS: Debian 12. Use apt, not the host's package manager.
- Installing system packages: `apt-get update && apt-get install -y PACKAGE` as root (needs network).
- The managed base image includes: bash, git, git-lfs, python3, pip3, node, npm, opencode, rg, jq, curl, gcc, cmake.
- Tools may have been changed after image creation; check only when the task needs an exact version or availability.

## Working behavior
- Start with the user's task; avoid a full system inventory or repeated probing.
- If a dependency is missing, explain the required change; use container-local installation only when appropriate and permitted.
- Never attempt to bypass container boundaries or reconfigure the host.
- OpenCode's own update check is off in this container (OPENCODE_DISABLE_AUTOUPDATE=1): the sandbox manager on the host installs and updates OpenCode. Do not run `opencode upgrade`.
- Follow project AGENTS.md instructions in addition to this environment guidance.
