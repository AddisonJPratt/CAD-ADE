"""Feature fixture: edge_break. A pilot-drill guide block for M4 screws.

Three breaks, three sizes, each for a reason: generous plan corners for the hand,
a small top break so the drill finds the bore, and a print-safe chamfer on the foot
(edge_break turns underside fillets into self-supporting chamfers on its own).
"""
from build123d import Align, Axis, Box, Cylinder

from library import standard_parts
from library.engineering import edge_break

SCREW = "M4"   # the guide bore is this screw's tap drill plus a sliding fit

PARAMS = {
    # name: (default, min, max)    mm
    "length": (36.0, 24.0, 60.0),     # block length, a comfortable pinch grip
    "width": (22.0, 16.0, 40.0),      # block width
    "height": (18.0, 12.0, 30.0),     # guide length; longer keeps the drill square
    "corner_r": (5.0, 3.0, 7.5),      # plan corner radius, for the hand
    "top_r": (1.2, 0.6, 2.0),         # top edge break, a lead-in for the drill
    "foot": (0.5, 0.4, 0.8),          # foot chamfer, about a nozzle: against first-layer flare, and small
                                      # enough that its 46 deg faces stay a minor share of downward area
}


def build(length, width, height, corner_r, top_r, foot):
    screw = standard_parts()["screws"][SCREW]
    bore = screw["tap"] + 2 * standard_parts()["fits"]["sliding"]
    block = Box(length, width, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    block -= Cylinder(bore / 2, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # Feature: plan corners.
    block = edge_break(block, block.edges().filter_by(Axis.Z).group_by(Axis.X)[0]
                       + block.edges().filter_by(Axis.Z).group_by(Axis.X)[-1], corner_r).shape
    # Feature: top lead-in, outer outline and bore mouth.
    top = block.faces().sort_by(Axis.Z)[-1]
    block = edge_break(block, top.edges(), top_r).shape
    # Feature: foot chamfer on the outer outline only, so the bore exit stays sharp.
    bottom = block.faces().sort_by(Axis.Z)[0]
    block = edge_break(block, bottom.outer_wire().edges(), foot).shape
    block.label = "drill_guide"
    return block
