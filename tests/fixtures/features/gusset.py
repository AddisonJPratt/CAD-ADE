"""Feature fixture: gusset. A shelf bracket: base on the bed, upright wall, gussets in the corner.

Prints on its base; the gussets' sloped faces look up, so none needs support.
Screw holes in the base are counterbored from the top for the library's M4.
"""
from build123d import Align, Box, Pos

from library import counterbored_hole
from library.engineering import gusset

SCREW = "M4"

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "width": (60.0, 40.0, 100.0),       # bracket width along the shelf edge
    "reach": (70.0, 50.0, 110.0),       # base depth, the shelf it carries
    "rise": (55.0, 40.0, 90.0),         # upright height on the wall
    "thickness": (6.0, 5.0, 9.0),       # base and upright thickness
    "leg": (32.0, 20.0, 45.0),          # gusset leg along each face
    "gusset_t": (4.0, 3.0, 6.0),        # gusset thickness
    "gussets": (2, 1, 3),               # gusset count
}


def build(width, reach, rise, thickness, leg, gusset_t, gussets):
    base = Box(width, reach, thickness, align=(Align.CENTER, Align.MIN, Align.MIN))
    upright = Box(width, thickness, rise, align=(Align.CENTER, Align.MIN, Align.MIN))
    bracket = base + upright
    # Feature: gussets along the inside corner, where base meets upright.
    bracket = gusset(bracket, (0, thickness, thickness), leg, gusset_t, count=gussets).shape
    # Feature: two counterbored screw holes through the base, outboard of the gussets' reach.
    hole = counterbored_hole(SCREW, depth=thickness)
    for x in (-width / 2 / 2, width / 2 / 2):
        bracket -= Pos(x, (thickness + leg + reach) / 2, thickness) * hole
    bracket.label = "shelf_bracket"
    return bracket
