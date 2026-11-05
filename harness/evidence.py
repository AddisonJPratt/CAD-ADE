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
