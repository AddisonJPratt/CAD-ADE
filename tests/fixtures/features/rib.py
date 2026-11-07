"""Feature fixture: rib. A stiffened access cover: thin plate, ribs along its long axis on top."""
from build123d import Align, Box

from library.engineering import rib

PARAMS = {
    # name: (default, min, max)    mm unless noted
    "length": (120.0, 80.0, 180.0),   # cover length
    "width": (64.0, 40.0, 100.0),     # cover width
    "plate": (1.6, 1.2, 2.4),         # plate thickness, thin on purpose: the ribs carry it
    "ribs": (3, 2, 5),                # rib count, evenly across the width
    "rib_h": (6.0, 3.0, 8.0),         # rib height above the plate; <= 10 x the thinnest rib_t
    "rib_t": (1.2, 0.8, 1.8),         # rib thickness, under the plate's so it does not sink-mark
}


def build(length, width, plate, ribs, rib_h, rib_t):
    cover = Box(length, width, plate, align=(Align.CENTER, Align.CENTER, Align.MIN))
    run = length / 2 - rib_h          # ribs stop one rib height short of each end
    for i in range(ribs):
        y = width * ((i + 0.5) / ribs - 0.5)
        # Feature: rib along X on the top face.
        cover = rib(cover, (0, y, plate), (-run, y, plate), (run, y, plate), rib_h, rib_t).shape
    cover.label = "cover"
    return cover
