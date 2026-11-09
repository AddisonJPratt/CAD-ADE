"""Screw-down C clip for one round cable. See evals/briefs/cable_clip.yaml.

Frame: Z is print-up; the whole part is one XY profile extruded by clip_width, so the arms flex
in the layer plane and nothing overhangs. Ear on -X, cable centre at the origin, mouth on +X.
The brief's probe puts the M3 screw on Z, parallel to the cable, so the cable leaves the mounting
surface at a right angle (a drop from a desk underside), not along it. Flagged in the progress note.
"""
import math

from build123d import Align, Axis, Cylinder, Line, Pos, ThreePointArc, Vector, Wire, extrude, make_face

from library import counterbored_hole, feature, standard_parts

SCREW = "M3"            # brief: 1x M3 counterbored, resolved through library/standard_parts.json

PARAMS = {
    # name: (default, min, max)    all mm
    "clip_width": (12.0, 8.0, 20.0),     # print height of the clip (hard dimension)
    "cable_dia": (6.0, 3.0, 10.0),       # round cable diameter
    "arm_thickness": (1.6, 1.2, 2.4),    # flexing arm wall
}


def polar(radius, angle):
    return (radius * math.cos(angle), radius * math.sin(angle))


def c_outline(inner_r, outer_r, tip_angle):
    """C profile: arms sweep from the mouth at +/-tip_angle round through -X; tips fully rounded."""
    mid_r = (inner_r + outer_r) / 2
    tip_r = (outer_r - inner_r) / 2
    tip_out = (mid_r * math.cos(tip_angle) + tip_r * math.cos(tip_angle - math.pi * 0.5),
               mid_r * math.sin(tip_angle) + tip_r * math.sin(tip_angle - math.pi * 0.5))
    return Wire([
        ThreePointArc(polar(outer_r, tip_angle), (-outer_r, 0), polar(outer_r, -tip_angle)),
        ThreePointArc(polar(outer_r, -tip_angle), (tip_out[0], -tip_out[1]), polar(inner_r, -tip_angle)),
        ThreePointArc(polar(inner_r, -tip_angle), (-inner_r, 0), polar(inner_r, tip_angle)),
        ThreePointArc(polar(inner_r, tip_angle), tip_out, polar(outer_r, tip_angle)),
    ])


def build(clip_width, cable_dia, arm_thickness):
    screw = standard_parts()["screws"][SCREW]
    channel_r = cable_dia / 2 + standard_parts()["fits"]["sliding"]
    outer_r = channel_r + arm_thickness
    mid_r = channel_r + arm_thickness / 2

    # Feature: C arms. The mouth is 3/4 of the cable, so it retains by flexing each arm cable/8.
    mouth_half = cable_dia * 0.5 * (1 - 0.5 * 0.5)
    tip_angle = math.asin((mouth_half + arm_thickness / 2) / mid_r)
    arms = extrude(make_face(c_outline(channel_r, outer_r, tip_angle)), amount=clip_width)
    # Feature: cable channel, the bore the arms wrap; named, not cut, since the arms' profile makes it.
    feature("cable channel", Cylinder(channel_r, clip_width, align=(Align.CENTER, Align.CENTER, Align.MIN)),
            params="cable_dia")

    # Feature: screw ear on -X; round end concentric with the screw, walls sized by the head,
    # never narrower than the C, so each arm root ends on the ear's flat end face.
    ear_half = max(screw["counterbore_dia"] / 2 + arm_thickness, outer_r)
    hole_x = -(outer_r + screw["counterbore_dia"] / 2 + arm_thickness * 0.5)
    ear_face = make_face(Wire([
        Line((-mid_r, -ear_half), (hole_x, -ear_half)),
        ThreePointArc((hole_x, -ear_half), (hole_x - ear_half, 0), (hole_x, ear_half)),
        Line((hole_x, ear_half), (-mid_r, ear_half)),
        Line((-mid_r, ear_half), (-mid_r, -ear_half)),
    ]))
    ear = extrude(ear_face, amount=clip_width)
    clip = arms + ear

    # Feature: root fillets where each arm leaves the ear; the flex stress peaks exactly here.
    root_y = math.sqrt(outer_r ** 2 - mid_r ** 2)
    roots = [min(clip.edges().filter_by(Axis.Z),
                 key=lambda e: (e.center() - Vector(-mid_r, sign * root_y, clip_width / 2)).length)
             for sign in (-1, 1)]
    clip = clip.fillet(arm_thickness * 0.5 * 0.5, roots)

    # Feature: counterbored screw hole, mouth up, so the head sits below the top face.
    clip -= feature("screw hole", Pos(hole_x, 0, clip_width) * counterbored_hole(SCREW, depth=clip_width))

    clip.label = "clip"
    return clip


def section_plane(clip_width, **_):
    return {"axis": "Z", "offset": clip_width / 2}
