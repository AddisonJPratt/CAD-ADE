"""Press-fit box: the cap presses onto the base on two pins, at the profile's press clearance."""
from build123d import Location

PARAMS = {
    "cap_thickness": (6.0, 3.0, 20.0),   # mm
}


def assemble(asm, cap_thickness):
    base = asm.printed("base", "base_block", name="Base")
    cap = asm.printed("cap", "cap_block", name="Cap", thickness=cap_thickness)
    top = base.shape.bounding_box().max.Z
    asm.place(cap, Location((0, 0, top + cap_thickness), (180, 0, 0)))
    asm.join("press_fit", "cap", "base")
