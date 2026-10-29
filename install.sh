#!/usr/bin/env bash
# Unprivileged installer for a source checkout on Linux; its package check uses pacman and runs on
# Arch Linux only (D-046). All writes require consent.
set -Eeuo pipefail
SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ACTION=install; DRY=0; OFFER=0; BUILD=0
APP_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/opencode-sandbox-manager"
RELEASES="$APP_HOME/releases"
CURRENT="$APP_HOME/current"
VENV="$CURRENT"
LINK="$HOME/.local/bin/opencode-sandbox"
# Default distribution image; tests/test_distros.py keeps it equal to distros.DEFAULT.
IMAGE="opencode-sandbox:debian"
DOCKER_CONTEXT_NAME="${OPENCODE_SANDBOX_DOCKER_CONTEXT:-rootless}"
IDENTITY="$SOURCE/src/opencode_sandbox/runtime_identity.py"
DOCKER_ENDPOINT=''
# Single version source: the package's __version__ literal.
VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$SOURCE/src/opencode_sandbox/__init__.py")"
[[ -n "$VERSION" ]] || { echo 'ERROR: cannot read the manager version from the source tree' >&2; exit 1; }
usage() { cat <<'HELP'
Usage: ./install.sh [install|update|uninstall|doctor|setup-rootless|verify] [--dry-run] [--offer-packages] [--build-image]
  install        Install isolated Python venv (default)
  update         Install new release and atomically switch the active venv
  uninstall      Remove managed releases and launcher; KEEP projects, config, backups, Docker data
  doctor         Read-only diagnostics (no Docker image downloads)
  verify         Read-only Docker/OpenCode check (does not create a container)
  setup-rootless Guided setup: manual subuid/subgid review, optional user service and smoke test
  --dry-run      Read-only plan; never invokes sudo, pip, or docker build
  --offer-packages  Ask before sudo pacman -S of missing packages available in enabled repos
  --build-image     Ask before Docker image build (downloads and Docker storage writes)
All filesystem writes, even in user home, require explicit confirmation.
Never run this script as root or with sudo.
HELP
}
for arg in "$@"; do case "$arg" in
  install|update|uninstall|doctor|setup-rootless|verify) ACTION="$arg";;
  --dry-run) DRY=1;; --offer-packages) OFFER=1;; --build-image) BUILD=1;;
  -h|--help) usage; exit 0;; *) echo "Unknown argument: $arg" >&2; exit 2;;
esac; done
(( EUID != 0 )) || { echo 'ERROR: refuse root/sudo execution' >&2; exit 1; }
if [[ "$ACTION" == setup-rootless ]]; then
  args=(); (( DRY )) && args+=(--dry-run)
  exec bash "$SOURCE/setup-rootless.sh" "${args[@]}"
fi
[[ -n "${HOME:-}" && -d "$HOME" ]] || { echo 'ERROR: invalid HOME' >&2; exit 1; }
# Without a TTY nothing can be confirmed: fail (non-zero) instead of reporting success.
confirm() { local ans; [[ -t 0 ]] || { echo "ERROR: confirmation needs a TTY: $1" >&2; exit 1; }; read -r -p "$1 [y/N] " ans; [[ "$ans" == y || "$ans" == Y || "$ans" == yes || "$ans" == YES ]]; }
# Fail closed on symlink redirection at target and parent paths.
check_path() {
  local path="$1" p
  [[ "$path" == /* ]] || { echo "ERROR: not an absolute path: $path" >&2; exit 1; }
  p="$path"
  while [[ "$p" != / ]]; do
    if [[ -L "$p" ]]; then echo "ERROR: symlink in managed path: $p" >&2; exit 1; fi
    p="$(dirname -- "$p")"
  done
}
# Daemon identity check shared with the manager (D-003). Sets DOCKER_ENDPOINT only for the
# current user's own verified rootless daemon; prints the report unless "quiet".
verify_daemon() {
  local out rc=0
  command -v python >/dev/null 2>&1 || { [[ "${1:-}" == quiet ]] || echo 'Daemon identity: not checked (python missing)'; return 1; }
  out="$(python -I -B "$IDENTITY" --context "$DOCKER_CONTEXT_NAME" </dev/null 2>&1)" || rc=$?
  [[ "${1:-}" == quiet ]] || printf '%s\n' "$out"
  (( rc == 0 )) && grep -qx 'Daemon identity: verified' <<<"$out" || return 1
  DOCKER_ENDPOINT="$(sed -n 's/^Endpoint: //p' <<<"$out")"
  [[ "$DOCKER_ENDPOINT" == unix://* ]]
}
check_path "$APP_HOME"
if [[ -e "$LINK" || -L "$LINK" ]]; then
  if ! [[ -L "$LINK" && "$(readlink -- "$LINK")" == "$VENV/bin/opencode-sandbox" ]]; then
    echo "ERROR: launcher belongs to another application: $LINK" >&2
    # The documented installation (pipx from GitHub) uses the same command name.
    if [[ "$(readlink -- "$LINK" 2>/dev/null)" == */venvs/opencode-sandbox/bin/opencode-sandbox ]]; then
      echo "It is a pipx installation of OpenCode Sandbox: keep using it, or remove it first with 'pipx uninstall opencode-sandbox'." >&2
    fi
    exit 1
  fi
fi
printf 'OpenCode Sandbox %s\nAction: %s\nSource: %s\nApp venv: %s\nLauncher: %s\n' "$VERSION" "$ACTION" "$SOURCE" "$VENV" "$LINK"
if [[ "$ACTION" == uninstall ]]; then
  echo "Will remove only managed releases and launcher; preserve projects, backups, configuration and Docker objects."
  (( DRY )) && exit 0
  confirm "Uninstall managed application?" || exit 0
  [[ -L "$LINK" ]] && rm -- "$LINK"
  if [[ -L "$CURRENT" ]]; then rm -- "$CURRENT"; fi
  if [[ -d "$RELEASES" ]]; then rm -rf -- "$RELEASES"; fi
  echo 'Uninstalled application only.'
  exit 0
fi
arch=0
if [[ -r /etc/os-release ]]; then
  # os-release is OS-controlled, not project-controlled.
  # shellcheck source=/dev/null
  . /etc/os-release
  [[ "${ID:-}" == arch ]] && arch=1
fi
(( arch )) || echo 'WARNING: not Arch Linux; pacman integration disabled.'
missing=()
for cmd in python git docker; do command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd"); done
if command -v python >/dev/null 2>&1; then
  python - <<'PY' || missing+=("python>=3.14 + venv/ensurepip")
import sys, venv, ensurepip
assert sys.version_info >= (3,14)
PY
fi
if ((${#missing[@]})); then printf 'Missing tools: %s\n' "${missing[*]}"; fi
# The release venv uses the system Python; after a Python minor upgrade it no longer starts.
if [[ -L "$CURRENT" ]] && ! "$CURRENT/bin/python" -I -c 'import opencode_sandbox' >/dev/null 2>&1; then
  echo "Installed release $(readlink -- "$CURRENT") does not start (its venv was built for another Python; after a Python minor upgrade): run ./install.sh update"
fi
verified=0
if command -v docker >/dev/null 2>&1; then
  echo "Docker daemon identity (context $DOCKER_CONTEXT_NAME):"
  if verify_daemon; then verified=1; else echo 'See docs/install.md. No service/context changes are made.'; fi
else
  echo 'Docker CLI unavailable; see docs/install.md'
fi
if (( arch )); then
  pkgs=()
  for pkg in python git docker docker-rootless-extras slirp4netns fuse-overlayfs; do
    if ! pacman -Qq "$pkg" >/dev/null 2>&1; then
      # The rootless setup tool may come from upstream scripts in ~/.local/bin instead.
      if [[ "$pkg" == docker-rootless-extras ]] && (( verified )); then
        echo 'Optional package not installed: docker-rootless-extras (a verified rootless daemon is running)'
      else
        pkgs+=("$pkg")
      fi
    fi
  done
  if ((${#pkgs[@]})); then
    echo "Not installed (verify repo availability): ${pkgs[*]}"
    if (( OFFER )) && [[ "$ACTION" != doctor ]] && (( ! DRY )); then
      available=()
      for pkg in "${pkgs[@]}"; do
        if pacman -Si "$pkg" >/dev/null 2>&1; then available+=("$pkg"); else echo "Not in enabled repos: $pkg"; fi
      done
      if ((${#available[@]})) && confirm "Run sudo pacman -S -- ${available[*]}?"; then sudo pacman -S -- "${available[@]}"; fi
    fi
  fi
fi
if (( verified )); then
  if docker -H "$DOCKER_ENDPOINT" image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Agent image $IMAGE: present"
  else
    echo "Agent image $IMAGE: missing"
  fi
fi
if [[ "$ACTION" == verify ]]; then
  if (( DRY )); then echo "[DRY RUN] Would inspect rootless engine and installed image"; exit 0; fi
  command -v docker >/dev/null 2>&1 || { echo "Docker CLI missing" >&2; exit 1; }
  (( verified )) || { echo "Docker daemon identity not verified (context $DOCKER_CONTEXT_NAME)" >&2; exit 1; }
  docker -H "$DOCKER_ENDPOINT" image inspect "$IMAGE" >/dev/null || { echo "Base image $IMAGE missing" >&2; exit 1; }
  echo "Verified rootless engine and base image available. OpenCode execution NOT verified."
  exit 0
fi
if [[ "$ACTION" == doctor || "$DRY" == 1 ]]; then
  echo 'Read-only run: no installation or configuration changes performed.'
  [[ "$ACTION" == doctor ]] || echo 'Plan: create/update isolated venv, optionally link launcher, optionally build image; each step requires confirmation.'
  exit 0
fi
if [[ "$ACTION" == update && ! -x "$CURRENT/bin/python" ]]; then echo 'ERROR: no managed release; run install first' >&2; exit 1; fi
command -v python >/dev/null 2>&1 || { echo 'ERROR: Python missing' >&2; exit 1; }
python - <<'PYTHON_CHECK'
import sys, venv, ensurepip
assert sys.version_info >= (3,14), 'Python 3.14+ required'
PYTHON_CHECK
confirm "${ACTION^} application into a new isolated release?" || exit 0
check_path "$RELEASES"
mkdir -p -- "$RELEASES"
NEW="$RELEASES/release-$(date -u +%Y%m%dT%H%M%SZ)-$$"
[[ ! -e "$NEW" ]] || { echo "Release collision" >&2; exit 1; }
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/ocs-install.XXXXXX")"
cleanup() { if [[ -n "${NEW:-}" && -d "$NEW" ]]; then rm -rf -- "$NEW"; fi; rm -rf -- "$STAGE"; }
trap cleanup EXIT
# Build from a private copy: setuptools writes build/ and *.egg-info next to the
# sources, which modified the user's checkout and failed on read-only sources.
cp -R -- "$SOURCE/pyproject.toml" "$SOURCE/src" "$STAGE/"
chmod -R u+w -- "$STAGE"
python -m venv "$NEW"
"$NEW/bin/python" -m pip install -- "$STAGE"
"$NEW/bin/opencode-sandbox" --help >/dev/null
RELEASE="$NEW"
NEW=''
TMP_LINK="$APP_HOME/.current.$$"
ln -s -- "$RELEASE" "$TMP_LINK"
# Atomic publication; existing release remains intact if installation fails.
mv -Tf -- "$TMP_LINK" "$CURRENT"
if [[ ! -L "$LINK" ]]; then
  if confirm "Create launcher $LINK (outside application directory)?"; then
    check_path "$(dirname "$LINK")"
    mkdir -p -- "$(dirname "$LINK")"
    ln -s -- "$VENV/bin/opencode-sandbox" "$LINK"
  fi
fi
if (( BUILD )); then
  if command -v docker >/dev/null 2>&1 && verify_daemon quiet; then
    if confirm 'Build agent Docker image (network downloads and Docker storage writes)?'; then "$CURRENT/bin/opencode-sandbox" build; fi
  else
    echo 'WARNING: cannot build until the rootless Docker daemon identity is verified (run ./install.sh doctor).'
  fi
fi
echo "Release active: $CURRENT. Check: $CURRENT/bin/opencode-sandbox doctor"
