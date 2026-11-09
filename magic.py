#!/usr/bin/env python
"""Magic CAD harness CLI. Exit code 0 only if all gates pass.

  python magic.py run <design.py> [--brief brief.yaml] [--out runs/<name>] [--samples N]
  python magic.py run <design.py> --quick      build, geometry, printability only (seconds); a draft
  python magic.py sweep <design.py> [--brief brief.yaml] [--out dir] [--samples N]
  python magic.py check <design.py> [--brief brief.yaml] [--out dir] [--samples N] [--no-sweep]
  python magic.py evals [--quick] [--out dir] [--timeout S]
  python magic.py assembly <assembly.py> [--project folder] [--out dir]   the assembly gate
  python magic.py instructions <gate output folder> [--style illustrated|checklist] [--out dir] [--no-pdf]
  python magic.py project <folder> [--samples N] [--timeout S]   every design in a project folder
  python magic.py serve [--port 8766]                             the local engine API
  python magic.py new <folder> --from <design stem or .py>        a project folder, version 1
  python magic.py versions <folder>                               its version timeline
  python magic.py save <folder> -m "message"                      save the current files as a version
  python magic.py rollback <folder> <version number or id>        restore a version, re-run the gates

The CLI and the engine API call the same functions (harness.pipeline.run, engine.projects).
"""
import argparse
import sys

from harness.pipeline import run, sweep_only


def main():
    if sys.argv[1:2] == ["evals"]:   # takes no design, so it has its own arguments
        from evals.run_evals import main as run_evals
        return run_evals(sys.argv[2:])
    if sys.argv[1:2] == ["assembly"]:
        return assembly_command(sys.argv[2:])
    if sys.argv[1:2] == ["instructions"]:
        return instructions_command(sys.argv[2:])
    if sys.argv[1:2] in (["project"], ["serve"], ["new"], ["versions"], ["save"], ["rollback"]):
        return engine_command(sys.argv[1], sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["run", "sweep", "check"])
    parser.add_argument("design")
    parser.add_argument("--brief", help="brief YAML; default briefs/<design stem>.yaml if present")
    parser.add_argument("--out", help="output folder; default runs/<design stem>[-check|-sweep]")
    parser.add_argument("--samples", type=int, help="sweep sample cap (must cover min/max of each param)")
    parser.add_argument("--timeout", type=int, default=180, help="seconds per build subprocess")
    parser.add_argument("--no-sweep", action="store_true",
                        help="check only: skip the sweep; the report marks it NOT RUN, so this verifies nothing parametric")
    parser.add_argument("--quick", action="store_true",
                        help="run/check: build, geometry and printability only, for mid-session iteration; "
                             "renders, sweep and exports are NOT RUN, nothing is kept, so it verifies nothing "
                             "for release. Default output runs/<design stem>-quick")
    args = parser.parse_args()
    command = " ".join(["magic.py"] + sys.argv[1:])
    try:
        if args.no_sweep and args.command != "check":
            raise ValueError("--no-sweep is only allowed with check")
        if args.quick and (args.command == "sweep" or args.no_sweep):
            raise ValueError("--quick is only allowed with run or check, and already skips the sweep")
        if args.command == "sweep":
            code, report = sweep_only(args.design, args.brief, args.out, args.samples, args.timeout)
        else:
            code, report = run(args.design, args.brief, args.out, args.samples,
                               args.command == "run", args.timeout, command, args.no_sweep,
                               quick=args.quick)
    except ValueError as err:   # bad CLI values, e.g. --samples too small to cover the ranges
        print(f"error: {err}", file=sys.stderr)
        return 2
    for gate in report["gates"]:
        print(f"{gate['status']:8} {gate['name']:15} {gate['detail']}")
    quick = report.get("mode") == "quick"
    print("OVERALL", ("QUICK PASS (draft: run without --quick to verify)" if quick else "PASS")
          if report["pass"] else "FAIL")
    return code


def assembly_command(argv):
    from pathlib import Path
    from assembly.gate import run_gate
    parser = argparse.ArgumentParser(prog="magic.py assembly")
    parser.add_argument("file", help="an assembly file, e.g. <project>/assembly.py")
    parser.add_argument("--project", help="folder whose designs/ the assembly uses; default the file's folder")
    parser.add_argument("--out", help="report folder; default runs/<file stem>-assembly")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    path = Path(args.file)
    project = Path(args.project) if args.project else path.resolve().parent
    out = Path(args.out) if args.out else Path("runs") / f"{path.stem}-assembly"
    report = run_gate(path, project, out, timeout=args.timeout)
    for check in report["checks"]:
        print(f"{check['status']:8} {check['name']:15} {check['detail']}")
    print("OVERALL", "PASS" if report["pass"] else "FAIL")
    return 0 if report["pass"] else 1


def instructions_command(argv):
    from pathlib import Path
    from assembly.instructions import STYLES, export
    from assembly.manifest import MANIFEST
    parser = argparse.ArgumentParser(prog="magic.py instructions",
                                     description="Assembly instructions from the gate's assembly manifest.")
    parser.add_argument("folder", help=f"a folder the assembly gate wrote, holding {MANIFEST} and meshes/")
    parser.add_argument("--style", choices=STYLES, default=STYLES[0],
                        help="illustrated: a rendered image per step (default); checklist: compact tick list")
    parser.add_argument("--out", help="where to write the HTML and PDF; default the folder itself")
    parser.add_argument("--no-pdf", action="store_true", help="write the HTML only")
    args = parser.parse_args(argv)
    folder = Path(args.folder)
    if not (folder / MANIFEST).is_file():
        print(f"error: no {MANIFEST} in {folder}; run `magic.py assembly` first", file=sys.stderr)
        return 2
    try:
        files = export(folder, Path(args.out) if args.out else folder, args.style, pdf=not args.no_pdf)
    except RuntimeError as err:   # no browser for the PDF, or it failed
        print(f"error: {err}", file=sys.stderr)
        return 1
    for path in files.values():
        print(path)
    return 0


def print_versions(rows):
    for v in rows:
        verdict = "not run" if v["verdict"] is None else ("PASS" if v["verdict"]["pass"] else "FAIL")
        print(f"{'*' if v['current'] else ' '} v{v['number']:<3} {v['timestamp']}  {verdict:8} {v['message']}")
    return 0


def engine_command(command, argv):
    parser = argparse.ArgumentParser(prog=f"magic.py {command}")
    if command == "serve":
        from engine.api import PORT, serve
        parser.add_argument("--port", type=int, default=PORT)
        parser.add_argument("--agent", choices=("claude", "scripted"), default="claude")
        args = parser.parse_args(argv)
        return serve(args.port, args.agent)
    from engine import versions
    from engine.projects import ProjectError, run_project
    parser.add_argument("folder")
    if command == "new":
        parser.add_argument("--from", dest="source", required=True)
    if command == "save":
        parser.add_argument("-m", "--message", required=True)
    if command == "rollback":
        parser.add_argument("version")
    if command in ("project", "rollback"):
        parser.add_argument("--samples", type=int)
        parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    try:
        if command == "new":
            folder = versions.create_project(args.folder, args.source)
            print(f"created {folder}")
            return print_versions(versions.list_versions(folder))
        if command == "versions":
            return print_versions(versions.list_versions(args.folder))
        if command == "save":
            return print_versions([versions.save_version(versions.require_versioned(args.folder),
                                                         args.message)])
        if command == "rollback":
            new, target = versions.restore_version(args.folder, args.version)
            print(f"restored version {target['number']} as version {new['number']}; re-running the gates")
        code, verdict = run_project(args.folder, samples=args.samples, timeout=args.timeout)
    except (ProjectError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    for design in verdict["designs"]:
        print(f"{'PASS' if design['pass'] else 'FAIL':8} {design['design']}")
        for gate in design["gates"]:
            print(f"  {gate['status']:8} {gate['name']:15} {gate['detail']}")
    print("OVERALL", "PASS" if verdict["pass"] else "FAIL")
    return code


if __name__ == "__main__":
    sys.exit(main())
