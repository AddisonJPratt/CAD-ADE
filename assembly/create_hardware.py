"""Generate a simplified M3 socket-head screw reference mesh (dimensions in mm).

It omits the socket and threads. It is an illustrative envelope, not a part for
manufacture or a specification for an actual fastener.
"""
from pathlib import Path
from build123d import Align, Cylinder, Pos, Rot, export_stl


def main():
    # Nominal M3 geometry. Twelve mm under-head length is an illustration only.
    head = Pos(1.5, 0, 0) * Rot(0, 90, 0) * Cylinder(2.75, 3.0, align=(Align.CENTER,)*3)
    shaft = Pos(-6, 0, 0) * Rot(0, 90, 0) * Cylinder(1.5, 12.0, align=(Align.CENTER,)*3)
    out = Path(__file__).parent / 'assets' / 'm3_socket_head.stl'
    export_stl(head + shaft, str(out), tolerance=0.01, angular_tolerance=0.1)


if __name__ == '__main__':
    main()
