#!/usr/bin/env bash
# Check a pipx installation of OpenCode Sandbox without a source tree (CI and RELEASING.md).
#   pipx_smoke.sh LAUNCHER PIPX_HOME [EXPECTED_VERSION]
# EXPECTED_VERSION defaults to __version__ of this checkout. With OCS_CI_ROOTFUL_CONTEXT set to the
# name of a Docker context of a rootful daemon, doctor must refuse it with exit status 4.
set -euo pipefail
launcher=$1 pipx_home=$2
here="$(cd "$(dirname "$0")/../.." && pwd)"
expected=${3:-$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$here/src/opencode_sandbox/__init__.py")}
fail() { echo "FAIL: $*" >&2; exit 1; }
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
export OPENCODE_SANDBOX_HOME="$work/data" OPENCODE_SANDBOX_CONFIG="$work/config"
unset PYTHONPATH

out="$("$launcher" --version)"
[[ "$out" == "opencode-sandbox $expected" ]] || fail "--version: '$out', expected 'opencode-sandbox $expected'"
"$launcher" --help >/dev/null || fail "--help"

python="$pipx_home/venvs/opencode-sandbox/bin/python"
"$python" -I - "$pipx_home" <<'PY' || fail "installed package"
import sys
from pathlib import Path
import opencode_sandbox, opencode_sandbox.distros as d
module = Path(opencode_sandbox.__file__).resolve()
assert str(module).startswith(str(Path(sys.argv[1]).resolve())), f"runs {module}, not the pipx installation"
assets = sorted(p.relative_to(d.IMAGES).as_posix() for p in d.IMAGES.rglob("*") if p.is_file())
for distro in d.REGISTRY.values():
    assert distro.dockerfile.is_file(), distro.dockerfile
assert any(a.startswith("common/") for a in assets), assets
print("installed package:", module.parent, "assets:", len(assets))
PY

set +e
OPENCODE_SANDBOX_DOCKER_CONTEXT=ocs-ci-no-such-context "$launcher" doctor >"$work/doctor.txt" 2>&1
code=$?
set -e
[[ $code == 8 ]] || { cat "$work/doctor.txt"; fail "doctor with a missing context: exit $code, expected 8"; }
grep -q 'Daemon identity: not-configured' "$work/doctor.txt" || fail "doctor did not report not-configured"

if [[ -n "${OCS_CI_ROOTFUL_CONTEXT:-}" ]]; then
  set +e
  OPENCODE_SANDBOX_DOCKER_CONTEXT=$OCS_CI_ROOTFUL_CONTEXT "$launcher" doctor >"$work/doctor.txt" 2>&1
  code=$?
  set -e
  cat "$work/doctor.txt"
  [[ $code == 4 ]] || fail "doctor with the rootful daemon: exit $code, expected 4 (mismatch)"
fi
echo "pipx installation OK: opencode-sandbox $expected"
