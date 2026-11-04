"""Brief card: load and validate the YAML schema (see README, 'Brief card')."""
from pathlib import Path

import yaml

REQUIRED = ["name", "function", "hard_dimensions", "interfaces", "soft_preferences",
            "assumptions", "params"]
PARAM_KEYS = {"value", "min", "max", "unit", "intent"}
BBOX_PROBES = {"bbox_x", "bbox_y", "bbox_z"}
HOLE_PROBES = {"hole_spacing", "hole_count"}


class BriefError(ValueError):
    pass


def validate(brief):
    """Raise BriefError on any schema problem; return the brief with defaults filled."""
    missing = [k for k in REQUIRED if k not in brief]
    if missing:
        raise BriefError(f"missing fields: {missing}")
    for name, value in brief["hard_dimensions"].items():
        if not isinstance(value, (int, float)):
            raise BriefError(f"hard_dimensions.{name} must be a number (mm)")
    for name, spec in brief["params"].items():
        absent = PARAM_KEYS - set(spec)
        if absent:
            raise BriefError(f"params.{name} missing {sorted(absent)}")
        if not spec["min"] <= spec["value"] <= spec["max"]:
            raise BriefError(f"params.{name}: value outside min..max")
    measures = brief.setdefault("measures", {})
    for name in brief["hard_dimensions"]:
        if name not in measures:
            raise BriefError(f"hard dimension {name!r} has no entry in measures")
    for name, probe in measures.items():
        kind = probe.get("probe")
        if kind not in BBOX_PROBES | HOLE_PROBES:
            raise BriefError(f"measures.{name}: unknown probe {kind!r}")
        if kind in HOLE_PROBES and not {"axis", "dia"} <= set(probe):
            raise BriefError(f"measures.{name}: {kind} needs axis and dia")
    brief.setdefault("allow_supports", False)
    brief.setdefault("expected_solids", 1)
    return brief


def load_brief(path):
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise BriefError(f"{path}: not a YAML mapping")
    return validate(data)
