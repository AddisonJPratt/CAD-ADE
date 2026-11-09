"""Joints between printed parts (#54): snap-fit, press fit, dovetail, print-in-place hinge,
living hinge, and screw + heat-set insert. All dimensions mm.

Geometry is built in a **joint frame**: origin on the contact plane, +Z pointing from part A
(the part that carries the male feature) into part B (the part the socket is cut from).
`build(kind, clearance)` returns a `JointGeometry` whose solids are added to or cut from each
part by the assembly model (assembly/joints.py); a design never repeats them.

Where the numbers come from:
- the per-side clearance: `clearance(fit, material)`, read from library/printer_profiles.py for
  the project's material (the CLAUDE.md fit table), never written here;
- the shapes' sizes: library/joints.json, each with its intent;
- slopes and walls: standard_parts.json "print_rules" (44 deg from vertical, two perimeters).

Every mating surface is either vertical or at the print slope, so a male feature that grows
straight up in its part's print frame and a socket opening up *or* down both print without
supports. The socket is the male profile offset by the clearance (sharp-corner offset), so
the gap measured between the two parts is the clearance everywhere, which is what the
assembly gate checks. These are uncalibrated starting values: a joint stays at the
needs-physical-test tier until a print result for it is recorded.
"""
import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from build123d import (Align, Axis, Box, Cylinder, Kind, Plane, Polyline, Pos, Rectangle, Solid,
                       make_face, offset)

from .features import standard_parts
from .printer_profiles import PROFILE

KINDS = ("snap_fit", "press_fit", "dovetail", "print_in_place_hinge", "living_hinge", "screw_insert")
LABELS = {"snap_fit": "snap-fit", "press_fit": "press fit", "dovetail": "dovetail",
          "print_in_place_hinge": "print-in-place hinge", "living_hinge": "living hinge",
          "screw_insert": "screw + heat-set insert"}
# Joints whose geometry the model adds and whose sites it can find on a face contact by itself.
FACE_JOINTS = ("snap_fit", "press_fit")


TABLE = Path(__file__).with_name("joints.json")


@lru_cache(maxsize=1)
def table():
    """The joint table, library/joints.json: sizes and fit classes, each with its intent."""
    return json.loads(TABLE.read_text())


def spec(kind):
    """The joints.json entry for a joint kind, without its _intent notes."""
    table_ = table()
    if kind not in table_ or kind.startswith("_"):
        raise ValueError(f"unknown joint {kind!r}; joints: {', '.join(KINDS)}")
    return {k: v for k, v in table_[kind].items() if not k.startswith("_")}


def materials():
    return sorted(PROFILE["materials"])


def clearance(fit, material="PLA"):
    """Per-side clearance (mm) of a fit class for a material, from the printer profile."""
    if material not in PROFILE["materials"]:
        raise ValueError(f"unknown material {material!r}; profile has {materials()}")
    table = PROFILE["materials"][material]["fit_clearance_mm_per_side"]
    if fit not in table:
        raise ValueError(f"unknown fit {fit!r}; profile has {sorted(table)}")
    return table[fit]


def calibrated(material="PLA"):
    return bool(PROFILE["materials"].get(material, {}).get("calibrated"))


def _rules():
    return standard_parts()["print_rules"]


def slope_deg():
    """Print slope used on every flank: inside the 45 deg gate (see print_rules._intent)."""
    return _rules()["self_supporting_deg"]


def min_wall():
    r = _rules()
    return r["nozzle"] * r["min_wall_perimeters"]


def embed():
    """How far a male feature reaches back into its own part, so the union is one solid.

    One nozzle width: the overlap sits inside the part, below the contact plane, so it never
    moves a mating face (kernel pitfalls: union overlaps sit inside the other shape).
    """
    return _rules()["nozzle"]


@dataclass
class JointGeometry:
    """A joint's solids in its joint frame. Each may be None.

    a_add / b_add are fused onto part A / B; a_cut / b_cut are cut from them. `probe` is the
    region (a Box in the joint frame) where the gate measures the gap between the two parts;
    `inset` is how far the site must sit from the edge of the contact face, and `depth` how
    much of part B must lie behind the contact face, along +Z.
    """
    kind: str
    fit: str
    clearance: float
    a_add: Solid = None
    a_cut: Solid = None
    b_add: Solid = None
    b_cut: Solid = None
    probe: Solid = None
    inset: float = 0.0
    depth: float = 0.0
    checks: dict = field(default_factory=dict)    # derived values the gate rules read
    revolute: bool = False                         # the joint turns about +Z instead of sliding on it


def _one(shape):
    solids = shape.solids()
    if len(solids) != 1:
        raise ValueError(f"joint feature came out as {len(solids)} solids; expected one")
    return solids[0]


def _half(face):
    """The x >= 0 half of a profile drawn symmetric about its axis, ready to revolve."""
    box = face.bounding_box()
    keep = Pos(0, box.center().Y) * Rectangle(box.max.X + 1, box.size.Y + 2, align=(Align.MIN, Align.CENTER))
    return (face & keep).faces()[0]


def _revolve(face):
    """Revolve a symmetric (x, z) profile drawn in XY about the Z axis."""
    return Solid.revolve(Plane.XZ * _half(face), 360, Axis.Z)


def _profile(points):
    """A closed profile from (r, z) points on the +r side, mirrored to make it symmetric."""
    right = list(points)
    left = [(-r, z) for r, z in reversed(right) if r != 0]
    return make_face(Polyline(*right, *left, close=True))


def _grown(face, gap):
    """The profile grown by the clearance with sharp corners: the socket profile."""
    return offset(face, gap, kind=Kind.INTERSECTION).faces()[0]


def _probe(radius, top):
    """Measuring region: everything within `radius` of the axis, a nozzle above the contact plane."""
    start = embed()
    return Pos(0, 0, start) * Box(2 * radius, 2 * radius, top - start,
                                  align=(Align.CENTER, Align.CENTER, Align.MIN))


def _prong_fibre(r, half_slot):
    """Farthest fibre from the bending axis of one D-shaped prong: a disc of radius r cut at
    x = half_slot. The prong is not a rectangle, so 1.5*t*d/L^2 understates its strain."""
    area = r * r * math.acos(half_slot / r) - half_slot * math.sqrt(r * r - half_slot * half_slot)
    centroid = 2 * (r * r - half_slot * half_slot) ** 1.5 / (3 * area)
    return max(centroid - half_slot, r - centroid)


def snap_fit(gap, peg_dia=None, barb=None, neck=None, slot=None, max_strain=None, **_):
    """Split barbed peg on A, grooved socket in B: a light, reusable snap.

    The peg is a neck, a barb that flares out at the print slope, and a lead-in tip cut flat
    where the prongs would thin below two nozzle widths; a slot with a rounded root splits it
    into two prongs that close as the barb passes the socket's neck. The socket is the peg's
    profile grown by the clearance, ending in a cone (no flat ceiling). Retention comes from
    the barb exceeding the neck clearance. Its back face is at the print slope too, so the snap
    pulls apart with about the force it took to push in: that is a limit of printing the barb
    without support, not a feature.

    The prongs stand along Z, so bending loads the layer bonds; their strain uses the D-shaped
    section's real far fibre (3*c*d/L^2) against the joint table's layer-bond limit.
    """
    s = spec("snap_fit")
    r = (peg_dia if peg_dia is not None else s["peg_dia"]) / 2
    barb = barb if barb is not None else s["barb"]
    neck = neck if neck is not None else s["neck"]
    slot = slot if slot is not None else s["slot"]
    max_strain = max_strain if max_strain is not None else s["max_strain"]
    tan = math.tan(math.radians(slope_deg()))
    flare = neck + barb / tan
    tip = slot / 2 + min_wall()                            # each prong keeps two perimeters at its tip
    top = flare + (r + barb - tip) / tan
    profile = _profile([(0, -embed()), (r, -embed()), (r, neck), (r + barb, flare), (tip, top), (0, top)])
    peg = _revolve(profile)
    floor = min_wall()
    prong = top - floor                                    # free length of each prong, from the slot's root
    root = slot / 2                                        # the slot ends in a half round, not a square corner
    split = Pos(0, 0, floor + root) * Box(slot, 2 * (r + barb) + 2, prong,
                                          align=(Align.CENTER, Align.CENTER, Align.MIN))
    fillet_ = Pos(0, 0, floor + root) * Cylinder(root, 2 * (r + barb) + 2, rotation=(90, 0, 0))
    peg = _one(peg - split - fillet_)
    peg.label = "snap peg"
    socket = _revolve(_grown(profile, gap))
    socket.label = "snap socket"
    deflection = barb - gap
    strain = 3 * _prong_fibre(r, slot / 2) * deflection / prong ** 2
    outer = r + barb + gap
    return JointGeometry("snap_fit", s["fit"], gap, a_add=peg, b_cut=socket,
                         probe=_probe(outer + min_wall(), top + gap + min_wall()),
                         inset=outer + min_wall(), depth=socket.bounding_box().max.Z + min_wall(),
                         checks={"strain": strain, "max_strain": max_strain, "retention": deflection,
                                 "prong_close": 2 * deflection, "slot": slot, "prong_length": prong})


def press_fit(gap, pin_dia=None, length=None, **_):
    """Pin on A with a lead-in chamfer at the print slope; hole in B grown by the press clearance."""
    s = spec("press_fit")
    r = (pin_dia if pin_dia is not None else s["pin_dia"]) / 2
    length = length if length is not None else s["length"]
    tan = math.tan(math.radians(slope_deg()))
    lead = min_wall()                                       # radial lead-in at the tip
    profile = _profile([(0, -embed()), (r, -embed()), (r, length - lead / tan), (r - lead, length), (0, length)])
    pin = _revolve(profile)
    pin.label = "press pin"
    # The hole ends in a cone at the print slope, so it prints opening up or down.
    hole_profile = _grown(profile, gap)
    box = hole_profile.bounding_box()
    tip = box.max.Y
    rr = box.max.X
    cone = _profile([(0, box.min.Y), (rr, box.min.Y), (rr, tip), (0, tip + rr / tan)])
    hole = _revolve(cone)
    hole.label = "press hole"
    return JointGeometry("press_fit", s["fit"], gap, a_add=pin, b_cut=hole,
                         probe=_probe(rr + min_wall(), length + gap + min_wall()),
                         inset=rr + min_wall(), depth=hole.bounding_box().max.Z + min_wall())


def dovetail(gap, width=None, depth=None, flank_deg=None, length=None, run=None, **_):
    """Tail on A, socket in B; the tail slides in along -Y and the socket runs out in +Y.

    run: how far the socket continues in +Y past the tail's end, so it leaves part B (the
    model passes part B's size). The tail widens away from A at flank_deg from vertical.
    """
    s = spec("dovetail")
    width = width if width is not None else s["width"]
    depth = depth if depth is not None else s["depth"]
    flank = flank_deg if flank_deg is not None else s["flank_deg"]
    length = length if length is not None else s["length"]
    if not 0 < flank <= slope_deg():
        raise ValueError(f"dovetail flank {flank} deg must be inside the {slope_deg()} deg print slope")
    spread = depth * math.tan(math.radians(flank))
    w = width / 2
    profile = make_face(Polyline((-w, -embed()), (w, -embed()), (w, 0), (w + spread, depth),
                                 (-w - spread, depth), (-w, 0), close=True))
    tail = (Plane.XZ * profile).faces()[0]
    tail = Solid.extrude(tail, (0, -length, 0)).moved(Pos(0, length / 2, 0))   # y from -L/2 to L/2
    tail.label = "dovetail tail"
    grown = _grown(profile, gap)
    run = run if run is not None else length
    socket = Solid.extrude((Plane.XZ * grown).faces()[0], (0, -(length + gap + run), 0)).moved(Pos(0, length / 2 + run, 0))
    socket.label = "dovetail socket"
    half = w + spread + gap + min_wall()
    probe = Pos(0, 0, embed()) * Box(2 * half, length + 2 * (gap + min_wall()), depth + gap + min_wall() - embed(),
                                     align=(Align.CENTER, Align.CENTER, Align.MIN))
    return JointGeometry("dovetail", s["fit"], gap, a_add=tail, b_cut=socket, probe=probe,
                         inset=half, depth=depth + gap + min_wall())


def print_in_place_hinge(gap, knuckle_dia=None, knuckle_height=None, spine=None, swing_deg=None, **_):
    """Three stacked knuckles about +Z: A's at the bottom and top, B's between, printed assembled.

    Knuckles meet on cones at the print slope: B's recess sits a clearance above A's cone and
    A's top recess a clearance above B's cone, so every knuckle prints on the one below it
    without a flat overhang, and the cones hold B captive. Each leaf's spine stands a clearance
    outside the other leaf's knuckle, along -X (A) or +X (B), and bridges join it to its own
    knuckles where the other leaf is nowhere near. Both leaves are built only by unions of
    shapes that never share a surface (kernel pitfall: a cut that coincides with a face leaves
    an invalid solid), and the gap between them is the clearance throughout.
    """
    s = spec("print_in_place_hinge")
    R = (knuckle_dia if knuckle_dia is not None else s["knuckle_dia"]) / 2
    H = knuckle_height if knuckle_height is not None else s["knuckle_height"]
    reach = spine if spine is not None else s["spine"]
    swing = swing_deg if swing_deg is not None else s["swing_deg"]
    if reach <= R + gap:
        raise ValueError(f"spine {reach} mm must reach past the knuckle radius {R} mm + clearance")
    tan = math.tan(math.radians(slope_deg()))
    cone = R / tan
    lift = gap / math.sin(math.radians(slope_deg()))   # vertical shift that sets a cone `gap` off its twin
    z1 = H                                             # top of A's bottom knuckle cylinder
    b0, b1 = z1 + lift, z1 + lift + H                  # B's knuckle cylinder, at its rim
    t0, top = b1 + lift, b1 + lift + H                 # A's top knuckle cylinder, at its rim
    a_bottom = _revolve(_profile([(0, 0), (R, 0), (R, z1), (0, z1 + cone)]))
    b_mid = _revolve(_profile([(0, b0 + cone), (R, b0), (R, b1), (0, b1 + cone)]))
    a_top = _revolve(_profile([(0, t0 + cone), (R, t0), (R, top)]))
    inner = R / 2                                      # bridges reach this far into their knuckle
    rise = (R - inner) / tan                           # how far a recess climbs between R and inner
    outside = R + gap                                  # spines stand here, a clearance off the other knuckle
    def block(x0, x1, z0, z1_):
        return Box(x1 - x0, 2 * R, z1_ - z0, align=(Align.MIN, Align.CENTER, Align.MIN)).moved(Pos(x0, 0, z0))
    def prism(*points):    # an (x, z) outline, as deep in Y as the knuckles
        face = (Plane.XZ * make_face(Polyline(*points, close=True))).faces()[0]
        return Solid.extrude(face, (0, -2 * R, 0)).moved(Pos(0, R, 0))
    # The upper bridges' undersides carry on the recess cone above them outward at the print
    # slope, so they stay a clearance off the knuckle below and print without a flat overhang.
    far = outside + gap
    drop = (far - R) / tan
    a_side = a_bottom.fuse(a_top, block(-reach, -outside, 0, top),
                           block(-far, -inner, 0, z1),
                           prism((-inner, t0 + rise), (-inner, top), (-far, top), (-far, t0 - drop)))
    a_side = _one(a_side.clean())
    a_side.label = "hinge leaf A"
    # Where B's spine faces A's bottom knuckle on the bed, a first-layer squish would close the
    # clearance: the spine's foot steps back at the print slope (an overhang-free relief).
    relief = s["bed_relief"]
    spine = block(outside, reach, 0, top) - prism((outside, -1), (outside + relief, -1), (outside + relief, 0),
                                                  (outside, relief / tan))
    b_side = b_mid.fuse(spine, prism((inner, b0 + rise), (far, b0 - drop), (far, b1), (inner, b1)))
    b_side = _one(b_side.clean())
    b_side.label = "hinge leaf B"
    # Each part's own body is cut back to a clearance off the other leaf's whole envelope
    # before its leaf is added, so no part body touches the other leaf.
    height = top + cone + 2 * gap
    a_cut = Box(reach + gap + outside, 2 * outside, height, align=(Align.MIN, Align.CENTER, Align.MIN)).moved(Pos(-outside, 0, -gap))
    b_cut = Box(reach + gap + outside, 2 * outside, height, align=(Align.MAX, Align.CENTER, Align.MIN)).moved(Pos(outside, 0, -gap))
    probe = Box(2 * (reach + gap), 2 * (outside + min_wall()), height,
                align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(Pos(0, 0, -gap))
    return JointGeometry("print_in_place_hinge", s["fit"], gap, a_add=a_side, b_add=b_side,
                         a_cut=a_cut, b_cut=b_cut, probe=probe, revolute=True,
                         checks={"swing_deg": swing, "height": top})


def living_hinge_rule(material="PLA"):
    """Web thickness range (mm) for a living hinge. The web lies on the bed, so its thickness is
    a count of layers at the profile's process layer height (joint table)."""
    s = spec("living_hinge")
    return {"min": s["layer_height"] * s["min_layers"], "max": s["layer_height"] * s["max_layers"],
            "note": None if material != "PLA" else
            "PLA living hinges crack after few cycles; PETG flexes far longer. Uncalibrated."}


def living_hinge_notch(web, gap, width, thickness):
    """Cutter for a design: a slot across a plate of `thickness` (in Z, base on z=0) that leaves
    a `web` on the bed. The slot is `gap` wide at the web and opens at the print slope, so its
    walls print without support. Centred on x=0, running along Y for `width`.
    """
    rule = living_hinge_rule()
    if not rule["min"] <= web <= rule["max"]:
        raise ValueError(f"web {web} mm outside {rule['min']:g}..{rule['max']:g} mm")
    if web >= thickness:
        raise ValueError("the web must be thinner than the plate")
    rise = thickness - web
    spread = rise * math.tan(math.radians(slope_deg()))
    profile = make_face(Polyline((-gap / 2, web), (gap / 2, web), (gap / 2 + spread, thickness + 1),
                                 (-gap / 2 - spread, thickness + 1), close=True))
    cutter = Solid.extrude((Plane.XZ * profile).faces()[0], (0, -width - 2, 0)).moved(Pos(0, width / 2 + 1, 0))
    cutter.label = "living hinge"
    return cutter


BUILDERS = {"snap_fit": snap_fit, "press_fit": press_fit, "dovetail": dovetail,
            "print_in_place_hinge": print_in_place_hinge}


def build(kind, gap, **options):
    """The JointGeometry of a geometric joint kind at a per-side clearance `gap`."""
    if kind not in BUILDERS:
        raise ValueError(f"{kind!r} has no added geometry; geometric joints: {', '.join(BUILDERS)}")
    return BUILDERS[kind](gap, **options)
