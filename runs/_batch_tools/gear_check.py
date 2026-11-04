"""Out-of-band mesh check: rotate reloaded gear STLs through one pitch of A, report worst gap and overlap."""
import json, subprocess, sys, tempfile, pathlib
sys.path.insert(0, "runs/_batch_tools")
from gap import *
cases = {"default": {}, "tight 18/60 m1 c0.25": {"module": 1.0, "teeth_a": 18, "teeth_b": 60, "flank_clearance": 0.25},
         "tight 18/18 m1 c0.25": {"module": 1.0, "teeth_a": 18, "teeth_b": 18, "flank_clearance": 0.25},
         "36/60 m3 25deg": {"module": 3.0, "teeth_a": 36, "teeth_b": 60, "pressure_angle": 25.0}}
for name, over in cases.items():
    with tempfile.TemporaryDirectory() as t:
        subprocess.run([".venv/bin/python", "-m", "harness.worker", "designs/gear_pair.py", t, json.dumps(over)], check=True)
        res = json.load(open(pathlib.Path(t) / "result.json"))
        p = res["params"]; a = p["module"] * (p["teeth_a"] + p["teeth_b"]) / 2
        worst_gap, worst_ol = 9e9, 0
        for i in range(13):
            phi = i / 12 * 360 / p["teeth_a"]
            A = load(f"{t}/gear_a.stl", rot_z=phi, about=(0, 0, 0))
            B = load(f"{t}/gear_b.stl", rot_z=-phi * p["teeth_a"] / p["teeth_b"], about=(a, 0, 0))
            worst_ol = max(worst_ol, (A ^ B).volume()); worst_gap = min(worst_gap, A.min_gap(B, 5.0))
        print(f"{name}: centre {a}, worst overlap {worst_ol:.3f} mm3, worst gap {worst_gap:.3f} mm over one pitch")
