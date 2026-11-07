"""The assembly manifest: one derived file per assembly, the contract between the engine and Studio.

The assembly gate writes `assembly.json` (schema: `manifest.schema.json`) and one STL per
instance under `meshes/` next to its report. Studio, the parts list and the instructions
generator read only this file; none of them compute placements, explode directions,
quantities or step order, so none of them can drift from the CAD.

Frames and units: every position, quaternion, joint origin and axis is in the assembly
frame (mm, degrees). A mesh is stored in its instance's local frame; the instance's
`transform` (position + quaternion [x, y, z, w], three.js order) places it.

The tree and joints come from the assembly file's connections:
- `fasten(screw, host, ...)`: the screw hangs off its host by a prismatic `fastener` joint along
  the screw axis (head into hole).
- `press(insert, host, ...)`: the insert hangs off its host by a prismatic `press` joint.
- a screw through a part into an insert pressed into another part clamps the two: the clamped
  part hangs off the insert's host by a `fixed` `clamp` joint along the screw axis.
Everything else is a root.

Explode rule (derived, deterministic; never hand-written):
1. A child moves along the reverse of its joint axis: hardware backs out of its hole, a clamped
   part lifts off the part it is clamped to.
2. It moves its own extent along that direction plus a gap: GAP_RATIO of the extent, at least
   GAP_MIN mm.
3. A clamped part also clears the farthest sibling that moves the same way (an insert popping
   out of the same base), so they never overlap when exploded.
4. Offsets accumulate down the tree: a lid carries its screws. `offset` is the full-explode
   displacement in the assembly frame; Studio scales it by a 0..1 slider.
Roots stay put.
"""
import hashlib
import json
import math
import sys
from pathlib import Path, PurePosixPath

MANIFEST = 'assembly.json'
MESHES = 'meshes'
SCHEMA = Path(__file__).with_name('manifest.schema.json')
FIXTURE = Path(__file__).resolve().parent.parent / 'tests' / 'fixtures' / 'assembly_manifest' / 'holder_clip.json'
SCHEMA_VERSION = 1
GAP_RATIO = 0.25      # explode gap as a fraction of the part's own extent
GAP_MIN = 5.0         # mm: smallest explode gap, so thin parts still separate visibly
SAME_WAY = 0.99       # cosine above which two explode directions count as the same
UNIT = 1e-6           # tolerance on unit-length vectors and quaternions
TOOLS = {'press': 'soldering iron', 'fastener': 'hex key'}
DISCLAIMER = ('Hardware is a simplified envelope (no threads or sockets). Exploded offsets and steps '
              'illustrate how the parts go together; they are not a collision-checked tool path or a '
              'motion simulation. Fit, retention and strength are not physically tested.')


class ManifestError(ValueError):
    """A manifest that breaks the schema or refers to something that is not there."""


def gap(extent):
    return max(GAP_RATIO * extent, GAP_MIN)


def _same_way(a, b):
    return sum(x * y for x, y in zip(a, b)) > SAME_WAY


def explode(nodes):
    """Explode rows from [{id, parent, direction, extent, role}]; see the module docstring."""
    by_id = {n['id']: n for n in nodes}
    order, state = [], {}
    def visit(ident):   # parents before children; a cycle is an error
        if state.get(ident) == 'done':
            return
        if state.get(ident) == 'open':
            raise ManifestError(f'the assembly tree has a cycle through {ident!r}')
        state[ident] = 'open'
        parent = by_id[ident]['parent']
        if parent is not None:
            visit(parent)
        state[ident] = 'done'
        order.append(ident)
    for n in nodes:
        visit(n['id'])

    plain = {n['id']: 0.0 if n['parent'] is None else n['extent'] + gap(n['extent']) for n in nodes}
    distance = dict(plain)
    for n in nodes:
        if n['parent'] is not None and n.get('role') == 'clamp':
            siblings = [plain[s['id']] for s in nodes if s['parent'] == n['parent'] and s['id'] != n['id']
                        and s.get('role') != 'clamp' and _same_way(s['direction'], n['direction'])]
            distance[n['id']] += max(siblings, default=0.0)
    offset = {}
    for ident in order:
        n = by_id[ident]
        base = offset[n['parent']] if n['parent'] is not None else [0.0, 0.0, 0.0]
        offset[ident] = [b + c * distance[ident] for b, c in zip(base, n['direction'])]
    clean = lambda v: [round(c, 4) + 0.0 for c in v]
    return [{'instance': n['id'], 'direction': clean(n['direction']) if n['parent'] is not None else [0, 0, 1],
             'distance': round(distance[n['id']], 4), 'offset': clean(offset[n['id']])} for n in nodes]


def quaternion_matrix(q):
    """3x3 rotation (rows) of a unit quaternion [x, y, z, w], as a reader applies a transform."""
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


# --- building from an evaluated assembly -------------------------------------------------------

def _vec(v, places=9):
    return [round(c, places) + 0.0 for c in (v.X, v.Y, v.Z)]


def _transform(location):
    q = location.wrapped.Transformation().GetRotation()
    position = location.position
    return {'position': [round(c, 6) + 0.0 for c in (position.X, position.Y, position.Z)],
            'quaternion': [round(c, 9) + 0.0 for c in (q.X(), q.Y(), q.Z(), q.W())]}


def _extent(shape, direction):
    box = shape.bounding_box()
    corners = [(x, y, z) for x in (box.min.X, box.max.X) for y in (box.min.Y, box.max.Y)
               for z in (box.min.Z, box.max.Z)]
    ts = [sum(c * d for c, d in zip(corner, direction)) for corner in corners]
    return max(ts) - min(ts)


def _source(inst):
    spec = inst.spec
    if inst.kind == 'printed':
        return spec['design'] + (f"#{spec['part']}" if spec.get('part') else '')
    if inst.kind == 'component':
        return f"catalogue:{spec['catalogue_id']}"
    table = 'screws' if spec['type'] == 'screw' else 'heatset_inserts'
    return f"library/standard_parts.json#{table}/{spec['size']}"


def tree(asm):
    """(parent of each instance, joints) derived from the assembly's connections."""
    from .model import axis_of
    parent = {ident: None for ident in asm.instances}
    joints = []
    def join(child, host, kind, role, origin, axis):
        parent[child] = host
        joints.append({'id': f'{child}_{role}', 'type': kind, 'role': role, 'parent': host, 'child': child,
                       'origin': _vec(origin, 6), 'axis': _vec(axis), 'rest': 0.0, 'range': None})
    for c in asm.connections:
        if c['kind'] == 'press':
            origin, axis = axis_of(asm.instances[c['part']])
            join(c['part'], c['host'], 'prismatic', 'press', origin, axis)
    for c in asm.connections:
        if c['kind'] == 'fastener':
            origin, axis = axis_of(asm.instances[c['screw']])
            join(c['screw'], c['host'], 'prismatic', 'fastener', origin, axis)
    def ancestors(ident):
        seen = []
        while parent[ident] is not None:
            ident = parent[ident]
            seen.append(ident)
        return seen
    for c in asm.connections:
        if c['kind'] != 'fastener' or not c.get('insert'):
            continue
        base = parent[c['insert']]
        clamped = c['host']
        if base and base != clamped and parent[clamped] is None and clamped not in ancestors(base):
            origin, axis = axis_of(asm.instances[c['screw']])
            join(clamped, base, 'fixed', 'clamp', origin, axis)
    return parent, joints


def _steps(report, joints):
    rows = {i: row for row in report['bom'] for i in row['part_ids']}
    roles = {j['child']: j for j in joints}
    steps = []
    for step in report['steps']:
        ids = step['part_ids']
        done = [roles[i]['id'] for i in ids if i in roles]
        tools = [TOOLS[roles[i]['role']] for i in ids if i in roles and roles[i]['role'] in TOOLS]
        hardware = [rows[i] for i in ids if rows[i]['category'] == 'Hardware']
        callout = None
        if hardware:
            counts = {}
            for row in hardware:
                counts[row['name']] = counts.get(row['name'], 0) + 1
            callout = ', '.join(f'{n} × {name}' for name, n in counts.items())
        steps.append({**step, 'joints': done, 'tool': tools[0] if tools else None, 'callout': callout})
    return steps


def _relative(path, project):
    path, project = Path(path).resolve(), Path(project).resolve()
    return path.relative_to(project).as_posix() if project in path.parents else path.name


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(asm, report, path, project, name=None):
    """The manifest dict for an evaluated assembly and its gate report."""
    parent, joints = tree(asm)
    by_child = {j['child']: j for j in joints}
    nodes = []
    for ident, inst in asm.instances.items():
        joint = by_child.get(ident)
        direction = [-c for c in joint['axis']] if joint else [0.0, 0.0, 1.0]
        nodes.append({'id': ident, 'parent': parent[ident], 'direction': direction,
                      'extent': _extent(inst.shape, direction), 'role': joint['role'] if joint else None})
    sources = {_relative(path, project): _digest(path)}
    for inst in asm.instances.values():
        if inst.kind == 'printed':
            sources[inst.spec['design']] = _digest(Path(project) / inst.spec['design'])
    manifest = {
        'schema_version': SCHEMA_VERSION, 'id': Path(path).stem, 'name': name or Path(path).stem.replace('_', ' '),
        'units': 'mm', 'angle_units': 'deg', 'pass': report['pass'], 'gate': report['gate']['status'],
        'disclaimer': DISCLAIMER, 'params': report['params'],
        'provenance': {'assembly_file': _relative(path, project), 'sources': dict(sorted(sources.items())),
                       'physical_assembly_tested': False},
        'instances': [{'id': ident, 'name': inst.name, 'kind': inst.kind, 'source': _source(inst),
                       'parent': parent[ident], 'transform': _transform(inst.location),
                       'mesh': f'{MESHES}/{ident}.stl'} for ident, inst in asm.instances.items()],
        'joints': joints,
        'explode': explode(nodes),
        'steps': _steps(report, joints),
        'bom': report['bom'],
        'warnings': [],
    }
    validate(manifest)
    return manifest


def write(asm, manifest, out):
    """Write the manifest and each instance's mesh in its local frame into `out`."""
    from build123d import Location, export_stl
    out = Path(out)
    (out / MESHES).mkdir(parents=True, exist_ok=True)
    for inst in manifest['instances']:
        shape = asm.instances[inst['id']].shape
        export_stl(shape.located(Location()), str(out / inst['mesh']), tolerance=0.01, angular_tolerance=0.1)
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2) + '\n')


# --- validation ----------------------------------------------------------------------------------

def _unit(v):
    return all(math.isfinite(c) for c in v) and abs(math.sqrt(sum(c * c for c in v)) - 1) < UNIT


def validate(manifest):
    """Schema, then the cross-references a schema cannot express. Raises ManifestError."""
    import jsonschema
    try:
        jsonschema.validate(manifest, json.loads(SCHEMA.read_text()))
    except jsonschema.ValidationError as err:
        where = '/'.join(str(p) for p in err.absolute_path) or 'manifest'
        raise ManifestError(f'{where}: {err.message}') from None
    from .gate import validate_entries
    instances = manifest['instances']
    ids = [i['id'] for i in instances]
    if len(set(ids)) != len(ids):
        raise ManifestError(f'instance ids repeat: {sorted({i for i in ids if ids.count(i) > 1})}')
    known = set(ids)
    parent = {i['id']: i['parent'] for i in instances}
    for inst in instances:
        if inst['parent'] is not None and inst['parent'] not in known:
            raise ManifestError(f"{inst['id']}: unknown parent {inst['parent']!r}")
        t = inst['transform']
        if not all(math.isfinite(c) for c in t['position']) or not _unit(t['quaternion']):
            raise ManifestError(f"{inst['id']}: transform needs a finite position and a unit quaternion")
        mesh = PurePosixPath(inst['mesh'])
        if mesh.is_absolute() or '..' in mesh.parts or mesh.suffix != '.stl':
            raise ManifestError(f"{inst['id']}: mesh must be an .stl path inside the output folder")
    for ident in ids:   # walk up from every instance; a revisit is a cycle
        seen, at = set(), ident
        while at is not None:
            if at in seen:
                raise ManifestError(f'the assembly tree has a cycle through {at!r}')
            seen.add(at)
            at = parent[at]
    joint_ids = set()
    for joint in manifest['joints']:
        if joint['id'] in joint_ids:
            raise ManifestError(f"joint id {joint['id']!r} repeats")
        joint_ids.add(joint['id'])
        if {joint['parent'], joint['child']} - known:
            raise ManifestError(f"{joint['id']}: names an instance that does not exist")
        if parent[joint['child']] != joint['parent']:
            raise ManifestError(f"{joint['id']}: joins {joint['child']} to {joint['parent']}, "
                                f"but the tree hangs it off {parent[joint['child']]}")
        if not all(math.isfinite(c) for c in joint['origin']) or not _unit(joint['axis']):
            raise ManifestError(f"{joint['id']}: needs a finite origin and a unit axis")
        if joint['range'] is not None:
            low, high = joint['range']
            if low > high or not low <= joint['rest'] <= high:
                raise ManifestError(f"{joint['id']}: range {joint['range']} must be ordered and contain rest")
    exploded = [r['instance'] for r in manifest['explode']]
    if sorted(exploded) != sorted(ids):
        raise ManifestError('explode must have exactly one row per instance')
    for row in manifest['explode']:
        if not _unit(row['direction']) or not all(math.isfinite(c) for c in row['offset']):
            raise ManifestError(f"{row['instance']}: explode needs a unit direction and a finite offset")
    for step in manifest['steps']:
        if set(step['joints']) - joint_ids:
            raise ManifestError(f"step {step['number']} names unknown joints {sorted(set(step['joints']) - joint_ids)}")
    try:
        validate_entries(ids, manifest['bom'], manifest['steps'])
    except ValueError as err:
        raise ManifestError(str(err)) from None
    return True


def main(argv):
    """--refresh-fixture: rebuild the committed holder manifest after a reviewed change."""
    if argv != ['--refresh-fixture']:
        print(__doc__.split('\n\n')[0])
        print('usage: python -m assembly.manifest --refresh-fixture')
        return 2
    import tempfile
    from .gate import evaluate
    root = FIXTURE.parent.parent.parent.parent
    with tempfile.TemporaryDirectory() as out:
        report = evaluate(root / 'assembly' / 'holder_clip.py', root, out=out)
        if 'manifest' not in report:
            print('the holder assembly did not build; nothing written')
            return 1
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text((Path(out) / MANIFEST).read_text())
    print(f'wrote {FIXTURE.relative_to(root)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
