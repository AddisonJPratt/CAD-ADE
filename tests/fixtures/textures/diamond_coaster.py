"""Texture fixture: a square coaster with a fine diamond knurl on top, inside a smooth border so
condensation does not run off the edges through open grooves. Sized for a mug foot up to about
85 mm. At this pitch the diamond has more cells than are kept as B-rep, so texture() routes it to
the exported mesh (watertight); the STEP stays smooth. Up-facing grooves add no downward faces."""
from build123d import Align, RectangleRounded, extrude

from library import standard_parts
from library.engineering import edge_break
from library.surface import pick_face, texture

PARAMS = {
    # name: (default, min, max)    mm
    "mug_foot": (85.0, 70.0, 95.0),    # largest mug foot it takes; the textured field is this square
    "border": (4.0, 3.0, 6.0),         # smooth band round the field: a dry edge to lift it by
    "thickness": (4.0, 3.2, 5.0),      # coaster thickness: stiff enough not to rock on a grain-raised table
    "pitch": (2.4, 2.0, 2.8),          # diamond pitch: grooves of half this
    "depth": (0.5, 0.4, 0.8),          # groove depth: 2-4 layers, enough to grip a wet mug foot
}


def build(mug_foot, border, thickness, pitch, depth):
    side = mug_foot + 2 * border
    # Feature: the slab, corners rounded by the border so the field's corners stay square inside it.
    coaster = extrude(RectangleRounded(side, side, border), amount=thickness)
    # Feature: bottom edge broken one nozzle wide against elephant's foot (self-supporting chamfer).
    coaster = edge_break(coaster, [(0, side / 2, 0)], standard_parts()["print_rules"]["nozzle"]).shape
    coaster.label = "coaster"
    return texture(coaster, pick_face(coaster, facing="+Z"), "diamond", pitch=pitch, depth=depth, border=border).shape
