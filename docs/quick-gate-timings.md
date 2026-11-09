# Quick gate timings (ticket #80)

Budget: `magic.py check <design> --quick` under about 20 s on every starter design.

Measured 2026-11-08 on a 10-core Mac. Sibling agent sessions were running sweeps at the time, so the
load average was 220–410. Wall clock under that load measures the queue, not the gate. The table
therefore also records CPU seconds (user + sys of the `magic.py` process and its build worker).
The quick run is close to single-threaded, so CPU time is about its wall time on an idle machine.
In an idle reference run, `check --no-sweep` on wall_bracket (quick plus renders) took
14.0 s wall for 11.3 s CPU.

Runs went one at a time:

| Design | CPU (s) | Wall under load (s) | Load avg | Result |
|---|---:|---:|---:|---|
| box_with_lid | 6.7 | 24.9 | 406 | FAIL: 2 solids, expected 1 (full run agrees) |
| cable_clip | 6.5 | 20.3 | 394 | PASS (draft) |
| cable_spool | 7.4 | 26.3 | 401 | PASS (draft) |
| doorstop | 7.0 | 19.6 | 408 | PASS (draft) |
| drawer_tray | 6.9 | 12.8 | 381 | PASS (draft) |
| gear_pair | 10.0 | 33.8 | 374 | PASS (draft) |
| holder_clip | 6.6 | 12.2 | 357 | PASS (draft) |
| holder_cradle | 6.9 | 15.0 | 349 | PASS (draft) |
| phone_stand | 5.7 | 6.8 | 335 | FAIL (full run agrees) |
| pipe_clamp | 6.6 | 11.1 | 304 | PASS (draft) |
| planter_pot | 8.2 | 13.3 | 288 | PASS (draft) |
| project_enclosure | 7.1 | 11.1 | 263 | PASS (draft) |
| wall_bracket | 7.9 | 15.8 | 223 | PASS (draft) |

For comparison, a full `magic.py run` of wall_bracket on the idle machine took 71.6 s wall.
Under the same load, full runs of the starters took 47–169 s.

Re-measure on a quiet machine with `.venv/bin/python tests/test_quick.py --record <file>`. That
script asserts the 20 s wall budget, so it fails when the machine is saturated. Read its load
average line before treating a timing failure as a regression.
