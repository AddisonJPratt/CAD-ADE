"""Build one design in this process and write result.json. Always run as a subprocess.

    python -m harness.worker design.py out_dir [params_json]

Every part is exported to STL and STEP, and all B-rep facts are measured on the STEP
file reloaded from disk. Beside each STL goes `<part>.faces.json`: every B-rep face with
its geometry (kind, centre, normal or axis, area, bbox) and the name of the feature the
design gave it with `library.feature(...)`, or null. Studio reads it to name a picked face.
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
FACE_ON_FEATURE = 0.01    # mm: a face belongs to a feature when its sample point lies on the feature's boundary
# Parametric samples tried in turn for a point that lies inside the face, clear of its edges: a
# face with a hole in it (a top face around a pocket) has its parametric centre in the hole, and
# a point on the rim of that hole would also lie on the cutter that made it.
FACE_SAMPLES = ((0.5, 0.5), (0.3, 0.3), (0.7, 0.7), (0.3, 0.7), (0.7, 0.3), (0.15, 0.5), (0.5, 0.15),
                (0.85, 0.5), (0.5, 0.85), (0.1, 0.1), (0.9, 0.9), (0.1, 0.9), (0.9, 0.1))
EDGE_CLEARANCE = 0.1      # mm: how far inside its edges the sample point must lie


def load_design(path, fits=None):
    sys.path.insert(0, str(ROOT))
    project = Path(path).resolve().parent.parent
    if (project / "library" / "__init__.py").is_file():
        sys.path.insert(0, str(project))
    if fits is not None:
        from library import standard_parts
        standard_parts()["fits"].update(fits)
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


def _xyz(v):
    return [c + 0.0 for c in (v.X, v.Y, v.Z)]  # + 0.0 turns -0.0 into 0.0


def point_on(face):
    """A point that lies on the face itself, not in one of its holes and not on its rim."""
    edges = face.edges()
    fallback = None
    for u, v in FACE_SAMPLES:
        point = face.position_at(u, v)
        if not face.is_inside(point):
            continue
        if all(edge.distance_to(point) > EDGE_CLEARANCE for edge in edges):
            return point
        fallback = fallback or point
    return fallback or face.position_at(0.5, 0.5)


def face_map(part_name, shape, features):
    """Every face of `shape` with its geometry and the named feature it belongs to, if any.

    A face belongs to the first declared feature whose boundary passes through the face's
    centre point: the faces a cutter leaves behind lie on the cutter's faces, and a boss's
    faces are its own. Unnamed faces keep their geometry so a pick still has a description.
    """
    from build123d import GeomType
    feature_faces = [(name, feature.faces()) for name, feature in features]
    faces = []
    for index, face in enumerate(shape.faces()):
        centre = point_on(face)
        name = next((n for n, fs in feature_faces
                     if any(f.distance_to(centre) <= FACE_ON_FEATURE for f in fs)), None)
        box = face.bounding_box()
        entry = {"id": index, "kind": face.geom_type.name.lower(), "feature": name,
                 "centre": _xyz(centre), "normal": None, "axis": None, "area": face.area,
                 "bbox": {"min": _xyz(box.min), "max": _xyz(box.max)}}
        if face.geom_type == GeomType.PLANE:
            entry["normal"] = _xyz(face.normal_at(centre))
        elif face.geom_type in (GeomType.CYLINDER, GeomType.CONE, GeomType.TORUS):
            axis = face.axis_of_rotation
            entry["axis"] = {"origin": _xyz(axis.position), "direction": _xyz(axis.direction)}
            if face.geom_type == GeomType.CYLINDER:
                entry["radius"] = face.radius
        faces.append(entry)
    return {"part": part_name, "features": [name for name, _ in features], "faces": faces}


def build_and_measure(design_path, out_dir, overrides, fits=None):
    from build123d import export_step, export_stl, import_step
    module = load_design(design_path, fits)
    import library.features as feature_registry  # the copy the design imported (project or root)
    reset = getattr(feature_registry, "reset_features", lambda: None)
    declared_features = getattr(feature_registry, "declared_features", list)
    declared = {k: list(v) for k, v in module.PARAMS.items()}
    params = {k: v[0] for k, v in module.PARAMS.items()}
    unknown = set(overrides) - set(params)
    if unknown:
        raise ValueError(f"unknown params: {sorted(unknown)}")
    params.update(overrides)
    parts = []
    reset()
    built = named_parts(module.build(**params))
    features = declared_features()
    for name, shape in built:
        stl, step, faces = out_dir / f"{name}.stl", out_dir / f"{name}.step", out_dir / f"{name}.faces.json"
        export_stl(shape, str(stl), tolerance=STL_TOLERANCE, angular_tolerance=STL_ANGULAR)
        export_step(shape, str(step))
        faces.write_text(json.dumps(face_map(name, shape, features), indent=1))
        reloaded = import_step(str(step))
        solids = reloaded.solids()
        parts.append({
            "name": name, "stl": str(stl), "step": str(step), "faces": str(faces),
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
    fits = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = build_and_measure(design, out_dir, overrides, fits)
    except BaseException:
        result = {"ok": False, "traceback": traceback.format_exc()}
    (out_dir / "result.json").write_text(json.dumps(result, indent=1))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
