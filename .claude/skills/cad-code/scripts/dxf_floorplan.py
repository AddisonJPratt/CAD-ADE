#!/usr/bin/env python3
"""
dxf_floorplan.py — parse a 2D DXF floor plan into a structured JSON the
CAD-building step can consume, so a 3D building can be generated from a
real drawing instead of hand-typed parameters.

DWG note: this reads DXF, not DWG. DWG is Autodesk's proprietary binary
format and there's no open-source reader available in this sandbox (no
apt package, no pip package that handles real DWG — only DXF). If the user
has a .dwg file, they need to export/convert it to DXF first — LibreCAD,
QCAD, and the free Autodesk/ODA File Converter, or "Save As DXF" from
AutoCAD/most CAD software, all do this in seconds. Say this plainly rather
than pretending DWG works.

Layer convention this parser expects (tell the user if their file uses
different layer names — pass them as arguments):
- Wall centerlines: closed LWPOLYLINE (or LINE chain) on a "walls" layer
- Door openings: closed rectangle (LWPOLYLINE) straddling a wall, on a
  "doors" layer — the rectangle's extent along the wall = opening width
- Window openings: same convention, on a "windows" layer

Usage:
    python3 dxf_floorplan.py floorplan.dxf floorplan.json
    python3 dxf_floorplan.py floorplan.dxf floorplan.json \\
        --wall-layer WALLS --door-layer DOORS --window-layer WINDOWS \\
        --wall-thickness 200
"""
import argparse
import json
import sys

import ezdxf
import numpy as np


def polyline_points(entity):
    if entity.dxftype() == "LWPOLYLINE":
        return [(p[0], p[1]) for p in entity.get_points()]
    if entity.dxftype() == "LINE":
        return [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]
    return []


def segment_from_points(pts):
    """Wall centerline segments: consecutive point pairs from a polyline."""
    segs = []
    for i in range(len(pts) - 1):
        segs.append((pts[i], pts[i + 1]))
    return segs


def rect_bounds(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def project_opening_onto_wall(opening_pts, wall_start, wall_end):
    """
    Given an opening marker's bounding rectangle and a wall segment,
    return (offset_along_wall, width) if the opening's centroid lies near
    the wall's line, else None.
    """
    wall_start = np.array(wall_start, dtype=float)
    wall_end = np.array(wall_end, dtype=float)
    wall_vec = wall_end - wall_start
    wall_len = np.linalg.norm(wall_vec)
    if wall_len < 1e-6:
        return None
    wall_dir = wall_vec / wall_len

    xs = [p[0] for p in opening_pts]
    ys = [p[1] for p in opening_pts]
    centroid = np.array([sum(xs) / len(xs), sum(ys) / len(ys)])

    # distance from centroid to the infinite wall line
    to_centroid = centroid - wall_start
    along = np.dot(to_centroid, wall_dir)
    perp = to_centroid - along * wall_dir
    dist = np.linalg.norm(perp)
    if dist > 300:  # not near this wall (tune per wall thickness if needed)
        return None
    if along < -50 or along > wall_len + 50:  # not within this wall's span
        return None

    # width = extent of the marker rectangle projected onto wall direction
    corners = np.array(opening_pts)
    projections = (corners - wall_start) @ wall_dir
    width = projections.max() - projections.min()
    offset = projections.min()
    return float(offset), float(width)


def parse(dxf_path, wall_layer="WALLS", door_layer="DOORS", window_layer="WINDOWS",
          wall_thickness=200.0, wall_height=2700.0, door_height=2100.0,
          window_height=1200.0, window_sill=900.0):
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    wall_segments = []
    for e in msp.query(f'LWPOLYLINE[layer=="{wall_layer}"]'):
        pts = polyline_points(e)
        wall_segments.extend(segment_from_points(pts))
    for e in msp.query(f'LINE[layer=="{wall_layer}"]'):
        pts = polyline_points(e)
        wall_segments.extend(segment_from_points(pts))

    door_markers = [polyline_points(e) for e in msp.query(f'LWPOLYLINE[layer=="{door_layer}"]')]
    window_markers = [polyline_points(e) for e in msp.query(f'LWPOLYLINE[layer=="{window_layer}"]')]

    walls_out = []
    for (start, end) in wall_segments:
        openings = []
        for marker in door_markers:
            r = project_opening_onto_wall(marker, start, end)
            if r:
                offset, width = r
                openings.append({"type": "door", "offset": offset, "width": width,
                                  "z0": 0.0, "height": door_height})
        for marker in window_markers:
            r = project_opening_onto_wall(marker, start, end)
            if r:
                offset, width = r
                openings.append({"type": "window", "offset": offset, "width": width,
                                  "z0": window_sill, "height": window_height})
        walls_out.append({
            "start": list(start), "end": list(end),
            "thickness": wall_thickness, "height": wall_height,
            "openings": openings,
        })

    return {
        "wall_thickness": wall_thickness,
        "wall_height": wall_height,
        "walls": walls_out,
        "source_file": dxf_path,
        "warnings": [] if wall_segments else [
            f"No wall centerlines found on layer '{wall_layer}' — check the "
            f"layer name matches the DXF, or pass --wall-layer explicitly."
        ],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dxf_path")
    ap.add_argument("out_json")
    ap.add_argument("--wall-layer", default="WALLS")
    ap.add_argument("--door-layer", default="DOORS")
    ap.add_argument("--window-layer", default="WINDOWS")
    ap.add_argument("--wall-thickness", type=float, default=200.0)
    ap.add_argument("--wall-height", type=float, default=2700.0)
    ap.add_argument("--door-height", type=float, default=2100.0)
    ap.add_argument("--window-height", type=float, default=1200.0)
    ap.add_argument("--window-sill", type=float, default=900.0)
    args = ap.parse_args()

    try:
        result = parse(
            args.dxf_path, args.wall_layer, args.door_layer, args.window_layer,
            args.wall_thickness, args.wall_height, args.door_height,
            args.window_height, args.window_sill,
        )
    except ezdxf.DXFStructureError as e:
        print(json.dumps({"error": f"Not a valid DXF file: {e}"}), file=sys.stderr)
        sys.exit(1)

    with open(args.out_json, "w") as f:
        json.dump(result, f, indent=2)

    print(json.dumps({
        "walls_found": len(result["walls"]),
        "openings_found": sum(len(w["openings"]) for w in result["walls"]),
        "warnings": result["warnings"],
    }))
