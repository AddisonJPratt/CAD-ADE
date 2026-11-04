# Build log

**build123d, not CadQuery, for Phase 1.** Its Python-native algebra API keeps designs short and
readable, and it runs on the same OpenCascade kernel with STEP export. The doc's bake-off on five
eval parts has not been run; revisit this choice when those designs exist.

## Decisions

- **Subprocess per build:** timeouts and kernel crashes stay contained. Importing build123d costs
  7-15 s under load, which dominates sweep time (31 samples, about 3.6 min on 4 cores).
- **The brief says how to measure** (`measures`), so a design can't report its own dimensions.
  Holes are found from cylindrical faces on the reloaded STEP.
- **Print orientation for the bracket:** shelf face down. No supports, flat wall and shelf faces,
  counterbores open upward or sideways. Teardrop wall holes (44° flanks) remove crown overhang.
  Tradeoff: layers cross the wall leg; see README.
- **Added beyond the brief:** contract lint for hard-coded literals, dead-param detection,
  `support_risk_pct`, bed-contact check, STEP and STL volume cross-checks, negative-control fixtures.
  All make gates stricter. No gate was loosened to pass.
- **Exports last:** a failing design leaves no STL or STEP that looks approved.

## What the checks caught during the build

1. The lint failed my first bracket for selection tolerances (0.001). Fixed the design: edges are
   now chosen by nearest expected position.
2. The dead-param check wrongly failed hole spacing: moving a symmetric hole pair changes neither
   volume nor bbox. Fixed the fingerprint by adding mesh second moments. `tests/fixtures/dead_param.py`
   still fails as it should.
3. The positive control then failed the same check: `gap` only moves a part. Added bbox position.
4. The wall estimate read about half a pixel per side high, found by calibrated-slab tests.
   Corrected the distance transform offset.

## Kernel and library notes

- build123d 0.13: `shape.fillet(radius, edges)`; the algebra `fillet()` has no `target`. `is_valid` is a property.
- The venv has scipy (trimesh `body_count` works) but no networkx, rtree or shapely. Use
  `trimesh.intersections.mesh_plane` for sections and rasterize them directly.
- The thinnest-section estimate reads ~4.0 mm on the bracket; the actual floor under the screw head
  is 3.8 mm by construction.

## Independent verification

Separately from the harness, exported `bracket.step` and `bracket.stl` were reloaded in a fresh process.
All 13 point-in-solid probes passed: through bores, floors, counterbores, teardrop tips and gusset.

## Phase 1.5: eval runner and MCP wrapper

- **`--no-sweep` added to `check`.** The brief wants `--quick` to use "check semantics and skip the
  sweep", but `check` includes the sweep. The flag is opt-in, refused with `run` and `sweep`, and
  reports the gate as NOT RUN. Default `run` and `check` are unchanged, and `only_default` still
  fails without the flag.
- **The eval runner trusts no single signal.** PASS needs exit 0, a well-formed report saying pass,
  and every gate satisfied; any disagreement is ERROR. In a full run a NOT RUN sweep is not a pass.
- **`run_check` looks for briefs in `evals/briefs/` too.** `magic.py` only looks in `briefs/`, so an
  eval design would otherwise pass without its hard dimensions being checked.
- **`min_gap` clamps to `search_length`,** so the tool searches past the combined bounding-box
  diagonal. It also reports a nested part's surface distance as a clearance, so any overlap volume
  forces the gap to 0.
- **Timeouts kill the process group.** `subprocess.run(timeout=)` leaves workers alive and can block
  on their pipes.
