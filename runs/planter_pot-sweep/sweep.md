# Magic CAD report: planter_pot.py

**Overall: PASS**  
Command: `sweep`  
Brief: `evals/briefs/planter_pot.yaml`  
Parameters: `{"rim_dia": 100.0, "height": 90.0, "taper_deg": 8.0, "wall": 2.4}`

## Checks

| Gate | Status | Detail |
|---|---|---|
| 1 Execute | PASS | built in 6.74 s |
| Sweep | PASS | 15/15 pass; dead params: none |

## Parameter sweep

**15/15 samples pass** (share 100%, required 100%). Dead params: none. Printability, informational: 0/15 pass; worst support risk 25.5 %, worst brief overhang 96.9 %.

| Sample | Result | Volume mm³ | Printable | Problems |
|---|---|---|---|---|
| default | PASS | 77314 | False | - |
| rim_dia=min | PASS | 47110 | False | - |
| rim_dia=max | PASS | 144531 | False | - |
| height=min | PASS | 59379 | False | - |
| height=max | PASS | 106672 | False | - |
| taper_deg=min | PASS | 81435 | False | - |
| taper_deg=max | PASS | 65492 | False | - |
| wall=min | PASS | 51883 | False | - |
| wall=max | PASS | 102258 | False | - |
| all=min | PASS | 26122 | False | - |
| all=max | PASS | 219948 | False | - |
| combo1 | PASS | 282892 | False | - |
| combo2 | PASS | 170214 | False | - |
| combo3 | PASS | 144315 | False | - |
| combo4 | PASS | 65830 | False | - |

## Assumptions surfaced

- Size is a guess for a 10 cm herb pot.
- PLA softens in direct summer sun; use PETG outdoors. Unverified here.
