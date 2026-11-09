#!/usr/bin/env python
"""magic-cad MCP server: this project's harness and data over stdio. See mcp/README.md.

Every tool returns a dict; failures are {"error": {"code", "message"}}, never an exception.
No LLM calls, no network, no shell. Do not add mcp/__init__.py: as a plain folder this can't
shadow the installed `mcp` package when the project root is on sys.path.
"""
import functools
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.run_evals import PYTHON, discover, read_report, run_harness
from mcp.server.mcpserver import Image, MCPServer
from mcp_types import CallToolResult, TextContent

# The folder the design tools work in: the repo by default, or a project folder (a designer's
# proposal draft, #61) when MAGIC_CAD_PROJECT names one. Paths resolve against it and must stay in
# it; the harness, library and eval corpus always come from the repo.
PROJECT = Path(os.environ.get("MAGIC_CAD_PROJECT") or ROOT).resolve()
DESIGNS_DIR = PROJECT / "designs"
BRIEFS_DIR = PROJECT / "briefs"
EVAL_BRIEFS_DIR = ROOT / "evals" / "briefs"
RESULTS_DIR = ROOT / "evals" / "results"
PARTS_FILE = ROOT / "library" / "standard_parts.json"
CHECK_TIMEOUT = 1800     # s; a check includes the sweep, about 4 min on 4 cores
QUICK_TIMEOUT = 300      # s; a quick check is build, geometry, printability: under 20 s on the starters
STEP_TIMEOUT = 180       # s; same as the harness's build timeout, importing build123d is the slow part
STL_SUFFIXES = {".stl"}
STEP_SUFFIXES = {".step", ".stp"}

server = MCPServer("magic-cad", instructions=(
    "Magic CAD harness and data. Geometry numbers come from files reloaded from disk. A passing "
    "run_check is a gate result, not a design verdict. All paths must stay inside the project."))


class ToolError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def structured(fn):
    """Keep tool failures as data, so a bad call can't surface as an unhandled exception."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolError as err:
            return {"error": {"code": err.code, "message": str(err)}}
        except Exception as err:
            return {"error": {"code": "internal", "message": f"{type(err).__name__}: {err}"}}
    return wrapper


def safe_path(raw):
    """Resolve a path (symlinks included) against the project root; refuse anything outside it."""
    try:
        path = Path(raw)
        path = (path if path.is_absolute() else PROJECT / path).resolve()
    except (ValueError, OSError, RuntimeError) as err:
        raise ToolError("invalid_path", f"unusable path {raw!r}: {err}") from err
    if not path.is_relative_to(PROJECT):
        raise ToolError("path_outside_project", f"{raw!r} resolves outside the project root")
    return path


def existing_file(raw):
    path = safe_path(raw)
    if not path.is_file():
        raise ToolError("not_found", f"no such file: {raw!r}")
    return path


def relative(path):
    return str(Path(path).relative_to(PROJECT))


def find_brief(stem):
    """briefs/ first, as the harness does, then evals/briefs/, which the harness would not find."""
    for folder in (BRIEFS_DIR, EVAL_BRIEFS_DIR) if PROJECT == ROOT else (BRIEFS_DIR,):
        candidate = folder / f"{stem}.yaml"
        if candidate.is_file():
            return candidate
    return None


@server.tool()
@structured
def list_designs() -> dict[str, Any]:
    """List each design in designs/ and whether a matching brief exists in briefs/ or evals/briefs/."""
    designs = []
    for path in sorted(DESIGNS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        brief = find_brief(path.stem)
        designs.append({"name": path.stem, "path": relative(path), "has_brief": brief is not None,
                        "brief_path": relative(brief) if brief else None})
    return {"count": len(designs), "designs": designs}


@server.tool()
@structured
def list_eval_briefs() -> dict[str, Any]:
    """List each eval brief in evals/briefs/ and whether its design exists. Coverage, not a pass rate."""
    entries = discover(EVAL_BRIEFS_DIR, ROOT / "designs")   # the eval corpus is the repo's
    briefs = [{"name": e["name"], "path": relative(e["brief"]), "is_symlink": e["brief_is_symlink"],
               "design_present": e["design_present"],
               "design_path": relative(e["design"]) if e["design_present"] else None} for e in entries]
    return {"total": len(briefs), "designs_present": sum(1 for b in briefs if b["design_present"]),
            "briefs": briefs}


def check_failure(code, message, report_path=None, exit_code=None, seconds=None, brief=None):
    return {"pass": False, "gates": [], "report_path": report_path, "brief": brief,
            "exit_code": exit_code, "seconds": seconds, "error": {"code": code, "message": message},
            "artefacts": None}


def project_paths(value):
    """Artefact paths relative to the project root, so the agent can Read them; other values unchanged."""
    if isinstance(value, dict):
        return {k: project_paths(v) for k, v in value.items()}
    if isinstance(value, list):
        return [project_paths(v) for v in value]
    if isinstance(value, str) and value.startswith(str(PROJECT) + os.sep):
        return relative(value)
    return value


def artefact_images(artefacts):
    """(caption, path) for each image the harness wrote, in reading order."""
    if not isinstance(artefacts, dict):
        return []
    shown = [(f"{name} view", path) for name, path in (artefacts.get("views") or {}).items()]
    shown.append(("overhang heatmap (downward faces by angle from straight down; red needs support)",
                  artefacts.get("overhang_heatmap")))
    shown.append(("design's own section plane", artefacts.get("design_section")))
    shown += [(f"section through {s.get('name')} ({s.get('axis')}={s.get('offset')})", s.get("path"))
              for s in artefacts.get("sections") or [] if isinstance(s, dict)]
    found = []
    for caption, path in shown:
        try:
            file = existing_file(path) if isinstance(path, str) else None
        except ToolError:
            file = None
        if file is not None and file.suffix.lower() == ".png":
            found.append((caption, file))
    return found


def with_images(result):
    """The check result as structured data, plus each harness image inline with a caption."""
    content = [TextContent(type="text", text=json.dumps(result, indent=1))]
    for caption, file in artefact_images(result.get("artefacts")):
        content.append(TextContent(type="text", text=f"{caption}: {relative(file)}"))
        content.append(Image(path=file).to_image_content())
    return CallToolResult(content=content, structured_content=result)


def resolve_design(design):
    """A bare name means designs/<name>.py; anything else is a path inside the project."""
    bare = design and "/" not in design and not design.endswith(".py")
    path = safe_path(f"designs/{design}.py" if bare else design)
    if path.suffix != ".py" or not path.is_file():
        raise ToolError("design_not_found", f"no design file for {design!r}")
    return path


def harness_check(design, timeout=CHECK_TIMEOUT, quick=False):
    try:
        path = resolve_design(design)
    except ToolError as err:
        return check_failure(err.code, str(err))
    # In a project folder, checks write under outputs/, which is never versioned or proposed.
    out = (ROOT / "runs" if PROJECT == ROOT else PROJECT / "outputs") / f"{path.stem}-{'quick' if quick else 'check'}"
    report_file = out / "report.json"
    brief = find_brief(path.stem)
    brief_name = relative(brief) if brief else None
    report_file.unlink(missing_ok=True)   # a crash must not be answered with an old report
    args = [PYTHON, ROOT / "magic.py", "check", path, "--out", out]
    args += ["--brief", brief] if brief else []
    args += ["--quick"] if quick else []
    outcome = run_harness(args, timeout)
    context = {"exit_code": outcome["returncode"], "seconds": outcome["seconds"], "brief": brief_name}
    if outcome["timed_out"]:
        return check_failure("timeout", f"harness still running after {timeout} s; killed", **context)
    if outcome["error"]:
        return check_failure("harness_error", outcome["error"], **context)
    report = read_report(report_file)
    if report is None:
        detail = outcome["stderr"].strip()[-500:] or "no stderr"
        return check_failure("harness_crashed", f"exit {outcome['returncode']}, no readable report.json: {detail}",
                             **context)
    gates = report.get("gates") if isinstance(report, dict) else None
    if not isinstance(gates, list) or not all(isinstance(g, dict) and "name" in g and "status" in g for g in gates) \
            or not isinstance(report.get("pass"), bool):
        return check_failure("malformed_report", "report.json lacks pass/gates", str(report_file), **context)
    if report["pass"] != (outcome["returncode"] == 0):
        return check_failure("inconsistent_result", f"exit {outcome['returncode']} but report pass={report['pass']}",
                             str(report_file), **context)
    result = {"pass": report["pass"], "gates": [{"name": g["name"], "status": g["status"]} for g in gates],
              "report_path": str(report_file), "error": None, **context,
              "artefacts": project_paths(report.get("artefacts"))}
    if quick:
        result.update(quick=True, verification=report.get("verification"))
    if not brief:
        result["warning"] = "no brief found: hard dimensions were not checked"
    return result


@server.tool()
@structured
def run_check(design: str, quick: bool = False) -> dict[str, Any]:
    """Run `magic.py check` on a design, sweep included (takes minutes), and return its gates.

    design: a name in designs/ ("wall_bracket") or a .py path inside the project. Writes to
    runs/<stem>-check/. Uses the brief from briefs/ or evals/briefs/ when one exists. A pass is
    a gate result: exports are not kept, and a design is only verified by `magic.py run`.

    Whenever the build got as far as the renders (pass or fail), the result also carries the
    harness artefacts: `artefacts` holds paths (iso/top/front/side views, overhang heatmap,
    sections at the thinnest wall and each named feature, face maps, eyes.json) and per-part
    metrics (bbox, volume, overhang shares, min wall, unsupported area), and the images
    themselves follow inline. Look at them before the next edit. They are read-only.

    quick=True is the mid-loop fast check (seconds): build, geometry and printability only, to
    runs/<stem>-quick/, with renders (so no artefacts), sweep and exports NOT RUN and verification "draft". Iterate
    with quick; run the full check before proposing. A quick pass never verifies a design.
    """
    return with_images(harness_check(design, QUICK_TIMEOUT if quick else CHECK_TIMEOUT, quick))


def bbox_mm(low, high):
    low, high = [round(float(x), 6) + 0.0 for x in low], [round(float(x), 6) + 0.0 for x in high]   # + 0.0: no -0.0
    return {"min": low, "max": high, "size": [round(b - a, 6) for a, b in zip(low, high)]}


def measure_stl(path):
    import trimesh
    mesh = trimesh.load_mesh(str(path))
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ToolError("load_failed", f"{relative(path)} did not load as a mesh")
    return {"format": "stl", "path": relative(path), "volume_mm3": float(mesh.volume),
            "bbox_mm": bbox_mm(*mesh.bounds),
            "watertight": bool(mesh.is_watertight), "components": int(mesh.body_count),
            "faces": len(mesh.faces)}


def probe_step(path):
    """Subprocess entry: OpenCascade can crash the process, and build123d must not touch our stdout."""
    from build123d import import_step
    shape = import_step(path)
    box = shape.bounding_box()
    low, high = [box.min.X, box.min.Y, box.min.Z], [box.max.X, box.max.Y, box.max.Z]
    print(json.dumps({"volume_mm3": shape.volume, "low": low, "high": high, "solids": len(shape.solids()),
                      "valid": shape.is_valid}))


def measure_step(path):
    outcome = run_harness([PYTHON, Path(__file__).resolve(), "--probe-step", path], STEP_TIMEOUT)
    if outcome["timed_out"]:
        raise ToolError("timeout", f"STEP import still running after {STEP_TIMEOUT} s; killed")
    if outcome["returncode"] != 0 or not outcome["stdout"].strip():
        raise ToolError("load_failed", f"{relative(path)}: {outcome['error'] or outcome['stderr'].strip()[-300:]}")
    data = json.loads(outcome["stdout"].strip().splitlines()[-1])
    return {"format": "step", "path": relative(path), "volume_mm3": data["volume_mm3"],
            "bbox_mm": bbox_mm(data["low"], data["high"]),
            "solids": data["solids"], "valid": data["valid"]}


@server.tool()
@structured
def measure_file(path: str) -> dict[str, Any]:
    """Measure an STL or STEP file reloaded from disk: volume_mm3 and bbox_mm (min, max, size).

    STL (via trimesh) also gives watertight, components and faces; volume is only meaningful
    when watertight. STEP (via build123d, in a subprocess, slower) also gives solids and valid.
    path must be inside the project.
    """
    file = existing_file(path)
    suffix = file.suffix.lower()
    if suffix in STL_SUFFIXES:
        return measure_stl(file)
    if suffix in STEP_SUFFIXES:
        return measure_step(file)
    raise ToolError("unsupported_type", f"{file.name}: expected .stl, .step or .stp")


def load_manifold(path):
    import manifold3d
    import numpy as np
    import trimesh
    mesh = trimesh.load_mesh(str(path))
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ToolError("load_failed", f"{relative(path)} did not load as a mesh")
    body = manifold3d.Manifold(manifold3d.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                                               tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))
    if body.status() != manifold3d.Error.NoError or body.is_empty():
        raise ToolError("not_manifold", f"{relative(path)} is not a manifold mesh: {body.status()}")
    return body, mesh.bounds


@server.tool()
@structured
def min_gap(path_a: str, path_b: str) -> dict[str, Any]:
    """Exact minimum clearance in mm between two STL meshes reloaded from disk, via manifold3d.

    STL only: STEP files are rejected. "Exact" is on the tessellated meshes, so curved surfaces
    carry facet error. gap_mm is 0 when the parts touch or overlap, including one nested inside
    the other; overlap_volume_mm3 tells those apart. Paths must be inside the project.
    """
    import numpy as np
    files = [existing_file(path_a), existing_file(path_b)]
    for file in files:
        if file.suffix.lower() not in STL_SUFFIXES:
            raise ToolError("unsupported_type", f"{file.name}: min_gap takes STL only")
    (a, bounds_a), (b, bounds_b) = load_manifold(files[0]), load_manifold(files[1])
    # min_gap clamps to search_length, so search further than the parts can possibly be apart.
    corners = np.vstack([bounds_a, bounds_b])
    search = float(np.linalg.norm(corners.max(axis=0) - corners.min(axis=0))) + 1.0
    overlap = float((a ^ b).volume())
    gap = 0.0 if overlap > 0 else float(a.min_gap(b, search))
    return {"gap_mm": gap, "overlap_volume_mm3": overlap, "search_length_mm": search,
            "path_a": relative(files[0]), "path_b": relative(files[1])}


def search_parts(query, parts):
    needle = query.strip().lower()
    if not needle:
        raise ToolError("empty_query", "query is empty")
    hit = lambda text: needle in str(text).lower()
    matches = []
    for category, entries in parts.items():
        # Underscore keys (_notes, _dimension_provenance, ...) are file metadata, not categories.
        if category.startswith("_") or not isinstance(entries, dict):
            continue
        for name, entry in entries.items():
            if name.startswith("_"):    # a category's own note (e.g. fits._source), not a part
                continue
            # Part categories hold records; fits and brief_constants hold plain values.
            if isinstance(entry, dict):
                value_hit = any(hit(k) or hit(v) for k, v in entry.items())
            else:
                value_hit = hit(entry)
            if hit(category) or hit(name) or value_hit:
                matches.append({"category": category, "name": name, "entry": entry})
    return matches


@server.tool()
@structured
def library_lookup(query: str) -> dict[str, Any]:
    """Case-insensitive substring search over library/standard_parts.json keys and values.

    Returns each matching entry. A match on a category name returns all its entries; numbers
    match as text, so "22" finds a 22.0 value.
    """
    matches = search_parts(query, json.loads(PARTS_FILE.read_text()))
    return {"query": query, "count": len(matches), "matches": matches}


@server.tool()
@structured
def eval_status() -> dict[str, Any]:
    """Summarize the newest evals/results/*/eval_report.json, or say no eval has run yet.

    Pass rate and coverage are separate numbers. Check summary.mode: a "quick" run skipped the
    sweep and verifies nothing parametric.
    """
    reports = sorted(RESULTS_DIR.glob("*/eval_report.json"), key=lambda p: (p.stat().st_mtime, p.parent.name))
    if not reports:
        return {"status": "no_eval_run", "message": "no eval run yet: run evals/run_evals.py"}
    newest = reports[-1]
    report = read_report(newest)
    if not isinstance(report, dict) or not isinstance(report.get("summary"), dict) \
            or not isinstance(report.get("briefs"), list):
        raise ToolError("malformed_report", f"{relative(newest)} is not a usable eval report")
    return {"status": "ok", "report_path": relative(newest), "generated_at": report.get("generated_at"),
            "summary": report["summary"],
            "briefs": [{"name": b.get("name"), "status": b.get("status")} for b in report["briefs"]]}


if __name__ == "__main__":
    if sys.argv[1:2] == ["--probe-step"]:
        probe_step(sys.argv[2])
    else:
        os.chdir(ROOT)
        server.run("stdio")
