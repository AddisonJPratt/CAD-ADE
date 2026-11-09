"""Feature fixture: pattern. A wall-hung tool plate: a grid of pegs stands on its face, and a
row of screw clearance holes is cut through its top band. Printed lying flat, pegs up.

The plate is sized from the patterns (count x spacing + border), so every count and spacing
in range fits; the pegs' web and the slot spacing are checked by the pattern helper."""
from build123d import Align, Box, Cylinder

from library import standard_parts
from library.engineering import edge_break
from library.textures import grid_pattern, linear_pattern, pattern

PARAMS = {
    # name: (default, min, max)    mm / count
    "pegs_u": (4, 2, 6),              # peg columns
    "pegs_v": (3, 2, 4),              # peg rows
    "spacing": (16.0, 12.0, 22.0),    # peg pitch, both directions
    "peg_radius": (2.5, 2.0, 4.0),    # peg radius; web to the next peg is spacing - 2r
    "peg_height": (12.0, 8.0, 20.0),  # peg length off the plate
    "thickness": (4.0, 3.0, 6.0),     # plate thickness
    "screws": (2, 2, 4),              # hanging screw holes along the top band
}


def build(pegs_u, pegs_v, spacing, peg_radius, peg_height, thickness, screws):
    up = (Align.CENTER, Align.CENTER, Align.MIN)
    screw = standard_parts()["screws"]["M4"]
    border = spacing / 2
    band = screw["head_dia"] * 2          # top band that carries the screw holes
    width = pegs_u * spacing + 2 * border
    depth = pegs_v * spacing + band + 2 * border
    plate = Box(width, depth, thickness, align=up)
    # Feature: peg grid, offset down to leave the screw band clear.
    pegs = grid_pattern(pegs_u, pegs_v, spacing, spacing)
    pegs = [(u, v - band / 2) for u, v in pegs]
    peg = Cylinder(peg_radius, peg_height, align=up)
    plate = pattern(plate, (0, 0, thickness), peg, pegs).shape
    # Feature: screw clearance holes along the top band, spread over the plate width.
    holes = [(u, depth / 2 - border - band / 2) for u, _ in linear_pattern(screws, (width - 2 * border) / screws)]
    bore = Cylinder(screw["clearance"] / 2, thickness * 2, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    plate = pattern(plate, (0, 0, thickness), bore, holes, cut=True).shape
    # Feature: round the peg tips so tools slide on.
    tips = [(u, v, thickness + peg_height) for u, v in pegs]
    plate = edge_break(plate, [(u + peg_radius, v, z) for u, v, z in tips], peg_radius / 2).shape
    plate.label = "tool_plate"
    return plate
