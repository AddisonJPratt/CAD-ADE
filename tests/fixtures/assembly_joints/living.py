"""A strap folding on its own living hinge: the joint names the web for the gate to measure."""
from build123d import Location

PARAMS = {
    "hinge_x": (0.0, -20.0, 20.0),   # mm along the strap from its centre, where the web is measured
}


def assemble(asm, hinge_x):
    strap = asm.printed("strap", "strap", name="Strap")
    asm.join("living_hinge", strap, at=Location((hinge_x, 0, 0)))
