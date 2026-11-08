"""Gate 4: flat z-buffer QA renders from reloaded STLs. Engineering checks, not beauty shots."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh

from .printability import section_segments, rasterize_section

SIZE = 900
LABEL = "QA render (flat z-buffer): engineering check only"
PALETTE = np.array([[0.62, 0.72, 0.85], [0.90, 0.68, 0.45], [0.60, 0.82, 0.62], [0.82, 0.62, 0.82]])
LIGHT = np.array([0.35, 0.45, 0.82])


def view_basis(view):
    """Rows are the screen right, screen up and toward-viewer axes."""
    forward = {"iso": np.array([1.0, -1.0, 0.8]), "front": np.array([0.0, -1.0, 0.0]),
               "top": np.array([0.0, 0.0, 1.0]), "side": np.array([1.0, 0.0, 0.0])}[view]
    forward = forward / np.linalg.norm(forward)
    up = np.array([0.0, 1.0, 0.0]) if view == "top" else np.array([0.0, 0.0, 1.0])
    right = np.cross(up, forward)
    right /= np.linalg.norm(right)
    return np.array([right, np.cross(forward, right), forward])


def zbuffer(meshes, view, size=SIZE, colors=None, background=(1.0, 1.0, 1.0), ambient=0.35):
    """Rasterize meshes orthographically. Returns (rgb image, mm per pixel, mins).

    `view` is a named view or a 3x3 basis (rows: screen right, screen up, toward the viewer);
    `colors` gives one rgb per mesh, default the QA palette; `ambient` is the darkest shade factor."""
    basis = view_basis(view) if isinstance(view, str) else np.asarray(view, dtype=float)
    all_pts = np.vstack([m.vertices @ basis.T for m in meshes])
    mins, maxs = all_pts[:, :2].min(axis=0), all_pts[:, :2].max(axis=0)
    scale = (maxs - mins).max() / (size * 0.9)
    pad = (size * scale - (maxs - mins)) / 2
    depth = np.full((size, size), -np.inf)
    image = np.ones((size, size, 3)) * np.asarray(background, dtype=float)
    for index, mesh in enumerate(meshes):
        tris = mesh.triangles @ basis.T
        xy = (tris[:, :, :2] - mins + pad) / scale
        shade = ambient + (1 - ambient) * np.abs(mesh.face_normals @ (LIGHT / np.linalg.norm(LIGHT)))
        color = PALETTE[index % len(PALETTE)] if colors is None else np.asarray(colors[index], dtype=float)
        for tri, z, s in zip(xy, tris[:, :, 2], shade):
            x0, y0 = np.floor(tri.min(axis=0)).astype(int)
            x1, y1 = np.ceil(tri.max(axis=0)).astype(int) + 1
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size), min(y1, size)
            if x0 >= x1 or y0 >= y1:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = tri
            det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(det) < 1e-12:
                continue
            w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / det
            w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / det
            w2 = 1 - w0 - w1
            hit = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
            zs = w0 * z[0] + w1 * z[1] + w2 * z[2]
            nearer = hit & (zs > depth[y0:y1, x0:x1])
            depth[y0:y1, x0:x1][nearer] = zs[nearer]
            image[y0:y1, x0:x1][nearer] = color * s
    # Dark outlines at depth jumps make edges readable on flat shading.
    finite = np.where(np.isfinite(depth), depth, depth[np.isfinite(depth)].min() - 100 * scale)
    edge = (np.abs(np.gradient(finite)[0]) + np.abs(np.gradient(finite)[1])) > 1.5 * scale * 2
    image[edge] = 0.15
    return image, scale, mins - pad


def save_view(meshes, view, path, title):
    image, scale, origin = zbuffer(meshes, view)
    fig, ax = plt.subplots(figsize=(7, 7), dpi=130)
    extent = [origin[0], origin[0] + SIZE * scale, origin[1], origin[1] + SIZE * scale]
    ax.imshow(image, origin="lower", extent=extent, interpolation="nearest")
    labels = {"front": ("X (mm)", "Z (mm)"), "top": ("X (mm)", "Y (mm)"),
              "side": ("Y (mm)", "Z (mm)"), "iso": ("screen mm", "screen mm")}[view]
    ax.set_xlabel(labels[0]), ax.set_ylabel(labels[1])
    ax.set_title(f"{title}: {view}\n{LABEL}", fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_section(meshes, plane, path, title):
    """Fill the section by parity; axis/offset come from the design or the mid-plane."""
    all_bounds = np.array([m.bounds for m in meshes])
    if plane is None:
        plane = {"axis": "Y", "offset": float(all_bounds[:, :, 1].mean())}
    axis = "XYZ".index(plane["axis"].upper())
    offset = plane["offset"] + 1.3e-3
    fig, ax = plt.subplots(figsize=(7, 7), dpi=130)
    keep = [i for i in range(3) if i != axis]
    for index, mesh in enumerate(meshes):
        segments = section_segments(mesh, axis, offset)
        if not len(segments):
            continue
        pixel = max(0.05, float(mesh.extents.max()) / 2000)
        mask, x0, y0 = rasterize_section(segments, pixel)
        rgba = np.zeros((*mask.shape, 4))
        rgba[mask] = [*PALETTE[index % len(PALETTE)], 1.0]
        ax.imshow(rgba, origin="lower", interpolation="nearest",
                  extent=[x0, x0 + mask.shape[1] * pixel, y0, y0 + mask.shape[0] * pixel])
        for a, b in segments:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="k", linewidth=0.5)
    ax.set_aspect("equal")
    ax.autoscale()
    ax.set_xlabel(f"{'XYZ'[keep[0]]} (mm)"), ax.set_ylabel(f"{'XYZ'[keep[1]]} (mm)")
    ax.set_title(f"{title}: section at {plane['axis'].upper()}={plane['offset']:.2f}\n{LABEL}",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def render_all(stl_paths, out_dir, title, section_plane=None):
    """Write iso/front/top/side/section PNGs from STLs reloaded off disk."""
    out_dir.mkdir(parents=True, exist_ok=True)
    meshes = [trimesh.load_mesh(p) for p in stl_paths.values()]
    files = []
    for view in ("iso", "front", "top", "side"):
        files.append(out_dir / f"{view}.png")
        save_view(meshes, view, files[-1], title)
    files.append(out_dir / "section.png")
    save_section(meshes, section_plane, files[-1], title)
    return [str(f) for f in files]
