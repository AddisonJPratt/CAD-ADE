"""Patterns and ingrained surface textures applied to a selected face (issue #52).

Patterns (linear, grid, circular, along a path) place a tool solid on a planar face at
each point of a parametric layout. Textures (straight and diamond knurl, ribbing, hex,
embossed or engraved text and outlines) ingrain a selected face. Every function returns the same
FeatureProposal as library/engineering.py, so the print check, slop flags and
allow_supports rule are shared.

Printability bounds, all derived from print_rules and texture_rules in
standard_parts.json (never hard-coded):
- min_feature: one nozzle line. A ridge, groove, web or glyph stroke narrower than this
  cannot be laid down at all; the texture is refused ("the nozzle's minimum feature").
- min_pitch: two lines (a ridge and a groove).
- min_depth: texture_rules.min_depth_nozzles of a nozzle; shallower disappears into the
  perimeter's own wobble. max_depth: texture_rules.max_depth; deeper is a pocket, not a
  texture (use lightening_cutouts).
- Flanks rise at tan(self_supporting_deg) per mm across the face, so every groove flank,
  pocket roof and raised-glyph underside on a wall prints without support, whatever
  direction it runs. That also caps depth: a V groove of width w is at most
  w/2 * flank_rate deep.

Coarse versus fine (the documented trade-off): a texture whose pitch is at least two
perimeters (brep_min_pitch) and whose feature count fits texture_rules.brep_max_features
is real B-rep geometry, in the STEP and every gate. A finer texture would be thousands of
boolean slivers, so it is recorded as a mesh texture: the proposal leaves the B-rep
unchanged and the harness displaces the exported STL (apply_mesh_textures), then gates the
displaced STL reloaded from disk. The STEP stays smooth. The cheap alternative for a
purely visual grip is the slicer's fuzzy skin, which needs no geometry at all.

Known limit of mesh textures: the refined triangles approximate a curved groove profile
with facets that can tilt up to about 1 deg off vertical, just past the gate's 0.5 deg
tolerance, so about 1 % of the textured area counts toward the brief-wording overhang
share. It is physically vertical; give a small part enough footprint.

All dimensions in mm; Z is print-up.
"""
import math

import numpy as np
from build123d import (Align, Box, Cone, Cylinder, Location, Plane, Polygon, Pos, RegularPolygon, Sketch,
                       Solid, Text, Vector, extrude, offset)

from .engineering import (FEATURES, FeatureError, GeomType, VERTICAL_EPS, _bounded, _describe, _face_frame,
                          _finish, _inside_face, min_wall, rules, select_face, slope_deg)
from .features import standard_parts

PLANAR_TOL = 1e-3        # mm, a mesh vertex this close to the texture plane is on it
SIMPLIFY_TOL = 1e-5      # mm: collapses what refinement left coplanar, leaves the texture alone
CHORD_TOL = 0.02         # mm, the same for a cylinder: twice the STL export chord tolerance (0.01)
FOOTPRINT_SHARE = 1e-6  # share of an instance's contact allowed off the face (boolean noise)
_MESH_TEXTURES = []      # specs declared while a design builds; the harness applies them at export


def texture_rules():
    """Texture bounds derived from print_rules + texture_rules (standard_parts.json)."""
    pr, tr = rules(), standard_parts()["texture_rules"]
    nozzle = pr["nozzle"]
    return {"min_feature": nozzle,
            "min_pitch": 2 * nozzle,
            "brep_min_pitch": 2 * min_wall(),
            "min_depth": nozzle * tr["min_depth_nozzles"],
            "max_depth": tr["max_depth"],
            "brep_max_features": tr["brep_max_features"],
            "mesh_samples_per_pitch": tr["mesh_samples_per_pitch"],
            "flank_rate": math.tan(math.radians(slope_deg()))}


def declared_mesh_textures():
    return list(_MESH_TEXTURES)


def reset_mesh_textures():
    _MESH_TEXTURES.clear()


# ---------------------------------------------------------------- pattern layouts


def _count(name, count, low=1, high=500):
    if int(count) != count:
        raise FeatureError(f"{name}: count {count} must be a whole number")
    return int(_bounded(name, "count", count, low, high))


def linear_pattern(count, spacing, angle=0.0):
    """`count` points `spacing` apart along a line at `angle` deg from the face's u axis, centred."""
    count = _count("linear_pattern", count)
    _bounded("linear_pattern", "spacing", spacing, 1e-6, math.inf)
    a = math.radians(angle)
    return [((i - (count - 1) / 2) * spacing * math.cos(a), (i - (count - 1) / 2) * spacing * math.sin(a))
            for i in range(count)]


def grid_pattern(count_u, count_v, spacing_u, spacing_v):
    """A centred count_u x count_v grid."""
    count_u, count_v = _count("grid_pattern", count_u), _count("grid_pattern", count_v)
    _bounded("grid_pattern", "spacing_u", spacing_u, 1e-6, math.inf)
    _bounded("grid_pattern", "spacing_v", spacing_v, 1e-6, math.inf)
    return [((i - (count_u - 1) / 2) * spacing_u, (j - (count_v - 1) / 2) * spacing_v)
            for i in range(count_u) for j in range(count_v)]


def circular_pattern(count, radius, start=0.0, sweep=360.0):
    """`count` points on a circle of `radius` round the face centre; a full sweep skips the seam."""
    count = _count("circular_pattern", count)
    _bounded("circular_pattern", "radius", radius, 1e-6, math.inf)
    _bounded("circular_pattern", "sweep", sweep, 1e-6, 360.0)
    closed = abs(sweep - 360.0) < 1e-9
    step = sweep / (count if closed or count == 1 else count - 1)
    return [(radius * math.cos(math.radians(start + i * step)), radius * math.sin(math.radians(start + i * step)))
            for i in range(count)]


def path_pattern(path, count):
    """`count` Locations evenly along an Edge/Wire (ends included), z along the tangent."""
    count = _count("path_pattern", count)
    params = [0.5] if count == 1 else [i / (count - 1) for i in range(count)]
    return [path.location_at(t) for t in params]


# ---------------------------------------------------------------- shared face handling


def _target(name, shape, face):
    target = select_face(shape, face)
    if target.geom_type == GeomType.PLANE:
        normal = target.normal_at()
    elif target.geom_type == GeomType.CYLINDER:
        axis = target.axis_of_rotation if hasattr(target, "axis_of_rotation") else None
        direction = axis.direction if axis is not None else Vector(0, 0, 1)
        if abs(abs(direction.Z) - 1) > VERTICAL_EPS:
            raise FeatureError(f"{name}: cylindrical face must run print-up (vertical axis)")
        normal = None
    else:
        raise FeatureError(f"{name}: target face must be planar or a vertical cylinder, got {target.geom_type.name}")
    if normal is not None and normal.Z < -VERTICAL_EPS:
        raise FeatureError(f"{name}: texture on a downward face would hang in the air; reorient the part")
    return target


def _is_wall(normal):
    """Not facing up: flanks here need the self-supporting taper."""
    return normal.Z < math.cos(math.radians(slope_deg()))


def _check_depth(name, depth, width):
    """depth within texture bounds, and no deeper than a self-supporting flank over width/2 allows."""
    r = texture_rules()
    _bounded(name, "depth", depth, r["min_depth"], r["max_depth"])
    flank_limit = width / 2 * r["flank_rate"]
    if depth > flank_limit + 1e-9:
        raise FeatureError(f"{name}: depth {depth} exceeds {flank_limit:.2f}, the most a "
                           f"{width:.2f} mm groove allows with self-supporting flanks")
    return depth


def _check_pitch(name, pitch):
    r = texture_rules()
    if pitch < r["min_pitch"]:
        raise FeatureError(f"{name}: pitch {pitch} is below {r['min_pitch']:.2f} mm, two lines of the "
                           f"{rules()['nozzle']} mm nozzle (minimum feature {r['min_feature']} mm)")
    return pitch


def _cylinder_frame(face):
    """(axis point at z=0, radius, z0, z1) of a vertical cylindrical face.

    The z range comes from the face's edges: its bounding box can be loose by a chamfer.
    """
    axis = face.axis_of_rotation if hasattr(face, "axis_of_rotation") else None
    centre = Vector(axis.position.X, axis.position.Y, 0) if axis is not None else face.center()
    zs = [p.Z for e in face.edges() for p in e.positions([0.0, 0.25, 0.5, 0.75, 1.0])]
    return centre, face.radius, min(zs), max(zs)


def _face_uv(face, origin, u, v):
    pts = [Vector(*p) for p in face.outer_wire().positions(np.linspace(0, 1, 129).tolist())]
    return [((p - origin).dot(u), (p - origin).dot(v)) for p in pts]


def _mesh_spec(kind, face, **params):
    """A JSON-ready description of a mesh texture region and its pattern."""
    spec = {"kind": kind, **params}
    if face.geom_type == GeomType.PLANE:
        origin, u, v, normal = _face_frame(face)
        spec.update(surface="plane", origin=tuple(origin), u=tuple(u), v=tuple(v), normal=tuple(normal),
                    outline=_face_uv(face, origin, u, v))
    else:
        centre, radius, z0, z1 = _cylinder_frame(face)
        spec.update(surface="cylinder", centre=tuple(centre), radius=radius, z0=z0, z1=z1)
    c = face.center()
    spec["anchor"] = (c.X, c.Y, c.Z)
    return spec


def _defer_to_mesh(name, shape, target, params, derived, spec, allow_supports, notes=()):
    _MESH_TEXTURES.append(spec)
    derived = {**derived, "mode": {"value": "mesh", "source": "pitch under brep_min_pitch or "
                                   "feature count over texture_rules.brep_max_features"}}
    proposal = _finish(name, shape, shape, _describe(target), params, derived, allow_supports,
                       notes=[*notes, "fine texture: applied to the exported STL, the STEP stays smooth",
                              "cheaper alternative: the slicer's fuzzy skin on this face"])
    proposal.shape = shape
    proposal.mesh_texture = spec
    return proposal


def _brep(derived, source="pitch >= brep_min_pitch and feature count within brep_max_features"):
    return {**derived, "mode": {"value": "brep", "source": source}}


# ---------------------------------------------------------------- patterns


def pattern(shape, face, tool, points, cut=False, allow_supports=False):
    """Place `tool` at each point of a layout on a planar face; add it, or cut it with cut=True.

    `tool` is modelled at the origin with +Z as the face's outward normal (a boss stands on
    z=0; a cutter hangs below z=0 or straddles it). `points` are (u, v) offsets from the face
    centre in its frame (u horizontal, v toward print-up), from linear/grid/circular_pattern,
    or Locations from path_pattern placed as given. Instances must leave a web of at least
    min_wall() between them and sit wholly on the face.
    """
    name = "pattern"
    target = select_face(shape, face)
    placed = []
    if points and isinstance(points[0], Location):
        placed = [loc * tool for loc in points]
        where = "path"
    else:
        if target.geom_type != GeomType.PLANE:
            raise FeatureError(f"{name}: a (u, v) layout needs a planar face")
        origin, u, _, normal = _face_frame(target)
        plane = Plane(origin=origin, x_dir=u, z_dir=normal)
        # the tool's section through the face plane must lie on the face
        slab = Plane(origin=origin, x_dir=u, z_dir=normal) * Box(1e4, 1e4, 2 * PLANAR_TOL)
        for pu, pv in points:
            at = plane.from_local_coords((pu, pv, 0))
            loc = Plane(origin=at, x_dir=u, z_dir=normal).location
            footprint = loc * tool
            contact = footprint & slab
            if contact.volume <= 0 or (contact - extrude(target, amount=PLANAR_TOL, both=True)).volume \
                    > FOOTPRINT_SHARE * contact.volume:
                raise FeatureError(f"{name}: instance at ({pu:.2f}, {pv:.2f}) runs off the face")
            placed.append(footprint)
        where = _describe(target)
    if not placed:
        raise FeatureError(f"{name}: empty layout")
    web = min_wall()
    centres = [p.center() for p in placed]
    reach = max(p.bounding_box().diagonal for p in placed)
    closest = math.inf
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            if (centres[i] - centres[j]).length < reach + web:
                closest = min(closest, placed[i].distance_to(placed[j]))
    if closest < web:
        raise FeatureError(f"{name}: instances {closest:.2f} mm apart leave a web under min_wall() "
                           f"({web} mm); increase spacing")
    tools = placed[0].fuse(*placed[1:]) if len(placed) > 1 else placed[0]
    result = shape - tools if cut else shape + tools
    derived = {"instances": {"value": len(placed), "source": "layout points"},
               "closest_web": {"value": None if closest == math.inf else closest,
                               "source": "min distance between instances; >= min_wall()"}}
    return _finish(name, shape, result, where, {"count": len(placed), "cut": cut}, derived, allow_supports)


# ---------------------------------------------------------------- grooves: knurl, diamond, ribbing
#
# A groove is a trapezoid across its run: a floor `floor` wide (0 = a V) and two flanks that
# climb `depth` over depth / flank_rate each. Its mouth is floor + 2 * depth / flank_rate wide,
# and the land left between grooves (the ridge or rib) is pitch - mouth >= min_feature.


def _groove_bounds(name, pitch, depth, angle, floor):
    """Check a groove family; returns the mouth width."""
    tr = texture_rules()
    _check_pitch(name, pitch)
    _bounded(name, "angle", angle, -90.0, 90.0)
    if floor < 0:
        raise FeatureError(f"{name}: groove floor {floor:.2f} < 0; the rib is too wide for this pitch and depth")
    if 0 < floor < tr["min_feature"]:
        raise FeatureError(f"{name}: groove floor {floor:.2f} is below the {tr['min_feature']} mm nozzle line")
    _check_depth(name, depth, pitch - tr["min_feature"] - floor)
    return floor + 2 * depth / tr["flank_rate"]


def _profile(s, depth, floor, run, rise):
    """One groove centred at s: mouth (run on by `rise` above the surface), flank, floor, flank."""
    climb = run * (1 + rise / depth)           # horizontal run of the flank from floor to y = rise
    pts = [(s - floor / 2 - climb, rise), (s - floor / 2, -depth)]
    if floor > 0:
        pts.append((s + floor / 2, -depth))
    return pts + [(s + floor / 2 + climb, rise)]


def _comb(plane, pitch, depth, floor, span, length, rise):
    """Grooves every `pitch` across `span`, extruded `length` along the plane normal.

    plane: x across the grooves, y along the face normal (y=0 the surface, y<0 into the part).
    The flanks run on above the surface by `rise`, then a strip joins them in the air.
    """
    run = depth / texture_rules()["flank_rate"]
    n = int(math.ceil(span / pitch)) + 1
    pts = [(-(n + 1) * pitch, 2 * rise)]
    for i in range(-n, n + 1):
        pts += _profile(i * pitch, depth, floor, run, rise)
    pts.append(((n + 1) * pitch, 2 * rise))
    return extrude(plane * Polygon(*pts, align=None), amount=length / 2, both=True)


def _grooves_planar(shape, target, pitch, depth, floor, angles):
    origin, u, v, normal = _face_frame(target)
    span = target.bounding_box().diagonal
    rise = depth / 2
    cutter = None
    for a in angles:
        r = math.radians(a)
        along = v * math.cos(r) + u * math.sin(r)        # groove direction in the face
        across = normal.cross(along).normalized()       # so the plane's y is the face normal
        comb = _comb(Plane(origin=origin, x_dir=across, z_dir=along), pitch, depth, floor, span, 2 * span, rise)
        cutter = comb if cutter is None else cutter + comb
    region = extrude(target, amount=depth + rise * 3, dir=-normal) + extrude(target, amount=rise * 3)
    return shape - (cutter & region)


def _star(radius, count, depth, floor, rise):
    """Cross-section of a cylinder with `count` grooves, lands outside the surface.

    Built in the unrolled (arc length, radial) frame and wrapped, so a groove has the same
    profile as on a flat face.
    """
    run = depth / texture_rules()["flank_rate"]
    pitch = 2 * math.pi * radius / count
    outer = (radius + 2 * rise) / math.cos(math.pi / count)
    pts = []
    for i in range(count):
        for s, y in _profile(i * pitch, depth, floor, run, rise):
            a, r = s / radius, radius + y
            pts.append((r * math.cos(a), r * math.sin(a)))
        a = (i + 0.5) * pitch / radius
        pts.append((outer * math.cos(a), outer * math.sin(a)))
    return Polygon(*pts, align=None).faces()[0]


def _grooves_cylinder(shape, target, count, depth, floor, angles):
    centre, radius, z0, z1 = _cylinder_frame(target)
    rise = depth / 2
    margin = depth
    height = z1 - z0 + 2 * margin
    keep = None
    for a in angles:
        twist = math.degrees(height * math.tan(math.radians(a)) / radius)
        star = Pos(centre.X, centre.Y, z0 - margin) * _star(radius, count, depth, floor, rise)
        if abs(twist) < 1e-9:   # straight: extrude_linear_with_rotation divides by the twist
            prism = extrude(star, amount=height)
        else:
            prism = Solid.extrude_linear_with_rotation(star, (centre.X, centre.Y, 0), (0, 0, height), twist)
        keep = prism if keep is None else keep & prism
    up = (Align.CENTER, Align.CENTER, Align.MIN)
    inner = radius - depth - margin
    tube = Pos(centre.X, centre.Y, z0) * (Cylinder(radius + 3 * rise, z1 - z0, align=up)
                                          - Cylinder(inner, z1 - z0, align=up))
    # Run-out: the grooves end under a cone that leaves the grip face at its top rim and slopes
    # self_supporting_deg from vertical, so a groove ending below more material (a crown
    # fillet, a flange) has a printable roof instead of a flat ceiling.
    rate = texture_rules()["flank_rate"]
    rise_to = radius + 3 * rise
    runout = Pos(centre.X, centre.Y, z1 - (radius - inner) / rate) * Cone(
        inner, rise_to, (rise_to - inner) / rate, align=up)
    return shape - (tube - keep - runout)


def _grooved(name, shape, face, pitch, depth, angles, floor, allow_supports, extra=None):
    target = _target(name, shape, face)
    mouth = _groove_bounds(name, pitch, depth, max(angles, key=abs), floor)
    tr = texture_rules()
    params = {"pitch": pitch, "depth": depth, "angle": angles[0], **(extra or {})}
    derived = {"flank_rate": {"value": tr["flank_rate"], "source": "tan(print_rules.self_supporting_deg)"},
               "groove_mouth": {"value": mouth, "source": "floor + 2 * depth / flank_rate"},
               "groove_floor": {"value": floor, "source": "pitch - rib - flanks (0 = V groove)"}}
    if target.geom_type == GeomType.CYLINDER:
        _, radius, _, _ = _cylinder_frame(target)
        lay = 2 * math.pi * radius * math.cos(math.radians(angles[0]))
        count = max(3, round(lay / pitch))
        wrapped = lay / count
        _check_depth(name, depth, wrapped - tr["min_feature"] - floor)
        derived.update(grooves_per_hand={"value": count, "source": "round(circumference * cos(angle) / pitch)"},
                       pitch_wrapped={"value": wrapped, "source": "pitch adjusted to close the circle"})
        features = count * len(angles)
        pitch_used = wrapped
    else:
        features = int(target.bounding_box().diagonal / pitch) * len(angles)
        derived["grooves"] = {"value": features, "source": "face diagonal / pitch per direction"}
        pitch_used = pitch
    if pitch_used < tr["brep_min_pitch"] or features > tr["brep_max_features"]:
        spec = _mesh_spec(name, target, pitch=pitch_used, depth=depth, angles=list(angles), floor=floor)
        return _defer_to_mesh(name, shape, target, params, derived, spec, allow_supports)
    if target.geom_type == GeomType.CYLINDER:
        result = _grooves_cylinder(shape, target, count, depth, floor, angles)
    else:
        result = _grooves_planar(shape, target, pitch, depth, floor, angles)
    return _finish(name, shape, result, _describe(target), params, _brep(derived), allow_supports)


def knurl(shape, face, pitch, depth=None, angle=0.0, allow_supports=False):
    """Straight knurl: V grooves `pitch` apart, running `angle` deg from print-up.

    The FDM-friendly knurl: at angle 0 on a wall every flank faces sideways, so it adds no
    downward area at all. A non-zero angle makes a helical (cylinder) or slanted knurl.

    Params:
      face:  a planar face (not downward) or a vertical cylindrical face (Face or point).
      pitch: groove spacing, measured across the grooves; >= texture_rules min_pitch
             (two nozzle lines). Below brep_min_pitch the knurl goes to the export mesh.
      depth: groove depth, min_depth .. max_depth and <= the flank limit for the pitch
             (the ridge left between grooves keeps one nozzle line). Default: half that limit.
      angle: -90 .. 90. Any angle prints on a wall: the flanks rise at the self-supporting
             slope across the groove, so even a horizontal groove's roof stands
             self_supporting_deg from vertical.
    """
    depth = _default_depth(pitch, depth)
    return _grooved("knurl", shape, face, pitch, depth, (angle,), 0.0, allow_supports)


def diamond_knurl(shape, face, pitch, depth=None, angle=30.0, allow_supports=False):
    """Diamond knurl: two V-groove sets at +-angle from print-up. Bounds as knurl.

    Every flank is self-supporting, but half of them face partly down: on a short part with
    a small footprint that downward area can exceed the harness's brief-wording overhang
    share. A straight knurl does not; prefer it where the grip allows.
    """
    depth = _default_depth(pitch, depth)
    return _grooved("diamond_knurl", shape, face, pitch, depth, (angle, -angle), 0.0, allow_supports)


def ribbing(shape, face, pitch, depth=None, rib=None, angle=0.0, allow_supports=False):
    """Flat-floored grooves leaving ribs `rib` wide, `pitch` apart, `angle` from print-up.

    Params:
      rib:   the rib (land) width, >= min_feature; default half the pitch.
      depth: as knurl; the floor (pitch - rib - flanks) must be 0 or >= min_feature.
    """
    depth = _default_depth(pitch, depth)
    rib = pitch / 2 if rib is None else rib
    if rib < texture_rules()["min_feature"]:
        raise FeatureError(f"ribbing: rib {rib} is below the {texture_rules()['min_feature']} mm nozzle line")
    floor = pitch - rib - 2 * depth / texture_rules()["flank_rate"]
    return _grooved("ribbing", shape, face, pitch, depth, (angle,), floor, allow_supports, {"rib": rib})


def _default_depth(pitch, depth):
    if depth is not None:
        return depth
    tr = texture_rules()
    return max(tr["min_depth"], min(tr["max_depth"], (pitch - tr["min_feature"]) / 4 * tr["flank_rate"]))


# ---------------------------------------------------------------- outlines: hex, text, logos


def _slant(normal):
    """Print-up shift per mm of depth that keeps roofs and raised undersides self-supporting.

    Zero on an upward face. On a wall, 1 / flank_rate: a roof that drops this much per mm
    into the face stands self_supporting_deg from vertical.
    """
    return 1 / texture_rules()["flank_rate"] if _is_wall(normal) else 0.0


def _slanted(sketch, depth, slant, raised):
    """The cut (or boss) for `sketch` (local XY, +Y print-up, +Z out of the face), `depth` deep.

    On a wall it is a sheared extrusion: the whole outline moves `slant` mm toward the
    surface's downhill side per mm of depth (an engraving drops as it goes in, a raised
    glyph climbs as it comes out). Every face of a sheared prism is parallel to the shear
    direction, so no face points nearer straight down than the shear allows (the
    self-supporting slope), whatever the outline: roofs and undersides print, and a thin
    horizontal stroke keeps its full depth. The visible outline at the face is exact; an
    engraving's floor runs on under the surface by up to slant * depth.
    (Intersecting a straight and a sheared prism instead leaves flat roof slivers wherever
    the shift slides along a slanted edge.) The solid also reaches `depth` back past the
    surface, so it is not coplanar with the face.
    """
    sign = 1 if raised else -1
    direction = Vector(0, sign * slant, sign)
    body = extrude(sketch, amount=depth * direction.length, dir=direction)
    return body + extrude(sketch, amount=depth, dir=(0, 0, -sign))


def _sunk(shape, target, sketch, depth, raised, plane):
    tool = plane.location * _slanted(sketch, depth, _slant(target.normal_at()), raised)
    return shape + tool if raised else shape - tool


def _check_strokes(name, sketch):
    """Every glyph/cell stroke must hold one nozzle line."""
    r = texture_rules()
    for glyph in sketch.faces():
        try:
            area = sum(f.area for f in offset(glyph, amount=-r["min_feature"] / 2).faces())
        except Exception:   # OCC refuses an offset that consumes the face
            area = 0.0
        if area <= 0:
            raise FeatureError(f"{name}: a stroke is narrower than the {r['min_feature']} mm nozzle "
                               f"line; enlarge it")


def emboss_outline(shape, face, outline, depth, raised=True, at=(0.0, 0.0), allow_supports=False):
    """Raise (or engrave, raised=False) a 2D outline - a logo - on a planar face.

    Params:
      outline: a build123d Sketch/Face in its own XY, placed with its origin at `at`
               (u, v offset from the face centre; v toward print-up).
      depth:   min_depth .. max_depth. On a wall the roof (engraved) or underside (raised)
               slopes self_supporting_deg from vertical, so it prints without support.
    """
    return _emboss("emboss_outline", shape, face, outline, depth, raised, at, allow_supports, {})


def emboss_text(shape, face, text, size, depth, raised=True, font="Arial", at=(0.0, 0.0),
                allow_supports=False):
    """Raised or engraved text on a planar face. Every stroke must hold a nozzle line."""
    _bounded("emboss_text", "size", size, texture_rules()["min_feature"], 500.0)
    sketch = Text(text, font_size=size, font=font)
    return _emboss("emboss_text", shape, face, sketch, depth, raised, at, allow_supports,
                   {"text": text, "size": size, "font": font})


def _emboss(name, shape, face, outline, depth, raised, at, allow_supports, extra):
    r = texture_rules()
    _bounded(name, "depth", depth, r["min_depth"], r["max_depth"])
    target = _target(name, shape, face)
    if target.geom_type != GeomType.PLANE:
        raise FeatureError(f"{name}: needs a planar face")
    normal = target.normal_at()
    _check_strokes(name, outline)
    origin, u, v, _ = _face_frame(target)
    plane = Plane(origin=origin + u * at[0] + v * at[1], x_dir=u, z_dir=normal)
    if not _inside_face(target, plane * outline):
        raise FeatureError(f"{name}: outline runs off the face")
    result = _sunk(shape, target, outline, depth, raised, plane)
    derived = {"slant": {"value": _slant(normal), "source": "1 / flank_rate on a wall, else 0"},
               "min_stroke": {"value": r["min_feature"], "source": "one nozzle line"}}
    params = {**extra, "depth": depth, "raised": raised, "at": list(at)}
    return _finish(name, shape, result, _describe(target), params, _brep(derived, "outline geometry"),
                   allow_supports)


def hex_texture(shape, face, cell, depth, web=None, allow_supports=False):
    """Hexagonal pockets across a planar face, `web` apart; whole cells only.

    Params:
      cell:  hex size across flats, >= min_pitch.
      depth: min_depth .. max_depth; on a wall each pocket roof slopes self-supporting.
      web:   material between cells, >= min_feature (one nozzle line). Default min_wall().
    Below brep_min_pitch, or past brep_max_features cells, the texture goes to the export mesh.
    """
    name = "hex_texture"
    r = texture_rules()
    web = min_wall() if web is None else web
    if web < r["min_feature"]:
        raise FeatureError(f"{name}: web {web} is below the {r['min_feature']} mm nozzle line")
    _check_pitch(name, cell)
    _bounded(name, "depth", depth, r["min_depth"], r["max_depth"])
    target = _target(name, shape, face)
    if target.geom_type != GeomType.PLANE:
        raise FeatureError(f"{name}: needs a planar face")
    normal = target.normal_at()
    params = {"cell": cell, "depth": depth, "web": web}
    across = cell - web
    if across < r["min_feature"]:
        raise FeatureError(f"{name}: a {across:.2f} mm pocket is narrower than the nozzle line; "
                           f"increase cell or reduce web")
    if cell < r["brep_min_pitch"]:
        spec = _mesh_spec(name, target, pitch=cell, depth=depth, web=web)
        return _defer_to_mesh(name, shape, target, params, {}, spec, allow_supports)
    origin, u, v, _ = _face_frame(target)
    uv = _face_uv(target, origin, u, v)
    reach_u = max(abs(p[0]) for p in uv)
    reach_v = max(abs(p[1]) for p in uv)
    # The same lattice as the mesh texture (_hex_depth): rows cell*sqrt(3)/2 apart about the
    # face centre, odd rows shifted half a cell; pointy-top cells, so their flats run print-up.
    row = cell * math.sqrt(3) / 2
    nu, nv = int(reach_u / cell) + 1, int(reach_v / row) + 1
    centres = [(i * cell + (cell / 2 if j % 2 else 0), j * row)
               for j in range(-nv, nv + 1) for i in range(-nu, nu + 1)]
    plane = Plane(origin=origin, x_dir=u, z_dir=normal)
    inner = offset(target, amount=-web / 2)
    hexagon = RegularPolygon(across / math.sqrt(3), 6, major_radius=True, rotation=90)
    local = [Pos(cu, cv) * hexagon for cu, cv in centres
             if abs(cu) <= reach_u and abs(cv) <= reach_v]
    local = [h for h in local if _inside_face(inner, plane * h)]
    if not local:
        raise FeatureError(f"{name}: no whole {cell} mm cell fits inside the face")
    derived = {"cells": {"value": len(local), "source": "whole cells inside face - web/2"}}
    if len(local) > r["brep_max_features"]:
        spec = _mesh_spec(name, target, pitch=cell, depth=depth, web=web)
        return _defer_to_mesh(name, shape, target, params, derived, spec, allow_supports)
    result = _sunk(shape, target, Sketch() + local, depth, False, plane)
    derived["slant"] = {"value": _slant(normal), "source": "1 / flank_rate on a wall, else 0"}
    return _finish(name, shape, result, _describe(target), params, _brep(derived), allow_supports)


# ---------------------------------------------------------------- mesh textures (fine)


def _groove_depth(s, pitch, depth, rate, floor=0.0):
    """Groove displacement for perpendicular coordinate s (mm): grooves centred on s = k*pitch."""
    d = np.abs(s - np.round(s / pitch) * pitch) - floor / 2
    return np.clip(depth - np.maximum(d, 0) * rate, 0.0, depth)


def _hex_depth(u, v, pitch, depth, web, rate):
    """Displacement for hex pockets of across-flats `pitch`; a web of `web` between them."""
    # nearest hex centre on a pointy-side lattice (rows pitch*sqrt(3)/2 apart, odd rows shifted)
    row_h = pitch * math.sqrt(3) / 2
    best = np.full(u.shape, np.inf)
    j0 = np.floor(v / row_h)
    for dj in (-1, 0, 1, 2):
        j = j0 + dj
        shift = np.where(np.mod(j, 2) == 1, pitch / 2, 0.0)
        i = np.round((u - shift) / pitch)
        cu, cv = i * pitch + shift, j * row_h
        du, dv = u - cu, v - cv
        # hex distance (flat-to-flat along u): max of three projections
        h = np.maximum(np.abs(du), np.abs(du) / 2 + np.abs(dv) * math.sqrt(3) / 2)
        best = np.minimum(best, h)
    inside = pitch / 2 - web / 2 - best          # distance from the pocket rim, + inside
    return np.clip(inside * rate, 0.0, depth)


def _pattern_depth(spec, s_u, s_v, rate):
    if spec["kind"] == "hex_texture":
        return _hex_depth(s_u, s_v, spec["pitch"], spec["depth"], spec["web"], rate)
    disp = np.zeros_like(s_u)
    for a in spec["angles"]:
        r = math.radians(a)
        s = s_u * math.cos(r) - s_v * math.sin(r)
        disp = np.maximum(disp, _groove_depth(s, spec["pitch"], spec["depth"], rate, spec.get("floor", 0.0)))
    return disp


def _polygon_edge_distance(points, poly):
    a = np.asarray(poly)
    b = np.roll(a, -1, axis=0)
    best = np.full(len(points), np.inf)
    for p0, p1 in zip(a, b):
        seg = p1 - p0
        length2 = seg.dot(seg)
        if length2 == 0:
            continue
        t = np.clip(((points - p0) @ seg) / length2, 0, 1)
        nearest = p0 + t[:, None] * seg
        best = np.minimum(best, np.linalg.norm(points - nearest, axis=1))
    return best


def _displace(spec, verts):
    """Per-vertex inward displacement vectors for the vertices on the texture's surface."""
    from matplotlib.path import Path as _Path
    rate = math.tan(math.radians(slope_deg()))
    out = np.zeros_like(verts)
    if spec["surface"] == "plane":
        o, u, v, n = (np.array(spec[k]) for k in ("origin", "u", "v", "normal"))
        rel = verts - o
        on = np.abs(rel @ n) < PLANAR_TOL
        uv = np.stack([rel @ u, rel @ v], axis=1)
        poly = np.array(spec["outline"])
        on &= _Path(poly).contains_points(uv, radius=-PLANAR_TOL)
        if not on.any():
            return out
        disp = _pattern_depth(spec, uv[on, 0], uv[on, 1], rate)
        disp = np.minimum(disp, _polygon_edge_distance(uv[on], poly) * rate)   # ramp to 0 at the rim
        out[on] = -disp[:, None] * n
        return out
    c, radius = np.array(spec["centre"]), spec["radius"]
    rel = verts - c
    rho = np.hypot(rel[:, 0], rel[:, 1])
    z = verts[:, 2]
    # rim rings stay put (their texture ramps to zero): projecting them would collapse the
    # neighbouring cap triangles that also lie within CHORD_TOL of the radius
    on = (np.abs(rho - radius) < CHORD_TOL) & (z > spec["z0"] + PLANAR_TOL) & (z < spec["z1"] - PLANAR_TOL)
    if not on.any():
        return out
    theta = np.arctan2(rel[on, 1], rel[on, 0])
    s_u, s_v = theta * radius, z[on] - spec["z0"]
    disp = _pattern_depth(spec, s_u, s_v, rate)
    disp = np.minimum(disp, np.minimum(z[on] - spec["z0"], spec["z1"] - z[on]).clip(0) * rate)
    radial = np.zeros((on.sum(), 3))
    radial[:, 0], radial[:, 1] = rel[on, 0] / rho[on], rel[on, 1] / rho[on]
    # move onto the true radius minus the texture, which also lifts facet-interior vertices
    # off the export chord so a refined facet does not fold against its displaced edges
    out[on] = ((radius - disp) - rho[on])[:, None] * radial
    return out


def apply_mesh_textures(stl_path, specs):
    """Displace an exported STL in place for each fine texture spec; returns the volume change.

    The whole mesh is refined to pitch / mesh_samples_per_pitch, the vertices on each
    textured face are moved (a vertex-only warp keeps the mesh manifold), and the result is
    simplified back within SIMPLIFY_TOL, which collapses everything the texture did not touch.
    (Refining only a slab round the face and rejoining it fails where the seam crosses a
    curved surface: the coarse and refined facets overlap and reload as non-manifold edges.)
    """
    import manifold3d
    import trimesh
    if not specs:
        return 0.0
    mesh = trimesh.load(str(stl_path))
    solid = manifold3d.Manifold(manifold3d.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                                                tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))
    before = solid.volume()
    samples = texture_rules()["mesh_samples_per_pitch"]
    solid = solid.refine_to_length(min(spec["pitch"] for spec in specs) / samples)

    def warp(verts):
        verts = np.asarray(verts, dtype=float)
        return verts + sum(_displace(spec, verts) for spec in specs)

    solid = solid.warp_batch(warp).simplify(SIMPLIFY_TOL)
    out = solid.to_mesh()
    textured = trimesh.Trimesh(np.asarray(out.vert_properties)[:, :3], np.asarray(out.tri_verts), process=False)
    textured.export(str(stl_path))
    return float(solid.volume() - before)


def mesh_textures_for(shape, specs):
    """The declared specs whose face anchor lies on this part's surface."""
    return [s for s in specs if shape.distance_to(Vector(*s["anchor"])) < PLANAR_TOL * 10]


TEXTURES = {"knurl": knurl, "diamond_knurl": diamond_knurl, "ribbing": ribbing, "hex_texture": hex_texture,
            "emboss_text": emboss_text, "emboss_outline": emboss_outline, "pattern": pattern}

FEATURES.update(TEXTURES)
