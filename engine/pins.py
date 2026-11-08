"""Note pins: short comments attached to a place on a version's model (#26).

A pin is a note about one saved version, not part of its source, so it lives beside the
repository like the version's verdict: .magic/pins/<version id>.json. Saving pins never
dirties the project. Studio sends a version's pins with every request to the agent.

    {"id", "instance", "point": [x, y, z], "normal": [x, y, z], "note", "feature": str|null, "face": int|null}
"""
import json
import math

from .versions import STATE, find_version, require_versioned
from .projects import ProjectError

MAX_NOTE = 280   # characters: a short comment, not a document
MAX_PINS = 50    # per version: enough to annotate a part, few enough to read


class PinError(ProjectError):
    """A pin that cannot be stored as sent."""


def _vec(value, name):
    if not (isinstance(value, list) and len(value) == 3
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value)):
        raise PinError(f"pin {name} must be three finite numbers")
    return [float(v) for v in value]


def _clean(raw):
    if not isinstance(raw, dict):
        raise PinError("each pin must be an object")
    ident, instance, note = raw.get("id"), raw.get("instance"), raw.get("note")
    if not isinstance(ident, str) or not ident.strip() or len(ident) > 64:
        raise PinError("pin id must be a short string")
    if not isinstance(instance, str) or not instance.strip():
        raise PinError("pin instance must name a body")
    if not isinstance(note, str) or not note.strip():
        raise PinError("pin note must not be empty")
    note = note.strip()
    if len(note) > MAX_NOTE:
        raise PinError(f"pin note is longer than {MAX_NOTE} characters")
    feature, face = raw.get("feature"), raw.get("face")
    if feature is not None and not isinstance(feature, str):
        raise PinError("pin feature must be a name or null")
    if face is not None and (not isinstance(face, int) or isinstance(face, bool)):
        raise PinError("pin face must be a face id or null")
    return {"id": ident, "instance": instance, "point": _vec(raw.get("point"), "point"),
            "normal": _vec(raw.get("normal"), "normal"), "note": note, "feature": feature, "face": face}


def _path(project, version):
    project = require_versioned(project)
    version_id = find_version(project, version)["id"]
    return project / STATE / "pins" / f"{version_id}.json", version_id


def load_pins(project, version):
    path, _ = _path(project, version)
    return json.loads(path.read_text())["pins"] if path.is_file() else []


def save_pins(project, version, pins):
    """Replace a version's pins with `pins` (validated); an empty list clears them."""
    if not isinstance(pins, list):
        raise PinError("pins must be a list")
    if len(pins) > MAX_PINS:
        raise PinError(f"at most {MAX_PINS} pins per version")
    cleaned = [_clean(p) for p in pins]
    if len({p["id"] for p in cleaned}) != len(cleaned):
        raise PinError("pin ids must be unique")
    path, version_id = _path(project, version)
    if not cleaned:
        path.unlink(missing_ok=True)
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": version_id, "pins": cleaned}, indent=2))
    temporary.replace(path)
    return cleaned


def pin_document(project, version):
    _, version_id = _path(project, version)
    return {"version": version_id, "pins": load_pins(project, version)}
