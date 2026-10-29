# Build context: assets/images/ (shared files in common/). Labels come from the registry
# (distros.py) at build time.
FROM archlinux:base-devel AS base
ENV LANG=C.UTF-8
# One synchronized package set for every stage: paru links the libalpm of this pacman.
# Global npm packages go to /usr/local, away from pacman-owned /usr/lib/node_modules.
# Downloads are retried: mirror transfers stalled repeatedly during image builds;
# completed files stay in the cache between attempts.
COPY arch/pacman-retry /usr/local/lib/ocs-build/pacman-retry
RUN sh /usr/local/lib/ocs-build/pacman-retry -Syu --noconfirm --needed git git-lfs openssh python python-pip \
  cmake jq ripgrep fd unzip zip less nano vim rsync curl wget bind nodejs npm \
 && rm -rf /var/cache/pacman/pkg/* /usr/local/lib/ocs-build \
 && useradd --system --create-home --home-dir /var/lib/aurbuild --shell /usr/bin/nologin aurbuild \
 && printf '%s\n' '# OpenCode Sandbox: no separate debug packages for AUR builds.' 'OPTIONS+=(!debug)' \
    > /etc/makepkg.conf.d/ocs.conf
ENV NPM_CONFIG_PREFIX=/usr/local

# AUR helper (D-006), built as the unprivileged user; the Rust toolchain stays in this stage.
FROM base AS paru
ARG PARU_AUR_COMMIT=329be2113c590046cb29858c23d9b96a8d7bd586
COPY arch/pacman-retry /tmp/pacman-retry
RUN sh /tmp/pacman-retry -S --noconfirm --needed rust
USER aurbuild
WORKDIR /var/lib/aurbuild
RUN git clone --quiet https://aur.archlinux.org/paru.git \
 && git -C paru checkout --quiet "$PARU_AUR_COMMIT" \
 && cd paru && makepkg --noconfirm

FROM base
RUN --mount=type=bind,from=paru,source=/var/lib/aurbuild/paru,target=/tmp/paru \
    pacman -U --noconfirm /tmp/paru/paru-*.pkg.tar.zst && rm -rf /var/cache/pacman/pkg/*
# makepkg refuses root and no-new-privileges blocks sudo: ocs-aur (run as root) runs paru as
# aurbuild and performs its pacman calls as root.
COPY --chmod=0755 arch/ocs-aur /usr/local/bin/ocs-aur
RUN mkdir -p /usr/local/lib/ocs-aur && ln -s /usr/local/bin/ocs-aur /usr/local/lib/ocs-aur/sudo
# OpenCode V2 (D-007); the manager always passes a concrete version.
ARG OPENCODE_VERSION
COPY common/install-opencode.sh /tmp/install-opencode.sh
RUN sh /tmp/install-opencode.sh "${OPENCODE_VERSION:?build with --build-arg OPENCODE_VERSION}" \
 && rm /tmp/install-opencode.sh
# Manager-owned system config: only lists the Agent Context file (D-008).
COPY common/opencode-system.json /etc/opencode/opencode.json
WORKDIR /workspace
CMD ["sleep", "infinity"]
