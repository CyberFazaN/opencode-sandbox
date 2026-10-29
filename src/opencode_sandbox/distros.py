"""Declarative registry of the managed sandbox distributions (D-005).

Everything that differs between distributions lives here or in the image assets under
`assets/images/<id>/`; the rest of the manager reads these records instead of branching on
a distribution name (a test enforces this).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IMAGES = Path(__file__).resolve().parent / "assets" / "images"
REPOSITORY = "opencode-sandbox"
LABEL = "org.opencode-sandbox."


@dataclass(frozen=True)
class Distro:
    id: str
    name: str
    version: str
    # Manager-owned; bump when this distribution's image definition changes.
    revision: int
    # /etc/os-release entries every build must report. A rolling release has no fixed
    # VERSION_ID (Arch's is the date of the upstream image), so it pins BUILD_ID instead.
    os_release: tuple[tuple[str, str], ...]
    package_manager: str
    install_hint: str
    # Executables the Agent Context promises; each build checks that they are on PATH.
    tools: tuple[str, ...]
    # Commands each build must run successfully (catches, e.g., a helper linked to another libalpm).
    smoke: tuple[str, ...] = ()
    # Extra Agent Context lines for this distribution.
    notes: tuple[str, ...] = ()
    aur_helper: str | None = None

    @property
    def image(self) -> str:
        return f"{REPOSITORY}:{self.id}"

    @property
    def dockerfile(self) -> Path:
        return IMAGES / self.id / "Dockerfile"

    def context_lines(self) -> list[str]:
        """Agent Context lines for an environment that uses this distribution's managed image; only
        what the registry pins and every build verifies (os-release entries, tools)."""
        return [f"- Base OS: {self.name} {self.version}. Use {self.package_manager}, not the host's package manager.",
                f"- Installing system packages: {self.install_hint}",
                *self.notes,
                "- The managed base image includes: " + ", ".join(self.tools) + "."]

    def image_labels(self) -> dict[str, str]:
        return {LABEL + "distro": self.id, LABEL + "distro-version": self.version,
                LABEL + "image-revision": str(self.revision)}


REGISTRY: dict[str, Distro] = {d.id: d for d in (
    Distro(id="debian", name="Debian", version="12", revision=1, package_manager="apt",
           os_release=(("ID", "debian"), ("VERSION_ID", "12")),
           install_hint="`apt-get update && apt-get install -y PACKAGE` as root (needs network).",
           tools=("bash", "git", "git-lfs", "python3", "pip3", "node", "npm", "opencode", "rg", "jq", "curl",
                  "gcc", "cmake")),
    Distro(id="arch", name="Arch Linux", version="rolling", revision=1, package_manager="pacman",
           os_release=(("ID", "arch"), ("BUILD_ID", "rolling")),
           install_hint="`pacman -Syu --needed PACKAGE` as root (needs network; Arch does not support partial "
                        "upgrades, so this also upgrades the container's other packages).",
           tools=("bash", "git", "git-lfs", "python3", "pip3", "node", "npm", "opencode", "rg", "jq", "curl",
                  "gcc", "cmake", "makepkg", "paru", "ocs-aur"),
           smoke=("paru --version", "ocs-aur --version"),
           notes=(("- AUR packages: `ocs-aur -S PACKAGE` (as root) runs paru as the unprivileged build user "
                   "`aurbuild` in /var/lib/aurbuild (never in /workspace) and installs the result with pacman. "
                   "`paru` and `makepkg` refuse to run as root, and sudo cannot raise privileges here. "
                   "Review first with `ocs-aur -Gp PACKAGE` (prints the PKGBUILD); installed packages run as root."),),
           aur_helper="paru"),
)}
DEFAULT = "debian"


def get(distro_id: str) -> Distro:
    try:
        return REGISTRY[distro_id]
    except (KeyError, TypeError):
        from .core import SandboxError
        raise SandboxError(f"Unknown distribution {distro_id!r}; available: {', '.join(REGISTRY)}") from None


def previous_tag(distro: Distro, token: str) -> str:
    """Rollback copy of a replaced base image (`update-base`)."""
    return f"{REPOSITORY}:{distro.id}-previous-{token}"


def candidate_tag(distro: Distro, token: str) -> str:
    return f"{REPOSITORY}:{distro.id}-candidate-{token}"
