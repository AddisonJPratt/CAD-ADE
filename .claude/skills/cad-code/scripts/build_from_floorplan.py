#!/usr/bin/env python3
"""
build_from_floorplan.py — turn a floorplan.json (from dxf_floorplan.py, or
hand-written for a prompt-only request) into 3D walls with real door/window
openings cut through them. Handles walls at any angle, not just the
axis-aligned rectangle case — each wall segment gets its own rotated box.

Usage (as a library):

    from build_from_floorplan import build_walls
    import json

    data = json.load(open("floorplan.json"))
    walls_solid, wall_solids_by_index = build_walls(data)
    # walls_solid: single unioned cq.Workplane for the whole shell
    # wall_solids_by_index: list of individual wall Workplanes, useful if
    # you want to color/tag them separately or add per-wall trim

Run standalone to go straight from floorplan JSON to STL/STEP:

    python3 build_from_floorplan.py floorplan.json out_prefix
    # writes out_prefix_walls.stl, out_prefix_walls.step
"""
import argparse
import json
import math
import sys

import cadquery as cq
from cadquery.occ_impl.exporters.assembly import exportAssembly


def wall_box(start, end, thickness, height, openings):
    """One wall as a box along its centerline, with openings cut through."""
    start = tuple(start)
    end = tuple(end)
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    angle = math.degrees(math.atan2(dy, dx))

    # Build the wall along local +X, centered on thickness, from z=0, then
    # rotate/translate into place — simplest way to get openings positioned
    # correctly regardless of wall angle.
    wall = (
        cq.Workplane("XY")
        .box(length, thickness, height, centered=(False, True, False))
    )
    for op in openings:
        cut = (
            cq.Workplane("XY")
            .center(op["offset"], 0)
            .box(op["width"], thickness + 20, op["height"], centered=(False, True, False))
            .translate((0, 0, op["z0"]))
        )
        wall = wall.cut(cut)

    wall = wall.rotate((0, 0, 0), (0, 0, 1), angle)
    wall = wall.translate((start[0], start[1], 0))
    return wall


def build_walls(data):
    wall_solids = []
    for w in data["walls"]:
        wall_solids.append(
            wall_box(w["start"], w["end"], w["thickness"], w["height"], w["openings"])
        )
    shell = wall_solids[0]
    for w in wall_solids[1:]:
        shell = shell.union(w)
    return shell, wall_solids


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("floorplan_json")
    ap.add_argument("out_prefix")
    args = ap.parse_args()

    with open(args.floorplan_json) as f:
        data = json.load(f)

    if not data["walls"]:
        print(json.dumps({"error": "No walls in floorplan JSON — nothing to build."}), file=sys.stderr)
        sys.exit(1)

    shell, wall_solids = build_walls(data)

    cq.exporters.export(shell, f"{args.out_prefix}_walls.stl")
    assy = cq.Assembly()
    for i, w in enumerate(wall_solids):
        assy.add(w, name=f"wall_{i+1}")
    exportAssembly(assy, f"{args.out_prefix}_walls.step")

    bb = shell.val().BoundingBox()
    print(json.dumps({
        "walls_built": len(wall_solids),
        "bbox_mm": [round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)],
    }))
