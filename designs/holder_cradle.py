"""Open-front wall cradle for a rectangular object, printed back-down.

The back rests on the print bed; the bottom and front lip support the object
when the back is attached to a wall. Fit and load require physical testing.
"""
from build123d import Align, Box, Cylinder, Pos
from library import standard_parts

PARAMS = {
    'obj_w': (90.0, 60.0, 120.0),   # mm, object width
    'obj_d': (35.0, 20.0, 50.0),    # mm, object depth
    'obj_h': (120.0, 80.0, 150.0),  # mm, object height
    'clearance': (0.25, 0.1, 0.7),  # mm, per side
    'wall': (3.0, 2.4, 4.0),        # mm, plate and lip thickness
}


def build(obj_w, obj_d, obj_h, clearance, wall):
    inner_w = obj_w + 2 * clearance
    inner_d = obj_d + clearance
    width = inner_w + 2 * wall
    height = obj_h * 0.5
    front = wall + inner_d
    # Backplate carries screw holes and supports the object against the wall.
    cradle = Box(width, height, wall, align=(Align.CENTER, Align.MIN, Align.MIN))
    # Bottom ledge and a retaining lip at its front, with continuous joints.
    ledge = Box(width, wall * 2, front + wall, align=(Align.CENTER, Align.MIN, Align.MIN))
    cradle += ledge
    lip = Pos(0, 0, front) * Box(width, wall * 2 + wall, wall,
                                   align=(Align.CENTER, Align.MIN, Align.MIN))
    cradle += lip
    # Side rails prevent lateral sliding without enclosing the object.
    for side in (-1, 1):
        rail = Pos(side * (inner_w / 2 + wall / 2), 0, 0) * Box(
            wall, height, front + wall, align=(Align.CENTER, Align.MIN, Align.MIN))
        cradle += rail
    # Mounting ears sit outside the object so screw heads cannot occupy its cavity.
    screw = standard_parts()['screws']['M3']
    head_d = screw['head_dia']
    mount_y = height * (1 - 0.5 * 0.5)
    for side in (-1, 1):
        mount_x = side * (width / 2 + head_d)
        ear = Pos(mount_x, mount_y, 0) * Box(
            2 * head_d, 2 * head_d, wall, align=(Align.CENTER, Align.CENTER, Align.MIN))
        cradle += ear
        hole = Pos(mount_x, mount_y, 0) * Cylinder(
            screw['clearance'] / 2, wall * 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
        cradle -= hole
    cradle.label = 'holder_cradle'
    return cradle
