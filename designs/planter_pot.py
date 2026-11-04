"""Round tapered planter with drain hole and foot ring. See evals/briefs/planter_pot.yaml.

Frame: Z is print-up, foot ring on z=0, axis on Z. Wall thickness is even normal to the taper.
taper_deg is a limit: on short, wide-taper combinations the base would close up, so the floor
holds a minimum diameter that clears the drain and the ring, and the taper eases to reach it.
"""
import math

from build123d import Align, Axis, Box, Cylinder, Plane, Polygon, Pos, Vector, extrude, revolve

from library import standard_parts

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "rim_dia": (100.0, 70.0, 160.0),    # outer rim diameter (hard dimension)
    "height": (90.0, 60.0, 150.0),      # overall height (hard dimension)
    "taper_deg": (8.0, 3.0, 25.0),      # wall lean from vertical, deg
    "wall": (2.4, 1.6, 3.2),            # even wall thickness
}


def build(rim_dia, height, taper_deg, wall):
    constants = standard_parts()["brief_constants"]["planter_pot"]
    drain_dia = constants["drain_dia"]
    foot_h = 2 * wall                   # ring height: lifts the drain clear of a saucer
    ring_w = 2 * wall
    floor_z = foot_h + wall             # top of the floor
    band_z = height - wall              # short vertical rim band: rounding it keeps the rim diameter

    # Base diameter from the taper, held open so the drain and the ring still fit.
    rim_r = rim_dia / 2
    base_r = max(rim_r - (band_z - foot_h) * math.tan(math.radians(taper_deg)), drain_dia + 2 * ring_w)
    lean = math.atan((rim_r - base_r) / (band_z - foot_h))
    foot_r = min(constants["foot_dia"] / 2, base_r)

    # Feature: shell, revolved; inner cone offset by wall normal to the taper, so it stays even.
    inner_rim_r = rim_r - wall / math.cos(lean)
    inner_floor_r = inner_rim_r - (height - floor_z) * math.tan(lean)
    section = Plane.XZ * Polygon(
        (foot_r - ring_w, foot_h), (base_r, foot_h), (rim_r, band_z), (rim_r, height), (inner_rim_r, height),
        (inner_floor_r, floor_z), (0, floor_z), (0, foot_h), align=None)
    # Feature: foot ring, overlapping into the floor so the union is solid.
    ring = Plane.XZ * Polygon(
        (foot_r - ring_w, 0), (foot_r, 0), (foot_r, floor_z), (foot_r - ring_w, floor_z), align=None)
    pot = revolve(section, axis=Axis.Z) + revolve(ring, axis=Axis.Z)

    # Feature: rounded rim, outside edge.
    rim_edge = min(pot.edges(), key=lambda e: (Vector(rim_r, 0, height) - e.position_at(0)).length
                   if abs(e.center().Z - height) < wall else math.inf)
    pot = pot.fillet(wall * 0.5 * 0.5, [rim_edge])

    # Feature: drain hole through the floor.
    pot -= Pos(0, 0, foot_h - wall) * Cylinder(drain_dia / 2, 2 * floor_z,
                                               align=(Align.CENTER, Align.CENTER, Align.MIN))
    # Feature: two weep slots through the ring, so water can leave the space it encloses.
    pot -= Box(2 * rim_dia, ring_w, foot_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

    pot.label = "pot"
    return pot


def section_plane(**_):
    return {"axis": "X", "offset": 0}
