"""The stack fixture's lid joined to its base by a screw into a heat-set insert, as one joint.

Evaluate with tests/fixtures/assembly_stack as the project.
"""
PARAMS = {
    "screw_length": (6.0, 4.0, 16.0),   # mm under the head; 6 engages the insert
}


def assemble(asm, screw_length):
    base = asm.printed("base", "base", name="Base plate")
    lid = asm.printed("lid", "lid", name="Lid")
    asm.place(lid, (0, 0, base.shape.bounding_box().max.Z))
    asm.join("screw_insert", lid, base, size="M3", length=screw_length)
