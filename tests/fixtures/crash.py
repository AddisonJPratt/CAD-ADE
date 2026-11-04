"""Negative control: raises, so the Execute gate must capture the traceback."""
PARAMS = {"size": (20.0, 10.0, 30.0)}


def build(size):
    raise RuntimeError("kernel exploded")
