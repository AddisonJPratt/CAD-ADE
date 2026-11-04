// Studio logic with no DOM and no Three.js, so it runs under node --test against real report data.

export const FILAMENT_G_PER_CM3 = 1.24;  // PLA density, as the brief sets it
export const PART_BUILD_S = 1.2;
const GATE_STEP_MIN_S = 0.45;
const VERDICT_HOLD_S = 0.7;  // the last gate gets read before the verdict replaces it
const HIDDEN_DETAIL = "-";  // how the harness fills the detail of a skipped gate

export const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
export const easeOutCubic = (t) => 1 - (1 - t) ** 3;
export const clamp01 = (t) => Math.min(1, Math.max(0, t));

export function humanName(stem) {
  const words = String(stem).replace(/[_-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function stageName(gateName) {
  return String(gateName ?? "Unnamed").replace(/^\d+\s+/, "");
}

// The state vocabulary from DESIGN.md: every state is a word plus a shape.
const STATES = {
  PASS: { word: "Passed", mark: "pass" },
  FAIL: { word: "Failed", mark: "fail" },
  ERROR: { word: "Error", mark: "fail" },
  SKIPPED: { word: "Skipped", mark: "idle" },
  "NOT RUN": { word: "Not run", mark: "idle" },
  NO_RUN: { word: "Not run", mark: "dash" },
  NO_DESIGN: { word: "No design", mark: "dash" },
};
export const stateOf = (status) => STATES[status] ?? { word: "No verdict", mark: "dash" };

export function failedGate(run) {
  return (run?.gates ?? []).find((gate) => stateOf(gate.status).mark === "fail") ?? null;
}

// The plain-words ending of a replay. Reports only what the run's own report says.
export function verdictOf(run) {
  const failed = failedGate(run);
  if (failed) return { tone: "fail", words: `Failed at ${stageName(failed.name).toLowerCase()}`, failedAt: stageName(failed.name) };
  const gates = run?.gates ?? [];
  if (run?.pass === true && gates.length && gates.every((gate) => gate.status === "PASS")) return { tone: "pass", words: "All checks passed" };
  if (run?.pass === true) return { tone: "idle", words: "Checks passed, some not run" };
  return { tone: "dash", words: "No verdict in this run" };
}

export function stageLine(gate) {
  const detail = gate.detail && gate.detail !== HIDDEN_DETAIL ? ` ${gate.detail}` : "";
  return `${stageName(gate.name)}: ${stateOf(gate.status).word.toLowerCase()}.${detail}`;
}

const trim = (value) => Number(value.toFixed(1)).toString();

// One row per part, because parts are laid out apart: their union is bed layout, not a size.
export function sizeRows(bbox) {
  if (!bbox || typeof bbox !== "object") return [];
  const entries = Object.entries(bbox).filter(([, size]) => Array.isArray(size) && size.length === 3);
  return entries.map(([part, size]) => ({
    label: entries.length === 1 ? "Size" : `${humanName(part)} size`,
    value: `${size.map(trim).join(" × ")} mm`,
  }));
}

export function volumeText(volumeMm3) {
  return Number.isFinite(volumeMm3) ? `${(volumeMm3 / 1000).toFixed(1)} cm³` : null;
}

export function filamentText(volumeMm3) {
  if (!Number.isFinite(volumeMm3)) return null;
  const grams = (volumeMm3 / 1000) * FILAMENT_G_PER_CM3;
  return `${grams < 10 ? grams.toFixed(1) : Math.round(grams)} g est.`;
}

// Parts grow one after another while the gates light across the whole span.
export function replayTimeline(partCount, gateCount) {
  const buildEnd = partCount * PART_BUILD_S;
  const total = Math.max(buildEnd, gateCount * GATE_STEP_MIN_S);
  const parts = Array.from({ length: partCount }, (_, i) => ({ start: i * PART_BUILD_S, end: (i + 1) * PART_BUILD_S }));
  const gates = Array.from({ length: gateCount }, (_, i) => (i + 1) * (total / gateCount));
  return { total: total + VERDICT_HOLD_S, parts, gates };
}

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const unit = (a) => { const n = Math.hypot(...a) || 1; return [a[0] / n, a[1] / n, a[2] / n]; };

// Z is print-up. Top leans a hair toward the viewer so "up" on screen stays defined.
export const VIEWS = {
  iso: unit([0.72, -1, 0.68]),
  front: unit([0, -1, 0.0001]),
  side: unit([1, 0, 0.0001]),
  top: unit([0, -0.0012, 1]),
};

export function fillTargets(aspect) {
  return aspect < 1 ? { height: 0.55, width: 0.82 } : { height: 0.75, width: 0.62 };
}

function viewBasis(direction) {
  const back = unit(direction);
  const right = unit(cross([0, 0, 1], back));
  return { back, right, up: cross(back, right) };
}

// The exact camera distance that makes the points fill the targets, under perspective.
export function fitDistance(points, target, direction, aspect, fovDeg, fill = fillTargets(aspect)) {
  const { back, right, up } = viewBasis(direction);
  const tanV = Math.tan((fovDeg * Math.PI) / 360);
  const tanH = tanV * aspect;
  let distance = 0;
  for (let i = 0; i < points.length; i += 3) {
    const p = [points[i] - target[0], points[i + 1] - target[1], points[i + 2] - target[2]];
    const depth = dot(p, back);
    distance = Math.max(distance,
      depth + Math.abs(dot(p, right)) / (tanH * fill.width),
      depth + Math.abs(dot(p, up)) / (tanV * fill.height));
  }
  return distance;
}

// The share of the viewport the points cover at a distance: the check on the 70-80 % promise.
export function projectedFill(points, target, direction, distance, aspect, fovDeg) {
  const { back, right, up } = viewBasis(direction);
  const tanV = Math.tan((fovDeg * Math.PI) / 360);
  let x = 0;
  let y = 0;
  for (let i = 0; i < points.length; i += 3) {
    const p = [points[i] - target[0], points[i + 1] - target[1], points[i + 2] - target[2]];
    const d = distance - dot(p, back);
    x = Math.max(x, Math.abs(dot(p, right)) / (d * tanV * aspect));
    y = Math.max(y, Math.abs(dot(p, up)) / (d * tanV));
  }
  return { width: x, height: y };
}

function fillTriangle(grid, size, ax, ay, bx, by, cx, cy) {
  const minX = Math.max(0, Math.floor(Math.min(ax, bx, cx)));
  const maxX = Math.min(size - 1, Math.ceil(Math.max(ax, bx, cx)));
  const minY = Math.max(0, Math.floor(Math.min(ay, by, cy)));
  const maxY = Math.min(size - 1, Math.ceil(Math.max(ay, by, cy)));
  const area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
  if (area === 0) return;
  const sign = area > 0 ? 1 : -1;
  for (let y = minY; y <= maxY; y += 1) {
    for (let x = minX; x <= maxX; x += 1) {
      const px = x + 0.5;
      const py = y + 0.5;
      const e0 = (bx - ax) * (py - ay) - (by - ay) * (px - ax);
      const e1 = (cx - bx) * (py - by) - (cy - by) * (px - bx);
      const e2 = (ax - cx) * (py - cy) - (ay - cy) * (px - cx);
      if (e0 * sign >= 0 && e1 * sign >= 0 && e2 * sign >= 0) grid[y * size + x] = 1;
    }
  }
}

function boxBlur(source, size, radius) {
  const window = radius * 2 + 1;
  let from = source;
  for (let pass = 0; pass < 3; pass += 1) {  // three box passes approximate a gaussian
    for (const horizontal of [true, false]) {
      const to = new Float32Array(size * size);
      for (let line = 0; line < size; line += 1) {
        let sum = 0;
        for (let i = -radius; i <= radius; i += 1) {
          const at = Math.min(size - 1, Math.max(0, i));
          sum += horizontal ? from[line * size + at] : from[at * size + line];
        }
        for (let i = 0; i < size; i += 1) {
          if (horizontal) to[line * size + i] = sum / window;
          else to[i * size + line] = sum / window;
          const leave = Math.max(0, i - radius);
          const enter = Math.min(size - 1, i + radius + 1);
          sum += horizontal ? from[line * size + enter] - from[line * size + leave] : from[enter * size + line] - from[leave * size + line];
        }
      }
      from = to;
    }
  }
  return from;
}

// A baked contact shadow: a wide soft pool from the whole footprint, plus a tight dark core from
// the faces that actually touch the bed. No hard edge can exist, because both layers are blurred.
export function contactShadow(positions, { size = 256, pool = 0.2, contact = 0.34 } = {}) {
  let minX = Infinity; let maxX = -Infinity; let minY = Infinity; let maxY = -Infinity; let minZ = Infinity; let maxZ = -Infinity;
  for (let i = 0; i < positions.length; i += 3) {
    minX = Math.min(minX, positions[i]); maxX = Math.max(maxX, positions[i]);
    minY = Math.min(minY, positions[i + 1]); maxY = Math.max(maxY, positions[i + 1]);
    minZ = Math.min(minZ, positions[i + 2]); maxZ = Math.max(maxZ, positions[i + 2]);
  }
  const extent = Math.max(maxX - minX, maxY - minY) || 1;
  const pad = extent * 0.28;
  const span = extent + pad * 2;
  const originX = (minX + maxX) / 2 - span / 2;
  const originY = (minY + maxY) / 2 - span / 2;
  const scale = size / span;
  const contactHeight = minZ + Math.min((maxZ - minZ) * 0.06, extent * 0.04);
  const all = new Float32Array(size * size);
  const touching = new Float32Array(size * size);
  for (let i = 0; i + 8 < positions.length; i += 9) {
    const ax = (positions[i] - originX) * scale; const ay = (positions[i + 1] - originY) * scale;
    const bx = (positions[i + 3] - originX) * scale; const by = (positions[i + 4] - originY) * scale;
    const cx = (positions[i + 6] - originX) * scale; const cy = (positions[i + 7] - originY) * scale;
    fillTriangle(all, size, ax, ay, bx, by, cx, cy);
    if (Math.max(positions[i + 2], positions[i + 5], positions[i + 8]) <= contactHeight) fillTriangle(touching, size, ax, ay, bx, by, cx, cy);
  }
  const wide = boxBlur(all, size, Math.max(2, Math.round(size * 0.035)));
  const tight = boxBlur(touching, size, Math.max(1, Math.round(size * 0.009)));
  const alpha = new Uint8Array(size * size);
  for (let i = 0; i < alpha.length; i += 1) {
    alpha[i] = Math.round(255 * (1 - (1 - wide[i] * pool) * (1 - tight[i] * contact)));
  }
  return { size, alpha, originX, originY, span, groundZ: minZ };
}

// Evenly thins a triangle soup to at most `limit` points, for framing maths.
export function samplePoints(positions, limit = 6000) {
  const count = positions.length / 3;
  if (count <= limit) return positions;
  const step = count / limit;
  const out = new Float32Array(limit * 3);
  for (let i = 0; i < limit; i += 1) {
    const at = Math.floor(i * step) * 3;
    out[i * 3] = positions[at]; out[i * 3 + 1] = positions[at + 1]; out[i * 3 + 2] = positions[at + 2];
  }
  return out;
}
