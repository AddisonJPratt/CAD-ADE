"""Stepped herb planter: even wall, drain grooves under a flat foot. See evals/briefs/planter_pot.yaml.

Frame: Z is print-up, foot on z=0, axis on Z.

Why stepped, not a smooth cone: the overhang gate caps every off-bed downward face at 15 % of all
downward area. A smooth outward lean is 1/sin(lean) times its footprint in downward area, so no
smooth taper can pass. The pot widens instead in two steps cut at step_overhang_deg (under 45 deg
from vertical, so each prints unsupported) between vertical bands. taper_deg is the lean of the
envelope through the steps. The total run is also held to max_run_share of the rim radius, past
which small, tall pots would exceed the overhang budget. At the default size the whole taper
range stays under that limit; on tall, narrow pots (rim 70 or height 150) the limit binds above
about 1 deg, and more taper there changes nothing.

Why a solid plinth: the floor sits on the bed as one flat foot circle. Raising it on a ring would
leave a large flat ceiling under the floor (support risk), and the bed contact is what keeps the
steps inside the budget. The cost is material: about a fifth of the volume is below the floor.
Three radial grooves under that plinth carry water from the drain out past the foot edge.
All design choices below come from design_constants.planter_pot, where each one's intent is noted.
"""
import math

from build123d import Align, Axis, Box, Compound, Cylinder, Plane, Polygon, Rot, revolve

from library import feature, standard_parts

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "rim_dia": (100.0, 70.0, 160.0),    # outer rim diameter (hard dimension)
    "height": (90.0, 60.0, 150.0),      # overall height (hard dimension)
    "taper_deg": (1.5, 0.5, 1.5),       # envelope lean through the steps, deg; clamped on tall, narrow pots
    "wall": (2.4, 1.6, 3.2),            # even wall thickness, normal to every face
}


def offset_inward(points, distance):
    """Offset an upward (r, z) polyline toward the axis by `distance`, normal to each segment."""
    lines = []
    for (r0, z0), (r1, z1) in zip(points, points[1:]):
        length = math.hypot(r1 - r0, z1 - z0)
        nr, nz = -(z1 - z0) / length, (r1 - r0) / length     # left normal of an upward segment
        lines.append(((r0 + nr * distance, z0 + nz * distance), (r1 - r0, z1 - z0)))
    out = [lines[0][0]]
    for (p, d), (q, e) in zip(lines, lines[1:]):
        t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / (d[0] * e[1] - d[1] * e[0])
        out.append((p[0] + t * d[0], p[1] + t * d[1]))
    (p, d) = lines[-1]
    out.append((p[0] + d[0], p[1] + d[1]))
    return out


def nearest_circle(shape, radius, z):
    """The circular edge of a revolved shape nearest to radius `radius` at height `z`."""
    def miss(edge):
        point = edge.position_at(0)
        return abs(math.hypot(point.X, point.Y) - radius) + abs(point.Z - z)
    return min(shape.edges(), key=miss)


def build(rim_dia, height, taper_deg, wall):
    drain_dia = standard_parts()["brief_constants"]["planter_pot"]["drain_dia"]
    choice = standard_parts()["design_constants"]["planter_pot"]
    steps = choice["steps"]
    step_slope = math.tan(math.radians(choice["step_overhang_deg"]))   # run per unit rise
    groove_depth = choice["saucer_clearance"]
    floor_z = groove_depth + wall       # top of the floor
    chamfer = choice["foot_chamfer"]

    # Envelope: the taper sets the base radius; the steps share the run equally.
    rim_r = rim_dia / 2
    total_run = min(height * math.tan(math.radians(taper_deg)), rim_r * choice["max_run_share"])
    base_r = rim_r - total_run
    run = total_run / steps
    rise = run / step_slope

    # Feature: stepped outer profile. Bands shrink upward by band_ratio, so the steps gather
    # toward the rim; the top band is the plain rim band.
    weights = [choice["band_ratio"] ** k for k in range(steps + 1)]
    band_total = height - steps * rise
    # Feature: foot chamfer at the bed edge; its face is as flat as the steps are steep.
    outer = [(base_r - chamfer, 0.0), (base_r, chamfer * step_slope)]
    r, z = base_r, 0.0
    for weight in weights[:-1]:
        z += band_total * weight / sum(weights)
        outer.append((r, z))
        r, z = r + run, z + rise
        outer.append((r, z))
    outer.append((rim_r, height))

    # Feature: inner profile, offset normal to every face so the wall is even all the way up.
    # The chamfer segment is left out: the floor fills that corner.
    inner = offset_inward(outer[1:], wall)
    first, second = inner[0], inner[1]
    floor_r = first[0] + (second[0] - first[0]) * (floor_z - first[1]) / (second[1] - first[1])
    inner = [(floor_r, floor_z)] + [p for p in inner[1:] if p[1] > floor_z]

    section = Plane.XZ * Polygon((0, 0), *outer, *reversed(inner), (0, floor_z), align=None)
    pot = revolve(section, axis=Axis.Z)

    # Feature: rounded rim. The outside, the edge you see and handle, is a full half-wall round;
    # the inside edge is eased at half that, so a flat land is left for the fillets to meet.
    pot = pot.fillet(wall * 0.5, [nearest_circle(pot, rim_r, height)])
    pot = pot.fillet(wall * 0.5 * 0.5, [nearest_circle(pot, inner[-1][0], height)])
    # Feature: soil-side cove where floor meets wall.
    pot = pot.fillet(wall, [nearest_circle(pot, floor_r, floor_z)])

    # Feature: drain hole through the floor.
    pot -= feature("drain hole", Cylinder(drain_dia / 2, floor_z, align=(Align.CENTER, Align.CENTER, Align.MIN)))
    # Feature: radial drain grooves under the floor, from the drain out past the foot edge.
    pot -= feature("drain grooves", Compound([
        Rot(0, 0, 2 * 180 * k / choice["drain_grooves"]) * Box(
            rim_dia, choice["groove_bridge"], groove_depth, align=(Align.MIN, Align.CENTER, Align.MIN))
        for k in range(choice["drain_grooves"])]))

    pot.label = "pot"
    return pot


def section_plane(**_):
    return {"axis": "X", "offset": 0}
