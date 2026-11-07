"""Negative control: larger than the 256 mm build volume."""
from build123d import Align, Box

PARAMS = {"size": (300.0, 260.0, 340.0)}


def build(size):
    return Box(size, size, size, align=(Align.CENTER, Align.CENTER, Align.MIN))
