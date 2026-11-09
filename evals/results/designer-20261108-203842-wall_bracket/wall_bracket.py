"""L-shaped shelf bracket, 2x M4 to the wall and 2x M4 up into the shelf. See briefs/wall_bracket.yaml.

Frame: Z is print-up. The shelf leg lies on the bed (z=0 is the shelf's underside face), the wall
face is x=0, the bracket is centred on Y. Printed shelf-face-down: the shelf counterbores open to the
bed and bridge 8 mm, the wall counterbores are horizontal teardrops so nothing needs support.
One L profile in XZ, extruded along Y, carries both legs and both corner fillets; a single rib on the
centreline joins the legs, so the screw heads at +/-spacing/2 stay open to a driver.
"""
from build123d import Axis, Compound, Plane, Polyline, Vector, extrude, fillet, make_face

from library import counterbored_hole, feature

SCREW = "M4"        # hardware choice, resolved through library/standard_parts.json

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "width": (60.0, 56.0, 100.0),              # bracket width along the wall (hard dimension)
    "shelf_depth": (80.0, 60.0, 120.0),        # shelf leg length from the wall face (hard dimension)
    "wall_height": (80.0, 60.0, 120.0),        # wall leg length from the shelf face (hard dimension)
    "thickness": (8.0, 7.0, 10.0),             # plate thickness; keeps a floor under the screw heads
    "wall_hole_spacing": (40.0, 24.0, 42.0),   # centre distance of wall screws, along Y (hard dimension)
    "shelf_hole_spacing": (40.0, 24.0, 42.0),  # centre distance of shelf screws, along Y (hard dimension)
    "inner_radius": (4.0, 3.0, 6.0),           # inside corner fillet, relieves the bending stress
    "outer_radius": (1.0, 0.5, 3.0),           # outside corner fillet, the L's heel on the bed
    "corner_radius": (4.0, 2.0, 8.0),          # plan radius at the four free plate corners
    "gusset_thickness": (5.0, 4.0, 8.0),       # central rib thickness along Y
    "gusset_reach": (0.7, 0.5, 0.85),          # rib length as a share of each free leg, ratio
    "gusset_edge_radius": (1.0, 0.5, 1.5),     # fillet on the rib's two ramp edges
}


def build(width, shelf_depth, wall_height, thickness, wall_hole_spacing, shelf_hole_spacing,
          inner_radius, outer_radius, corner_radius, gusset_thickness, gusset_reach, gusset_edge_radius):
    t = thickness
    half_w = width / 2

    # Feature: L profile in XZ (local x -> X, local y -> Z), filleted as a sketch, then extruded on Y.
    # The inner fillet spreads the bending stress at the knee; the outer one is the heel on the bed.
    sketch = make_face(Polyline((0, 0), (shelf_depth, 0), (shelf_depth, t), (t, t), (t, wall_height),
                                (0, wall_height), close=True))
    sketch = fillet([nearest_vertex(sketch, (t, t))], radius=inner_radius)
    sketch = fillet([nearest_vertex(sketch, (0, 0))], radius=outer_radius)
    plate = feature("L plate", extrude(Plane.XZ * sketch, amount=half_w, both=True),
                    params=("shelf_depth", "wall_height", "thickness"))

    # Feature: rounded free corners in plan, the ones a hand or the shelf's edge meets.
    shelf_corners = nearest_each(plate.edges().filter_by(Axis.Z),
                                 [(shelf_depth, sign * half_w, t / 2) for sign in (-1, 1)])
    wall_corners = nearest_each(plate.edges().filter_by(Axis.X),
                                [(t / 2, sign * half_w, wall_height) for sign in (-1, 1)])
    bracket = plate.fillet(corner_radius, shelf_corners + wall_corners)

    # Feature: centreline rib. Its heel starts half a plate inside both legs, so the union never meets
    # a leg face edge-on; the ramp runs from gusset_reach of one free leg to gusset_reach of the other.
    ramp_x = t + gusset_reach * (shelf_depth - t)
    ramp_z = t + gusset_reach * (wall_height - t)
    rib_sketch = make_face(Polyline((t / 2, t / 2), (ramp_x, t / 2), (ramp_x, t), (t, ramp_z),
                                    (t / 2, ramp_z), close=True))
    rib = extrude(Plane.XZ * rib_sketch, amount=gusset_thickness / 2, both=True)
    ramp_edges = nearest_each(rib.edges(), [((ramp_x + t) / 2, sign * gusset_thickness / 2, (t + ramp_z) / 2)
                                            for sign in (-1, 1)])
    rib = rib.fillet(gusset_edge_radius, ramp_edges)  # fillet before the boolean
    bracket += feature("gusset", rib, params=("gusset_thickness", "gusset_reach", "gusset_edge_radius"))

    # Feature: shelf screw holes, counterbored from below (the bed face), centred on the free shelf leg.
    shelf_x = (t + shelf_depth) / 2
    shelf_cutter = counterbored_hole(SCREW, depth=t)
    shelf_frames = [Plane(origin=(shelf_x, sign * shelf_hole_spacing / 2, 0), x_dir=(1, 0, 0), z_dir=(0, 0, -1))
                    for sign in (-1, 1)]
    bracket -= feature("shelf screw holes", Compound([f.location * shelf_cutter for f in shelf_frames]),
                       params="shelf_hole_spacing")

    # Feature: wall screw holes, counterbored from the room side, teardrop peak print-up (+Z) so the
    # horizontal bores print without support. Centred on the free wall leg.
    wall_z = (t + wall_height) / 2
    wall_cutter = counterbored_hole(SCREW, depth=t, teardrop=True)
    wall_frames = [Plane(origin=(t, sign * wall_hole_spacing / 2, wall_z), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
                   for sign in (-1, 1)]
    bracket -= feature("wall screw holes", Compound([f.location * wall_cutter for f in wall_frames]),
                       params="wall_hole_spacing")

    bracket.label = "wall_bracket"
    return bracket


def nearest_vertex(sketch, point):
    """Named-feature selection: the sketch vertex closest to an expected (x, y) point."""
    target = Vector(*point)
    return min(sketch.vertices(), key=lambda v: (Vector(v.X, v.Y, v.Z) - target).length)


def nearest_each(edges, points):
    """Named-feature selection: for each expected point, the edge whose centre is closest."""
    return [min(edges, key=lambda e: (e.center() - Vector(*p)).length) for p in points]


def section_plane(**_):
    return {"axis": "Y", "offset": 0}
