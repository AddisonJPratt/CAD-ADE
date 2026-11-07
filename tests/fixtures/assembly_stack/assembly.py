"""Assembly fixture: the lid screwed to the base through one M3 heat-set insert.

The defaults pass the assembly gate. The negative controls override one value each:
lid_gap below zero sinks the lid into the boss, a long screw bottoms out in the
insert hole, and lid_clearance set to the tap drill leaves no clearance for the shank.
"""
from assembly.model import insert_mouths, seats
from library import standard_parts

M3 = standard_parts()["screws"]["M3"]

PARAMS = {
    "screw_length": (6.0, 4.0, 16.0),                   # mm under the head; 6 engages the insert, 0.8 mm grip
    "lid_gap": (0.0, -2.0, 2.0),                        # mm from boss top to lid underside; < 0 overlaps
    "lid_clearance": (M3["clearance"], M3["tap"], M3["head_dia"]),  # mm, the lid's through hole
}


def assemble(asm, screw_length, lid_gap, lid_clearance):
    base = asm.printed("base", "base", name="Base plate")
    lid = asm.printed("lid", "lid", name="Lid", clearance=lid_clearance)
    boss_top = base.shape.bounding_box().max.Z
    asm.place(lid, (0, 0, boss_top + lid_gap))
    insert = asm.insert("insert", "M3", name="M3 heat-set insert")
    asm.press(insert, base, insert_mouths(base, "M3")[0])
    screw = asm.screw("screw", "M3", screw_length, name="M3 screw")
    asm.fasten(screw, lid, seats(lid, "M3")[0], insert=insert)
