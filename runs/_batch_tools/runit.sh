#!/bin/bash
# usage: runit.sh stem ; full harness run with wall clock and key numbers
cd /home/hatch/workspace/magic-cad
s=$SECONDS
.venv/bin/python magic.py run designs/$1.py --brief evals/briefs/$1.yaml --out runs/$1
code=$?
echo "exit=$code wall=$((SECONDS-s))s"
.venv/bin/python - "$1" <<'P'
import json,sys
r=json.load(open(f"runs/{sys.argv[1]}/report.json"))
g=r.get("geometry",{})
for d in g.get("dimensions",[]): print(" ",d["name"],d["spec"],d["measured"],d["pass"])
print("  bbox",g.get("bbox"))
for n,p in r.get("printability",{}).items():
    m=p["metrics"];print("  ",n,{k:round(m[k],1) for k in("overhang_brief_pct","support_risk_pct","bed_contact_mm2","flat_undersides_above_bed_mm2")},"minfeat",m.get("min_feature",{}).get("mm"),"warn",m.get("min_feature_warning"))
s=r.get("sweep")
if s:
    print("  sweep",s["passed"],s["total"],"dead",s["dead_params"],"printable",s["printable_passed"],"maxrisk",round(s["max_support_risk_pct"],1),"maxbrief",round(s["max_overhang_brief_pct"],1))
    for row in s["rows"]:
        if not row["pass"] or not row.get("printable"): print("   ",row["label"],row["params"] if row['label'].startswith('combo') else '',row["problems"],row.get("printable"),round(row.get("support_risk_pct",0),1),round(row.get("overhang_brief_pct",0),1))
P
