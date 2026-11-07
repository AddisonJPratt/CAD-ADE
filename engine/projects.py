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

from harness.pipeline import run as run_design

OUTPUTS = "outputs"
ASSEMBLY = "assembly.py"
ASSEMBLY_OUT = "_assembly"   # a leading _ can never be a design stem (designs_of skips them)
ARTIFACT_TYPES = {".stl": "model/stl", ".step": "model/step", ".png": "image/png",
                  ".json": "application/json", ".md": "text/markdown; charset=utf-8"}


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


def artifacts_of(project, stem):
    """Files a run left for one design, as paths relative to the project's outputs folder."""
    folder = Path(project) / OUTPUTS / stem
    if not folder.is_dir():
        return []
    return sorted(p.relative_to(folder.parent).as_posix() for p in folder.rglob("*")
                  if p.is_file() and p.suffix in ARTIFACT_TYPES)


def run_project(project, on_event=None, samples=None, timeout=180):
    """Run every gate on every design in the project. Returns (exit code, verdict).

    on_event receives the pipeline's gate events plus run_started, design_started,
    design_finished, assembly_started, assembly_finished and run_finished. The exit code is 0
    only if every design, and the assembly when there is one, passes.
    """
    emit = on_event or (lambda event: None)
    project = Path(project).resolve()
    designs = designs_of(project)
    verdict = {"project": str(project), "started": now(), "pass": False, "designs": []}
    emit({"type": "run_started", "project": str(project), "designs": [d.name for d in designs]})
    began = time.time()
    for design in designs:
        emit({"type": "design_started", "design": design.name})
        out = project / OUTPUTS / design.stem
        command = f"engine run {design.relative_to(project).as_posix()}"
        _, report = run_design(design, out=out, samples=samples, timeout=timeout,
                               command=command, on_event=on_event)
        entry = {"design": design.name, "pass": report["pass"], "gates": report["gates"],
                 "report": f"{design.stem}/report.json", "claims": report["claims"],
                 "artifacts": artifacts_of(project, design.stem)}
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
