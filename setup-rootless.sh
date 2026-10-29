#!/usr/bin/env bash
# Guided, opt-in rootless Docker preparation (written for Arch Linux, the tested host; D-046).
set -Eeuo pipefail
(( EUID != 0 )) || { echo 'ERROR: run as an ordinary user, never sudo' >&2; exit 1; }
DRY=0
[[ "${1:-}" == '--dry-run' ]] && DRY=1
[[ $# -le 1 ]] || { echo 'Usage: setup-rootless.sh [--dry-run]' >&2; exit 2; }
confirm() {
  local reply
  [[ -t 0 ]] || { echo 'Interactive terminal required for changes; skipping.'; return 1; }
  read -r -p "$1 [y/N] " reply
  [[ "$reply" == y || "$reply" == Y || "$reply" == yes || "$reply" == YES ]]
}
section() { printf '\n=== %s ===\n' "$1"; }
SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
DOCKER_CONTEXT_NAME="${OPENCODE_SANDBOX_DOCKER_CONTEXT:-rootless}"
DOCKER_ENDPOINT=''
# Same daemon identity check as the manager (D-003); sets DOCKER_ENDPOINT when verified.
verify_daemon() {
  local out rc=0 py
  DOCKER_ENDPOINT=''
  command -v docker >/dev/null 2>&1 || return 1
  py="$(command -v python3 || command -v python)" || { [[ "${1:-}" == quiet ]] || echo 'Daemon identity: not checked (python missing)'; return 1; }
  out="$("$py" -I -B "$SOURCE/src/opencode_sandbox/runtime_identity.py" --context "$DOCKER_CONTEXT_NAME" </dev/null 2>&1)" || rc=$?
  [[ "${1:-}" == quiet ]] || printf '%s\n' "$out"
  (( rc == 0 )) && grep -qx 'Daemon identity: verified' <<<"$out" || return 1
  DOCKER_ENDPOINT="$(sed -n 's/^Endpoint: //p' <<<"$out")"
  [[ "$DOCKER_ENDPOINT" == unix://* ]]
}
section 'Rootless Docker guided setup (no silent changes)'
echo 'Read-only checks are performed first. No firewall, /etc/subuid, /etc/subgid or daemon.json edits.'
# shellcheck source=/dev/null
[[ -r /etc/os-release ]] && { . /etc/os-release; [[ "${ID:-}" == arch ]] || echo 'WARNING: Not Arch Linux; package suggestions may differ.'; }
for cmd in docker dockerd-rootless-setuptool.sh rootlesskit newuidmap newgidmap systemctl; do
  if command -v "$cmd" >/dev/null 2>&1; then printf '[OK] %s\n' "$cmd"
  # Docker's upstream rootless installer puts its tools in ~/.local/bin.
  elif [[ -x "$HOME/.local/bin/$cmd" ]]; then printf '[OK] %s (in ~/.local/bin, which is not on PATH)\n' "$cmd"
  else printf '[MISSING] %s\n' "$cmd"; fi
done
section 'Subordinate ID ranges — manual only'
username="$(id -un)"; uid="$(id -u)"
for f in /etc/subuid /etc/subgid; do
  echo "$f:"
  if [[ -r "$f" ]]; then
    awk -F: -v user="$username" -v uid="$uid" '$1==user || $1==uid { found=1; if ($2 ~ /^[0-9]+$/ && $3 ~ /^[0-9]+$/) printf "  entry: start=%s count=%s%s\n",$2,$3,($3+0>=65536?" (>=65536)":" (too small)"); else print "  invalid entry"; found=1 } END {if (!found) print "  no matching entry"}' "$f"
  else echo '  cannot read; inspect manually with administrator privileges'; fi
done
cat <<'HELP'
If a range is missing, overlaps another allocation, or has fewer than 65536 IDs,
STOP and review /etc/subuid and /etc/subgid manually. Do not blindly append a
range. Consult: https://docs.docker.com/engine/security/rootless/
Return and re-run this wizard after manual changes.
HELP
section 'Rootless service and context'
if verify_daemon; then
  echo "[OK] context $DOCKER_CONTEXT_NAME reaches your own rootless daemon."
else
  echo "[NOT READY] context $DOCKER_CONTEXT_NAME does not reach a verified rootless daemon of this user."
  cat <<'HELP'
Recommended manual bootstrap (review the installed tool before executing):
  dockerd-rootless-setuptool.sh install
It may create a user systemd service and Docker context. Review its output.
Never run this tool with sudo. If the command is unavailable, install Docker's
rootless extras first (on Arch Linux: the AUR package docker-rootless-extras).
HELP
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user is-enabled docker.service 2>/dev/null || true
  systemctl --user is-active docker.service 2>/dev/null || true
  if (( DRY )); then
    echo '[DRY RUN] Would offer systemctl --user enable --now docker.service (only if service exists).'
  elif systemctl --user cat docker.service >/dev/null 2>&1; then
    if confirm 'Enable and start the USER docker.service? (changes user systemd state)'; then
      systemctl --user enable --now docker.service
    fi
  else
    echo 'User docker.service not installed; complete manual bootstrap first.'
  fi
fi
section 'Optional user lingering'
echo 'Lingering starts user services without an active login session and changes host login behavior.'
echo 'Not enabled automatically. If needed, review: loginctl enable-linger "'"$username"'" (may require administrator authorization).'
section 'Optional smoke test'
if (( DRY )); then
  echo '[DRY RUN] Would offer docker run --rm hello-world on the verified daemon (may download image).'
elif verify_daemon quiet; then
  if confirm 'Run rootless hello-world container? (may download an image and write Docker storage)'; then
    docker -H "$DOCKER_ENDPOINT" run --rm hello-world
  fi
fi
section 'Final check'
if verify_daemon quiet; then
  echo 'Rootless engine: READY (daemon identity verified). Next: ./install.sh install --build-image'
else
  echo 'Rootless engine: NOT READY. Complete manual steps, then re-run ./install.sh setup-rootless.'
fi
