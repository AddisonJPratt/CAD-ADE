// An exploded inspection of the stored assembly transforms, not a motion simulation.
import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";
import { STLLoader } from "three/addons/STLLoader.js";

let sceneState = null;
let sequence = 0;
const escape = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));

function dispose() {
  if (!sceneState) return;
  const state = sceneState;
  sceneState = null;
  cancelAnimationFrame(state.frame);
  state.observer?.disconnect();
  state.controls.dispose();
  for (const mesh of state.meshes) {
    mesh.geometry.dispose();
    mesh.material.dispose();
  }
  state.renderer.dispose();
}

export function leave() { sequence += 1; dispose(); }

function infoView(data) {
  const bom = data.bom ?? [];
  const steps = data.steps ?? [];
  return `<div class="assembly-heading"><div><h1 tabindex="-1">${escape(data.name)}</h1><p>Assembly demonstration · ${escape(data.units)}</p></div><a href="#/studio">Back to Studio</a></div>
    <div class="assembly-warnings"><strong>About this demonstration</strong><p class="assembly-copy">${escape(data.disclaimer)}</p>${data.warnings?.length ? `<ul>${data.warnings.map((w) => `<li>${escape(w)}</li>`).join("")}</ul>` : ""}</div>
    <div class="assembly-layout"><div><div class="assembly-viewport"><canvas id="assembly-canvas" tabindex="0" aria-label="3D assembly model. Drag to orbit, scroll to zoom."></canvas><span class="assembly-hint">Drag to orbit · scroll to zoom</span></div>
      <div class="assembly-controls"><label for="assembly-explode">Exploded view</label><output id="assembly-amount" for="assembly-explode">Assembled</output><input id="assembly-explode" type="range" min="0" max="100" value="0" aria-label="Exploded view amount"><div class="ends"><span>Assembled</span><span>Exploded</span></div></div><p class="assembly-copy">This separates parts along their stored offsets. It is an illustrative view, not a simulation or a validated assembly sequence.</p><p class="assembly-status" id="assembly-status" role="status">Loading 3D parts…</p></div>
      <aside class="assembly-sidebar"><section><h2>Parts and hardware</h2><ul class="assembly-list">${bom.map((item) => `<li>${escape(item.name)} <span class="meta">${escape(item.quantity)} × · ${escape(item.category)}${item.note ? ` · ${escape(item.note)}` : ""}</span></li>`).join("") || "<li>No parts listed.</li>"}</ul></section><section><h2>Assembly guide</h2><ol class="assembly-list">${steps.map((step) => `<li class="assembly-step"><span>${escape(step.number)}</span><span>${escape(step.text)}</span></li>`).join("") || "<li>No steps provided.</li>"}</ol></section></aside></div>`;
}

function resize(state) {
  const width = state.canvas.clientWidth, height = state.canvas.clientHeight;
  if (!width || !height) return;
  state.renderer.setSize(width, height, false);
  state.camera.aspect = width / height;
  state.camera.updateProjectionMatrix();
}

function renderLoop(state) {
  if (sceneState !== state) return;
  state.controls.update();
  state.renderer.render(state.scene, state.camera);
  state.frame = requestAnimationFrame(() => renderLoop(state));
}

export async function enter(view, isCurrent = () => true) {
  const ticket = ++sequence;
  dispose();
  const response = await fetch("/api/assembly/demo");
  if (!response.ok) throw new Error("The assembly data could not be loaded.");
  const data = await response.json();
  if (ticket !== sequence || !isCurrent()) return;
  view.innerHTML = infoView(data);
  const canvas = document.getElementById("assembly-canvas");
  const status = document.getElementById("assembly-status");
  if (!Array.isArray(data.parts) || !data.parts.length || data.parts.some((p) => p.mesh_available === false)) {
    status.textContent = "The 3D model is unavailable because an assembly mesh is missing or has changed. See the notes above.";
    return;
  }
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true }); }
  catch { status.textContent = "This browser could not start 3D graphics. Parts and assembly notes are still available."; return; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0xece9e3);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, .1, 10000);
  camera.up.set(0, 0, 1);
  scene.add(new THREE.HemisphereLight(0xffffff, 0xa69f93, 2));
  const light = new THREE.DirectionalLight(0xfff6e8, 2.2); light.position.set(-3, -4, 6); scene.add(light);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  const state = {scene, camera, renderer, controls, canvas, meshes: [], frame: 0, observer: null};
  sceneState = state;
  try {
    const loader = new STLLoader();
    const geometries = await Promise.all(data.parts.map((part) => loader.loadAsync(part.mesh)));
    if (ticket !== sequence || !isCurrent() || sceneState !== state) { geometries.forEach((g) => g.dispose()); return; }
    const bounds = new THREE.Box3();
    geometries.forEach((geometry, index) => {
      const part = data.parts[index];
      geometry.computeVertexNormals();
      const color = typeof part.color === "string" || typeof part.color === "number" ? part.color : 0xb7b2aa;
      const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({color, roughness: .6, metalness: part.kind === "hardware" ? .65 : 0}));
      mesh.position.fromArray(part.position);
      mesh.userData.base = new THREE.Vector3().fromArray(part.position);
      mesh.userData.offset = new THREE.Vector3().fromArray(part.exploded_offset);
      scene.add(mesh); state.meshes.push(mesh);
      const local = new THREE.Box3().setFromObject(mesh); bounds.union(local);
      const separated = local.clone().translate(mesh.userData.offset); bounds.union(separated);
    });
    const center = bounds.getCenter(new THREE.Vector3());
    const radius = Math.max(bounds.getSize(new THREE.Vector3()).length() / 2, 1);
    controls.target.copy(center);
    camera.position.copy(center).add(new THREE.Vector3(1, -1.5, 1.1).normalize().multiplyScalar(radius * 3.6));
    camera.near = Math.max(radius / 100, .01); camera.far = radius * 100; camera.updateProjectionMatrix();
    controls.minDistance = radius * .6; controls.maxDistance = radius * 12;
    const slider = document.getElementById("assembly-explode"), amount = document.getElementById("assembly-amount");
    slider.addEventListener("input", () => {
      const fraction = Number(slider.value) / 100;
      for (const mesh of state.meshes) mesh.position.copy(mesh.userData.base).addScaledVector(mesh.userData.offset, fraction);
      amount.textContent = fraction === 0 ? "Assembled" : fraction === 1 ? "Exploded" : `${slider.value}%`;
    });
    state.observer = new ResizeObserver(() => resize(state)); state.observer.observe(canvas);
    resize(state); renderLoop(state);
    status.textContent = `${data.parts.length} parts shown. Model positions are from the assembly data.`;
  } catch {
    dispose();
    if (ticket === sequence && isCurrent()) status.textContent = "One or more model files could not be loaded. Check the assembly notes and try again.";
  }
}
