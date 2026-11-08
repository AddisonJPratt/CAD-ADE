/** The face map the harness writes beside each STL (`<part>.faces.json`), and how a pick finds its face in it.
 *
 * The mesh carries no face identity, so a pick is matched geometrically: the clicked point lies on
 * the B-rep face it came from, and a flat pick also knows its plane. The map's keys are tied to the
 * worker's export by the committed fixture `tests/fixtures/faces_map/plate.faces.json`.
 */
export type Vec3 = [number, number, number];
export type FaceRecord = {
  id: number; kind: string; feature: string | null;
  centre: Vec3; normal: Vec3 | null; axis: { origin: Vec3; direction: Vec3 } | null;
  radius?: number; area: number; bbox: { min: Vec3; max: Vec3 };
};
/** A feature's driving PARAMS at the values this model was built with: {param: value}. */
export type FeatureParameters = Record<string, number>;
export type FaceMap = { part: string; features: string[]; parameters: Record<string, FeatureParameters>; faces: FaceRecord[] };

export const FACE_KEYS = ['id', 'kind', 'feature', 'centre', 'normal', 'axis', 'area', 'bbox'] as const;
const PLANE_DOT = 0.97;        // cos 14°: the pick's normal must agree with the face's
const BASE_TOLERANCE = 0.5;    // mm, plus a share of the part's size, for bbox containment and coplanarity
const SIZE_SHARE = 0.005;

const isVec = (v: unknown): v is Vec3 => Array.isArray(v) && v.length === 3 && v.every(n => typeof n === 'number' && Number.isFinite(n));

export function parseFaceMap(data: unknown): FaceMap {
  const map = data as Record<string, unknown>;
  if (!map || typeof map !== 'object' || typeof map.part !== 'string') throw new Error('face map: missing part');
  if (!Array.isArray(map.features) || !map.features.every(f => typeof f === 'string')) throw new Error('face map: missing features');
  if (!Array.isArray(map.faces)) throw new Error('face map: missing faces');
  // Optional: maps exported before driving parameters existed have none.
  const parameters = (map.parameters ?? {}) as Record<string, unknown>;
  if (typeof parameters !== 'object' || Array.isArray(parameters)
    || !Object.values(parameters).every(p => p && typeof p === 'object' && !Array.isArray(p) && Object.values(p).every(v => typeof v === 'number' && Number.isFinite(v))))
    throw new Error('face map: malformed parameters');
  const faces = map.faces.map((raw, i) => {
    const face = raw as Record<string, unknown>;
    for (const key of FACE_KEYS) if (!(key in face)) throw new Error(`face map: face ${i} missing ${key}`);
    if (typeof face.id !== 'number' || typeof face.kind !== 'string' || typeof face.area !== 'number') throw new Error(`face map: face ${i} malformed`);
    if (face.feature !== null && typeof face.feature !== 'string') throw new Error(`face map: face ${i} feature`);
    if (!isVec(face.centre) || (face.normal !== null && !isVec(face.normal))) throw new Error(`face map: face ${i} geometry`);
    const bbox = face.bbox as { min: unknown; max: unknown };
    if (!bbox || !isVec(bbox.min) || !isVec(bbox.max)) throw new Error(`face map: face ${i} bbox`);
    const axis = face.axis as { origin: unknown; direction: unknown } | null;
    if (axis !== null && (!axis || !isVec(axis.origin) || !isVec(axis.direction))) throw new Error(`face map: face ${i} axis`);
    return { id: face.id, kind: face.kind, feature: face.feature, centre: face.centre, normal: face.normal, axis: axis as FaceRecord['axis'],
      area: face.area, bbox: { min: bbox.min, max: bbox.max }, ...(typeof face.radius === 'number' ? { radius: face.radius } : {}) } as FaceRecord;
  });
  return { part: map.part, features: map.features as string[], parameters: parameters as FaceMap['parameters'], faces };
}

function extent(map: FaceMap) {
  let size = 0;
  for (const f of map.faces) size = Math.max(size, ...f.bbox.max.map((v, k) => v - f.bbox.min[k]));
  return size;
}
const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const length = (a: Vec3) => Math.hypot(a[0], a[1], a[2]);
const contains = (f: FaceRecord, p: Vec3, tol: number) => p.every((v, k) => v >= f.bbox.min[k] - tol && v <= f.bbox.max[k] + tol);

/** The B-rep face a pick lies on: `point` is on the surface; `normal` and `flat` come from the mesh region when known. */
export function faceAt(map: FaceMap | undefined, point: Vec3, normal: Vec3 | null = null, flat: boolean | null = null): FaceRecord | null {
  if (!map || !map.faces.length) return null;
  const tol = BASE_TOLERANCE + SIZE_SHARE * extent(map);
  const near = map.faces.filter(f => contains(f, point, tol));
  if (!near.length) return null;
  let preferred: FaceRecord[] = near;
  if (flat === true && normal) {
    preferred = near.filter(f => f.kind === 'plane' && f.normal && Math.abs(dot(f.normal, normal)) > PLANE_DOT && Math.abs(dot(f.normal, sub(point, f.centre))) < tol);
  } else if (flat === false) {
    preferred = near.filter(f => f.kind !== 'plane');
  }
  if (preferred.length) return preferred.reduce((best, f) => f.area < best.area ? f : best);
  // No face of the expected kind under the point: the closest centre among the faces whose extent holds it.
  return near.reduce((best, f) => length(sub(point, f.centre)) < length(sub(point, best.centre)) ? f : best);
}

/** The parameters that drive the feature a face belongs to; none for an unnamed face. */
export function featureParameters(map: FaceMap | undefined, face: FaceRecord | null | undefined): FeatureParameters {
  return (face?.feature && map?.parameters[face.feature]) || {};
}

const number = (v: number) => String(Math.round(v * 100) / 100);
const DIAMETER = /(^|_)(d|dia|diam|diameter)$/i;
const RADIUS = /(^|_)(r|rad|radius)$/i;

/** The first (most telling) driving parameter as a drawing would print it: Ø4, R1.5, or "pocket depth 3". */
export function parameterText(parameters: FeatureParameters) {
  const [first] = Object.entries(parameters);
  if (!first) return '';
  const [name, value] = first;
  if (DIAMETER.test(name)) return `Ø${number(value)}`;
  if (RADIUS.test(name)) return `R${number(value)}`;
  return `${name.replace(/_/g, ' ')} ${number(value)}`;
}
