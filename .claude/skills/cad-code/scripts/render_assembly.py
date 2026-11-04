#!/usr/bin/env python3
"""
render_assembly.py — like render_stl.py, but for multi-part assemblies where
each named part should render in its own color (walls vs. roof vs. door vs.
glazing, etc.). Still pure matplotlib/Agg, still headless-safe, still no X
server or OpenGL dependency.

Usage (as a library):

    from render_assembly import render_assembly

    render_assembly(
        parts=[
            ("walls.stl",        "#d9cdb8"),
            ("roof.stl",         "#8c3a26"),
            ("door.stl",         "#59331a"),
            ("window_front.stl", "#99ccdd"),
            ("window_side.stl",  "#99ccdd"),
        ],
        out_path="render_iso.png",
        view="iso",
    )

Prints combined bounding-box dimensions as JSON, same convention as
render_stl.py, computed across all parts together.
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


def hex_to_rgb(color):
    color = color.lstrip("#")
    return np.array([int(color[i:i+2], 16) / 255 for i in (0, 2, 4)])


def shaded_colors(normals, light_dir, base_rgb):
    light_dir = light_dir / np.linalg.norm(light_dir)
    intensity = np.clip(normals @ light_dir, 0.15, 1.0)
    intensity = 0.35 + 0.65 * intensity
    colors = np.clip(base_rgb[None, :] * intensity[:, None], 0, 1)
    return colors


def render_assembly(parts, out_path, view="iso", imgsize=(1100, 850), dpi=150, alpha=None):
    """parts: list of (stl_path, hex_color[, alpha]) tuples."""
    fig = plt.figure(figsize=(imgsize[0] / dpi, imgsize[1] / dpi), dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_proj_type("persp")

    light_dir = np.array([0.4, -0.5, 0.75])
    all_mins, all_maxs = [], []

    # Sort parts back-to-front-ish by centroid depth along the view direction
    # so overlapping faces composite more sensibly — matplotlib's per-
    # collection z-order isn't a true depth buffer, so for busy scenes
    # generate a couple of views and pick the clean one.
    loaded = []
    for entry in parts:
        stl_path, color = entry[0], entry[1]
        part_alpha = entry[2] if len(entry) > 2 else (alpha if alpha is not None else 1.0)
        m = mesh.Mesh.from_file(stl_path)
        vectors = m.vectors
        pts = vectors.reshape(-1, 3)
        all_mins.append(pts.min(axis=0))
        all_maxs.append(pts.max(axis=0))
        centroid_depth = pts.mean(axis=0) @ np.array([0.6, -0.6, 0.5])
        loaded.append((centroid_depth, stl_path, vectors, color, part_alpha))

    loaded.sort(key=lambda t: t[0])  # painter's algorithm, back to front

    for _, stl_path, vectors, color, part_alpha in loaded:
        normals = np.cross(vectors[:, 1] - vectors[:, 0], vectors[:, 2] - vectors[:, 0])
        norm_len = np.linalg.norm(normals, axis=1, keepdims=True)
        norm_len[norm_len == 0] = 1
        normals = normals / norm_len
        base_rgb = hex_to_rgb(color)
        colors = shaded_colors(normals, light_dir, base_rgb)
        face_colors = np.hstack([colors, np.full((len(colors), 1), part_alpha)])
        poly = Poly3DCollection(vectors, facecolor=face_colors, edgecolor=(0, 0, 0, 0.12), linewidths=0.2)
        ax.add_collection3d(poly)

    mins = np.min(all_mins, axis=0)
    maxs = np.max(all_maxs, axis=0)
    dims = (maxs - mins).tolist()
    center = (maxs + mins) / 2

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
    ap.add_argument("out_path")
    ap.add_argument("--parts", required=True,
                     help="JSON file: list of [stl_path, hex_color] or [stl_path, hex_color, alpha]")
    ap.add_argument("--view", default="iso", choices=list(VIEWS.keys()))
    args = ap.parse_args()

    with open(args.parts) as f:
        parts = [tuple(p) for p in json.load(f)]

    try:
        result = render_assembly(parts, args.out_path, view=args.view)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
