# Build context: assets/images/ (shared files in common/). Labels come from the registry
# (distros.py) at build time.
# Use the same Node and npm as Debian without pulling Kali's full npm build-tool dependency tree.
FROM node:24-trixie AS node-runtime
FROM docker.io/kalilinux/kali-rolling
ENV DEBIAN_FRONTEND=noninteractive
# Every build upgrades installed packages: the manager passes a per-build nonce, so this layer
# runs with fresh indexes even when earlier layers are cached.
ARG SYSTEM_PACKAGE_REFRESH
RUN test -n "${SYSTEM_PACKAGE_REFRESH:?build with --build-arg SYSTEM_PACKAGE_REFRESH}" && apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends \
 bash ca-certificates curl git git-lfs openssh-client libstdc++6 python3 sudo tar \
 && rm -rf /var/lib/apt/lists/*
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
# OpenCode V2 (D-007); the manager always passes a concrete version.
ARG OPENCODE_VERSION
COPY common/install-opencode.sh /tmp/install-opencode.sh
RUN sh /tmp/install-opencode.sh "${OPENCODE_VERSION:?build with --build-arg OPENCODE_VERSION}" \
 && rm /tmp/install-opencode.sh
# Neutral system config; the manager reconciles per-environment Agent Context activation.
COPY common/opencode-system.json /etc/opencode/opencode.json
COPY common/ocs_opencode.py /tmp/ocs_opencode.py
COPY common/ocs-shell-hint.sh /usr/local/lib/ocs-shell-hint.sh
# Set the executable mode inside the image, independent of the build context's mode or ACLs.
RUN install -m 0755 /tmp/ocs_opencode.py /usr/local/bin/ocs-opencode \
 && rm /tmp/ocs_opencode.py \
 && printf '\n. /usr/local/lib/ocs-shell-hint.sh\n' >> /etc/bash.bashrc
WORKDIR /workspace
CMD ["sleep", "infinity"]
