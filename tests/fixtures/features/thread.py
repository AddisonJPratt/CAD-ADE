"""Feature fixture: thread. A screw-top jar and its lid, each in print orientation.

The jar prints upright; the lid prints top-down. Both threads run print-up with the
library's self-supporting flank, and the lid is sized from the jar by the sliding fit.
"""
from build123d import Align, Axis, Cylinder, Pos

from library.engineering import mating_radius, shell, thread

EXPECTED_SOLIDS = 2

PARAMS = {
    # name: (default, min, max)    mm
    "radius": (40.0, 32.0, 50.0),     # jar outside radius, the thread root
    "height": (60.0, 45.0, 90.0),     # jar height
    "wall": (2.4, 2.0, 3.2),          # jar and lid wall
    "pitch": (4.0, 3.0, 5.0),         # thread pitch, jar-lid coarse
    "depth": (0.8, 0.8, 1.0),         # thread depth: shallow, like a moulded jar; <= the finest pitch / 3
    "turns": (1.5, 1.0, 2.0),         # turns of engagement; jar lids need little more than one
}


def build(radius, height, wall, pitch, depth, turns):
    engaged = turns * pitch
    jar = Cylinder(radius, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    jar = shell(jar, [jar.faces().sort_by(Axis.Z)[-1]], wall).shape
    # Feature: external thread near the rim, half a pitch below it.
    jar = thread(jar, (radius, 0, height - pitch), pitch, depth, length=engaged,
                 z_start=height - engaged - pitch / 2).shape

    bore = mating_radius(radius, depth, internal=False)
    skirt = engaged + pitch
    lid = Cylinder(bore + wall, wall + skirt, align=(Align.CENTER, Align.CENTER, Align.MIN))
    lid -= Pos(0, 0, wall) * Cylinder(bore, skirt, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # Feature: internal thread in the lid skirt.
    lid = thread(lid, (bore, 0, wall + skirt / 2), pitch, depth, length=engaged,
                 z_start=wall + pitch / 2).shape
    lid = Pos(radius + bore + 2 * wall + pitch, 0, 0) * lid
    jar.label, lid.label = "jar", "lid"
    return {"jar": jar, "lid": lid}


def section_plane(**_):
    return {"axis": "Y", "offset": 0}
