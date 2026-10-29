"""Non-secret dashboard preferences, atomically persisted."""
import json
import os
import tempfile

from . import core as c

DEFAULTS = {"confirm_stop": True, "show_quick": True, "refresh_on_return": True}

def read():
    path = c.CONFIG / "ui.json"
    if not path.exists():
        return dict(DEFAULTS)
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise c.SandboxError("Invalid UI settings")
    return {k: raw.get(k) if type(raw.get(k)) is bool else v for k, v in DEFAULTS.items()}

def write(settings):
    c.init_dirs()
    if set(settings) != set(DEFAULTS) or any(type(v) is not bool for v in settings.values()):
        raise c.SandboxError("Invalid UI settings")
    fd, tmp = tempfile.mkstemp(prefix=".ui-", dir=c.CONFIG)
    try:
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(settings, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, c.CONFIG / "ui.json")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
