# Build context: assets/images/ (shared files in common/). Labels come from the registry
# (distros.py) at build time.
FROM node:24-trixie
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
 bash ca-certificates curl wget git git-lfs openssh-client python3 python3-pip python3-venv \
 build-essential cmake pkg-config jq ripgrep fd-find unzip zip tar less procps iproute2 \
 iputils-ping dnsutils sudo nano vim-tiny rsync patch file && rm -rf /var/lib/apt/lists/*
# OpenCode V2 (D-007); the manager always passes a concrete version.
ARG OPENCODE_VERSION
COPY common/install-opencode.sh /tmp/install-opencode.sh
RUN sh /tmp/install-opencode.sh "${OPENCODE_VERSION:?build with --build-arg OPENCODE_VERSION}" \
 && rm /tmp/install-opencode.sh
# Manager-owned system config: only lists the Agent Context file (D-008). OpenCode combines
# `instructions` from all config documents; user config in /root/.config/opencode stays untouched.
COPY common/opencode-system.json /etc/opencode/opencode.json
WORKDIR /workspace
CMD ["sleep", "infinity"]
