"""Open-front wall cradle for a rectangular object, printed back-down.

The back rests on the print bed; the bottom and front lip support the object
when the back is attached to a wall. Fit and load require physical testing.
"""
from build123d import Align, Box, Compound, Cylinder, Pos
from library import feature, standard_parts

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
    screw = standard_parts()['screws']['M3']
    head_d = screw['head_dia']
    mount_y = height * (1 - 0.5 * 0.5)
    mounts = [Pos(side * (width / 2 + head_d), mount_y, 0) for side in (-1, 1)]
    # Named in the order a shared face should take: holes, then the parts the object touches,
    # then the plate behind them all.
    holes = feature('screw holes', Compound([at * Cylinder(
        screw['clearance'] / 2, wall * 2, align=(Align.CENTER, Align.CENTER, Align.MIN)) for at in mounts]),
        params='obj_h')
    # Retaining lip at the ledge's front, with continuous joints.
    lip = feature('retaining lip', Pos(0, 0, front) * Box(
        width, wall * 2 + wall, wall, align=(Align.CENTER, Align.MIN, Align.MIN)), params='obj_d')
    # Side rails prevent lateral sliding without enclosing the object.
    rails = feature('side rails', Compound([Pos(side * (inner_w / 2 + wall / 2), 0, 0) * Box(
        wall, height, front + wall, align=(Align.CENTER, Align.MIN, Align.MIN)) for side in (-1, 1)]),
        params=('obj_w', 'clearance'))
    # Bottom ledge the object stands on.
    ledge = feature('ledge', Box(width, wall * 2, front + wall, align=(Align.CENTER, Align.MIN, Align.MIN)),
                    params='obj_d')
    # Mounting ears sit outside the object so screw heads cannot occupy its cavity.
    ears = feature('mounting ears', Compound([at * Box(
        2 * head_d, 2 * head_d, wall, align=(Align.CENTER, Align.CENTER, Align.MIN)) for at in mounts]),
        params='obj_w')
    # Backplate carries screw holes and supports the object against the wall.
    cradle = feature('backplate', Box(width, height, wall, align=(Align.CENTER, Align.MIN, Align.MIN)),
                     params=('obj_h', 'wall'))
    cradle += ledge
    cradle += lip
    cradle += rails
    cradle += ears
    cradle -= holes
    cradle.label = 'holder_cradle'
    return cradle
