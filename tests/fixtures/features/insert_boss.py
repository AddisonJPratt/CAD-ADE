"""Feature fixture: insert_boss. A PCB carrier plate: four M3 heat-set bosses on the board's
hole pattern; insert hole, boss OD and floor come from standard_parts.json."""
from build123d import Align, Box

from library import standard_parts
from library.engineering import insert_boss

SCREW = "M3"

PARAMS = {
    # name: (default, min, max)    mm
    "pcb_x": (58.0, 40.0, 90.0),      # board hole spacing in X
    "pcb_y": (49.0, 30.0, 70.0),      # board hole spacing in Y
    "plate": (3.0, 2.4, 4.0),         # plate thickness
    "standoff": (9.0, 7.9, 14.0),     # boss height: clears through-hole leads under the board
}


def build(pcb_x, pcb_y, plate, standoff):
    boss_od = standard_parts()["heatset_inserts"][SCREW]["boss_od"]
    carrier = Box(pcb_x + 2 * boss_od, pcb_y + 2 * boss_od, plate,
                  align=(Align.CENTER, Align.CENTER, Align.MIN))
    for sx in (-1, 1):
        for sy in (-1, 1):
            # Feature: heat-set boss on the top face at a board hole.
            at = (sx * pcb_x / 2, sy * pcb_y / 2, plate)
            carrier = insert_boss(carrier, at, at, SCREW, height=standoff).shape
    carrier.label = "pcb_carrier"
    return carrier
