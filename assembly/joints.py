"""Joints in an assembly file (#54): `asm.join(kind, a, b)` and the gate's Joints check.

A joint lives in the assembly file, not in either design. `join` builds the joint's geometry
(library/joints.py) at the per-side clearance the project's material gets from the printer
profile, and adds it to / cuts it from the two printed instances, in each part's print frame:

    asm.join("snap_fit", "cap", "base")          # sites found on the cap/base face contact
    asm.join("dovetail", cap, base, at=frame)    # an explicit joint frame (+Z from a into b)
    asm.join("print_in_place_hinge", left, right, at=frame)
    asm.join("living_hinge", strap, at=frame)    # a flexure inside one part: +Z through the web
    asm.join("screw_insert", lid, base, size="M3", length=screw_length)

Without `at`, a snap-fit or press fit finds its sites itself: the largest face-to-face contact
between the two parts, sites at least `inset` inside its edges, with enough of the socket's
part behind them, as far apart as possible. The male feature goes on whichever part it grows
straight up from in that part's print frame (the 44 deg flanks print only upright); the
socket prints opening up or down. Joins come before any `fasten` on the same parts.

The gate re-derives the expected clearance from the profile at check time and measures the
gap between the two parts around each site on meshes reloaded from disk (manifold3d
min_gap), so an assembly that asks for a different clearance, or a part whose own geometry
crowds the joint, fails. Every joint is a computed claim only: it carries the
needs-physical-test tier until a matching print result is recorded.
"""
import json
import math
import tempfile
from pathlib import Path

from build123d import Axis, GeomType, Location, Plane, Vector, export_stl

from library import joints as lib

from .model import AssemblyError, Instance, insert_mouths, on_axis, seats

STL_TOLERANCE = 0.01      # mm, as harness/worker.py exports: the meshes the gap is measured on
STL_ANGULAR = 0.1         # rad
# Each meshed surface may sit up to one chord tolerance inside its true surface, so a measured
# gap can read up to two tolerances off the modelled one.
MEASURE_TOL = 2 * STL_TOLERANCE
PLANE_TOL = 1e-4          # mm: two faces this close along their normal are coplanar
# A male feature's flanks sit at the print slope; tilted further than 45 - slope they overhang.
UPRIGHT = math.cos(math.radians(45 - lib.slope_deg()))
CAPTIVE = ('print_in_place_hinge',)     # printed assembled: nothing to explode apart


def project_material(project):
    try:
        from engine.printers import project_printer
        return project_printer(project)['material']
    except Exception:
        return 'PLA'


def _instance(asm, ref):
    if isinstance(ref, Instance):
        return ref
    if ref not in asm.instances:
        raise AssemblyError(f'no instance {ref!r}; instances: {sorted(asm.instances)}')
    return asm.instances[ref]


def _vec(v, places=6):
    return [round(c, places) + 0.0 for c in (v.X, v.Y, v.Z)]


def frame(location):
    """JSON form of a joint frame: origin, +Z and +X in the assembly frame."""
    plane = Plane(location)
    return {'origin': _vec(plane.origin), 'axis': _vec(plane.z_dir, 9), 'x_dir': _vec(plane.x_dir, 9)}


def location(row):
    return Location(Plane(origin=row['origin'], x_dir=row['x_dir'], z_dir=row['axis']))


def _flip(site):
    """The same site seen from the other part: +Z reversed, X kept."""
    plane = Plane(site)
    return Location(Plane(origin=plane.origin, x_dir=plane.x_dir, z_dir=-plane.z_dir))


def upright(inst, site):
    """Does +Z of this site point straight up in the instance's print frame?"""
    return Plane(inst.location.inverse() * site).z_dir.Z >= UPRIGHT


def material_behind(inst, point, direction):
    """How much of the instance lies along `direction` from a point on its surface."""
    hits = sorted((p - point).dot(direction) for p, _ in inst.shape.find_intersection_points(Axis(point, direction)))
    ahead = [t for t in hits if t > PLANE_TOL]
    return ahead[0] if ahead else 0.0


def _near(one, other):
    """Do two (possibly flat) bounding boxes meet, within the coplanar tolerance?"""
    return all(lo1 <= hi2 + PLANE_TOL and lo2 <= hi1 + PLANE_TOL for lo1, hi1, lo2, hi2 in
               zip(one.min, one.max, other.min, other.max))


def contact(a, b):
    """The largest face-to-face contact between two instances: (face, normal out of a)."""
    best = None
    for fa in a.shape.faces():
        if fa.geom_type != GeomType.PLANE:
            continue
        na, ca, box = fa.normal_at(), fa.center(), fa.bounding_box()
        for fb in b.shape.faces():
            if fb.geom_type != GeomType.PLANE or na.dot(fb.normal_at()) > -1 + 1e-9:
                continue
            if abs((fb.center() - ca).dot(na)) > PLANE_TOL or not _near(box, fb.bounding_box()):
                continue
            common = fa & fb
            for face in (common.faces() if common is not None else []):
                if best is None or face.area > best[0].area:
                    best = (face, na)
    if best is None:
        raise AssemblyError(f'{a.id} and {b.id} do not touch face to face; place them so a face of one '
                            f'rests on a face of the other, or give the joint an explicit at=')
    return best


def sites(face, normal, inset, count, accept):
    """`count` points on a planar face, each at least `inset` from its edges and accepted,
    spread as far apart as possible. Deterministic: a grid at half the inset."""
    plane = Plane(origin=face.center(), z_dir=normal)
    step = inset / 2
    reach = int(face.bounding_box().diagonal / 2 / step) + 1
    edges = face.edges()
    found = []
    for i in range(-reach, reach + 1):
        for j in range(-reach, reach + 1):
            point = plane.from_local_coords((i * step, j * step))
            if face.distance_to(point) > PLANE_TOL:
                continue
            if min(e.distance_to(point) for e in edges) < inset - PLANE_TOL or not accept(point):
                continue
            found.append(point)
    if len(found) < count:
        return found
    if count == 1:
        return [min(found, key=lambda p: (p - face.center()).length)]
    chosen = [max(((p, q) for p in found for q in found), key=lambda pq: (pq[0] - pq[1]).length)[0]]
    while len(chosen) < count:
        chosen.append(max(found, key=lambda p: min((p - c).length for c in chosen)))
    return chosen


def _x_dir(normal):
    for axis in (Vector(1, 0, 0), Vector(0, 1, 0)):
        x = axis - normal * axis.dot(normal)
        if x.length > 1e-6:
            return x.normalized()


def _apply(inst, site, add=None, cut=None):
    """Cut then add joint solids (joint frame) on an instance, in its own print frame."""
    loc = inst.location
    shape = inst.shape.located(Location())
    if inst.original is None:
        inst.original = shape
    local = loc.inverse() * site
    if cut is not None:
        shape = shape - cut.moved(local)
    if add is not None:
        shape = shape.fuse(add.moved(local)).clean()
    solids = shape.solids()
    if len(solids) != 1:
        what = add.label if add is not None else cut.label
        raise AssemblyError(f'the {what} leaves {inst.id} in {len(solids)} pieces; '
                            f'move the joint so it sits on the part')
    joints = getattr(inst.shape, 'joints', {})
    inst.shape = solids[0].located(loc)
    inst.shape.label = inst.id
    inst.shape.joints = joints


def join(asm, kind, a, b=None, at=None, count=None, clearance=None, **options):
    """Join instances a and b with a joint of `kind`; see the module docstring."""
    if kind not in lib.KINDS:
        raise AssemblyError(f'unknown joint {kind!r}; joints: {", ".join(lib.KINDS)}')
    a = _instance(asm, a)
    b = _instance(asm, b) if b is not None else None
    material = project_material(asm.project)
    if kind == 'living_hinge':
        return _living(asm, a, at, material)
    if b is None or b is a:
        raise AssemblyError(f'a {lib.LABELS[kind]} joins two different instances')
    if kind == 'screw_insert':
        return _screw_insert(asm, a, b, material, **options)
    for inst in (a, b):
        if inst.kind != 'printed':
            raise AssemblyError(f'{inst.id}: a {lib.LABELS[kind]} joins printed parts')
    spec = lib.spec(kind)
    expected = lib.clearance(spec['fit'], material)
    used = expected if clearance is None else clearance
    if kind == 'dovetail':
        options.setdefault('run', max(b.shape.bounding_box().diagonal, a.shape.bounding_box().diagonal))
    try:
        geom = lib.build(kind, used, **options)
    except ValueError as err:
        raise AssemblyError(f'{kind}: {err}') from None
    if at is not None:
        placed = [(s, a, b) for s in (at if isinstance(at, (list, tuple)) else [at])]
    elif kind in lib.FACE_JOINTS:
        placed = _found(a, b, geom, count if count is not None else spec['count'], kind)
    else:
        raise AssemblyError(f'a {lib.LABELS[kind]} needs at=: the frame it is built in')
    for site, male, female in placed:
        _apply(male, site, add=geom.a_add, cut=geom.a_cut)
        _apply(female, site, add=geom.b_add, cut=geom.b_cut)
    male, female = placed[0][1], placed[0][2]
    row = {'kind': 'joint', 'id': f'{kind}_{a.id}_{b.id}', 'type': kind, 'a': a.id, 'b': b.id,
           'male': male.id, 'female': female.id, 'fit': spec['fit'], 'material': material,
           'clearance': used, 'options': options, 'checks': geom.checks, 'revolute': geom.revolute,
           'sites': [{**frame(s), 'male': m.id} for s, m, _ in placed]}
    asm.connections.append(row)
    return row


def _found(a, b, geom, count, kind):
    face, normal = contact(a, b)
    probe = Location(Plane(origin=face.center(), z_dir=normal, x_dir=_x_dir(normal)))
    if upright(a, probe):
        male, female, axis = a, b, normal
    elif upright(b, _flip(probe)):
        male, female, axis = b, a, -normal
    else:
        raise AssemblyError(f'a {lib.LABELS[kind]} needs its peg to grow straight up from one part as it '
                            f'prints; neither {a.id} nor {b.id} has the contact face on top')
    accept = lambda p: material_behind(female, p, axis) >= geom.depth - PLANE_TOL
    points = sites(face, axis, geom.inset, count, accept)
    if len(points) < count:
        raise AssemblyError(f'the {a.id}/{b.id} contact has room for {len(points)} of {count} '
                            f'{lib.LABELS[kind]} sites: each needs {geom.inset:.2f} mm from the contact '
                            f'edge and {geom.depth:.2f} mm of {female.id} behind it')
    return [(Location(Plane(origin=p, x_dir=_x_dir(axis), z_dir=axis)), male, female) for p in points]


def _living(asm, part, at, material):
    if at is None:
        raise AssemblyError('a living hinge needs at=: a frame on the bed under the web, +Z through it')
    if part.kind != 'printed':
        raise AssemblyError(f'{part.id}: a living hinge is part of a printed part')
    row = {'kind': 'joint', 'id': f'living_hinge_{part.id}', 'type': 'living_hinge', 'a': part.id, 'b': None,
           'male': part.id, 'female': None, 'fit': None, 'material': material, 'clearance': None,
           'options': {}, 'checks': {}, 'revolute': True, 'sites': [{**frame(at), 'male': part.id}]}
    asm.connections.append(row)
    return row


def _screw_insert(asm, a, b, material, size='M3', length=None, **_):
    """Heat-set inserts pressed into b's insert holes; screws through a's seats into them."""
    if length is None:
        raise AssemblyError('a screw + insert joint needs the screw length')
    pairs = []
    for seat in seats(a, size):
        plane = Plane(seat)
        for mouth in insert_mouths(b, size):
            mp = Plane(mouth)
            if mp.z_dir.dot(plane.z_dir) > 1 - 1e-6 and on_axis(plane.origin, plane.z_dir, (mp.origin, mp.z_dir, 0, None)):
                pairs.append((seat, mouth))
    if not pairs:
        raise AssemblyError(f'no {size} seat in {a.id} lines up with a {size} insert hole in {b.id}')
    screws, inserts = [], []
    for n, (seat, mouth) in enumerate(pairs, 1):
        insert = asm.insert(f'{b.id}_insert_{n}', size, name=f'{size} heat-set insert {n}')
        asm.press(insert, b, mouth)
        screw = asm.screw(f'{a.id}_screw_{n}', size, length, name=f'{size} screw {n}')
        asm.fasten(screw, a, seat, insert=insert)
        screws.append(screw.id)
        inserts.append(insert.id)
    row = {'kind': 'joint', 'id': f'screw_insert_{a.id}_{b.id}', 'type': 'screw_insert', 'a': a.id, 'b': b.id,
           'male': a.id, 'female': b.id, 'fit': lib.spec('screw_insert')['fit'], 'material': material,
           'clearance': None, 'options': {'size': size, 'length': length}, 'checks': {}, 'revolute': False,
           'sites': [{**frame(seat), 'male': a.id} for seat, _ in pairs], 'screws': screws, 'inserts': inserts}
    asm.connections.append(row)
    return row


# --- the hierarchy: which side of a joint hangs off which -----------------------------------------

def child_of(asm, row):
    """(child, parent) of a two-part joint: the instance declared later hangs off the other."""
    order = list(asm.instances)
    a, b = row['a'], row['b']
    return (b, a) if order.index(b) > order.index(a) else (a, b)


def manifest_axis(row, child):
    """Unit axis along which the child goes onto its parent (or turns, for a hinge)."""
    site = row['sites'][0]
    z, x = Vector(*site['axis']), Vector(*site['x_dir'])
    y = z.cross(x)
    if row['revolute']:
        return z
    if row['type'] == 'dovetail':        # the tail slides in along -Y of its frame
        return -y if child == site['male'] else y
    if row['type'] == 'screw_insert':
        return z
    return z if child == site['male'] else -z


STEP_TEXT = {
    'snap_fit': 'Snap the {child} onto the {parent}: {n} snap peg{s} click into their sockets.',
    'press_fit': 'Press the {child} onto the {parent}: {n} pin{s}; squeeze it square in a vise.',
    'dovetail': 'Slide the {child} onto the {parent} along the dovetail.',
    'print_in_place_hinge': 'The {child} and the {parent} print assembled on their hinge: print them together, '
                            'then work the hinge free.',
}


# --- the gate's check ------------------------------------------------------------------------------

def _manifold(shape, folder, name):
    import manifold3d
    import numpy as np
    import trimesh
    path = Path(folder) / f'{name}.stl'
    export_stl(shape, str(path), tolerance=STL_TOLERANCE, angular_tolerance=STL_ANGULAR)
    mesh = trimesh.load_mesh(path)
    return manifold3d.Manifold(manifold3d.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                                               tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))


def measure_gap(asm, row, folder):
    """Smallest gap between the joint's two parts inside each site's probe, on reloaded meshes."""
    geom = lib.build(row['type'], row['clearance'], **row['options'])
    a, b = asm.instances[row['a']], asm.instances[row['b']]
    bodies = {i.id: _manifold(i.shape, folder, i.id) for i in (a, b)}
    gaps = []
    for n, site in enumerate(row['sites']):
        probe = _manifold(geom.probe.moved(location(site)), folder, f'probe_{row["id"]}_{n}')
        near = {k: v ^ probe for k, v in bodies.items()}
        if any(m.is_empty() for m in near.values()):
            gaps.append(None)
            continue
        overlap = (near[a.id] ^ near[b.id]).volume()
        gaps.append(0.0 if overlap > 0 else near[a.id].min_gap(near[b.id], 4 * row['clearance'] + 1))
    return gaps


SWING_STEP = 5.0          # deg between the poses the hinge sweep checks


def _rotation(axis, origin, degrees):
    """3x4 matrix turning points by `degrees` about the line through origin along axis."""
    import numpy as np
    k = np.asarray(axis, dtype=float)
    k /= np.linalg.norm(k)
    t = math.radians(degrees)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    R = np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K
    o = np.asarray(origin, dtype=float)
    return np.hstack([R, (o - R @ o).reshape(3, 1)])


def swing_clear(asm, row, folder, limit):
    """Turn b about the hinge axis each way in SWING_STEP steps up to the declared swing, on
    reloaded meshes. Returns (clear_low, clear_high): the first poses where the parts overlap by
    more than `limit` mm^3 stop the range."""
    site = row['sites'][0]
    a = _manifold(asm.instances[row['a']].shape, folder, f"swing_{row['a']}")
    b = _manifold(asm.instances[row['b']].shape, folder, f"swing_{row['b']}")
    swing = row['checks']['swing_deg']
    steps = int(math.ceil(swing / SWING_STEP))
    reached = []
    for sign in (-1, 1):
        clear = 0.0
        for n in range(1, steps + 1):
            angle = sign * min(n * SWING_STEP, swing)
            if (a ^ b.transform(_rotation(site['axis'], site['origin'], angle))).volume() > limit:
                break
            clear = angle
        reached.append(clear)
    return tuple(reached)


def overhang_added(inst):
    """Unsupported area (mm^2) the joints added to an instance, in its print frame."""
    from library.engineering import unsupported_area
    if inst.original is None:
        return 0.0
    return unsupported_area(inst.shape.located(Location())) - unsupported_area(inst.original)


def tier(row):
    """needs physical test, until a print result for this joint type and material says it fit."""
    events = []
    try:
        from engine.make import calibration_dir
        folder = calibration_dir() / 'events'
        events = [json.loads(p.read_text()) for p in sorted(folder.glob('*.json'))] if folder.is_dir() else []
    except Exception:
        pass
    good = [e for e in events if e.get('joint_type') == row['type'] and e.get('material') == row['material']
            and e.get('result') == 'perfect']
    return ('print tested', f'{len(good)} recorded print(s) fit') if good else (
        'needs physical test', 'no print result recorded for this joint and material')


def check(asm, fasteners):
    """One row per joint: measured against the profile's clearance, and the type's own rules."""
    from library.engineering import rules
    rows = []
    overhang = {}
    tolerance = rules()['overhang_tolerance_mm2']
    with tempfile.TemporaryDirectory(prefix='magic_joints_') as folder:
        for c in asm.connections:
            if c['kind'] != 'joint':
                continue
            problems, row = [], {'id': c['id'], 'type': c['type'], 'label': lib.LABELS[c['type']], 'a': c['a'],
                                 'b': c['b'], 'fit': c['fit'], 'material': c['material'], 'sites': len(c['sites'])}
            if c['type'] in lib.BUILDERS:
                expected = lib.clearance(c['fit'], c['material'])
                gaps = measure_gap(asm, c, folder)
                row.update(expected=expected, measured=[None if g is None else round(g, 4) for g in gaps])
                for n, g in enumerate(gaps, 1):
                    if g is None:
                        problems.append(f"{c['id']} site {n}: no joint material where the joint was built")
                    elif abs(g - expected) > MEASURE_TOL:
                        problems.append(f"{c['id']} site {n}: gap {g:.3f} mm; {c['material']} {c['fit']} fit "
                                        f"is {expected:g} mm per side")
                for ident in {c['a'], c['b']}:
                    if ident not in overhang:
                        overhang[ident] = overhang_added(asm.instances[ident])
                    if overhang[ident] > tolerance:
                        problems.append(f"{c['id']}: adds {overhang[ident]:.1f} mm² of unsupported overhang to "
                                        f"{ident} as printed")
                row['overhang_added'] = {i: round(overhang[i], 3) for i in sorted({c['a'], c['b']})}
            if c['type'] == 'print_in_place_hinge':
                from .gate import OVERLAP_LIMIT
                low, high = swing_clear(asm, c, folder, OVERLAP_LIMIT)
                swing = c['checks']['swing_deg']
                row['swing'] = [low, high]
                if low > -swing or high < swing:
                    problems.append(f"{c['id']}: the leaves collide turning past {low:g}/{high:g} deg; "
                                    f"the joint declares ±{swing:g} deg")
            if c['type'] == 'snap_fit':
                k = c['checks']
                row['strain'] = round(k['strain'], 4)
                if k['strain'] > k['max_strain']:
                    problems.append(f"{c['id']}: prong strain {k['strain']:.3f} over {k['max_strain']:g}")
                if k['retention'] <= 0:
                    problems.append(f"{c['id']}: the barb does not exceed the clearance, so it does not retain")
                if k['slot'] < k['prong_close']:
                    problems.append(f"{c['id']}: the slot is narrower than the prongs must close")
            elif c['type'] == 'living_hinge':
                rule = lib.living_hinge_rule(c['material'])
                site = c['sites'][0]
                web = material_behind(asm.instances[c['a']], Vector(*site['origin']), Vector(*site['axis']))
                row.update(web=round(web, 4), web_range=[rule['min'], rule['max']], note=rule['note'])
                if not rule['min'] - MEASURE_TOL <= web <= rule['max'] + MEASURE_TOL:
                    problems.append(f"{c['id']}: web {web:.2f} mm; a living hinge flexes between "
                                    f"{rule['min']:g} and {rule['max']:g} mm")
            elif c['type'] == 'screw_insert':
                mine = [f for f in fasteners if f['screw'] in c['screws']]
                row['clearance_holes'] = [h['dia'] for f in mine for h in f['clearance_holes']]
                problems += [p for f in mine for p in f['problems']]
            row['tier'], row['evidence'] = tier(c)
            row['problems'], row['pass'] = problems, not problems
            rows.append(row)
    return rows
