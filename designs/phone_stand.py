"""Desk phone stand with a slot gauge. See evals/briefs/phone_stand.yaml.

Frame: Z is print-up, base on z=0, front lip at x=0, rear at x=depth, centred on Y.
The rest's rear is a vertical wall, not a parallel leaning slab: a slab's back would face down
along its whole height and overhang, so the wedge between them stays solid (mass for stability).
The gap slot_gap is perpendicular to the rest, from the lip's top rear corner. No probe reads it
in the stand; see the brief's assumptions. The gauge nests in the rear cable channel to stay
inside the stand's bbox, because the brief's width and depth probes read both parts.
"""
import math

from build123d import Align, Axis, Box, Plane, Polygon, Pos, Vector, extrude

from library import feature, standard_parts

EXPECTED_SOLIDS = 2     # stand and slot gauge, as evals/briefs/phone_stand.yaml has it

PARAMS = {
    # name: (default, min, max)    all mm
    "width": (80.0, 60.0, 110.0),        # base width along Y (hard dimension)
    "depth": (90.0, 70.0, 120.0),        # base depth along X, sets tip resistance (hard dimension)
    "slot_gap": (9.0, 7.0, 16.0),        # phone-with-case thickness (hard dimension, on the gauge)
}


def build(width, depth, slot_gap):
    constants = standard_parts()["brief_constants"]["phone_stand"]
    tilt = math.radians(constants["tilt_deg"])
    cable_w = constants["cable_slot_width"]
    seat_z = slot_gap                    # seat height: also the tunnel height under the rest
    lip_h = slot_gap                     # retains the phone without hiding the screen's bottom edge
    lip_t = slot_gap * 0.5
    rest_top_t = slot_gap * 0.5
    deck_z = slot_gap * 0.5

    # Rest face, offset slot_gap perpendicular from the lip's top rear corner.
    rest_foot_x = lip_t + (slot_gap - lip_h * math.sin(tilt)) / math.cos(tilt)
    rest_top_x = rest_foot_x + depth * math.tan(tilt)
    rest_rear_x = rest_top_x + rest_top_t
    top_z = seat_z + depth

    # Feature: side profile of base, lip, seat, tilted rest and rear deck.
    profile = Plane.XZ * Polygon(
        (0, 0), (depth, 0), (depth, deck_z), (rest_rear_x, deck_z), (rest_rear_x, top_z),
        (rest_top_x, top_z), (rest_foot_x, seat_z), (lip_t, seat_z), (lip_t, seat_z + lip_h),
        (0, seat_z + lip_h), align=None)
    stand = extrude(profile, amount=width / 2, both=True)

    # Feature: rounded front edges where a hand or the phone meets the part.
    lip_edges = nearest_each(stand.edges().filter_by(Axis.Y), [(0, 0, seat_z + lip_h)])
    stand = stand.fillet(lip_t * 0.5, lip_edges)
    rest_edges = nearest_each(stand.edges().filter_by(Axis.Y), [(rest_top_x, 0, top_z)])
    stand = stand.fillet(rest_top_t * 0.5, rest_edges)
    # Feature: rounded rear plan corners, the ones a desk user catches.
    rear = nearest_each(stand.edges().filter_by(Axis.Z), [(depth, sign * width / 2, deck_z / 2) for sign in (-1, 1)])
    stand = stand.fillet(deck_z * 0.5, rear)

    # Feature: cable channel on the centreline, behind the lip. Open to the bed its whole run,
    # open above except for a short flat bridge under the rest.
    channel = Pos(lip_t, 0, 0) * Box(depth, cable_w, seat_z, align=(Align.MIN, Align.CENTER, Align.MIN))

    # Feature: slot gauge bar; its height is the gap, tried in the slot by hand. Nests in the channel.
    # Named before the channel, whose ceiling plane its top shares.
    side_gap = cable_w / 2 * 0.5
    gauge_len = depth - rest_rear_x - 2 * side_gap
    gauge = feature("slot gauge", Pos(rest_rear_x + side_gap, 0, 0) * Box(
        gauge_len, cable_w / 2, slot_gap, align=(Align.MIN, Align.CENTER, Align.MIN)), params="slot_gap")
    stand -= feature("cable channel", channel)

    stand.label, gauge.label = "stand", "slot_gauge"
    return {"stand": stand, "slot_gauge": gauge}


def nearest_each(edges, points):
    """Named-feature selection: for each expected point, the edge whose centre is closest."""
    return [min(edges, key=lambda e: (e.center() - Vector(*p)).length) for p in points]


def section_plane(**_):
    return {"axis": "Y", "offset": 0}
