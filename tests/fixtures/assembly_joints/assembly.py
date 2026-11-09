"""Snap-fit box: the cap snaps onto the base on two pegs.

The cap prints top-down, so the assembly turns it over onto the base's rim. The joint is all
the assembly says: `join` finds the face contact, puts the pegs on the cap (which they grow
straight up from as it prints) and the sockets in the base's rim, at the PLA or PETG sliding
clearance from the printer profile.
"""
from build123d import Location

PARAMS = {
    "cap_thickness": (6.0, 3.0, 20.0),   # mm; the pegs grow from the cap, so it need not hold a socket
}


def assemble(asm, cap_thickness):
    base = asm.printed("base", "base_block", name="Base")
    cap = asm.printed("cap", "cap_block", name="Cap", thickness=cap_thickness)
    top = base.shape.bounding_box().max.Z
    asm.place(cap, Location((0, 0, top + cap_thickness), (180, 0, 0)))
    asm.join("snap_fit", "cap", "base")
