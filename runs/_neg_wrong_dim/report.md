# Magic CAD report: wrong_dim.py

**Overall: FAIL**  
Command: `magic.py check tests/fixtures/wrong_dim.py --brief tests/fixtures/wrong_dim.yaml --out runs/_neg_wrong_dim`  
Brief: `tests/fixtures/wrong_dim.yaml`  
Parameters: `{"width": 60.0}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 6.86 s; no hard-coded literals |
| 2 Geometry | FAIL | width: measured 60.5, spec 60.0 |
| 3 Printability | SKIPPED | - |
| 4 Renders | SKIPPED | - |
| Sweep | SKIPPED | - |
| 5 Exports | SKIPPED | - |

## Measured vs spec (reloaded STEP, ±0.1 mm)

| Dimension | Spec | Measured | Delta | Result |
|---|---|---|---|---|
| width | 60.000 | 60.500 | 0.500 | FAIL |
