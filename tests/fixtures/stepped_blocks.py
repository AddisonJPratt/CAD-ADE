"""Two stacked blocks for Studio's measure tool: a riser standing on a wider base.

The riser's height is a hard dimension the geometry gate measures (bbox_z of the riser part),
and it is also the gap between two faces Studio can pick from above: the riser's top and the
base's top ledge around it. Studio's reading must agree with the gate's within 0.1 mm.
"""
from build123d import Align, Box, Pos

EXPECTED_SOLIDS = 2
PARAMS = {
    "base_side": (40.0, 30.0, 50.0),     # mm, base footprint side, 30..50
    "base_height": (8.0, 5.0, 12.0),     # mm, base thickness, 5..12
    "riser_side": (22.0, 15.0, 25.0),    # mm, riser footprint side, kept inside the base, 15..25
    "riser_height": (13.5, 10.0, 20.0),  # mm, riser height above the ledge, 10..20
}


def build(base_side, base_height, riser_side, riser_height):
    # Feature: the base, footprint centred on the origin, bottom on z=0
    base = Box(base_side, base_side, base_height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # Feature: the riser, standing on the base's top face so the two touch without overlapping
    riser = Pos(0, 0, base_height) * Box(riser_side, riser_side, riser_height,
                                          align=(Align.CENTER, Align.CENTER, Align.MIN))
    return {"base": base, "riser": riser}
