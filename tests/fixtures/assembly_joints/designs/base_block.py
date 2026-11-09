"""Joint fixture: an open box whose rim is wide enough to take a joint socket with a wall each side."""
from build123d import Align, Box, Pos

PARAMS = {
    "width": (60.0, 40.0, 120.0),    # mm, X
    "depth": (40.0, 30.0, 120.0),    # mm, Y
    "height": (20.0, 14.0, 60.0),    # mm, Z; a snap socket needs ~9 mm of rim behind it
    "rim": (10.0, 9.0, 12.0),        # mm, wall; a snap socket is 6.7 mm across plus a wall each side
    "floor": (3.0, 2.0, 6.0),        # mm
}


def build(width, depth, height, rim, floor):
    body = Box(width, depth, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    pocket = Pos(0, 0, floor) * Box(width - 2 * rim, depth - 2 * rim, height,
                                    align=(Align.CENTER, Align.CENTER, Align.MIN))
    part = body - pocket
    part.label = "base block"
    return part
