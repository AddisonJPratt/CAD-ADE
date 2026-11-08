# First Proof

> Superseded by Make mode in the Studio app (`studio-app/`, Make tab; engine side in
> `engine/make.py`, tests in `tests/test_make.py`). Makes there are ordinary engine projects
> with versions, so the Shelf, Studio and Mission Control share them. This app is kept, unchanged,
> until Make mode has been used for a real print; its data folder is not migrated.

Start from the project root with `.venv/bin/python proof/server.py`, then open
http://127.0.0.1:8766. The server listens on the local machine only. A make runs
all harness gates and can take several minutes; only a passing run exposes an STL.

The first templates cover round objects 30–50 mm in diameter and rectangular
objects 60–120 mm wide, 20–50 mm deep, and 80–150 mm high. Round-object length
is recorded but does not change the clip. Both templates use M3 screws.

After a physical print, record the outcome on the make's page. Feedback is saved
locally and may adjust the per-side clearance for the next holder of the same
type. Printer settings and initial clearance are placeholders. Geometry checks
and interference tests do not establish insertion force, retention, strength,
fatigue, slicer compatibility, or real-world fit.

Runs and calibration are stored in `proof/`, generated briefs in
`briefs/generated/`, and print outcomes in `prints/PRINT_LOG.md`. Do not record
simulated feedback in the real profile; use isolated directories through
`MAGIC_PROOF_DATA`, `MAGIC_PROOF_BRIEFS`, and `MAGIC_PROOF_PRINT_LOG` for tests.

Run the app tests with `.venv/bin/python -m unittest discover -s proof/tests -v`.
