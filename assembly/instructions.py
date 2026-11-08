"""Assembly instructions, generated from the assembly manifest and nothing else.

Both styles render one step list (`steps`), so they cannot disagree:
- illustrated (default): each step with a rendered image of that stage, the hardware callout and
  the tool;
- checklist: one compact row per step with a tick box, the same text, callout and tool.
`export` writes either style as a standalone HTML file (images inline) and prints that same file
to PDF with headless Chrome/Chromium, so the PDF is the HTML, not a second layout.

A stage image shows what is already built in a quiet blue-grey and the parts this step adds in
the accent colour, backed out along their joint by their own explode distance (the manifest's
explode rule), with an arrow to where each one seats. Every stage uses one camera (`camera`):
the corner view, of a fixed set, that shows the most of the new parts (a quick low-resolution
render of each); ties keep the first, the usual front-right isometric.
"""
import base64
import glob
import html as markup
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh

from harness.render import zbuffer

from .manifest import MANIFEST, quaternion_matrix

STYLES = ('illustrated', 'checklist')   # the first is the default
ACCENT = (0.839, 0.357, 0.145) # parts added in this step: Studio's accent orange, #d65b25
BUILT = (0.60, 0.66, 0.74)     # parts placed in earlier steps: a cool grey that reads against it
PAPER = (0.980, 0.976, 0.965)  # render background (#faf9f6, the sheet); written out transparent
IMAGE_PX = 720                 # stage image edge, px
AMBIENT = 0.55                 # darkest face shade: lighter than the QA renders so faces read on paper
ARROW = (0.596, 0.2, 0.0)      # seat arrows: Studio accent ink, #983300
PDF_TIMEOUT = 120              # s: headless browser print
BROWSERS = ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
            'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome', 'msedge')
ARROW_MIN = 0.5                # mm: shorter travel than this gets no arrow
TRIAL_PX = 140                 # edge of the low-resolution renders that pick the camera
TIE = 1.05                     # a later view must show this many times more of the new parts to win
CORNERS = [np.array(c, dtype=float) for c in   # toward-viewer directions; first wins a tie
           ((1, -1, 0.8), (-1, -1, 0.8), (1, 1, 0.8), (-1, 1, 0.8),
            (1, -1, 2.0), (-1, -1, 2.0), (1, 1, 2.0), (-1, 1, 2.0))]


def steps(manifest):
    """The step list both styles render: the manifest's steps plus what is new and already built."""
    names = {i['id']: i['name'] for i in manifest['instances']}
    built, rows = [], []
    for step in manifest['steps']:
        new = list(step['part_ids'])
        rows.append({'number': step['number'], 'text': step['text'], 'tool': step['tool'],
                     'callout': step['callout'], 'new': new, 'built': list(built),
                     'parts': [names[i] for i in new]})
        built += new
    return rows


def _placed(instance, folder):
    mesh = trimesh.load(Path(folder) / instance['mesh'], force='mesh')
    matrix = np.eye(4)
    matrix[:3, :3] = quaternion_matrix(instance['transform']['quaternion'])
    matrix[:3, 3] = instance['transform']['position']
    return mesh.apply_transform(matrix)


def _basis(forward):
    forward = forward / np.linalg.norm(forward)
    right = np.cross([0.0, 0.0, 1.0], forward)
    right /= np.linalg.norm(right)
    return np.array([right, np.cross(forward, right), forward])


def _accent_pixels(image):
    """Pixels shaded from ACCENT: flat shading scales a colour, so its channel ratios survive."""
    ratio = image / np.maximum(image.max(axis=2, keepdims=True), 1e-9)
    return int(np.all(np.abs(ratio - np.asarray(ACCENT) / max(ACCENT)) < 0.02, axis=2).sum())


def _scene(manifest, folder, step):
    """(meshes, colours, arrows) for one step; see the module docstring."""
    instances = {i['id']: i for i in manifest['instances']}
    explode = {r['instance']: r for r in manifest['explode']}
    joints = {j['child']: j for j in manifest['joints']}
    meshes, colors, arrows = [], [], []
    for ident in step['built']:
        meshes.append(_placed(instances[ident], folder))
        colors.append(BUILT)
    for ident in step['new']:
        mesh = _placed(instances[ident], folder)
        parent = instances[ident]['parent']
        if parent is not None:   # back out along its own joint, relative to its seated parent
            direction = np.asarray(explode[ident]['direction'], dtype=float)
            mesh.apply_translation(np.asarray(explode[ident]['offset']) - np.asarray(explode[parent]['offset']))
            joint = joints.get(ident)
            if joint is not None:
                seat = np.asarray(joint['origin'], dtype=float)
                lead = float((mesh.vertices @ direction).min())
                start = seat + direction * (lead - float(seat @ direction))
                if np.linalg.norm(start - seat) > ARROW_MIN:
                    arrows.append((start, seat))
        meshes.append(mesh)
        colors.append(ACCENT)
    return meshes, colors, arrows


def camera(manifest, folder):
    """One view for every stage of a document: the corner that shows the most of the parts being
    added onto something (steps that only place a first part do not vote unless no step adds onto
    anything). Ties keep the first corner."""
    rows = steps(manifest)
    voters = [r for r in rows if r['built']] or rows
    scenes = [_scene(manifest, folder, r)[:2] for r in voters]
    best, seen = None, 0
    for corner in CORNERS:
        basis = _basis(corner)
        count = sum(_accent_pixels(zbuffer(m, basis, size=TRIAL_PX, colors=c, background=PAPER, ambient=AMBIENT)[0])
                    for m, c in scenes)
        if best is None or count > seen * TIE:
            best, seen = basis, count
    return best


def render_stage(manifest, folder, step, path, size=IMAGE_PX, basis=None):
    """Write the stage image (PNG, transparent background) for one step of `steps(manifest)`;
    meshes are read from `folder`. `basis` defaults to `camera(manifest, folder)`."""
    meshes, colors, arrows = _scene(manifest, folder, step)
    basis = camera(manifest, folder) if basis is None else basis
    image, scale, origin = zbuffer(meshes, basis, size=size, colors=colors, background=PAPER, ambient=AMBIENT)
    alpha = (~np.all(image == np.asarray(PAPER), axis=2)).astype(float)   # nothing drawn: see-through
    fig = plt.figure(figsize=(size / 100, size / 100), dpi=100)
    fig.patch.set_alpha(0)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.imshow(np.dstack([image, alpha]), origin='lower', interpolation='nearest',
              extent=[origin[0], origin[0] + size * scale, origin[1], origin[1] + size * scale])
    for start, end in arrows:
        (x0, y0), (x1, y1) = (basis @ start)[:2], (basis @ end)[:2]
        ax.annotate('', xy=(x1, y1), xytext=(x0, y0),
                    arrowprops={'arrowstyle': '-|>', 'color': ARROW, 'lw': 2.4, 'linestyle': (0, (3, 2)),
                                'mutation_scale': 22, 'shrinkA': 0, 'shrinkB': 0})
    ax.set_axis_off()
    fig.savefig(path, dpi=100, transparent=True)
    plt.close(fig)
    return Path(path)


# --- the page ----------------------------------------------------------------------------------

def _e(text):
    return markup.escape(str(text), quote=True)


def _join(names):
    return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]


def _alt(step, names):
    new = _join([names[i] for i in step['new']])
    if not step['built']:
        return f"Step {step['number']}: the {new.lower()} on its own, highlighted."
    return (f"Step {step['number']}: {new} (highlighted) shown backed out from the "
            f"{_join([names[i] for i in step['built']]).lower()}, with arrows to where they seat.")


def _png(path):
    return 'data:image/png;base64,' + base64.b64encode(Path(path).read_bytes()).decode('ascii')


def _tools(rows):
    seen = []
    for row in rows:
        if row['tool'] and row['tool'] not in seen:
            seen.append(row['tool'])
    return seen


def _detail(row, tag='p'):
    parts = []
    if row['callout']:
        parts.append(f'<{tag} class="callout"><span class="label">Hardware</span>'
                     f'<span data-field="callout">{_e(row["callout"])}</span></{tag}>')
    if row['tool']:
        parts.append(f'<{tag} class="tool"><span class="label">Tool</span>'
                     f'<span data-field="tool">{_e(row["tool"])}</span></{tag}>')
    return ''.join(parts)


def _illustrated(rows, manifest, folder):
    names = {i['id']: i['name'] for i in manifest['instances']}
    out, basis = [], camera(manifest, folder)
    with tempfile.TemporaryDirectory() as tmp:
        for row in rows:
            image = render_stage(manifest, folder, row, Path(tmp) / f"step-{row['number']}.png", basis=basis)
            out.append(
                f'<section class="step" data-step="{row["number"]}" aria-labelledby="step-{row["number"]}">'
                f'<div class="step-words"><h3 id="step-{row["number"]}"><span class="n" aria-hidden="true">{row["number"]}</span>'
                f'<span class="visually-hidden">Step {row["number"]}: </span>'
                f'<span data-field="text">{_e(row["text"])}</span></h3>{_detail(row)}</div>'
                f'<figure><img src="{_png(image)}" width="{IMAGE_PX}" height="{IMAGE_PX}" '
                f'alt="{_e(_alt(row, names))}"></figure></section>')
    return f'<div class="steps">{"".join(out)}</div>'


def _checklist(rows):
    items = []
    for row in rows:
        n, detail = row['number'], _detail(row)
        described = f' aria-describedby="detail-{n}"' if detail else ''
        items.append(f'<li data-step="{n}"><input type="checkbox" id="check-{n}"{described}>'
                     f'<span class="n" aria-hidden="true">{n}</span><div class="what">'
                     f'<label for="check-{n}" data-field="text">{_e(row["text"])}</label>'
                     + (f'<div id="detail-{n}">{detail}</div>' if detail else '') + '</div></li>')
    return f'<ol class="checklist">{"".join(items)}</ol>'


def _parts(manifest):
    rows = ''.join(f'<tr><td class="qty">{row["quantity"]}</td><th scope="row">{_e(row["name"])}'
                   f'<small>{_e(row["specification"])}</small></th></tr>' for row in manifest['bom'])
    return (f'<div><h2 id="parts">Parts</h2><table class="parts" aria-labelledby="parts"><tbody>{rows}'
            f'</tbody></table></div>')


CSS = """
:root{--sheet:#faf9f6;--bench:#ece9e3;--ink:#1d1b18;--muted:#58544d;--line:#d2cec7;--accent:#d65b25;
--accent-ink:#983300;--warn:#a23737;--hover:#f1efea;--select:#ffd9c4;--shadow:#1d1b1814;
color-scheme:light;
font-family:Seravek,"Gill Sans Nova","Segoe UI Variable Text","Segoe UI",sans-serif;font-synthesis:none;
font-variant-numeric:tabular-nums;color:var(--ink);background:var(--bench)}
*{box-sizing:border-box}
::selection{background:var(--select);color:var(--ink)}
body{margin:0;padding:48px 16px}
main{max-width:60rem;margin:0 auto;background:var(--sheet);padding:56px 64px 48px;border:1px solid var(--line);
box-shadow:0 12px 32px var(--shadow)}
h1{font-size:2.25rem;line-height:1.1;letter-spacing:-.025em;font-weight:500;margin:0 0 12px;text-wrap:balance;
max-width:24ch}
.meta{margin:0;color:var(--muted);font-size:.9375rem;line-height:1.5}
.meta strong{color:var(--ink);font-weight:600}
.failed{margin:24px 0 0;padding:12px 16px;border:1px solid var(--warn);color:var(--warn);font-weight:600}
.prep{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:40px;margin:40px 0 0;padding:24px 0;
border-top:2px solid var(--ink);border-bottom:1px solid var(--line)}
.prep h2{font-size:.8125rem;font-weight:600;text-align:left;margin:0 0 12px;padding:0}
table{border-collapse:collapse;width:100%}
td,th{padding:8px 0;border-top:1px solid var(--line);vertical-align:baseline;text-align:left;font-size:.9375rem}
th{font-weight:500}
th small{display:block;overflow-wrap:anywhere;font-weight:400;color:var(--muted);font-size:.8125rem;line-height:1.4;margin-top:2px}
.qty{width:3.5rem;font-size:1.25rem;font-weight:600;padding-right:12px}
.qty::after{content:" ×" / "";font-weight:400;color:var(--muted);font-size:1rem}
.prep ul{list-style:none;margin:0;padding:0}
.prep li{padding:8px 0;border-top:1px solid var(--line);font-size:.9375rem}
.prep p{margin:0;color:var(--muted);font-size:.9375rem;padding:8px 0;border-top:1px solid var(--line)}
.steps{margin-top:8px}
.step{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:40px;align-items:center;
padding:32px 0;border-bottom:1px solid var(--line);break-inside:avoid}
h3{margin:0 0 20px;font-size:1.25rem;line-height:1.35;font-weight:500;text-wrap:pretty}
h3 .n,.checklist .n{display:block;font-size:3.5rem;line-height:1;font-weight:300;letter-spacing:-.04em;
margin-bottom:12px}
.callout,.tool{display:flex;gap:12px;align-items:baseline;margin:0;padding:8px 0;border-top:1px solid var(--line);
font-size:1rem}
.callout [data-field]{font-weight:600;color:var(--accent-ink);text-wrap:balance}
.label{flex:0 0 4.5rem;font-size:.8125rem;color:var(--muted)}
figure{margin:0}
img{display:block;width:100%;height:auto}
.checklist{list-style:none;margin:8px 0 0;padding:0}
.checklist li{display:grid;grid-template-columns:28px 3rem minmax(0,1fr);gap:16px;align-items:start;
padding:20px 8px;margin:0 -8px;border-bottom:1px solid var(--line);break-inside:avoid;font-size:1.0625rem;
line-height:1.45}
.checklist li:hover{background:var(--hover)}
.checklist label{cursor:pointer}
.checklist .n{font-size:1.75rem;margin:0;line-height:1}
.checklist .callout,.checklist .tool{font-size:.9375rem;padding:4px 0;border:0}
.checklist .callout{margin-top:8px}
.checklist .callout,.checklist .tool{display:flex}
.checklist .label{flex-basis:4.5rem}
input[type=checkbox]{appearance:none;width:24px;height:24px;margin:2px 0 0;border:1.5px solid var(--ink);
border-radius:3px;background:var(--sheet);display:grid;place-content:center;cursor:pointer}
input[type=checkbox]::before{content:"";width:12px;height:7px;border-left:2.5px solid var(--sheet);
border-bottom:2.5px solid var(--sheet);transform:translateY(-2px) rotate(-45deg)}
input[type=checkbox]:checked{background:var(--accent);border-color:var(--accent)}
input[type=checkbox]:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
li:has(input:checked) .what{color:var(--muted)}
.done{margin:24px 0 0;font-size:1.0625rem;font-weight:500}
footer{margin-top:40px;color:var(--muted);font-size:.8125rem;line-height:1.55;max-width:70ch}
footer p{margin:0 0 8px}
code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.8125rem}
.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
@media (max-width:720px){body{padding:0}main{padding:32px 16px;border:0;box-shadow:none}h1{font-size:1.75rem}
.prep,.step{grid-template-columns:minmax(0,1fr);gap:24px}h3 .n{font-size:2.75rem}}
@page{margin:14mm 16mm}
@media print{:root{background:none}body{padding:0}main{max-width:none;padding:0;border:0;box-shadow:none;
background:none}
.prep{break-inside:avoid}.step{grid-template-columns:minmax(0,1fr) 64mm;padding:16px 0;gap:28px}
img{max-height:64mm;width:auto;max-width:100%;margin:0 auto}h3 .n,.checklist .n{font-weight:400}
.checklist li{margin:0;padding:16px 0}}
"""


def html(manifest, folder, style=STYLES[0]):
    """The standalone instructions page (images inline) for one style; meshes are read from `folder`."""
    if style not in STYLES:
        raise ValueError(f'unknown instructions style {style!r}; choose one of {", ".join(STYLES)}')
    rows = steps(manifest)
    tools = _tools(rows)
    body = _illustrated(rows, manifest, folder) if style == 'illustrated' else _checklist(rows)
    count = len(rows)
    failed = '' if manifest['pass'] else (
        '<p class="failed" role="note">The assembly gate failed. These steps describe an assembly that '
        'did not pass its checks; fix the assembly before building it.</p>')
    tool_items = ''.join(f'<li>{_e(t)}</li>' for t in tools) if tools else ''
    tool_block = f'<ul>{tool_items}</ul>' if tools else '<p>No tools needed.</p>'
    sources = manifest['provenance']['sources']
    source = manifest['provenance']['assembly_file']
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(manifest['name'])}: assembly</title>
<style>{CSS}</style>
</head>
<body>
<main>
<header>
<h1>{_e(manifest['name'])}</h1>
<p class="meta"><strong>{count} step{'s' if count != 1 else ''}</strong> · {style}</p>
{failed}
</header>
<section class="prep" aria-label="Before you start">
{_parts(manifest)}
<div><h2>Tools</h2>{tool_block}</div>
</section>
<h2 class="visually-hidden">Steps</h2>
{body}
<p class="done">That's every step. The assembly is complete.</p>
<footer>
<p>{_e(manifest['disclaimer'])}</p>
<p>Generated from <code>{_e(source)}</code> (sha256 <code>{_e(sources.get(source, '')[:12])}</code>) by the
assembly gate (result: {_e(manifest['gate'])}). Edit the assembly, not this page.</p>
</footer>
</main>
</body>
</html>
"""


# --- export ------------------------------------------------------------------------------------

def browser():
    """A Chrome/Chromium executable for PDF printing: $MAGIC_CHROME, an installed app, or Playwright's."""
    candidates = [os.environ.get('MAGIC_CHROME', '')] + list(BROWSERS)
    for name in candidates:
        found = name and (name if os.path.isfile(name) and os.access(name, os.X_OK) else shutil.which(name))
        if found:
            return found
    shells = sorted(glob.glob(os.path.expanduser('~/Library/Caches/ms-playwright/chromium_headless_shell-*/*/'
                                                 'chrome-headless-shell')) +
                    glob.glob(os.path.expanduser('~/.cache/ms-playwright/chromium_headless_shell-*/*/'
                                                 'chrome-headless-shell')))
    return shells[-1] if shells else None


def to_pdf(page, pdf):
    """Print an HTML file to PDF with a headless browser in a throwaway profile.

    Success is the PDF on disk, not the exit code: Chrome on macOS can write the file and then
    crash in its teardown watchdog."""
    executable = browser()
    if not executable:
        raise RuntimeError('PDF export needs Chrome or Chromium; install one or set MAGIC_CHROME to its path')
    given, pdf = Path(pdf), Path(pdf).resolve()
    pdf.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as profile:
        done = subprocess.run([executable, '--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
                               f'--user-data-dir={profile}', '--no-pdf-header-footer',
                               f'--print-to-pdf={pdf}', Path(page).resolve().as_uri()],
                              capture_output=True, text=True, timeout=PDF_TIMEOUT)
    if not pdf.is_file() or not pdf.read_bytes()[:5] == b'%PDF-':
        raise RuntimeError(f'PDF export failed (exit {done.returncode}): {done.stderr.strip()[-400:]}')
    return given


def export(folder, out, style=STYLES[0], pdf=True):
    """Write <id>-instructions-<style>.html (and .pdf) into `out` from the manifest in `folder`."""
    manifest = json.loads((Path(folder) / MANIFEST).read_text())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{manifest['id']}-instructions-{style}"
    files = {'html': out / f'{stem}.html'}
    files['html'].write_text(html(manifest, folder, style))
    if pdf:
        files['pdf'] = to_pdf(files['html'], out / f'{stem}.pdf')
    return files
