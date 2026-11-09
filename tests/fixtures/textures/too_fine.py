"""Negative control: a diamond knurl finer than a 0.4 mm nozzle can lay down, on the top of a
small plate. Its pitch range sits under the minimum feature, so Gate 3 must refuse it (a mesh
texture is applied at export, and its bounds are checked there). Nothing else is wrong with it."""
from build123d import Align, Box

from library.surface import mesh_texture, pick_face

PARAMS = {
    # name: (default, min, max)    mm
    "side": (20.0, 18.0, 22.0),        # plate side
    "thickness": (3.0, 2.4, 3.2),      # plate thickness
    "pitch": (0.8, 0.8, 1.0),          # diamond pitch: grooves 0.4 mm, one line, below the minimum
    "depth": (0.4, 0.4, 0.5),          # groove depth
}


def build(side, thickness, pitch, depth):
    plate = Box(side, side, thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
    plate.label = "plate"
    return mesh_texture(plate, pick_face(plate, facing="+Z"), "diamond", pitch=pitch, depth=depth)
