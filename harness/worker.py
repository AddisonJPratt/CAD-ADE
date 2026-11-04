"""Build one design in this process and write result.json. Always run as a subprocess.

    python -m harness.worker design.py out_dir [params_json]

Every part is exported to STL and STEP, and all B-rep facts are measured on the STEP
file reloaded from disk.
"""
import importlib.util
import json
import math
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STL_TOLERANCE = 0.01      # mm linear deflection
STL_ANGULAR = 0.1         # rad


def load_design(path):
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("magic_design", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def named_parts(result):
    """Normalize build()'s return value to [(name, shape)]."""
    if isinstance(result, dict):
        return list(result.items())
    if isinstance(result, (list, tuple)):
        parts = []
        for i, item in enumerate(result):
            if isinstance(item, tuple):
                parts.append(item)
            else:
                parts.append((getattr(item, "label", "") or f"part{i + 1}", item))
        return parts
    return [(getattr(result, "label", "") or "part", result)]


def is_closed(solid):
    from OCP.BRep import BRep_Tool
    return bool(solid.shells()) and all(BRep_Tool.IsClosed_s(s.wrapped) for s in solid.shells())


def bbox_dict(shape):
    box = shape.bounding_box()
    return {"min": [box.min.X, box.min.Y, box.min.Z], "max": [box.max.X, box.max.Y, box.max.Z],
            "size": [box.size.X, box.size.Y, box.size.Z]}


def internal_cylinders(shape):
    """All material-outside cylindrical faces: holes, plus concave fillets."""
    from build123d import GeomType
    found = []
    for face in shape.faces():
        if face.geom_type != GeomType.CYLINDER:
            continue
        axis = face.axis_of_rotation
        direction = axis.direction
        point = face.position_at(0.5, 0.5)
        to_axis = (axis.position + direction * (point - axis.position).dot(direction)) - point
        if face.normal_at(point).dot(to_axis) <= 0:
            continue  # normal points away from the axis: a convex (external) surface
        found.append({"dia": 2 * face.radius, "dir": [direction.X, direction.Y, direction.Z],
                      "origin": [axis.position.X, axis.position.Y, axis.position.Z]})
    return found


def build_and_measure(design_path, out_dir, overrides):
    from build123d import export_step, export_stl, import_step
    module = load_design(design_path)
    declared = {k: list(v) for k, v in module.PARAMS.items()}
    params = {k: v[0] for k, v in module.PARAMS.items()}
    unknown = set(overrides) - set(params)
    if unknown:
        raise ValueError(f"unknown params: {sorted(unknown)}")
    params.update(overrides)
    parts = []
    for name, shape in named_parts(module.build(**params)):
        stl, step = out_dir / f"{name}.stl", out_dir / f"{name}.step"
        export_stl(shape, str(stl), tolerance=STL_TOLERANCE, angular_tolerance=STL_ANGULAR)
        export_step(shape, str(step))
        reloaded = import_step(str(step))
        solids = reloaded.solids()
        parts.append({
            "name": name, "stl": str(stl), "step": str(step),
            "solids": [{"valid": bool(s.is_valid), "closed": is_closed(s), "volume": s.volume}
                       for s in solids],
            "volume_in_memory": shape.volume, "volume": sum(s.volume for s in solids),
            "bbox": bbox_dict(reloaded), "cylinders": internal_cylinders(reloaded),
        })
    section = getattr(module, "section_plane", None)
    return {"ok": True, "declared": declared, "params": params, "parts": parts,
            "expected_solids": getattr(module, "EXPECTED_SOLIDS", None),
            "section": section(**params) if section else None}


def main():
    design, out_dir = sys.argv[1], Path(sys.argv[2])
    overrides = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = build_and_measure(design, out_dir, overrides)
    except BaseException:
        result = {"ok": False, "traceback": traceback.format_exc()}
    (out_dir / "result.json").write_text(json.dumps(result, indent=1))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
