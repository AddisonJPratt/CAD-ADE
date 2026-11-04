"""Negative control: a mushroom whose flat ceiling the brief's literal metric cannot see."""
from build123d import Align, Box, Pos

PARAMS = {"stem": (10.0, 8.0, 12.0), "cap": (40.0, 30.0, 50.0)}


def build(stem, cap):
    align = (Align.CENTER, Align.CENTER, Align.MIN)
    return Box(stem, stem, cap, align=align) + Pos(0, 0, cap) * Box(cap, cap, stem, align=align)
