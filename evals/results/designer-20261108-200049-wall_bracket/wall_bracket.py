"""L-shaped shelf bracket with a centreline gusset, 2x M4 to the wall, 2x M4 to the shelf.
See briefs/wall_bracket.yaml.

Frame: Z is print-up. The shelf face lies on the bed (z=0), the wall face is x=0, the part is
centred on Y. In use the bracket is turned over: the shelf sits on z=0 and the wall is at x=0.
The L is one XZ profile (inner and outer corner fillets applied to the sketch, before any
boolean), extruded along Y. The gusset is a triangle on the centreline, its ramp edges filleted
before the union. Shelf screws are plain counterbores from z=thickness (below the shelf in use).
Wall screws are horizontal, so they are teardrop counterbores, peak print-up, from the room face
x=thickness; both legs keep a floor of thickness - counterbore_depth under the head.
"""
from build123d import Axis, Plane, Polygon, Polyline, Pos, Vector, extrude, fillet, make_face

from library import counterbored_hole, feature, standard_parts

SCREW = "M4"            # brief: 2x M4 + 2x M4 counterbored socket head, via library/standard_parts.json

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "width": (60.0, 56.0, 100.0),              # bracket width along the wall (hard dimension)
    "shelf_depth": (80.0, 60.0, 120.0),        # shelf leg length from the wall face (hard dimension)
    "wall_height": (80.0, 60.0, 120.0),        # wall leg length from the shelf face (hard dimension)
    "thickness": (8.0, 7.0, 10.0),             # plate thickness; keeps a floor under the screw heads
    "wall_hole_spacing": (40.0, 24.0, 42.0),   # centre distance of wall screws along Y (hard dimension)
    "shelf_hole_spacing": (40.0, 24.0, 42.0),  # centre distance of shelf screws along Y (hard dimension)
    "inner_radius": (4.0, 3.0, 6.0),           # inside corner fillet to relieve bending stress
    "outer_radius": (1.0, 0.5, 3.0),           # outside corner fillet
    "corner_radius": (4.0, 2.0, 8.0),          # plan radius at the free plate corners
    "gusset_thickness": (5.0, 4.0, 8.0),       # central rib thickness
    "gusset_reach": (0.7, 0.5, 0.85),          # ratio: rib length as a share of the free leg
    "gusset_edge_radius": (1.0, 0.5, 1.5),     # fillet on the rib ramp edges
}


def build(width, shelf_depth, wall_height, thickness, wall_hole_spacing, shelf_hole_spacing,
          inner_radius, outer_radius, corner_radius, gusset_thickness, gusset_reach,
          gusset_edge_radius):
    screw = standard_parts()["screws"][SCREW]
    t = thickness
    half_w = width / 2

    # Feature: L profile in XZ. Inner and outer corner fillets go on the sketch, before extrusion.
    profile = make_face(Polyline((0, 0), (shelf_depth, 0), (shelf_depth, t), (t, t),
                                 (t, wall_height), (0, wall_height), close=True))
    profile = fillet(nearest_each(profile.vertices(), [(t, t, 0)]), radius=inner_radius)
    profile = fillet(nearest_each(profile.vertices(), [(0, 0, 0)]), radius=outer_radius)
    bracket = extrude(Plane.XZ * profile, amount=half_w, both=True)

    # Feature: rounded free corners of both plates, the ones a hand or the shelf edge catches.
    shelf_corners = nearest_each(bracket.edges().filter_by(Axis.Z),
                                 [(shelf_depth, sign * half_w, t / 2) for sign in (-1, 1)])
    wall_corners = nearest_each(bracket.edges().filter_by(Axis.X),
                                [(t / 2, sign * half_w, wall_height) for sign in (-1, 1)])
    bracket = bracket.fillet(corner_radius, shelf_corners + wall_corners)

    # Feature: centreline gusset. Its hypotenuse meets each leg's inner face at gusset_reach of the
    # free leg and runs on to the leg's mid-plane, so the union never meets at a tangent. The ramp
    # faces up-and-out in print orientation, so it is self-supporting.
    reach_x = t + gusset_reach * (shelf_depth - t)
    reach_z = t + gusset_reach * (wall_height - t)
    a = t / 2
    foot_x = reach_x + (a - t) * (t - reach_x) / (reach_z - t)   # hypotenuse extended to z = a
    top_z = t + (a - reach_x) * (reach_z - t) / (t - reach_x)    # hypotenuse extended to x = a
    gusset = extrude(Plane.XZ * Polygon((a, a), (foot_x, a), (a, top_z), align=None),
                     amount=gusset_thickness / 2, both=True)
    ramp_mid = Vector((foot_x + a) / 2, 0, (a + top_z) / 2)
    ramp_edges = nearest_each(gusset.edges(),
                              [ramp_mid + Vector(0, sign * gusset_thickness / 2, 0) for sign in (-1, 1)])
    gusset = gusset.fillet(gusset_edge_radius, ramp_edges)
    bracket += feature("gusset", gusset, params=("gusset_thickness", "gusset_reach", "gusset_edge_radius"))

    # Feature: shelf screws, counterbored from the face away from the shelf (z = t), centred on
    # the free part of the shelf leg.
    shelf_x = t + (shelf_depth - t) / 2
    for sign, side in ((-1, "left"), (1, "right")):
        cutter = Pos(shelf_x, sign * shelf_hole_spacing / 2, t) * counterbored_hole(SCREW, depth=t)
        bracket -= feature(f"shelf screw {side}", cutter, params=("shelf_hole_spacing", "thickness"))

    # Feature: wall screws, horizontal teardrop counterbores from the room face (x = t), peak
    # print-up, centred on the free part of the wall leg.
    wall_z = t + (wall_height - t) / 2
    for sign, side in ((-1, "left"), (1, "right")):
        frame = Plane(origin=(t, sign * wall_hole_spacing / 2, wall_z), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
        cutter = frame.location * counterbored_hole(SCREW, depth=t, teardrop=True)
        bracket -= feature(f"wall screw {side}", cutter, params=("wall_hole_spacing", "thickness"))

    bracket.label = "wall_bracket"
    return bracket


def nearest_each(items, points):
    """Named-feature selection: for each expected point, the edge or vertex whose centre is closest."""
    return [min(items, key=lambda e: (e.center() - Vector(*p)).length) for p in points]


def section_plane(shelf_hole_spacing, **_):
    return {"axis": "Y", "offset": shelf_hole_spacing / 2}
