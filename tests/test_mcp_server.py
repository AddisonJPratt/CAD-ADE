#!/usr/bin/env python
"""magic-cad MCP server: tools called directly, then once over real stdio. No CAD build; about 30 s
(the STEP probe imports build123d, and run_check fixtures start the harness).

    .venv/bin/python tests/test_mcp_server.py
"""
import asyncio
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import trimesh

SERVER_FILE = ROOT / "mcp" / "magic_cad_server.py"
spec = importlib.util.spec_from_file_location("magic_cad_server", SERVER_FILE)
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)

BRACKET_STL = "ui/tests/fixtures/models/wall_bracket/bracket.stl"   # committed; runs/ STLs aren't
BRACKET_STEP = "runs/wall_bracket/bracket.step"
BRACKET_VOLUME = 78220.0

TOOLS = {"list_designs", "list_eval_briefs", "run_check", "measure_file", "min_gap",
         "library_lookup", "eval_status"}

results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"{'PASS' if condition else 'FAIL'}  {name}  {detail}")


def code_of(result):
    result = getattr(result, "structured_content", result)   # run_check returns a CallToolResult
    return (result.get("error") or {}).get("code")


def test_listing():
    designs = srv.list_designs()
    bracket = next(d for d in designs["designs"] if d["name"] == "wall_bracket")
    check("list_designs: bracket has its brief", bracket["has_brief"] and bracket["brief_path"] == "briefs/wall_bracket.yaml")
    briefs = srv.list_eval_briefs()
    by_name = {b["name"]: b for b in briefs["briefs"]}
    # The corpus ships real files (symlink handling itself is covered in tests/test_evals.py).
    check("list_eval_briefs: wall_bracket found with its design", "wall_bracket" in by_name
          and by_name["wall_bracket"]["design_present"] and not by_name["wall_bracket"]["is_symlink"])
    check("list_eval_briefs: at least the 11 founding briefs listed", briefs["total"] >= 11, str(briefs["total"]))
    check("list_eval_briefs: counts", briefs["total"] == len(list((ROOT / "evals/briefs").glob("*.yaml"))),
          f"{briefs['designs_present']}/{briefs['total']}")


def test_measure():
    stl = srv.measure_file(BRACKET_STL)
    check("measure_file: STL volume within 1 %", abs(stl["volume_mm3"] - BRACKET_VOLUME) <= 0.01 * BRACKET_VOLUME,
          f"{stl['volume_mm3']:.1f}")
    check("measure_file: STL mesh facts", stl["watertight"] is True and stl["components"] == 1)
    check("measure_file: bbox size", [round(s, 3) for s in stl["bbox_mm"]["size"]] == [80.0, 60.0, 80.0], str(stl["bbox_mm"]["size"]))
    step = srv.measure_file(BRACKET_STEP)
    check("measure_file: STEP volume agrees", abs(step.get("volume_mm3", 0) - BRACKET_VOLUME) <= 0.01 * BRACKET_VOLUME
          and step["solids"] == 1 and step["valid"], str(step)[:200])


def test_paths():
    for label, raw in {"../": "../secret.stl", "nested ../": "runs/../../secret.stl", "absolute": "/etc/passwd"}.items():
        check(f"measure_file rejects {label}", code_of(srv.measure_file(raw)) == "path_outside_project")
    check("min_gap rejects ../", code_of(srv.min_gap("../a.stl", BRACKET_STL)) == "path_outside_project")
    check("min_gap rejects ../ second arg", code_of(srv.min_gap(BRACKET_STL, "../a.stl")) == "path_outside_project")
    escape = srv.run_check("../evil.py").structured_content
    check("run_check rejects ../ as structured failure", escape["pass"] is False and code_of(escape) == "path_outside_project")
    check("NUL byte is a structured error", code_of(srv.measure_file("a\x00b.stl")) == "invalid_path")
    check("missing file is a structured error", code_of(srv.measure_file("runs/nothing.stl")) == "not_found")
    check("directory is not a file", code_of(srv.measure_file("")) == "not_found")
    with tempfile.TemporaryDirectory(dir=ROOT / "runs", prefix="_mcp_test_") as tmp:
        link = Path(tmp) / "link.stl"
        link.symlink_to("/etc/passwd")
        check("symlink leaving the project is rejected", code_of(srv.measure_file(str(link))) == "path_outside_project")
        text = Path(tmp) / "notes.txt"
        text.write_text("hello")
        check("unknown file type is rejected", code_of(srv.measure_file(str(text))) == "unsupported_type")
        junk = Path(tmp) / "junk.stl"
        junk.write_text("not an stl")
        check("corrupt STL is a structured error", "error" in srv.measure_file(str(junk)))


def save_box(folder, name, size, centre):
    path = Path(folder) / name
    box = trimesh.creation.box(size)
    box.apply_translation(centre)
    box.export(path)
    return str(path)


def test_min_gap():
    with tempfile.TemporaryDirectory(dir=ROOT / "runs", prefix="_mcp_test_") as tmp:
        a = save_box(tmp, "a.stl", (10, 10, 10), (0, 0, 0))
        near = save_box(tmp, "near.stl", (10, 10, 10), (12.5, 0, 0))
        far = save_box(tmp, "far.stl", (10, 10, 10), (500, 0, 0))
        touch = save_box(tmp, "touch.stl", (10, 10, 10), (10, 0, 0))
        overlap = save_box(tmp, "overlap.stl", (10, 10, 10), (9, 0, 0))
        inner = save_box(tmp, "inner.stl", (2, 2, 2), (0, 0, 0))
        result = srv.min_gap(a, near)
        check("min_gap: 2.5 mm gap", abs(result["gap_mm"] - 2.5) < 1e-4 and result["overlap_volume_mm3"] == 0, str(result["gap_mm"]))
        result = srv.min_gap(a, far)
        check("min_gap: 490 mm is not clamped", abs(result["gap_mm"] - 490) < 1e-3, str(result["gap_mm"]))
        result = srv.min_gap(a, touch)
        check("min_gap: touching reads 0", abs(result["gap_mm"]) < 1e-4, str(result["gap_mm"]))
        result = srv.min_gap(a, overlap)
        check("min_gap: overlap reads 0 with a volume", result["gap_mm"] == 0 and abs(result["overlap_volume_mm3"] - 100) < 1e-2,
              str(result["overlap_volume_mm3"]))
        result = srv.min_gap(a, inner)
        check("min_gap: nested part reads 0, not its wall distance", result["gap_mm"] == 0 and abs(result["overlap_volume_mm3"] - 8) < 1e-3,
              str(result))
        check("min_gap: STEP is refused", code_of(srv.min_gap(a, BRACKET_STEP)) == "unsupported_type")


def test_library():
    found = srv.library_lookup("608")
    check("library_lookup: 608 bearing", any(m["category"] == "bearings" and m["name"] == "608" and m["entry"]["od"] == 22.0
                                             for m in found["matches"]))
    check("library_lookup: case-insensitive", srv.library_lookup("nema")["matches"][0]["name"] == "NEMA17")
    names = {(m["category"], m["name"]) for m in srv.library_lookup("m3")["matches"]}
    check("library_lookup: finds values too", {("screws", "M3"), ("heatset_inserts", "M3"), ("motor_mounts", "NEMA17")} <= names, str(names))
    check("library_lookup: category key returns entries", srv.library_lookup("bearings")["count"] == 1)
    check("library_lookup: no match is empty", srv.library_lookup("zzzz") == {"query": "zzzz", "count": 0, "matches": []})
    check("library_lookup: blank query refused", code_of(srv.library_lookup("  ")) == "empty_query")
    fits = srv.library_lookup("fits")["matches"]
    check("library_lookup: plain-value category returns its values, not its notes",
          {m["name"] for m in fits} == {"sliding", "press", "print_in_place"}, str([m["name"] for m in fits]))


def test_eval_status():
    saved = srv.RESULTS_DIR
    try:
        with tempfile.TemporaryDirectory(dir=ROOT / "runs", prefix="_mcp_test_") as tmp:
            srv.RESULTS_DIR = Path(tmp)
            check("eval_status: no run yet", srv.eval_status()["status"] == "no_eval_run")
            run = Path(tmp) / "20260101-000000"
            run.mkdir()
            (run / "eval_report.json").write_text(json.dumps({"generated_at": "t", "summary": {"mode": "full"},
                                                              "briefs": [{"name": "a", "status": "PASS"}]}))
            status = srv.eval_status()
            check("eval_status: reads the report", status["status"] == "ok" and status["briefs"][0]["status"] == "PASS")
            (run / "eval_report.json").write_text("{broken")
            check("eval_status: corrupt report is structured", code_of(srv.eval_status()) == "malformed_report")
    finally:
        srv.RESULTS_DIR = saved


def test_run_check_failures():
    check("run_check: unknown design", code_of(srv.run_check("no_such_design")) == "design_not_found")
    check("run_check: not python", code_of(srv.run_check(BRACKET_STL)) == "design_not_found")
    saved = srv.run_harness
    out = ROOT / "runs" / "hang-check"
    try:
        result = srv.harness_check("tests/fixtures/hang.py", timeout=2)
        check("run_check: timeout is structured and prompt", code_of(result) == "timeout" and result["pass"] is False
              and result["seconds"] < 10, str(result["seconds"]))

        out.mkdir(exist_ok=True)
        (out / "report.json").write_text(json.dumps({"pass": True, "gates": []}))
        srv.run_harness = lambda args, timeout: {"returncode": -11, "stdout": "", "stderr": "segfault", "timed_out": False,
                                                 "error": None, "seconds": 1.0}
        result = srv.harness_check("tests/fixtures/hang.py")
        check("run_check: crash is structured, old report ignored", code_of(result) == "harness_crashed"
              and result["pass"] is False and "segfault" in result["error"]["message"])

        def writes(report, code):
            def fake(args, timeout):
                (out / "report.json").write_text(report)
                return {"returncode": code, "stdout": "", "stderr": "", "timed_out": False, "error": None, "seconds": 1.0}
            return fake

        srv.run_harness = writes("{broken", 1)
        check("run_check: unreadable report", code_of(srv.harness_check("tests/fixtures/hang.py")) == "harness_crashed")
        srv.run_harness = writes(json.dumps({"pass": True}), 0)
        check("run_check: report without gates", code_of(srv.harness_check("tests/fixtures/hang.py")) == "malformed_report")
        srv.run_harness = writes(json.dumps({"pass": True, "gates": []}), 1)
        check("run_check: exit and report disagree", code_of(srv.harness_check("tests/fixtures/hang.py")) == "inconsistent_result")
        srv.run_harness = lambda args, timeout: {"returncode": None, "stdout": "", "stderr": "", "timed_out": False,
                                                 "error": "could not start harness", "seconds": 0.0}
        check("run_check: unstartable harness", code_of(srv.harness_check("tests/fixtures/hang.py")) == "harness_error")

        calls = []
        quick_out = ROOT / "runs" / "hang-quick"

        def quick_fake(args, timeout):
            calls.append(([str(a) for a in args], timeout))
            quick_out.mkdir(exist_ok=True)
            (quick_out / "report.json").write_text(json.dumps(
                {"pass": True, "quick": True, "verification": "draft",
                 "gates": [{"name": "1 Execute", "status": "PASS"}, {"name": "Sweep", "status": "NOT RUN"}]}))
            return {"returncode": 0, "stdout": "", "stderr": "", "timed_out": False, "error": None, "seconds": 1.0}

        srv.run_harness = quick_fake
        try:
            result = srv.run_check("tests/fixtures/hang.py", quick=True).structured_content
        finally:
            for leftover in sorted(quick_out.rglob("*"), reverse=True) if quick_out.exists() else []:
                leftover.rmdir() if leftover.is_dir() else leftover.unlink()
            if quick_out.exists():
                quick_out.rmdir()
        args, timeout = calls[0]
        check("run_check quick: passes --quick to its own folder", "--quick" in args
              and args[args.index("--out") + 1].endswith("runs/hang-quick"), str(args))
        check("run_check quick: short timeout", timeout == srv.QUICK_TIMEOUT < srv.CHECK_TIMEOUT, str(timeout))
        check("run_check quick: result says quick and draft, never verified",
              result.get("quick") is True and result.get("verification") == "draft" and result["pass"] is True, str(result))
        check("run_check: full run unchanged, no --quick", "--quick" not in harness_args_of(srv, "hang"))
    finally:
        srv.run_harness = saved
        (out / "report.json").unlink(missing_ok=True)
        for leftover in sorted(out.rglob("*"), reverse=True) if out.exists() else []:
            leftover.rmdir() if leftover.is_dir() else leftover.unlink()
        if out.exists():
            out.rmdir()


def harness_args_of(server, stem):
    """The argv a full run_check would pass to the harness, captured without running it."""
    seen = []
    saved = server.run_harness
    server.run_harness = lambda args, timeout: seen.append([str(a) for a in args]) or {
        "returncode": None, "stdout": "", "stderr": "", "timed_out": False, "error": "captured", "seconds": 0.0}
    try:
        server.harness_check(f"tests/fixtures/{stem}.py")
    finally:
        server.run_harness = saved
    return seen[0]


def test_run_check_artefacts():
    """Eyes (#79): a check hands back the harness's renders as images, plus paths and metrics."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    saved = srv.run_harness
    out = ROOT / "runs" / "hang-check"
    try:
        out.mkdir(exist_ok=True)
        pngs = {}
        for name in ("iso", "top", "front", "side", "heatmap", "section", "thin"):
            pngs[name] = out / f"{name}.png"
            plt.imsave(pngs[name], [[0.0, 1.0], [1.0, 0.0]])
        art = {"views": {v: str(pngs[v]) for v in ("iso", "top", "front", "side")},
               "overhang_heatmap": str(pngs["heatmap"]), "design_section": str(pngs["section"]),
               "sections": [{"name": "thinnest wall", "axis": "Z", "offset": 1.0, "path": str(pngs["thin"])}],
               "face_maps": {"part": str(out / "part.faces.json")}, "manifest": str(out / "eyes.json"),
               "metrics": {"part": {"min_wall_mm": 1.2}}}
        report = {"pass": False, "gates": [{"name": "3 Printability", "status": "FAIL"}], "artefacts": art}

        def fake(args, timeout):
            (out / "report.json").write_text(json.dumps(report))
            return {"returncode": 1, "stdout": "", "stderr": "", "timed_out": False, "error": None, "seconds": 1.0}
        srv.run_harness = fake
        plain = srv.harness_check("tests/fixtures/hang.py")
        check("artefacts: paths and metrics come back on a failing check", plain["pass"] is False
              and plain["artefacts"]["metrics"]["part"]["min_wall_mm"] == 1.2
              and plain["artefacts"]["views"]["iso"] == "runs/hang-check/iso.png", str(plain.get("artefacts"))[:200])
        call = srv.run_check("tests/fixtures/hang.py")
        images = [c for c in call.content if c.type == "image"]
        check("artefacts: run_check result carries the renders inline", len(images) == 7
              and all(i.mime_type == "image/png" for i in images), str(len(images)))
        texts = [c.text for c in call.content if c.type == "text"]
        check("artefacts: each image is captioned", any("overhang heatmap" in t for t in texts)
              and any("thinnest wall" in t for t in texts), str(texts)[:300])
        check("artefacts: structured content unchanged", call.structured_content == plain)
        report.pop("artefacts")
        call = srv.run_check("tests/fixtures/hang.py")
        check("artefacts: no images when the harness made none", not [c for c in call.content if c.type == "image"]
              and call.structured_content["artefacts"] is None)
    finally:
        srv.run_harness = saved
        for leftover in sorted(out.rglob("*"), reverse=True) if out.exists() else []:
            leftover.rmdir() if leftover.is_dir() else leftover.unlink()
        if out.exists():
            out.rmdir()


async def protocol():
    from mcp import Client, StdioServerParameters
    params = StdioServerParameters(command=str(srv.PYTHON), args=[str(SERVER_FILE)], cwd="/")
    async with Client(params) as client:
        tools = await client.list_tools()
        check("protocol: all tools listed", {t.name for t in tools.tools} == TOOLS, str(sorted(t.name for t in tools.tools)))
        check("protocol: inputs are typed", all(t.input_schema.get("type") == "object" for t in tools.tools))
        by_name = {t.name: t for t in tools.tools}
        check("protocol: min_gap says STL only", "STL only" in by_name["min_gap"].description)
        check("protocol: min_gap args typed", by_name["min_gap"].input_schema["properties"]["path_a"]["type"] == "string")
        call = await client.call_tool("measure_file", {"path": BRACKET_STL})
        volume = call.structured_content["volume_mm3"]
        check("protocol: measure_file returns structured data, cwd independent", not call.is_error
              and abs(volume - BRACKET_VOLUME) <= 0.01 * BRACKET_VOLUME, f"{volume:.1f}")
        call = await client.call_tool("library_lookup", {"query": "608"})
        check("protocol: library_lookup", call.structured_content["matches"][0]["name"] == "608")
        call = await client.call_tool("measure_file", {"path": "../x.stl"})
        check("protocol: escape comes back as data", call.structured_content["error"]["code"] == "path_outside_project")
        call = await client.call_tool("run_check", {"design": "../evil.py"})
        check("protocol: run_check's CallToolResult keeps structured content", not call.is_error
              and call.structured_content["error"]["code"] == "path_outside_project"
              and call.structured_content["artefacts"] is None)
        check("protocol: run_check documents its artefacts", "overhang heatmap" in by_name["run_check"].description)


if __name__ == "__main__":
    for test in (test_listing, test_measure, test_paths, test_min_gap, test_library, test_eval_status,
                 test_run_check_failures, test_run_check_artefacts):
        print(f"--- {test.__name__}")
        test()
    print("--- protocol")
    asyncio.run(protocol())
    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)
