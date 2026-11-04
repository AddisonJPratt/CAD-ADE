#!/usr/bin/env python3
"""
render_stl.py — universal, headless, shaded preview renderer for STL files.

Works identically regardless of which CAD tool produced the STL (OpenSCAD,
CadQuery, Build123d), so it's the one rendering code path for all three —
no X server, no OpenGL, no segfaults. Pure matplotlib (Agg backend) + numpy.

Usage:
    python3 render_stl.py model.stl preview.png
    python3 render_stl.py model.stl preview.png --view iso       # default
    python3 render_stl.py model.stl preview.png --view front
    python3 render_stl.py model.stl preview.png --view top
    python3 render_stl.py model.stl preview.png --view right
    python3 render_stl.py model.stl preview.png --color "#4a90d9"

Prints the model's bounding-box dimensions (mm) to stdout as JSON on the
last line, so callers can capture real dimensions instead of trusting
hand-typed parameter comments.
"""
import argparse
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from stl import mesh

VIEWS = {
    "iso":   dict(elev=28, azim=-50),
    "front": dict(elev=0,  azim=-90),
    "top":   dict(elev=90, azim=-90),
    "right": dict(elev=0,  azim=0),
}


def shaded_colors(normals, light_dir, base_rgb):
    light_dir = light_dir / np.linalg.norm(light_dir)
    intensity = np.clip(normals @ light_dir, 0.15, 1.0)  # ambient floor 0.15
    intensity = 0.35 + 0.65 * intensity  # compress so nothing goes fully black
    base = np.array(base_rgb)
    colors = np.clip(base[None, :] * intensity[:, None], 0, 1)
    return colors


def render(stl_path, out_path, view="iso", color="#e8a33d", imgsize=(1000, 800), dpi=150):
    m = mesh.Mesh.from_file(stl_path)
    vectors = m.vectors  # (N, 3, 3)

    # Bounding box / real dimensions, computed from geometry — not assumed.
    all_pts = vectors.reshape(-1, 3)
    mins, maxs = all_pts.min(axis=0), all_pts.max(axis=0)
    dims = (maxs - mins).tolist()
    center = (maxs + mins) / 2

    normals = m.normals / np.linalg.norm(m.normals, axis=1, keepdims=True)
    base_rgb = np.array([int(color.lstrip("#")[i:i+2], 16) / 255 for i in (0, 2, 4)])

    fig = plt.figure(figsize=(imgsize[0] / dpi, imgsize[1] / dpi), dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_proj_type("persp")

    light_dir = np.array([0.4, -0.5, 0.75])
    colors = shaded_colors(normals, light_dir, base_rgb)

    poly = Poly3DCollection(vectors, facecolor=colors, edgecolor=(0, 0, 0, 0.15), linewidths=0.25)
    ax.add_collection3d(poly)

    radius = max(dims) / 2 * 1.15 if max(dims) > 0 else 1
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)
    ax.set_box_aspect([1, 1, 1])

    v = VIEWS.get(view, VIEWS["iso"])
    ax.view_init(elev=v["elev"], azim=v["azim"])
    ax.set_axis_off()
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    plt.tight_layout(pad=0)
    fig.savefig(out_path, facecolor="white", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)

    return {"dims_mm": [round(d, 2) for d in dims]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stl_path")
    ap.add_argument("out_path")
    ap.add_argument("--view", default="iso", choices=list(VIEWS.keys()))
    ap.add_argument("--color", default="#e8a33d")
    args = ap.parse_args()

    try:
        result = render(args.stl_path, args.out_path, view=args.view, color=args.color)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
