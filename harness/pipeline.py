"""Run the gates cheapest-first, then write the reports. Exit code 0 only if all pass."""
import hashlib
import shutil
import tempfile
from pathlib import Path

from .brief import BriefError, load_brief
from .execute import run_worker
from .geometry import check_geometry, pairwise_overlaps
from .lint import lint_design
from .printability import check_stl
from .render import render_all
from .report import write_reports
from .sweep import run_sweep

GATE_NAMES = ["1 Execute", "2 Geometry", "3 Printability", "4 Renders", "Sweep", "5 Exports"]
PRODUCED = ("*.stl", "*.step", "report.json", "report.md", "sweep.json", "sweep.md")
MESH_VOLUME_REL = 0.01  # STL may differ from the B-rep by facet error, no more


def find_brief(design, brief_path):
    """--brief wins; otherwise use briefs/<design stem>.yaml when it exists."""
    if brief_path:
        return Path(brief_path)
    candidate = Path(design).resolve().parent.parent / "briefs" / f"{Path(design).stem}.yaml"
    return candidate if candidate.exists() else None


def clear_outputs(out):
    out.mkdir(parents=True, exist_ok=True)
    for pattern in PRODUCED:
        for stale in out.glob(pattern):
            stale.unlink()
    shutil.rmtree(out / "renders", ignore_errors=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def new_report(design, brief_path, brief, command):
    return {"design": Path(design).name, "command": command,
            "brief": str(brief_path) if brief_path else None, "pass": False, "gates": [],
            "assumptions": (brief or {}).get("assumptions", [])}


def add_gate(report, name, passed, detail):
    report["gates"].append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})
    return passed


def finish(report, out, stem="report"):
    done = {g["name"] for g in report["gates"]}
    names = GATE_NAMES if stem == "report" else ["1 Execute", "Sweep"]
    for name in names:
        if name not in done:
            report["gates"].append({"name": name, "status": "SKIPPED", "detail": "-"})
    report["gates"].sort(key=lambda g: names.index(g["name"]) if g["name"] in names else len(names))
    report["pass"] = all(g["status"] in ("PASS", "NOT RUN") for g in report["gates"])
    write_reports(report, out, stem)
    return 0 if report["pass"] else 1


def run(design, brief_path=None, out=None, samples=None, exports=True, timeout=180, command="run",
        skip_sweep=False):
    """Full pipeline. exports=False is `check`: identical gates, no STL/STEP kept.

    skip_sweep is opt-in, for fast feedback, and refused with exports so a design that never
    swept can't leave files that look approved. The report says the sweep did not run.
    """
    if skip_sweep and exports:
        raise ValueError("--no-sweep is only allowed with check: exports require the sweep")
    design = Path(design)
    out = Path(out) if out else Path("runs") / (design.stem + ("" if exports else "-check"))
    clear_outputs(out)
    brief_path = find_brief(design, brief_path)
    brief = None
    if brief_path:
        try:
            brief = load_brief(brief_path)
        except (BriefError, OSError) as err:
            report = new_report(design, brief_path, None, command)
            add_gate(report, "1 Execute", False, f"brief invalid: {err}")
            return finish(report, out), report
    report = new_report(design, brief_path, brief, command)
    if brief is None:
        report["assumptions"] = ["No brief: hard dimensions were not checked."]

    with tempfile.TemporaryDirectory(prefix="magic_run_") as tmp:
        tmp = Path(tmp)
        # Gate 1: contract lint (cheapest), then execute in a subprocess.
        lint = lint_design(design)
        if lint:
            add_gate(report, "1 Execute", False, f"hard-coded dimensions: {'; '.join(lint[:8])}")
            return finish(report, out), report
        result = run_worker(design, tmp, None, timeout)
        if not result["ok"]:
            report["traceback"] = result["traceback"]
            add_gate(report, "1 Execute", False, result["traceback"].strip().splitlines()[-1])
            return finish(report, out), report
        add_gate(report, "1 Execute", True, f"built in {result['seconds']} s; no hard-coded literals")
        report["params"] = result["params"]

        # Gate 2: B-rep facts from the reloaded STEP, overlap from the reloaded STLs.
        geo = check_geometry(result, brief)
        stls = {p["name"]: p["stl"] for p in result["parts"]}
        overlaps = pairwise_overlaps(stls)
        report["geometry"], report["overlaps"] = geo, overlaps
        problems = geo["problems"] + [f"{r['a']}/{r['b']} overlap {r['volume']:.2f} mm3"
                                      for r in overlaps if not r["pass"]]
        detail = f"{geo['solids']}/{geo['expected_solids']} solids, volume {geo['volume']:.0f} mm³, " \
                 f"{sum(r['pass'] for r in geo['dimensions'])}/{len(geo['dimensions'])} dims in ±0.1"
        if not add_gate(report, "2 Geometry", not problems, "; ".join(problems) or detail):
            return finish(report, out), report

        # Gate 3: STL reloaded from disk.
        allow = bool(brief and brief["allow_supports"])
        printed = {name: check_stl(path, allow) for name, path in stls.items()}
        report["printability"] = printed
        problems = [f"{n}: {x}" for n, r in printed.items() for x in r["problems"]]
        for part in result["parts"]:
            mesh_volume = printed[part["name"]]["metrics"]["mesh_volume"]
            if abs(mesh_volume - part["volume"]) > MESH_VOLUME_REL * part["volume"]:
                problems.append(f"{part['name']}: STL volume {mesh_volume:.0f} vs STEP {part['volume']:.0f}")
        worst = max(r["metrics"]["support_risk_pct"] for r in printed.values())
        worst_brief = max(r["metrics"]["overhang_brief_pct"] for r in printed.values())
        printable = add_gate(report, "3 Printability", not problems, "; ".join(problems) or
                             f"watertight, single component, fits bed; overhang brief {worst_brief:.1f} %, "
                             f"support risk {worst:.1f} %")

        # Gate 4: renders, also on a printability failure, since they help diagnose it.
        title = design.stem
        renders = render_all(stls, out / "renders", title, result.get("section"))
        report["renders"] = renders
        add_gate(report, "4 Renders", all(Path(f).stat().st_size > 0 for f in renders),
                 f"{len(renders)} PNGs from reloaded STL")
        if not printable:
            return finish(report, out), report

        if skip_sweep:
            report["gates"].append({"name": "Sweep", "status": "NOT RUN",
                                    "detail": "--no-sweep: parametric behaviour not verified"})
            report["gates"].append({"name": "5 Exports", "status": "NOT RUN",
                                    "detail": "check mode: no exports kept"})
            return finish(report, out), report

        # Sweep: costliest, so it runs after the cheap gates.
        sweep = run_sweep(design, {k: tuple(v) for k, v in result["declared"].items()},
                          brief, samples, timeout)
        report["sweep"] = sweep
        if not add_gate(report, "Sweep", sweep["pass"],
                        f"{sweep['passed']}/{sweep['total']} pass; dead params: {sweep['dead_params'] or 'none'}"):
            return finish(report, out), report

        # Gate 5: exports, only for a design that passed everything else.
        if not exports:
            report["gates"].append({"name": "5 Exports", "status": "NOT RUN",
                                    "detail": "check mode: no exports kept"})
            return finish(report, out), report
        ok = True
        files = []
        for part in result["parts"]:
            for key in ("stl", "step"):
                target = out / Path(part[key]).name
                shutil.copy2(part[key], target)
                ok = ok and sha(part[key]) == sha(target) and target.stat().st_size > 0
                files.append(target.name)
        add_gate(report, "5 Exports", ok, ", ".join(files))
        report["exports"] = files
    return finish(report, out), report


def sweep_only(design, brief_path=None, out=None, samples=None, timeout=180):
    """`magic.py sweep`: build at defaults for the declarations, then sweep."""
    design = Path(design)
    out = Path(out) if out else Path("runs") / f"{design.stem}-sweep"
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("sweep.*"):
        stale.unlink()
    brief_path = find_brief(design, brief_path)
    brief = load_brief(brief_path) if brief_path else None
    report = new_report(design, brief_path, brief, "sweep")
    with tempfile.TemporaryDirectory(prefix="magic_run_") as tmp:
        result = run_worker(design, Path(tmp), None, timeout)
    if not result["ok"]:
        report["traceback"] = result["traceback"]
        add_gate(report, "1 Execute", False, result["traceback"].strip().splitlines()[-1])
        return finish(report, out, "sweep"), report
    add_gate(report, "1 Execute", True, f"built in {result['seconds']} s")
    report["params"] = result["params"]
    sweep = run_sweep(design, {k: tuple(v) for k, v in result["declared"].items()},
                      brief, samples, timeout)
    report["sweep"] = sweep
    add_gate(report, "Sweep", sweep["pass"],
             f"{sweep['passed']}/{sweep['total']} pass; dead params: {sweep['dead_params'] or 'none'}")
    return finish(report, out, "sweep"), report
