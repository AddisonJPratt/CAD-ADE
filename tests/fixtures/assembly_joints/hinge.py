"""Two leaves on a print-in-place hinge: printed together, flat, the hinge axis upright."""
from build123d import Location

from library.joints import spec

HINGE = spec("print_in_place_hinge")

PARAMS = {
    "leaf_length": (30.0, 15.0, 80.0),   # mm
}


def assemble(asm, leaf_length):
    left = asm.printed("left", "leaf", name="Left leaf", length=leaf_length)
    right = asm.printed("right", "leaf", name="Right leaf", length=leaf_length)
    # Each leaf's inner edge sits halfway along its spine, clear of the other leaf's knuckle.
    edge = (HINGE["knuckle_dia"] / 2 + HINGE["spine"]) / 2
    asm.place(left, (-(edge + leaf_length / 2), 0, 0))
    asm.place(right, (edge + leaf_length / 2, 0, 0))
    asm.join("print_in_place_hinge", left, right, at=Location())
