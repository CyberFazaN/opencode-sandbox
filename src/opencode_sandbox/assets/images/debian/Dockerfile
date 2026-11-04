# Build context: assets/images/ (shared files in common/). Labels come from the registry
# (distros.py) at build time.
FROM node:24-trixie
ENV DEBIAN_FRONTEND=noninteractive
# Every build upgrades installed packages: the manager passes a per-build nonce, so this layer
# runs with fresh indexes even when earlier layers are cached.
ARG SYSTEM_PACKAGE_REFRESH
RUN test -n "${SYSTEM_PACKAGE_REFRESH:?build with --build-arg SYSTEM_PACKAGE_REFRESH}" && apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends \
 bash ca-certificates curl wget git git-lfs openssh-client python3 python3-pip python3-venv \
 build-essential cmake pkg-config jq ripgrep fd-find unzip zip tar less procps iproute2 \
 iputils-ping dnsutils sudo nano vim-tiny rsync patch file && rm -rf /var/lib/apt/lists/*
# OpenCode V2 (D-007); the manager always passes a concrete version.
ARG OPENCODE_VERSION
COPY common/install-opencode.sh /tmp/install-opencode.sh
RUN sh /tmp/install-opencode.sh "${OPENCODE_VERSION:?build with --build-arg OPENCODE_VERSION}" \
 && rm /tmp/install-opencode.sh
# Neutral system config; the manager reconciles per-environment Agent Context activation.
COPY common/opencode-system.json /etc/opencode/opencode.json
COPY --chmod=0755 common/ocs_opencode.py /usr/local/bin/ocs-opencode
COPY common/ocs-shell-hint.sh /usr/local/lib/ocs-shell-hint.sh
RUN printf '\n. /usr/local/lib/ocs-shell-hint.sh\n' >> /etc/bash.bashrc
WORKDIR /workspace
CMD ["sleep", "infinity"]
