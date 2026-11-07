"""Feature fixture: print_draft. A desk headphone hanger printed upright: the arm's flat
underside would be a ceiling, so print_draft fills under it at the self-supporting slope.

The draft's sloped faces still count in the brief's steep-downward share, so the foot is
sized against the arm: a longer reach needs a bigger foot, which it also needs not to tip."""
from build123d import Align, Box, Pos

from library.engineering import print_draft

PARAMS = {
    # name: (default, min, max)    mm
    "height": (230.0, 180.0, 245.0),  # spine height, a headband clears the desk
    "spine": (22.0, 18.0, 28.0),      # spine and arm width
    "spine_t": (14.0, 10.0, 18.0),    # spine depth
    "reach": (55.0, 45.0, 70.0),      # arm reach from the spine: one headband plus a finger
    "arm_t": (10.0, 8.0, 14.0),       # arm thickness at the tip
    "foot": (120.0, 100.0, 140.0),    # foot plate depth, keeps it from tipping
    "foot_t": (6.0, 5.0, 8.0),        # foot plate thickness
    "foot_w": (100.0, 90.0, 120.0),   # foot plate width; with foot, the bed area that keeps the
                                      # drafted arm's 46 deg underside under the 15 % overhang share
}


def build(height, spine, spine_t, reach, arm_t, foot, foot_t, foot_w):
    hanger = Box(foot_w, foot, foot_t, align=(Align.CENTER, Align.CENTER, Align.MIN))
    hanger += Box(spine, spine_t, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    hanger += Pos(0, spine_t / 2, height - arm_t) * Box(
        spine, reach, arm_t, align=(Align.CENTER, Align.MIN, Align.MIN))
    # Feature: draft under the arm.
    hanger = print_draft(hanger, (0, spine_t / 2 + reach / 2, height - arm_t)).shape
    hanger.label = "headphone_hanger"
    return hanger
