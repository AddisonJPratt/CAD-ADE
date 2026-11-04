"""Wedge doorstop, sawtooth grip ribs, cord hole. See briefs/doorstop.yaml.

Frame: Z is print-up. Printed on its side: X runs tip-to-heel along the floor, Y is the wedge's
height with the floor at y=0, Z is the width. Heel at x=0, thin tip at x=length. The whole part is
one XY profile extruded by the width, so no face points down except the bed face.
Vertical tooth faces look toward the heel: they bite when the door drives the wedge heelward.
"""
from build123d import Align, Cylinder, Polygon, Pos, extrude

PARAMS = {
    # name: (default, min, max)    all mm
    "length": (120.0, 90.0, 160.0),      # tip to heel along the floor (hard dimension)
    "wedge_height": (32.0, 25.0, 50.0),  # heel height above the rib tips (hard dimension)
    "width": (45.0, 30.0, 60.0),         # width across the door path, print height (hard dimension)
    "tip_t": (2.4, 1.6, 3.2),            # tip thickness, thin enough to slide under a door
    "rib_depth": (1.6, 0.8, 2.4),        # tooth height from valley to tip
    "rib_pitch": (6.0, 4.0, 9.0),        # tooth spacing along the floor
    "cord_dia": (6.0, 4.0, 8.0),         # cord hole diameter at the heel
}


def build(length, wedge_height, width, tip_t, rib_depth, rib_pitch, cord_dia):
    # Top slope: from the heel's top to the tip. Teeth stop where the slope leaves one rib depth of
    # solid above a valley, so the thin end stays one flat, unbroken tongue.
    slope = (wedge_height - tip_t) / length
    rib_end = length - (2 * rib_depth / slope if 2 * rib_depth / slope > 2 * rib_pitch else 2 * rib_pitch)

    # Feature: sawtooth underside, heel to rib_end. Each tooth ramps up from the heel side to a
    # vertical bite face looking heelward, so it drags going tipward and bites going heelward.
    under = [(rib_pitch * 0.5, 0)]        # heel keeps a half-pitch land of its own, not a thin first tooth
    x = rib_pitch * 0.5
    while x + rib_pitch <= rib_end:
        under += [(x + rib_pitch, rib_depth), (x + rib_pitch, 0)]
        x += rib_pitch

    # Feature: flat tongue under the thin tip, on the floor plane, ending in the tip's blunt face.
    outline = [(0, 0)] + under + [(length, 0), (length, tip_t), (0, wedge_height)]
    wedge = extrude(Polygon(*outline, align=None), amount=width)

    # Feature: cord hole through the heel, centred in the heel's solid height.
    hole_x = wedge_height * 0.5
    hole_y = (wedge_height - hole_x * slope) * 0.5
    wedge -= Pos(hole_x, hole_y, 0) * Cylinder(cord_dia / 2, width, align=(Align.CENTER, Align.CENTER, Align.MIN))

    wedge.label = "doorstop"
    return wedge


def section_plane(width, **_):
    return {"axis": "Z", "offset": width / 2}
