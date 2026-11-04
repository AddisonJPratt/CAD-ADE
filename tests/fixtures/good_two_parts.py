"""Positive control: a two-part design with a clearance gap passes every gate."""
from build123d import Align, Box, Pos

EXPECTED_SOLIDS = 2
PARAMS = {"size": (20.0, 10.0, 30.0), "gap": (1.0, 0.5, 2.0)}


def build(size, gap):
    box = Box(size, size, size, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return {"a": box, "b": Pos(size + gap, 0, 0) * box}
