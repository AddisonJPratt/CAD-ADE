"""Evidence attached to claims in a gate report.

A gate describes a computed check, not a physical outcome. Future slicer and
print-result integrations may add stronger evidence only when they have it.
"""


def claims_for_report(report):
    claims = [{"claim": gate["name"], "tier": "computed", "status": gate["status"],
               "detail": gate["detail"]} for gate in report["gates"]]
    for row in (report.get("geometry") or {}).get("dimensions", []):
        claims.append({"claim": f"Dimension: {row['name']}", "tier": "computed",
                       "status": "PASS" if row["pass"] else "FAIL",
                       "detail": f"Measured {row['measured']}; specified {row['spec']} (mm)."})
    for name, part in (report.get("printability") or {}).items():
        metrics = part["metrics"]
        claims.append({"claim": f"Printability metrics: {name}", "tier": "computed",
                       "status": "PASS" if part["pass"] else "FAIL",
                       "detail": f"Watertight: {metrics['watertight']}; support risk: "
                                 f"{metrics['support_risk_pct']:.2f}%; brief overhang: "
                                 f"{metrics['overhang_brief_pct']:.2f}%."})
    for row in (report.get("sweep") or {}).get("rows", []):
        claims.append({"claim": f"Sweep sample: {row['label']}", "tier": "computed",
                       "status": "PASS" if row["pass"] else "FAIL",
                       "detail": "; ".join(row["problems"]) or "Sample passed geometry checks."})
    claims.append({"claim": "Physical fit and performance", "tier": "needs physical test",
                   "status": "NOT TESTED", "detail": "No physical print result recorded."})
    return claims


SLICER_BACKED = ("3 Printability", "Printability metrics: ")
SLICER_MISSING = ("ElegooSlicer is not installed: not sliced. Install ElegooSlicer, or set "
                  "MAGIC_ELEGOO_SLICER to its executable.")


def duration(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m {secs}s"


def apply_slice(claims, result):
    """Claims after a slicer check. A clean slice upgrades the printability claims it backs to
    slicer-checked; a failed or missing slice upgrades nothing and says why in a Slice claim.
    result None means no slicer; result["ran"] False means the slicer could not be set up."""
    if result is None or not result.get("ran", True):
        reason = "; ".join(result["problems"]) if result else SLICER_MISSING
        return [*claims, {"claim": "Slice", "tier": "computed", "status": "NOT RUN", "detail": reason}]
    setup = (f"{result['slicer']}, {result['printer']}, {result['process'].split(' @')[0]} process, "
             f"{result['material']} ({result['filament']})")
    if not result["ok"]:
        return [*claims, {"claim": "Slice", "tier": "slicer-checked", "status": "FAIL",
                          "detail": f"{setup}: " + "; ".join(result["problems"]) + "."}]
    supports = ("no supports" if not result["support_used"] else
                f"supports used ({result['support_filament_mm']:.0f} mm of filament)")
    layers = f", {result['layers']} layers" if result.get("layers") else ""
    found = (f"{duration(result['print_seconds'])} print time, {result['filament_m']:.2f} m / "
             f"{result['filament_g']:.2f} g filament, {supports}{layers}")
    upgraded = [{**c, "tier": "slicer-checked", "detail": f"{c['detail'].rstrip('. ')}. Sliced cleanly: {found}."}
                if c["tier"] == "computed" and c["status"] == "PASS" and c["claim"].startswith(SLICER_BACKED)
                else c for c in claims]
    return [*upgraded, {"claim": "Slice", "tier": "slicer-checked", "status": "PASS",
                        "detail": f"{setup}: {found}. 3MF: {result['three_mf']}."}]
