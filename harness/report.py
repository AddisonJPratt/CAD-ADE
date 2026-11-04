"""Write report.json and report.md."""
import json


def fmt(value, digits=3):
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def sweep_lines(sweep):
    lines = [f"**{sweep['passed']}/{sweep['total']} samples pass** "
             f"(share {sweep['pass_share']:.0%}, required {sweep['required_share']:.0%}). "
             f"Dead params: {', '.join(sweep['dead_params']) or 'none'}. "
             f"Printability, informational: {sweep['printable_passed']}/{sweep['total']} pass; worst "
             f"support risk {sweep['max_support_risk_pct']:.1f} %, worst brief overhang "
             f"{sweep['max_overhang_brief_pct']:.1f} %.", "",
             "| Sample | Result | Volume mm³ | Printable | Problems |", "|---|---|---|---|---|"]
    for row in sweep["rows"]:
        problems = "; ".join(row["problems"])[:160] or "-"
        lines.append(f"| {row['label']} | {'PASS' if row['pass'] else 'FAIL'} | "
                     f"{fmt(row.get('volume'), 0)} | {row['printable']} | {problems} |")
    return lines


def to_markdown(report):
    out = [f"# Magic CAD report: {report['design']}", "",
           f"**Overall: {'PASS' if report['pass'] else 'FAIL'}**  ",
           f"Command: `{report['command']}`  ", f"Brief: `{report['brief'] or 'none'}`  ",
           f"Parameters: `{json.dumps(report.get('params', {}))}`", "",
           "## Checks", "", "| Gate | Status | Detail |", "|---|---|---|"]
    for gate in report["gates"]:
        out.append(f"| {gate['name']} | {gate['status']} | {gate['detail']} |")
    geo = report.get("geometry")
    if geo and geo["dimensions"]:
        out += ["", "## Measured vs spec (reloaded STEP, ±0.1 mm)", "",
                "| Dimension | Spec | Measured | Delta | Result |", "|---|---|---|---|---|"]
        for row in geo["dimensions"]:
            out.append(f"| {row['name']} | {fmt(float(row['spec']))} | {fmt(row['measured'])} | "
                       f"{fmt(row['delta'])} | {'PASS' if row['pass'] else 'FAIL'} |")
    for part, data in (report.get("printability") or {}).items():
        m = data["metrics"]
        feature = m.get("min_feature", {})
        out += ["", f"## Printability: {part} (reloaded STL)", "",
                f"- Watertight: {m['watertight']}; components: {m['components']}; faces: {m['faces']}",
                f"- Extents: {' x '.join(fmt(e, 2) for e in m['extents'])} mm; fits 250x250 bed: {m['fits_bed']}",
                f"- Brief overhang metric (downward faces >45° from straight down): {m['overhang_brief_pct']:.2f} %",
                f"- Support-risk metric (within 45° of straight down, off the bed): {m['support_risk_pct']:.2f} %",
                f"- Flat undersides above bed: {m['flat_undersides_above_bed_mm2']:.2f} mm²; bed contact: {m['bed_contact_mm2']:.0f} mm²",
                f"- Thinnest section (approximate, section sampling): ~{fmt(feature.get('mm'), 1)} mm "
                f"(step {fmt(feature.get('resolution_mm'), 1)}; short tabs read high) at {feature.get('where')}"
                + (" **below 2 perimeters**" if m.get("min_feature_warning") else "")]
    for row in report.get("overlaps") or []:
        out.append(f"- Overlap {row['a']} / {row['b']}: {row['volume']:.3f} mm³")
    if report.get("sweep"):
        out += ["", "## Parameter sweep", ""] + sweep_lines(report["sweep"])
    assumptions = report.get("assumptions") or []
    if assumptions:
        out += ["", "## Assumptions surfaced", ""] + [f"- {a}" for a in assumptions]
    if report.get("renders"):
        out += ["", "## Renders (flat QA renders)", ""]
        out += [f"![{p.rsplit('/', 1)[-1]}](renders/{p.rsplit('/', 1)[-1]})" for p in report["renders"]]
    if report.get("traceback"):
        out += ["", "## Traceback", "", "```", report["traceback"], "```"]
    return "\n".join(out) + "\n"


def write_reports(report, out_dir, stem="report"):
    (out_dir / f"{stem}.json").write_text(json.dumps(report, indent=2, default=str))
    (out_dir / f"{stem}.md").write_text(to_markdown(report))
