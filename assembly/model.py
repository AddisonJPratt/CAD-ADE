"""Assembly model: printed parts, library hardware and catalogue components joined by build123d joints.

All values are mm. An assembly file is Python with a PARAMS table (the design contract's
(default, min, max) form) and `assemble(asm, **params)`, which calls this API:

    clip = asm.printed("clip", "holder_clip")              # designs/holder_clip.py at its defaults
    screw = asm.screw("screw_1", "M3", screw_length)       # library hardware, simplified envelope
    asm.fasten(screw, clip, seats(clip, "M3")[0], into="substrate")

Placement and connection go through build123d RigidJoints: each hardware item carries a
joint at its seating face, and `fasten` / `press` attach a matching joint to the host part
and connect the two. Hardware geometry is an envelope (no threads, no socket) for checking
collisions and fit, not a manufacturing model.
"""
import json
import re
from pathlib import Path

from build123d import (Align, Axis, Box, Cylinder, GeomType, Location, Plane, RigidJoint, Vector)

from harness.worker import load_design, named_parts
from library import standard_parts

AXIS_TOLERANCE = 0.05      # mm: a cylinder this close to an axis is on it
DIA_TOLERANCE = 0.05       # mm: to match a measured cylinder to a library diameter
PROBE = 0.3                # mm: step beyond a hole end to see whether material is there
IDENT = re.compile(r'[a-z][a-z0-9_]*')
KINDS = ('printed', 'hardware', 'component')


class AssemblyError(ValueError):
    """The assembly file asks for something the model cannot build."""


def nominal(size):
    """Nominal thread diameter of a metric size: 'M2.5' -> 2.5."""
    match = re.fullmatch(r'M(\d+(?:\.\d+)?)', size or '')
    if not match:
        raise AssemblyError(f'unknown thread size {size!r}')
    return float(match.group(1))


def lookup(table, size):
    entries = standard_parts()[table]
    if size not in entries:
        raise AssemblyError(f'{size!r} not in standard_parts {table}; available: {sorted(entries)}')
    return entries[size]


class Instance:
    """One placed thing in the assembly. `shape` is located in assembly coordinates."""

    def __init__(self, ident, name, kind, shape, spec):
        self.id, self.name, self.kind, self.shape, self.spec = ident, name, kind, shape, spec
        shape.label = ident

    @property
    def location(self):
        return self.shape.location

    def describe(self):
        loc = self.location
        axis = Plane(loc).z_dir
        xyz = lambda v, places: [round(c, places) + 0.0 for c in (v.X, v.Y, v.Z)]
        return {'id': self.id, 'name': self.name, 'kind': self.kind, 'spec': self.spec,
                'position': xyz(loc.position, 6), 'rotation': xyz(loc.orientation, 6),
                'axis': xyz(axis, 9)}


class Assembly:
    def __init__(self, project):
        self.project = Path(project).resolve()
        self.instances = {}
        self.connections = []

    def _add(self, instance):
        if not isinstance(instance.id, str) or not IDENT.fullmatch(instance.id):
            raise AssemblyError(f'instance id {instance.id!r} must be lowercase letters, digits and _')
        if instance.id in self.instances:
            raise AssemblyError(f'instance id {instance.id!r} is used twice')
        self.instances[instance.id] = instance
        return instance

    def printed(self, ident, design, name=None, part=None, **params):
        """A printed part: designs/<design>.py built at its defaults, overridden by params."""
        path = self.project / 'designs' / f'{design}.py'
        if not path.is_file():
            raise AssemblyError(f'no design {path.relative_to(self.project).as_posix()}')
        module = load_design(path)
        values = {k: v[0] for k, v in module.PARAMS.items()}
        unknown = set(params) - set(values)
        if unknown:
            raise AssemblyError(f'{design}: unknown params {sorted(unknown)}')
        values.update(params)
        parts = dict(named_parts(module.build(**values)))
        if part is None and len(parts) != 1:
            raise AssemblyError(f'{design} builds {len(parts)} parts; choose one with part=')
        shape = parts[part] if part is not None else next(iter(parts.values()))
        spec = {'design': f'designs/{design}.py', 'part': part, 'params': values}
        return self._add(Instance(ident, name or design.replace('_', ' '), 'printed', shape, spec))

    def screw(self, ident, size, length, name=None):
        """Socket-head screw envelope. Its 'head' joint sits on the underside of the head, +Z down the shank."""
        spec = lookup('screws', size)
        if not length > 0:
            raise AssemblyError(f'{ident}: screw length must be positive')
        head = Cylinder(spec['head_dia'] / 2, spec['head_height'], align=(Align.CENTER, Align.CENTER, Align.MAX))
        shank = Cylinder(nominal(size) / 2, length, align=(Align.CENTER, Align.CENTER, Align.MIN))
        shape = (head + shank).solids()[0]
        RigidJoint('head', shape, Location())
        return self._add(Instance(ident, name or f'{size} x {length:g} mm screw', 'hardware', shape,
                                  {'type': 'screw', 'size': size, 'length': length,
                                   'standard': 'ISO 4762 socket head, simplified envelope'}))

    def insert(self, ident, size, name=None):
        """Heat-set insert envelope. Its 'top' joint is the insert's top face, +Z into the hole."""
        spec = lookup('heatset_inserts', size)
        shape = Cylinder(spec['insert_od'] / 2, spec['insert_length'], align=(Align.CENTER, Align.CENTER, Align.MIN))
        RigidJoint('top', shape, Location())
        return self._add(Instance(ident, name or f'{size} heat-set insert', 'hardware', shape,
                                  {'type': 'heatset_insert', 'size': size, 'length': spec['insert_length']}))

    def component(self, ident, component_id, name=None):
        """A purchased component from the catalogue, as its outline box (width x, length y, z from 0)."""
        from engine.catalogue import list_components
        found = [c for c in list_components(str(self.project)) if c['id'] == component_id]
        if not found:
            raise AssemblyError(f'no catalogue component {component_id!r}')
        item = found[0]
        dims = {k: v['value'] for k, v in item['dimensions'].items()}
        shape = Box(dims['width'], dims['length'], dims['height'], align=(Align.CENTER, Align.CENTER, Align.MIN))
        spec = {'catalogue_id': component_id, 'source': item.get('source'), 'dimensions': dims,
                'provenance': {k: v['provenance'] for k, v in item['dimensions'].items()}}
        return self._add(Instance(ident, name or item['name'], 'component', shape, spec))

    def place(self, instance, at):
        """Set an instance's location: a Location, or an (x, y, z) translation."""
        instance.shape.locate(at if isinstance(at, Location) else Location(at))
        return instance

    def fasten(self, screw, host, seat, into=None, insert=None, max_depth=None):
        """Seat a screw's head on `seat` (an assembly-space Location, +Z into the hole) of `host`.

        into: 'insert' (give the pressed insert), or 'substrate' for a screw that continues into
        something not modelled, such as a wall; max_depth then bounds how far it may go.
        """
        into = 'insert' if insert is not None else into
        if into not in ('insert', 'substrate'):
            raise AssemblyError(f'{screw.id}: fasten into an insert or the substrate')
        if screw.spec.get('type') != 'screw':
            raise AssemblyError(f'{screw.id} is not a screw')
        RigidJoint(f'{screw.id}_seat', host.shape, seat).connect_to(screw.shape.joints['head'])
        self.connections.append({'kind': 'fastener', 'screw': screw.id, 'host': host.id, 'into': into,
                                 'insert': insert.id if insert else None, 'max_depth': max_depth})

    def press(self, insert, host, mouth):
        """Press an insert into `host` at `mouth` (an assembly-space Location, +Z into the hole)."""
        if insert.spec.get('type') != 'heatset_insert':
            raise AssemblyError(f'{insert.id} is not an insert')
        RigidJoint(f'{insert.id}_mouth', host.shape, mouth).connect_to(insert.shape.joints['top'])
        self.connections.append({'kind': 'press', 'part': insert.id, 'host': host.id})


# Hole finding on built geometry: the assembly file locates hardware from the part itself,
# so a design never repeats its own hole positions.

def internal_cylinders(shape):
    """Concave cylindrical faces (holes) as (axis point, unit direction, diameter, face)."""
    found = []
    for face in shape.faces():
        if face.geom_type != GeomType.CYLINDER:
            continue
        axis = face.axis_of_rotation
        direction = axis.direction.normalized()
        point = face.position_at(0.5, 0.5)
        to_axis = (axis.position + direction * (point - axis.position).dot(direction)) - point
        if face.normal_at(point).dot(to_axis) <= 0:
            continue  # convex: an outside surface, not a hole
        found.append((axis.position, direction, 2 * face.radius, face))
    return found


def on_axis(origin, direction, cylinder):
    point, axis, _, _ = cylinder
    if abs(abs(axis.dot(direction)) - 1) > 1e-6:
        return False
    offset = point - origin
    return (offset - direction * offset.dot(direction)).length < AXIS_TOLERANCE


def extent(origin, direction, face):
    ts = [(Vector(v.X, v.Y, v.Z) - origin).dot(direction) for v in face.vertices()]
    return min(ts), max(ts)


def along(origin, direction, shape):
    """Coaxial hole segments of `shape` on an axis: [(dia, t0, t1)], t measured from origin."""
    segments = [(dia, *extent(origin, direction, face))
                for point, axis, dia, face in internal_cylinders(shape)
                if on_axis(origin, direction, (point, axis, dia, face))]
    return sorted(segments, key=lambda s: s[1])


def frame(point, direction):
    return Location(Plane(origin=point, z_dir=direction))


def _unique(locations):
    kept = []
    for loc in locations:
        if not any((loc.position - k.position).length < AXIS_TOLERANCE for k in kept):
            kept.append(loc)
    return sorted(kept, key=lambda l: (round(l.position.Z, 3), round(l.position.Y, 3), round(l.position.X, 3)))


def seats(instance, size):
    """Screw-head seats on a part: where a counterbore meets the smaller hole below it.

    Matched by the library counterbore diameter only, so a wrong clearance hole is still
    found and then failed by the gate. Each Location's +Z points from the head into the hole.
    """
    spec = lookup('screws', size)
    holes = internal_cylinders(instance.shape)
    found = []
    for bore in holes:
        point, direction, dia, face = bore
        if abs(dia - spec['counterbore_dia']) > DIA_TOLERANCE:
            continue
        c0, c1 = extent(point, direction, face)
        for other in holes:
            if other[2] >= dia - DIA_TOLERANCE or not on_axis(point, direction, other):
                continue
            s0, s1 = extent(point, direction, other[3])
            if abs(s1 - c0) < AXIS_TOLERANCE:
                found.append(frame(point + direction * c0, -direction))
            elif abs(s0 - c1) < AXIS_TOLERANCE:
                found.append(frame(point + direction * c1, direction))
    return _unique(found)


def insert_mouths(instance, size):
    """Openings of blind heat-set insert holes; each Location's +Z points into the hole."""
    spec = lookup('heatset_inserts', size)
    found = []
    for point, direction, dia, face in internal_cylinders(instance.shape):
        if abs(dia - spec['hole_dia']) > DIA_TOLERANCE:
            continue
        t0, t1 = extent(point, direction, face)
        solid_before = instance.shape.is_inside(point + direction * (t0 - PROBE))
        solid_after = instance.shape.is_inside(point + direction * (t1 + PROBE))
        if solid_after and not solid_before:
            found.append(frame(point + direction * t0, direction))
        elif solid_before and not solid_after:
            found.append(frame(point + direction * t1, -direction))
    return _unique(found)


def axis_of(instance):
    loc = instance.location
    return loc.position, Plane(loc).z_dir.normalized()


def first_hit(origin, direction, shape):
    """Distance along the axis to the first material of `shape`, or None."""
    hits = [(p - origin).dot(direction) for p, _ in shape.find_intersection_points(Axis(origin, direction))]
    ahead = [t for t in hits if t > 1e-6]
    return min(ahead) if ahead else None


def to_json(value):
    return json.loads(json.dumps(value, default=str))
