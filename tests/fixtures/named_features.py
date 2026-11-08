"""A plate with two named features, for the face map Studio reads when a face is picked.

The lid pocket is cut into the top and the mount hole runs vertically through the plate,
so every face the two cutters leave behind is named; the plate's own faces are not.
"""
from build123d import Align, Box, Cylinder, Pos
from library import feature

PARAMS = {
    "size": (36.0, 32.0, 40.0),        # mm, plate side; square in plan, 32..40
    "height": (12.0, 8.0, 20.0),       # mm, plate thickness, 8..20
    "pocket_depth": (3.0, 1.0, 5.0),   # mm, how deep the lid sits in the top, 1..5
    "hole_dia": (4.0, 3.0, 4.0),       # mm, mount hole diameter, 3..4
}


def build(size, height, pocket_depth, hole_dia):
    # Feature: the plate, base on z=0
    plate = Box(size, size, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # Feature: lid pocket, a square recess half the plate's width, centred on the top face
    pocket = feature("lid pocket", Pos(0, 0, height) * Box(size / 2, size / 2, 2 * pocket_depth),
                     params=("pocket_depth",))
    # Feature: mount hole, vertical through-hole in one corner, one diameter clear of the pocket
    at = size / 2 / 2 + hole_dia
    hole = feature("mount hole", Pos(at, at, 0) * Cylinder(hole_dia / 2, 2 * height), params=("hole_dia",))
    plate = plate - pocket - hole
    plate.label = "plate"
    return plate
