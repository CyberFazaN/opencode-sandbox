"""Read-only Updates inventory. No discovery, image helpers or lifecycle mutation on inventory."""
import json
import re

from . import core as c
from . import distros
from . import opencode_versions as v


def base_inventory(distro, *, check=False):
    p = c.docker("image", "inspect", distro.image, capture=True, check=False)
    if p.returncode:
        if "no such image:" in (p.stderr or "").lower():
            return {"state": "not built", "version": None, "observation": None, "eligible": False}
        raise c.SandboxError(f"Cannot inspect {distro.image}: {p.stderr.strip()}")
    try:
        (info,) = json.loads(p.stdout)
        image_id = info["Id"]
        if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id): raise ValueError("invalid ID")
        labels = info["Config"].get("Labels") or {}
        if not isinstance(labels, dict): raise TypeError("invalid labels")
    except (ValueError, KeyError, TypeError) as exc:
        raise c.SandboxError(f"Invalid base inventory for {distro.image}") from exc
    definition = distros.image_definition(distro.id, labels)
    eligible = definition is not None and not labels.get(c.DATA_LABEL) and not labels.get(distros.LABEL + "id")
    if not eligible:
        state = "ownership/provenance unknown"
    elif definition.revision > distro.revision:
        state = "newer definition"
    elif definition.revision < distro.revision:
        state = "old definition"
    elif definition.version != distro.version:
        state = "different definition"
    else:
        state = "current definition"
    result = {"state": state, "image": image_id, "created": info.get("Created"),
              "definition": vars(definition) if definition else None, "eligible": eligible,
              "version": None, "observation": None, "build_version": labels.get(v.VERSION_LABEL)}
    # Inspect the immutable object again, never a mutable tag, for cache/probe evidence.
    if eligible:
        observed = v.image_observation(image_id, check=check)
        result.update(observed)
        result["version"] = observed["observation"]["value"] if observed["observation"] else None
    return result
