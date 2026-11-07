"""The assembly gate: collisions, fastener fit, and derived entries that map to exactly one instance.

    python -m assembly.gate <assembly.py> <project folder> <report.json> [overrides_json]

Always run through `run_gate`, which evaluates the assembly file in a subprocess (it executes
design code) and writes <out>/report.json. `evaluate` is the in-process core, used by that
subprocess and by the tests.

Fastener rules (starting values, not calibrated on a real print):
- clearance hole: from the screw's ISO 273 medium clearance in standard_parts.json up to that
  plus 2 x the fits table's sliding clearance; smaller binds the shank, larger lets it wander.
- into an insert: the screw engages at least 1.5 x its nominal diameter of thread, and its tip stays
  inside the insert hole: no deeper than insert length + the hole's extra depth, and short of
  the hole floor measured on the part.
- into the substrate (a wall, not modelled): the screw reaches past the clamped part, and no
  further than max_depth when the assembly states one.
"""
import importlib.util
import json
import math
import subprocess
import sys
import traceback
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAP_LIMIT = 0.1   # mm^3: parts touching at a face measure ~0; same limit as gate 2
ENGAGEMENT = 1.5      # minimum thread engagement in an insert, in nominal diameters (brass rule of thumb)
EPS = 1e-3            # mm
CHECKS = ('Assembly file', 'Collisions', 'Fasteners', 'Derived entries')
GATE = '6 Assembly'


def validate_entries(ids, bom, steps):
    """Every parts-list row and every step refers to real instances, each exactly once."""
    ids = list(ids)
    known = set(ids)
    listed = []
    for row in bom:
        related = row.get('part_ids') or []
        if not set(related) <= known:
            raise ValueError(f'parts list row {row.get("name")!r} names unknown instances {sorted(set(related) - known)}')
        if row.get('quantity') != len(related):
            raise ValueError(f'parts list row {row.get("name")!r}: quantity {row.get("quantity")} for {len(related)} instances')
        listed += related
    duplicated = sorted({i for i in listed if listed.count(i) > 1})
    if duplicated or set(listed) != known:
        raise ValueError(f'parts list must name each instance once; duplicated {duplicated}, '
                         f'missing {sorted(known - set(listed))}')
    visited = []
    for number, step in enumerate(steps, 1):
        if step.get('number') != number or not step.get('text') or not step.get('part_ids'):
            raise ValueError(f'step {number} is malformed')
        unknown = set(step['part_ids']) - known
        if unknown:
            raise ValueError(f'step {number} names unknown instances {sorted(unknown)}')
        visited += step['part_ids']
    duplicated = sorted({i for i in visited if visited.count(i) > 1})
    if duplicated or set(visited) != known:
        raise ValueError(f'steps must use each instance once; in more than one step {duplicated}, '
                         f'in no step {sorted(known - set(visited))}')
    return True


def lower(name):
    """'Wall clip' -> 'wall clip' for running text; leaves 'M3 screw' and 'ESP32 board' alone."""
    return name[0].lower() + name[1:] if name[:2].istitle() else name


def derive(asm):
    """Parts list and assembly order, derived from the assembly; never written by hand."""
    groups = OrderedDict()
    for inst in asm.instances.values():
        spec = inst.spec
        if inst.kind == 'printed':
            key = ('printed', spec['design'], spec['part'], json.dumps(spec['params'], sort_keys=True))
            row = {'name': inst.name, 'category': 'Printed part', 'source': spec['design']}
        elif inst.kind == 'component':
            key = ('component', spec['catalogue_id'])
            row = {'name': inst.name, 'category': 'Purchased component', 'source': spec['catalogue_id']}
        elif spec['type'] == 'screw':
            key = ('screw', spec['size'], spec['length'])
            row = {'name': f"{spec['size']} socket-head screw, {spec['length']:g} mm", 'category': 'Hardware',
                   'source': 'library/standard_parts.json'}
        else:
            key = ('insert', spec['size'])
            row = {'name': f"{spec['size']} heat-set insert", 'category': 'Hardware',
                   'source': 'library/standard_parts.json'}
        groups.setdefault(key, {**row, 'part_ids': []})['part_ids'].append(inst.id)
    bom = [{**row, 'quantity': len(row['part_ids'])} for row in groups.values()]

    steps = []
    def step(text, ids):
        steps.append({'number': len(steps) + 1, 'text': text, 'part_ids': ids})
    for inst in asm.instances.values():
        if inst.kind != 'hardware':
            step(f'Place the {lower(inst.name)}.', [inst.id])
    def grouped(kind, key):
        out = OrderedDict()
        for c in asm.connections:
            if c['kind'] == kind:
                out.setdefault(key(c), []).append(c)
        return out
    for host, rows in grouped('press', lambda c: c['host']).items():
        ids = [c['part'] for c in rows]
        size = asm.instances[ids[0]].spec['size']
        step(f'Press {len(ids)} {size} heat-set insert{"s" if len(ids) > 1 else ""} into the '
             f'{lower(asm.instances[host].name)} with a soldering iron.', ids)
    for (host, size, length, into), rows in grouped(
            'fastener', lambda c: (c['host'], *(asm.instances[c['screw']].spec[k] for k in ('size', 'length')),
                                   c['into'])).items():
        ids = [c['screw'] for c in rows]
        where = 'into the inserts' if into == 'insert' else 'into the mounting surface'
        step(f'Fasten the {lower(asm.instances[host].name)} with {len(ids)} {size} x {length:g} mm '
             f'screw{"s" if len(ids) > 1 else ""} {where}.', ids)
    return bom, steps


def collisions(asm):
    """Interference volume for every instance pair, except intended contact (press fit, threads)."""
    exempt = {frozenset((c['part'], c['host'])) for c in asm.connections if c['kind'] == 'press'}
    exempt |= {frozenset((c['screw'], c['insert'])) for c in asm.connections if c.get('insert')}
    items = list(asm.instances.values())
    rows = []
    for i, a in enumerate(items):
        box_a = a.shape.bounding_box()
        for b in items[i + 1:]:
            if frozenset((a.id, b.id)) in exempt or not box_a.overlaps(b.shape.bounding_box()):
                continue
            common = a.shape.intersect(b.shape)
            volume = sum(s.volume for s in common.solids()) if common is not None else 0.0
            rows.append({'a': a.id, 'b': b.id, 'volume': round(volume, 4), 'pass': volume <= OVERLAP_LIMIT})
    return rows


def fastener(asm, connection):
    from .model import along, axis_of, first_hit, lookup, nominal
    from library import standard_parts
    screw = asm.instances[connection['screw']]
    size, length = screw.spec['size'], screw.spec['length']
    spec = lookup('screws', size)
    sliding = standard_parts()['fits']['sliding']
    low, high = spec['clearance'], spec['clearance'] + 2 * sliding
    origin, direction = axis_of(screw)
    insert = asm.instances.get(connection.get('insert') or '')
    insert_host = next((c['host'] for c in asm.connections
                        if c['kind'] == 'press' and insert and c['part'] == insert.id), None)
    insert_spec = lookup('heatset_inserts', insert.spec['size']) if insert else None
    hosts = [i for i in asm.instances.values() if i.kind != 'hardware']
    problems, clearance, ends = [], [], []
    for host in hosts:
        for dia, t0, t1 in along(origin, direction, host.shape):
            if t1 <= EPS or t0 >= length - EPS or dia >= spec['head_dia']:
                continue  # behind the head, past the tip, or a counterbore
            if insert_spec and host.id == insert_host and abs(dia - insert_spec['hole_dia']) < 0.05:
                continue  # the insert's own hole
            clearance.append({'host': host.id, 'dia': round(dia, 4), 't0': round(t0, 4), 't1': round(t1, 4)})
            ends.append(t1)
            if not low - EPS <= dia <= high + EPS:
                problems.append(f'{screw.id}: clearance hole {dia:.2f} mm in {host.id}; '
                                f'{size} needs {low:.2f} to {high:.2f} mm')
    if not clearance:
        problems.append(f'{screw.id}: no clearance hole under the head')
    grip = max(ends, default=0.0)
    hits = [t for t in (first_hit(origin, direction, h.shape) for h in hosts) if t is not None]
    floor = min(hits, default=math.inf)
    row = {'screw': screw.id, 'host': connection['host'], 'into': connection['into'], 'size': size,
           'length': length, 'clearance_holes': clearance, 'clearance_range': [round(low, 4), round(high, 4)],
           'grip': round(grip, 4), 'material_at': None if math.isinf(floor) else round(floor, 4)}
    if length > floor + EPS:
        problems.append(f'{screw.id}: {length:g} mm screw bottoms out; material {floor:.2f} mm below the head')
    if connection['into'] == 'insert':
        top = (insert.location.position - origin).dot(direction)
        engagement = length - top
        deepest = top + insert_spec['insert_length'] + insert_spec['hole_extra_depth']
        row.update(engagement=round(engagement, 4), insert_top=round(top, 4))
        needed = ENGAGEMENT * nominal(size)
        if engagement < needed - EPS:
            problems.append(f'{screw.id}: engages {engagement:.2f} mm of the insert; needs at least {needed:g} mm')
        if length > deepest + EPS and length <= floor + EPS:
            problems.append(f'{screw.id}: {length:g} mm screw bottoms out; the insert hole ends {deepest:.2f} mm below the head')
    else:
        protrusion = length - grip
        row['protrusion'] = round(protrusion, 4)
        if protrusion <= EPS:
            problems.append(f'{screw.id}: does not reach past the {connection["host"]}')
        limit = connection.get('max_depth')
        if limit is not None and protrusion > limit + EPS:
            problems.append(f'{screw.id}: goes {protrusion:.2f} mm into the substrate; limit {limit:g} mm')
    row['problems'], row['pass'] = problems, not problems
    return row


def load_assembly(path):
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location('magic_assembly', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate(path, project, overrides=None):
    """Build the assembly in this process and run every check. Returns the report dict."""
    from harness.lint import lint_design
    from .model import Assembly
    path, project = Path(path), Path(project)
    report = {'assembly': path.name, 'project': str(project.resolve()), 'pass': False, 'checks': [],
              'params': {}, 'instances': [], 'connections': [], 'collisions': [], 'fasteners': [],
              'bom': [], 'steps': []}
    add = lambda name, ok, detail: report['checks'].append(
        {'name': name, 'status': 'PASS' if ok else 'FAIL', 'detail': detail})
    lint = lint_design(path)
    if lint:
        add('Assembly file', False, f"hard-coded dimensions: {'; '.join(lint[:8])}")
        return finish(report)
    try:
        module = load_assembly(path)
        params = {k: v[0] for k, v in module.PARAMS.items()}
        unknown = set(overrides or {}) - set(params)
        if unknown:
            raise ValueError(f'unknown params: {sorted(unknown)}')
        params.update(overrides or {})
        asm = Assembly(project)
        module.assemble(asm, **params)
        if not asm.instances:
            raise ValueError('the assembly has no instances')
    except Exception:
        report['traceback'] = traceback.format_exc()
        add('Assembly file', False, report['traceback'].strip().splitlines()[-1])
        return finish(report)
    report['params'] = params
    report['instances'] = [i.describe() for i in asm.instances.values()]
    report['connections'] = asm.connections
    kinds = {k: sum(i.kind == k for i in asm.instances.values()) for k in ('printed', 'hardware', 'component')}
    add('Assembly file', True, f"{kinds['printed']} printed, {kinds['hardware']} hardware, "
                               f"{kinds['component']} purchased; {len(asm.connections)} joints")

    report['collisions'] = rows = collisions(asm)
    bad = [r for r in rows if not r['pass']]
    add('Collisions', not bad, '; '.join(f"{r['a']}/{r['b']} overlap {r['volume']:.2f} mm³" for r in bad)
        or f'{len(rows)} nearby pairs clear')

    report['fasteners'] = rows = [fastener(asm, c) for c in asm.connections if c['kind'] == 'fastener']
    problems = [p for r in rows for p in r['problems']]
    add('Fasteners', not problems, '; '.join(problems) or (f'{len(rows)} screws fit their holes and lengths' if len(rows) != 1 else '1 screw fits its hole and length'))

    bom, steps = derive(asm)
    report['bom'], report['steps'] = bom, steps
    try:
        validate_entries(asm.instances, bom, steps)
        add('Derived entries', True, f'{len(bom)} parts-list rows and {len(steps)} steps, each instance once')
    except ValueError as err:
        add('Derived entries', False, str(err))
    return finish(report)


def finish(report):
    done = {c['name'] for c in report['checks']}
    report['checks'] += [{'name': n, 'status': 'SKIPPED', 'detail': '-'} for n in CHECKS if n not in done]
    report['pass'] = all(c['status'] == 'PASS' for c in report['checks'])
    report['claims'] = [{'claim': f"Assembly: {c['name']}", 'tier': 'computed', 'status': c['status'],
                         'detail': c['detail']} for c in report['checks']]
    report['claims'].append({'claim': 'Physical assembly, fit and retention', 'tier': 'needs physical test',
                             'status': 'NOT TESTED', 'detail': 'Hardware is a simplified envelope; nothing was assembled.'})
    report['gate'] = {'name': GATE, 'status': 'PASS' if report['pass'] else 'FAIL',
                      'detail': '; '.join(f"{c['name']}: {c['detail']}" for c in report['checks']
                                          if c['status'] == 'FAIL') or
                                '; '.join(c['detail'] for c in report['checks'])}
    return json.loads(json.dumps(report, default=str))


def run_gate(path, project, out, overrides=None, timeout=180):
    """Evaluate in a subprocess; write and return <out>/report.json. A crash or timeout is a FAIL."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'report.json'
    target.unlink(missing_ok=True)
    command = [sys.executable, '-m', 'assembly.gate', str(Path(path).resolve()), str(Path(project).resolve()),
               str(target.resolve()), json.dumps(overrides or {})]
    try:
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        failure = None if target.is_file() else (done.stderr.strip().splitlines() or ['no report written'])[-1]
    except subprocess.TimeoutExpired:
        failure = f'timed out after {timeout} s'
    if failure:
        report = finish({'assembly': Path(path).name, 'project': str(project), 'pass': False,
                         'checks': [{'name': 'Assembly file', 'status': 'FAIL', 'detail': failure}]})
        target.write_text(json.dumps(report, indent=2))
    return json.loads(target.read_text())


def main():
    path, project, target = sys.argv[1:4]
    if (Path(project) / 'library' / '__init__.py').is_file():
        sys.path.insert(0, str(Path(project).resolve()))  # the project's own library, as its designs see it
    overrides = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
    report = evaluate(path, project, overrides)
    Path(target).write_text(json.dumps(report, indent=2))
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
