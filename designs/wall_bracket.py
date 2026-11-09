"""L wall bracket with central gusset. Modelled in print orientation; see briefs/wall_bracket.yaml.

Frame: Z is print-up, with the shelf-side face on the bed (z=0) and the wall-side face at x=0.
In service the part is flipped so z=0 is the top face carrying the shelf.
Design intent: hold a shelf with M4 screws, printable without supports.
"""
from build123d import Align, Axis, Box, Compound, Plane, Polygon, Pos, Vector, extrude

from library import counterbored_hole, feature, standard_parts

SCREW = "M4"            # hardware choice, resolved through library/standard_parts.json

PARAMS = {
    # name: (default, min, max)    all mm unless noted
    "width": (60.0, 56.0, 100.0),               # bracket width along Y (hard dimension)
    "shelf_depth": (80.0, 60.0, 120.0),         # shelf leg length from wall face, along X
    "wall_height": (80.0, 60.0, 120.0),         # wall leg length from shelf face, along Z
    "thickness": (8.0, 7.0, 10.0),              # plate thickness; leaves >=2.8 under the M4 head
    "wall_hole_spacing": (40.0, 24.0, 42.0),    # centre distance, wall screws
    "shelf_hole_spacing": (40.0, 24.0, 42.0),   # centre distance, shelf screws
    "inner_radius": (4.0, 3.0, 6.0),            # inside corner fillet, relieves bending stress
    "outer_radius": (1.0, 0.5, 3.0),            # outside corner fillet
    "corner_radius": (4.0, 2.0, 8.0),           # plan radius at the free plate corners
    "gusset_thickness": (5.0, 4.0, 8.0),        # central rib thickness along Y
    "gusset_reach": (0.7, 0.5, 0.85),           # ratio: rib length / free leg length
    "gusset_edge_radius": (1.0, 0.5, 1.5),      # fillet on the rib's ramp edges
}


def section_plane(wall_hole_spacing, **_):
    """QA section through one wall hole and one shelf hole (when the spacings match)."""
    return {"axis": "Y", "offset": wall_hole_spacing / 2}


def build(width, shelf_depth, wall_height, thickness, wall_hole_spacing, shelf_hole_spacing,
          inner_radius, outer_radius, corner_radius, gusset_thickness, gusset_reach,
          gusset_edge_radius):
    t = thickness

    # Feature: L plate, filleted before any boolean.
    profile = Plane.XZ * Polygon((0, 0), (shelf_depth, 0), (shelf_depth, t), (t, t),
                                 (t, wall_height), (0, wall_height), align=None)
    plate = extrude(profile, amount=width / 2, both=True)
    plate = plate.fillet(inner_radius, nearest(plate.edges().filter_by(Axis.Y), (t, 0, t)))
    plate = plate.fillet(outer_radius, nearest(plate.edges().filter_by(Axis.Y), (0, 0, 0)))
    free_corners = []
    for sign in (-1, 1):
        free_corners += nearest(plate.edges().filter_by(Axis.Z), (shelf_depth, sign * width / 2, t / 2))
        free_corners += nearest(plate.edges().filter_by(Axis.X), (t / 2, sign * width / 2, wall_height))
    plate = plate.fillet(corner_radius, free_corners)

    # Feature: central gusset; its overlap with the plate stays inside the legs.
    reach_x = t + gusset_reach * (shelf_depth - t)
    reach_z = t + gusset_reach * (wall_height - t)
    rib_profile = Plane.XZ * Polygon((t / 2, t / 2), (reach_x, t / 2), (reach_x, t), (t, reach_z),
                                     (t / 2, reach_z), align=None)
    rib = extrude(rib_profile, amount=gusset_thickness / 2, both=True)
    ramp_edges = []
    for sign in (-1, 1):
        ramp_edges += nearest(rib.edges(), ((reach_x + t) / 2, sign * gusset_thickness / 2, (t + reach_z) / 2))
    rib = rib.fillet(gusset_edge_radius, ramp_edges)
    bracket = plate + feature("gusset", rib, params=("gusset_reach", "gusset_thickness"))

    # Screw cutters, mouth at local z=0. The counterbore feature is each cutter trimmed to its
    # head, so the head's wall and floor are named apart from the bore; declared first, it wins.
    cb_depth = standard_parts()["screws"][SCREW]["counterbore_depth"]
    shelf_hole = counterbored_hole(SCREW, depth=t)
    wall_hole = counterbored_hole(SCREW, depth=t, teardrop=True)

    def head_of(cutter):
        box = cutter.bounding_box()   # off-centre in Y for a teardrop, whose peak must stay in
        return cutter & Pos(box.center().X, box.center().Y, -cb_depth) * Box(
            box.size.X, box.size.Y, cb_depth + t, align=(Align.CENTER, Align.CENTER, Align.MIN))

    # Feature: shelf screw holes, centred on the free shelf leg; mouth up, so no overhang.
    shelf_x = (t + inner_radius + shelf_depth) / 2
    shelf_at = [Pos(shelf_x, sign * shelf_hole_spacing / 2, t) for sign in (-1, 1)]
    # Feature: wall screw holes, centred on the free wall leg; teardrop peak is print-up.
    wall_z = (t + inner_radius + wall_height) / 2
    wall_at = [Plane(origin=(t, sign * wall_hole_spacing / 2, wall_z), x_dir=(0, 1, 0),
                     z_dir=(1, 0, 0)).location for sign in (-1, 1)]

    feature("counterbore", Compound([at * head_of(shelf_hole) for at in shelf_at]
                                    + [at * head_of(wall_hole) for at in wall_at]))
    bracket -= feature("shelf screw hole", Compound([at * shelf_hole for at in shelf_at]),
                       params="shelf_hole_spacing")
    bracket -= feature("wall screw hole", Compound([at * wall_hole for at in wall_at]),
                       params="wall_hole_spacing")

    bracket.label = "bracket"
    return bracket


def nearest(edges, point):
    """Named-feature selection: the one edge whose centre is closest to an expected point."""
    return [min(edges, key=lambda edge: (edge.center() - Vector(*point)).length)]
