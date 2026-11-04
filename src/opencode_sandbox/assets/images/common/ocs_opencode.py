#!/usr/bin/env python3
"""Shared data-only provider validation and container launcher (also imported by the manager)."""
import json
import os
import re
import sys
from pathlib import Path

RESERVED = frozenset({"OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG", "OPENCODE_CONFIG_DIR"})
PROFILE = "/run/secrets/ocs-provider.json"


class ProfileError(ValueError):
    """Only fixed validation messages/key names, never values or parser input."""


def validate_profile(values):
    if not isinstance(values, dict):
        raise ProfileError("Provider profile must be a JSON object")
    for key, value in values.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) \
                or not isinstance(value, str) or "\0" in value:
            raise ProfileError("Invalid provider environment variable or value")
        if key in RESERVED:
            raise ProfileError(f"{key} is reserved: use native OpenCode config files or OpenCode Configs, not a provider profile")
    return values


def load_profile():
    path = Path(PROFILE)
    # Empty is a bind-mount stub retained by docker commit, not executable content.
    raw = path.read_text() if path.exists() else ""
    return validate_profile(json.loads(raw) if raw.strip() else {})


def main():
    try:
        values = load_profile()
    except ProfileError as exc:
        sys.exit("Invalid provider profile: " + str(exc))
    except (OSError, UnicodeError, ValueError):
        # Never print parser exceptions: JSON errors or values can contain credentials.
        sys.exit("Invalid provider profile; check JSON and reserved configuration variables with the manager")
    os.environ.update(values)
    os.environ["OCS_PROVIDER_LOADED"] = "1"
    args = sys.argv[1:]
    shell = False
    if args[:1] == ["--ocs-managed"]:
        context, system, token, enabled = args[1:]
        try:
            instructions = json.loads(Path(system).read_text()).get("instructions", [])
            if not isinstance(instructions, list) or instructions.count(context) != int(enabled):
                raise ValueError()
        except (OSError, ValueError, AttributeError):
            sys.exit("Agent Context activation differs from saved settings; rerun manager start to reconcile it")
        os.environ["OCS_RUN_TOKEN"] = token
        shell = os.environ.get("OCS_SHELL") == "1"
        args = []
    argv = ["bash"] if shell else ["opencode", "--standalone", *args]
    os.umask(0o022)
    os.execvp(argv[0], argv)


if __name__ == "__main__":
    main()
