"""Attempt 2 for planter_pot: same pot printed rim-down, to test whether orientation clears gate 3."""
import importlib.util, pathlib
from build123d import Axis, Pos
spec = importlib.util.spec_from_file_location("pot", pathlib.Path(__file__).parents[2] / "designs" / "planter_pot.py")
pot = importlib.util.module_from_spec(spec); spec.loader.exec_module(pot)
PARAMS = pot.PARAMS
def build(**params):
    part = Pos(0, 0, params["height"]) * pot.build(**params).rotate(Axis.X, 180)
    part.label = "pot"
    return part
