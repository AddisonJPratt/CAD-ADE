#!/usr/bin/env python
"""Magic CAD harness CLI. Exit code 0 only if all gates pass.

  python magic.py run <design.py> [--brief brief.yaml] [--out runs/<name>] [--samples N]
  python magic.py sweep <design.py> [--brief brief.yaml] [--out dir] [--samples N]
  python magic.py check <design.py> [--brief brief.yaml] [--out dir] [--samples N] [--no-sweep]
  python magic.py evals [--quick] [--out dir] [--timeout S]
"""
import argparse
import sys

from harness.pipeline import run, sweep_only


def main():
    if sys.argv[1:2] == ["evals"]:   # takes no design, so it has its own arguments
        from evals.run_evals import main as run_evals
        return run_evals(sys.argv[2:])
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
    args = parser.parse_args()
    command = " ".join(["magic.py"] + sys.argv[1:])
    try:
        if args.no_sweep and args.command != "check":
            raise ValueError("--no-sweep is only allowed with check")
        if args.command == "sweep":
            code, report = sweep_only(args.design, args.brief, args.out, args.samples, args.timeout)
        else:
            code, report = run(args.design, args.brief, args.out, args.samples,
                               args.command == "run", args.timeout, command, args.no_sweep)
    except ValueError as err:   # bad CLI values, e.g. --samples too small to cover the ranges
        print(f"error: {err}", file=sys.stderr)
        return 2
    for gate in report["gates"]:
        print(f"{gate['status']:8} {gate['name']:15} {gate['detail']}")
    print("OVERALL", "PASS" if report["pass"] else "FAIL")
    return code


if __name__ == "__main__":
    sys.exit(main())
