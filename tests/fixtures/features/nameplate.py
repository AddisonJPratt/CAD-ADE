"""Feature fixture: emboss_text + hex_texture. A desk nameplate: an upright panel on a foot,
the name engraved in its front face and a hex texture across its back. Both faces are walls,
so every letter and cell roof is tapered self-supporting; nothing needs support."""
from build123d import Align, Box

from library.engineering import edge_break
from library.textures import emboss_text, hex_texture

PARAMS = {
    # name: (default, min, max)    mm
    "width": (140.0, 110.0, 180.0),   # panel width
    "height": (45.0, 38.0, 60.0),     # panel height above the foot
    "thickness": (6.0, 5.0, 8.0),     # panel thickness
    "foot": (40.0, 32.0, 50.0),       # foot depth, front to back, for stability
    "letter": (18.0, 16.0, 24.0),     # cap height of the name
    "depth": (0.8, 0.6, 1.0),         # engraving and texture depth
    "cell": (7.0, 6.0, 9.0),          # hex cell across flats on the back
}

NAME = "MAGIC"


def build(width, height, thickness, foot, letter, depth, cell):
    up = (Align.CENTER, Align.CENTER, Align.MIN)
    base = Box(width, foot, thickness, align=up)
    panel = Box(width, thickness, height, align=up)
    plate = base + panel
    # Feature: soften the panel's top edges (fillets on upward-facing edges).
    plate = edge_break(plate, [(0, -thickness / 2, height), (0, thickness / 2, height)], thickness / 2 / 2).shape
    # Feature: engraved name, centred in the panel above the foot.
    mid = thickness + (height - thickness) / 2
    plate = emboss_text(plate, (0, -thickness / 2, mid), NAME, letter, depth, raised=False).shape
    # Feature: hex texture across the panel back.
    plate = hex_texture(plate, (0, thickness / 2, mid), cell, depth).shape
    plate.label = "nameplate"
    return plate
