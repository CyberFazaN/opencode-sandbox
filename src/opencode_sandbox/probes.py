"""Finite diagnostics inside containers; never a temporary start of a stopped environment.

The container-side timeout remains effective if the host Docker client is canceled/killed.
Images/custom containers without a compatible timeout tool are unavailable, never probed without
a bound. This is not a timeout/cancellation mechanism for user exec, builds or installations.
"""
from __future__ import annotations

import json
import re
import secrets

from . import core as c

EXEC_TIMEOUT = 5.0
IMAGE_TIMEOUT = 30.0
CLIENT_GRACE = 3.0
CLEANUP_TIMEOUT = 3.0
LABEL = "org.opencode-sandbox.probe"
PREFIX = "ocs-probe-"


def _command(argv, timeout):
    # GNU timeout kills its own command group, including ordinary descendants. --foreground
    # would lose that property. Missing/custom tooling fails; never silently retry unbounded.
    return ("timeout", "--signal=KILL", f"{timeout:g}s", *argv)


def _result(p, timeout):
    if p.returncode in (124, 137):
        raise c.SandboxError(f"Container diagnostic timed out after {timeout:g}s; no version/result verified")
    if p.returncode in (126, 127) and "timeout" in ((p.stderr or "") + (p.stdout or "")):
        raise c.SandboxError("Container diagnostic unavailable: compatible timeout or requested tool is missing")
    return p


def exec(m, *argv, timeout=None):
    timeout = EXEC_TIMEOUT if timeout is None else timeout
    with c.diagnostic_timeout(timeout + CLIENT_GRACE):
        p = c.docker("exec", c.cname(m), *_command(argv, timeout), capture=True, check=False)
    return _result(p, timeout)


def _remove_helper(name, token):
    """After an interrupted run, remove only the full ID bearing this invocation's labels.

    Cleanup gets its own bounded, non-cancelable budget. If the daemon is unavailable we cannot
    claim removal: keep the helper name in the error so normal labelled cleanup can retry later.
    """
    with c.runtime_feedback(progress=None, cancelled=None), c.diagnostic_timeout(CLEANUP_TIMEOUT):
        p = c.docker("container", "inspect", name, capture=True, check=False)
        if p.returncode:
            if re.search(r"no such (container|object)", p.stderr or "", re.IGNORECASE): return
            raise c.SandboxError("helper inspection unavailable")
        try:
            (info,) = json.loads(p.stdout)
            labels = info["Config"]["Labels"]
            image_id = info["Id"]
            if not isinstance(labels, dict): raise TypeError("invalid labels")
            if not re.fullmatch(r"[0-9a-f]{64}", image_id) or labels.get(LABEL) != token \
                    or labels.get(c.DATA_LABEL) != c.data_id() or labels.get(c.HELPER_LABEL) != "diagnostic" \
                    or labels.get("org.opencode-sandbox.managed") != "true":
                raise c.SandboxError("helper ownership mismatch; refusing removal")
        except (ValueError, KeyError, TypeError) as exc:
            raise c.SandboxError("invalid helper ownership inspection") from exc
        c.docker("rm", "-f", image_id, capture=True)


def image(image, *argv, timeout=None):
    timeout = IMAGE_TIMEOUT if timeout is None else timeout
    token = secrets.token_hex(12)
    name = PREFIX + token
    command = _command(argv, timeout)
    try:
        with c.diagnostic_timeout(timeout + CLIENT_GRACE):
            p = c.docker("run", "--rm", "--pull", "never", "--name", name, "--network", "none",
                         "--security-opt", "no-new-privileges:true", *c.helper_labels("diagnostic"),
                         "--label", f"{LABEL}={token}", "--entrypoint", command[0], image,
                         *command[1:], capture=True, check=False)
    except BaseException as exc:  # every interrupted launch must clean its owned helper, then re-raise
        # A client cancellation is not proof Docker stopped/removed the helper. Preserve the
        # original error/cancellation only after owned cleanup, or report its unconfirmed state.
        try:
            _remove_helper(name, token)
        except c.SandboxError as cleanup:
            raise c.SandboxError(f"Image diagnostic interrupted ({c.error_text(exc)}); cleanup not confirmed for {name}: {cleanup}. "
                                 "Retry labelled leftovers with opencode-sandbox disk cleanup --yes") from exc
        raise
    p = _result(p, timeout)
    if p.returncode:
        raise c.SandboxError(f"Image diagnostic failed (exit {p.returncode}); requires timeout and the requested tools")
    return p
