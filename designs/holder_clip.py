"""Wall clip for a cylindrical object, printed with the clip axis vertical.

The mounting face is at negative X, with screw holes normal to that face.
Fit, screw access and spring life require physical validation.
"""
import math

from build123d import Align, Box, Cylinder, Pos, Rot, extrude, make_face
from designs.cable_clip import c_outline
from library import standard_parts

PARAMS = {
    'barrel_dia': (38.0, 30.0, 50.0),
    'clearance': (0.25, 0.1, 0.7),
    'clip_height': (32.0, 28.0, 40.0),
    'wall': (2.4, 2.0, 3.0),
}


def build(barrel_dia, clearance, clip_height, wall):
    screw = standard_parts()['screws']['M3']
    inner = barrel_dia / 2 + clearance
    outer = inner + wall
    middle = inner + wall / 2
    mouth_half = (barrel_dia + 2 * clearance) * (1 - 0.5 * 0.5) / 2
    angle = math.asin((mouth_half + wall / 2) / middle)
    arms = extrude(make_face(c_outline(inner, outer, angle)), amount=clip_height)
    # Backplate meets the outside of the C along its root; the holes face the wall.
    plate = Pos(-outer - wall / 2, 0, 0) * Box(wall * 2, outer, clip_height,
                                                  align=(Align.CENTER, Align.CENTER, Align.MIN))
    holder = arms + plate
    hole_dia = screw['clearance']
    for z in (clip_height * 0.5 * 0.5, clip_height * (1 - 0.5 * 0.5)):
        hole = Pos(-outer, 0, z) * Rot(0, 90, 0) * Cylinder(hole_dia / 2, wall * 2 * 2,
                    align=(Align.CENTER, Align.CENTER, Align.CENTER))
        holder -= hole
        # Recess the screw head below the barrel bore, preserving clearance for the object.
        recess_depth = screw['counterbore_depth']
        recess = Pos(-inner - recess_depth / 2 + wall / 2, 0, z) * Rot(0, 90, 0) * Cylinder(
            screw['counterbore_dia'] / 2, recess_depth + wall,
            align=(Align.CENTER, Align.CENTER, Align.CENTER))
        holder -= recess
    holder.label = 'holder_clip'
    return holder
