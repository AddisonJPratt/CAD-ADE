"""Patterns and ingrained surface textures on a selected face (issue #52).

Patterns place copies of a tool (a hole, a boss, a slot) at locations from one of four
placements: linear, grid, circular, or along a path. `pattern()` cuts or adds every copy and
returns a reviewable FeatureProposal (library/engineering.py). Counts and spacings are meant to
be PARAMS, so the sweep exercises them.

Textures: knurl, diamond, hex, ribbing, and embossed/engraved text, on a face picked by
`pick_face` (by facing, kind, and optionally the named feature it lies on). Every texture has
a feature width (the narrowest ridge, groove, gap or stroke) and a depth, bounded by the
print rules in standard_parts.json, never by literals here:

    minimum feature  = nozzle x texture_min_lines            (0.8 mm at a 0.4 mm nozzle)
    minimum depth    = layer_height x texture_min_layers     (0.4 mm at 0.2 mm layers)
    maximum depth    = texture_max_aspect x feature width
    sloped walls     = 90 - self_supporting_deg off the face normal (hex studs)

Coarse versus fine, the trade-off:
- B-rep (knurl, diamond, hex, ribbing, text): real geometry in the STEP, named faces in Studio,
  exact overhang check. Each cell is a boolean tool, so past texture_brep_max_cells the build
  is slow and the STEP heavy; the B-rep functions refuse and `texture()` routes to the mesh.
- Mesh (`mesh_texture`: knurl, diamond, hex, ribbing): a height field displaced into the
  exported STL by the harness (manifold3d refine + warp, still watertight). Cheap at any cell
  count and the only way to put a helical diamond on a cylinder here, but the STEP stays smooth,
  the texture has no named faces, and it is checked only by Gate 3 on the exported mesh. The
  texture fades out over two depths at the face edges so the mesh never folds.
- Cheapest of all: the slicer's fuzzy skin. It roughens every outer wall at print time with no
  geometry at all. Use it when the brief wants grip or a matte look, not a specific pattern.

Print direction: every B-rep texture runs the overhang check of engineering._finish, so a
texture that adds unsupported area is refused unless allow_supports=True (a brief must allow
supports). Knurl and ribbing grooves run along the face's most print-up direction; hex studs
have walls sloped self-supporting; text on a wall usually has letter ceilings and is refused.
All dimensions in mm; Z is print-up.
"""
import math

import numpy as np
from build123d import (Align, GeomType, Location, Plane, Polygon, Pos, Rectangle, Rot, Sketch,
                       Text, Vector, extrude)

from . import features as registry
from .engineering import (FeatureError, VERTICAL_EPS, _bounded, _face_frame, _finish, _inside_face,
                          _planar, rules, slope_deg)

OVERSHOOT = 0.05          # mm, cutters run this far past the surface so no boolean ends coplanar
ON_FEATURE = 1e-3         # mm, a face lies on a named feature when its centre is this close to it
ON_SURFACE = 0.05         # mm, a mesh vertex lies on the textured surface (chord sag at export tolerance)
MAX_COPIES_PAIRWISE = 60  # past this, pattern webs are checked between neighbours only
FACING = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Y": (0, 1, 0), "-Y": (0, -1, 0),
          "+Z": (0, 0, 1), "-Z": (0, 0, -1)}
KINDS = ("knurl", "diamond", "hex", "ribbing", "text")
MESH_KINDS = ("knurl", "diamond", "hex", "ribbing")


# ---------------------------------------------------------------- bounds


def bounds():
    """Texture printability bounds, all derived from standard_parts.json print_rules."""
    r = rules()
    return {"min_feature": r["nozzle"] * r["texture_min_lines"],
            "min_depth": r["layer_height"] * r["texture_min_layers"],
            "max_aspect": r["texture_max_aspect"],
            "brep_max_cells": r["texture_brep_max_cells"],
            "wall_taper_deg": 90.0 - slope_deg(),
            "text_stroke_share": r["text_stroke_share"],
            "nozzle": r["nozzle"], "lines": r["texture_min_lines"]}


def _hex_widths(pitch, depth):
    """Hex studs: base across-flats, gap between studs, and top across-flats after the wall slope."""
    base = pitch * 3 / 4
    taper = math.tan(math.radians(bounds()["wall_taper_deg"]))
    return base, pitch - base, base - 2 * depth * taper


def texture_spec(kind, pitch, depth, representation="brep", **extra):
    """What a texture is, for the record and the gate: its narrowest feature and its depth.

    pitch is the repeat (centre to centre); for text it is the font size.
    """
    if kind not in KINDS:
        raise FeatureError(f"unknown texture {kind!r}; available: {', '.join(KINDS)}")
    if kind == "hex":
        base, gap, top = _hex_widths(pitch, depth)
        width, aspect_width = min(gap, top), gap
    elif kind == "text":
        width = aspect_width = pitch * bounds()["text_stroke_share"]
    else:   # knurl, diamond, ribbing: grooves and lands each half the pitch
        width = aspect_width = pitch / 2
    return {"kind": kind, "pitch": float(pitch), "depth": float(depth), "feature_width": width,
            "aspect_width": aspect_width, "representation": representation, **extra}


def texture_problems(spec):
    """Why a texture would not print on this printer, or [] (also Gate 3's texture check)."""
    b = bounds()
    kind, width, depth = spec["kind"], spec["feature_width"], spec["depth"]
    problems = []
    if width < b["min_feature"] - 1e-9:
        problems.append(f"{kind}: narrowest feature {width:.2f} mm is below the {b['min_feature']:.2f} mm "
                        f"minimum feature ({b['lines']} lines of a {b['nozzle']} mm nozzle)")
    if depth < b["min_depth"] - 1e-9:
        problems.append(f"{kind}: depth {depth:.2f} mm is below the {b['min_depth']:.2f} mm minimum relief")
    limit = b["max_aspect"] * spec.get("aspect_width", width)
    if depth > limit + 1e-9:
        problems.append(f"{kind}: depth {depth:.2f} mm is over {limit:.2f} mm "
                        f"({b['max_aspect']} x its {spec.get('aspect_width', width):.2f} mm feature width)")
    measured = spec.get("depth_measured")
    if spec.get("representation") == "mesh" and measured is not None and measured < depth / 2:
        problems.append(f"{kind}: mesh texture not applied (measured depth {measured:.2f} of {depth:.2f} mm)")
    return problems


def texture_ranges(kind):
    """(default, min, max) for pitch and depth: what an agent writes into PARAMS for a texture.

    Derived by search from the print rules, so every corner of the box is printable and a
    sweep over the two PARAMS never samples a texture the gate would refuse.
    """
    if kind == "text":
        raise FeatureError("text is sized by its font size, not a pitch")
    b = bounds()
    step = b["nozzle"] / 4
    depth_lo = b["min_depth"]
    depth_hi = 2 * depth_lo
    pitch = b["min_feature"]
    while any(texture_problems(texture_spec(kind, pitch, d)) for d in (depth_lo, depth_hi)):
        pitch += step
        if pitch > 100 * b["min_feature"]:
            raise FeatureError(f"{kind}: no printable pitch for these print rules")
    pitch = round(math.ceil(pitch / step - 1e-9) * step, 3)
    snap = lambda x: round(math.ceil(x / step - 1e-9) * step, 3)
    return {"pitch": (snap(pitch * 5 / 4), pitch, snap(pitch * 5 / 2)),
            "depth": (snap((depth_lo + depth_hi) / 2), depth_lo, depth_hi)}


def _check(spec, cells):
    problems = texture_problems(spec)
    if problems:
        raise FeatureError("; ".join(problems))
    if cells > bounds()["brep_max_cells"]:
        raise FeatureError(f"{spec['kind']}: {cells} cells is over the {bounds()['brep_max_cells']} kept as B-rep; "
                           "use mesh_texture (applied to the exported mesh) or a coarser pitch")


# ---------------------------------------------------------------- face picking


def pick_face(shape, facing=None, kind="plane", feature=None):
    """The face a texture goes on, chosen by what it is rather than where it is, so it survives a sweep.

    kind="plane": the planar face facing `facing` ("+X" .. "-Z") farthest along that direction;
                  with feature="name", only faces lying on that named feature (library.feature).
    kind="cylinder": the outermost cylindrical face (largest radius, then largest area).
    """
    faces = list(shape.faces())
    if feature is not None:
        named = [s for name, s in registry.declared_features() if name == feature]
        if not named:
            raise FeatureError(f"no feature named {feature!r}")
        on = named[-1]
        faces = [f for f in faces if min(g.distance_to(f.center()) for g in on.faces()) < ON_FEATURE]
    if kind == "cylinder":
        faces = [f for f in faces if f.geom_type == GeomType.CYLINDER]
        if not faces:
            raise FeatureError("no cylindrical face to texture")
        return max(faces, key=lambda f: (round(f.radius, 6), f.area))
    if kind != "plane":
        raise FeatureError(f"kind must be 'plane' or 'cylinder', got {kind!r}")
    if facing not in FACING:
        raise FeatureError(f"facing must be one of {', '.join(FACING)}, got {facing!r}")
    axis = Vector(*FACING[facing])
    faces = [f for f in faces if f.geom_type == GeomType.PLANE and f.normal_at().dot(axis) > 1 - VERTICAL_EPS]
    if not faces:
        raise FeatureError(f"no planar face facing {facing}" + (f" on {feature!r}" if feature else ""))
    return max(faces, key=lambda f: (round(f.center().dot(axis), 6), f.area))


def _upright_cylinder(feature, face):
    axis = face.axis_of_rotation if hasattr(face, "axis_of_rotation") else None
    direction = axis.direction if axis is not None else None
    if direction is None or abs(abs(direction.Z) - 1) > VERTICAL_EPS:
        raise FeatureError(f"{feature}: the cylinder must stand upright (axis along print-up Z); "
                           "lay the part so the textured cylinder stands, or use a planar face")
    box = face.bounding_box()
    return Vector(axis.position.X, axis.position.Y, 0), face.radius, box.min.Z, box.max.Z


def _uv_extent(face, origin, u, v):
    pts = [e.position_at(t) for e in face.edges() for t in np.linspace(0, 1, 9)]
    us = [(p - origin).dot(u) for p in pts]
    vs = [(p - origin).dot(v) for p in pts]
    return min(us), max(us), min(vs), max(vs)


# ---------------------------------------------------------------- patterns


def _count(count):
    if count != int(count) or count < 1:
        raise FeatureError(f"pattern count must be a whole number >= 1, got {count}")
    return int(count)


def linear_pattern(count, spacing, direction=(1, 0, 0), origin=(0, 0, 0)):
    """`count` locations `spacing` apart along `direction`, centred on `origin`."""
    count = _count(count)
    d = Vector(*direction).normalized()
    start = Vector(*origin) - d * (spacing * (count - 1) / 2)
    return [Location(tuple(start + d * (spacing * i))) for i in range(count)]


def grid_pattern(count_x, count_y, spacing_x, spacing_y, origin=(0, 0, 0)):
    """A count_x by count_y grid in XY, centred on `origin`."""
    xs = linear_pattern(count_x, spacing_x, (1, 0, 0), origin)
    return [Location(tuple(x.position + Vector(0, y.position.Y - origin[1], 0)))
            for y in linear_pattern(count_y, spacing_y, (0, 1, 0), origin) for x in xs]


def circular_pattern(count, radius, sweep_deg=360.0, start_deg=0.0, center=(0, 0, 0)):
    """`count` locations on a circle about Z, each turned to face outward (local +X radial).

    A full turn spaces them 360/count apart; a partial sweep puts copies on both ends.
    """
    count = _count(count)
    full = abs(sweep_deg - 360.0) < 1e-9
    step = sweep_deg / count if full or count == 1 else sweep_deg / (count - 1)
    c = Vector(*center)
    out = []
    for i in range(count):
        a = start_deg + i * step
        out.append(Pos(c.X + radius * math.cos(math.radians(a)), c.Y + radius * math.sin(math.radians(a)), c.Z)
                   * Rot(0, 0, a))
    return out


def path_pattern(path, count):
    """`count` locations evenly along an Edge or Wire, both ends included; local +X along the tangent."""
    count = _count(count)
    out = []
    for i in range(count):
        t = 0.5 if count == 1 else i / (count - 1)
        point, tangent = path.position_at(t), path.tangent_at(t)
        up = Vector(0, 0, 1) if abs(tangent.Z) < 1 - VERTICAL_EPS else Vector(0, 1, 0)
        normal = tangent.cross(up).cross(tangent).normalized()
        out.append(Location(Plane(origin=point, x_dir=tangent, z_dir=normal)))
    return out


def pattern(shape, tool, locations, cut=False, name="pattern", params=(), allow_supports=False):
    """Cut (cut=True) or add a copy of `tool` at every location; returns a FeatureProposal.

    Refused: a copy that misses the part, or a web between two copies thinner than the
    minimum feature (copies may overlap or touch; a sliver between them will not print).
    """
    locations = list(locations)
    if not locations:
        raise FeatureError(f"{name}: no locations (count must be >= 1)")
    copies = [loc * tool for loc in locations]
    for i, c in enumerate(copies):
        if shape.distance_to(c) > ON_FEATURE:
            raise FeatureError(f"{name}: copy {i + 1} of {len(copies)} misses the part")
    min_web = bounds()["min_feature"]
    pairs = ([(i, j) for i in range(len(copies)) for j in range(i + 1, len(copies))]
             if len(copies) <= MAX_COPIES_PAIRWISE else [(i, i + 1) for i in range(len(copies) - 1)])
    for i, j in pairs:
        web = copies[i].distance_to(copies[j])
        if ON_FEATURE < web < min_web:
            raise FeatureError(f"{name}: web of {web:.2f} mm between copies {i + 1} and {j + 1} is below the "
                               f"{min_web:.2f} mm minimum feature; widen the spacing or overlap them")
    tools = copies[0]
    for c in copies[1:]:
        tools = tools + c
    registry.feature(name, tools, params)
    result = shape - tools if cut else shape + tools
    derived = {"copies": {"value": len(copies), "source": "locations"},
               "min_web": {"value": min_web, "source": "print_rules.nozzle x texture_min_lines"}}
    return _finish(name, shape, result, f"{len(copies)} copies", {"cut": cut}, derived, allow_supports)


# ---------------------------------------------------------------- B-rep textures


def _groove(width, depth, length, plane, across):
    """A V-groove prism along the plane's local Y at local x=`across`, apex `depth` below the surface."""
    half = width / 2 * (depth + OVERSHOOT) / depth
    section = Polygon((across - half, OVERSHOOT), (across + half, OVERSHOOT), (across, -depth), align=None)
    # Local y of this section plane is the face normal (z = -y_dir gives y = z x x = normal),
    # so +OVERSHOOT is outside the part and the apex is `depth` into it.
    side = Plane(origin=plane.origin, x_dir=plane.x_dir, z_dir=-plane.y_dir)
    assert abs(side.y_dir.dot(plane.z_dir) - 1) < 1e-9
    return extrude(side * section, amount=length / 2, both=True)


def _slab(face, depth, outward):
    """The face extruded `depth` into (outward=False) or out of the part, overshooting the surface."""
    normal = face.normal_at()
    if outward:
        return Pos(*(normal * -OVERSHOOT)) * extrude(face, amount=depth + 2 * OVERSHOOT, dir=normal)
    return Pos(*(normal * OVERSHOOT)) * extrude(face, amount=depth + 2 * OVERSHOOT, dir=-normal)


def _record(spec, shape, name, tools, params):
    registry.feature(name, tools, params)
    registry.declare_texture(spec, shape)


def _fit(span, pitch, land):
    """Grooves (or ribs) that fit across `span` with at least `land` left at each edge."""
    n = int((span - land - pitch / 2) // pitch) + 1
    return max(n, 0)


def knurl(shape, face, pitch, depth, name="knurl", params=(), allow_supports=False):
    """Straight knurl: V-grooves along the print-up direction of a planar face, or along the axis
    of an upright cylinder. Grooves and lands are each half the pitch.

    Params: pitch, depth bounded by texture_problems (see texture_ranges("knurl")).
    """
    target = face
    spec = texture_spec("knurl", pitch, depth)
    if target.geom_type == GeomType.CYLINDER:
        centre, radius, z0, z1 = _upright_cylinder(name, target)
        n = int(2 * math.pi * radius // pitch)
        actual = 2 * math.pi * radius / n
        spec = texture_spec("knurl", actual, depth)
        _check(spec, n)
        grooves = None
        for i in range(n):
            a = 360.0 * i / n
            plane = Plane(origin=(centre.X + radius * math.cos(math.radians(a)),
                                  centre.Y + radius * math.sin(math.radians(a)), (z0 + z1) / 2),
                          x_dir=(-math.sin(math.radians(a)), math.cos(math.radians(a)), 0),
                          z_dir=(math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
            g = _groove(actual / 2, depth, z1 - z0 + 2 * OVERSHOOT, plane, 0.0)
            grooves = g if grooves is None else grooves + g
        tools = grooves
    else:
        _planar(name, target)
        origin, u, v, normal = _face_frame(target)
        u0, u1, v0, v1 = _uv_extent(target, origin, u, v)
        n = _fit(u1 - u0, pitch, pitch / 2)
        _check(spec, n)
        if n < 1:
            raise FeatureError(f"{name}: face is too narrow for one {pitch} mm groove")
        plane = Plane(origin=origin + u * ((u0 + u1) / 2) + v * ((v0 + v1) / 2), x_dir=u, z_dir=normal)
        grooves = None
        for i in range(n):
            g = _groove(pitch / 2, depth, v1 - v0 + 2 * OVERSHOOT, plane, (i - (n - 1) / 2) * pitch)
            grooves = g if grooves is None else grooves + g
        tools = grooves & _slab(target, depth, outward=False)
    spec["cells"] = n
    result = shape - tools
    proposal = _finish(name, shape, result, f"{target.geom_type.name.lower()} face", {"pitch": pitch, "depth": depth},
                       {"grooves": {"value": n, "source": "whole grooves across the face"},
                        "feature_width": {"value": spec["feature_width"], "source": "pitch / 2"}}, allow_supports)
    _record(spec, proposal.shape, name, tools, params)
    return proposal


def diamond(shape, face, pitch, depth, angle_deg=30.0, name="diamond", params=(), allow_supports=False):
    """Diamond knurl on a planar face: two sets of V-grooves at +/-angle_deg from print-up.

    On a cylinder a diamond knurl is helical: use mesh_texture(..., "diamond", ...).
    angle_deg: 15..60; steeper (smaller) keeps groove flanks off the overhang limit on a wall.
    """
    _bounded(name, "angle_deg", angle_deg, 15.0, 60.0)
    if face.geom_type == GeomType.CYLINDER:
        raise FeatureError(f"{name}: a diamond knurl on a cylinder is helical; use mesh_texture")
    target = _planar(name, face)
    spec = texture_spec("diamond", pitch, depth, angle_deg=angle_deg)
    origin, u, v, normal = _face_frame(target)
    u0, u1, v0, v1 = _uv_extent(target, origin, u, v)
    centre = origin + u * ((u0 + u1) / 2) + v * ((v0 + v1) / 2)
    diagonal = math.hypot(u1 - u0, v1 - v0)
    n = int(diagonal // pitch) + 1
    cells = int((u1 - u0) * (v1 - v0) / pitch ** 2)
    _check(spec, max(cells, 2 * n))
    grooves = None
    for sign in (1, -1):
        a = math.radians(sign * angle_deg)
        along = v * math.cos(a) + u * math.sin(a)
        across = along.cross(normal).normalized()
        plane = Plane(origin=centre, x_dir=across, z_dir=normal)
        for i in range(n):
            g = _groove(pitch / 2, depth, diagonal + 2 * OVERSHOOT, plane, (i - (n - 1) / 2) * pitch)
            grooves = g if grooves is None else grooves + g
    tools = grooves & _slab(target, depth, outward=False)
    spec["cells"] = cells
    proposal = _finish(name, shape, shape - tools, "planar face", {"pitch": pitch, "depth": depth, "angle_deg": angle_deg},
                       {"grooves": {"value": 2 * n, "source": "two sets across the face diagonal"}}, allow_supports)
    _record(spec, proposal.shape, name, tools, params)
    return proposal


def ribbing(shape, face, pitch, depth, name="ribbing", params=(), allow_supports=False):
    """Raised ribs along the print-up direction of a planar face, or along an upright cylinder.
    Ribs and gaps are each half the pitch; ribs are clipped to the face, whole ribs only across it."""
    target = face
    spec = texture_spec("ribbing", pitch, depth)
    if target.geom_type == GeomType.CYLINDER:
        centre, radius, z0, z1 = _upright_cylinder(name, target)
        n = int(2 * math.pi * radius // pitch)
        actual = 2 * math.pi * radius / n
        spec = texture_spec("ribbing", actual, depth)
        _check(spec, n)
        ribs = None
        for i in range(n):
            a = 360.0 * i / n
            rib = Pos(centre.X, centre.Y, z0) * Rot(0, 0, a) * Pos(radius - OVERSHOOT, 0, 0) * extrude(
                Rectangle(depth + OVERSHOOT, actual / 2, align=(Align.MIN, Align.CENTER)), amount=z1 - z0)
            ribs = rib if ribs is None else ribs + rib
        tools = ribs
    else:
        _planar(name, target)
        origin, u, v, normal = _face_frame(target)
        u0, u1, v0, v1 = _uv_extent(target, origin, u, v)
        n = _fit(u1 - u0, pitch, pitch / 2)
        _check(spec, n)
        if n < 1:
            raise FeatureError(f"{name}: face is too narrow for one {pitch} mm rib")
        plane = Plane(origin=origin + u * ((u0 + u1) / 2) + v * ((v0 + v1) / 2) - normal * OVERSHOOT,
                      x_dir=u, z_dir=normal)
        outline = Sketch() + [Pos((i - (n - 1) / 2) * pitch, 0) * Rectangle(pitch / 2, v1 - v0 + 2 * OVERSHOOT)
                              for i in range(n)]
        tools = extrude(plane * outline, amount=depth + OVERSHOOT) & _slab(target, depth, outward=True)
    spec["cells"] = n
    proposal = _finish(name, shape, shape + tools, f"{target.geom_type.name.lower()} face",
                       {"pitch": pitch, "depth": depth}, {"ribs": {"value": n, "source": "whole ribs across the face"}},
                       allow_supports)
    _record(spec, proposal.shape, name, tools, params)
    return proposal


def hex_texture(shape, face, pitch, depth, name="hex", params=(), allow_supports=False):
    """Raised hexagonal studs on a planar face, pointy end toward print-up, walls sloped
    90 - self_supporting_deg off the face normal so no stud wall is an overhang on a wall.
    Whole studs only; studs are 3/4 of the pitch across the flats at their base."""
    target = _planar(name, face)
    spec = texture_spec("hex", pitch, depth)
    base, gap, top = _hex_widths(pitch, depth)
    origin, u, v, normal = _face_frame(target)
    u0, u1, v0, v1 = _uv_extent(target, origin, u, v)
    row = pitch * math.sqrt(3) / 2
    nu, nv = int((u1 - u0 - gap) // pitch) + 1, int((v1 - v0 - gap) // row) + 1
    _check(spec, nu * nv)
    plane = Plane(origin=origin + u * ((u0 + u1) / 2) + v * ((v0 + v1) / 2) - normal * OVERSHOOT, x_dir=u, z_dir=normal)
    corner = base / math.sqrt(3)     # circumradius of a hexagon `base` across the flats
    hexagon = Polygon(*[(corner * math.cos(math.radians(90 + 60 * k)), corner * math.sin(math.radians(90 + 60 * k)))
                        for k in range(6)], align=None)
    margin = gap + corner
    studs = []
    for j in range(nv):
        for i in range(nu + 1):
            x = (i - nu / 2 + (0.5 if j % 2 else 0)) * pitch
            y = (j - (nv - 1) / 2) * row
            if abs(x) > (u1 - u0) / 2 - margin + 1e-9 or abs(y) > (v1 - v0) / 2 - margin + 1e-9:
                continue
            outline = plane * (Pos(x, y) * hexagon)
            if _inside_face(target, Pos(*(normal * OVERSHOOT)) * outline):
                studs.append(outline)
    if not studs:
        raise FeatureError(f"{name}: no whole {pitch} mm stud fits on the face")
    taper = bounds()["wall_taper_deg"]
    tools = None
    for s in studs:
        # Base starts OVERSHOOT under the face; the taper over that overshoot is below a micron.
        stud = extrude(s, amount=depth + OVERSHOOT, taper=taper)
        tools = stud if tools is None else tools + stud
    spec["cells"] = len(studs)
    proposal = _finish(name, shape, shape + tools, "planar face", {"pitch": pitch, "depth": depth},
                       {"studs": {"value": len(studs), "source": "whole studs inside the face"},
                        "top_across_flats": {"value": top, "source": "base - 2 depth tan(90 - self_supporting_deg)"}},
                       allow_supports)
    _record(spec, proposal.shape, name, tools, params)
    return proposal


def text(shape, face, words, size, depth, emboss=True, offset=(0.0, 0.0), name="text", params=(),
         allow_supports=False):
    """Embossed (emboss=True) or engraved text on a planar face, reading along the face's
    horizontal direction with its top toward print-up, centred on the face plus `offset`
    (mm along that horizontal, then along the face's up). size is the font size; its stroke
    (size x text_stroke_share) must reach the minimum feature. The letters must lie wholly on
    the face (clear of holes and edges)."""
    target = _planar(name, face)
    if not isinstance(words, str) or not words.strip():
        raise FeatureError(f"{name}: needs some text")
    spec = texture_spec("text", size, depth, emboss=bool(emboss), text=words)
    _check(spec, 1)
    origin, u, v, normal = _face_frame(target)
    u0, u1, v0, v1 = _uv_extent(target, origin, u, v)
    centre = origin + u * ((u0 + u1) / 2 + offset[0]) + v * ((v0 + v1) / 2 + offset[1])
    letters = Plane(origin=centre, x_dir=u, z_dir=normal) * Text(words, font_size=size)
    if not _inside_face(target, Sketch() + letters.faces()):
        raise FeatureError(f"{name}: {words!r} at {size} mm runs off the face")
    if emboss:
        tools = Pos(*(normal * -OVERSHOOT)) * extrude(letters, amount=depth + OVERSHOOT)
        result = shape + tools
    else:
        tools = Pos(*(normal * OVERSHOOT)) * extrude(letters, amount=depth + OVERSHOOT, dir=-normal)
        result = shape - tools
    proposal = _finish(name, shape, result, "planar face", {"text": words, "size": size, "depth": depth,
                                                            "emboss": bool(emboss)},
                       {"stroke": {"value": spec["feature_width"], "source": "size x print_rules.text_stroke_share"}},
                       allow_supports)
    _record(spec, proposal.shape, name, tools, params)
    return proposal


BREP = {"knurl": knurl, "diamond": diamond, "ribbing": ribbing, "hex": hex_texture}


def texture(shape, face, kind, pitch, depth, representation="auto", **kwargs):
    """Apply a texture by name. representation: "brep", "mesh", or "auto" (B-rep unless the
    texture is over texture_brep_max_cells or is a diamond on a cylinder, then mesh).

    Returns a FeatureProposal; for a mesh texture the shape is unchanged (the harness
    textures the exported STL) and the proposal says so in its notes.
    """
    if kind == "text":
        return text(shape, face, kwargs.pop("words"), pitch, depth, **kwargs)
    if kind not in BREP:
        raise FeatureError(f"unknown texture {kind!r}; available: {', '.join(KINDS)}")
    border = kwargs.pop("border", 0.0)   # mesh only: B-rep textures clip to the face outline
    if representation not in ("auto", "brep", "mesh"):
        raise FeatureError(f"representation must be auto, brep or mesh, got {representation!r}")
    if representation != "mesh":
        try:
            return BREP[kind](shape, face, pitch, depth, **kwargs)
        except FeatureError as err:
            if representation == "brep" or "mesh_texture" not in str(err):
                raise
    allow = kwargs.get("allow_supports", False)
    mesh_texture(shape, face, kind, pitch, depth, angle_deg=kwargs.get("angle_deg", 30.0),
                 border=border)
    return _finish(kind, shape, shape, "mesh texture", {"pitch": pitch, "depth": depth},
                   {"representation": {"value": "mesh", "source": "over texture_brep_max_cells, or helical"}},
                   allow, notes=[f"{kind} is applied to the exported mesh; the STEP stays smooth"])


# ---------------------------------------------------------------- mesh textures


def mesh_texture(shape, face, kind, pitch, depth, angle_deg=30.0, border=0.0, name=None):
    """Record a fine texture to displace into this shape's exported STL; returns the shape unchanged.

    Call it last, on the part build() returns. The face must be planar or an upright cylinder,
    without holes. border (planar faces): a smooth band this wide kept round the face's edges.
    Its bounds are checked by Gate 3 on the exported mesh, where it is applied.
    """
    if kind not in MESH_KINDS:
        raise FeatureError(f"mesh textures: {', '.join(MESH_KINDS)}; got {kind!r}")
    if face.inner_wires():
        raise FeatureError("mesh textures need a face without holes (the displacement would fold at a hole)")
    region = {}
    if face.geom_type == GeomType.CYLINDER:
        centre, radius, z0, z1 = _upright_cylinder(kind, face)
        region = {"surface": "cylinder", "centre": [centre.X, centre.Y], "radius": radius, "z": [z0, z1]}
    else:
        _planar(kind, face)
        origin, u, v, normal = _face_frame(face)
        u0, u1, v0, v1 = _uv_extent(face, origin, u, v)
        if border < 0 or 2 * border >= min(u1 - u0, v1 - v0):
            raise FeatureError(f"{kind}: border {border} leaves no face to texture")
        region = {"surface": "plane", "origin": list(origin), "u": list(u), "v": list(v), "normal": list(normal),
                  "u_range": [u0 + border, u1 - border], "v_range": [v0 + border, v1 - border]}
    spec = texture_spec(kind, pitch, depth, representation="mesh", angle_deg=angle_deg,
                        part=getattr(shape, "label", "") or None, name=name or kind, region=region)
    registry.declare_texture(spec, shape)
    return shape


def _vgroove(x, period):
    """0 on the land, rising linearly to 1 at the groove centre; the groove is half the period."""
    phase = np.mod(x / period, 1.0)
    return np.where(phase < 0.5, 1 - np.abs(phase - 0.25) / 0.25, 0.0)


def _height(kind, s, t, pitch, angle_deg, circumference=None):
    """Height field in [0, 1] (1 = full depth) over surface coordinates s (across) and t (print-up)."""
    if kind == "knurl":
        return _vgroove(s, pitch)
    if kind == "ribbing":   # flat-bottomed grooves with sloped sides
        phase = np.mod(s / pitch, 1.0)
        return np.clip((0.25 - np.abs(phase - 0.25)) / (0.25 / 2), 0, 1) * (phase < 0.5)
    if kind == "diamond":
        a = math.radians(angle_deg)
        p = pitch
        if circumference:   # whole grooves around: the across period along s is p / cos(a)
            p = circumference * math.cos(a) / max(1, round(circumference * math.cos(a) / pitch))
        return np.maximum(_vgroove(s * math.cos(a) - t * math.sin(a), p),
                          _vgroove(s * math.cos(a) + t * math.sin(a), p))
    # hex: studs (height 0) 3/4 of the pitch across the flats, pointy end up; gaps ramp to full depth.
    base, gap, _ = _hex_widths(pitch, 0.0)
    row = pitch * math.sqrt(3) / 2
    best = np.full(s.shape, np.inf)
    for offset_s, offset_t, step_t in ((0.0, 0.0, 2 * row), (pitch / 2, row, 2 * row)):
        ds = np.mod(s - offset_s + pitch / 2, pitch) - pitch / 2
        dt = np.mod(t - offset_t + step_t / 2, step_t) - step_t / 2
        norm = np.maximum(np.abs(ds), (np.abs(ds) + math.sqrt(3) * np.abs(dt)) / 2)
        best = np.minimum(best, norm)
    return np.clip((best - base / 2) / (gap / 2), 0, 1)


def apply_mesh_texture(stl_path, spec):
    """Displace a recorded mesh texture into an STL in place; returns what it did.

    manifold3d refines the whole mesh (edges <= pitch/8) so the result stays watertight, then
    moves the vertices on the textured surface inward by depth x height field, fading to zero
    over two depths at the face's edges.
    """
    import trimesh
    from manifold3d import Manifold, Mesh

    mesh = trimesh.load_mesh(stl_path)
    before = float(mesh.volume)
    solid = Manifold(Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                          tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))
    pitch, depth, kind = spec["pitch"], spec["depth"], spec["kind"]
    region = spec["region"]
    fade = 2 * depth
    moved = {"max": 0.0}

    def warp(points):
        p = np.asarray(points, dtype=np.float64)
        out = p.copy()
        if region["surface"] == "cylinder":
            cx, cy = region["centre"]
            r, (z0, z1) = region["radius"], region["z"]
            dx, dy = p[:, 0] - cx, p[:, 1] - cy
            rho = np.hypot(dx, dy)
            on = (np.abs(rho - r) < ON_SURFACE) & (p[:, 2] >= z0 - ON_SURFACE) & (p[:, 2] <= z1 + ON_SURFACE)
            s = np.arctan2(dy, dx) * r
            t = p[:, 2]
            edge = np.minimum(t - z0, z1 - t)
            h = _height(kind, s, t, pitch, spec.get("angle_deg", 30.0), 2 * math.pi * r)
            disp = np.where(on, depth * h * np.clip(edge / fade, 0, 1), 0.0)
            scale = np.where(rho > 0, disp / np.where(rho > 0, rho, 1), 0)
            out[:, 0] -= dx * scale
            out[:, 1] -= dy * scale
        else:
            o, u, v, n = (np.array(region[k]) for k in ("origin", "u", "v", "normal"))
            rel = p - o
            s, t, w = rel @ u, rel @ v, rel @ n
            (u0, u1), (v0, v1) = region["u_range"], region["v_range"]
            on = (np.abs(w) < ON_SURFACE) & (s >= u0 - ON_SURFACE) & (s <= u1 + ON_SURFACE) \
                & (t >= v0 - ON_SURFACE) & (t <= v1 + ON_SURFACE)
            edge = np.minimum.reduce([s - u0, u1 - s, t - v0, v1 - t])
            h = _height(kind, s - (u0 + u1) / 2, t - (v0 + v1) / 2, pitch, spec.get("angle_deg", 30.0))
            disp = np.where(on, depth * h * np.clip(edge / fade, 0, 1), 0.0)
            out -= np.outer(disp, n)
        moved["max"] = max(moved["max"], float(disp.max()) if len(disp) else 0.0)
        return out.astype(np.float32)

    textured = solid.refine_to_length(pitch / 8).warp_batch(warp)
    result = textured.to_mesh()
    out = trimesh.Trimesh(vertices=np.asarray(result.vert_properties)[:, :3], faces=np.asarray(result.tri_verts),
                          process=True)
    out.export(stl_path)
    after = float(trimesh.load_mesh(stl_path).volume)
    return {"volume_delta_mm3": after - before, "depth_measured": moved["max"], "faces": len(out.faces)}


def on_part(result, name, fn):
    """Apply fn to the part called `name` in a build() result (a shape, list, tuple pairs or dict).

    A single-part result is that part whatever its name. The part keeps its label.
    """
    def apply(part, label):
        part.label = label
        out = fn(part)
        out.label = label
        return out
    if isinstance(result, dict):
        if name not in result:
            raise FeatureError(f"no part named {name!r}; parts: {', '.join(result)}")
        return {k: apply(v, k) if k == name else v for k, v in result.items()}
    if isinstance(result, (list, tuple)):
        out, found = [], False
        for i, item in enumerate(result):
            label, part = item if isinstance(item, tuple) else (getattr(item, "label", "") or f"part{i + 1}", item)
            if label == name:
                part, found = apply(part, label), True
            out.append((label, part) if isinstance(item, tuple) else part)
        if not found:
            raise FeatureError(f"no part named {name!r}")
        return out
    return apply(result, getattr(result, "label", "") or name or "part")
