"""Joint fixture: a strap with a living hinge across its middle, printed flat."""
from build123d import Align, Box

from library import feature
from library.joints import living_hinge_notch

PARAMS = {
    "length": (60.0, 30.0, 120.0),    # mm, X
    "width": (15.0, 8.0, 40.0),       # mm, Y
    "thickness": (3.0, 2.0, 6.0),     # mm, Z
    "web": (0.6, 0.4, 0.8),           # mm, hinge web on the bed: one to two perimeters
    "hinge_gap": (1.0, 0.5, 3.0),     # mm, hinge length along X at the web
}


def build(length, width, thickness, web, hinge_gap):
    part = Box(length, width, thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
    part -= feature("living hinge", living_hinge_notch(web, hinge_gap, width, thickness),
                    params=("web", "hinge_gap"))
    part.label = "strap"
    return part
