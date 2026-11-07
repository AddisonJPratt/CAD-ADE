"""Run the gates cheapest-first, then write the reports. Exit code 0 only if all pass."""
import hashlib
import shutil
import tempfile
from pathlib import Path

from .brief import BriefError, load_brief
from .execute import run_worker
from .geometry import check_geometry, pairwise_overlaps
from .evidence import claims_for_report
from .lint import lint_design
from .printability import check_stl, DEFAULT_BUILD_VOLUME
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


def printer_for_design(design):
    """Resolve a project printer for direct CLI runs as well as engine runs."""
    path = Path(design).resolve()
    project = path.parent.parent
    if path.parent.name == "designs":
        from engine.printers import project_printer
        return project_printer(project)
    return None


def material_fits(printer):
    return printer["profile"]["materials"][printer["material"]]["fit_clearance_mm_per_side"] if printer else None


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


class Events:
    """Gate start/finish notifications for a live listener (the engine API). Never affects a verdict.

    on_event receives dicts: {"type": "gate_started", "gate"} and
    {"type": "gate_finished", "gate", "status", "detail"}; every gate in the final report,
    SKIPPED and NOT RUN included, is reported finished exactly once.
    """

    def __init__(self, on_event=None, design=None):
        self.on_event, self.design, self.finished = on_event, design, set()

    def emit(self, event):
        if self.on_event:
            self.on_event({"design": self.design, **event})

    def start(self, name):
        self.emit({"type": "gate_started", "gate": name})

    def done(self, gate):
        if gate["name"] not in self.finished:
            self.finished.add(gate["name"])
            self.emit({"type": "gate_finished", "gate": gate["name"], "status": gate["status"],
                       "detail": gate["detail"]})


QUIET = Events()


def add_gate(report, name, passed, detail, events=QUIET):
    return add_status(report, name, "PASS" if passed else "FAIL", detail, events) == "PASS"


def add_status(report, name, status, detail, events=QUIET):
    gate = {"name": name, "status": status, "detail": detail}
    report["gates"].append(gate)
    events.done(gate)
    return status


def finish(report, out, stem="report", events=QUIET):
    done = {g["name"] for g in report["gates"]}
    names = GATE_NAMES if stem == "report" else ["1 Execute", "Sweep"]
    for name in names:
        if name not in done:
            report["gates"].append({"name": name, "status": "SKIPPED", "detail": "-"})
    report["gates"].sort(key=lambda g: names.index(g["name"]) if g["name"] in names else len(names))
    report["pass"] = all(g["status"] in ("PASS", "NOT RUN") for g in report["gates"])
    report["verification"] = ("failed" if not report["pass"] else
                              "draft" if any(g["status"] in ("NOT RUN", "SKIPPED")
                                             for g in report["gates"]) else "passed")
    report["claims"] = claims_for_report(report)
    # Production files must not survive a failed gate, including export verification.
    if stem == "report" and not report["pass"]:
        for pattern in ("*.stl", "*.step"):
            for artifact in out.glob(pattern):
                artifact.unlink()
        report.pop("exports", None)
    write_reports(report, out, stem)
    for gate in report["gates"]:
        events.done(gate)
    return 0 if report["pass"] else 1


def run(design, brief_path=None, out=None, samples=None, exports=True, timeout=180, command="run",
        skip_sweep=False, on_event=None, printer=None):
    """Full pipeline. exports=False is `check`: identical gates, no STL/STEP kept.

    skip_sweep is opt-in, for fast feedback, and refused with exports so a design that never
    swept can't leave files that look approved. The report says the sweep did not run.
    on_event, if given, is called as each gate starts and finishes (see Events).
    """
    if skip_sweep and exports:
        raise ValueError("--no-sweep is only allowed with check: exports require the sweep")
    design = Path(design)
    printer = printer if printer is not None else printer_for_design(design)
    ev = Events(on_event, design.name)
    out = Path(out) if out else Path("runs") / (design.stem + ("" if exports else "-check"))
    clear_outputs(out)
    brief_path = find_brief(design, brief_path)
    brief = None
    if brief_path:
        try:
            brief = load_brief(brief_path)
        except (BriefError, OSError) as err:
            report = new_report(design, brief_path, None, command)
            add_gate(report, "1 Execute", False, f"brief invalid: {err}", ev)
            return finish(report, out, events=ev), report
    report = new_report(design, brief_path, brief, command)
    if printer is not None:
        report["printer"] = printer
    if brief is None:
        report["assumptions"] = ["No brief: hard dimensions were not checked."]

    with tempfile.TemporaryDirectory(prefix="magic_run_") as tmp:
        tmp = Path(tmp)
        # Gate 1: contract lint (cheapest), then execute in a subprocess.
        ev.start("1 Execute")
        lint = lint_design(design)
        if lint:
            add_gate(report, "1 Execute", False, f"hard-coded dimensions: {'; '.join(lint[:8])}", ev)
            return finish(report, out, events=ev), report
        fits = material_fits(printer)
        result = run_worker(design, tmp, None, timeout, fits)
        if not result["ok"]:
            report["traceback"] = result["traceback"]
            add_gate(report, "1 Execute", False, result["traceback"].strip().splitlines()[-1], ev)
            return finish(report, out, events=ev), report
        add_gate(report, "1 Execute", True, f"built in {result['seconds']} s; no hard-coded literals", ev)
        report["params"] = result["params"]

        # Gate 2: B-rep facts from the reloaded STEP, overlap from the reloaded STLs.
        ev.start("2 Geometry")
        geo = check_geometry(result, brief)
        stls = {p["name"]: p["stl"] for p in result["parts"]}
        overlaps = pairwise_overlaps(stls)
        report["geometry"], report["overlaps"] = geo, overlaps
        problems = geo["problems"] + [f"{r['a']}/{r['b']} overlap {r['volume']:.2f} mm3"
                                      for r in overlaps if not r["pass"]]
        detail = f"{geo['solids']}/{geo['expected_solids']} solids, volume {geo['volume']:.0f} mm³, " \
                 f"{sum(r['pass'] for r in geo['dimensions'])}/{len(geo['dimensions'])} dims in ±0.1"
        if not add_gate(report, "2 Geometry", not problems, "; ".join(problems) or detail, ev):
            return finish(report, out, events=ev), report

        # Gate 3: STL reloaded from disk.
        ev.start("3 Printability")
        allow = bool(brief and brief["allow_supports"])
        volume = printer["profile"]["build_volume_mm"] if printer else DEFAULT_BUILD_VOLUME
        printed = {name: check_stl(path, allow, build_volume=volume) for name, path in stls.items()}
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
                             f"support risk {worst:.1f} %", ev)

        # Gate 4: renders, also on a printability failure, since they help diagnose it.
        ev.start("4 Renders")
        title = design.stem
        renders = render_all(stls, out / "renders", title, result.get("section"))
        report["renders"] = renders
        add_gate(report, "4 Renders", all(Path(f).stat().st_size > 0 for f in renders),
                 f"{len(renders)} PNGs from reloaded STL", ev)
        if not printable:
            return finish(report, out, events=ev), report

        if skip_sweep:
            add_status(report, "Sweep", "NOT RUN", "--no-sweep: parametric behaviour not verified", ev)
            add_status(report, "5 Exports", "NOT RUN", "check mode: no exports kept", ev)
            return finish(report, out, events=ev), report

        # Sweep: costliest, so it runs after the cheap gates.
        ev.start("Sweep")
        sweep = run_sweep(design, {k: tuple(v) for k, v in result["declared"].items()},
                          brief, samples, timeout, build_volume=volume, fits=fits)
        report["sweep"] = sweep
        if not add_gate(report, "Sweep", sweep["pass"],
                        f"{sweep['passed']}/{sweep['total']} pass; dead params: {sweep['dead_params'] or 'none'}", ev):
            return finish(report, out, events=ev), report

        # Gate 5: exports, only for a design that passed everything else.
        if not exports:
            add_status(report, "5 Exports", "NOT RUN", "check mode: no exports kept", ev)
            return finish(report, out, events=ev), report
        ev.start("5 Exports")
        ok = True
        files = []
        for part in result["parts"]:
            for key in ("stl", "step"):
                target = out / Path(part[key]).name
                shutil.copy2(part[key], target)
                ok = ok and sha(part[key]) == sha(target) and target.stat().st_size > 0
                files.append(target.name)
        add_gate(report, "5 Exports", ok, ", ".join(files), ev)
        report["exports"] = files
    return finish(report, out, events=ev), report


def sweep_only(design, brief_path=None, out=None, samples=None, timeout=180):
    """`magic.py sweep`: build at defaults for the declarations, then sweep."""
    design = Path(design)
    printer = printer_for_design(design)
    fits = material_fits(printer)
    volume = printer["profile"]["build_volume_mm"] if printer else DEFAULT_BUILD_VOLUME
    out = Path(out) if out else Path("runs") / f"{design.stem}-sweep"
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("sweep.*"):
        stale.unlink()
    brief_path = find_brief(design, brief_path)
    brief = load_brief(brief_path) if brief_path else None
    report = new_report(design, brief_path, brief, "sweep")
    if printer is not None:
        report["printer"] = printer
    with tempfile.TemporaryDirectory(prefix="magic_run_") as tmp:
        result = run_worker(design, Path(tmp), None, timeout, fits)
    if not result["ok"]:
        report["traceback"] = result["traceback"]
        add_gate(report, "1 Execute", False, result["traceback"].strip().splitlines()[-1])
        return finish(report, out, "sweep"), report
    add_gate(report, "1 Execute", True, f"built in {result['seconds']} s")
    report["params"] = result["params"]
    sweep = run_sweep(design, {k: tuple(v) for k, v in result["declared"].items()},
                      brief, samples, timeout, build_volume=volume, fits=fits)
    report["sweep"] = sweep
    add_gate(report, "Sweep", sweep["pass"],
             f"{sweep['passed']}/{sweep['total']} pass; dead params: {sweep['dead_params'] or 'none'}")
    return finish(report, out, "sweep"), report
