"""Negative control: builds only at its default, so the sweep must fail."""
from build123d import Box

PARAMS = {"size": (20.0, 10.0, 30.0)}


def build(size):
    if size != PARAMS["size"][0]:
        raise ValueError("only works at the default")
    return Box(size, size, size).moved(Box(size, size, size).location)
