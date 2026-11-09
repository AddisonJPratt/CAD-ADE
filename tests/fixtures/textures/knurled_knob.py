"""Texture fixture: a thumb knob that drives an M4 bolt. An M4 nut presses into a hex pocket
open at the top (press fit on the flats, so it stays put unloaded), and the knob turns the thread
instead of spinning on it. A straight knurl (B-rep)
runs round the grip with its grooves vertical, so every flank prints without support, and ends on
a bearing flange whose bottom edge is broken against elephant's foot."""
from build123d import Align, Cone, Cylinder, Pos, RegularPolygon, extrude

from library import feature, standard_parts
from library.engineering import edge_break
from library.surface import knurl

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "grip_dia": (28.0, 22.0, 36.0),    # knurled grip: a thumb-and-finger knob for hand-tight M4
    "grip_h": (11.0, 8.0, 14.0),       # grip height above the flange: two finger pads
    "flange_lip": (2.0, 1.6, 3.0),     # flange reach past the grip root; carries the knurl's run-out
    "flange_h": (2.4, 1.6, 3.2),       # flange thickness; the knurl stops at its top face
    "knurl_pitch": (2.0, 1.6, 3.0),    # groove pitch round the grip
    "knurl_depth": (0.6, 0.4, 0.8),    # groove depth
}


def build(grip_dia, grip_h, flange_lip, flange_h, knurl_pitch, knurl_depth):
    nut = standard_parts()["nuts"]["M4"]
    screw = standard_parts()["screws"]["M4"]
    fit = standard_parts()["fits"]["press"]
    rules = standard_parts()["print_rules"]
    flange = Cylinder(grip_dia / 2 + flange_lip, flange_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    grip = Pos(0, 0, flange_h) * Cylinder(grip_dia / 2, grip_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    knob = flange + grip
    top = flange_h + grip_h
    # Feature: bolt clearance through the knob.
    knob = knob - feature("bolt bore", Cylinder(screw["clearance"] / 2, 2 * top))
    # Feature: hex nut pocket from the top, a press fit on the flats; vertical walls, no overhang.
    flats = nut["across_flats"] + 2 * fit
    pocket = Pos(0, 0, top - nut["thickness"] - fit) * extrude(
        RegularPolygon(flats / 2, nut["sides"], major_radius=False), amount=nut["thickness"] + fit + 1)
    knob = knob - feature("nut pocket", pocket)
    # Feature: straight knurl round the grip (the flange is the outer cylinder, so take the grip by radius).
    grip_face = max((f for f in knob.faces() if f.geom_type.name == "CYLINDER"
                     and abs(f.radius - grip_dia / 2) < knurl_depth), key=lambda f: f.area)
    knob = knurl(knob, grip_face, pitch=knurl_pitch, depth=knurl_depth, params=("knurl_pitch", "knurl_depth")).shape
    # Feature: top edge broken after the knurl by a cone cut one groove deep: it removes the
    # sharp groove tips and leaves only up-facing slopes, so no groove end becomes a ceiling.
    r = grip_dia / 2
    crown = Pos(0, 0, top - knurl_depth) * (
        Cylinder(r + knurl_depth, knurl_depth + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))
        - Cone(r, r - knurl_depth - 1, knurl_depth + 1, align=(Align.CENTER, Align.CENTER, Align.MIN)))
    knob = knob - feature("top edge break", crown, params="knurl_depth")
    # Feature: flange bottom edge broken one nozzle wide (a self-supporting chamfer on an underside edge).
    rim = (0, grip_dia / 2 + flange_lip, 0)   # off the +X seam line, on the bottom circle
    knob = edge_break(knob, [rim], rules["nozzle"]).shape
    knob.label = "knob"
    return knob
