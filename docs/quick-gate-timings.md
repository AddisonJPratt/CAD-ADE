# Quick gate timings (ticket #80)

Budget: `magic.py check <design> --quick` under about 20 s on every starter design.

Measured 2026-11-08 on a 10-core Mac shared with sibling agent sessions running sweeps. The load
average swung between 26 and 420, so wall clock partly measures the queue. Two measurements are
recorded below.

## CPU seconds, one run at a time

These are user + sys seconds of the `magic.py` process and its build worker. A quick run is close
to single-threaded, so this is about its wall time on an idle machine. For comparison, on an idle
machine, `check --no-sweep` on wall_bracket (quick plus renders) took 14.0 s wall for 11.3 s CPU.
A full `magic.py run` on wall_bracket took 71.6 s wall.

| Design | CPU (s) | Wall (s) | Load avg |
|---|---:|---:|---:|
| box_with_lid | 6.7 | 24.9 | 406 |
| cable_clip | 6.5 | 20.3 | 394 |
| cable_spool | 7.4 | 26.3 | 401 |
| doorstop | 7.0 | 19.6 | 408 |
| drawer_tray | 6.9 | 12.8 | 381 |
| gear_pair | 10.0 | 33.8 | 374 |
| holder_clip | 6.6 | 12.2 | 357 |
| holder_cradle | 6.9 | 15.0 | 349 |
| phone_stand | 5.7 | 6.8 | 335 |
| pipe_clamp | 6.6 | 11.1 | 304 |
| planter_pot | 8.2 | 13.3 | 288 |
| project_enclosure | 7.1 | 11.1 | 263 |
| wall_bracket | 7.9 | 15.8 | 223 |

## `tests/test_quick.py --record`, wall clock

Main at 149b5bf. The run started at load 26 and ended at load 226. Quick runs went two at a
time; the test now runs them one at a time. Full runs went four at a time. Quick and full agreed
on every build, geometry and printability verdict.

| Design | Quick (s) | Full (s) | Quick verification | Full verification |
|---|---:|---:|---|---|
| box_with_lid | 24.0 | 45.8 | draft | passed |
| cable_clip | 22.1 | 32.1 | draft | passed |
| cable_spool | 24.6 | 61.9 | draft | passed |
| doorstop | 24.9 | 44.6 | draft | passed |
| drawer_tray | 17.0 | 84.7 | draft | passed |
| gear_pair | 22.3 | 186.0 | draft | passed |
| holder_clip | 16.1 | 46.9 | draft | passed |
| holder_cradle | 16.4 | 109.9 | draft | passed |
| phone_stand | 18.0 | 61.1 | draft | passed |
| pipe_clamp | 17.6 | 51.0 | draft | passed |
| planter_pot | 19.2 | 74.9 | draft | passed |
| project_enclosure | 14.8 | 110.2 | draft | passed |
| wall_bracket | 11.8 | 108.9 | draft | passed |

## Verdict

Every starter needs 6–10 CPU seconds, and an uncontended quick run of three of them took under
20 s wall. On a shared, loaded machine, five starters took 22–25 s. Re-run
`tests/test_quick.py --record docs/quick-gate-timings.md` on a quiet machine to close the wall-clock
criterion. The script asserts the 20 s budget, so read its load-average line before treating a
timing failure as a regression.
