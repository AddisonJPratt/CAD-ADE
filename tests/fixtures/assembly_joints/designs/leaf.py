"""Joint fixture: a flat hinge leaf, printed flat."""
from build123d import Align, Box

PARAMS = {
    "length": (30.0, 15.0, 80.0),     # mm, X
    "width": (10.0, 8.0, 12.0),       # mm, Y; at most twice the leaf's distance from the hinge axis, so it swings ±90 deg clear
    "thickness": (4.0, 2.0, 8.0),     # mm, Z
}


def build(length, width, thickness):
    part = Box(length, width, thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
    part.label = "leaf"
    return part
