"""CI only: build and verify a distribution's base image with the manager's own build and image
verification (`core.build_image`), on a hosted runner.

    python .github/scripts/build_image.py DISTRO [ENDPOINT]

A hosted runner's Docker daemon is rootful, which the manager refuses by design (D-003). This
script points the manager's Docker calls at the given endpoint (default: the runner's
unix:///var/run/docker.sock) without the identity check. It is for disposable CI runners only;
never use it on your own machine. The image is tagged `ocs-ci-<distro>:latest`."""
import sys

from opencode_sandbox import core as c
from opencode_sandbox import distros
from opencode_sandbox import opencode_versions as v

if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    distro = distros.get(sys.argv[1])
    endpoint = sys.argv[2] if len(sys.argv) == 3 else "unix:///var/run/docker.sock"
    c.docker_endpoint = lambda: endpoint
    version = v.supported(v.latest())
    tag = f"ocs-ci-{distro.id}:latest"
    c.build_image(distro, version, tag)
    print(f"{tag}: {distro.name} {distro.version}, OpenCode {version}, built and verified")
