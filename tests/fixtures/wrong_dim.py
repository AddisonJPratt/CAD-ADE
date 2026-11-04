"""Negative control: width is off by 0.5 mm against its brief."""
from build123d import Align, Box

PARAMS = {"width": (60.0, 50.0, 70.0)}


def build(width):
    return Box(width + 0.5, width, width, align=(Align.CENTER, Align.CENTER, Align.MIN))
