"""Run the worker in a subprocess with a timeout; capture any traceback."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_worker(design, out_dir, params=None, timeout=180):
    """Return the worker's result dict; ok=False with a traceback on any failure."""
    out_dir = Path(out_dir)
    cmd = [sys.executable, "-m", "harness.worker", str(Path(design).resolve()), str(out_dir),
           json.dumps(params or {})]
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "traceback": f"timeout after {timeout} s", "seconds": timeout}
    seconds = round(time.time() - started, 2)
    result_file = out_dir / "result.json"
    if not result_file.exists():
        return {"ok": False, "seconds": seconds,
                "traceback": f"worker died (exit {proc.returncode}):\n{proc.stderr[-2000:]}"}
    result = json.loads(result_file.read_text())
    result["seconds"] = seconds
    return result
