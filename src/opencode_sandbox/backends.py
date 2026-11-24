"""Operation-local Docker selection and persisted runtime identity."""
import os
import pwd
import re
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

ROOTLESS = "rootless"
ROOTFUL = "rootful"
NAMES = (ROOTLESS, ROOTFUL)
WARNING = ("Rootful Docker runs with host root authority. Inside the container the session user "
           "can become root with passwordless sudo and can change ownership or permissions in a writable workspace. "
           "Files it creates there may grant elevated privileges if executed on the host. Use rootless for untrusted work.")
_active = ContextVar("docker_backend", default=None)
endpoint = ContextVar("rootful_endpoint", default=None)


def selected():
    return _active.get() or ROOTLESS


def get(m):
    return m.get("backend", ROOTLESS)


def allowed():
    from . import preferences
    return preferences.read()["allow_rootful"]


@contextmanager
def use(name):
    from .core import SandboxError

    if name not in NAMES:
        raise SandboxError("Docker backend must be rootless or rootful")
    current = _active.get()
    if current is not None and current != name:
        raise SandboxError("Conflicting Docker backend in the same operation")
    if current == name:
        yield
        return
    if name == ROOTFUL and not allowed():
        raise SandboxError("Rootful Docker is disabled. Enable Allow rootful Docker environments in Settings.")
    token = _active.set(name)
    socket = endpoint.set(None)
    try:
        yield
    finally:
        endpoint.reset(socket)
        _active.reset(token)


def environment(function):
    @wraps(function)
    def routed(m, *args, **kwargs):
        from .core import SandboxError

        with use(get(m)):
            if get(m) == ROOTFUL and m.get("identity") != host_identity():
                raise SandboxError("Rootful environment requires its original host username, UID and primary GID")
            return function(m, *args, **kwargs)
    return routed


def host_identity():
    from .core import SandboxError

    uid, gid = os.getuid(), os.getgid()
    try:
        identity = {"name": pwd.getpwuid(uid).pw_name, "uid": uid, "gid": gid}
    except KeyError:
        raise SandboxError("Cannot find the host account for the current UID") from None
    if not valid_identity(identity):
        raise SandboxError("Rootful environments require a non-root host account with a supported username and primary GID")
    return identity


def valid_identity(value):
    return (isinstance(value, dict) and set(value) == {"name", "uid", "gid"}
            and isinstance(value["name"], str) and re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_.-]{0,31}", value["name"])
            and value["name"] != "root"
            and all(type(value[key]) is int and 0 < value[key] < 2**32 - 1 for key in ("uid", "gid")))


def home(m):
    return "/home/ocs" if get(m) == ROOTFUL else "/root"


def user(m):
    identity = m["identity"]
    return f"{identity['uid']}:{identity['gid']}"


def describe(m):
    if get(m) == ROOTLESS:
        return "rootless · " + ("container UID 0" if m.get("distro") else "image user")
    identity = m["identity"]
    return f"rootful · {identity['name']} ({user(m)})"


def cli_flag():
    return "--docker-backend rootful " if selected() == ROOTFUL else ""
