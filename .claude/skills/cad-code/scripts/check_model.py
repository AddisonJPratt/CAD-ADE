#!/usr/bin/env python3
"""
check_model.py — geometry sanity checks to run before delivering any model.
Catches the failure classes that render fine in a preview but are broken as
solids: non-manifold meshes, degenerate/zero-area triangles, and wildly
off-scale results (a "small bracket" that's 4 meters across is a units bug,
not a design).

Usage:
    python3 check_model.py model.stl
    python3 check_model.py model.stl --expect-max-dim 500   # mm, sanity ceiling

Exits non-zero if any check fails, printing a JSON report either way.
"""
import argparse
import json
import sys

import numpy as np
from stl import mesh


def check(stl_path, expect_max_dim=None):
    report = {"file": stl_path, "checks": {}, "ok": True}

    m = mesh.Mesh.from_file(stl_path)
    vectors = m.vectors
    n_tris = len(vectors)
    report["checks"]["triangle_count"] = n_tris

    if n_tris == 0:
        report["ok"] = False
        report["checks"]["empty_mesh"] = True
        print(json.dumps(report, indent=2))
        return report

    # Degenerate triangles (zero or near-zero area) — usually a sign of
    # coincident-face boolean issues.
    v0, v1, v2 = vectors[:, 0], vectors[:, 1], vectors[:, 2]
    cross = np.cross(v1 - v0, v2 - v0)
    areas = 0.5 * np.linalg.norm(cross, axis=1)
    degenerate = int(np.sum(areas < 1e-9))
    report["checks"]["degenerate_triangles"] = degenerate
    if degenerate > 0:
        report["ok"] = False

    # Bounding box / overall dimensions
    all_pts = vectors.reshape(-1, 3)
    mins, maxs = all_pts.min(axis=0), all_pts.max(axis=0)
    dims = (maxs - mins).tolist()
    report["checks"]["bbox_mm"] = [round(d, 3) for d in dims]

    if min(dims) < 1e-6:
        report["ok"] = False
        report["checks"]["zero_thickness_axis"] = True

    if expect_max_dim and max(dims) > expect_max_dim:
        report["ok"] = False
        report["checks"]["exceeds_expected_max_dim"] = True

    # Watertightness proxy: every edge should be shared by exactly two
    # triangles in a closed manifold. This is an approximate check (uses
    # rounded vertex coordinates to find shared edges) — good enough to catch
    # gross manifold problems without a full CAD kernel.
    def edge_key(a, b, decimals=6):
        a = tuple(np.round(a, decimals))
        b = tuple(np.round(b, decimals))
        return (a, b) if a < b else (b, a)

    from collections import Counter
    edge_counts = Counter()
    for tri in vectors:
        for i in range(3):
            edge_counts[edge_key(tri[i], tri[(i + 1) % 3])] += 1

    bad_edges = sum(1 for c in edge_counts.values() if c != 2)
    report["checks"]["non_manifold_edges_approx"] = bad_edges
    if bad_edges > 0:
        report["ok"] = False

    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stl_path")
    ap.add_argument("--expect-max-dim", type=float, default=None)
    args = ap.parse_args()

    report = check(args.stl_path, expect_max_dim=args.expect_max_dim)
    sys.exit(0 if report["ok"] else 1)
