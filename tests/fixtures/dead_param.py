"""Negative control: `extra` changes nothing, so the sweep must flag it as dead."""
from build123d import Align, Box

PARAMS = {"size": (20.0, 10.0, 30.0), "extra": (5.0, 1.0, 9.0)}


def build(size, extra):
    return Box(size, size, size, align=(Align.CENTER, Align.CENTER, Align.MIN))
