"""Two blocks whose PARAMS declare unit and intent only in house-style comments (no brief)."""
from build123d import Align, Box, Pos

EXPECTED_SOLIDS = 2
PARAMS = {
    # name: (default, min, max)    all mm
    "size": (20.0, 10.0, 30.0),    # block edge length
    "gap": (1.0, 0.5, 2.0),        # clearance between the blocks
}


def build(size, gap):
    box = Box(size, size, size, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return {"a": box, "b": Pos(size + gap, 0, 0) * box}
