"""Negative control: a dimension outside PARAMS, so the contract lint must fail."""
from build123d import Box

PARAMS = {"size": (20.0, 10.0, 30.0)}


def build(size):
    return Box(size, size, 37.5)
