"""Assembly fixture: a lid with one counterbored M3 screw hole at its centre.

`clearance` is exposed only so negative fixtures can ask for a wrong hole; the default
is the M3 ISO 273 medium clearance from standard_parts.json.
"""
from build123d import Align, Box, Cylinder, Pos

from library import standard_parts

M3 = standard_parts()["screws"]["M3"]

PARAMS = {
    "size": (20.0, 16.0, 30.0),                               # mm, lid side
    "thickness": (4.0, 3.6, 6.0),                             # mm, must exceed the counterbore depth
    "clearance": (M3["clearance"], M3["tap"], M3["head_dia"]),  # mm, through-hole diameter
}


def build(size, thickness, clearance):
    lid = Box(size, size, thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # Counterbore from the top face; the screw head sits on its floor.
    counterbore = Pos(0, 0, thickness - M3["counterbore_depth"]) * Cylinder(
        M3["counterbore_dia"] / 2, thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
    shank = Pos(0, 0, -thickness) * Cylinder(clearance / 2, thickness * 2 * 2,
                                             align=(Align.CENTER, Align.CENTER, Align.MIN))
    lid = lid - counterbore - shank
    lid.label = "lid"
    return lid
