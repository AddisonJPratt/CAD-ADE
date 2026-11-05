#!/usr/bin/env python3
"""Local first-proof app. Start with .venv/bin/python proof/server.py."""
import ast
import html
import json
import math
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('MAGIC_PROOF_DATA', ROOT / 'proof')).resolve()
BRIEFS = Path(os.environ.get('MAGIC_PROOF_BRIEFS', ROOT / 'briefs' / 'generated')).resolve()
PRINT_LOG = Path(os.environ.get('MAGIC_PROOF_PRINT_LOG', ROOT / 'prints' / 'PRINT_LOG.md')).resolve()
LOCK = threading.RLock()
BUILD_LOCK = threading.Lock()
TEMPLATES = {'round': 'holder_clip', 'rectangular': 'holder_cradle'}
GATES = ['1 Execute', '2 Geometry', '3 Printability', '4 Renders', 'Sweep', '5 Exports']
RESULTS = {'perfect': 'Perfect', 'too_tight': 'Too tight', 'too_loose': 'Too loose', 'broke': 'It broke'}
STYLE = '''
:root{color-scheme:light;--ink:#1d1b18;--muted:#58544d;--line:#ccc7bd;--paper:#ece9e3;--accent:#f25c05; font-family:Seravek,"Segoe UI",sans-serif;color:var(--ink);background:var(--paper)}
*{box-sizing:border-box}body{margin:0}header{display:flex;align-items:center;justify-content:space-between;padding:1.3rem clamp(1rem,5vw,4rem);border-bottom:1px solid var(--line)}a{color:inherit;text-underline-offset:.2em}header a{text-decoration:none}nav{display:flex;gap:1.5rem}main{max-width:1100px;margin:auto;padding:clamp(2rem,5vw,4rem) clamp(1rem,5vw,3rem)}h1{font-size:clamp(2rem,4vw,3rem);font-weight:500;letter-spacing:-.025em;margin:0 0 .7rem}h2{font-weight:500}p{line-height:1.55;max-width:65ch}.muted,small{color:var(--muted)}.layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:clamp(2rem,6vw,5rem)}label{display:block;margin:1.1rem 0 .4rem;font-weight:600}input,select{font:inherit;width:100%;border:1px solid #a7a097;background:#faf9f6;color:var(--ink);padding:.75rem;border-radius:5px;min-height:44px}button,.button{font:inherit;font-weight:600;background:var(--accent);color:#190d05;border:0;border-radius:6px;padding:.85rem 1.2rem;min-height:48px;cursor:pointer;display:inline-block;text-decoration:none}button:hover,.button:hover{background:#d95000}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #1d1b18;outline-offset:3px}.choices{display:flex;gap:.6rem;flex-wrap:wrap}.choices button{background:transparent;border:1px solid #9c958a;color:var(--ink)}.choices button:hover{background:#ded9d0}.image{width:100%;background:white;display:block}.line{border-top:1px solid var(--line);margin:1.6rem 0}.error{color:#852b00;font-weight:600}ul{padding-left:1.2rem}li{margin:.4rem 0}.row{display:flex;gap:1rem}.row>*{flex:1}footer{margin-top:3rem;color:var(--muted);font-size:.85rem}@media(max-width:720px){.layout{grid-template-columns:1fr;gap:2rem}header{padding:1rem}main{padding:2rem 1rem}.row{display:block}}
'''


def esc(value):
    return html.escape(str(value), quote=True)


def page(title, body):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(title) + ' · Magic CAD</title><style>' + STYLE + '</style></head><body><header><a href="/"><strong>magic cad</strong></a><nav><a href="/">Make</a><a href="/shelf">Shelf</a></nav></header><main>' + body + '</main></body></html>').encode()


def template(shape):
    name = TEMPLATES[shape]
    source = (ROOT / 'designs' / (name + '.py')).read_text()
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PARAMS' for t in n.targets))
    return name, tree, node, ast.literal_eval(node.value)


def num(form, name, low, high):
    try:
        x = float(form[name])
    except (KeyError, ValueError, TypeError):
        raise ValueError(f'Enter a valid {name.replace("_", " ")} in millimetres.')
    if not math.isfinite(x) or not low <= x <= high:
        raise ValueError(f'{name.replace("_", " ").capitalize()} must be between {low:g} and {high:g} mm.')
    return x


def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temp, path)


def prepare(form):
    shape = form.get('shape', '')
    if shape not in TEMPLATES:
        raise ValueError('Choose a round or rectangular object.')
    obj = form.get('object', '').strip()
    if not obj or len(obj) > 100 or any(ord(c) < 32 for c in obj):
        raise ValueError('Enter an object name, up to 100 characters.')
    material = form.get('material', 'PETG')
    if material not in ('PETG', 'PLA', 'ABS') or form.get('mount') != 'screws':
        raise ValueError('Choose a supported material and screw mounting.')
    name, tree, node, declared = template(shape)
    with LOCK:
        reconcile_events()
        adjustments = read_json(DATA / 'profile.json', {}).get('adjustments_mm', {})
        clearance = round(declared['clearance'][0] + float(adjustments.get(name, 0)), 5)
    overrides = {'clearance': clearance}
    if shape == 'round':
        overrides['barrel_dia'] = num(form, 'diameter', *declared['barrel_dia'][1:])
        readings = {'diameter': overrides['barrel_dia'], 'length': num(form, 'length', 1, 2000)}
    else:
        readings = {}
        for field, param in [('width', 'obj_w'), ('depth', 'obj_d'), ('height', 'obj_h')]:
            readings[field] = num(form, field, *declared[param][1:])
            overrides[param] = readings[field]
    for key, value in overrides.items():
        if not math.isfinite(value) or not declared[key][1] <= value <= declared[key][2]:
            raise ValueError('The saved fit adjustment is outside the tested range. Reset the profile before making another holder.')
    updated = {k: (overrides.get(k, v[0]), v[1], v[2]) for k, v in declared.items()}
    node.value = ast.parse(repr(updated), mode='eval').body
    ast.fix_missing_locations(tree)
    ident = uuid.uuid4().hex
    dest = DATA / 'makes' / ident
    dest.mkdir(parents=True)
    design = dest / (name + '.py')
    design.write_text(ast.unparse(tree) + '\n')
    hard = {'mount_holes': 2}
    measures = {'mount_holes': {'probe': 'hole_count', 'axis': 'X' if shape == 'round' else 'Z', 'dia': 3.4}}
    if shape == 'round':
        hard['clip_height'] = updated['clip_height'][0]
        measures['clip_height'] = {'probe': 'bbox_z'}
    brief = {'name': name, 'function': f'Wall holder for {obj}', 'hard_dimensions': hard,
             'measures': measures, 'interfaces': ['Round object' if shape == 'round' else 'Rectangular object', 'Two M3 screws'],
             'soft_preferences': ['No supports'], 'assumptions': ['Fit, retention and load are not validated by the harness.', 'Clearance and printer profile are not physically calibrated.'],
             'params': {k: {'value': v[0], 'min': v[1], 'max': v[2], 'unit': 'mm', 'intent': k.replace('_', ' ')} for k, v in updated.items()}}
    BRIEFS.mkdir(parents=True, exist_ok=True)
    brief_path = BRIEFS / (ident + '.yaml')
    write_json(brief_path, brief)  # JSON is a YAML subset.
    meta = {'id': ident, 'object': obj, 'shape': shape, 'template': name, 'joint_type': name,
            'material': material, 'mount': 'screws', 'readings': readings, 'clearance_used_mm': clearance,
            'created_at': datetime.now(timezone.utc).isoformat(), 'brief': str(brief_path), 'status': 'building'}
    write_json(dest / 'make.json', meta)
    return meta, dest, design, brief_path


def run_make(meta, dest, design, brief):
    out = dest / 'run'
    try:
        proc = subprocess.run([sys.executable, str(ROOT / 'magic.py'), 'run', str(design), '--brief', str(brief), '--out', str(out)], cwd=ROOT, capture_output=True, text=True, timeout=1800)
        report = read_json(out / 'report.json', {})
        gate_map = {g.get('name'): g.get('status') for g in report.get('gates', [])}
        stls = [out / x for x in report.get('exports', []) if isinstance(x, str) and Path(x).name == x and x.endswith('.stl')]
        passed = proc.returncode == 0 and report.get('pass') is True and all(gate_map.get(g) == 'PASS' for g in GATES) and len(stls) == 1 and stls[0].is_file() and stls[0].stat().st_size > 0
        meta['status'] = 'passed' if passed else 'failed'
        meta['stl'] = stls[0].name if passed else None
        meta['gates'] = report.get('gates', [])
        meta['failure'] = next((g.get('detail') for g in meta['gates'] if g.get('status') == 'FAIL'), 'The verification run did not complete successfully.') if not passed else None
    except (OSError, subprocess.TimeoutExpired):
        meta.update(status='failed', failure='The design check could not finish. Please try again.', gates=[])
    write_json(dest / 'make.json', meta)


def reconcile_events():
    """Rebuild derived files from durable, immutable per-make outcomes under LOCK."""
    events = []
    for path in (DATA / 'events').glob('*.json'):
        if re.fullmatch(r'[0-9a-f]{32}\.json', path.name):
            events.append(read_json(path, {}))
    events.sort(key=lambda e: (e['ts'], e['make_id']))
    profile = {'adjustments_mm': {}}
    for event in events:
        joint = event['joint_type']
        profile['adjustments_mm'][joint] = round(profile['adjustments_mm'].get(joint, 0) + event['adjustment_mm'], 5)
    write_json(DATA / 'profile.json', profile)
    target = DATA / 'outcomes.jsonl'
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(''.join(json.dumps(e, ensure_ascii=True) + '\n' for e in events))
    os.replace(tmp, target)
    PRINT_LOG.parent.mkdir(parents=True, exist_ok=True)
    existing = PRINT_LOG.read_text() if PRINT_LOG.exists() else ''
    for e in events:
        marker = '<!-- magic-proof:' + e['make_id'] + ' -->'
        if marker not in existing:
            entry = (f"\n{marker}\n## {e['ts'][:10]} — {e['template']} — default printer, {e['material']}, nozzle unknown\n"
                     f"- Modelled vs measured: not recorded\n- Fit results: {e['joint_type']}: {RESULTS[e['result']]}, per-side clearance {e['clearance_used_mm']} mm\n"
                     f"- Failures: {'reported broken; review needed' if e['result'] == 'broke' else 'not recorded'}\n"
                     f"- Verdict: {'adjust clearance by ' + str(e['adjustment_mm']) + ' mm' if e['adjustment_mm'] else 'recorded; no clearance adjustment'}\n")
            with PRINT_LOG.open('a') as f:
                f.write(entry)
            existing += entry
        meta_path = make_path(e['make_id']) / 'make.json'
        meta = read_json(meta_path, None)
        if meta and not meta.get('outcome'):
            meta['outcome'] = e
            write_json(meta_path, meta)


def feedback(ident, result):
    if result not in RESULTS:
        raise ValueError('Choose a fit result.')
    dest = make_path(ident)
    with LOCK:
        reconcile_events()
        meta = read_json(dest / 'make.json', None)
        if not meta or meta.get('status') != 'passed':
            raise ValueError('A completed, checked design is needed before recording a print.')
        event_path = DATA / 'events' / (ident + '.json')
        if event_path.exists():
            raise ValueError('A fit result has already been recorded for this print.')
        requested = {'too_tight': 0.2, 'too_loose': -0.2}.get(result, 0)
        profile = read_json(DATA / 'profile.json', {'adjustments_mm': {}})
        current = float(profile.get('adjustments_mm', {}).get(meta['joint_type'], 0))
        _, _, _, declared = template(meta['shape'])
        next_clearance = round(declared['clearance'][0] + current + requested, 5)
        in_range = declared['clearance'][1] <= next_clearance <= declared['clearance'][2]
        fresh = abs((declared['clearance'][0] + current) - meta['clearance_used_mm']) < 1e-6
        allowed = in_range and (fresh or not requested)
        reason = None if allowed else ('The saved profile has changed since this print; review this result before adjusting it.' if not fresh else 'Requested adjustment exceeds the tested clearance range.')
        outcome = {'ts': datetime.now(timezone.utc).isoformat(), 'make_id': ident, 'object': meta['object'],
                   'template': meta['template'], 'joint_type': meta['joint_type'], 'material': meta['material'],
                   'printer': 'default', 'clearance_used_mm': meta['clearance_used_mm'], 'result': result,
                   'adjustment_mm': requested if allowed else 0,
                   'review_needed': result == 'broke' or not allowed,
                   'adjustment_reason': reason}
        # A single atomic event is authoritative. Derivative files can be rebuilt after a crash.
        write_json(event_path, outcome)
        reconcile_events()
    return read_json(dest / 'make.json', meta)


def make_path(ident):
    if not re.fullmatch(r'[0-9a-f]{32}', ident):
        raise ValueError('Invalid design ID.')
    return DATA / 'makes' / ident


def form_html(values=None, message=''):
    v = values or {}
    val = lambda k, default='': esc(v.get(k, default))
    shape = v.get('shape', 'round')
    return f'''<div class="layout"><div><h1>What are we holding?</h1><p>Tell us a little about your object. We’ll make a wall holder and check the design.</p><p class="muted">Measure the object with calipers. The first version uses screws and supports a limited range of sizes.</p></div><form action="/make" method="post" onsubmit="this.querySelector('button').disabled=true;document.getElementById('progress').hidden=false"><p class="error" role="alert">{esc(message)}</p><label for="object">Object name</label><input id="object" name="object" value="{val('object')}" maxlength="100" required placeholder="Bike pump"><label for="shape">Object shape</label><select id="shape" name="shape" onchange="document.getElementById('round').hidden=this.value!=='round';document.getElementById('rectangle').hidden=this.value!=='rectangular';document.querySelectorAll('[data-shape]').forEach(x=>x.disabled=x.dataset.shape!==this.value)"><option value="round" {'selected' if shape == 'round' else ''}>Round</option><option value="rectangular" {'selected' if shape == 'rectangular' else ''}>Rectangular</option></select><div id="round" {'hidden' if shape != 'round' else ''}><label for="diameter">Diameter (30–50 mm)</label><input id="diameter" name="diameter" data-shape="round" type="number" min="30" max="50" step="any" value="{val('diameter','38')}" {'disabled' if shape != 'round' else ''} required><label for="length">Object length (mm)</label><input id="length" name="length" data-shape="round" type="number" min="1" max="2000" step="any" value="{val('length','250')}" {'disabled' if shape != 'round' else ''} required><small>Length is saved for reference; it doesn’t change this clip yet.</small></div><div id="rectangle" {'hidden' if shape != 'rectangular' else ''}><label for="width">Width (60–120 mm)</label><input id="width" name="width" data-shape="rectangular" type="number" min="60" max="120" step="any" value="{val('width','90')}" {'disabled' if shape != 'rectangular' else ''} required><label for="depth">Depth (20–50 mm)</label><input id="depth" name="depth" data-shape="rectangular" type="number" min="20" max="50" step="any" value="{val('depth','35')}" {'disabled' if shape != 'rectangular' else ''} required><label for="height">Height (80–150 mm)</label><input id="height" name="height" data-shape="rectangular" type="number" min="80" max="150" step="any" value="{val('height','120')}" {'disabled' if shape != 'rectangular' else ''} required></div><label for="mount">Mount</label><select id="mount" name="mount"><option value="screws">Screws</option><option disabled>Adhesive — coming later</option></select><label for="material">Material</label><select id="material" name="material"><option>PETG</option><option {'selected' if v.get('material') == 'PLA' else ''}>PLA</option><option {'selected' if v.get('material') == 'ABS' else ''}>ABS</option></select><p><button type="submit">Make my holder</button></p><p id="progress" hidden role="status">Making and checking your design. This can take several minutes; keep this page open.</p></form></div>'''


def result_html(meta):
    ident = meta['id']
    if meta['status'] != 'passed':
        return '<h1>We couldn’t verify this holder</h1><p>' + esc(meta.get('failure', 'The check is still running.')) + '</p><p><a href="/make/' + ident + '/report">See check details</a> · <a href="/">Try another design</a></p>'
    display = f"Sized for a {meta['readings']['diameter']:g} mm barrel" if meta['shape'] == 'round' else f"Sized for {meta['readings']['width']:g} × {meta['readings']['depth']:g} × {meta['readings']['height']:g} mm"
    image = f'/make/{ident}/render'
    if meta.get('outcome'):
        info = '<p>Recorded: ' + esc(RESULTS[meta['outcome']['result']]) + '.</p>'
        if meta['outcome'].get('adjustment_reason'):
            info += '<p>' + esc(meta['outcome']['adjustment_reason']) + ' Your result is saved for review.</p>'
        elif meta['outcome']['result'] in ('too_tight','too_loose'):
            info += '<p>Fit adjustment saved. <a href="/remake/' + ident + '">Make an adjusted version</a>.</p>'
    else:
        info = '<form action="/feedback/' + ident + '" method="post"><p>Printed it? How did it fit?</p><div class="choices">' + ''.join('<button name="result" value="' + k + '">' + esc(v) + '</button>' for k,v in RESULTS.items()) + '</div></form>'
    return f'''<div class="layout"><div><img class="image" src="{image}" alt="Quality assurance render of the holder"><p class="muted">The render shows the checked design in its print orientation.</p></div><div><h1>{esc(meta['object'])} holder</h1><p>{esc(display)} · Screws to the wall</p><div class="line"></div><p><strong>Geometry and printability checks passed.</strong><br>Fit and strength have not been physically tested.</p><p><a class="button" href="/make/{ident}/download">Download the print file</a></p><p class="muted">STL · Printability is based on geometry checks, not a slicer or print.</p><div class="line"></div>{info}<footer>Material: {esc(meta['material'])}. Printer and clearance settings are starting values.</footer></div></div>'''


class Handler(BaseHTTPRequestHandler):
    def send_page(self, status, title, body):
        data = page(title, body)
        self.send_response(status); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.send_header('Content-Length', str(len(data))); self.send_header('X-Content-Type-Options', 'nosniff'); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(data)

    def host_ok(self):
        return self.headers.get('Host', '') in ('localhost:8766', '127.0.0.1:8766')

    def do_GET(self):
        if not self.host_ok():
            self.send_error(HTTPStatus.FORBIDDEN); return
        path = urlparse(self.path).path
        # A desktop shell can verify it connected to the child it just started.
        # Standalone browser mode does not expose this endpoint.
        if path == '/__desktop_ready':
            token = os.environ.get('MAGIC_PROOF_DESKTOP_TOKEN')
            if not token:
                self.send_error(404); return
            data = token.encode('ascii')
            self.send_response(200); self.send_header('Content-Type', 'text/plain; charset=us-ascii')
            self.send_header('Content-Length', str(len(data))); self.send_header('Cache-Control', 'no-store')
            self.end_headers(); self.wfile.write(data); return
        try:
            if path == '/':
                return self.send_page(200, 'Make a holder', form_html())
            if path == '/shelf':
                items = []
                for f in (DATA / 'makes').glob('*/make.json'):
                    m = read_json(f, {})
                    if re.fullmatch(r'[0-9a-f]{32}', str(m.get('id',''))):
                        items.append(m)
                items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                listing = ''.join('<li><a href="/make/' + x['id'] + '">' + esc(x.get('object','Holder')) + '</a> · ' + esc(x.get('created_at','')[:10]) + ' · ' + esc(RESULTS.get((x.get('outcome') or {}).get('result'), x.get('status','unknown'))) + '</li>' for x in items)
                return self.send_page(200, 'Shelf', '<h1>Your shelf</h1><p>Past designs and print results live here.</p>' + ('<ul>' + listing + '</ul>' if listing else '<p>No designs yet. <a href="/">Make your first holder</a>.</p>'))
            match = re.fullmatch(r'/make/([0-9a-f]{32})(?:/(download|render|report))?', path)
            if match:
                ident, action = match.groups(); dest = make_path(ident); meta = read_json(dest / 'make.json', {})
                if not meta: raise ValueError('Design not found.')
                if action is None: return self.send_page(200, 'Holder', result_html(meta))
                if action == 'report':
                    report = dest / 'run' / 'report.md'
                    if not report.is_file() or report.stat().st_size > 1000000: raise ValueError('Report unavailable.')
                    return self.send_page(200, 'Check details', '<h1>Check details</h1><pre style="white-space:pre-wrap;overflow-wrap:anywhere">' + esc(report.read_text()) + '</pre>')
                if meta.get('status') != 'passed': raise ValueError('Design is not available.')
                filename = meta.get('stl') if action == 'download' else 'iso.png'
                if action == 'download' and (not isinstance(filename,str) or Path(filename).name != filename or not filename.endswith('.stl')): raise ValueError('File unavailable.')
                file = dest / 'run' / (filename if action == 'download' else 'renders/iso.png')
                if not file.is_file() or not file.stat().st_size: raise ValueError('File unavailable.')
                data = file.read_bytes(); self.send_response(200); self.send_header('Content-Type', 'model/stl' if action == 'download' else 'image/png'); self.send_header('Content-Length', str(len(data))); self.send_header('X-Content-Type-Options', 'nosniff')
                if action == 'download': self.send_header('Content-Disposition', 'attachment; filename="holder.stl"')
                self.end_headers(); self.wfile.write(data); return
            match = re.fullmatch(r'/remake/([0-9a-f]{32})', path)
            if match:
                m = read_json(make_path(match.group(1)) / 'make.json', {})
                if not m: raise ValueError('Design not found.')
                v = {'object':m['object'], 'shape':m['shape'], 'material':m['material'], **m['readings']}
                return self.send_page(200, 'Adjust holder', form_html(v, 'Your fit adjustment will be used for the next design.'))
            self.send_error(404)
        except (ValueError, OSError):
            self.send_error(404)

    def do_POST(self):
        if not self.host_ok() or self.headers.get('Origin', '') not in ('http://localhost:8766', 'http://127.0.0.1:8766'):
            self.send_error(HTTPStatus.FORBIDDEN); return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192 or self.headers.get_content_type() != 'application/x-www-form-urlencoded': raise ValueError('Invalid request.')
            raw = parse_qs(self.rfile.read(length).decode('utf-8'), keep_blank_values=True, max_num_fields=20)
            if any(len(v) != 1 for v in raw.values()): raise ValueError('Invalid request.')
            form = {k:v[0] for k,v in raw.items()}
            if self.path == '/make':
                meta, dest, design, brief = prepare(form)
                with BUILD_LOCK:
                    run_make(meta, dest, design, brief)
                self.send_response(303); self.send_header('Location', '/make/' + meta['id']); self.end_headers(); return
            match = re.fullmatch(r'/feedback/([0-9a-f]{32})', self.path)
            if match:
                feedback(match.group(1), form.get('result', ''))
                self.send_response(303); self.send_header('Location', '/make/' + match.group(1)); self.end_headers(); return
            self.send_error(404)
        except (ValueError, UnicodeError) as e:
            self.send_page(400, 'Please check your details', form_html(form if 'form' in locals() else {}, str(e)))
        except OSError:
            self.send_page(500, 'Could not save', '<h1>Couldn’t save your result</h1><p>Please check disk access and try again.</p>')


def recover_interrupted_makes():
    """A stopped server cannot continue its builds; preserve their history honestly."""
    for path in (DATA / 'makes').glob('*/make.json'):
        if not re.fullmatch(r'[0-9a-f]{32}', path.parent.name):
            continue
        try:
            meta = read_json(path, {})
            if meta.get('status') == 'building':
                meta.update(status='failed', failure='The app closed before this check finished. Please make the holder again.', gates=[])
                write_json(path, meta)
        except (OSError, ValueError, TypeError):
            # A damaged record should not prevent startup or change unrelated files.
            continue


def main():
    # Bind before recovery: never mark another running instance's builds as failed.
    server = ThreadingHTTPServer(('127.0.0.1', 8766), Handler)
    recover_interrupted_makes()
    print('Magic CAD First Proof: http://127.0.0.1:8766', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
