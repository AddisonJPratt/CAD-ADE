"""Feature fixture: fine knurl (mesh texture). A file handle: a straight knurl too fine for
B-rep (pitch under two perimeters) is applied to the exported STL; the STEP stays smooth.

Printed pommel-down: the pommel flange stops the hand sliding off the end and gives the
part its footprint. The tang bore is a press fit and the crown is rounded for the palm."""
from build123d import Align, Cylinder, Pos

from library import standard_parts
from library.engineering import edge_break
from library.textures import knurl

PARAMS = {
    # name: (default, min, max)    mm
    "radius": (11.0, 9.0, 14.0),     # grip radius
    "length": (60.0, 45.0, 80.0),    # grip length above the pommel
    "pommel": (3.0, 2.5, 4.0),       # pommel flange: radial lip past the grip, and its height
    "tang": (4.0, 3.0, 5.0),         # tang width the bore takes
    "pitch": (1.2, 1.0, 1.4),        # knurl pitch: below brep_min_pitch, so a mesh texture
    "depth": (0.25, 0.2, 0.28),      # knurl depth: <= the flank limit at the finest pitch
}


def build(radius, length, pommel, tang, pitch, depth):
    up = (Align.CENTER, Align.CENTER, Align.MIN)
    top = pommel + length
    handle = Cylinder(radius + pommel, pommel, align=up) + Cylinder(radius, top, align=up)
    # Feature: tang bore from the crown down, a press fit on the tang, half the grip deep.
    bore = tang / 2 + standard_parts()["fits"]["press"]
    handle -= Pos(0, 0, top) * Cylinder(bore, length / 2, align=(Align.CENTER, Align.CENTER, Align.MAX))
    # Feature: rounded crown edge for the palm, and a rounded pommel rim.
    handle = edge_break(handle, [(0, radius, top), (0, radius + pommel, pommel)], pommel / 2).shape
    # Feature: fine straight knurl along the grip, applied to the export mesh.
    handle = knurl(handle, (0, radius, pommel + length / 2), pitch, depth).shape
    handle.label = "handle"
    return handle
