// Run from the project root: node --test ui/tests/studio-core.test.mjs
import assert from "node:assert/strict";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { test } from "node:test";
import {
  VIEWS, contactShadow, fitDistance, filamentText, projectedFill, replayTimeline, samplePoints, sizeRows, stageLine, stageName, verdictOf, volumeText,
} from "../studio-core.js";

function stlPositions(path) {
  const bytes = readFileSync(path);
  const count = bytes.readUInt32LE(80);
  const out = new Float32Array(count * 9);
  for (let i = 0; i < count; i += 1) {
    for (let v = 0; v < 9; v += 1) out[i * 9 + v] = bytes.readFloatLE(84 + i * 50 + 12 + v * 4);
  }
  return out;
}

// Committed fixtures (ui/tests/make_fixtures.py) make a fresh clone testable; a run's own STLs, when a
// local `magic.py run` has written them, replace that model's fixture so new geometry is framed too.
const FIXTURES = "ui/tests/fixtures/models";

function stlsIn(dir) {
  return existsSync(dir) ? readdirSync(dir).filter((name) => name.endsWith(".stl")).map((name) => `${dir}/${name}`) : [];
}

function realModels() {
  const byFolder = new Map();
  for (const folder of readdirSync(FIXTURES)) byFolder.set(folder, stlsIn(`${FIXTURES}/${folder}`));
  for (const folder of readdirSync("runs")) {
    const report = `runs/${folder}/report.json`;
    // Only a passing run's geometry replaces a fixture; a failed local check may have left broken meshes.
    if (folder.startsWith("_") || !existsSync(report) || JSON.parse(readFileSync(report, "utf8")).pass !== true) continue;
    const stls = stlsIn(`runs/${folder}`);
    if (stls.length) byFolder.set(folder, stls);
  }
  return [...byFolder].filter(([, paths]) => paths.length).map(([folder, paths]) => ({ folder, parts: paths.map(stlPositions) }));
}

test("verdict words come from the run's own gates", () => {
  const passed = { pass: true, gates: [{ name: "1 Execute", status: "PASS" }, { name: "5 Exports", status: "PASS" }] };
  assert.equal(verdictOf(passed).words, "All checks passed");
  const failed = { pass: false, gates: [{ name: "1 Execute", status: "PASS" }, { name: "3 Printability", status: "FAIL" }, { name: "Sweep", status: "SKIPPED" }] };
  assert.equal(verdictOf(failed).words, "Failed at printability");
  assert.equal(verdictOf({ pass: true, gates: [{ name: "5 Exports", status: "NOT RUN" }] }).words, "Checks passed, some not run");
  assert.equal(verdictOf({}).words, "No verdict in this run");
});

test("a stage line drops the harness's dash placeholder", () => {
  assert.equal(stageName("3 Printability"), "Printability");
  assert.equal(stageName("Sweep"), "Sweep");
  assert.equal(stageLine({ name: "Sweep", status: "SKIPPED", detail: "-" }), "Sweep: skipped.");
  assert.equal(stageLine({ name: "1 Execute", status: "PASS", detail: "built in 10 s" }), "Execute: passed. built in 10 s");
});

test("numbers: one size row per part, filament is volume x 1.24", () => {
  assert.deepEqual(sizeRows({ box: [80, 60, 30], lid: [80, 60, 8] }).map((row) => row.label), ["Box size", "Lid size"]);
  assert.deepEqual(sizeRows({ part: [17.2145, 9.7000001, 12] }), [{ label: "Size", value: "17.2 × 9.7 × 12 mm" }]);
  assert.equal(volumeText(36799.28), "36.8 cm³");
  assert.equal(filamentText(36799.28), "46 g est.");
  assert.equal(filamentText(1172.56), "1.5 g est.");
  assert.equal(filamentText(undefined), null);
});

test("replay: 1.2 s per part, and the gates finish with the span", () => {
  const one = replayTimeline(1, 6);
  assert.equal(one.parts[0].end, 1.2);
  assert.ok(one.total >= 2.7);
  assert.equal(one.gates.length, 6);
  assert.ok(one.gates[5] < one.total, "the last gate is on screen before the verdict");
  const eight = replayTimeline(8, 6);
  assert.equal(eight.parts[7].start, 8.4);
  assert.ok(Math.abs(eight.gates[5] - 9.6) < 1e-9);
});

test("every real model is framed to the fill targets: 75 % of height, 62 % of width beside the panel, 82 % on a phone", () => {
  const screens = [[1440, 900], [1920, 1080], [1280, 720], [390, 844]];
  const models = realModels();
  assert.ok(models.length >= 5);
  for (const { folder, parts } of models) {
    const raw = Float32Array.from(parts.flatMap((part) => [...part]));
    const points = samplePoints(raw);
    const min = [0, 1, 2].map((axis) => { let m = Infinity; for (let i = axis; i < raw.length; i += 3) m = Math.min(m, raw[i]); return m; });
    const max = [0, 1, 2].map((axis) => { let m = -Infinity; for (let i = axis; i < raw.length; i += 3) m = Math.max(m, raw[i]); return m; });
    const center = min.map((value, axis) => (value + max[axis]) / 2);
    for (const [width, height] of screens) {
      for (const [name, direction] of Object.entries(VIEWS)) {
        const aspect = width / height;
        const distance = fitDistance(points, center, direction, aspect, 26);
        const fill = projectedFill(points, center, direction, distance, aspect, 26);
        const context = `${folder} ${name} ${width}x${height}: ${fill.width.toFixed(3)} w, ${fill.height.toFixed(3)} h`;
        assert.ok(fill.width <= 0.83 && fill.height <= 0.76, `overflows: ${context}`);
        assert.ok(aspect < 1 ? fill.width >= 0.8 || fill.height >= 0.54 : fill.height >= 0.74 || fill.width >= 0.61, `underfills: ${context}`);
      }
    }
  }
});

test("the contact shadow has no hard edge and fades to nothing at its border", () => {
  for (const { folder, parts } of realModels()) {
    for (const part of parts) {
      const { alpha, size } = contactShadow(part);
      let peak = 0;
      let steepest = 0;
      for (let y = 0; y < size; y += 1) {
        for (let x = 0; x < size; x += 1) {
          const value = alpha[y * size + x];
          peak = Math.max(peak, value);
          if (x + 1 < size) steepest = Math.max(steepest, Math.abs(value - alpha[y * size + x + 1]));
          if (y + 1 < size) steepest = Math.max(steepest, Math.abs(value - alpha[(y + 1) * size + x]));
        }
      }
      for (let i = 0; i < size; i += 1) assert.ok(alpha[i] === 0 && alpha[alpha.length - 1 - i] === 0, `${folder}: shadow reaches the border`);
      assert.ok(peak > 40 && peak < 150, `${folder}: peak ${peak}`);
      assert.ok(steepest < 30, `${folder}: a step of ${steepest}/255 between neighbours is a visible edge`);
    }
  }
});
