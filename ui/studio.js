// The Studio view: the part on a workbench, orbitable, with a build replay of the verification run.
import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";
import { STLLoader } from "three/addons/STLLoader.js";
import { toCreasedNormals } from "three/addons/BufferGeometryUtils.js";
import { RoomEnvironment } from "three/addons/RoomEnvironment.js";
import {
  VIEWS, clamp01, contactShadow, easeInOutCubic, easeOutCubic, filamentText, failedGate, fitDistance, fillTargets,
  humanName, replayTimeline, samplePoints, sizeRows, stageLine, stageName, stateOf, verdictOf, volumeText,
} from "/studio-core.js";

// The photographed look, in one place, because it is judged by eye.
const LOOK = {
  exposure: 0.95,
  fov: 26,
  filament: 0xd2d0ca,
  roughness: 0.56,
  sheen: 0.35,
  sheenRoughness: 0.65,
  specular: 0.42,
  envIntensity: 0.62,
  hemiSky: 0xfffaf2,
  hemiGround: 0xb9b1a6,
  hemiIntensity: 0.5,
  keyColor: 0xfff4e6,
  keyIntensity: 1.55,
  keyDirection: new THREE.Vector3(-0.55, -0.7, 1.15).normalize(),
  shadowTint: 0x2c2620,
  creaseRadians: THREE.MathUtils.degToRad(32),
  cutFace: 0xf25c05,  // the accent: Build's rising cut face
};
const CAMERA_MS = 600;
const NUDGE_MS = 180;
const INTRO_MS = 700;
const FADE_MS = 200;
const NO_CLIP = 1e7;
const ORBIT_FADE_DELAY_MS = 120;
const ORBIT_RETURN_DELAY_MS = 350;
const NUDGE_RADIANS = THREE.MathUtils.degToRad(15);

const $ = (id) => document.getElementById(id);
const el = {
  root: $("studio"), canvas: $("st-canvas"), absent: $("st-absent"), name: $("st-name"), summary: $("st-summary"),
  fn: $("st-function"), facts: $("st-facts"), provenance: $("st-provenance"), notices: $("st-notices"),
  panel: $("st-panel"), collapse: $("st-collapse"), build: $("st-build"), replay: $("st-replay"), stages: $("st-stages"),
  line: $("st-line"), live: $("st-live"), replayClose: $("st-replay-close"), hint: $("st-hint"), menu: $("st-menu"),
  switchRoot: $("st-switch"), switchButton: $("st-switch-button"), switchName: $("st-switch-name"), switchMark: $("st-switch-mark"),
  chips: [...document.querySelectorAll(".st-chip")],
};
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const narrow = window.matchMedia("(max-width: 760px)");

let gfx = null;           // renderer, scene, camera, controls, lights
let model = null;         // the loaded parts
let design = null;        // the /api/studio/<stem> payload on show
let designList = [];
let loadTicket = 0;
let running = false;
let dirty = true;
let tween = null;
let replay = null;
let intro = null;
let view = null;          // the named camera in use, or null once orbited by hand
let userMoved = false;
let openingCamera = null;
let orbitTimer = 0;

function mark(kind) {
  const span = document.createElement("span");
  span.className = `st-mark st-mark--${kind}`;
  span.setAttribute("aria-hidden", "true");
  return span;
}

function setMark(node, kind) {
  node.className = `st-mark st-mark--${kind}`;
}

function missionLink(text, stem, folder) {
  const link = document.createElement("a");
  link.href = folder ? `#/design/${encodeURIComponent(stem)}/${encodeURIComponent(folder)}` : "#/overview";
  link.textContent = text;
  return link;
}

/* ---------- Graphics ---------- */

function initGraphics() {
  const renderer = new THREE.WebGLRenderer({ canvas: el.canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);  // the workbench is the page's own colour, untouched by tone mapping
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = LOOK.exposure;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.localClippingEnabled = true;

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
  pmrem.dispose();

  scene.add(new THREE.HemisphereLight(LOOK.hemiSky, LOOK.hemiGround, LOOK.hemiIntensity));
  const key = new THREE.DirectionalLight(LOOK.keyColor, LOOK.keyIntensity);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  scene.add(key, key.target);

  const camera = new THREE.PerspectiveCamera(LOOK.fov, 1, 1, 10000);
  camera.up.set(0, 0, 1);  // Z is print-up, and the STLs keep their exported coordinates

  // Registered before OrbitControls so a press during a camera tween is not lost to it.
  el.canvas.addEventListener("pointerdown", cancelTween, { capture: true });
  el.canvas.addEventListener("wheel", cancelTween, { capture: true, passive: true });

  const controls = new OrbitControls(camera, el.canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.rotateSpeed = 0.8;
  controls.autoRotateSpeed = 0.7;
  controls.addEventListener("change", () => { dirty = true; });
  controls.addEventListener("start", onOrbitStart);
  controls.addEventListener("end", onOrbitEnd);

  el.canvas.addEventListener("keydown", onCanvasKey);
  el.canvas.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    showAbsent("The 3D view lost its graphics context. It will come back when the browser restores it.");
  });
  el.canvas.addEventListener("webglcontextrestored", () => { showAbsent(null); dirty = true; });
  window.addEventListener("resize", onResize);

  gfx = { renderer, scene, camera, controls, key };
  onResize();
}

function onOrbitStart() {
  stopAutoRotate();
  userMoved = true;
  setView(null);
  window.clearTimeout(orbitTimer);
  orbitTimer = window.setTimeout(() => el.root.classList.add("is-orbiting"), ORBIT_FADE_DELAY_MS);
}

function onOrbitEnd() {
  window.clearTimeout(orbitTimer);
  orbitTimer = window.setTimeout(() => el.root.classList.remove("is-orbiting"), ORBIT_RETURN_DELAY_MS);
}

function stopAutoRotate() {
  gfx.controls.autoRotate = false;
  el.hint.classList.add("is-spent");
}

function onResize() {
  if (!gfx) return;
  const width = window.innerWidth;
  const height = window.innerHeight;
  gfx.renderer.setSize(width, height, false);
  gfx.camera.aspect = width / height;
  gfx.camera.updateProjectionMatrix();
  if (model && !userMoved) frame(view ?? "iso", 0);
  dirty = true;
}

function tick(now) {
  if (!running) return;
  window.requestAnimationFrame(tick);
  if (tween) stepTween(now);
  else if (gfx.controls.update()) dirty = true;
  if (intro) stepIntro(now);
  if (replay) stepReplay(now);
  if (dirty) {
    gfx.renderer.render(gfx.scene, gfx.camera);
    dirty = false;
  }
}

/* ---------- Camera ---------- */

function setView(name) {
  view = name;
  el.chips.forEach((chip) => chip.setAttribute("aria-pressed", String(chip.dataset.cam === name)));
}

function cancelTween() {
  if (!tween) return;
  tween = null;
  gfx.controls.enabled = true;
}

function moveCamera(direction, distance, target, ms) {
  const { camera, controls } = gfx;
  const from = { direction: camera.position.clone().sub(controls.target).normalize(), distance: camera.position.distanceTo(controls.target), target: controls.target.clone() };
  if (ms <= 0 || reducedMotion.matches) {
    tween = null;
    controls.enabled = true;
    controls.target.copy(target);
    camera.position.copy(target).addScaledVector(direction, distance);
    camera.lookAt(target);
    controls.update();
    dirty = true;
    return;
  }
  controls.enabled = false;
  tween = { start: performance.now(), ms, from, turn: new THREE.Quaternion().setFromUnitVectors(from.direction, direction), direction, distance, target };
}

function stepTween(now) {
  const { camera, controls } = gfx;
  const t = clamp01((now - tween.start) / tween.ms);
  const e = easeInOutCubic(t);
  const turned = tween.from.direction.clone().applyQuaternion(new THREE.Quaternion().slerp(tween.turn, e));
  controls.target.lerpVectors(tween.from.target, tween.target, e);
  camera.position.copy(controls.target).addScaledVector(turned, THREE.MathUtils.lerp(tween.from.distance, tween.distance, e));
  camera.lookAt(controls.target);
  dirty = true;
  if (t >= 1) {
    tween = null;
    controls.enabled = true;
    controls.update();
  }
}

function frame(name, ms) {
  const direction = new THREE.Vector3(...VIEWS[name]);
  const target = model.center;
  const distance = fitDistance(model.points, target.toArray(), VIEWS[name], gfx.camera.aspect, LOOK.fov, fillTargets(gfx.camera.aspect));
  moveCamera(direction, distance, target, ms);
}

function onCanvasKey(event) {
  if (!model) return;
  const { camera, controls } = gfx;
  const offset = camera.position.clone().sub(controls.target);
  const up = new THREE.Vector3(0, 0, 1);
  const right = new THREE.Vector3().crossVectors(up, offset).normalize();
  const turns = {
    ArrowLeft: () => offset.applyAxisAngle(up, -NUDGE_RADIANS),
    ArrowRight: () => offset.applyAxisAngle(up, NUDGE_RADIANS),
    ArrowUp: () => offset.applyAxisAngle(right, -NUDGE_RADIANS),
    ArrowDown: () => offset.applyAxisAngle(right, NUDGE_RADIANS),
    "+": () => offset.multiplyScalar(0.88),
    "=": () => offset.multiplyScalar(0.88),
    "-": () => offset.multiplyScalar(1.14),
  };
  const turn = turns[event.key];
  if (!turn) return;
  event.preventDefault();
  turn();
  stopAutoRotate();
  userMoved = true;
  setView(null);
  moveCamera(offset.clone().normalize(), offset.length(), controls.target.clone(), NUDGE_MS);
}

/* ---------- The model ---------- */

function disposeModel() {
  if (!model) return;
  gfx.scene.remove(model.root);
  for (const part of model.parts) {
    part.solid.geometry.dispose();
    part.solid.material.dispose();
    part.cut.material.dispose();
    part.shadow.geometry.dispose();
    part.shadow.material.map.dispose();
    part.shadow.material.dispose();
  }
  model = null;
  dirty = true;
}

function makeShadow(raw) {
  const shade = contactShadow(raw);
  const tint = new THREE.Color(LOOK.shadowTint).convertLinearToSRGB();
  const data = new Uint8Array(shade.alpha.length * 4);
  for (let i = 0; i < shade.alpha.length; i += 1) {
    data[i * 4] = Math.round(tint.r * 255);
    data[i * 4 + 1] = Math.round(tint.g * 255);
    data[i * 4 + 2] = Math.round(tint.b * 255);
    data[i * 4 + 3] = shade.alpha[i];
  }
  const texture = new THREE.DataTexture(data, shade.size, shade.size, THREE.RGBAFormat);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearFilter;
  texture.needsUpdate = true;
  const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(shade.span, shade.span), material);
  mesh.position.set(shade.originX + shade.span / 2, shade.originY + shade.span / 2, shade.groundZ - shade.span * 1e-4);
  mesh.renderOrder = -1;
  return mesh;
}

function makePart(name, loaded) {
  const raw = loaded.getAttribute("position").array;
  const geometry = toCreasedNormals(loaded, LOOK.creaseRadians);
  loaded.dispose();
  geometry.computeBoundingBox();
  const plane = new THREE.Plane(new THREE.Vector3(0, 0, -1), NO_CLIP);
  const solid = new THREE.Mesh(geometry, new THREE.MeshPhysicalMaterial({
    color: LOOK.filament,
    roughness: LOOK.roughness,
    metalness: 0,
    sheen: LOOK.sheen,
    sheenRoughness: LOOK.sheenRoughness,
    sheenColor: new THREE.Color(0xffffff),
    specularIntensity: LOOK.specular,
    envMapIntensity: LOOK.envIntensity,
    clippingPlanes: [plane],
    clipShadows: true,
  }));
  solid.castShadow = true;
  solid.receiveShadow = true;
  solid.name = name;
  // Back faces seen through the cut read as a filled cross-section, so the part looks solid as it rises.
  const cut = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color: LOOK.cutFace, side: THREE.BackSide, clippingPlanes: [plane], toneMapped: false }));
  cut.visible = false;
  return { name, solid, cut, plane, shadow: makeShadow(raw), raw, zMin: geometry.boundingBox.min.z, zMax: geometry.boundingBox.max.z };
}

function assemble(parts) {
  const root = new THREE.Group();
  const bounds = new THREE.Box3();
  for (const part of parts) {
    root.add(part.solid, part.cut, part.shadow);
    bounds.union(part.solid.geometry.boundingBox);
  }
  gfx.scene.add(root);
  const center = bounds.getCenter(new THREE.Vector3());
  const radius = bounds.getBoundingSphere(new THREE.Sphere()).radius;
  const pointCount = parts.reduce((sum, part) => sum + part.raw.length, 0);
  const all = new Float32Array(pointCount);
  let at = 0;
  for (const part of parts) {
    all.set(part.raw, at);
    at += part.raw.length;
    delete part.raw;
  }
  const { key, camera, controls } = gfx;
  key.position.copy(center).addScaledVector(LOOK.keyDirection, radius * 3);
  key.target.position.copy(center);
  key.target.updateMatrixWorld();
  Object.assign(key.shadow.camera, { left: -radius * 1.3, right: radius * 1.3, top: radius * 1.3, bottom: -radius * 1.3, near: radius * 0.5, far: radius * 6 });
  key.shadow.camera.updateProjectionMatrix();
  key.shadow.bias = -0.0002;
  key.shadow.normalBias = radius * 0.004;
  camera.near = radius * 0.05;
  camera.far = radius * 60;
  camera.updateProjectionMatrix();
  controls.minDistance = radius * 0.5;
  controls.maxDistance = radius * 20;
  model = { root, parts, center, radius, points: samplePoints(all) };
}

async function fetchPart(part) {
  const response = await fetch(part.url);
  if (!response.ok) throw new Error(`${part.name}.stl answered ${response.status}`);
  return new STLLoader().parse(await response.arrayBuffer());
}

function reveal() {
  if (reducedMotion.matches) {
    model.root.scale.setScalar(1);
  } else {
    intro = { start: performance.now() };
    stepIntro(intro.start);
  }
  el.canvas.classList.add("is-shown");
  dirty = true;
}

function stepIntro(now) {
  const e = easeOutCubic(clamp01((now - intro.start) / INTRO_MS));
  const scale = 0.965 + 0.035 * e;
  model.root.scale.setScalar(scale);
  model.root.position.copy(model.center).multiplyScalar(1 - scale);
  dirty = true;
  if (e >= 1) intro = null;
}

/* ---------- Replay ---------- */

function setPartBuilt(part) {
  part.plane.constant = NO_CLIP;
  part.solid.visible = true;
  part.cut.visible = false;
  part.shadow.visible = true;
  part.shadow.material.opacity = 1;
}

function endReplay() {
  if (!replay) return;
  replay = null;
  model?.parts.forEach(setPartBuilt);
  el.build.textContent = "Build";
  dirty = true;
}

function paintStage(index, lit, gate) {
  const row = el.stages.children[index];
  const state = stateOf(gate.status);
  row.classList.toggle("is-lit", lit);
  row.classList.toggle("is-problem", lit && state.mark === "fail");
  setMark(row.querySelector(".st-mark"), lit ? state.mark : "unlit");
  row.querySelector("button").setAttribute("aria-disabled", String(!lit));
  row.querySelector(".visually-hidden").textContent = lit ? `, ${state.word}` : "";
}

function showVerdict() {
  const run = design.model;
  const verdict = verdictOf(run);
  el.line.replaceChildren();
  el.line.classList.toggle("is-problem", verdict.tone === "fail");
  el.line.classList.add("is-verdict");
  if (verdict.tone === "fail") {
    el.line.append(`${verdict.words} — `, missionLink("see Mission Control", design.stem, run.folder));
  } else {
    el.line.append(verdict.words);
  }
  el.live.textContent = verdict.tone === "fail" ? `${verdict.words}. See Mission Control.` : verdict.words;
  el.stages.querySelectorAll("button").forEach((button) => button.removeAttribute("aria-current"));
}

function renderStages(gates) {
  el.stages.replaceChildren(...gates.map((gate, index) => {
    const row = document.createElement("li");
    row.className = "st-stage-item";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "st-stage-button";
    const label = document.createElement("span");
    label.className = "st-stage-label";
    label.textContent = stageName(gate.name);
    const word = document.createElement("span");
    word.className = "visually-hidden";
    button.append(mark("unlit"), label, word);
    button.addEventListener("click", () => {
      if (button.getAttribute("aria-disabled") === "true") return;
      const wasCurrent = button.getAttribute("aria-current") === "true";
      if (replay) return;
      if (wasCurrent) return showVerdict();
      el.stages.querySelectorAll("button").forEach((other) => other.removeAttribute("aria-current"));
      button.setAttribute("aria-current", "true");
      el.line.classList.remove("is-verdict");
      el.line.classList.toggle("is-problem", stateOf(gate.status).mark === "fail");
      el.line.textContent = stageLine(gate);
    });
    row.append(button);
    return row;
  }));
}

function playReplay() {
  if (!model || !design?.model) return;
  const gates = design.model.gates;
  endReplay();
  renderStages(gates);
  el.replay.hidden = false;
  window.requestAnimationFrame(() => el.replay.classList.add("is-open"));
  el.line.textContent = "";
  el.line.classList.remove("is-problem", "is-verdict");
  el.live.textContent = "";
  if (reducedMotion.matches) {  // the same result without the motion: state, not spectacle
    gates.forEach((gate, index) => paintStage(index, true, gate));
    showVerdict();
    return;
  }
  stopAutoRotate();
  model.parts.forEach((part) => {
    part.solid.visible = false;
    part.cut.visible = false;
    part.shadow.visible = false;
  });
  el.build.textContent = "Building";
  replay = { start: performance.now(), timeline: replayTimeline(model.parts.length, gates.length), lit: 0 };
  dirty = true;
}

function stepReplay(now) {
  const { timeline } = replay;
  const t = (now - replay.start) / 1000;
  model.parts.forEach((part, index) => {
    const span = timeline.parts[index];
    const p = clamp01((t - span.start) / (span.end - span.start));
    if (p <= 0) return;
    if (p >= 1) return setPartBuilt(part);
    const e = easeInOutCubic(p);
    part.plane.constant = THREE.MathUtils.lerp(part.zMin, part.zMax, e);
    part.solid.visible = true;
    part.cut.visible = true;
    part.shadow.visible = true;
    part.shadow.material.opacity = e;
  });
  const gates = design.model.gates;
  while (replay.lit < gates.length && t >= timeline.gates[replay.lit]) {
    paintStage(replay.lit, true, gates[replay.lit]);
    el.line.textContent = stageLine(gates[replay.lit]);
    el.line.classList.toggle("is-problem", stateOf(gates[replay.lit].status).mark === "fail");
    replay.lit += 1;
  }
  dirty = true;
  if (t >= timeline.total) {
    endReplay();
    showVerdict();
  }
}

function closeReplay() {
  endReplay();
  el.replay.classList.remove("is-open");
  window.setTimeout(() => { if (!el.replay.classList.contains("is-open")) el.replay.hidden = true; }, FADE_MS);
}

/* ---------- Chrome ---------- */

function showAbsent(message) {
  el.absent.replaceChildren();
  if (message) el.absent.append(...[].concat(message));
  el.absent.hidden = !message;
}

function renderMenu(activeStem) {
  el.menu.replaceChildren(...designList.map((item) => {
    const state = stateOf(item.status);
    const row = document.createElement("li");
    const entry = document.createElement(item.has_model ? "a" : "span");
    entry.className = "st-menu-entry";
    const name = document.createElement("span");
    name.className = "st-menu-name";
    name.textContent = humanName(item.stem);
    const word = document.createElement("span");
    word.className = "st-menu-word";
    word.textContent = item.has_model ? state.word : `${state.word}, no model`;
    entry.append(mark(state.mark), name, word);
    if (item.has_model) {
      entry.href = `#/studio/${encodeURIComponent(item.stem)}`;
      if (item.stem === activeStem) entry.setAttribute("aria-current", "true");
      entry.addEventListener("click", () => closeMenu(false));
    } else {
      entry.setAttribute("aria-disabled", "true");
      entry.classList.add("is-disabled");
    }
    row.append(entry);
    return row;
  }));
}

function menuLinks() {
  return [...el.menu.querySelectorAll("a")];
}

function openMenu() {
  el.menu.hidden = false;
  el.switchButton.setAttribute("aria-expanded", "true");
  (el.menu.querySelector('a[aria-current="true"]') ?? menuLinks()[0])?.focus();
}

function closeMenu(returnFocus = true) {
  if (el.menu.hidden) return;
  el.menu.hidden = true;
  el.switchButton.setAttribute("aria-expanded", "false");
  if (returnFocus) el.switchButton.focus();
}

function factRow(label, value, kind) {
  const row = document.createElement("div");
  row.className = "st-fact";
  const term = document.createElement("dt");
  term.textContent = label;
  const data = document.createElement("dd");
  if (kind) data.append(mark(kind));
  data.append(value ?? "No data");
  row.append(term, data);
  return row;
}

function setCollapsed(collapsed) {
  el.panel.classList.toggle("is-collapsed", collapsed);
  el.root.classList.toggle("is-sheet-open", !collapsed);
  el.collapse.setAttribute("aria-expanded", String(!collapsed));
  el.collapse.setAttribute("aria-label", collapsed ? "Show details" : "Hide details");
}

function noticesFor(payload) {
  const run = payload.model;
  const notes = [];
  if (!run) return notes;
  if (!run.is_newest_run && payload.newest_run) {
    const newest = payload.newest_run;
    const failed = failedGate(newest);
    notes.push(failed
      ? `The newest run, ${newest.folder}, failed at ${stageName(failed.name).toLowerCase()}. This is the last exported model.`
      : `The newest run, ${newest.folder}, is a ${newest.mode ?? "partial"} run with no exports. This is the last exported model.`);
  }
  if (!run.exports_written) notes.push("This run did not export these files. They are left over from an earlier run in the same folder.");
  if (run.changed_since?.length) {
    const count = run.changed_since.length;
    notes.push(`${count} input ${count === 1 ? "file has" : "files have"} changed since this run, so it may no longer describe them.`);
  }
  return notes;
}

function renderPanel(payload) {
  const name = humanName(payload.stem);
  const run = payload.model;
  const verdict = run ? verdictOf(run) : null;
  el.name.textContent = name;
  document.title = `${name} · Magic CAD Studio`;
  el.canvas.setAttribute("aria-label", `3D view of ${name}. Arrow keys turn it, plus and minus zoom.`);
  el.fn.textContent = payload.function ?? "No brief states this design's function.";
  el.fn.classList.toggle("is-absent", !payload.function);
  el.summary.replaceChildren();
  el.facts.replaceChildren();
  el.provenance.textContent = "";
  el.notices.replaceChildren();
  const stateWord = stateOf(payload.status);
  setMark(el.switchMark, stateWord.mark);
  el.switchName.textContent = name;
  if (!run) {
    el.summary.append(mark(stateWord.mark), stateWord.word);
    el.facts.append(factRow("Checks", stateWord.word, stateWord.mark));
    return;
  }
  el.summary.append(mark(verdict.tone), verdict.words);
  el.facts.append(...sizeRows(run.bbox).map((row) => factRow(row.label, row.value)));
  el.facts.append(factRow("Volume", volumeText(run.volume)), factRow("Filament", filamentText(run.volume)), factRow("Checks", verdict.words, verdict.tone));
  const when = new Date(run.modified);
  const stamp = Number.isNaN(when.valueOf()) ? "" : `, ${when.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false })}`;
  el.provenance.textContent = `Run ${run.folder}${stamp}. Harness checks only, not a design review or a print.`;
  el.notices.append(...noticesFor(payload).map((text) => {
    const note = document.createElement("li");
    note.append(mark("warn"), text);
    return note;
  }));
}

function absentMessage(payload) {
  const name = payload.stem;
  if (payload.status === "NO_DESIGN") return "This brief has no design yet, so there is nothing to show.";
  if (payload.status === "NO_RUN") return "This design has not been through the harness yet, so no model has been exported.";
  const failed = failedGate(payload.newest_run);
  const lead = failed ? `The newest run failed at ${stageName(failed.name).toLowerCase()}, so no model was exported — ` : "No run has exported a model yet — ";
  return [lead, missionLink("see Mission Control", name, payload.newest_run?.folder)];
}

/* ---------- Loading ---------- */

async function loadDesign(stem) {
  const ticket = ++loadTicket;
  el.build.disabled = true;
  endReplay();
  closeReplay();
  cancelTween();
  const response = await fetch(`/api/studio/${encodeURIComponent(stem)}`);
  const payload = await response.json();
  if (ticket !== loadTicket) return;
  if (!response.ok) {
    design = null;
    clearStage();
    el.panel.hidden = true;
    showAbsent([`${payload.message ?? "This design could not be read."} `, missionLink("Open Mission Control", null, null)]);
    return;
  }
  el.panel.hidden = false;
  const sameModel = model && design?.stem === stem && design.model?.modified === payload.model?.modified;
  design = payload;
  renderPanel(payload);
  renderMenu(stem);
  if (sameModel) {
    el.build.disabled = false;
    return;
  }
  el.canvas.classList.remove("is-shown");
  if (!payload.model) {
    clearStage();
    showAbsent(absentMessage(payload));
    return;
  }
  showAbsent(null);
  const fetching = Promise.all(payload.model.parts.map(fetchPart));
  await Promise.all([fetching.catch(() => {}), model && !reducedMotion.matches ? new Promise((done) => { window.setTimeout(done, FADE_MS); }) : null]);
  let loaded;
  try {
    loaded = await fetching;
  } catch (error) {
    if (ticket !== loadTicket) return;
    clearStage();
    showAbsent([`The model files could not be read: ${error.message}. `, missionLink("See Mission Control", stem, payload.model.folder)]);
    return;
  }
  if (ticket !== loadTicket) return;
  disposeModel();
  intro = null;
  assemble(payload.model.parts.map((part, index) => makePart(part.name, loaded[index])));
  const opening = openingCamera ?? view ?? "iso";
  const firstOpen = openingCamera !== null;
  openingCamera = null;
  userMoved = false;
  setView(firstOpen || view ? opening : null);
  frame(opening, 0);
  gfx.controls.autoRotate = !firstOpen && !view && !reducedMotion.matches && !el.hint.classList.contains("is-spent");
  el.build.disabled = false;
  reveal();
}

function clearStage() {
  disposeModel();
  el.canvas.classList.remove("is-shown");
  el.build.disabled = true;
}

function wireChrome() {
  el.build.addEventListener("click", playReplay);
  el.replayClose.addEventListener("click", closeReplay);
  el.collapse.addEventListener("click", () => setCollapsed(!el.panel.classList.contains("is-collapsed")));
  el.chips.forEach((chip) => chip.addEventListener("click", () => {
    if (!model) return;
    stopAutoRotate();
    userMoved = false;
    setView(chip.dataset.cam);
    frame(chip.dataset.cam, CAMERA_MS);
  }));
  el.switchButton.addEventListener("click", () => (el.menu.hidden ? openMenu() : closeMenu()));
  document.addEventListener("pointerdown", (event) => {
    if (!el.switchRoot.contains(event.target)) closeMenu(false);
  });
  el.switchRoot.addEventListener("keydown", (event) => {
    if (el.menu.hidden) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeMenu();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const links = menuLinks();
      const at = links.indexOf(document.activeElement);
      links[(at + (event.key === "ArrowDown" ? 1 : -1) + links.length) % links.length]?.focus();
    }
  });
  el.switchRoot.addEventListener("focusout", (event) => {
    if (event.relatedTarget && !el.switchRoot.contains(event.relatedTarget)) closeMenu(false);
  });
  if (window.matchMedia("(pointer: coarse)").matches) el.hint.textContent = "Drag to orbit, pinch to zoom";
  setCollapsed(narrow.matches);
  const requested = new URLSearchParams(location.search).get("cam");
  openingCamera = Object.hasOwn(VIEWS, requested ?? "") ? requested : null;
}

let wired = false;

export async function enter(stem) {
  if (!wired) {
    wireChrome();
    wired = true;
  }
  try {
    if (!gfx) initGraphics();
  } catch (error) {
    showAbsent(["This browser could not start 3D graphics, so the part can't be shown here. ", missionLink("The gate reports are in Mission Control", null, null)]);
    throw error;
  }
  if (!running) {
    running = true;
    dirty = true;
    window.requestAnimationFrame(tick);
  }
  try {
    const response = await fetch("/api/studio");
    const list = await response.json();
    designList = list.designs ?? [];
    const chosen = stem ?? list.default;
    renderMenu(chosen);
    if (!chosen) {
      showAbsent(["No design has an exported model yet. ", missionLink("Open Mission Control", null, null)]);
      return;
    }
    await loadDesign(chosen);
  } catch {
    showAbsent(["The studio server did not answer. Start it from the project root with .venv/bin/python ui/server.py, then reload."]);
  }
}

export function leave() {
  running = false;
  loadTicket += 1;
  endReplay();
  closeMenu(false);
}
