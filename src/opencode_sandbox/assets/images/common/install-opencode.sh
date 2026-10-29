#!/bin/sh
# Install OpenCode V2 (npm package @opencode/cli) system-wide. Shared by every image build
# (RUN) and by in-container updates (`sh -c <this file> ocs-install-opencode VERSION`).
set -eu
version="${1:?usage: install-opencode.sh VERSION}"
# docker exec inherits rootless dockerd's umask (0000): without 022 the tree is world-writable.
umask 022
# npm's cache (~465 MB), its logs and the state OpenCode writes when it first runs must not
# land in /root or /tmp: Docker copies the image's /root into every new home volume, and in a
# running container /root is the user's home volume. A private HOME also keeps a
# user's ~/.npmrc from redirecting this system-wide install.
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
unset XDG_CONFIG_HOME XDG_DATA_HOME XDG_STATE_HOME XDG_CACHE_HOME
export HOME="$scratch/home" TMPDIR="$scratch"
mkdir "$HOME"
# The package's postinstall hard-links (or copies) the native binary for this CPU and libc to
# bin/opencode.exe; npm blocks install scripts that are not allowed explicitly.
npm install -g --no-audit --no-fund --fetch-timeout=60000 --fetch-retries=1 \
  --allow-scripts=@opencode/cli "@opencode/cli@$version"
root="$(npm root -g)/@opencode/cli"
binary="$root/bin/opencode.exe"
[ -f "$binary" ] && [ ! -L "$binary" ] || { echo "install-opencode: $binary missing" >&2; exit 1; }
# The platform packages (glibc/musl x AVX2/baseline, about 230 MB each) only hold the binary
# that postinstall already placed in bin/.
rm -rf "$root"/node_modules/@opencode/cli-*
opencode --version
