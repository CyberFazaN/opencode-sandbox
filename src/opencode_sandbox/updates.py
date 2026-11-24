"""Read-only Updates inventory. No discovery, image helpers or lifecycle mutation on inventory."""
from . import core as c
from . import opencode_versions as v


def base_inventory(distro, *, check=False):
    info = c.base_image_info(distro.image)
    if info is None:
        return {"state": "not built", "version": None, "observation": None, "eligible": False}
    image_id = info["Id"]
    labels = info["Config"].get("Labels") or {}
    definition = c.base_definition(distro, info)
    eligible = definition is not None
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
    if eligible:
        observed = v.inspect_image_version_evidence(image_id, labels, check=check)
        result.update(observed)
        result["version"] = observed["observation"]["value"] if observed["observation"] else None
    return result
