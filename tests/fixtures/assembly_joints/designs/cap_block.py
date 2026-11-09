"""Joint fixture: a cap printed top-down, so its inner face is on top as it prints."""
from build123d import Align, Box

PARAMS = {
    "width": (60.0, 40.0, 120.0),     # mm, X; matches the base
    "depth": (40.0, 30.0, 120.0),     # mm, Y
    "thickness": (6.0, 3.0, 20.0),    # mm, Z
}


def build(width, depth, thickness):
    part = Box(width, depth, thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
    part.label = "cap block"
    return part
