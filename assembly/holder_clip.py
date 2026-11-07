"""The 38 mm wall clip held by two M3 socket-head screws: the assembly demo as an assembly file.

Evaluate it with the repository root as the project (its designs/ folder holds the clip):

    .venv/bin/python magic.py assembly assembly/holder_clip.py --project .

The wall is not modelled. The screws pass through the clip's back plate into the mounting
substrate, so the gate checks the clip's own clearance holes and head recesses, and that
each screw reaches past the plate. The screw length is the demo's illustrative choice, not
a verified fastener specification.
"""
from assembly.model import seats

PARAMS = {
    "screw_length": (12.0, 8.0, 20.0),   # mm under the head; the demo's example length
}


def assemble(asm, screw_length):
    clip = asm.printed("clip", "holder_clip", name="Wall clip")
    for number, seat in enumerate(seats(clip, "M3"), 1):
        screw = asm.screw(f"screw_{number}", "M3", screw_length, name=f"M3 screw {number}")
        asm.fasten(screw, clip, seat, into="substrate")
