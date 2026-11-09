"""Feature fixture: knurl. A thumb knob on an M4 heat-set insert: straight knurl round
its grip, the insert bore from the underside, and a rounded crown so the top edge is kind
to the thumb. Printed crown-up; the knurl flanks rise at the self-supporting slope."""
from build123d import Align, Cylinder

from library import standard_parts
from library.engineering import edge_break
from library.textures import knurl

PARAMS = {
    # name: (default, min, max)    mm / deg
    "radius": (14.0, 10.0, 20.0),   # grip radius
    "height": (14.0, 10.0, 20.0),   # grip height
    "pitch": (2.4, 1.8, 3.2),       # knurl groove spacing, across the grooves (B-rep range)
    "depth": (0.5, 0.3, 0.6),       # knurl groove depth; <= the flank limit at the finest pitch
    "angle": (0.0, 0.0, 20.0),      # groove angle from print-up: 0 straight, else a gentle helix
}


def build(radius, height, pitch, depth, angle):
    up = (Align.CENTER, Align.CENTER, Align.MIN)
    insert = standard_parts()["heatset_inserts"]["M4"]
    knob = Cylinder(radius, height, align=up)
    # Feature: heat-set insert bore, pressed in from the underside after printing.
    knob -= Cylinder(insert["hole_dia"] / 2, insert["insert_length"] + insert["hole_extra_depth"], align=up)
    # Feature: crown break on the top outer edge.
    knob = edge_break(knob, [(0, radius, height)], depth * 2).shape
    # Feature: straight knurl on the grip: V grooves with self-supporting flanks.
    knob = knurl(knob, (radius, 0, height / 2), pitch, depth, angle).shape
    knob.label = "knob"
    return knob
