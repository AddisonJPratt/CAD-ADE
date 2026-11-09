"""Pattern fixture: a vent cover plate. A grid of round vents (count and spacing are PARAMS, so
the sweep covers them; the plate is sized from the grid), four corner M3 holes placed by a
circular pattern on the plate's diagonals, and an embossed label in a band under the vents."""
import math

from build123d import Align, Box, Cylinder, Pos

from library import standard_parts
from library.surface import circular_pattern, grid_pattern, pattern, pick_face, text

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "cols": (5, 3, 6),                 # count, vents across
    "rows": (3, 2, 4),                 # count, vents down
    "vent_dia": (4.0, 3.0, 5.0),       # vent diameter
    "spacing": (7.0, 6.0, 9.0),        # vent pitch; web = spacing - vent_dia, >= the minimum feature
    "plate": (2.4, 2.0, 3.2),          # panel thickness
    "label_size": (8.0, 8.0, 10.0),    # label font size; strokes reach the minimum feature at 8
    "label_depth": (0.6, 0.4, 0.8),    # label relief
}


def build(cols, rows, vent_dia, spacing, plate, label_size, label_depth):
    screw = standard_parts()["screws"]["M3"]
    margin = 2 * screw["head_dia"]                         # a pan or socket head bears wholly on the plate
    width = cols * spacing + 2 * margin
    depth = rows * spacing + 2 * margin + label_size      # one label height added below the vents
    panel = Box(width, depth, plate, align=(Align.CENTER, Align.CENTER, Align.MIN))
    vents = Pos(0, label_size / 2, 0) * Cylinder(vent_dia / 2, 2 * plate + 2)
    # Feature: vent grid, offset up to leave the label band.
    panel = pattern(panel, vents, grid_pattern(cols, rows, spacing, spacing), cut=True, name="vents",
                    params=("cols", "rows", "vent_dia", "spacing")).shape
    # Feature: four corner screw holes, a circular pattern on the panel's corner diagonal.
    corner = math.hypot(width / 2 - margin / 2, depth / 2 - margin / 2)
    start = math.degrees(math.atan2(depth / 2 - margin / 2, width / 2 - margin / 2))
    holes = circular_pattern(2, corner, sweep_deg=180, start_deg=start) + \
        circular_pattern(2, corner, sweep_deg=180, start_deg=180 - start)
    panel = pattern(panel, Cylinder(screw["clearance"] / 2, 2 * plate + 2), holes, cut=True, name="screw holes").shape
    # Feature: embossed label centred in the band between the vents and the near edge.
    top = pick_face(panel, facing="+Z")
    panel = text(panel, top, "VENT", size=label_size, depth=label_depth, offset=(0, -(rows * spacing + margin) / 2),
                 name="label", params=("label_size", "label_depth")).shape
    panel.label = "panel"
    return panel
