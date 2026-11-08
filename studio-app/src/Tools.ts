/** Outline, note pin and measure tools (#26). All three feed the #25 selection payload.
 *
 * - The lasso's catch: every visible B-rep face and corner point inside a drawn screen loop.
 * - Note pins: short comments on a place on the model, kept with the version (engine/pins.py)
 *   and sent with every request.
 * - Measure: distance and angle between two picks. Parallel flat faces measure plane to plane
 *   on the harness face map's exact planes, which is how the geometry gate reads a bbox probe.
 */
import { BufferGeometry, Vector3 } from 'three';
import { faceAt, type FaceMap, type FaceRecord } from './Features';
import { analyse, label, measure, type Enclosure, type Pick, type SelectionPayload, type Vec } from './Selection';

/* ---------- Measure ---------- */

export type Measurement = { value: number; kind: 'gap between parallel faces' | 'centre to centre'; from: Vec; to: Vec; angle: number | null };
const PARALLEL = 0.999;   // |cos| above this (about 2.5°) counts as parallel, as the mesh test in measure() does
const v3 = (v: Vec) => new Vector3(...v);
const plane = (pick: Pick): { normal: Vector3; centre: Vector3 } | null => {
  if (pick.kind === 'body') return null;
  if (pick.face?.kind === 'plane' && pick.face.normal) return { normal: v3(pick.face.normal), centre: v3(pick.face.centre) };
  return pick.flat ? { normal: v3(pick.normal), centre: v3(pick.centroid) } : null;
};

/** Distance and angle between two picks. The angle is between the faces' planes (0° parallel, 90° square), null without two planes. */
export function measureBetween(a: Pick, b: Pick): Measurement {
  const pa = plane(a), pb = plane(b);
  if (!pa || !pb) return { ...measure(a, b), angle: null };
  const cos = Math.min(1, Math.abs(pa.normal.dot(pb.normal)));
  const angle = Math.acos(cos) * 180 / Math.PI;
  if (cos > PARALLEL) {
    // Plane to plane on the exact planes, drawn square from the first pick's own centre.
    const d = pa.normal.dot(pb.centre.clone().sub(pa.centre)); const from = v3(a.centroid);
    const to = from.clone().addScaledVector(pa.normal, pa.normal.dot(pb.centre.clone().sub(from)));
    return { value: Math.abs(d), kind: 'gap between parallel faces', from: from.toArray() as Vec, to: to.toArray() as Vec, angle };
  }
  return { ...measure(a, b), kind: 'centre to centre', angle };
}

const tilted = (m: Measurement) => m.angle != null && m.angle >= 0.05;
/** The dimension's words on the model: "13.5 mm", plus the angle when the faces are not parallel. */
export function measureText(m: Measurement) {
  return tilted(m) ? `${m.value.toFixed(1)} mm · ${m.angle!.toFixed(1)}°` : `${m.value.toFixed(1)} mm`;
}

/** The reading in words, at the dimension's precision: what the gap is, or that the faces are not parallel. */
export function measureSentence(m: Measurement) {
  if (m.kind === 'gap between parallel faces') return `Gap between parallel faces ${m.value.toFixed(1)} mm`;
  return tilted(m) ? `Faces at ${m.angle!.toFixed(1)}° · centres ${m.value.toFixed(1)} mm apart` : `Centres ${m.value.toFixed(1)} mm apart`;
}

/* ---------- Lasso ---------- */

function inside([x, y]: [number, number], poly: [number, number][]) {
  let hit = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
}
const CORNER_FACES = 3;   // flat faces meeting at a mesh vertex make it a B-rep corner (box corners, step edges)
const INWARD = 0.1;       // triangle samples: the centre, and each vertex pulled this share toward it

/** Faces and corner points of one body inside a screen loop. `project` maps a point to pixels; `visible` says whether nothing hides it. */
export function enclosed(geometry: BufferGeometry, polygon: [number, number][], project: (v: Vector3) => [number, number],
  eye: Vector3, map: FaceMap | undefined, instance: string, visible: (v: Vector3) => boolean = () => true): Enclosure {
  const a = analyse(geometry);
  const facing = (t: number) => a.normal[t].dot(eye.clone().sub(a.centre[t])) > 0;
  const seen = (v: Vector3) => inside(project(v), polygon) && visible(v);
  const faces = new Map<number, FaceRecord>();
  const corners = new Map<string, { point: Vector3; planes: Set<number>; facing: boolean }>();
  for (let t = 0; t < a.count; t++) {
    const tri = a.tri(t);
    tri.forEach(v => {
      const key = v.toArray().map(n => n.toFixed(4)).join(',');
      const entry = corners.get(key) || corners.set(key, { point: v, planes: new Set(), facing: false }).get(key)!;
      if (a.cluster[t] >= 0) entry.planes.add(a.cluster[t]);
      entry.facing ||= facing(t);
    });
    if (!map || !facing(t)) continue;
    // Cheap tests first: inside the loop, then which face; the occlusion test runs once per face at most.
    const samples = [a.centre[t], ...tri.map(v => v.clone().lerp(a.centre[t], INWARD))].filter(v => inside(project(v), polygon));
    if (!samples.length) continue;
    const face = faceAt(map, a.centre[t].toArray() as Vec, a.normal[t].toArray() as Vec, a.cluster[t] >= 0);
    if (face && !faces.has(face.id) && samples.some(visible)) faces.set(face.id, face);
  }
  const points = [...corners.values()].filter(c => c.facing && c.planes.size >= CORNER_FACES && seen(c.point))
    .map(c => ({ instance, point: c.point.toArray().map(n => Math.round(n * 1000) / 1000) as Vec }));
  return { faces: [...faces.values()].sort((x, y) => x.id - y.id).map(face => ({ instance, face })), points };
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

/** A chip: the #25 label, plus what a lasso caught. */
export function toolLabel(pick: Pick) {
  const caught = pick.enclosed;
  if (!caught) return label(pick);
  const parts = [plural(caught.faces.length, 'face'), ...(caught.points.length ? [plural(caught.points.length, 'corner')] : [])];
  return `${label(pick)} · ${parts.join(', ')}`;
}

function catchWords(caught: Enclosure) {
  const names = new Map<string, number>(); let unnamed = 0;
  caught.faces.forEach(({ face }) => { if (face.feature) names.set(face.feature, (names.get(face.feature) || 0) + 1); else unnamed++; });
  const parts = [...names].map(([name, n]) => n === 1 ? name : `${name} ×${n}`);
  if (unnamed) parts.push(unnamed === caught.faces.length ? 'unnamed' : `${unnamed} unnamed`);
  return `${plural(caught.faces.length, 'face')}${parts.length ? ` (${parts.join(', ')})` : ''} and ${plural(caught.points.length, 'corner point')}`;
}

/* ---------- Note pins ---------- */

export type Pin = { id: string; instance: string; point: Vec; normal: Vec; note: string; feature: string | null; face: number | null };
export const MAX_NOTE = 280;   // engine/pins.py MAX_NOTE
const round = (n: number) => Math.abs(n) < 0.05 ? '0.0' : n.toFixed(1);

export function describePin(pin: Pin) {
  const where = pin.feature ? `the "${pin.feature}" feature of body "${pin.instance}"` : `body "${pin.instance}"`;
  return `a note pinned on ${where} at (${pin.point.map(round).join(', ')}) mm: "${pin.note}"`;
}

/* ---------- Payload ---------- */

export type ToolPayload = Omit<SelectionPayload, 'picks' | 'measurement'> & {
  picks: (SelectionPayload['picks'][number] & { enclosed?: { faces: { instance: string; face: number; feature: string | null; kind: string }[]; points: { instance: string; point: Vec }[] } })[];
  measurement: (NonNullable<SelectionPayload['measurement']> & { angle: number | null }) | null;
  pins: (Pin & { description: string })[];
};

/** The #25 payload plus the tools' additions: each lasso's catch, the measured angle and the version's pins. */
export function withTools(payload: SelectionPayload, picks: Pick[], pins: Pin[], measured: Measurement | null): ToolPayload {
  return {
    ...payload,
    picks: payload.picks.map((entry, i) => {
      const caught = picks[i]?.enclosed;
      if (!caught) return entry;
      return { ...entry, description: `${entry.description}; it encloses ${catchWords(caught)}`,
        enclosed: { faces: caught.faces.map(({ instance, face }) => ({ instance, face: face.id, feature: face.feature, kind: face.kind })), points: caught.points } };
    }),
    measurement: payload.measurement ? { ...payload.measurement, angle: measured?.angle == null ? null : Math.round(measured.angle * 10) / 10 } : null,
    pins: pins.map(pin => ({ ...pin, description: describePin(pin) })),
  };
}
