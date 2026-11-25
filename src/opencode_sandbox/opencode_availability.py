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
# confused with a missing executable. Drain stdout but retain only a bounded tail
# (the version is on the last line). The outer probe timeout covers the whole pipeline.
_PROBE = """
if ! command -v opencode >/dev/null 2>&1; then
    printf '%s\\n' 'Missing'
else
    printf '%s\\n' 'Found'
    {
        opencode --version 2>/dev/null
        printf '\\nocs-exit:%s\\n' "$?"
    } | tail -c 4096
fi
"""


def observe(m, *, container_id=None):
    """Return status and internal version evidence from one bounded command."""
    try:
        if container_id is None:
            state = c.inspect_container(m)
            if not state or not state.get("Running"):
                return Status.UNKNOWN, None
        p = probes.exec(m, "sh", "-c", _PROBE, container_id=container_id)
    except (c.SandboxError, UnicodeError):
        return Status.UNKNOWN, None
    if p.returncode != 0:
        return Status.UNKNOWN, None
    marker, _, output = (p.stdout or "").partition("\n")
    if marker == "Missing" and not output:
        return Status.MISSING, None
    version, sep, code = output.rstrip("\n").rpartition("\nocs-exit:")
    if marker == "Found" and sep and code.isascii() and code.isdecimal() and len(code) <= 3 and int(code) <= 255:
        return (Status.AVAILABLE, version.strip()) if code == "0" else (Status.BROKEN, None)
    return Status.UNKNOWN, None


def check(m):
    """Inspect an owned running container without starting it or exposing output."""
    return observe(m)[0]
