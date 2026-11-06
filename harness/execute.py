"""Run the worker in a subprocess with a timeout; capture any traceback."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_worker(design, out_dir, params=None, timeout=180, cancel_event=None):
    """Return the worker's result dict; ok=False with a traceback on any failure."""
    out_dir = Path(out_dir)
    cmd = [sys.executable, "-m", "harness.worker", str(Path(design).resolve()), str(out_dir),
           json.dumps(params or {})]
    started = time.time()
    try:
        if cancel_event is None:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
            stderr = proc.stderr
        else:
            with subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
                while True:
                    if cancel_event.is_set():
                        proc.kill()
                        proc.communicate()
                        return {"ok": False, "interrupted": True, "traceback": "interrupted"}
                    remaining = timeout - (time.time() - started)
                    if remaining <= 0:
                        proc.kill()
                        proc.communicate()
                        raise subprocess.TimeoutExpired(cmd, timeout)
                    try:
                        _, stderr = proc.communicate(timeout=min(0.2, remaining))
                        break
                    except subprocess.TimeoutExpired:
                        pass
    except subprocess.TimeoutExpired:
        return {"ok": False, "traceback": f"timeout after {timeout} s", "seconds": timeout}
    seconds = round(time.time() - started, 2)
    result_file = out_dir / "result.json"
    if not result_file.exists():
        return {"ok": False, "seconds": seconds,
                "traceback": f"worker died (exit {proc.returncode}):\n{stderr[-2000:]}"}
    result = json.loads(result_file.read_text())
    result["seconds"] = seconds
    return result
