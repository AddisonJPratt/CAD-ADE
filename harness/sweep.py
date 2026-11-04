"""Parameter sweep: rebuild across each range and geometry-check every sample.

The gate passes only if every sampled combination passes AND every parameter visibly
changes the geometry between its min and max. A 'parameter' with no effect is a
hard-coded design wearing a parameter's name, so it fails.
Printability is also measured per sample and reported, but does not gate (per the brief).
"""
import random
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os

from .execute import run_worker
from .geometry import check_geometry
from .printability import check_stl

COMBOS_DEFAULT = 6
SAMPLES_LIMIT = 64
PASS_SHARE_REQUIRED = 1.0
DEAD_REL = 1e-6          # relative change below this counts as no change


def is_int(spec):
    return all(isinstance(v, int) for v in spec)


def plan_samples(declared, samples=None, seed=0):
    """Default, then each param at min and max, then corner/random combos, capped at samples."""
    required = 1 + 2 * len(declared)
    total = min(samples if samples is not None else required + COMBOS_DEFAULT, SAMPLES_LIMIT)
    if total < required:
        raise ValueError(f"--samples {total} too small: {required} needed for min/default/max "
                         f"of {len(declared)} params")
    plan = [("default", {})]
    for name, (_, low, high) in declared.items():
        plan += [(f"{name}=min", {name: low}), (f"{name}=max", {name: high})]
    if total > len(plan):
        plan.append(("all=min", {n: s[1] for n, s in declared.items()}))
    if total > len(plan):
        plan.append(("all=max", {n: s[2] for n, s in declared.items()}))
    rng = random.Random(seed)
    index = 1
    while len(plan) < total:
        combo = {}
        for name, spec in declared.items():
            if index % 2:       # corners stress interactions; interior samples catch the rest
                combo[name] = rng.choice(spec[1:])
            elif is_int(spec):
                combo[name] = rng.randint(spec[1], spec[2])
            else:
                combo[name] = round(rng.uniform(spec[1], spec[2]), 3)
        plan.append((f"combo{index}", combo))
        index += 1
    return plan


def fingerprint(result, printed):
    """Volume, bbox position and mesh second moments (these see symmetric hole moves)."""
    parts = result["parts"]
    return ([sum(p["volume"] for p in parts)]
            + [x for p in parts for x in p["bbox"]["min"] + p["bbox"]["max"]]
            + [x for p in printed for x in p["metrics"]["inertia"]])


def same_shape(a, b):
    return len(a) == len(b) and all(abs(x - y) <= DEAD_REL * max(abs(x), abs(y), 1.0)
                                    for x, y in zip(a, b))


def run_sample(design, brief, label, params, timeout, allow_supports):
    with tempfile.TemporaryDirectory(prefix="magic_sweep_") as tmp:
        result = run_worker(design, Path(tmp), params, timeout)
        row = {"label": label, "params": params, "seconds": result.get("seconds")}
        if not result["ok"]:
            problem = result["traceback"].strip().splitlines()[-1]
            row.update({"pass": False, "problems": [problem], "printable": None})
            return row, None
        geo = check_geometry(result, brief)
        printed = [check_stl(p["stl"], allow_supports, sections=False) for p in result["parts"]]
        row.update({"pass": geo["pass"], "problems": geo["problems"],
                    "volume": geo["volume"], "bbox": geo["bbox"],
                    "printable": all(p["pass"] for p in printed),
                    "support_risk_pct": max(p["metrics"]["support_risk_pct"] for p in printed),
                    "overhang_brief_pct": max(p["metrics"]["overhang_brief_pct"] for p in printed)})
        return row, fingerprint(result, printed)


def run_sweep(design, declared, brief=None, samples=None, timeout=180):
    """Run all samples in parallel subprocesses and return the sweep result dict."""
    plan = plan_samples(declared, samples)
    allow = bool(brief and brief["allow_supports"])
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        done = list(pool.map(lambda s: run_sample(design, brief, s[0], s[1], timeout, allow), plan))
    rows = [row for row, _ in done]
    prints = {row["label"]: fp for row, fp in done}
    dead = []
    for name in declared:
        low, high = prints.get(f"{name}=min"), prints.get(f"{name}=max")
        if low and high and same_shape(low, high):
            dead.append(name)
    passed = sum(1 for r in rows if r["pass"])
    share = passed / len(rows)
    return {"pass": share >= PASS_SHARE_REQUIRED and not dead, "total": len(rows), "passed": passed,
            "pass_share": share, "required_share": PASS_SHARE_REQUIRED, "dead_params": dead,
            "printable_passed": sum(1 for r in rows if r["printable"]),
            "max_support_risk_pct": max((r.get("support_risk_pct", 0) for r in rows), default=0),
            "max_overhang_brief_pct": max((r.get("overhang_brief_pct", 0) for r in rows), default=0),
            "rows": rows}
