"""Negative control: two disjoint solids in one part, expected count is 1."""
from build123d import Align, Box, Pos

PARAMS = {"size": (20.0, 10.0, 30.0)}


def build(size):
    box = Box(size, size, size, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return box + Pos(size * 2, 0, 0) * box
