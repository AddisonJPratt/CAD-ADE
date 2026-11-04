"""Electronics enclosure: base with four heat-set bosses, flush screw-down lid. See briefs/project_enclosure.yaml.

Frame: Z is print-up. Base prints floor-down. Lid prints inner-face-down with the counterbores
opening up, so neither part has a ceiling beyond the connector opening's short bridge.
Bosses sit proud of the walls with a corner filler behind them, leaving no slot a nozzle can't fill.
"""
from build123d import Align, Axis, Box, Pos, Rectangle, extrude, fillet

from library import counterbored_hole, heatset_boss, standard_parts

SCREW = "M3"            # hardware choice, resolved through library/standard_parts.json

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "outer_x": (100.0, 80.0, 140.0),     # outside length (hard dimension)
    "outer_y": (60.0, 50.0, 90.0),       # outside width (hard dimension)
    "outer_z": (35.0, 25.0, 50.0),       # assembled height, lid flush (hard dimension)
    "lid_thickness": (5.0, 4.4, 6.0),    # leaves at least 1.2 under the M3 head (hard dimension)
    "wall": (2.4, 1.6, 3.2),             # side wall; half is cut away for the rebate
    "floor": (2.0, 1.6, 3.2),            # base floor thickness
    "port_w": (12.0, 9.0, 16.0),         # connector opening width
    "port_h": (6.0, 4.0, 8.0),           # connector opening height
    "vent_count": (5, 3, 9),             # lid vent slots, count
    "vent_w": (2.0, 1.6, 3.0),           # vent slot width
}


def rounded_prism(x, y, height, radius):
    """Base on z=0, centred in XY, plan corners rounded."""
    solid = extrude(Rectangle(x, y), amount=height)
    return fillet(solid.edges().filter_by(Axis.Z), radius)


def build(outer_x, outer_y, outer_z, lid_thickness, wall, floor, port_w, port_h, vent_count, vent_w):
    inserts = standard_parts()["heatset_inserts"][SCREW]
    clearance = standard_parts()["fits"]["sliding"]
    boss_r = inserts["boss_od"] / 2
    outer_r = 2 * wall                   # outside plan radius, scaled to the wall
    step = wall * 0.5                    # wall left beside the lid after the rebate
    ledge_z = outer_z - lid_thickness    # the lid and the boss tops both land here

    # Screw axes: bosses bite a quarter wall into the side walls, so the union never meets at a tangent.
    inset = wall * (1 - 0.5 * 0.5) + boss_r
    axis_x, axis_y = outer_x / 2 - inset, outer_y / 2 - inset
    screw_axes = [(sx * axis_x, sy * axis_y) for sx in (-1, 1) for sy in (-1, 1)]

    # Feature: base shell. Cavity corners stay square, since the bosses and fillers hide them.
    base = rounded_prism(outer_x, outer_y, outer_z, outer_r)
    base -= Pos(0, 0, floor) * Box(outer_x - 2 * wall, outer_y - 2 * wall, outer_z,
                                   align=(Align.CENTER, Align.CENTER, Align.MIN))
    # Feature: lid rebate, concentric with the outside corner.
    base -= Pos(0, 0, ledge_z) * rounded_prism(outer_x - 2 * step, outer_y - 2 * step, lid_thickness, outer_r - step)

    # Feature: four heat-set bosses, tops on the lid ledge; library hole depth and floor from the DB.
    boss = heatset_boss(SCREW, height=ledge_z)
    filler_from = boss_r * 0.5           # filler corner stays inside the boss wall, clear of the insert hole
    filler_size = inset - filler_from - wall * (1 - 0.5 * 0.5)  # stops inside the wall, clear of the rounded outside corner
    for x, y in screw_axes:
        sx, sy = (1 if x > 0 else -1), (1 if y > 0 else -1)
        # Feature: filler between boss and corner, up to the ledge.
        base += Pos(x + sx * (filler_from + filler_size / 2), y + sy * (filler_from + filler_size / 2), 0) * Box(
            filler_size, filler_size, ledge_z, align=(Align.CENTER, Align.CENTER, Align.MIN))
        base += Pos(x, y, 0) * boss

    # Feature: connector opening in the -X end wall, one opening-height above the floor.
    base -= Pos(-outer_x / 2 - wall, 0, floor + port_h) * Box(
        2 * wall + wall, port_w, port_h, align=(Align.MIN, Align.CENTER, Align.MIN))

    # Feature: lid plate, sliding clearance per side inside the rebate.
    lid = rounded_prism(outer_x - 2 * (step + clearance), outer_y - 2 * (step + clearance), lid_thickness,
                        outer_r - step - clearance)
    # Feature: four counterbored M3 holes on the same axes as the bosses.
    hole = counterbored_hole(SCREW, depth=lid_thickness)
    for x, y in screw_axes:
        lid -= Pos(x, y, lid_thickness) * hole
    # Feature: vent slots between the screw rows, one slot width apart.
    pitch = 2 * vent_w
    slot_len = outer_y * 0.5
    for i in range(vent_count):
        x = (i - (vent_count - 1) / 2) * pitch
        lid -= Pos(x, 0, 0) * Box(vent_w, slot_len, lid_thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
    lid = Pos(0, outer_y + 2 * wall, 0) * lid

    base.label, lid.label = "base", "lid"
    return {"base": base, "lid": lid}


def section_plane(**_):
    return {"axis": "Y", "offset": 0}
