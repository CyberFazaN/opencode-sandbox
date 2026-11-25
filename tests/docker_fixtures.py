"""Image inspection payloads for fake Docker transports."""
import json
from types import SimpleNamespace

from opencode_sandbox import distros


def managed_image_json(distro=distros.DEFAULT, *, image_id="sha256:" + "a" * 64):
    labels = {**distros.get(distro).image_labels(), distros.LABEL + "managed": "true"}
    return json.dumps([{"Id": image_id, "Config": {"Labels": labels}}])


def start_transport(calls, distro=distros.DEFAULT):
    """Record calls to a fake runtime with a managed base ready for first start."""
    def docker(*args, **kwargs):
        calls.append(args)
        reply = managed_image_json(distro) if args == ("image", "inspect", distros.get(distro).image) else ""
        return SimpleNamespace(returncode=0, stdout=reply, stderr="")
    return docker
