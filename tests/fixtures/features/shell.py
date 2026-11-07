"""Feature fixture: shell. A desk tidy cup, hollowed from a solid with the top face open."""
from build123d import Align, Axis, Box

from library.engineering import edge_break, shell

PARAMS = {
    # name: (default, min, max)    mm
    "width": (70.0, 50.0, 110.0),     # outside width
    "depth": (52.0, 40.0, 90.0),      # outside depth
    "height": (95.0, 60.0, 130.0),    # outside height; pens stand above the rim
    "wall": (1.6, 1.2, 3.2),          # side and floor wall
    "corner_r": (9.0, 6.0, 14.0),     # plan corner radius
}


def build(width, depth, height, wall, corner_r):
    cup = Box(width, depth, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # Feature: plan corners first, so the shell keeps the wall even round them.
    cup = edge_break(cup, cup.edges().filter_by(Axis.Z), corner_r).shape
    # Feature: shell with the top open.
    cup = shell(cup, [cup.faces().sort_by(Axis.Z)[-1]], wall).shape
    cup.label = "tidy_cup"
    return cup
