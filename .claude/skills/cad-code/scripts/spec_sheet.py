#!/usr/bin/env python3
"""
spec_sheet.py — composite a rendered preview with a dimensions/parameters
table into a single "spec sheet" image. This is the standard deliverable
for the cad-code skill: a render alone doesn't communicate exact sizes,
and a table alone has no picture to check against.

Usage (as a library — typical case, called from a small per-project script):

    from spec_sheet import build_spec_sheet

    build_spec_sheet(
        render_path="render_iso.png",
        out_path="spec_sheet.png",
        title="Phone Stand",
        rows=[
            ("base_w",   "70 mm", "Base width"),
            ("base_d",   "55 mm", "Base depth"),
            ("height",   "65 mm", "Overall height"),
            ("slot_w",   "9 mm",  "Phone thickness clearance"),
            ("slot_ang", "60°",  "Slot angle from horizontal"),
            ("lip_h",    "14 mm", "Front retaining lip height"),
        ],
        bbox_mm=(70.0, 55.0, 65.0),   # from render_stl.py's stdout, not guessed
    )

Also runnable standalone with a JSON rows file:

    python3 spec_sheet.py render.png spec_sheet.png --title "Phone Stand" \\
        --rows rows.json --bbox 70,55,65
"""
import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg


def build_spec_sheet(render_path, out_path, title, rows, bbox_mm=None, notes=None):
    """
    rows: list of (name, value, description) tuples.
    bbox_mm: optional (x, y, z) overall bounding box, shown as a header line —
             pull this from render_stl.py's output so it's measured, not typed.
    """
    img = mpimg.imread(render_path)

    fig = plt.figure(figsize=(12.5, 6.4), dpi=160)
    fig.patch.set_facecolor("white")

    ax_img = fig.add_axes([0.02, 0.06, 0.44, 0.86])
    ax_img.imshow(img)
    ax_img.set_axis_off()

    ax_table = fig.add_axes([0.49, 0.06, 0.49, 0.86])
    ax_table.set_axis_off()

    fig.text(0.49, 0.94, title, fontsize=18, fontweight="bold", va="top")
    y = 0.87
    if bbox_mm:
        bbox_str = f"Overall envelope: {bbox_mm[0]:.1f} × {bbox_mm[1]:.1f} × {bbox_mm[2]:.1f} mm"
        fig.text(0.49, y, bbox_str, fontsize=10.5, color="#444444", va="top")
        y -= 0.055

    table_data = [[n, v, d] for n, v, d in rows]
    headers = ["Parameter", "Value", "Description"]

    # Manual column widths based on content length — auto_set_column_width
    # inside a fixed bbox doesn't reliably prevent clipping on longer values.
    col_chars = [
        max(len(str(r[c])) for r in ([headers] + table_data))
        for c in range(3)
    ]
    total = sum(col_chars)
    col_fracs = [c / total for c in col_chars]

    tbl = ax_table.table(
        cellText=table_data,
        colLabels=headers,
        cellLoc="left",
        colLoc="left",
        loc="upper left",
        colWidths=col_fracs,
        bbox=[0, max(0.0, y - 0.62 - 0.03), 1, 0.62],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)

    for (row, col), cell in tbl.get_celld().items():
        cell.PAD = 0.02
        cell.set_edgecolor("#dddddd")
        if row == 0:
            cell.set_facecolor("#2d3748")
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor("#f7f7f7" if row % 2 == 0 else "white")

    if notes:
        fig.text(0.49, max(0.03, y - 0.62 - 0.06), notes, fontsize=8.5,
                  color="#666666", va="top", wrap=True, style="italic")

    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("render_path")
    ap.add_argument("out_path")
    ap.add_argument("--title", default="Model")
    ap.add_argument("--rows", required=True, help="JSON file: list of [name, value, description]")
    ap.add_argument("--bbox", default=None, help="x,y,z in mm")
    ap.add_argument("--notes", default=None)
    args = ap.parse_args()

    with open(args.rows) as f:
        rows = [tuple(r) for r in json.load(f)]

    bbox = tuple(float(x) for x in args.bbox.split(",")) if args.bbox else None
    build_spec_sheet(args.render_path, args.out_path, args.title, rows, bbox_mm=bbox, notes=args.notes)
    print(f"wrote {args.out_path}")
