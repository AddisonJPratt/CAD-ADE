"""Negative control: two declared parts that interpenetrate."""
from build123d import Align, Box, Pos

EXPECTED_SOLIDS = 2
PARAMS = {"size": (20.0, 10.0, 30.0)}


def build(size):
    box = Box(size, size, size, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return {"a": box, "b": Pos(size / 2, 0, 0) * box}
