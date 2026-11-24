"""Check the live executable independently of its installer or version policy."""
from enum import Enum

from . import core as c
from . import probes


class Status(str, Enum):
    AVAILABLE = "Available"
    MISSING = "Missing"
    BROKEN = "Broken"
    UNKNOWN = "Unknown"


# Use a marker from the probe itself so a Docker transport/exec failure cannot be
# confused with a missing executable. Do not expose executable output to callers.
_PROBE = """
if ! command -v opencode >/dev/null 2>&1; then
    printf '%s\\n' 'Missing'
else
    printf '%s\\n' 'Found'
    if timeout --signal=KILL 3s opencode --version >/dev/null 2>&1; then
        printf '%s\\n' 'Available'
    else
        printf '%s\\n' 'Broken'
    fi
fi
"""


def check(m):
    """Inspect an owned running container. A stopped container stays stopped."""
    try:
        state = c.inspect_container(m)
        if not state or not state.get("Running"):
            return Status.UNKNOWN
        p = probes.exec(m, "sh", "-c", _PROBE)
    except c.SandboxError:
        return Status.UNKNOWN
    output = (getattr(p, "stdout", None) or "").strip()
    if p.returncode == 0:
        if output == "Found\nAvailable":
            return Status.AVAILABLE
        if output == "Missing":
            return Status.MISSING
        if output == "Found\nBroken":
            return Status.BROKEN
    return Status.UNKNOWN
