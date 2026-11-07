import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { BOM_KEYS, EXPLODE_KEYS, INSTANCE_KEYS, JOINT_KEYS, MANIFEST_KEYS, STEP_KEYS, explodedPosition, parseManifest } from '../src/assembly/manifest';

const repo = (path: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../${path}`, import.meta.url)), 'utf8'));
const schema = repo('assembly/manifest.schema.json');
const fixture = repo('tests/fixtures/assembly_manifest/holder_clip.json');

test('Studio key lists match the schema required lists', () => {
  const sorted = (keys: readonly string[]) => [...keys].sort();
  expect(sorted(MANIFEST_KEYS)).toEqual(sorted(schema.required));
  expect(sorted(INSTANCE_KEYS)).toEqual(sorted(schema.$defs.instance.required));
  expect(sorted(JOINT_KEYS)).toEqual(sorted(schema.$defs.joint.required));
  expect(sorted(EXPLODE_KEYS)).toEqual(sorted(schema.$defs.explode.required));
  expect(sorted(STEP_KEYS)).toEqual(sorted(schema.$defs.step.required));
  expect(sorted(BOM_KEYS)).toEqual(sorted(schema.$defs.bomRow.required));
});

test('the holder manifest fixture parses and explodes the screws away from the wall', () => {
  const manifest = parseManifest(fixture);
  expect(manifest.instances.map(i => [i.id, i.parent])).toEqual([['clip', null], ['screw_1', 'clip'], ['screw_2', 'clip']]);
  expect(explodedPosition(manifest, 'clip', 1)).toEqual([0, 0, 0]);
  const [x0] = explodedPosition(manifest, 'screw_1', 0);
  const [x1] = explodedPosition(manifest, 'screw_1', 1);
  expect(x0).toBeCloseTo(-22.45);
  expect(x1).toBeGreaterThan(x0);
});

test('a manifest from a newer schema or missing a field is refused', () => {
  expect(() => parseManifest({ ...fixture, schema_version: 2 })).toThrow(/unsupported version/);
  const { joints: _, ...noJoints } = fixture;
  expect(() => parseManifest(noJoints)).toThrow(/missing joints/);
});
