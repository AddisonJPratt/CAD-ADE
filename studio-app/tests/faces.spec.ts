import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { FACE_KEYS, faceAt, featureParameters, parameterText, parseFaceMap } from '../src/Features';
import { describe, label, selectionPayload, type Pick } from '../src/Selection';
import { BufferGeometry } from 'three';

const repo = (path: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../${path}`, import.meta.url)), 'utf8'));
const fixture = repo('tests/fixtures/faces_map/plate.faces.json');
const map = parseFaceMap(fixture);
const pick = (extra: Partial<Pick>): Pick => ({ id: 'p', kind: 'face', body: 'plate', point: [0, 0, 9], normal: [0, 0, 1], centroid: [0, 0, 9], area: 64, flat: true, geometry: new BufferGeometry(), ...extra });

test('the face map fixture parses and every face carries the keys the worker writes', () => {
  expect(map.part).toBe('plate');
  expect(map.features).toEqual(['lid pocket', 'mount hole']);
  for (const face of fixture.faces) expect(Object.keys(face)).toEqual(expect.arrayContaining([...FACE_KEYS]));
  expect(() => parseFaceMap({ ...fixture, faces: [{ id: 0 }] })).toThrow(/missing kind/);
  expect(() => parseFaceMap({ part: 'x' })).toThrow(/missing features/);
  // Each feature carries the parameters that drive it, at their built values.
  expect(map.parameters).toEqual({ 'lid pocket': { pocket_depth: 3 }, 'mount hole': { hole_dia: 4 } });
  // A map from before driving parameters were exported still parses, with none.
  const { parameters: _, ...older } = fixture;
  expect(parseFaceMap(older).parameters).toEqual({});
  expect(() => parseFaceMap({ ...fixture, parameters: { 'lid pocket': { pocket_depth: 'deep' } } })).toThrow(/parameters/);
});

test('a picked face knows the parameters that drive its feature; an unnamed face has none', () => {
  expect(featureParameters(map, faceAt(map, [13, 11, 4]))).toEqual({ hole_dia: 4 });
  expect(featureParameters(map, faceAt(map, [2, -18, 5], [0, -1, 0], true))).toEqual({});
  expect(featureParameters(map, null)).toEqual({});
  expect(featureParameters(undefined, faceAt(map, [13, 11, 4]))).toEqual({});
});

test('the chip reads a driving parameter the way a drawing would', () => {
  expect(parameterText({ hole_dia: 4 })).toBe('Ø4');
  expect(parameterText({ boss_d: 3.2, boss_h: 8 })).toBe('Ø3.2');
  expect(parameterText({ fillet_r: 1.5 })).toBe('R1.5');
  expect(parameterText({ pocket_depth: 3 })).toBe('pocket depth 3');
  expect(parameterText({ wall: 1.234567 })).toBe('wall 1.23');
  expect(parameterText({})).toBe('');
});

test('a click on a labelled face names its feature, flat or curved', () => {
  // The pocket floor: a flat pick anywhere on it, with its plane normal.
  expect(faceAt(map, [1.5, -2, 9], [0, 0, 1], true)?.feature).toBe('lid pocket');
  // A pocket wall, picked with the mesh's (outward from the material) normal.
  expect(faceAt(map, [9, 1, 10.5], [-1, 0, 0], true)?.feature).toBe('lid pocket');
  // The hole: a curved patch, so the plane test is skipped and the cylinder wins.
  expect(faceAt(map, [13, 11, 4], [-0.2, -0.98, 0], false)?.feature).toBe('mount hole');
  // A point pick with no region information still lands on the hole wall.
  expect(faceAt(map, [13, 11, 4])?.feature).toBe('mount hole');
});

test('an unlabelled face falls back to its geometry', () => {
  const front = faceAt(map, [2, -18, 5], [0, -1, 0], true);
  expect(front?.feature).toBeNull();
  expect(front?.kind).toBe('plane');
  expect(front?.normal).toEqual([0, -1, 0]);
  // The top face around the pocket is not the pocket floor, although both face up.
  expect(faceAt(map, [-12, -12, 12], [0, 0, 1], true)?.feature).toBeNull();
  expect(faceAt(map, [0, 0, 9], [0, 0, 1], true)?.feature).toBe('lid pocket');
  // Off the part entirely: nothing to name, and no map at all is the same.
  expect(faceAt(map, [80, 80, 80], [0, 0, 1], true)).toBeNull();
  expect(faceAt(undefined, [0, 0, 9], [0, 0, 1], true)).toBeNull();
});

test('chips and the agent text use the feature name, and the payload carries both forms', () => {
  const floor = pick({ feature: 'lid pocket', parameters: { pocket_depth: 3 }, face: faceAt(map, [0, 0, 9], [0, 0, 1], true)! });
  const hole = pick({ feature: 'mount hole', parameters: { hole_dia: 4 }, flat: false, point: [13, 11, 4], normal: [-0.2, -0.98, 0], centroid: [13, 11, 4], area: 6 });
  const front = pick({ feature: null, parameters: {}, point: [2, -18, 5], normal: [0, -1, 0], centroid: [0, -18, 6], area: 432, locked: true, note: 'keep flat' });
  expect(label(floor)).toBe('Lid pocket, pocket depth 3 · plate');
  expect(label(hole)).toBe('Mount hole Ø4 · plate');
  expect(label(pick({ feature: 'lid pocket' }))).toBe('Lid pocket · plate');
  expect(label(front)).toBe('Keep: Face on plate · front');
  expect(describe(floor)).toBe('a flat face on the "lid pocket" feature of body "plate" (driven by pocket_depth = 3) facing up (+Z), area ≈ 64 mm², centred at (0.0, 0.0, 9.0) mm');
  expect(describe(front)).toBe('KEEP UNCHANGED: a flat face on body "plate" facing front (−Y), area ≈ 432 mm², centred at (0.0, -18.0, 6.0) mm (note: "keep flat")');
  const body = pick({ kind: 'body', features: map.features });
  expect(describe(body)).toBe('the whole body "plate" (named features: lid pocket, mount hole)');
  const payload = selectionPayload('named_features.py', [floor, front], { value: 18.2483, kind: 'centre to centre', from: [0, 0, 9], to: [0, -18, 6] });
  expect(payload.design).toBe('named_features.py');
  expect(payload.picks.map(p => [p.instance, p.feature, p.parameters, p.face, p.locked, p.note])).toEqual([['plate', 'lid pocket', { pocket_depth: 3 }, floor.face!.id, false, null], ['plate', null, {}, null, true, 'keep flat']]);
  expect(describe(hole)).toContain('the "mount hole" feature of body "plate" (driven by hole_dia = 4)');
  expect(payload.picks[0].description).toBe(describe(floor));
  expect(payload.measurement).toEqual({ value: 18.25, kind: 'centre to centre', from: [0, 0, 9], to: [0, -18, 6] });
  expect(selectionPayload('named_features.py', [body], null).picks[0].features).toEqual(['lid pocket', 'mount hole']);
});
