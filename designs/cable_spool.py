"""Wall-mounted cable spool: flange, hollow hub, retaining tabs, centre screw. See briefs/cable_spool.yaml.

Frame: Z is print-up and the spool axis, wall face on z=0. The hub is open at its free end, so the
screw's counterbore opens up and nothing inside has a ceiling. Only the tab undersides face down.
"""
import math

from build123d import Align, Axis, Box, Plane, Polygon, Pos, Rot, revolve

from library import counterbored_hole
from library.features import TEARDROP_FLANK_DEG

SCREW = "M4"            # hardware choice, resolved through library/standard_parts.json

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "flange_dia": (90.0, 80.0, 130.0),   # back flange diameter (hard dimension)
    "hub_dia": (50.0, 36.0, 60.0),       # hub outside diameter
    "spool_height": (40.0, 28.0, 60.0),  # overall height off the wall (hard dimension)
    "flange_t": (6.0, 5.2, 8.0),         # flange thickness; leaves at least 1 under the M4 head
    "wall": (3.0, 2.0, 4.0),             # hub wall
    "lip_reach": (7.0, 4.0, 10.0),       # tab reach past the hub
    "lip_arc": (50.0, 30.0, 70.0),       # angular width of each tab, deg
    "lip_count": (3, 2, 4),              # number of tabs round the hub, count
    "notch_w": (4.0, 3.0, 6.0),          # cable-end notch width in the flange rim
}


def ring_edge(shape, radius, z):
    """Named-feature selection: the circular edge nearest a given radius and height."""
    def miss(edge):
        p = edge.position_at(0)
        return abs(math.hypot(p.X, p.Y) - radius) + abs(p.Z - z)
    return min(shape.edges(), key=miss)


def build(flange_dia, hub_dia, spool_height, flange_t, wall, lip_reach, lip_arc, lip_count, notch_w):
    flange_r, hub_r = flange_dia / 2, hub_dia / 2
    bore_r = hub_r - wall

    # Feature: flange and hollow hub, one revolved profile. Floor is the flange; hub open at the top.
    body = revolve(Plane.XZ * Polygon(
        (0, 0), (flange_r, 0), (flange_r, flange_t), (hub_r, flange_t), (hub_r, spool_height),
        (bore_r, spool_height), (bore_r, flange_t), (0, flange_t), align=None), axis=Axis.Z)
    # Feature: load radius at the hub root, and a rounded flange edge for the hand winding past it.
    body = body.fillet(wall, [ring_edge(body, hub_r, flange_t)])
    body = body.fillet(flange_t * 0.5 * 0.5, [ring_edge(body, flange_r, flange_t)])

    # Feature: retaining tabs. Underside is a 44 deg cone from vertical, started inside the hub wall.
    # Reach never passes half the coil width, so a tab can't outgrow the flange on a large hub.
    lip_reach = min(lip_reach, (flange_r - hub_r) * 0.5)
    root_r = hub_r - wall * 0.5
    edge_t = wall * 0.5                  # tab's outer edge thickness, printable at two perimeters
    drop = (lip_reach + wall * 0.5) / math.tan(math.radians(TEARDROP_FLANK_DEG))
    tab_section = Plane.XZ * Polygon(
        (root_r, spool_height), (hub_r + lip_reach, spool_height), (hub_r + lip_reach, spool_height - edge_t),
        (root_r, spool_height - edge_t - drop), align=None)
    tab = revolve(tab_section, axis=Axis.Z, revolution_arc=lip_arc)
    for i in range(lip_count):
        body += Rot(0, 0, i * 2 * 180 / lip_count) * tab

    # Feature: centre screw, counterbored into the flange from inside the hub.
    body -= Pos(0, 0, flange_t) * counterbored_hole(SCREW, depth=flange_t)

    # Feature: cable-end notch through the flange rim, off the X and Y extremes so it can't shrink the bbox.
    notch_depth = 2 * notch_w
    notch = Pos(flange_r, 0, 0) * Box(2 * notch_depth, notch_w, 2 * flange_t, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    body -= Rot(0, 0, 90 * 0.5) * notch

    body.label = "spool"
    return body


def section_plane(**_):
    return {"axis": "X", "offset": 0}
