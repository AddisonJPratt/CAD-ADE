# Assemblies

## Assembly file and gate

An assembly file is Python with a `PARAMS` table (same `(default, min, max)` form and
the same no-literals lint as a design) and `assemble(asm, **params)`. It declares:

- printed part instances, each built from its own parametric design: `asm.printed(id, stem, **params)`
- library hardware from `library/standard_parts.json`: `asm.screw(id, "M3", length)`, `asm.insert(id, "M3")`
- purchased components from the catalogue: `asm.component(id, "esp32-devkitc-v4")`
- placements, `asm.place(instance, (x, y, z))`, and connections made with build123d
  `RigidJoint`s: `asm.press(insert, host, mouth)` and `asm.fasten(screw, host, seat, insert=... | into="substrate")`

`model.seats(part, "M3")` and `model.insert_mouths(part, "M3")` find screw-head seats and
insert holes on the built part, so an assembly never repeats a design's hole positions.
See `holder_clip.py` (the demo below as an assembly file) and
`tests/fixtures/assembly_stack/assembly.py` (a lid screwed into a heat-set insert).

`assembly/gate.py` checks, in a subprocess:

| Check | Rule |
|---|---|
| Assembly file | lint passes; every instance builds and every joint connects |
| Collisions | no instance pair overlaps by more than 0.1 mm³, except an insert in its host and a screw in its insert |
| Fasteners | clearance hole from the ISO 273 medium clearance to that + 2 × the sliding fit; into an insert, at least 1.5 × the thread diameter engaged and the tip short of the hole floor and the insert hole's depth; into a substrate, the screw reaches past the part (and no further than `max_depth`, when given) |
| Joints | each part-to-part joint's measured gap is its material's profile clearance; see Joints below |
| Derived entries | the parts list and assembly order are derived from the assembly; each names every instance exactly once |

The fastener rules are uncalibrated starting values, like the clearance table in
`CLAUDE.md`. Hardware is a simplified envelope (no threads or sockets): a PASS is a
computed check, not a physical assembly test.

```
.venv/bin/python magic.py assembly assembly/holder_clip.py --project .
.venv/bin/python magic.py assembly tests/fixtures/assembly_stack/assembly.py
```

### Joints (#54)

`asm.join(kind, a, b)` joins two printed parts. The joint lives in the assembly file: its geometry
(`library/joints.py`, sizes in `library/joints.json`) is added to and cut from the two parts at
assembly time, in each part's print frame, so neither design repeats it.

| Joint | Fit class | Geometry | Placed |
|---|---|---|---|
| `snap_fit` | sliding | split barbed peg on one part, grooved socket in the other | sites found on the face contact |
| `press_fit` | press | chamfered pin, cone-ended hole | sites found on the face contact |
| `dovetail` | sliding | tail and a socket that runs out of the part | `at=` frame |
| `print_in_place_hinge` | print-in-place | three cone-interface knuckles, printed assembled | `at=` frame |
| `living_hinge` | (web thickness) | the design's own notch (`living_hinge_notch`) | `at=` under the web |
| `screw_insert` | sliding (clearance hole) | heat-set inserts and screws through matching seats | the parts' own holes |

The clearance is the project's material's per-side value for the joint's fit class from the
printer profile (the CLAUDE.md table), never a number in the assembly file. Without `at=`, a
snap-fit or press fit uses the largest face-to-face contact between the parts, puts its sites at
least a socket and a wall inside the contact's edges with enough of the socket's part behind them,
as far apart as it can, and puts the peg on the part it grows straight up from as printed.
Every mating surface is vertical or at the 44° print slope, so sockets print opening up or down.

The gate's **Joints** check, per joint:

| Rule | |
|---|---|
| Fit | the gap between the two parts around each site, measured with manifold3d `min_gap` on meshes reloaded from STL, is the profile clearance for the joint's fit class within 2 × the STL tolerance |
| Printability | the joint adds no more unsupported overhang to either part, in its print frame, than `print_rules.overhang_tolerance_mm2` |
| Snap-fit | prong root strain (D-section far fibre, 3·c·d/L²) under the layer-bond `max_strain`; barb taller than the clearance (it retains); slot wide enough for the prongs to close |
| Living hinge | web, measured through the part, two to four layers at the profile's 0.2 mm process; PLA carries a fatigue note |
| Print-in-place hinge | turned each way in 5° steps on reloaded meshes, the leaves stay clear (≤ 0.1 mm³ overlap) through the declared swing |
| Screw + insert | the fastener rules above |

Each joint adds a claim at the `needs physical test` tier until a print result (#15's calibration
events, `engine/make.py`) rates that joint type in that material; it is then `physically tested`,
PASS only if the latest rating was perfect. The
manifest carries part-to-part joints with their `fit` (class, material, clearance, measured gap,
tier); the child (the part declared later) explodes back along the way it went on, except a
print-in-place hinge's leaf, which prints assembled. `tests/fixtures/assembly_joints` has one
assembly file per joint type.

In Studio, pick a face on each of two parts and ask "Join these two parts with a snap-fit" (or a
press fit): `engine/joins.py` proposes the one-line `assembly.py` edit and previews the assembly
through this gate before anything is kept.

### Parts list

`assembly/parts_list.py` turns the gate's derived rows into the parts list: printed parts
(design and parameters), hardware with size and length, and purchased components with their
source link and dimension provenance, each with a quantity and the instances it covers. It is
never edited by hand. The gate writes it beside its report as `parts_list.csv` and
`parts_list.json`; the engine API serves the current assembly's list at
`GET /projects/parts-list?project=<folder>[&format=csv]`, and Mission Control shows it.

A project folder with an `assembly.py` runs the gate after its designs (`magic.py project`,
or POST `/runs` on the engine API); its verdict carries an `assembly` entry, gate
`6 Assembly`, and passes only if the assembly does. The report is `outputs/_assembly/report.json`.

## Assembly manifest

Next to its report, the gate writes the **assembly manifest**, `assembly.json`
(schema `manifest.schema.json`), plus `meshes/<id>.stl` for each instance in that instance's
local frame. It's written for every assembly that builds, pass or fail. Studio, the parts list
and the instructions read only this file (ADR 0001):

- the instances, each with a parent in the tree and a transform (position plus quaternion
  `[x, y, z, w]`, in the assembly frame)
- the joints derived from `fasten` / `press`: `fastener` and `press` (prismatic along the
  hardware axis), and `clamp` (a part screwed onto another part through an insert)
- the explode offsets, derived by the rule in `manifest.py`'s docstring
- the steps, each with its joints, tool and hardware callout
- the parts list, provenance hashes and disclaimer

`tests/fixtures/assembly_manifest/holder_clip.json` is the holder's manifest, committed so
Studio can be built without running CAD. If a design or the rule changes, the fixture test
fails. Review the diff, then refresh it:

```
XDG_CACHE_HOME=/tmp/cad-ade-cache .venv/bin/python -m assembly.manifest --refresh-fixture
```

## Assembly instructions

`assembly/instructions.py` turns the manifest into build instructions, in one of two styles
the user picks:

- **illustrated** (default): one section per step with a rendered image of that stage (what is
  already built in grey, the parts this step adds in Studio's orange, backed out along their joint
  with dashed arrows to their seats), the step text, the hardware callout (e.g. `2 × M3
  socket-head screw, 12 mm`) and the tool;
- **checklist**: one compact row per step with a tick box and the same text, callout and tool.

Both render one step list (`instructions.steps`) read from the manifest's `steps`, so they agree
step for step and cannot drift from the CAD. Every stage uses one camera, chosen per document as
the corner view that shows the most of the parts being added. Each export is a standalone HTML
file (images inline, no network) plus a PDF printed from that same file by headless
Chrome/Chromium (found on the usual paths or Playwright's cache, or set `MAGIC_CHROME`).

```
.venv/bin/python magic.py assembly assembly/holder_clip.py --project . --out runs/holder_clip-assembly
.venv/bin/python magic.py instructions runs/holder_clip-assembly [--style checklist] [--out dir] [--no-pdf]
```

`samples/` holds the holder's instructions in both styles, generated this way, for review.
The steps inherit the manifest's disclaimer: they illustrate the assembly, they are not a
physically tested procedure.

## Illustrative demo

`demo.get_demo(project_root)` is one **illustrative, read-only example**, not a general
assembly solver. It returns a millimetre-space description containing
three named instances, their mesh URLs, assembled translations and exploded
offsets, a bill of materials, and an ordered illustrative sequence. Rendering
or interpolating those vectors is not a collision-checked tool path, a motion
simulation, or a validated physical assembly procedure. `holder_clip.py` expresses
the same assembly as an assembly file; `test_assembly.py` checks that the gate places
the screws exactly where the demo shows them.

The clip mesh and STEP originate from the `runs/holder_clip` full run. Two M3
screw meshes are simplified envelopes with a nominal 12 mm under-head length;
threads, sockets, and the wall are not modeled. The screw length and mounting
substrate must be selected for the actual build. Fit, insertion, retention,
strength and durability have not been physically verified.

`demo_hashes.json` pins the holder source, relevant library files, brief, report,
STEP and mesh, plus the screw mesh and generator, to this example. A changed or
missing source or artifact is surfaced as a warning; missing or changed meshes
are flagged unavailable. This snapshot detects later changes but does not prove
original artifact provenance. Rerunning or modifying the design requires a new
review of placements and updating the snapshot; do not just replace the hashes.

Run tests from the project root:

```
XDG_CACHE_HOME=/tmp/cad-ade-cache .venv/bin/python -m unittest assembly.test_demo assembly.test_assembly assembly.test_manifest assembly.test_instructions -v
.venv/bin/python tests/test_assembly_api.py
```

The demo tests validate the structural contract, source drift behavior, and static
interference between the screw envelopes and the holder reloaded from its STEP.
