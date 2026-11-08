import { useMemo } from 'react';
import { BufferAttribute, BufferGeometry, DoubleSide, EdgesGeometry, Vector3 } from 'three';
import type { FaceRecord } from './Features';

export type PickKind = 'body' | 'face' | 'area' | 'point';
export type Vec = [number, number, number];
export type Pick = {
  id: string; kind: PickKind; body: string;
  point: Vec; normal: Vec; centroid: Vec;
  area?: number; flat?: boolean; region?: Float32Array; geometry: BufferGeometry;
  note?: string; locked?: boolean; loop?: Float32Array;
  /** From the harness face map: the named feature this pick lies on (null when the face is unnamed), the B-rep face, and for a body its feature names. */
  feature?: string | null; face?: FaceRecord; features?: string[];
  /** A lasso's catch (#26): every visible B-rep face and corner point inside the drawn loop, on any body. */
  enclosed?: Enclosure;
};
export type Enclosure = { faces: { instance: string; face: FaceRecord }[]; points: { instance: string; point: Vec }[] };

const round = (n: number) => Math.abs(n) < 0.05 ? '0.0' : n.toFixed(1);
const toVec = (v: Vector3) => v.toArray() as Vec;

/* ---------- Geometry analysis (cached per mesh) ---------- */

type Analysis = { count: number; tri: (t: number) => [Vector3, Vector3, Vector3]; normal: Vector3[]; area: number[]; centre: Vector3[]; cluster: Int32Array; members: number[][]; size: number };
const cache = new WeakMap<BufferGeometry, Analysis>();

/** Triangles grouped into flat faces: same plane, two or more triangles. Lone triangles are curved surface. */
export function analyse(geometry: BufferGeometry): Analysis {
  const known = cache.get(geometry); if (known) return known;
  const pos = geometry.getAttribute('position').array; const index = geometry.getIndex()?.array;
  const count = (index ? index.length : pos.length / 3) / 3;
  const vertex = (i: number) => new Vector3(pos[3 * i], pos[3 * i + 1], pos[3 * i + 2]);
  const tri = (t: number) => [0, 1, 2].map(k => vertex(index ? index[3 * t + k] : 3 * t + k)) as [Vector3, Vector3, Vector3];
  geometry.computeBoundingBox(); const size = geometry.boundingBox!.getSize(new Vector3()).length() || 1;
  const normal: Vector3[] = [], area: number[] = [], centre: Vector3[] = [];
  const planes = new Map<string, number[]>();
  for (let t = 0; t < count; t++) {
    const [a, b, c] = tri(t); const cross = b.clone().sub(a).cross(c.clone().sub(a));
    const n = cross.clone().normalize(); normal.push(n); area.push(cross.length() / 2); centre.push(a.clone().add(b).add(c).divideScalar(3));
    const key = `${n.x.toFixed(3)},${n.y.toFixed(3)},${n.z.toFixed(3)},${(n.dot(a) / size).toFixed(4)}`;
    (planes.get(key) || planes.set(key, []).get(key)!).push(t);
  }
  const cluster = new Int32Array(count).fill(-1); const members: number[][] = [];
  planes.forEach(list => { if (list.length < 2) return; const id = members.push(list) - 1; list.forEach(t => { cluster[t] = id; }); });
  const result = { count, tri, normal, area, centre, cluster, members, size };
  cache.set(geometry, result); return result;
}

function pack(geometry: BufferGeometry, triangles: number[]) {
  const a = analyse(geometry); const out = new Float32Array(triangles.length * 9); let area = 0; const c = new Vector3(); const n = new Vector3();
  triangles.forEach((t, i) => { a.tri(t).forEach((v, k) => out.set([v.x, v.y, v.z], i * 9 + k * 3)); area += a.area[t]; c.addScaledVector(a.centre[t], a.area[t]); n.addScaledVector(a.normal[t], a.area[t]); });
  return { region: out, area, centroid: area ? c.divideScalar(area) : c, normal: n.normalize() };
}

/** The flat face under the cursor, or on a curved surface the patch of similar facing around it. */
export function regionAt(geometry: BufferGeometry, faceIndex: number, hit: Vector3) {
  const a = analyse(geometry); const id = a.cluster[faceIndex];
  if (id >= 0) return { ...pack(geometry, a.members[id]), flat: true };
  const n0 = a.normal[faceIndex], radius = a.size * 0.12, list: number[] = [];
  for (let t = 0; t < a.count; t++) if (t === faceIndex || (a.normal[t].dot(n0) > Math.cos(Math.PI / 9) && a.centre[t].distanceTo(hit) < radius)) list.push(t);
  return { ...pack(geometry, list), flat: false };
}

/** Front-facing triangles whose centres fall inside a screen-space lasso. `project` maps a point to screen pixels. */
export function circled(geometry: BufferGeometry, polygon: [number, number][], project: (v: Vector3) => [number, number], eye: Vector3) {
  const a = analyse(geometry); const list: number[] = [];
  for (let t = 0; t < a.count; t++) {
    if (a.normal[t].dot(eye.clone().sub(a.centre[t])) <= 0) continue;
    if (inside(project(a.centre[t]), polygon)) list.push(t);
  }
  return list.length ? pack(geometry, list) : null;
}

function inside([x, y]: [number, number], poly: [number, number][]) {
  let hit = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
}

/** Area enclosed by a 3D loop that lies roughly on one surface (vector shoelace). */
export function loopArea(loop: Vector3[]) {
  const sum = new Vector3();
  for (let i = 0; i < loop.length; i++) sum.add(loop[i].clone().cross(loop[(i + 1) % loop.length]));
  return sum.length() / 2;
}

/** Distance between two picks: plane-to-plane for parallel flat faces, otherwise centre to centre. */
export function measure(a: Pick, b: Pick) {
  const ca = new Vector3(...a.centroid), cb = new Vector3(...b.centroid), na = new Vector3(...a.normal), nb = new Vector3(...b.normal);
  if (a.kind !== 'body' && b.kind !== 'body' && a.flat && b.flat && Math.abs(na.dot(nb)) > 0.999) {
    const d = na.dot(cb.clone().sub(ca));
    return { value: Math.abs(d), from: toVec(ca), to: toVec(ca.clone().addScaledVector(na, d)), kind: 'gap between parallel faces' as const };
  }
  return { value: ca.distanceTo(cb), from: toVec(ca), to: toVec(cb), kind: 'centre to centre' as const };
}

/* ---------- Words ---------- */

function facing([x, y, z]: Vec) {
  const axes: [number, string][] = [[x, x > 0 ? 'right (+X)' : 'left (−X)'], [y, y > 0 ? 'back (+Y)' : 'front (−Y)'], [z, z > 0 ? 'up (+Z)' : 'down (−Z)']];
  const [value, name] = axes.reduce((best, axis) => Math.abs(axis[0]) > Math.abs(best[0]) ? axis : best);
  return Math.abs(value) > 0.97 ? name : `mostly ${name}`;
}

const title = (name: string) => name.replace(/^./, c => c.toUpperCase());

/** Chip text: the feature's name when the harness named the face, otherwise where the pick is. */
export function label(pick: Pick) {
  const name = pick.feature ? title(pick.feature) : null;
  const base = pick.kind === 'body' ? `Body ${pick.body}`
    : pick.kind === 'area' ? `Circled area on ${name ? `${pick.feature}, ${pick.body}` : pick.body}`
    : pick.kind === 'point' ? `Point on ${name ? `${pick.feature}, ${pick.body}` : pick.body}`
    : name ? `${name} · ${pick.body}` : `${pick.flat === false ? 'Surface' : 'Face'} on ${pick.body} · ${facing(pick.normal).split(' (')[0]}`;
  return pick.locked ? `Keep: ${base}` : base;
}

/** What the assistant reads: the named feature when the harness exported one, else the face's geometry. */
export function describe(pick: Pick) {
  const [x, y, z] = pick.centroid.map(round);
  const named = pick.feature ? `the "${pick.feature}" feature of body "${pick.body}"` : null;
  const what = pick.kind === 'body' ? `the whole body "${pick.body}"${pick.features?.length ? ` (named features: ${pick.features.join(', ')})` : ''}`
    : pick.kind === 'point' ? `a point on ${named || `body "${pick.body}"`} at (${pick.point.map(round).join(', ')}) mm`
    : `${pick.kind === 'area' ? 'an area circled' : pick.flat === false ? 'a curved surface patch' : 'a flat face'} on ${named || `body "${pick.body}"`} facing ${facing(pick.normal)}, area ≈ ${Math.round(pick.area || 0)} mm², centred at (${x}, ${y}, ${z}) mm`;
  return `${pick.locked ? 'KEEP UNCHANGED: ' : ''}${what}${pick.note ? ` (note: "${pick.note}")` : ''}`;
}

/** The structured selection sent with a request: what the engine hands the agent adapter as-is. */
export type SelectionPayload = {
  design: string;
  picks: { instance: string; kind: PickKind; feature: string | null; features?: string[]; face: number | null; description: string;
    point: Vec; normal: Vec; centroid: Vec; area: number | null; flat: boolean | null; note: string | null; locked: boolean }[];
  measurement: { value: number; kind: string; from: Vec; to: Vec } | null;
};
const mm = (v: Vec): Vec => v.map(n => Math.round(n * 100) / 100) as Vec;
export function selectionPayload(design: string, picks: Pick[], measured: ReturnType<typeof measure> | null): SelectionPayload {
  return {
    design,
    picks: picks.map(pick => ({ instance: pick.body, kind: pick.kind, feature: pick.feature ?? null, ...(pick.kind === 'body' ? { features: pick.features ?? [] } : {}),
      face: pick.face?.id ?? null, description: describe(pick), point: mm(pick.point), normal: mm(pick.normal), centroid: mm(pick.centroid),
      area: pick.area == null ? null : Math.round(pick.area * 10) / 10, flat: pick.flat ?? null, note: pick.note ?? null, locked: !!pick.locked })),
    measurement: measured ? { value: Math.round(measured.value * 100) / 100, kind: measured.kind, from: mm(measured.from), to: mm(measured.to) } : null,
  };
}

/* ---------- Drawing ---------- */

function outline(region: Float32Array) {
  const key = (i: number) => `${region[i].toFixed(3)},${region[i + 1].toFixed(3)},${region[i + 2].toFixed(3)}`;
  const edges = new Map<string, number[]>();
  for (let t = 0; t < region.length; t += 9) for (const [p, q] of [[0, 3], [3, 6], [6, 0]]) {
    const a = key(t + p), b = key(t + q); const k = a < b ? `${a}|${b}` : `${b}|${a}`;
    if (edges.has(k)) edges.delete(k); else edges.set(k, [region[t + p], region[t + p + 1], region[t + p + 2], region[t + q], region[t + q + 1], region[t + q + 2]]);
  }
  const g = new BufferGeometry(); g.setAttribute('position', new BufferAttribute(new Float32Array([...edges.values()].flat()), 3)); return g;
}

export function Highlight({ pick, colour, hover = false }: { pick: Pick; colour: string; hover?: boolean }) {
  const shapes = useMemo(() => {
    if (pick.kind === 'body') return { fill: pick.geometry, edges: new EdgesGeometry(pick.geometry, 28) };
    if (pick.loop && pick.loop.length >= 9) {
      // The drawn loop, laid on the surface: a fan from its centre fills it, the loop itself outlines it.
      const c = pick.centroid, n = pick.loop.length / 3, fan: number[] = [], ring: number[] = [];
      for (let i = 0; i < n; i++) { const j = (i + 1) % n; fan.push(...c, pick.loop[3 * i], pick.loop[3 * i + 1], pick.loop[3 * i + 2], pick.loop[3 * j], pick.loop[3 * j + 1], pick.loop[3 * j + 2]); ring.push(pick.loop[3 * i], pick.loop[3 * i + 1], pick.loop[3 * i + 2], pick.loop[3 * j], pick.loop[3 * j + 1], pick.loop[3 * j + 2]); }
      const fill = new BufferGeometry(); fill.setAttribute('position', new BufferAttribute(new Float32Array(fan), 3));
      const edges = new BufferGeometry(); edges.setAttribute('position', new BufferAttribute(new Float32Array(ring), 3));
      return { fill, edges };
    }
    if (!pick.region) return null;
    const fill = new BufferGeometry(); fill.setAttribute('position', new BufferAttribute(pick.region, 3));
    return { fill, edges: outline(pick.region) };
  }, [pick]);
  const opacity = hover ? 0.16 : pick.locked ? 0.22 : pick.kind === 'body' ? 0.2 : 0.34;
  if (!shapes) return <mesh position={pick.point} renderOrder={4}><sphereGeometry args={[0.9, 16, 12]}/><meshBasicMaterial color={colour} depthTest={false}/></mesh>;
  return <group renderOrder={3}>
    <mesh geometry={shapes.fill} renderOrder={3}><meshBasicMaterial color={colour} transparent opacity={opacity} side={DoubleSide} depthWrite={false} polygonOffset polygonOffsetFactor={-2} polygonOffsetUnits={-2}/></mesh>
    {!hover && <lineSegments geometry={shapes.edges} renderOrder={4}><lineBasicMaterial color={colour} transparent opacity={pick.locked ? 0.6 : 0.95} depthTest={pick.kind === 'body'}/></lineSegments>}
  </group>;
}
