"""Three feature helpers, and feature naming. All dimensions in mm; Z is the print axis unless noted."""
import json
import math
from functools import lru_cache
from pathlib import Path

from build123d import (Align, Axis, Cylinder, Plane, Polygon, Pos, Solid, extrude,
                       fillet, make_face, Polyline)

DB_PATH = Path(__file__).with_name("standard_parts.json")
# Flanks at 44 deg from vertical: self-supporting, and clear of float noise at exactly 45.
TEARDROP_FLANK_DEG = 44.0


@lru_cache(maxsize=1)
def standard_parts():
    """Return the standard-parts database as a dict."""
    return json.loads(DB_PATH.read_text())


def _lookup(table, key):
    entries = standard_parts()[table]
    if key not in entries:
        raise ValueError(f"{key!r} not in {table}; available: {sorted(entries)}")
    return entries[key]


# Features a design named while building, in order, and the PARAMS each is driven by.
# Read by the harness worker after build().
_DECLARED = []
_PARAMETERS = {}


def feature(name, shape, params=()):
    """Name a feature of a design: a cutter, a boss, any shape whose faces end up on the part.

    Sets the shape's label and records it, so the harness can name the part's faces that
    lie on this shape (`<part>.faces.json`, read by Studio when a face is picked). Returns
    the shape, so it reads inline: `part -= feature("cable slot", Box(...), params="slot_w")`.

    params: the PARAMS key, or keys, that drive this feature (most telling first). The harness
    exports each with its built value, and fails the design if one is not in PARAMS.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("a feature needs a non-empty name")
    if not hasattr(shape, "faces"):
        raise ValueError(f"feature {name!r} must be a build123d shape, not {type(shape).__name__}")
    params = (params,) if isinstance(params, str) else tuple(params)
    if not all(isinstance(p, str) and p.strip() for p in params):
        raise ValueError(f"feature {name!r}: params must be PARAMS names, got {params!r}")
    shape.label = name.strip()
    _DECLARED.append((shape.label, shape))
    _PARAMETERS[shape.label] = tuple(p.strip() for p in params)
    return shape


def declared_features():
    """Named features in declaration order, as (name, shape) pairs."""
    return list(_DECLARED)


def feature_parameters():
    """Each named feature's driving PARAMS names: {feature name: (param, ...)}."""
    return dict(_PARAMETERS)


def reset_features():
    """Forget the features named so far (the worker calls this before each build)."""
    _DECLARED.clear()
    _PARAMETERS.clear()


def _one_solid(shape):
    solids = shape.solids()
    if len(solids) != 1:
        raise ValueError(f"expected one solid, got {len(solids)}")
    return solids[0]


def _bore(radius, z_top, z_bottom, teardrop):
    """Prism along Z between two heights; with teardrop=True a 44 deg peak points to +Y."""
    height = z_top - z_bottom
    bore = Pos(0, 0, z_bottom) * Cylinder(radius, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    if not teardrop:
        return bore
    flank = math.radians(TEARDROP_FLANK_DEG)
    apex_y = radius / math.sin(flank)
    tx, ty = radius * math.cos(flank), radius * math.sin(flank)
    peak = Polygon((-tx, ty), (tx, ty), (0, apex_y), align=None)
    return bore + extrude(Plane.XY.offset(z_bottom) * peak, amount=height)


def counterbored_hole(screw="M4", depth=None, teardrop=False, overshoot=1.0):
    """Cutter for a counterbored clearance hole; subtract it from a part.

    The cutter's mouth plane is z=0. The counterbore runs down into -Z, then the
    clearance bore continues to z=-depth. `overshoot` extends past both faces so
    the boolean never ends coplanar with the part.

    Params / valid range:
      screw:     key of standard_parts.json "screws" (M3, M4, M5). Dimensions come from there.
      depth:     through-thickness of the part, in (counterbore_depth, inf) mm.
                 Default = counterbore depth + head height (a sensible minimum plate).
      teardrop:  True adds a 44 deg peak toward local +Y, so a horizontal hole prints
                 without supports. Orient the cutter so local +Y is print-up.
      overshoot: > 0 mm.
    """
    spec = _lookup("screws", screw)
    cb_depth = spec["counterbore_depth"]
    depth = cb_depth + spec["head_height"] if depth is None else depth
    if depth <= cb_depth:
        raise ValueError(f"depth {depth} must exceed {screw} counterbore depth {cb_depth}")
    if overshoot <= 0:
        raise ValueError("overshoot must be > 0")
    head = counterbore(screw, teardrop, overshoot)
    shank = _bore(spec["clearance"] / 2, overshoot, -depth - overshoot, teardrop)
    return _one_solid(head + shank)


def counterbore(screw="M4", teardrop=False, overshoot=1.0):
    """Just the head pocket of `counterbored_hole`, in the same frame (mouth plane z=0).

    Name it as its own feature before the whole hole, so a pick on the seat or the pocket wall
    says "counterbore" and a pick in the shank says "screw hole":
        bracket -= feature("wall hole counterbore", at * counterbore("M4"), params="thickness")
    Params as `counterbored_hole`.
    """
    spec = _lookup("screws", screw)
    if overshoot <= 0:
        raise ValueError("overshoot must be > 0")
    return _one_solid(_bore(spec["counterbore_dia"] / 2, overshoot, -spec["counterbore_depth"], teardrop))


def heatset_boss(screw="M4", height=None):
    """Round boss with a blind heat-set insert hole opening at the top; base on z=0.

    Params / valid range:
      screw:  key of standard_parts.json "heatset_inserts" (M3, M4).
      height: boss height, >= hole depth + floor from the DB (M3: 7.9, M4: 10.3 mm).
              Default = that minimum.
    """
    spec = _lookup("heatset_inserts", screw)
    hole_depth = spec["insert_length"] + spec["hole_extra_depth"]
    minimum = hole_depth + spec["floor"]
    height = minimum if height is None else height
    if height < minimum:
        raise ValueError(f"height {height} below {screw} minimum {minimum:.2f}")
    body = Cylinder(spec["boss_od"] / 2, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    hole = Pos(0, 0, height - hole_depth) * Cylinder(
        spec["hole_dia"] / 2, hole_depth + 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return _one_solid(body - hole)


def snap_cantilever(length, width, thickness, deflection, max_strain=0.03):
    """Snap-fit cantilever: base block, beam with root fillets, hook. Base face at x=0 root.

    The profile lies in the XY (layer) plane and is extruded along Z by `width`, so the
    beam flexes in +/-Y, in the layer plane; layer lines run along the beam, not across it.

    Params / valid range:
      length:     root to hook, 8..40 mm.
      width:      print height of the beam, 3..20 mm.
      thickness:  beam thickness in Y, 1..4 mm (>= 2 perimeters at 0.4 nozzle).
      deflection: hook overhang = flex needed to clear, 0.3..4 mm.
      max_strain: limit on root strain 1.5*t*d/L^2. Default 0.03 is a conservative PLA
                  starting value, not a measured one. Over the limit raises ValueError.
    """
    checks = {"length": (length, 8, 40), "width": (width, 3, 20),
              "thickness": (thickness, 1, 4), "deflection": (deflection, 0.3, 4)}
    for name, (value, low, high) in checks.items():
        if not low <= value <= high:
            raise ValueError(f"{name}={value} outside {low}..{high}")
    strain = 1.5 * thickness * deflection / length ** 2
    if strain > max_strain:
        raise ValueError(f"root strain {strain:.3f} > {max_strain}; lengthen or thin the beam")
    base_len = base_side = 2 * thickness
    lead_in = deflection / math.tan(math.radians(30))  # 30 deg lead-in, one-handed insertion
    catch = deflection * 0.5                           # slightly undercut-free catch flat
    pts = [(-base_len, -base_side), (0, -base_side), (0, 0), (length, 0),
           (length + catch + lead_in, 0), (length + catch, thickness + deflection),
           (length, thickness + deflection), (length, thickness),
           (0, thickness), (0, thickness + base_side), (-base_len, thickness + base_side)]
    face = make_face(Polyline(*pts, close=True))
    roots = [v for v in face.vertices()
             if abs(v.X) < 1e-6 and (abs(v.Y) < 1e-6 or abs(v.Y - thickness) < 1e-6)]
    face = fillet(roots, radius=thickness * 0.5)
    return _one_solid(extrude(face, amount=width))
