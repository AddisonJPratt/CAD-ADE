// The assembly manifest (assembly/manifest.schema.json), as Studio reads it.
// The engine derives every value; Studio never computes placements, explode directions,
// quantities or step order. Lengths mm, angles degrees, everything in the assembly frame.
// Each *_KEYS list must equal its interface's keys (checked by tsc below) and the schema's
// `required` list (checked by tests/manifest.spec.ts), so the three cannot drift apart.

export type Vec3 = [number, number, number];
export type Quaternion = [number, number, number, number]; // [x, y, z, w], three.js order

export interface Transform { position: Vec3; quaternion: Quaternion }

export interface Instance {
  id: string;
  name: string;
  kind: 'printed' | 'hardware' | 'component';
  source: string;
  parent: string | null;
  transform: Transform;
  mesh: string; // relative to the manifest; the mesh is in the instance's local frame
}

export interface Joint {
  id: string;
  type: 'fixed' | 'revolute' | 'prismatic';
  role: 'fastener' | 'press' | 'clamp';
  parent: string;
  child: string;
  origin: Vec3;
  axis: Vec3;
  rest: number;
  range: [number, number] | null; // null until motion is declared
}

export interface ExplodeRow { instance: string; direction: Vec3; distance: number; offset: Vec3 }

export interface Step {
  number: number;
  text: string;
  part_ids: string[];
  joints: string[];
  tool: string | null;
  callout: string | null;
}

export interface BomRow {
  name: string;
  category: 'Printed part' | 'Hardware' | 'Purchased component';
  source: string;
  part_ids: string[];
  quantity: number;
}

export interface Provenance { assembly_file: string; sources: Record<string, string>; physical_assembly_tested: boolean }

export interface AssemblyManifest {
  schema_version: 1;
  id: string;
  name: string;
  units: 'mm';
  angle_units: 'deg';
  pass: boolean;
  gate: 'PASS' | 'FAIL';
  disclaimer: string;
  params: Record<string, number>;
  provenance: Provenance;
  instances: Instance[];
  joints: Joint[];
  explode: ExplodeRow[];
  steps: Step[];
  bom: BomRow[];
  warnings: string[];
}

export const MANIFEST_KEYS = ['schema_version', 'id', 'name', 'units', 'angle_units', 'pass', 'gate', 'disclaimer',
  'params', 'provenance', 'instances', 'joints', 'explode', 'steps', 'bom', 'warnings'] as const satisfies readonly (keyof AssemblyManifest)[];
export const INSTANCE_KEYS = ['id', 'name', 'kind', 'source', 'parent', 'transform', 'mesh'] as const satisfies readonly (keyof Instance)[];
export const JOINT_KEYS = ['id', 'type', 'role', 'parent', 'child', 'origin', 'axis', 'rest', 'range'] as const satisfies readonly (keyof Joint)[];
export const EXPLODE_KEYS = ['instance', 'direction', 'distance', 'offset'] as const satisfies readonly (keyof ExplodeRow)[];
export const STEP_KEYS = ['number', 'text', 'part_ids', 'joints', 'tool', 'callout'] as const satisfies readonly (keyof Step)[];
export const BOM_KEYS = ['name', 'category', 'source', 'part_ids', 'quantity'] as const satisfies readonly (keyof BomRow)[];

// A key added to an interface but not to its list fails to compile here.
type Covers<T, L extends readonly unknown[]> = [Exclude<keyof T, L[number]>] extends [never] ? true : never;
export const KEYS_COVER_TYPES: [Covers<AssemblyManifest, typeof MANIFEST_KEYS>, Covers<Instance, typeof INSTANCE_KEYS>,
  Covers<Joint, typeof JOINT_KEYS>, Covers<ExplodeRow, typeof EXPLODE_KEYS>, Covers<Step, typeof STEP_KEYS>,
  Covers<BomRow, typeof BOM_KEYS>] = [true, true, true, true, true, true];

function fail(where: string, message: string): never { throw new Error(`assembly manifest ${where}: ${message}`); }

function record(value: unknown, keys: readonly string[], where: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) fail(where, 'expected an object');
  const missing = keys.filter(k => !(k in value));
  if (missing.length) fail(where, `missing ${missing.join(', ')}`);
  return value as Record<string, unknown>;
}

function list(value: unknown, keys: readonly string[], where: string) {
  if (!Array.isArray(value)) fail(where, 'expected a list');
  value.forEach((item, i) => record(item, keys, `${where}[${i}]`));
}

/** Shape check for the manifest the engine wrote. The engine's validator owns the cross-references. */
export function parseManifest(value: unknown): AssemblyManifest {
  const data = record(value, MANIFEST_KEYS, 'root');
  if (data.schema_version !== 1) fail('schema_version', `unsupported version ${String(data.schema_version)}`);
  if (data.units !== 'mm') fail('units', 'must be mm');
  list(data.instances, INSTANCE_KEYS, 'instances');
  list(data.joints, JOINT_KEYS, 'joints');
  list(data.explode, EXPLODE_KEYS, 'explode');
  list(data.steps, STEP_KEYS, 'steps');
  list(data.bom, BOM_KEYS, 'bom');
  return data as unknown as AssemblyManifest;
}

/** Where an instance sits at explode fraction t (0 assembled, 1 fully exploded). */
export function explodedPosition(manifest: AssemblyManifest, id: string, t: number): Vec3 {
  const instance = manifest.instances.find(i => i.id === id) ?? fail('instances', `no instance ${id}`);
  const row = manifest.explode.find(r => r.instance === id) ?? fail('explode', `no row for ${id}`);
  const [x, y, z] = instance.transform.position;
  return [x + row.offset[0] * t, y + row.offset[1] * t, z + row.offset[2] * t];
}
