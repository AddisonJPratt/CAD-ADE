"""Eyes (#79): instruments the agent reads back after a build. Read-only, never a gate.

Written beside Gate 4's renders into <out>/eyes/ from the same reloaded STLs:

- overhang_heatmap.png: the part seen from below, downward faces coloured by angle from
  straight down, using the printability gate's own thresholds
- section_thinnest_wall.png: a section through the plane where Gate 3 found the thinnest wall
- section_<feature>.png: a section through the centre of each named feature (library.feature)
- <part>.faces.json: the worker's face map, kept even in check mode and on a failed gate
- eyes.json: every path above plus per-part metrics (bbox, volume, overhang shares, min wall,
  unsupported area)

Nothing here changes a gate's status. Face maps and PNGs are not printable files, so a failed
gate keeping them does not leave anything that looks approved.
"""
import json
import re
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Patch

from .printability import BED_Z_TOL, VERTICAL_EPS
from .render import LABEL, SIZE, save_section, zbuffer

FOLDER = "eyes"
MAX_FEATURE_SECTIONS = 6
# (name, rgb), in class-index order. Angles are from straight down, as Gate 3 measures them.
OVERHANG_CLASSES = [
    ("up or vertical", (0.80, 0.80, 0.80)),
    ("bed", (0.35, 0.55, 0.85)),
    ("needs support (0-45 deg)", (0.80, 0.10, 0.10)),
    ("steep, self-supporting (45-60 deg)", (0.95, 0.55, 0.15)),
    ("near vertical (60-90 deg)", (0.95, 0.85, 0.30)),
]
BELOW = np.array([1.0, -1.0, -0.8])   # viewer direction for the heatmap: from below, so undersides show


def overhang_classes(mesh):
    """Index into OVERHANG_CLASSES for each face, with the printability gate's own definitions."""
    normals = mesh.face_normals
    down = normals[:, 2] < -VERTICAL_EPS
    angle = np.degrees(np.arccos(np.clip(-normals[:, 2], -1, 1)))
    on_bed = down & (angle < 1.0) & (mesh.triangles[:, :, 2].max(axis=1) <= mesh.bounds[0, 2] + BED_Z_TOL)
    classes = np.zeros(len(mesh.faces), dtype=int)
    classes[down & (angle <= 45) & ~on_bed] = 2
    classes[down & (angle > 45) & (angle <= 60)] = 3
    classes[down & (angle > 60)] = 4
    classes[on_bed] = 1
    return classes


def below_basis():
    forward = BELOW / np.linalg.norm(BELOW)
    right = np.cross(np.array([0.0, 0.0, 1.0]), forward)
    right /= np.linalg.norm(right)
    return np.array([right, np.cross(forward, right), forward])


def save_heatmap(meshes, path, title):
    pieces, colors = [], []
    for mesh in meshes:
        classes = overhang_classes(mesh)
        for index, (_, rgb) in enumerate(OVERHANG_CLASSES):
            faces = np.flatnonzero(classes == index)
            if len(faces):
                pieces.append(mesh.submesh([faces], append=True))
                colors.append(rgb)
    image, scale, origin = zbuffer(pieces, below_basis(), colors=colors, ambient=0.6)
    fig, ax = plt.subplots(figsize=(7, 7), dpi=130)
    ax.imshow(image, origin="lower", interpolation="nearest",
              extent=[origin[0], origin[0] + SIZE * scale, origin[1], origin[1] + SIZE * scale])
    ax.set_xlabel("screen mm"), ax.set_ylabel("screen mm")
    ax.legend(handles=[Patch(color=rgb, label=name) for name, rgb in OVERHANG_CLASSES],
              loc="upper right", fontsize=7, framealpha=0.85)
    ax.set_title(f"{title}: overhang heatmap, seen from below\n{LABEL}", fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def feature_planes(face_map_files):
    """One section plane per named feature: through its faces' bbox centre, across its thinnest extent."""
    boxes = {}
    for path in face_map_files:
        for face in json.loads(path.read_text())["faces"]:
            if face["feature"]:
                low, high = np.array(face["bbox"]["min"]), np.array(face["bbox"]["max"])
                if face["feature"] in boxes:
                    old_low, old_high = boxes[face["feature"]]
                    low, high = np.minimum(low, old_low), np.maximum(high, old_high)
                boxes[face["feature"]] = (low, high)
    planes = []
    for name, (low, high) in list(boxes.items())[:MAX_FEATURE_SECTIONS]:
        axis = int(np.argmin(high - low))
        planes.append({"name": name, "axis": "XYZ"[axis], "offset": round(float((low[axis] + high[axis]) / 2), 3)})
    return planes


def part_metrics(mesh, printed):
    metrics = printed["metrics"]
    classes = overhang_classes(mesh)
    low, high = mesh.bounds
    wall = metrics.get("min_feature") or {}
    mm = lambda values: [round(float(v), 3) + 0.0 for v in values]   # + 0.0: no -0.0
    return {"bbox": {"min": mm(low), "max": mm(high), "size": mm(high - low)},
            "volume_mm3": round(float(mesh.volume), 1),
            "overhang_brief_pct": round(metrics["overhang_brief_pct"], 2),
            "support_risk_pct": round(metrics["support_risk_pct"], 2),
            "unsupported_area_mm2": round(float(mesh.area_faces[classes == 2].sum()), 1),
            "bed_contact_mm2": round(metrics["bed_contact_mm2"], 1),
            "min_wall_mm": round(wall["mm"], 2) if "mm" in wall else None,
            "min_wall_where": wall.get("where")}


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "feature"


def write_artefacts(parts, printed, views, design_section, out, title):
    """Write <out>/eyes/ and return its manifest. `parts` are worker part entries (stl, faces)."""
    folder = out / FOLDER
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    meshes = [trimesh.load_mesh(p["stl"]) for p in parts]
    face_maps = {}
    for part in parts:
        target = folder / f"{part['name']}.faces.json"
        shutil.copy2(part["faces"], target)
        face_maps[part["name"]] = str(target)
    heatmap = folder / "overhang_heatmap.png"
    save_heatmap(meshes, heatmap, title)
    sections = []
    thinnest = min((printed[p["name"]]["metrics"].get("min_feature") or {} for p in parts),
                   key=lambda w: w.get("mm", np.inf), default={})
    planes = ([{"name": "thinnest wall", **thinnest["where"]}] if thinnest.get("where") else [])
    planes += feature_planes([folder / f"{p['name']}.faces.json" for p in parts])
    for plane in planes:
        path = folder / f"section_{slug(plane['name'])}.png"
        save_section(meshes, plane, path, f"{title} ({plane['name']})")
        sections.append({**plane, "path": str(path)})
    manifest = {"views": views, "design_section": design_section, "overhang_heatmap": str(heatmap),
                "sections": sections, "face_maps": face_maps,
                "metrics": {p["name"]: part_metrics(m, printed[p["name"]]) for p, m in zip(parts, meshes)},
                "manifest": str(folder / "eyes.json")}
    (folder / "eyes.json").write_text(json.dumps(manifest, indent=1))
    return manifest
