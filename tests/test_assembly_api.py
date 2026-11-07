#!/usr/bin/env python
"""The assembly gate through the engine API: it runs after a project's designs and joins the verdict.

    .venv/bin/python tests/test_assembly_api.py

The project is the lid-and-base fixture (tests/fixtures/assembly_stack): two designs that pass
the five gates on their own, joined by an M3 screw into a heat-set insert.
"""
import shutil
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.api import make_server  # noqa: E402
from test_engine_api import Client, check, results  # noqa: E402  (same client and tally)

STACK = ROOT / "tests" / "fixtures" / "assembly_stack"
SAMPLES = 7   # min/default/max of the lid's three params; sweep coverage is tested elsewhere


def project(tmp, name, screw_length=None):
    folder = tmp / name
    shutil.copytree(STACK, folder, ignore=shutil.ignore_patterns("__pycache__", "outputs"))
    if screw_length is not None:
        source = (folder / "assembly.py").read_text()
        (folder / "assembly.py").write_text(source.replace('"screw_length": (6.0,', f'"screw_length": ({screw_length},'))
    return folder


def run(api, folder):
    status, queued = api.json("POST", "/runs", {"project": str(folder), "samples": SAMPLES})
    assert status == 202, queued
    events = api.events(queued["id"])
    _, done = api.json("GET", f"/runs/{queued['id']}")
    return done, events


def test_passing_assembly(api, tmp):
    done, events = run(api, project(tmp, "stack"))
    verdict = done["verdict"]
    check("designs pass their five gates", [d["pass"] for d in verdict["designs"]] == [True, True],
          str([(d["design"], d["pass"]) for d in verdict["designs"]]))
    entry = verdict.get("assembly") or {}
    check("verdict carries the assembly gate, and it passes", entry.get("pass") is True and verdict["pass"],
          str(entry.get("gates")))
    check("the gate reports each of its checks",
          [c["name"] for c in entry["checks"]] == ["Assembly file", "Collisions", "Fasteners", "Derived entries"])
    names = [n for n, _ in events]
    check("assembly runs after the designs, before run_finished",
          names.index("assembly_started") > max(i for i, n in enumerate(names) if n == "design_finished")
          and names.index("assembly_finished") < names.index("run_finished"))
    finished = [d for n, d in events if n == "gate_finished" and d.get("design") == "assembly.py"]
    check("its gate finishes on the stream like any other", [d["gate"] for d in finished] == ["6 Assembly"]
          and finished[0]["status"] == "PASS", str(finished))
    status, _, data = api.request("GET", f"/runs/{done['id']}/artifacts/{entry['report']}")
    check("the assembly report downloads as a run artifact", status == 200 and b'"Fasteners"' in data, str(status))
    check("claims mark the assembly as computed, not physically tested",
          any(c["tier"] == "computed" for c in entry["claims"])
          and any(c["tier"] == "needs physical test" for c in entry["claims"]))


def test_failing_assembly_fails_the_project(api, tmp):
    done, _ = run(api, project(tmp, "long_screw", screw_length=10.0))
    verdict = done["verdict"]
    check("designs still pass on their own", all(d["pass"] for d in verdict["designs"]))
    check("a too-long screw fails the assembly and the project",
          verdict["assembly"]["pass"] is False and verdict["pass"] is False
          and "bottoms out" in verdict["assembly"]["gates"][0]["detail"], verdict["assembly"]["gates"][0]["detail"])


def test_project_without_assembly_is_unchanged(api, tmp):
    folder = project(tmp, "no_assembly")
    (folder / "assembly.py").unlink()
    done, events = run(api, folder)
    check("no assembly file: no assembly gate, verdict as before",
          "assembly" not in done["verdict"] and done["verdict"]["pass"]
          and not any(n.startswith("assembly_") for n, _ in events))


def main():
    server = make_server(port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api = Client(server.server_address[1])
    try:
        with tempfile.TemporaryDirectory(prefix="assembly_api_") as tmp:
            for test in (test_passing_assembly, test_failing_assembly_fails_the_project,
                         test_project_without_assembly_is_unchanged):
                print(f"--- {test.__name__}")
                test(api, Path(tmp))
    finally:
        server.shutdown()
        server.server_close()
    print(f"\n{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
