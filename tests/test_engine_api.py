#!/usr/bin/env python
"""Engine API through its public HTTP seam, against fixture project folders.

    .venv/bin/python tests/test_engine_api.py

Fixture projects are assembled from the harness controls in tests/fixtures/ (one source of
truth for each control): a passing two-part project, and a project holding every negative
control. Each API verdict is compared with what `magic.py run` gives for the same design.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.api import make_server  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
HANG_TIMEOUT = 40  # same per-build timeout tests/run_tests.py gives the hang control
# Negative controls: fixture -> text its report must contain (same needles as tests/run_tests.py).
NEGATIVES = {
    "only_default": "only works at the default",
    "dead_param": "Dead params: extra",
    "hardcoded": "literal 37.5",
    "crash": "kernel exploded",
    "hang": "timeout after",
    "two_bodies": "2 solids, expected 1",
    "overlap_parts": "overlap",
    "ceiling": "support_risk_pct",
    "oversize": "exceeds bed",
    "wrong_dim": "width: measured",
}
results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"{'PASS' if condition else 'FAIL'}  {name}  {detail}")


def make_project(folder, fixtures):
    """A project folder: designs/<fixture>.py plus briefs/<fixture>.yaml where the fixture has one."""
    (folder / "designs").mkdir(parents=True)
    for name in fixtures:
        shutil.copy2(FIXTURES / f"{name}.py", folder / "designs" / f"{name}.py")
        brief = FIXTURES / f"{name}.yaml"
        if brief.exists():
            (folder / "briefs").mkdir(exist_ok=True)
            shutil.copy2(brief, folder / "briefs" / brief.name)
    return folder


class Client:
    def __init__(self, port):
        self.base, self.host = f"http://127.0.0.1:{port}", f"127.0.0.1:{port}"

    def request(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        head = {"Host": self.host, **({"Content-Type": "application/json"} if data else {}),
                **(headers or {})}
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=head)
        try:
            with urllib.request.urlopen(req, timeout=900) as resp:
                return resp.status, resp.headers.get("Content-Type"), resp.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers.get("Content-Type"), err.read()

    def json(self, method, path, body=None, headers=None):
        status, _, raw = self.request(method, path, body, headers)
        return status, json.loads(raw)

    def events(self, run_id, on_event=None):
        """Read the SSE stream to its end. Returns [(event name, data dict)]."""
        req = urllib.request.Request(f"{self.base}/runs/{run_id}/events", headers={"Host": self.host})
        seen, name = [], None
        with urllib.request.urlopen(req, timeout=900) as resp:
            for raw in resp:
                line = raw.decode().rstrip("\n")
                if line.startswith("event: "):
                    name = line[7:]
                elif line.startswith("data: "):
                    seen.append((name, json.loads(line[6:])))
                    if on_event:
                        on_event(name, seen[-1][1])
                    if name == "end":
                        return seen
        return seen


def cli(*args):
    proc = subprocess.run([sys.executable, str(ROOT / "magic.py"), *args], cwd=ROOT,
                          capture_output=True, text=True)
    return proc.returncode


def cli_report(design, *extra):
    """`magic.py run` on one design into a scratch folder: (exit code, report dict)."""
    with tempfile.TemporaryDirectory() as out:
        code = cli("run", str(design), "--out", out, *extra)
        return code, json.loads((Path(out) / "report.json").read_text())


def statuses(gates):
    return [(g["name"], g["status"]) for g in gates]


def test_guards(api, tmp):
    status, body = api.json("GET", "/health")
    check("health names the engine", status == 200 and body["engine"] == "magic-cad", str(body))
    status, _ = api.json("GET", "/health", headers={"Host": "evil.example:80"})
    check("foreign Host header is refused", status == 403, f"status {status}")
    status, _, _ = api.request("POST", "/runs", headers={"Content-Type": "text/plain"})
    check("POST without application/json is refused", status == 415, f"status {status}")
    empty = tmp / "not_a_project"
    empty.mkdir()
    status, body = api.json("POST", "/runs", {"project": str(empty)})
    check("a folder without designs is refused", status == 400 and "no designs" in body["error"], str(body))
    status, _ = api.json("GET", "/runs/" + "0" * 32)
    check("unknown run is 404", status == 404, f"status {status}")


def test_passing_project(api, tmp):
    project = make_project(tmp / "two_parts", ["good_two_parts"])
    status, run = api.json("POST", "/runs", {"project": str(project)})
    check("POST queues a run", status == 202 and run["status"] in ("queued", "running"), str(status))

    live = {}

    def watch(name, data):  # the first gate event must arrive while the run is still going
        if name == "gate_started" and "status" not in live:
            live["status"] = api.json("GET", f"/runs/{run['id']}")[1]["status"]

    events = api.events(run["id"], watch)
    check("gate events stream while the run is in progress", live.get("status") == "running",
          f"status at first gate_started: {live.get('status')}")
    _, done = api.json("GET", f"/runs/{run['id']}")
    verdict = done["verdict"]
    check("passing project: verdict PASS", done["status"] == "done" and verdict["pass"], done["status"])

    names = [n for n, _ in events]
    check("stream is bracketed by run_started ... run_finished, end",
          names[0] == "queued" and names[1] == "run_started" and names[-2:] == ["run_finished", "end"],
          f"{names[:2]} ... {names[-2:]}")
    gates = verdict["designs"][0]["gates"]
    finished = [d["gate"] for n, d in events if n == "gate_finished"]
    check("every gate in the verdict finished exactly once on the stream",
          sorted(finished) == sorted(g["name"] for g in gates), str(finished))
    started = [d["gate"] for n, d in events if n == "gate_started"]
    first = {}
    for i, (n, d) in enumerate(events):
        if n in ("gate_started", "gate_finished"):
            first.setdefault((n, d["gate"]), i)
    order_ok = all(first[("gate_started", g)] < first[("gate_finished", g)] for g in started)
    check("each gate starts before it finishes", order_ok and len(started) == 6, str(started))

    code, report = cli_report(project / "designs" / "good_two_parts.py")
    check("API verdict matches `magic.py run`", code == 0 and report["pass"] == verdict["pass"]
          and statuses(report["gates"]) == statuses(gates), f"cli exit {code}")
    check("`magic.py project` agrees", cli("project", str(project)) == 0)

    # Artifacts: STL, STEP, renders and report, byte-identical to the files in outputs/.
    artifacts = verdict["designs"][0]["artifacts"]
    kinds = {Path(a).suffix for a in artifacts}
    check("artifacts list STL, STEP, PNG, report", {".stl", ".step", ".png", ".json", ".md"} <= kinds,
          str(sorted(kinds)))
    same = True
    for rel in artifacts:
        status, ctype, data = api.request("GET", f"/runs/{run['id']}/artifacts/{rel}")
        same = same and status == 200 and data == (project / "outputs" / rel).read_bytes()
    check("every artifact downloads byte-identical", same, f"{len(artifacts)} files")
    _, ctype, _ = api.request("GET", f"/runs/{run['id']}/artifacts/good_two_parts/a.stl")
    check("STL served as model/stl", ctype == "model/stl", ctype)
    status, _, _ = api.request("GET", f"/runs/{run['id']}/artifacts/../designs/good_two_parts.py")
    status2, _, _ = api.request("GET", f"/runs/{run['id']}/artifacts/good_two_parts/%2e%2e/%2e%2e/designs/good_two_parts.py")
    check("artifacts outside outputs/ are refused", status == 404 and status2 == 404, f"{status} {status2}")

    replay = api.events(run["id"])
    check("a finished run's stream replays the whole history", [n for n, _ in replay] == names)


def test_negative_controls(api, tmp):
    project = make_project(tmp / "negatives", list(NEGATIVES))
    began = time.time()
    status, done = api.json("POST", "/runs", {"project": str(project), "timeout": HANG_TIMEOUT, "wait": True})
    verdict = done["verdict"]
    check("negative-control project: verdict FAIL", status == 200 and done["status"] == "done"
          and not verdict["pass"], f"{time.time() - began:.0f} s")
    by_design = {d["design"]: d for d in verdict["designs"]}
    for name, needle in NEGATIVES.items():
        entry = by_design[f"{name}.py"]
        _, _, md = api.request("GET", f"/runs/{done['id']}/artifacts/{name}/report.md")
        code, report = cli_report(project / "designs" / f"{name}.py", "--timeout", str(HANG_TIMEOUT))
        check(f"negative {name}: fails, says why, matches CLI",
              not entry["pass"] and needle in md.decode() and code == 1
              and statuses(report["gates"]) == statuses(entry["gates"]),
              f"cli exit {code}")


def main():
    server = make_server(port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api = Client(server.server_address[1])
    try:
        with tempfile.TemporaryDirectory(prefix="engine_api_") as tmp:
            tmp = Path(tmp)
            for test in (test_guards, test_passing_project, test_negative_controls):
                print(f"--- {test.__name__}")
                test(api, tmp)
    finally:
        server.shutdown()
        server.server_close()
    print(f"\n{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
