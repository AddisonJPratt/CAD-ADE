"""Two meshing spur gears, laid out at their running centre distance. See briefs/gear_pair.yaml.

Frame: Z is print-up, both gears flat on z=0. Gear A centred at the origin with a tooth on +X,
gear B at (centre distance, 0) with a tooth space on -X. Every feature is a straight prism or an
open-top pocket, so nothing overhangs. Teeth are thinned at the standard centre distance to make
the flank clearance. Tooth form is not gated by the harness; see the brief's assumptions.
"""
import math

from build123d import Align, Cylinder, Location, Polygon, Pos, Rot, extrude

from library import feature, standard_parts

AXLE = "M4"             # axle screw, resolved through library/standard_parts.json

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "module": (1.5, 1.0, 3.0),              # tooth size; pitch diameter is module x teeth
    "teeth_a": (20, 18, 36),                # pinion teeth, count
    "teeth_b": (36, 18, 60),                # wheel teeth, count
    "pressure_angle": (20.0, 20.0, 25.0),   # deg
    "thickness": (8.0, 5.0, 15.0),          # gear thickness along the axle (hard dimension)
    "web": (3.0, 2.0, 4.0),                 # web thickness inside the rim
    "hub_wall": (3.0, 2.0, 5.0),            # hub wall around the axle bore
    "flank_clearance": (0.35, 0.25, 0.5),   # normal gap per flank at the running centre distance
    "flank_steps": (6, 4, 10),              # straight facets per involute flank, count
}


def involute(angle):
    return math.tan(angle) - angle


def tooth_outline(module, teeth, pressure, thinning, steps):
    """Closed gear outline: involute flanks from the base circle, radial below it, chord roots."""
    pitch_r = module * teeth / 2
    base_r = pitch_r * math.cos(pressure)
    tip_r = pitch_r + module
    root_r = pitch_r - module * (1 + 0.5 * 0.5)      # dedendum 1.25 m
    half_tooth = math.pi / teeth / 2 - thinning / pitch_r + involute(pressure)
    start_r = max(base_r, root_r)
    radii = [start_r + (tip_r - start_r) * i / steps for i in range(steps + 1)]
    flank = [(r, half_tooth - involute(math.acos(min(base_r / r, 1)))) for r in radii]
    if root_r < base_r:
        flank.insert(0, (root_r, flank[0][1]))
    points = []
    for tooth in range(teeth):
        centre = 2 * math.pi * tooth / teeth
        side = [(r, centre - a) for r, a in flank] + [(r, centre + a) for r, a in reversed(flank)]
        points += [(r * math.cos(t), r * math.sin(t)) for r, t in side]
    return points


def gear(module, teeth, pressure, thickness, web, hub_wall, thinning, steps, bore_dia, at=Location()):
    """One gear, a tooth on local +X, flat on z=0, placed at `at` (its cutters too, so they name its faces)."""
    outline = Polygon(*tooth_outline(module, teeth, pressure, thinning, steps), align=None)
    # Feature: teeth. Names the flank and root faces only: the outline, run past both flat faces
    # so its ends name nothing.
    feature("teeth", at * Pos(0, 0, -thickness) * extrude(outline, amount=thickness * (1 + 2)),
            params=("module", "flank_clearance"))
    body = at * extrude(outline, amount=thickness)
    root_r = module * teeth / 2 - module * (1 + 0.5 * 0.5)
    # Feature: thin web between hub and rim, as an open-top pocket; the rim stays full height under the teeth.
    hub_r = bore_dia / 2 + hub_wall
    rim_inner_r = root_r - 2 * module
    if rim_inner_r > hub_r + hub_wall:   # small pinions stay solid: no room for a useful web
        # Feature: hub, standing proud of the web. Names faces only, and before the pocket, whose
        # inner wall is the hub's outside.
        feature("hub", at * Cylinder(hub_r, thickness, align=(Align.CENTER, Align.CENTER, Align.MIN)),
                params="hub_wall")
        pocket = Cylinder(rim_inner_r, thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
        pocket -= Cylinder(hub_r, thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
        body -= feature("web pocket", at * Pos(0, 0, web) * pocket, params=("web", "hub_wall"))
    # Feature: axle bore through the hub.
    body -= feature("axle bore", at * Cylinder(bore_dia / 2, 2 * thickness, align=(Align.CENTER, Align.CENTER, Align.CENTER)))
    return body


def build(module, teeth_a, teeth_b, pressure_angle, thickness, web, hub_wall, flank_clearance, flank_steps):
    pressure = math.radians(pressure_angle)
    bore_dia = standard_parts()["screws"][AXLE]["clearance"]
    # Both gears lose thinning on each flank, so the normal gap is 2 * thinning * cos(pressure).
    thinning = flank_clearance / (2 * math.cos(pressure))
    args = (pressure, thickness, web, hub_wall, thinning, flank_steps, bore_dia)

    gear_a = gear(module, teeth_a, *args)
    # Feature: gear B turned half a pitch from a tooth on -X, so a space meets A's tooth.
    turn = 180 + 180 / teeth_b
    centre_distance = module * (teeth_a + teeth_b) / 2
    gear_b = gear(module, teeth_b, *args, at=Pos(centre_distance, 0, 0) * Rot(0, 0, turn))

    gear_a.label, gear_b.label = "gear_a", "gear_b"
    return {"gear_a": gear_a, "gear_b": gear_b}


def section_plane(thickness, **_):
    return {"axis": "Z", "offset": thickness / 2}
