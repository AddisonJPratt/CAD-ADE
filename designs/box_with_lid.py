"""Two-part storage box: open tray and a separate drop-on lid. See evals/briefs/box_with_lid.yaml.

Frame: Z is print-up. Tray prints floor-down; lid prints top-down, so its locating lip rises
off the plate and neither part has a ceiling. Parts sit apart on the bed (the brief's print layout).
Design intent: the lip's sliding clearance sets the fit, its depth keeps the lid from rocking.
"""
from build123d import Align, Axis, Box, Pos, Rectangle, Vector, chamfer, extrude, fillet

from library import standard_parts

PARAMS = {
    # name: (default, min, max)    all mm
    "outer_x": (80.0, 50.0, 150.0),      # outside length (hard dimension)
    "outer_y": (60.0, 40.0, 120.0),      # outside width (hard dimension)
    "box_height": (30.0, 15.0, 80.0),    # tray height without lid (hard dimension)
    "lid_height": (8.0, 5.0, 15.0),      # lid height including lip (hard dimension)
    "wall": (2.0, 1.2, 3.2),             # wall and floor thickness
}


def rounded_prism(x, y, height, radius):
    """Base on z=0, centred in XY, plan corners rounded."""
    solid = extrude(Rectangle(x, y), amount=height)
    return fillet(solid.edges().filter_by(Axis.Z), radius)


def build(outer_x, outer_y, box_height, lid_height, wall):
    clearance = standard_parts()["fits"]["sliding"]
    outer_r = 2 * wall                 # outside plan radius; concentric inner corners keep the wall even
    edge = wall * 0.5                  # outside chamfer, thinner than the wall on purpose

    # Feature: tray shell, floor down; plan corners concentric so the wall stays even round the bend.
    tray = rounded_prism(outer_x, outer_y, box_height, outer_r)
    cavity = rounded_prism(outer_x - 2 * wall, outer_y - 2 * wall, box_height, outer_r - wall)
    tray -= Pos(0, 0, wall) * cavity
    # Feature: outside chamfer around the rim only; the bed edge stays square for first-layer contact.
    rim = [e for e in tray.edges() if abs(e.center().Z - box_height) < edge and is_outer(e, outer_x, outer_y, wall)]
    tray = chamfer(rim, edge)
    # Feature: thumb notch in one long rim, so the lid can be lifted off a fit that has no handle.
    notch = wall + lid_height
    tray -= Pos(0, -outer_y / 2, box_height) * Box(2 * notch, 2 * wall, 2 * notch * 0.5)

    # Feature: lid plate, top face on the bed.
    plate = rounded_prism(outer_x, outer_y, wall, outer_r)
    # Feature: locating lip, sliding clearance per side inside the tray cavity; depth stops rocking.
    lip_x, lip_y = outer_x - 2 * (wall + clearance), outer_y - 2 * (wall + clearance)
    lip_r = outer_r - wall - clearance
    lip = rounded_prism(lip_x, lip_y, lid_height - wall, lip_r)
    bore = rounded_prism(lip_x - 2 * wall, lip_y - 2 * wall, lid_height - wall, lip_r * 0.5)
    lid = plate + Pos(0, 0, wall) * (lip - bore)
    lid = Pos(0, outer_y + 2 * wall, 0) * lid

    tray.label, lid.label = "box", "lid"
    return {"box": tray, "lid": lid}


def is_outer(edge, outer_x, outer_y, wall):
    """True for edges on the outer skin of the tray rim, not the cavity's."""
    centre = edge.center()
    return abs(centre.X) > outer_x / 2 - wall or abs(centre.Y) > outer_y / 2 - wall


def section_plane(**_):
    return {"axis": "X", "offset": 0}
