"""Three-bay desk drawer tray: one long bay, two small bays. See briefs/drawer_tray.yaml.

Frame: Z is print-up, floor on z=0, centred in XY. Bays are cut down from the top, so everything
above the floor is a wall with upward-facing scoops and there are no ceilings. Dividers stay as
real walls between bays, trimmed lower than the rim by a single slab cut.
"""
from build123d import Axis, Cylinder, Pos, Rectangle, Rot, extrude, fillet

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "outer_x": (240.0, 120.0, 245.0),      # outside length (hard dimension)
    "outer_y": (120.0, 80.0, 200.0),       # outside width (hard dimension)
    "height": (45.0, 25.0, 70.0),          # overall height (hard dimension)
    "wall": (1.8, 1.2, 3.0),               # outer wall
    "floor": (1.6, 1.2, 2.4),              # floor thickness
    "divider_t": (1.6, 1.2, 3.0),          # divider thickness; carries no load
    "divider_ratio": (0.75, 0.5, 1.0),     # divider height / bay depth, ratio
    "split_x": (0.6, 0.4, 0.75),           # long bay's share of the inside length, ratio
    "split_y": (0.5, 0.3, 0.65),           # first small bay's share of the inside width, ratio
    "scoop_r": (6.0, 4.0, 8.0),            # floor-to-wall radius
}


def rounded_prism(x, y, height, radius):
    """Base on z=0, centred in XY, plan corners rounded."""
    solid = extrude(Rectangle(x, y), amount=height)
    return fillet(solid.edges().filter_by(Axis.Z), radius)


def bay(x0, x1, y0, y1, depth, scoop_r):
    """Pocket cutter with its floor on z=0; plan radius wider than the scoop, so the fillet closes."""
    plan_r = scoop_r * (1 + 0.5 * 0.5)
    cutter = rounded_prism(x1 - x0, y1 - y0, depth, plan_r)
    cutter = fillet(cutter.faces().sort_by(Axis.Z)[0].edges(), scoop_r)   # fillet before boolean
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, 0) * cutter


def build(outer_x, outer_y, height, wall, floor, divider_t, divider_ratio, split_x, split_y, scoop_r):
    plan_r = scoop_r * (1 + 0.5 * 0.5)
    inner_x, inner_y = outer_x - 2 * wall, outer_y - 2 * wall
    left, right = -inner_x / 2, inner_x / 2
    front, back = -inner_y / 2, inner_y / 2
    depth = height - floor

    # Feature: outer shell, concentric with the bay corners so the wall stays even round the bend.
    tray = rounded_prism(outer_x, outer_y, height, plan_r + wall)

    # Feature: long bay, then two small bays beside it; the walls left between them are the dividers.
    split_at_x = left + inner_x * split_x
    split_at_y = front + inner_y * split_y
    half_t = divider_t / 2
    for x0, x1, y0, y1 in ((left, split_at_x - half_t, front, back),
                           (split_at_x + half_t, right, front, split_at_y - half_t),
                           (split_at_x + half_t, right, split_at_y + half_t, back)):
        tray -= Pos(0, 0, floor) * bay(x0, x1, y0, y1, depth, scoop_r)

    # Feature: trim all dividers below the rim, so a hand sweeps across; slab keeps the rim's plan shape.
    divider_top = floor + depth * divider_ratio
    if divider_ratio < 1:
        tray -= Pos(0, 0, divider_top) * rounded_prism(inner_x, inner_y, height - divider_top, plan_r)

    # Feature: finger dip in the long divider, centred on the front small bay so it clears the T
    # junction; a round cut leaves no ceiling.
    dip_r = depth * 0.5 * 0.5
    dip_y = (front + split_at_y) / 2
    tray -= Pos(split_at_x, dip_y, divider_top) * Rot(0, 90, 0) * Cylinder(dip_r, 2 * divider_t)

    tray.label = "tray"
    return tray


def section_plane(outer_y, **_):
    return {"axis": "Y", "offset": outer_y * 0.5 * 0.5}
