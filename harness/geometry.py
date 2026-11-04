"""Gate 2: solid count/validity, volume, hard dimensions, part overlap."""
import numpy as np

DIM_TOLERANCE = 0.1       # mm, per the brief
DIA_TOLERANCE = 0.02      # mm, to match a cylinder to a probe's diameter
OVERLAP_LIMIT = 0.1       # mm^3; meshes touching at a face measure ~0 within this
VOLUME_REL = 1e-3         # allowed relative change across a STEP round trip
AXES = {"X": 0, "Y": 1, "Z": 2}


def hole_axes(cylinders, axis, dia):
    """Distinct hole centre positions (in-plane) for internal cylinders on one axis."""
    index = AXES[axis.upper()]
    positions = []
    for cyl in cylinders:
        if abs(abs(cyl["dir"][index]) - 1) > 1e-6 or abs(cyl["dia"] - dia) > DIA_TOLERANCE:
            continue
        centre = np.array(cyl["origin"], dtype=float)
        centre[index] = 0.0
        if not any(np.linalg.norm(centre - p) < DIA_TOLERANCE for p in positions):
            positions.append(centre)
    return positions


def measure(probe, parts):
    """Evaluate one measures entry on the reloaded B-rep. Returns a number or None."""
    selected = [p for p in parts if probe.get("part") in (None, p["name"])]
    if not selected:
        return None
    kind = probe["probe"]
    if kind.startswith("bbox_"):
        index = AXES[kind[-1].upper()]
        low = min(p["bbox"]["min"][index] for p in selected)
        high = max(p["bbox"]["max"][index] for p in selected)
        return high - low
    cylinders = [c for p in selected for c in p["cylinders"]]
    positions = hole_axes(cylinders, probe["axis"], probe["dia"])
    if kind == "hole_count":
        return float(len(positions))
    if len(positions) != 2:
        return None  # spacing is only defined for exactly one pair
    return float(np.linalg.norm(positions[0] - positions[1]))


def expected_dimension(name, brief, params):
    """A hard dimension bound to a same-named param follows that param during sweeps."""
    if params is not None and name in brief["params"] and name in params:
        return params[name]
    return brief["hard_dimensions"][name]


def check_geometry(result, brief=None, expected_solids=None):
    """Return {pass, problems, ...} for one worker result."""
    parts = result["parts"]
    problems = []
    all_solids = [s for p in parts for s in p["solids"]]
    if expected_solids is None:
        expected_solids = brief["expected_solids"] if brief else result.get("expected_solids") or 1
    if len(all_solids) != expected_solids:
        problems.append(f"{len(all_solids)} solids, expected {expected_solids}")
    for part in parts:
        for solid in part["solids"]:
            if not solid["valid"]:
                problems.append(f"{part['name']}: invalid solid")
            if not solid["closed"]:
                problems.append(f"{part['name']}: open shell")
            if solid["volume"] <= 0:
                problems.append(f"{part['name']}: volume {solid['volume']:.3f}")
        if abs(part["volume_in_memory"] - part["volume"]) > VOLUME_REL * abs(part["volume"]):
            problems.append(f"{part['name']}: STEP reload volume differs from the built solid")
    rows = []
    if brief:
        for name in brief["hard_dimensions"]:
            spec = expected_dimension(name, brief, result.get("params"))
            value = measure(brief["measures"][name], parts)
            ok = value is not None and abs(value - spec) <= DIM_TOLERANCE
            rows.append({"name": name, "spec": spec, "measured": value,
                         "delta": None if value is None else value - spec, "pass": ok})
            if not ok:
                problems.append(f"{name}: measured {value}, spec {spec}")
        for name, spec in brief["params"].items():
            declared = result["declared"].get(name)
            if declared != [spec["value"], spec["min"], spec["max"]]:
                problems.append(f"brief param {name} differs from design PARAMS: {declared}")
        extra = set(result["declared"]) - set(brief["params"])
        if extra:
            problems.append(f"design PARAMS not in brief: {sorted(extra)}")
    return {"pass": not problems, "problems": problems, "dimensions": rows,
            "solids": len(all_solids), "expected_solids": expected_solids,
            "volume": sum(p["volume"] for p in parts),
            "bbox": {p["name"]: p["bbox"]["size"] for p in parts}}


def pairwise_overlaps(stl_paths):
    """Overlap volume of each part pair, from meshes reloaded off disk, via manifold3d."""
    import manifold3d
    import trimesh
    if len(stl_paths) < 2:
        return []
    bodies = {}
    for name, path in stl_paths.items():
        mesh = trimesh.load_mesh(path)
        bodies[name] = manifold3d.Manifold(manifold3d.Mesh(
            vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
            tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))
    names = list(bodies)
    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            volume = (bodies[a] ^ bodies[b]).volume()
            rows.append({"a": a, "b": b, "volume": volume, "pass": volume <= OVERLAP_LIMIT})
    return rows
