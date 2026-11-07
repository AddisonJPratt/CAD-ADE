"""Gate 3: checks on the STL reloaded from disk, never on in-memory geometry.

Overhang is reported two ways, both gated at OVERHANG_LIMIT_PCT. Z is the print axis.
Both are area shares of all downward-facing area, bed contact included.

- overhang_brief_pct: the brief's wording, "downward faces >45 deg from straight down".
  Taken literally, this counts steep, printable faces and misses flat ceilings.
- support_risk_pct: faces a slicer would flag at a 45 deg threshold, i.e. within 45 deg
  of straight down and not on the bed. Added so flat ceilings cannot pass unseen.
"""
import numpy as np
import trimesh
from scipy import ndimage
from library.printer_profiles import PROFILE

DEFAULT_BUILD_VOLUME = tuple(PROFILE["build_volume_mm"])
OVERHANG_LIMIT_PCT = 15.0
VERTICAL_EPS = np.sin(np.radians(0.5))  # nearer vertical than 0.5 deg = vertical (float noise)
BED_Z_TOL = 0.01                 # mm
MIN_FEATURE_WARN = 0.8           # mm, two 0.4 mm perimeters
MIN_BED_CONTACT = 1.0            # mm^2


def overhang_metrics(mesh):
    normals, areas = mesh.face_normals, mesh.area_faces
    down = normals[:, 2] < -VERTICAL_EPS
    angle = np.degrees(np.arccos(np.clip(-normals[:, 2], -1, 1)))
    z_min = mesh.bounds[0, 2]
    on_bed = down & (angle < 1.0) & (mesh.triangles[:, :, 2].max(axis=1) <= z_min + BED_Z_TOL)
    total_down = areas[down].sum()
    share = lambda mask: 100.0 * areas[mask].sum() / total_down if total_down else 0.0
    return {
        "overhang_brief_pct": share(down & (angle > 45)),
        "support_risk_pct": share(down & (angle <= 45) & ~on_bed),
        "flat_undersides_above_bed_mm2": float(areas[down & (angle < 1.0) & ~on_bed].sum()),
        "bed_contact_mm2": float(areas[on_bed].sum()),
    }


def rasterize_section(segments, pixel):
    """Parity-fill 2D segments (n,2,2) into a boolean grid. Returns mask, x0, y0."""
    low, high = segments.reshape(-1, 2).min(axis=0), segments.reshape(-1, 2).max(axis=0)
    width, height = np.ceil((high - low) / pixel).astype(int) + 3
    x0, y0 = low - pixel
    mask = np.zeros((height, width), dtype=bool)
    a, b = segments[:, 0], segments[:, 1]
    for row in range(height):
        y = y0 + (row + 0.5) * pixel
        crossing = (a[:, 1] <= y) != (b[:, 1] <= y)
        if not crossing.any():
            continue
        t = (y - a[crossing, 1]) / (b[crossing, 1] - a[crossing, 1])
        xs = np.sort(a[crossing, 0] + t * (b[crossing, 0] - a[crossing, 0]))
        for start, end in zip(xs[::2], xs[1::2]):
            i0, i1 = np.ceil(((start - x0) / pixel - 0.5, (end - x0) / pixel - 0.5)).astype(int)
            mask[row, i0:i1] = True
    return mask, x0, y0


def section_segments(mesh, axis, offset):
    """Section by an axis-aligned plane: 2D segments in the remaining two coordinates."""
    normal = np.zeros(3)
    normal[axis] = 1.0
    origin = np.zeros(3)
    origin[axis] = offset
    lines = trimesh.intersections.mesh_plane(mesh, normal, origin)
    keep = [i for i in range(3) if i != axis]
    return np.asarray(lines).reshape(-1, 2, 3)[:, :, keep]


def thinnest_in_mask(mask, pixel, upper):
    """Smallest disk diameter whose morphological opening deletes a wall-like region.

    A region counts only if its inscribed radius is >= 60 % of the disk's. A 90 deg
    corner's leftover reaches about 29 %, so plain corners are not reported as thin.
    """
    # EDT measures to background pixel centres, half a pixel past the true boundary.
    inside = (ndimage.distance_transform_edt(mask) - 0.5) * pixel
    t = 2 * pixel
    while t < upper:
        core = inside >= t / 2
        if not core.any():
            return t  # nothing that wide fits anywhere in this section
        opened = ndimage.distance_transform_edt(~core) * pixel <= t / 2 + pixel
        labels, count = ndimage.label(mask & ~opened)
        if count and ndimage.maximum(inside, labels, range(1, count + 1)).max() >= 0.6 * t / 2:
            return t
        t += 2 * pixel
    return upper


def min_feature(mesh, slices=8, max_pixels=500):
    """Thinnest wall estimate by section sampling; an approximation, not a guarantee.

    Slices `slices` planes per axis, rasterizes at about 0.2 mm, and runs
    thinnest_in_mask. Long walls read within one step (2 pixels; see tests). Short tabs
    can read about 1 mm high, and features lying between planes can be missed.
    """
    best, where = np.inf, None
    pixel = max(0.2, float(mesh.extents.max()) / max_pixels)
    for axis in range(3):
        low, high = mesh.bounds[:, axis]
        for fraction in (np.arange(slices) + 0.5) / slices:
            offset = low + fraction * (high - low) + 1.3e-3  # avoid coplanar facets
            segments = section_segments(mesh, axis, offset)
            if not len(segments):
                continue
            mask, _, _ = rasterize_section(segments, pixel)
            value = thinnest_in_mask(mask, pixel, min(best, 12.0))
            if value < best:
                best, where = value, {"axis": "XYZ"[axis], "offset": round(float(offset), 2)}
    return {"mm": float(best), "resolution_mm": 2 * pixel, "where": where}


def check_stl(path, allow_supports=False, sections=True, build_volume=DEFAULT_BUILD_VOLUME):
    """Reload an STL from disk and return {pass, problems, metrics}."""
    mesh = trimesh.load_mesh(path)
    extents = mesh.extents
    metrics = {"watertight": bool(mesh.is_watertight),
               "winding_consistent": bool(mesh.is_winding_consistent),
               "components": int(mesh.body_count), "faces": len(mesh.faces),
               "mesh_volume": float(mesh.volume), "extents": [float(e) for e in extents],
               "inertia": [float(i) for i in np.diag(mesh.moment_inertia)],
               "fits_bed": bool(all(extents[i] <= build_volume[i] for i in range(3))),
               "allow_supports": allow_supports, **overhang_metrics(mesh)}
    problems = []
    if not metrics["watertight"] or not metrics["winding_consistent"]:
        problems.append("mesh not watertight/consistently wound")
    if metrics["components"] != 1:
        problems.append(f"{metrics['components']} mesh components")
    if not metrics["fits_bed"]:
        problems.append(f"size {extents[0]:.1f}x{extents[1]:.1f}x{extents[2]:.1f} exceeds bed or build height ({build_volume[0]:g}x{build_volume[1]:g}x{build_volume[2]:g} mm)")
    if metrics["bed_contact_mm2"] < MIN_BED_CONTACT:
        problems.append(f"only {metrics['bed_contact_mm2']:.2f} mm^2 on the bed")
    if not allow_supports:
        for key in ("overhang_brief_pct", "support_risk_pct"):
            if metrics[key] > OVERHANG_LIMIT_PCT:
                problems.append(f"{key} {metrics[key]:.1f} > {OVERHANG_LIMIT_PCT}")
    if sections:
        metrics["min_feature"] = min_feature(mesh)
        metrics["min_feature_warning"] = metrics["min_feature"]["mm"] < MIN_FEATURE_WARN
    return {"pass": not problems, "problems": problems, "metrics": metrics}
