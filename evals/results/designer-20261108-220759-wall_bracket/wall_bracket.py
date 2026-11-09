"""L-shaped shelf bracket, 2x M4 to the wall and 2x M4 up into the shelf. See briefs/wall_bracket.yaml.

Frame: Z is print-up. The shelf face is z=0 (on the bed), the wall face is x=0, the part is
centred on y=0 and the width runs along Y. The shelf leg reaches +X, the wall leg +Z.

Printed shelf-face-down, as the brief assumes. The wall screws are therefore horizontal, so their
counterbores are teardrops (44 deg peak print-up) and need no support. The shelf screws enter
from the bed face: their counterbore floors are the one flat ceiling, a 1.75 mm wide ring bridged
over an 8 mm bore, which any slicer bridges; the brief sizes the thickness around exactly this
(4.2 deep counterbore plus a floor). The L's outer corner sits on the bed, so a fillet there
would curl into an unsupported ceiling; following library/engineering.edge_break it is cut as a
chamfer at the self-supporting slope with outer_radius as its horizontal leg. The free edges a
hand meets reaching under the shelf are filleted; the inside corner carries the bending stress and
gets inner_radius, blended into the profile before any 3D boolean.

The gusset is one rib on the centreline, so it never sits in front of a screw head. Its base is
sunk half a plate into both legs (no coplanar union faces) and its ramp edges are filleted before
the union. Load path: shelf load -> rib ramp -> wall leg -> upper wall screw pair in tension.
"""
import math

from build123d import Align, Axis, GeomType, Plane, Polyline, Pos, Vector, extrude, fillet, make_face

from library import counterbored_hole, feature, standard_parts

SCREW = "M4"            # brief: 2x M4 + 2x M4 counterbored socket heads, via library/standard_parts.json

PARAMS = {
    # name: (default, min, max)
    "width": (60.0, 56.0, 100.0),               # mm; bracket width along the wall (hard dimension)
    "shelf_depth": (80.0, 60.0, 120.0),         # mm; shelf leg length from the wall face (hard dimension)
    "wall_height": (80.0, 60.0, 120.0),         # mm; wall leg length from the shelf face (hard dimension)
    "thickness": (8.0, 7.0, 10.0),              # mm; plate thickness, keeps a floor under the screw heads
    "wall_hole_spacing": (40.0, 24.0, 42.0),    # mm; centre distance of the wall screws (hard dimension)
    "shelf_hole_spacing": (40.0, 24.0, 42.0),   # mm; centre distance of the shelf screws (hard dimension)
    "inner_radius": (4.0, 3.0, 6.0),            # mm; inside corner fillet, relieves the bending stress
    "outer_radius": (1.0, 0.5, 3.0),            # mm; outside corner break: chamfer leg on the bed edge, fillet on hand edges
    "corner_radius": (4.0, 2.0, 8.0),           # mm; plan radius at the free plate corners
    "gusset_thickness": (5.0, 4.0, 8.0),        # mm; central rib thickness
    "gusset_reach": (0.7, 0.5, 0.85),           # ratio; rib length as a share of each free leg
    "gusset_edge_radius": (1.0, 0.5, 1.5),      # mm; fillet on the rib ramp edges
}


def rules():
    return standard_parts()["print_rules"]


def slope_rad():
    """Self-supporting slope from vertical (44 deg: one degree inside the overhang gate)."""
    return math.radians(rules()["self_supporting_deg"])


def snap_tol():
    """Position tolerance for edge selection: half a nozzle, far below any feature size."""
    return rules()["nozzle"] / 2


def nearest(edges, point):
    """Named-feature selection: the edge whose centre is closest to an expected point."""
    return min(edges, key=lambda e: (e.center() - Vector(*point)).length)


def is_smooth(shape, edge):
    """True where the two faces meeting at `edge` are tangent (a fillet's own boundary); never fillet those."""
    faces = [f for f in shape.faces() if any(edge.is_same(e) for e in f.edges())]
    if len(faces) != 2:
        return True
    point = edge.position_at(0.5)
    return faces[0].normal_at(point).dot(faces[1].normal_at(point)) > math.cos(math.radians(1))


def l_profile(shelf_depth, wall_height, thickness, inner_radius, outer_radius):
    """XZ section of the L: inside fillet, and a self-supporting chamfer where the outer corner meets the bed."""
    leg_x = outer_radius                               # horizontal leg: the break reads outer_radius from the room
    leg_z = outer_radius / math.tan(slope_rad())       # vertical leg: the chamfer face at the self-supporting slope
    outline = Polyline((leg_x, 0), (shelf_depth, 0), (shelf_depth, thickness), (thickness, thickness),
                       (thickness, wall_height), (0, wall_height), (0, leg_z), close=True)
    face = make_face(outline)
    inner = [v for v in face.vertices()
             if abs(v.X - thickness) < snap_tol() and abs(v.Y - thickness) < snap_tol()]
    return fillet(inner, radius=inner_radius), leg_x


def build(width, shelf_depth, wall_height, thickness, wall_hole_spacing, shelf_hole_spacing,
          inner_radius, outer_radius, corner_radius, gusset_thickness, gusset_reach, gusset_edge_radius):
    screw = standard_parts()["screws"][SCREW]
    t = thickness

    # Feature: the L body, one XZ profile extruded across the width.
    profile, leg_x = l_profile(shelf_depth, wall_height, t, inner_radius, outer_radius)
    bracket = extrude(Plane.XZ * profile, amount=width / 2, both=True)

    # Feature: plan radius at the four free plate corners (shelf front corners, wall top corners).
    z_edges, x_edges = bracket.edges().filter_by(Axis.Z), bracket.edges().filter_by(Axis.X)
    corners = ([nearest(z_edges, (shelf_depth, side * width / 2, t / 2)) for side in (-1, 1)]
               + [nearest(x_edges, (t / 2, side * width / 2, wall_height)) for side in (-1, 1)])
    bracket = bracket.fillet(corner_radius, corners)

    # Feature: hand-edge break on the room-side convex edges: shelf top perimeter, room face perimeter
    # and the inside-corner side arcs, which the plan arcs join into one tangent chain. Bed edges stay
    # sharp for first-layer contact and the wall face (x=0) stays sharp so it sits flat on the wall. The
    # fillet is capped at half the plan radius so it never rolls round an arc tighter than itself.
    hand_break = min(outer_radius, corner_radius / 2)
    hand_edges = [e for e in bracket.edges()
                  if e.bounding_box().min.Z > snap_tol()                 # off the bed
                  and e.bounding_box().max.X > leg_x + snap_tol()        # off the wall face and chamfer
                  and not is_smooth(bracket, e)]
    bracket = bracket.fillet(hand_break, hand_edges)

    # Feature: centreline gusset. Ramp from (reach along the shelf) to (reach up the wall); its base is
    # sunk half a plate into both legs so the union never meets face-on-face. Ramp edges filleted first.
    sink = t / 2
    reach_x, reach_z = gusset_reach * (shelf_depth - t), gusset_reach * (wall_height - t)
    rib_face = make_face(Polyline((t - sink, t - sink), (t + reach_x, t - sink), (t + reach_x, t),
                                  (t, t + reach_z), (t - sink, t + reach_z), close=True))
    rib = extrude(Plane.XZ * rib_face, amount=gusset_thickness / 2, both=True)
    ramp_edges = [e for e in rib.edges().filter_by(GeomType.LINE)
                  if abs(e.length - math.hypot(reach_x, reach_z)) < snap_tol()]
    rib = rib.fillet(gusset_edge_radius, ramp_edges)
    bracket += feature("gusset", rib, params=("gusset_reach", "gusset_thickness", "gusset_edge_radius"))

    # Feature: wall screw holes, axis X, counterbored from the room face x=t; teardrop peak print-up
    # (cutter local +Y -> world +Z) so the horizontal bores print without support. Centred on the free wall leg.
    wall_z = t + (wall_height - t) / 2
    wall_cutter = counterbored_hole(SCREW, depth=t, teardrop=True)
    for side in (-1, 1):
        frame = Plane(origin=(t, side * wall_hole_spacing / 2, wall_z), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
        bracket -= feature("wall screw hole", frame.location * wall_cutter, params="wall_hole_spacing")

    # Feature: shelf screw holes, axis Z, counterbored from the bed face z=0 (the screw goes up into the
    # shelf; the head sits below the plate). Centred on the free shelf leg.
    shelf_x = t + (shelf_depth - t) / 2
    shelf_cutter = counterbored_hole(SCREW, depth=t)
    for side in (-1, 1):
        frame = Plane(origin=(shelf_x, side * shelf_hole_spacing / 2, 0), x_dir=(1, 0, 0), z_dir=(0, 0, -1))
        bracket -= feature("shelf screw hole", frame.location * shelf_cutter, params="shelf_hole_spacing")

    bracket.label = "wall_bracket"
    return bracket


def section_plane(**_):
    """Section on the centreline, through the gusset and the L profile."""
    return {"axis": "Y", "offset": 0}
