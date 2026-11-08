"""A design whose feature tag names a parameter PARAMS does not declare: the harness must fail it."""
from build123d import Align, Box, Cylinder, Pos
from library import feature

PARAMS = {
    "size": (30.0, 24.0, 40.0),     # mm, block side, 24..40
    "height": (10.0, 8.0, 16.0),    # mm, block height, 8..16
    "hole_dia": (3.2, 3.0, 4.0),    # mm, boss bore, 3..4
}


def build(size, height, hole_dia):
    # Feature: the block, base on z=0
    block = Box(size, size, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # Feature: screw boss bore, tagged with a parameter name that was renamed away ("boss_d")
    bore = feature("screw boss", Pos(0, 0, 0) * Cylinder(hole_dia / 2, 2 * height), params=("boss_d",))
    block = block - bore
    block.label = "block"
    return block
