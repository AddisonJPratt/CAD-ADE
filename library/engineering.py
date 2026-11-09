"""Engineering features applied to a selected face or edge (issue #53).

Every feature is a named function with bounded parameters. It takes a solid and a
target (a build123d Face/Edge, or a point near it: selection by nearest position, see
magic-kernel-pitfalls), and returns a FeatureProposal: the new solid plus a reviewable
record of what was resolved, which sizes came from where, and the print check.

Print check: each feature measures the unsupported downward area (faces within 45 deg of
straight down and not on the bed, the harness's support_risk definition) before and after.
A feature that adds unsupported area raises FeatureError unless allow_supports=True,
which only a brief that permits supports should pass.

Sizes come from the caller's PARAMS or from library/standard_parts.json (inserts,
screws, print_rules); clearances come from its "fits" table, which mirrors CLAUDE.md.
All dimensions in mm; Z is print-up.
"""
import copy
import math
from dataclasses import dataclass, field

import numpy as np
from build123d import (Align, Box, Circle, Cone, Cylinder, Helix, GeomType, Plane, Polygon, Pos, Rectangle,
                       RectangleRounded, Sketch, Solid, Vector, extrude, offset, sweep)

from .features import heatset_boss, standard_parts

STL_TOLERANCE = 0.01      # mm, matches harness/worker.py, so the check sees what the gate sees
STL_ANGULAR = 0.1         # rad
VERTICAL_EPS = math.sin(math.radians(0.5))   # as harness/printability.py
BED_Z_TOL = 0.01                             # mm, as harness/printability.py
FOOTPRINT_REL_TOL = 1e-6                     # boolean noise when testing a footprint lies inside a face


class FeatureError(ValueError):
    """A feature refused: out-of-bounds parameter, bad target, or new unsupported overhang."""


def rules():
    return standard_parts()["print_rules"]


def fits():
    return {k: v for k, v in standard_parts()["fits"].items() if not k.startswith("_")}


def min_wall():
    r = rules()
    return r["nozzle"] * r["min_wall_perimeters"]


def slope_deg():
    return rules()["self_supporting_deg"]


# ---------------------------------------------------------------- proposals


@dataclass
class FeatureProposal:
    """What a feature did, for review before it is accepted into a design."""
    feature: str
    target: str
    params: dict
    derived: dict            # size -> {"value", "source"}
    shape: Solid
    overhang_before_mm2: float
    overhang_after_mm2: float
    volume_delta_mm3: float
    allow_supports: bool = False
    slop_flags: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    mesh_texture: dict = None    # a fine texture applied to the exported STL (library/textures.py)

    @property
    def adds_overhang_mm2(self):
        return self.overhang_after_mm2 - self.overhang_before_mm2

    def to_dict(self):
        """JSON-ready summary (no geometry) for the Studio proposal card."""
        return {"feature": self.feature, "target": self.target, "params": self.params,
                "derived": self.derived, "volume_delta_mm3": round(self.volume_delta_mm3, 3),
                "overhang_before_mm2": round(self.overhang_before_mm2, 3),
                "overhang_after_mm2": round(self.overhang_after_mm2, 3),
                "allow_supports": self.allow_supports, "slop_flags": list(self.slop_flags),
                "notes": list(self.notes), "mesh_texture": self.mesh_texture}


def unsupported_area(shape):
    """Downward area a slicer would support: within 45 deg of straight down, off the bed.

    Same definition as harness support_risk, in mm^2 rather than a share. Area comes from a
    tessellation at the harness's export tolerance, but each triangle on a curved face is
    classified by the true surface normal at its centroid, not its facet normal: thin facets
    where a helical flank meets a trim plane can tilt 30 deg off the real surface.
    """
    # Mesh a deep copy: OCC caches each face's triangulation on the shape, and per-face meshes
    # do not share edge points, so a later STL export of the original would not be watertight.
    work = copy.deepcopy(shape)
    z_min = work.bounding_box().min.Z
    total = 0.0
    for face in work.faces():
        verts, tris = face.tessellate(STL_TOLERANCE, STL_ANGULAR)
        if not tris:
            continue
        v = np.array([tuple(p) for p in verts])
        t = np.array(tris)
        a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        cross = np.cross(b - a, c - a)
        area = np.linalg.norm(cross, axis=1) / 2
        if face.geom_type == GeomType.PLANE:
            nz = np.full(len(t), face.normal_at().Z)
        else:
            nz = np.divide(cross[:, 2], 2 * area, out=np.zeros_like(area), where=area > 0)
            centroids = (a + b + c) / 3
            for i in np.nonzero(nz < -VERTICAL_EPS)[0]:   # only downward facets need the true normal
                nz[i] = face.normal_at(Vector(*centroids[i])).Z
        down = nz < -VERTICAL_EPS
        angle = np.degrees(np.arccos(np.clip(-nz, -1, 1)))
        top = np.maximum(np.maximum(a[:, 2], b[:, 2]), c[:, 2])
        on_bed = down & (angle < 1.0) & (top <= z_min + BED_Z_TOL)
        total += float(area[down & (angle <= 45) & ~on_bed].sum())
    return total


def _single(shape, feature):
    solids = shape.solids() if hasattr(shape, "solids") else [shape]
    if len(solids) != 1:
        raise FeatureError(f"{feature}: result has {len(solids)} solids, expected 1")
    solid = solids[0]
    if not solid.is_valid:
        raise FeatureError(f"{feature}: result is not a valid solid")
    return solid


def _finish(feature, before, after, target, params, derived, allow_supports, slop=(), notes=()):
    after = _single(after, feature)
    after.label = getattr(before, "label", "") or ""
    o_before, o_after = unsupported_area(before), unsupported_area(after)
    proposal = FeatureProposal(feature, target, params, derived, after, o_before, o_after,
                               after.volume - before.volume, allow_supports, list(slop), list(notes))
    if proposal.adds_overhang_mm2 > rules()["overhang_tolerance_mm2"]:
        message = (f"{feature} adds {proposal.adds_overhang_mm2:.2f} mm^2 of unsupported overhang "
                   f"on {target}")
        if not allow_supports:
            raise FeatureError(message + "; reorient, pick another target, or allow supports in the brief")
        proposal.notes.append(message + " (brief allows supports)")
    return proposal


def _bounded(feature, name, value, low, high):
    if not low <= value <= high:
        raise FeatureError(f"{feature}: {name}={value} outside {low:.3g}..{high:.3g}")
    return value


# ---------------------------------------------------------------- selection


def _vec(p):
    return p if isinstance(p, Vector) else Vector(*p)


def _mid(edge):
    """A point on the edge (an arc's center() is off the edge, inside its chord)."""
    return edge.position_at(0.5)


def select_edges(shape, targets):
    """Edges given directly, or the edge nearest each point (selection by expected position)."""
    edges = []
    for target in targets:
        if hasattr(target, "geom_type") and target.__class__.__name__ == "Edge":
            edges.append(target)
            continue
        point = _vec(target)
        edges.append(min(shape.edges(), key=lambda e: e.distance_to(point)))
    unique = []
    for e in edges:
        if not any(e.is_same(u) for u in unique):
            unique.append(e)
    return unique


def select_face(shape, target):
    """A face given directly, or the face nearest a point."""
    if target.__class__.__name__ == "Face":
        return target
    point = _vec(target)
    return min(shape.faces(), key=lambda f: f.distance_to(point))


def _faces_of(shape, edge):
    return [f for f in shape.faces() if any(edge.is_same(e) for e in f.edges())]


def _describe(item):
    c = item.center()
    return f"{item.__class__.__name__.lower()} at ({c.X:.2f}, {c.Y:.2f}, {c.Z:.2f})"


def _planar(feature, face):
    if face.geom_type != GeomType.PLANE:
        raise FeatureError(f"{feature}: target face must be planar, got {face.geom_type.name}")
    return face


def _inside_face(face, footprint):
    """True if the 2D footprint face lies within the target face (both coplanar)."""
    return (footprint - face).area <= FOOTPRINT_REL_TOL * footprint.area


# ---------------------------------------------------------------- features


def edge_break(shape, edges, radius, allow_supports=False):
    """Fillet the selected edges; edges on a downward face get a self-supporting chamfer instead.

    A fillet on an underside edge curls into an unsupported ceiling near the bed. Those
    edges get a chamfer whose face slopes self_supporting_deg from vertical, with its
    horizontal leg equal to `radius`, so the break reads the same size from above.

    Params:
      edges:  Edge objects or points near them.
      radius: min_wall()/2 .. 20 mm; must also be smaller than the adjoining faces allow
              (the kernel refusal is reported as FeatureError).
    """
    name = "edge_break"
    _bounded(name, "radius", radius, min_wall() / 2, 20.0)
    selected = select_edges(shape, edges)
    underside, upper = [], []
    for edge in selected:
        downward = [f for f in _faces_of(shape, edge)
                    if f.geom_type == GeomType.PLANE and f.normal_at(edge.center()).Z < -VERTICAL_EPS]
        (underside if downward else upper).append((edge, downward[0] if downward else None))
    result = shape
    vertical_leg = radius / math.tan(math.radians(slope_deg()))
    try:
        groups = []   # one chamfer call per downward face, which is the leg reference
        for edge, face in underside:
            group = next((g for g in groups if g[0].is_same(face)), None)
            if group is None:
                groups.append((face, [edge]))
            else:
                group[1].append(edge)
        for i, (face, group) in enumerate(groups):
            if i:   # earlier chamfers rebuilt the topology: re-find by position
                group, face = select_edges(result, [_mid(e) for e in group]), select_face(result, face.center())
            result = result.chamfer(radius, vertical_leg, group, face)
        if upper:   # re-find by midpoint: the chamfers rebuilt the topology
            result = result.fillet(radius, select_edges(result, [_mid(e) for e, _ in upper]))
    except Exception as err:  # OCC raises StdFail_NotDone and friends
        raise FeatureError(f"{name}: kernel refused radius {radius} on {len(selected)} edges ({err})") from err
    slop = []
    if len(selected) >= 0.9 * len(shape.edges()):
        slop.append(f"uniform edge break: one size ({radius}) on {len(selected)} of {len(shape.edges())} edges")
    derived = {"chamfer_vertical_leg": {"value": vertical_leg,
                                        "source": "radius / tan(print_rules.self_supporting_deg)"}}
    notes = [f"{len(upper)} edges filleted, {len(underside)} underside edges chamfered"]
    return _finish(name, shape, result, f"{len(selected)} edges", {"radius": radius},
                   derived, allow_supports, slop, notes)


def shell(shape, open_faces, wall, allow_supports=False):
    """Hollow the solid to `wall`, removing the selected faces as openings.

    Params:
      open_faces: Face objects or points near them; at least one.
      wall:       min_wall() .. 10 mm.
    Opening a face that is not on top usually leaves a ceiling inside; the print check refuses it.
    """
    name = "shell"
    _bounded(name, "wall", wall, min_wall(), 10.0)
    faces = [select_face(shape, t) for t in open_faces]
    if not faces:
        raise FeatureError(f"{name}: needs at least one open face")
    try:
        result = offset(shape, amount=-wall, openings=faces)
    except Exception as err:
        raise FeatureError(f"{name}: kernel refused wall {wall} ({err})") from err
    return _finish(name, shape, result, ", ".join(_describe(f) for f in faces), {"wall": wall},
                   {}, allow_supports)


def rib(shape, face, start, end, height, thickness, allow_supports=False):
    """A straight stiffening rib standing on a planar face, from `start` to `end`.

    Params:
      face:       the face the rib stands on (Face or point near it).
      start, end: points on that face (mm); length >= 2 * thickness.
      height:     rib height off the face, thickness .. 10 * thickness (slender ribs whip).
      thickness:  min_wall() .. 10 mm.
    A rib on a vertical face, running horizontally, has a ceiling under it; refused.
    """
    name = "rib"
    _bounded(name, "thickness", thickness, min_wall(), 10.0)
    _bounded(name, "height", height, thickness, 10 * thickness)
    target = _planar(name, select_face(shape, face))
    a, b = _vec(start), _vec(end)
    length = (b - a).length
    _bounded(name, "length", length, 2 * thickness, math.inf)
    normal = target.normal_at((a + b) * 0.5)
    direction = (b - a).normalized()
    if abs(direction.dot(normal)) > VERTICAL_EPS:
        raise FeatureError(f"{name}: start/end must lie in the face plane")
    plane = Plane(origin=(a + b) * 0.5, x_dir=direction, z_dir=normal)
    footprint = plane * Rectangle(length, thickness)
    if not _inside_face(target, footprint):
        raise FeatureError(f"{name}: rib footprint runs off the face")
    result = shape + extrude(footprint, amount=height)
    return _finish(name, shape, result, _describe(target),
                   {"height": height, "thickness": thickness, "length": length}, {}, allow_supports)


def gusset(shape, edge, leg, thickness, count=1, allow_supports=False):
    """Triangular gussets in a concave 90 deg corner along a straight edge.

    Params:
      edge:      the inside corner edge (Edge or point near it).
      leg:       length of each leg along the two faces, 2 * thickness .. 100 mm.
      thickness: min_wall() .. 10 mm.
      count:     1 .. 12, spaced evenly along the edge; count * thickness <= edge length.
    """
    name = "gusset"
    _bounded(name, "thickness", thickness, min_wall(), 10.0)
    _bounded(name, "leg", leg, 2 * thickness, 100.0)
    _bounded(name, "count", count, 1, 12)
    target = select_edges(shape, [edge])[0]
    if target.geom_type != GeomType.LINE:
        raise FeatureError(f"{name}: corner edge must be straight")
    faces = _faces_of(shape, target)
    if len(faces) != 2 or any(f.geom_type != GeomType.PLANE for f in faces):
        raise FeatureError(f"{name}: corner edge must join two planar faces")
    mid = target.center()
    n1, n2 = (f.normal_at(mid) for f in faces)
    if abs(n1.dot(n2)) > VERTICAL_EPS:
        raise FeatureError(f"{name}: faces meet at {math.degrees(math.acos(n1.dot(n2))):.1f} deg, need 90")
    # Inside corner: a step off face 1 and back past face 2 lands in face 2's material.
    # On an outside corner the same step lands in air.
    probe = min_wall() / 2
    if not shape.is_inside(mid + (n1 - n2) * probe):
        raise FeatureError(f"{name}: corner is convex; a gusset needs an inside corner")
    length = target.length
    if count * thickness > length:
        raise FeatureError(f"{name}: {count} gussets of {thickness} do not fit on a {length:.1f} edge")
    direction = (target.end_point() - target.start_point()).normalized()
    result = shape
    for i in range(count):
        at = target.start_point() + direction * (length * (i + 0.5) / count)
        plane = Plane(origin=at, x_dir=n2, z_dir=direction)
        local_n1 = plane.to_local_coords(at + n1) - plane.to_local_coords(at)
        triangle = Polygon((0, 0), (leg, 0), (local_n1.X * leg, local_n1.Y * leg), align=None)
        result = result + extrude(plane * triangle, amount=thickness / 2, both=True)
    derived = {"spacing": {"value": length / count, "source": "edge length / count"}}
    return _finish(name, shape, result, _describe(target),
                   {"leg": leg, "thickness": thickness, "count": count}, derived, allow_supports)


def _face_frame(face):
    """(origin, u, v, normal) with v the in-face direction closest to print-up."""
    normal = face.normal_at()
    up = Vector(0, 0, 1)
    u = up.cross(normal)
    u = Vector(1, 0, 0) if u.length < VERTICAL_EPS else u.normalized()
    v = normal.cross(u).normalized()
    return face.center(), u, v, normal


def lightening_cutouts(shape, face, cell, web, margin=None, depth=None, allow_supports=False):
    """A grid of pockets through (or into) a planar face, leaving webs between them.

    On a face that is not facing up or down, pockets are diamonds whose upper flanks slope
    self_supporting_deg from vertical, so each pocket roof prints without support. On a
    horizontal face they are rectangles with corners rounded by web/2.

    Params:
      cell:   target pocket size, 2 * web .. 200 mm (the grid fits whole pockets).
      web:    min_wall() .. 20 mm, the material left between pockets.
      margin: border kept solid inside the face edge; default = web.
      depth:  pocket depth into the face; default None cuts through the part.
    """
    name = "lightening_cutouts"
    _bounded(name, "web", web, min_wall(), 20.0)
    _bounded(name, "cell", cell, 2 * web, 200.0)
    margin = web if margin is None else _bounded(name, "margin", margin, min_wall(), 50.0)
    target = _planar(name, select_face(shape, face))
    origin, u, v, normal = _face_frame(target)
    vertical_face = abs(normal.Z) < math.cos(math.radians(slope_deg()))
    pts = [target.center()] + [p for p in target.vertices()]
    us = [(_vec(p) - origin).dot(u) for p in pts]
    vs = [(_vec(p) - origin).dot(v) for p in pts]
    span_u, span_v = max(us) - min(us) - 2 * margin, max(vs) - min(vs) - 2 * margin
    nu, nv = int((span_u + web) // (cell + web)), int((span_v + web) // (cell + web))
    if nu < 1 or nv < 1:
        raise FeatureError(f"{name}: no {cell} mm pocket fits inside a {margin} mm margin")
    size_u, size_v = (span_u - (nu - 1) * web) / nu, (span_v - (nv - 1) * web) / nv
    if vertical_face:  # diamond: half-width / half-height <= tan(slope)
        size_u = min(size_u, size_v * math.tan(math.radians(slope_deg())))
        pitch_u = size_u + web
    else:
        pitch_u = (span_u + web) / nu
    pitch_v = (span_v + web) / nv
    centre_u, centre_v = (max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2
    plane = Plane(origin=origin, x_dir=u, z_dir=normal)
    try:
        inner = offset(target, amount=-margin)
    except Exception as err:
        raise FeatureError(f"{name}: margin {margin} leaves no face ({err})") from err
    through = (shape.bounding_box().diagonal + 1.0) if depth is None else depth
    if depth is not None:
        _bounded(name, "depth", depth, min_wall(), shape.bounding_box().diagonal)
    pockets = []
    for i in range(nu):
        for j in range(nv):
            cu = centre_u + (i - (nu - 1) / 2) * pitch_u
            cv = centre_v + (j - (nv - 1) / 2) * pitch_v
            if vertical_face:
                hu, hv = size_u / 2, size_v / 2
                outline = Polygon((cu - hu, cv), (cu, cv - hv), (cu + hu, cv), (cu, cv + hv), align=None)
            else:
                outline = Pos(cu, cv) * RectangleRounded(size_u, size_v, web / 2)
            pockets.append(plane * outline)
    if not _inside_face(inner, Sketch() + pockets):   # a hole or notch: keep pockets clear of it
        pockets = [p for p in pockets if _inside_face(inner, p)]
    if not pockets:
        raise FeatureError(f"{name}: no pocket fits wholly inside the face")
    cutter = extrude(Sketch() + pockets, amount=through, dir=-normal)
    result = shape - cutter
    derived = {"pocket_u": {"value": size_u, "source": "grid fit of cell, web, margin"
                            + (", capped by self_supporting_deg" if vertical_face else "")},
               "pocket_v": {"value": size_v, "source": "grid fit of cell, web, margin"},
               "pockets": {"value": len(pockets), "source": "whole pockets inside face - margin"},
               "shape": {"value": "diamond" if vertical_face else "rounded rectangle",
                         "source": "face orientation vs print-up"}}
    return _finish(name, shape, result, _describe(target),
                   {"cell": cell, "web": web, "margin": margin, "depth": depth}, derived, allow_supports)


def insert_boss(shape, face, at, screw="M3", height=None, allow_supports=False):
    """A heat-set insert boss standing on a planar face at point `at`.

    Hole, boss OD, floor and minimum height all come from standard_parts.json
    heatset_inserts[screw]; the insert hole is the vendor's press size, so no fit
    clearance is added. On anything but an upward face the boss overhangs; refused.

    Params:
      screw:  key of heatset_inserts (M2.5, M3, M4).
      height: boss height off the face, DB minimum .. 4 x minimum. Default the minimum.
    """
    name = "insert_boss"
    spec = standard_parts()["heatset_inserts"].get(screw)
    if spec is None:
        raise FeatureError(f"{name}: {screw!r} not in heatset_inserts")
    minimum = spec["insert_length"] + spec["hole_extra_depth"] + spec["floor"]
    height = minimum if height is None else _bounded(name, "height", height, minimum, 4 * minimum)
    target = _planar(name, select_face(shape, face))
    point = _vec(at)
    normal = target.normal_at(point)
    if normal.Z < -VERTICAL_EPS:   # it may only replace existing ceiling, so the area check passes it
        raise FeatureError(f"{name}: boss on a downward face would end in an unsupported overhang")
    plane = Plane(origin=point, x_dir=_face_frame(target)[1], z_dir=normal)
    if not _inside_face(target, plane * Circle(spec["boss_od"] / 2)):
        raise FeatureError(f"{name}: a {spec['boss_od']} mm boss at {tuple(point)} runs off the face")
    boss = heatset_boss(screw, height=height)
    result = shape + plane.location * boss
    derived = {"hole_dia": {"value": spec["hole_dia"], "source": f"heatset_inserts.{screw}"},
               "boss_od": {"value": spec["boss_od"], "source": f"heatset_inserts.{screw}"},
               "min_height": {"value": minimum, "source": "insert_length + hole_extra_depth + floor"}}
    return _finish(name, shape, result, _describe(target), {"screw": screw, "height": height},
                   derived, allow_supports)


# Threads: a printable trapezoid. Both flanks slope self_supporting_deg from the axis, so a
# vertical thread prints without support; ISO 60 deg flanks would be 30 deg overhangs.


def interference_of(depth, pitch, root_width):
    """How far the thread root is sunk into the core, so the union never meets at a tangent.

    Half the depth, capped so the flanks' run into the core leaves adjacent turns half a
    nozzle apart: overlapping turns make the sweep self-intersect.
    """
    room = (pitch - root_width - rules()["nozzle"] / 2) / 2
    if room <= 0:
        room = (pitch - root_width) / 4
    return min(depth * 0.5, room * math.tan(math.radians(slope_deg())))


def thread_profile(pitch, depth, fit="sliding"):
    """Widths of the printable thread profile and the clearance that mates it.

    Returns {apex_width, root_width, axial_clearance, radial_clearance}. The profile is
    symmetric: the mating internal thread has the same widths, offset radially by the
    fit's per-side clearance (CLAUDE.md table) and axially by clearance * tan(slope/2).
    """
    if fit not in fits():
        raise FeatureError(f"thread: fit {fit!r} not in {sorted(fits())}")
    clearance = fits()[fit]
    rise = depth / math.tan(math.radians(slope_deg()))     # axial run of one flank
    axial = clearance * math.tan(math.radians(slope_deg()) / 2)
    apex = pitch / 2 - rise - axial
    if apex < rules()["nozzle"] / 2:
        raise FeatureError(f"thread: depth {depth} too deep for pitch {pitch} (crest {apex:.2f} mm)")
    return {"apex_width": apex, "root_width": pitch / 2 + rise - axial,
            "axial_clearance": axial, "radial_clearance": clearance}


def mating_radius(radius, depth, internal, fit="sliding"):
    """Root radius of the mating thread: a nut for a post of root `radius`, or vice versa."""
    clearance = fits()[fit]
    return radius + depth + clearance if not internal else radius - depth - clearance


def thread(shape, face, pitch, depth, length=None, z_start=None, fit="sliding", allow_supports=False):
    """A printable helical thread on a vertical cylindrical face: ridges outward on a post,
    inward in a bore. The cylinder's radius is the thread root.

    Params:
      face:    the cylindrical face (Face or point near it); axis must be print-up (Z).
      pitch:   1.5 .. 8 mm.
      depth:   radial ridge height, min_wall() .. pitch / 3 (crest stays >= nozzle/2).
      length:  threaded length; default the face height minus one pitch.
      z_start: where the thread starts; default half a pitch above the face bottom.
      fit:     fits table key used for the clearance that thread_profile() reports.
    """
    name = "thread"
    _bounded(name, "pitch", pitch, 1.5, 8.0)
    _bounded(name, "depth", depth, min_wall(), pitch / 3)
    target = select_face(shape, face)
    if target.geom_type != GeomType.CYLINDER:
        raise FeatureError(f"{name}: target must be a cylindrical face")
    axis = target.axis_of_rotation
    if abs(abs(axis.direction.Z) - 1) > VERTICAL_EPS:
        raise FeatureError(f"{name}: thread axis must be print-up (Z); a horizontal thread stair-steps")
    radius = target.radius
    box = target.bounding_box()
    centre = Vector(axis.position.X, axis.position.Y, 0)
    probe = centre + Vector(radius + depth * 0.5, 0, (box.min.Z + box.max.Z) / 2)
    internal = shape.is_inside(probe)   # material outside the radius: a bore
    length = box.size.Z - pitch if length is None else length
    z_start = box.min.Z + pitch / 2 if z_start is None else z_start
    _bounded(name, "length", length, pitch, box.size.Z)
    if z_start < box.min.Z - BED_Z_TOL or z_start + length > box.max.Z + BED_Z_TOL:
        raise FeatureError(f"{name}: thread runs off the {box.size.Z:.1f} mm face")
    profile = thread_profile(pitch, depth, fit)
    apex_r = radius - depth if internal else radius + depth
    # One frenet sweep of the trapezoid along a helix, overrunning a pitch at each end; the
    # ends are trimmed below. (bd_warehouse's Thread leaves horizontal slivers at its segment
    # joints and its fade ends slope at exactly 45 deg, so it is not used.)
    interference = interference_of(depth, pitch, profile["root_width"])
    side = -1 if internal else 1
    root_in, apex_r = radius - side * interference, radius + side * depth
    # Flanks run straight on into the core, so no profile corner sits on the cylinder surface
    # (a corner there leaves coincident-edge slivers in the union).
    half_in = profile["root_width"] / 2 + interference / math.tan(math.radians(slope_deg()))
    half_apex = profile["apex_width"] / 2
    section = Plane.XZ * Polygon((root_in, -half_in), (apex_r, -half_apex), (apex_r, half_apex),
                                 (root_in, half_in), align=None)
    ridge = sweep(section, Helix(pitch, length + 2 * pitch, radius), is_frenet=True)
    ridge = Pos(0, 0, -pitch) * ridge
    # Bottom trim: a cone sloping self_supporting_deg from vertical, so the cut end faces
    # down-and-out (or down-and-in, for a bore) at a printable angle. Top trim: flat, faces up.
    flare = (depth + interference) / math.tan(math.radians(slope_deg())) + pitch
    grow = flare * math.tan(math.radians(slope_deg()))
    outer = radius + depth + grow
    band = Cylinder(outer, length, align=(Align.CENTER, Align.CENTER, Align.MIN))
    if internal:
        cone = Cone(radius, max(radius - grow, 0.0), flare, align=(Align.CENTER, Align.CENTER, Align.MIN))
        keep = band - cone
    else:
        cone = Cone(radius, radius + grow, flare, align=(Align.CENTER, Align.CENTER, Align.MIN))
        above = Pos(0, 0, flare) * Cylinder(outer, length, align=(Align.CENTER, Align.CENTER, Align.MIN))
        keep = band & (cone + above)
    ridge = ridge & keep
    placed = Pos(centre.X, centre.Y, z_start) * ridge
    try:
        result = shape + placed
    except Exception as err:
        raise FeatureError(f"{name}: kernel refused the thread ({err})") from err
    derived = {**{k: {"value": v, "source": "thread_profile(): slope from print_rules, clearance "
                      f"from fits.{fit}"} for k, v in profile.items()},
               "kind": {"value": "internal" if internal else "external", "source": "material side of face"}}
    return _finish(name, shape, result, _describe(target),
                   {"pitch": pitch, "depth": depth, "length": length, "z_start": z_start, "fit": fit},
                   derived, allow_supports)


def print_draft(shape, face, allow_supports=False):
    """Draft a flat or shallow underside for print direction: fill under it with a solid
    whose free sides slope self_supporting_deg from vertical, down to the bed or the part.

    Edges of the face that sit on a wall running down from them stay vertical; only free
    edges slope. The target must be a convex polygon facing within 45 deg of straight down.
    """
    name = "print_draft"
    target = _planar(name, select_face(shape, face))
    normal = target.normal_at()
    if -normal.Z < math.cos(math.radians(45)):
        raise FeatureError(f"{name}: face is not an underside (normal {tuple(normal)})")
    if target.inner_wires() or any(e.geom_type != GeomType.LINE for e in target.edges()):
        raise FeatureError(f"{name}: underside must be a polygon without holes")
    box = shape.bounding_box()
    big = 4 * box.diagonal
    centroid = target.center()
    z_bed = box.min.Z
    if centroid.Z - z_bed < min_wall():
        raise FeatureError(f"{name}: underside already on the bed")
    tilt = math.tan(math.radians(slope_deg()))
    # Half-spaces: below the face plane, above the bed, and one per edge.
    keep_below = Plane(origin=centroid, z_dir=normal)   # box grows along the normal: down
    region = keep_below * Box(big, big, big, align=(Align.CENTER, Align.CENTER, Align.MIN))
    region = region & (Pos(box.center().X, box.center().Y, z_bed)
                       * Box(big, big, big, align=(Align.CENTER, Align.CENTER, Align.MIN)))
    sloped = 0
    for edge in target.edges():
        mid = edge.center()
        d = (edge.end_point() - edge.start_point()).normalized()
        out = mid - centroid
        out = Vector(out.X, out.Y, 0)
        out = (out - d * out.dot(d))
        out = Vector(out.X, out.Y, 0).normalized()
        others = [f for f in _faces_of(shape, edge) if not f.is_same(target)]
        # Walled: a vertical face continues down from this edge, so the fill can follow it.
        walled = any(abs(f.normal_at(mid).Z) < VERTICAL_EPS
                     and f.bounding_box().min.Z < mid.Z - min_wall() for f in others)
        down = Vector(0, 0, -1) if walled else (Vector(0, 0, -1) - out * tilt).normalized()
        sloped += not walled
        n = d.cross(down).normalized()
        if n.dot(out) < 0:
            n = -n
        keep = Plane(origin=mid, x_dir=d, z_dir=-n)
        region = region & (keep * Box(big, big, big, align=(Align.CENTER, Align.CENTER, Align.MIN)))
    if not sloped:
        raise FeatureError(f"{name}: every edge is walled; nothing to draft")
    if region.volume <= 0:
        raise FeatureError(f"{name}: draft solid is empty")
    result = shape + region
    derived = {"slope_deg": {"value": slope_deg(), "source": "print_rules.self_supporting_deg"},
               "sloped_edges": {"value": sloped, "source": "edges not sitting on a wall below"},
               "fill_mm3": {"value": region.volume, "source": "half-space intersection"}}
    return _finish(name, shape, result, _describe(target), {}, derived, allow_supports)


# ---------------------------------------------------------------- registry

FEATURES = {
    "edge_break": edge_break,
    "shell": shell,
    "rib": rib,
    "gusset": gusset,
    "lightening_cutouts": lightening_cutouts,
    "insert_boss": insert_boss,
    "thread": thread,
    "print_draft": print_draft,
}


from . import textures  # noqa: E402,F401  textures builds on the helpers above and registers in FEATURES


def propose(feature, shape, **kwargs):
    """Apply a feature by name; returns its FeatureProposal (raises FeatureError if refused)."""
    if feature not in FEATURES:
        raise FeatureError(f"unknown feature {feature!r}; available: {sorted(FEATURES)}")
    return FEATURES[feature](shape, **kwargs)


def review_flags(proposals):
    """CAD slop tells across a design's accepted proposals (see CLAUDE.md critique gate)."""
    flags = [f for p in proposals for f in p.slop_flags]
    breaks = [p for p in proposals if p.feature == "edge_break"]
    radii = {p.params["radius"] for p in breaks}
    if len(breaks) >= 2 and len(radii) == 1:
        flags.append(f"default-everything: every edge break uses radius {radii.pop()}")
    return flags
