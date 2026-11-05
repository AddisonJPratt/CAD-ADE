#!/usr/bin/env python
"""Regenerate the Studio test fixtures: one STL per part of every passing run, from its committed STEP.

    .venv/bin/python ui/tests/make_fixtures.py

STLs are not committed under runs/ (a fresh clone has only the STEP files), so the Studio framing and
shadow tests read these fixtures instead. They use the harness's own STL tolerances, so they are the
meshes a `magic.py run` would have written. Rerun after a design's committed STEP changes.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from harness.worker import STL_ANGULAR, STL_TOLERANCE  # noqa: E402

OUT = ROOT / "ui" / "tests" / "fixtures" / "models"


def passing_runs():
    for folder in sorted((ROOT / "runs").iterdir()):
        report = folder / "report.json"
        if folder.name.startswith("_") or not report.is_file():
            continue
        steps = sorted(folder.glob("*.step"))
        if steps and json.loads(report.read_text()).get("pass") is True:
            yield folder.name, steps


def main():
    from build123d import export_stl, import_step
    # Build beside the old set and swap at the end, so a failure leaves the committed fixtures intact.
    staging = OUT.with_name(OUT.name + ".new")
    if staging.exists():
        shutil.rmtree(staging)
    for name, steps in passing_runs():
        (staging / name).mkdir(parents=True)
        for step in steps:
            export_stl(import_step(str(step)), str(staging / name / f"{step.stem}.stl"),
                       tolerance=STL_TOLERANCE, angular_tolerance=STL_ANGULAR)
        print(f"{name}: {', '.join(s.stem for s in steps)}")
    if OUT.exists():
        shutil.rmtree(OUT)
    staging.rename(OUT)


if __name__ == "__main__":
    main()
