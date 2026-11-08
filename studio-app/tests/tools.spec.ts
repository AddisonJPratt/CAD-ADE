// Outline, note pin and measure tools (#26): the pure parts, on real harness exports.
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { BufferGeometry, Vector3 } from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { parseFaceMap, faceAt } from '../src/Features';
import { analyse, regionAt, selectionPayload, type Pick, type Vec } from '../src/Selection';
import { describePin, enclosed, measureBetween, measureSentence, measureText, toolLabel, withTools, type Pin } from '../src/Tools';

const file = (path: string) => fileURLToPath(new URL(`../../${path}`, import.meta.url));
const stl = (path: string) => { const bytes = readFileSync(file(path)); return new STLLoader().parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)); };
const json = (path: string) => JSON.parse(readFileSync(file(path), 'utf8'));
const gate = json('tests/fixtures/measure/gate.json');
const bodies = { base: stl('tests/fixtures/measure/base.stl'), riser: stl('tests/fixtures/measure/riser.stl') };
const maps = { base: parseFaceMap(json('tests/fixtures/measure/base.faces.json')), riser: parseFaceMap(json('tests/fixtures/measure/riser.faces.json')) };

/** A face pick the way Studio makes one on a click at `at`: the hit triangle's region, matched to the face map. */
function facePick(body: 'base' | 'riser', at: Vec, withMap = true): Pick {
  const geometry = bodies[body]; const a = analyse(geometry); const p = new Vector3(...at);
  const t = [...Array(a.count).keys()].find(i => {
    const [x, y, z] = a.tri(i); const n = a.normal[i];
    if (Math.abs(n.dot(p.clone().sub(x))) > 1e-6) return false;
    // Inside the triangle: the point is on the inner side of all three edges.
    return [[x, y], [y, z], [z, x]].every(([u, v]) => v.clone().sub(u).cross(p.clone().sub(u)).dot(n) >= -1e-9);
  });
  if (t === undefined) throw new Error(`no triangle of ${body} holds ${at}`);
  const r = regionAt(geometry, t, p);
  const face = withMap ? faceAt(maps[body], at, r.normal.toArray() as Vec, r.flat) : null;
  return { id: `${body}-${t}`, kind: 'face', body, geometry, point: at, region: r.region, area: r.area, flat: r.flat,
    normal: r.normal.toArray() as Vec, centroid: r.centroid.toArray() as Vec, feature: face?.feature ?? null, face: face ?? undefined };
}
// Points a user can click: the riser's top, the base's top ledge outside the riser's footprint, and side faces.
const RISER_TOP: Vec = [3, -4, 21.5], LEDGE: Vec = [15, 2, 8];

test('the measured gap between the riser top and the base ledge matches the gate within 0.1 mm', () => {
  const expected = gate.dimensions.find((d: { name: string }) => d.name === 'riser_height').measured;
  expect(expected).toBe(13.5);
  const top = facePick('riser', RISER_TOP), shelf = facePick('base', LEDGE);
  expect(top.face?.kind).toBe('plane'); expect(shelf.face?.kind).toBe('plane');
  const m = measureBetween(top, shelf);
  expect(m.kind).toBe('gap between parallel faces');
  expect(Math.abs(m.value - expected)).toBeLessThanOrEqual(0.1);
  expect(m.angle).toBeCloseTo(0, 6);
  // Order does not matter, and without a face map the mesh planes give the same reading.
  expect(Math.abs(measureBetween(shelf, top).value - expected)).toBeLessThanOrEqual(0.1);
  expect(Math.abs(measureBetween(facePick('riser', RISER_TOP, false), facePick('base', LEDGE, false)).value - expected)).toBeLessThanOrEqual(0.1);
  // The dimension line runs square to both faces.
  expect(m.from[0]).toBeCloseTo(m.to[0], 6); expect(m.from[1]).toBeCloseTo(m.to[1], 6);
});

test('the angle between two faces is reported, and non-parallel faces measure centre to centre', () => {
  const top = facePick('riser', RISER_TOP);
  const side = facePick('riser', [11, 1, 15]);
  const m = measureBetween(top, side);
  expect(m.kind).toBe('centre to centre');
  expect(m.angle).toBeCloseTo(90, 6);
  const front = facePick('base', [5, -20, 4]);
  expect(measureBetween(side, front).angle).toBeCloseTo(90, 6);
  // Words: one decimal everywhere; the angle only when the faces are not parallel.
  expect(measureSentence(m)).toBe(`Faces at 90.0° · centres ${m.value.toFixed(1)} mm apart`);
  expect(measureText(m)).toBe(`${m.value.toFixed(1)} mm · 90.0°`);
  const gap = measureBetween(facePick('riser', RISER_TOP), facePick('base', LEDGE));
  expect(measureSentence(gap)).toBe('Gap between parallel faces 13.5 mm');
  expect(measureText(gap)).toBe('13.5 mm');
  // A body pick has no plane: distance only.
  const body: Pick = { ...top, id: 'b', kind: 'body', features: [] };
  expect(measureBetween(body, side).angle).toBeNull();
});

test('the lasso encloses the faces and corner points inside the drawn region', () => {
  // Looking straight down (+Z up the screen is Y): project x,y to pixels at 10 px per mm.
  const project = (v: Vector3): [number, number] => [400 + v.x * 10, 300 - v.y * 10];
  const eye = new Vector3(0, 0, 500);
  // A loop just around the riser's footprint (22 mm square): its top face and four top corners.
  const around: [number, number][] = [[400 - 125, 300 - 125], [400 + 125, 300 - 125], [400 + 125, 300 + 125], [400 - 125, 300 + 125]];
  const riser = enclosed(bodies.riser, around, project, eye, maps.riser, 'riser');
  expect(riser.faces.map(f => [f.instance, f.face.kind, f.face.normal])).toEqual([['riser', 'plane', [0, 0, 1]]]);
  expect(riser.points.map(p => p.point).sort()).toEqual([[-11, -11, 21.5], [-11, 11, 21.5], [11, -11, 21.5], [11, 11, 21.5]].sort());
  // The base's top face is mostly outside that loop and hidden under the riser where it is inside.
  const hidden = (v: Vector3) => !(Math.abs(v.x) < 11 && Math.abs(v.y) < 11 && v.z < 21.5);
  expect(enclosed(bodies.base, around, project, eye, maps.base, 'base', hidden).faces).toEqual([]);
  // A loop around the whole model takes the base top and its four top corners too.
  const all: [number, number][] = [[0, 0], [800, 0], [800, 600], [0, 600]];
  const base = enclosed(bodies.base, all, project, eye, maps.base, 'base', hidden);
  expect(base.faces.map(f => f.face.normal)).toEqual([[0, 0, 1]]);
  expect(base.points).toHaveLength(4);
  // Without a face map, faces cannot be named but corners still count.
  const unnamed = enclosed(bodies.riser, around, project, eye, undefined, 'riser');
  expect(unnamed.faces).toEqual([]); expect(unnamed.points).toHaveLength(4);
});

test('pins and enclosed faces ride in the selection payload the agent receives', () => {
  const pin: Pin = { id: 'pin-1', instance: 'riser', point: [2, -3, 21.5], normal: [0, 0, 1], note: 'Round this corner', feature: null, face: 4 };
  expect(describePin(pin)).toBe('a note pinned on body "riser" at (2.0, -3.0, 21.5) mm: "Round this corner"');
  expect(describePin({ ...pin, feature: 'lid pocket', instance: 'plate' })).toBe('a note pinned on the "lid pocket" feature of body "plate" at (2.0, -3.0, 21.5) mm: "Round this corner"');
  const project = (v: Vector3): [number, number] => [400 + v.x * 10, 300 - v.y * 10];
  const loop: [number, number][] = [[275, 175], [525, 175], [525, 425], [275, 425]];
  const inside = enclosed(bodies.riser, loop, project, new Vector3(0, 0, 500), maps.riser, 'riser');
  const area: Pick = { id: 'a', kind: 'area', body: 'riser', geometry: new BufferGeometry(), point: [0, 0, 21.5], normal: [0, 0, 1], centroid: [0, 0, 21.5], area: 484, flat: false, enclosed: inside };
  expect(toolLabel(area)).toBe('Circled area on riser · 1 face, 4 corners');
  expect(toolLabel({ ...area, enclosed: { faces: inside.faces, points: [] } })).toBe('Circled area on riser · 1 face');
  const top = facePick('riser', RISER_TOP), shelf = facePick('base', LEDGE);
  const m = measureBetween(top, shelf);
  const payload = withTools(selectionPayload('stepped_blocks.py', [area], m), [area], [pin], m);
  expect(payload.pins).toEqual([{ ...pin, description: describePin(pin) }]);
  expect(payload.picks[0].enclosed).toEqual({ faces: [{ instance: 'riser', face: inside.faces[0].face.id, feature: null, kind: 'plane' }], points: inside.points.map(p => ({ instance: 'riser', point: p.point })) });
  expect(payload.picks[0].description).toMatch(/; it encloses 1 face \(unnamed\) and 4 corner points$/);
  expect(payload.measurement).toEqual({ value: 13.5, kind: 'gap between parallel faces', from: payload.measurement!.from, to: payload.measurement!.to, angle: 0 });
  // Nothing extra when there is nothing to add: the #25 payload is unchanged apart from an empty pin list.
  const plain = selectionPayload('stepped_blocks.py', [top], null);
  expect(withTools(plain, [top], [], null)).toEqual({ ...plain, pins: [] });
});
