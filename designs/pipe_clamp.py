"""Wall clamp for a round pipe, compliant strap, cross bolt. See briefs/pipe_clamp.yaml.

Frame: Z is print-up and along the pipe. Wall face is y=0, room side is +Y, pipe axis on x=0.
One XY profile extruded by strap_width, so the strap flexes in the layer plane. Wall screws are
horizontal teardrop bores, peak print-up, and the cross bolt a round one. Neither is counterbored:
the first version had counterbores and failed the overhang gate at 21.6 %.
"""
import math

from build123d import Align, Axis, Box, Compound, Cylinder, Plane, Polygon, Pos, Vector, extrude

from library import feature, standard_parts
from library.features import TEARDROP_FLANK_DEG

WALL_SCREW = "M4"       # hardware choice, resolved through library/standard_parts.json
BOLT = "M3"

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "pipe_dia": (32.0, 20.0, 40.0),         # pipe outside diameter
    "strap_width": (18.0, 14.0, 30.0),      # clamp width along the pipe, print height (hard dimension)
    "strap_t": (2.0, 1.6, 2.8),             # compliant strap thickness
    "base_t": (7.0, 6.0, 10.0),             # plate thickness; also the saddle floor under the pipe
    "hole_spacing": (70.0, 60.0, 90.0),     # wall screw spacing; minimum clears the largest strap (hard dimension)
    "mouth_ratio": (0.85, 0.75, 0.9),      # mouth gap / pipe diameter, ratio
}


def prism(x0, x1, y0, y1, height):
    """Rectangular prism from corner ranges, base on z=0."""
    return Pos(x0, y0, 0) * Box(x1 - x0, y1 - y0, height, align=(Align.MIN, Align.MIN, Align.MIN))


def teardrop_bore(radius, length):
    """Cutter along local Z, overshooting both ends by 1; 44 deg peak toward local +Y."""
    flank = math.radians(TEARDROP_FLANK_DEG)
    apex_y = radius / math.sin(flank)
    tx, ty = radius * math.cos(flank), radius * math.sin(flank)
    round_part = Cylinder(radius, length + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    peak = extrude(Polygon((-tx, ty), (tx, ty), (0, apex_y), align=None), amount=length + 2)
    return Pos(0, 0, -length - 1) * (round_part + peak)


def build(pipe_dia, strap_width, strap_t, base_t, hole_spacing, mouth_ratio):
    parts = standard_parts()
    wall_screw, bolt = parts["screws"][WALL_SCREW], parts["screws"][BOLT]
    bore_r = pipe_dia / 2 + parts["fits"]["sliding"]
    outer_r = bore_r + strap_t
    mid_r = bore_r + strap_t / 2
    centre_y = base_t + bore_r           # the plate is the saddle's floor under the pipe
    mid_z = strap_width / 2

    # Feature: wall plate, ending one strap thickness past the screw heads.
    plate_x = hole_spacing / 2 + wall_screw["head_dia"] / 2 + strap_t
    plate = prism(-plate_x, plate_x, 0, base_t, strap_width)
    # Feature: saddle with slanted gussets, stopping short of the screw heads so a driver reaches them.
    # Its top ends inside the strap, so the two cross cleanly and never meet at a tangent.
    gusset_x = hole_spacing / 2 - wall_screw["head_dia"] / 2 - strap_t
    # Landing 45 deg below the pipe centre leaves the strap about 25 mm of free arc to bend over.
    land_x = mid_r * math.cos(math.radians(90 * 0.5))
    land_y = centre_y - land_x
    saddle = extrude(Polygon((-gusset_x, 0), (gusset_x, 0), (gusset_x, base_t), (land_x, land_y),
                             (-land_x, land_y), (-gusset_x, base_t), align=None), amount=strap_width)
    # Feature: strap ring, cut below to the bore and above to the mouth.
    ring = Pos(0, centre_y, 0) * Cylinder(outer_r, strap_width, align=(Align.CENTER, Align.CENTER, Align.MIN))
    clamp = plate + saddle + ring

    # Feature: fillets where the strap leaves the gussets; the flex stress peaks exactly here.
    root_x, root_y = line_circle(gusset_x, base_t, land_x, land_y, centre_y, outer_r)
    roots = [nearest(clamp, Vector(sign * root_x, root_y, mid_z)) for sign in (-1, 1)]
    clamp = clamp.fillet(strap_t * 0.5, roots)
    # Feature: rounded plate corners, the ones a hand catches.
    corners = [nearest(clamp, Vector(sx * plate_x, y, mid_z)) for sx in (-1, 1) for y in (0, base_t)]
    clamp = clamp.fillet(base_t * 0.5 * 0.5, corners)

    # Feature: pipe bore.
    clamp -= feature("pipe bore", Pos(0, centre_y, 0) * Cylinder(bore_r, strap_width, align=(Align.CENTER, Align.CENTER, Align.MIN)),
                     params="pipe_dia")
    # Feature: mouth; the strap springs open to pass the pipe, then the bolt closes it.
    gap_half = pipe_dia * mouth_ratio / 2
    clamp -= feature("mouth", prism(-gap_half, gap_half, centre_y, centre_y + 2 * outer_r, strap_width),
                     params="mouth_ratio")

    # Feature: bolt ears on the strap tips. Twice the strap, stiff enough that the strap does the bending.
    ear_t = 2 * strap_t
    bolt_y = centre_y + outer_r + bolt["head_dia"] / 2
    ear_top = bolt_y + bolt["head_dia"] / 2 + strap_t
    ear_bottom = centre_y + math.sqrt(mid_r ** 2 - gap_half ** 2)
    for sign in (-1, 1):
        x0, x1 = sorted((sign * gap_half, sign * (gap_half + ear_t)))
        clamp += prism(x0, x1, ear_bottom, ear_top, strap_width)

    # Feature: cross bolt, plain round clearance through both ears. A 3.4 mm hole bridges with slight
    # sag; a teardrop peak here tips the literal overhang gate, so this bore stays round.
    bolt_frame = Plane(origin=(gap_half + ear_t, bolt_y, mid_z), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    clamp -= feature("bolt hole", bolt_frame.location * Pos(0, 0, -(gap_half + ear_t)) * Cylinder(
        bolt["clearance"] / 2, 2 * (gap_half + ear_t) + 2))

    # Feature: plain wall screw holes, teardrop peak print-up; heads seat on the plate's room face.
    wall_cutter = teardrop_bore(wall_screw["clearance"] / 2, base_t)
    frames = [Plane(origin=(sign * hole_spacing / 2, base_t, mid_z), x_dir=(-1, 0, 0), z_dir=(0, 1, 0))
              for sign in (-1, 1)]
    clamp -= feature("wall screw hole", Compound([frame.location * wall_cutter for frame in frames]),
                     params="hole_spacing")

    clamp.label = "clamp"
    return clamp


def line_circle(x0, y0, x1, y1, centre_y, radius):
    """Where the segment from (x0, y0) to (x1, y1) enters a circle on (0, centre_y); bisection."""
    low, high = 0, 1
    for _ in range(int(radius * radius)):
        t = (low + high) / 2
        x, y = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if math.hypot(x, y - centre_y) > radius:
            low = t
        else:
            high = t
    return x0 + low * (x1 - x0), y0 + low * (y1 - y0)


def nearest(shape, point):
    """Named-feature selection: the Z edge whose centre is closest to an expected point."""
    return min(shape.edges().filter_by(Axis.Z), key=lambda e: (e.center() - point).length)


def section_plane(strap_width, **_):
    return {"axis": "Z", "offset": strap_width / 2}
