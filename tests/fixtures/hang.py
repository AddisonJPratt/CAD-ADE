"""Negative control: never returns, so the Execute gate must time out."""
PARAMS = {"size": (20.0, 10.0, 30.0)}


def build(size):
    while True:
        pass
