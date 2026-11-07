"""Assembly fixture: a square base plate with one M3 heat-set insert boss at its centre."""
from build123d import Align, Box, Pos

from library import heatset_boss

PARAMS = {
    "size": (30.0, 24.0, 40.0),        # mm, plate side; room around the boss
    "thickness": (3.0, 2.4, 4.0),      # mm, plate thickness under the boss
}


def build(size, thickness):
    plate = Box(size, size, thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # Insert boss stands on the plate; its blind insert hole opens at the top.
    base = plate + Pos(0, 0, thickness) * heatset_boss("M3")
    base.label = "base"
    return base
