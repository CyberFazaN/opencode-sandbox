"""Optional dashboard metadata discovery and quiet cached comparisons, never runtime probes.

Only npm is implemented. A later GitHub source must supply its own discovery/attempt contract;
there is no speculative manager request, generic executor or component mutation here.
"""
from . import core as c
from . import opencode_versions as v


def check():
    error = None
    try: v.latest(automatic=True)
    except c.SandboxError as exc: error = c.error_text(exc)
    return {**v.discovery(), "scheduling_error": error}


def available():
    """Count notify-policy environments against dated history, without Docker or metadata edits.

    Unknown history cannot prove availability. Manual/Pinned and pending recovery are excluded;
    explicit Updates comparisons remain independent of this optional indicator.
    """
    remote = v.discovery()
    success = remote["success"]
    if not success: return 0
    count = 0
    for m in c.all_envs():
        try:
            if m.get("operation") or m.get("opencode_policy", "notify") != "notify": continue
            history = v.environment_history(m)
            if history["version"] and v.compare(history["version"], success["value"]) < 0: count += 1
        except c.SandboxError:
            continue
    return count
