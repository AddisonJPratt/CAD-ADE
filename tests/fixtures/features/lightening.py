"""Feature fixture: lightening_cutouts. A bookend: base plate under the books, upright panel
lightened with diamond pockets so every pocket roof prints without support."""
from build123d import Align, Box

from library.engineering import lightening_cutouts

PARAMS = {
    # name: (default, min, max)    mm
    "width": (110.0, 80.0, 150.0),    # bookend width
    "base": (100.0, 80.0, 140.0),     # base depth the books stand on
    "height": (140.0, 110.0, 180.0),  # upright height
    "thickness": (4.0, 3.0, 6.0),     # plate thickness
    "cell": (24.0, 16.0, 34.0),       # target pocket size
    "web": (6.0, 4.0, 9.0),           # web between pockets
}


def build(width, base, height, thickness, cell, web):
    plate = Box(width, base, thickness, align=(Align.CENTER, Align.MIN, Align.MIN))
    upright = Box(width, thickness, height, align=(Align.CENTER, Align.MIN, Align.MIN))
    bookend = plate + upright
    # Feature: diamond pockets through the upright, kept two webs clear of the base.
    bookend = lightening_cutouts(bookend, (0, 0, height / 2), cell=cell, web=web, margin=2 * web).shape
    bookend.label = "bookend"
    return bookend
