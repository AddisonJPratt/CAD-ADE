// A click on a flat face highlights the whole face, not a scatter of its triangles.
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { BufferGeometry, Float32BufferAttribute, Vector3 } from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { parseFaceMap } from '../src/Features';
import { analyse, regionAt } from '../src/Selection';

const file = (path: string) => fileURLToPath(new URL(`../../${path}`, import.meta.url));
const stl = (path: string) => { const bytes = readFileSync(file(path)); return new STLLoader().parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)); };

// The harness's own wall bracket export: its back and shelf plates carry teardrop screw holes whose
// tessellation fans long sliver triangles out to the plate corners. Those slivers' normals carry
// float noise, which once split one plate into several "faces" (an hourglass highlight).
const bracket = stl('tests/fixtures/split_faces/bracket.stl');
const map = parseFaceMap(JSON.parse(readFileSync(file('tests/fixtures/split_faces/bracket.faces.json'), 'utf8')));

test('a click anywhere on a flat face selects that whole B-rep face', () => {
  const a = analyse(bracket);
  const planes = map.faces.filter(f => f.kind === 'plane' && f.normal && f.area > 1);
  expect(planes.length).toBeGreaterThan(4);
  for (const face of planes) {
    const n = new Vector3(...face.normal!), c = new Vector3(...face.centre);
    // Every mesh triangle lying on this face's plane, inside its extent.
    const on = [...Array(a.count).keys()].filter(t => a.normal[t].dot(n) > 0.99 && Math.abs(a.centre[t].clone().sub(c).dot(n)) < 1e-3
      && a.centre[t].toArray().every((v, k) => v >= face.bbox.min[k] - 1e-3 && v <= face.bbox.max[k] + 1e-3));
    expect(on.length, `face ${face.id} has triangles`).toBeGreaterThan(0);
    // Compare with the meshed area: chords across a rounded boundary make it differ slightly from the B-rep area.
    const meshed = on.reduce((sum, t) => sum + a.area[t], 0);
    expect(Math.abs(meshed - face.area) / face.area, `face ${face.id} meshes to its B-rep area`).toBeLessThan(0.02);
    // Click each of them: the same whole face comes back every time. Known limit, both ways, along fillet edges: the
    // mesher leaves slivers of the plane tilted ~2° and ~0.003 mm off it, and a fillet's first facet can sit within
    // 0.7° and 0.0003 mm of the plane. Mesh geometry alone cannot tell them apart, so the region may gain or lose a
    // sliver (about 1 mm²; a stray plane sliver clicked on its own may select only itself). Hence the 1% bound.
    for (const t of on.filter(t => a.area[t] > face.area * 0.01 || on.length < 3)) {
      const r = regionAt(bracket, t, a.centre[t]);
      expect(r.flat, `face ${face.id} triangle ${t} reads as flat`).toBe(true);
      expect(Math.abs(r.area - meshed) / meshed, `face ${face.id} (${meshed.toFixed(2)} mm² meshed) clicked on triangle ${t} gave ${r.area.toFixed(2)} mm²`).toBeLessThan(0.01);
    }
  }
});

test('two separate faces on one plane stay separate', () => {
  // A coplanar but unconnected face must not join the clicked one: two unit squares on z = 0, apart.
  const square = (x: number) => [x, 0, 0, x + 1, 0, 0, x + 1, 1, 0, x, 0, 0, x + 1, 1, 0, x, 1, 0];
  const g = new BufferGeometry();
  g.setAttribute('position', new Float32BufferAttribute([...square(0), ...square(5)], 3));
  const r = regionAt(g, 0, new Vector3(0.5, 0.5, 0));
  expect(r.flat).toBe(true);
  expect(r.area).toBeCloseTo(1, 6);
});
