"""Dovetail box: the cap slides onto the base along a dovetail in the base's +X rim."""
from build123d import Location

PARAMS = {
    "cap_thickness": (6.0, 3.0, 20.0),   # mm
}


def assemble(asm, cap_thickness):
    base = asm.printed("base", "base_block", name="Base")
    cap = asm.printed("cap", "cap_block", name="Cap", thickness=cap_thickness)
    box = base.shape.bounding_box()
    rim = base.spec["params"]["rim"]
    asm.place(cap, Location((0, 0, box.max.Z + cap_thickness), (180, 0, 0)))
    # Joint frame on the rim's centre line: +Z from the cap down into the base.
    centre = (box.max.X - rim / 2, 0, box.max.Z)
    asm.join("dovetail", cap, base, at=Location(centre, (180, 0, 0)))
