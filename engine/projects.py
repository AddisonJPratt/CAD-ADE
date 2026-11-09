"""Project folder in, verdict and artifacts out. The one function the CLI and the engine API share.

A project folder holds:

    <project>/designs/<part>.py      parametric build123d designs (the design contract)
    <project>/briefs/<part>.yaml     optional brief card per design, matched by stem
    <project>/assembly.py            optional assembly of the parts, hardware and components
    <project>/outputs/<part>/        written here: report.json/.md, STL, STEP, renders
    <project>/outputs/_assembly/     written here: the assembly gate's report.json
    <project>/outputs/verdict.json   written here: the project verdict
    <project>/.git, .magic/          versions (see engine/versions.py); a plain folder works too

Each design goes through harness.pipeline.run, exactly as `magic.py run designs/<part>.py`
would run it, so a project verdict is the CLI verdict for each of its designs. When the
project has an assembly file, the assembly gate runs after the designs and the project
passes only if it passes too.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from harness.evidence import apply_slice
from harness.pipeline import run as run_design
from harness.report import write_reports

OUTPUTS = "outputs"
ASSEMBLY = "assembly.py"
ASSEMBLY_OUT = "_assembly"   # a leading _ can never be a design stem (designs_of skips them)
ARTIFACT_TYPES = {".stl": "model/stl", ".step": "model/step", ".3mf": "model/3mf", ".png": "image/png",
                  ".json": "application/json", ".md": "text/markdown; charset=utf-8",
                  ".csv": "text/csv; charset=utf-8"}


class ProjectError(ValueError):
    """The folder is not a project the engine can run."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def designs_of(project):
    """The project's designs, in name order. Raises ProjectError for anything that is not a project."""
    project = Path(project)
    if not project.is_dir():
        raise ProjectError(f"not a folder: {project}")
    designs = sorted(p for p in (project / "designs").glob("*.py") if not p.name.startswith("_"))
    if not designs:
        raise ProjectError(f"no designs/*.py in {project}")
    return designs


def briefs_of(project):
    """The project's brief cards, in name order (possibly none)."""
    return sorted(p for p in (Path(project) / "briefs").glob("*.yaml") if not p.name.startswith("_"))


def require_project(project):
    """A project folder holds designs, or brief cards the designer (#61) has yet to design.
    Raises ProjectError for anything else."""
    project = Path(project)
    if project.is_dir() and briefs_of(project):
        return project
    designs_of(project)
    return project


def artifacts_of(project, stem):
    """Files a run left for one design, as paths relative to the project's outputs folder."""
    folder = Path(project) / OUTPUTS / stem
    if not folder.is_dir():
        return []
    return sorted(p.relative_to(folder.parent).as_posix() for p in folder.rglob("*")
                  if p.is_file() and p.suffix in ARTIFACT_TYPES
                  and (p.suffix != ".3mf" or p == folder / f"{stem}.3mf"))  # only the slicer's own 3MF


def slice_passed(report, out, stem, material, emit):
    """Slice a passing design's exported STLs; fold the result into its report and claims.

    A failed slice fails the design: a geometry pass is not a slice pass. Without a usable
    ElegooSlicer the claims say so and the verdict is unchanged.
    """
    from .slicer import find_slicer, slice_design
    executable = find_slicer()
    emit({"type": "slice_started", "design": report["design"]})
    if executable is None:
        result = None
    else:
        allow = any(p["metrics"].get("allow_supports") for p in (report.get("printability") or {}).values())
        result = slice_design(sorted(out.glob("*.stl")), out, stem, material, allow, executable)
        result["three_mf"] = f"{stem}/{result['three_mf']}" if result.get("three_mf") else None
        report["slice"] = result
        if result["ran"] and not result["ok"]:
            report["pass"], report["verification"] = False, "failed"
    report["claims"] = apply_slice(report["claims"], result)
    write_reports(report, out)
    emit({"type": "slice_finished", "design": report["design"],
          "status": "NOT RUN" if result is None or not result["ran"] else "PASS" if result["ok"] else "FAIL"})
    return result


def run_project(project, on_event=None, samples=None, timeout=180, slice=False):
    """Run every gate on every design in the project. Returns (exit code, verdict).

    on_event receives the pipeline's gate events plus run_started, design_started,
    design_finished, assembly_started, assembly_finished and run_finished. The exit code is 0
    only if every design, and the assembly when there is one, passes.
    slice=True also slices each passing design with ElegooSlicer (engine/slicer.py),
    adding slice_started / slice_finished events and a 3MF beside its other outputs.
    """
    emit = on_event or (lambda event: None)
    project = Path(project).resolve()
    designs = designs_of(project)
    from .printers import project_printer
    printer = project_printer(project)
    verdict = {"project": str(project), "started": now(), "pass": False, "designs": []}
    emit({"type": "run_started", "project": str(project), "designs": [d.name for d in designs]})
    began = time.time()
    for design in designs:
        emit({"type": "design_started", "design": design.name})
        out = project / OUTPUTS / design.stem
        command = f"engine run {design.relative_to(project).as_posix()}"
        (out / f"{design.stem}.3mf").unlink(missing_ok=True)  # a 3MF only ever belongs to this run's slice
        _, report = run_design(design, out=out, samples=samples, timeout=timeout,
                               command=command, on_event=on_event, printer=printer)
        if slice and report["pass"]:
            slice_passed(report, out, design.stem, printer["material"], emit)
        entry = {"design": design.name, "pass": report["pass"], "gates": report["gates"],
                 "report": f"{design.stem}/report.json", "claims": report["claims"],
                 "artifacts": artifacts_of(project, design.stem)}
        if "slice" in report:
            entry["slice"] = report["slice"]
        verdict["designs"].append(entry)
        emit({"type": "design_finished", "design": design.name, "pass": report["pass"]})
    if (project / ASSEMBLY).is_file():
        verdict["assembly"] = run_assembly(project, emit, timeout)
    verdict["pass"] = all(d["pass"] for d in verdict["designs"]) and \
        verdict.get("assembly", {}).get("pass", True)
    verdict["finished"] = now()
    verdict["seconds"] = round(time.time() - began, 1)
    from .versions import record_verdict  # here, not at the top: versions imports this module
    verdict["version"] = record_verdict(project, verdict)
    (project / OUTPUTS / "verdict.json").write_text(json.dumps(verdict, indent=2))
    emit({"type": "run_finished", "pass": verdict["pass"]})
    return (0 if verdict["pass"] else 1), verdict


def run_assembly(project, emit, timeout=180):
    """The assembly gate on <project>/assembly.py, reported like one more design's gate."""
    from assembly.gate import GATE, run_gate
    emit({"type": "assembly_started", "assembly": ASSEMBLY})
    emit({"type": "gate_started", "design": ASSEMBLY, "gate": GATE})
    report = run_gate(project / ASSEMBLY, project, project / OUTPUTS / ASSEMBLY_OUT, timeout=timeout)
    gate = report["gate"]
    emit({"type": "gate_finished", "design": ASSEMBLY, "gate": gate["name"], "status": gate["status"],
          "detail": gate["detail"]})
    emit({"type": "assembly_finished", "assembly": ASSEMBLY, "pass": report["pass"]})
    return {"assembly": ASSEMBLY, "pass": report["pass"], "gates": [gate], "checks": report["checks"],
            "report": f"{ASSEMBLY_OUT}/report.json", "claims": report["claims"],
            "artifacts": artifacts_of(project, ASSEMBLY_OUT)}


def project_parts_list(project, timeout=180):
    """The parts list of the project's assembly file as it is now (not as of the last run)."""
    from assembly.gate import evaluate_parts
    from assembly.parts_list import parts_list
    project = Path(project).resolve()
    designs_of(project)
    if not (project / ASSEMBLY).is_file():
        raise ProjectError(f"no {ASSEMBLY} in {project}")
    report = evaluate_parts(project / ASSEMBLY, project, timeout)
    failed = next((c for c in report["checks"] if c["name"] == "Assembly file" and c["status"] == "FAIL"), None)
    if failed:
        raise ProjectError(f"the assembly file does not build: {failed['detail']}")
    return parts_list(report)


def verdict_artifacts(verdict):
    """Every artifact a verdict names, relative to the outputs folder."""
    entries = verdict["designs"] + ([verdict["assembly"]] if verdict.get("assembly") else [])
    return [path for entry in entries for path in entry["artifacts"]]


def artifact_path(project, relative):
    """Resolve an artifact inside the project's outputs folder, refusing anything outside it."""
    outputs = (Path(project) / OUTPUTS).resolve()
    target = (outputs / relative).resolve()
    if outputs not in target.parents or not target.is_file() or target.suffix not in ARTIFACT_TYPES:
        return None
    return target
