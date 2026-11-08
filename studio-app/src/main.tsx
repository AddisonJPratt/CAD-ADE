import React, { Suspense, useEffect, useState, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas, useLoader, useThree, type ThreeEvent } from '@react-three/fiber';
import { Bounds, Grid, Html, OrbitControls, useProgress } from '@react-three/drei';
import { Box3, BufferGeometry, Mesh, PMREMGenerator, PerspectiveCamera, Raycaster, Vector2, Vector3, MOUSE, TOUCH } from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import './style.css';
import { Evidence, type EvidenceDesign } from './Evidence';
import { Catalogue } from './Catalogue';
import { Icon } from './icons';
import { BrandMark, Wordmark } from './Brand';
import { ParameterPanel } from './ParameterPanel';
import { CommandSearch, type StudioCommand } from './watermelon/CommandSearch';
import { ToolHint } from './watermelon/ToolHint';
import { ViewportTools, DEFAULT_VIEW, MATERIALS, type ViewStyle, type ToolMode } from './watermelon/ViewportTools';
import { Verdict } from './Verdict';
import { Highlight, circled, describe, label, loopArea, measure, regionAt, type Pick } from './Selection';
import { PartsList } from './PartsList';
import { ProjectPicker } from './ProjectPicker';

// The assistant's name in the interface. One place, so the owner can rename it.
export const ASSISTANT = 'Drafter';
const niceName = (file: string) => file.replace(/\.py$/, '').replace(/[_-]+/g, ' ').replace(/^./, c => c.toUpperCase());
type Turn = { id: number; who: 'you' | 'assistant'; text: string; chips?: string[]; tone?: 'error' };
const COLUMN = { min: 320, max: 640, initial: 400 };
function storedWidth() { try { const n = Number(localStorage.getItem('studio.column')); return n >= COLUMN.min && n <= COLUMN.max ? n : COLUMN.initial; } catch { return COLUMN.initial; } }

function StudioEnvironment({light=100}:{light?:number}) {
  const { gl, scene, invalidate } = useThree();
  useEffect(() => { const generator = new PMREMGenerator(gl); const room = new RoomEnvironment(); const texture = generator.fromScene(room).texture; scene.environment = texture; return () => { scene.environment = null; texture.dispose(); room.dispose(); generator.dispose(); }; }, [gl, scene]);
  useEffect(() => { scene.environmentIntensity = 0.65 * light / 100; invalidate(); }, [scene,light,invalidate]);
  return null;
}
type Proposal = { id:string; changes:{parameter:string; old:number; new:number}[]; previews:{before:string[]; after:string[]}; preview_dimensions:{before:number[][]; after:number[][]} };
type SourceFile = { name: string; content: string };
type Gate = { name: string; status: string; detail: string };
type Details = { briefs: SourceFile[]; designs: SourceFile[]; report: null | { designs: { design: string; gates: Gate[] }[] } };
type Mode = "Make" | "Studio" | "Mission Control";
type Printer = { material: string; profile: { name: string; build_volume_mm: number[]; nozzle_mm: number; materials: Record<string, unknown> } };
type Version = { id: string; number: number; message: string; timestamp: string; current: boolean; verdict: null | { pass: boolean; designs?: EvidenceDesign[] } };
async function json<T>(url: string): Promise<T> { const response = await fetch(url); const value = await response.json(); if (!response.ok) throw new Error(value.error || 'Engine request failed'); return value as T; }
type Interact = { pick: (e: ThreeEvent<MouseEvent>, g: BufferGeometry) => void; body: (e: ThreeEvent<MouseEvent>, g: BufferGeometry) => void; hover: (e: ThreeEvent<PointerEvent> | null, g: BufferGeometry) => void };
function Model({ url, name, visible = true, wireframe = false, style, interact }: { url: string; name?: string; visible?: boolean; wireframe?: boolean; style:ViewStyle; interact?: Interact }) { const geometry = useLoader(STLLoader, url); return <mesh userData={{cadBody:true, body:name}} geometry={geometry} visible={visible} onClick={interact ? e => interact.pick(e, geometry) : undefined} onDoubleClick={interact ? e => interact.body(e, geometry) : undefined} onPointerMove={interact ? e => interact.hover(e, geometry) : undefined} onPointerOut={interact ? () => interact.hover(null, geometry) : undefined}><meshPhysicalMaterial color={MATERIALS[style.material].color} metalness={MATERIALS[style.material].metalness} roughness={MATERIALS[style.material].roughness} clearcoat={0.15} wireframe={wireframe}/></mesh>; }
function Workplane({visible,dark}:{visible:boolean;dark:boolean}) {
  return visible ? <Grid position={[0,0,-.08]} rotation={[Math.PI/2,0,0]} args={[1000,1000]} cellSize={10} sectionSize={50} cellThickness={.5} sectionThickness={.8} cellColor={dark ? '#36322c' : '#c9c1b4'} sectionColor={dark ? '#4d473e' : '#a39a8c'} fadeDistance={500} fadeStrength={1.5} infiniteGrid /> : null;
}

function ComparisonModels({ proposal, side, onReady }: { proposal: Proposal; side: 'before' | 'after'; onReady: (side: 'before' | 'after') => void }) {
  const paths = [...proposal.previews.before, ...proposal.previews.after];
  const geometries = useLoader(STLLoader, paths.map(path => '/api' + path));
  const { camera, controls, size, invalidate } = useThree();
  useEffect(() => {
    const orbit = controls as unknown as { target: Vector3; update: () => void } | null;
    if (!orbit || !size.width || !size.height) return;
    const box = new Box3();
    geometries.forEach(geometry => { geometry.computeBoundingBox(); if (geometry.boundingBox) box.union(geometry.boundingBox); });
    const center = box.getCenter(new Vector3());
    const extent = box.getSize(new Vector3()).length();
    const fov = (camera as PerspectiveCamera).fov * Math.PI / 180;
    const distance = extent / (2 * Math.tan(fov / 2)) * 1.12 * Math.max(1, size.height / size.width);
    camera.up.set(0, 0, 1);
    camera.position.copy(center).add(new Vector3(1, -1, 1).normalize().multiplyScalar(distance));
    camera.near = Math.max(distance / 100, 0.01); camera.far = distance * 100;
    camera.lookAt(center); camera.updateProjectionMatrix();
    orbit.target.copy(center); orbit.update(); invalidate(); onReady(side);
  }, [camera, controls, geometries, size.width, size.height, side, invalidate, onReady]);
  return <>{geometries.map((geometry, i) => <mesh key={paths[i]} geometry={geometry} visible={(i < proposal.previews.before.length) === (side === 'before')}><meshPhysicalMaterial color="#b9c2c7" metalness={0.22} roughness={0.38} clearcoat={0.15}/></mesh>)}</>;
}

type LassoHit = { body: string; geometry: BufferGeometry; loop: Vector3[]; normal: Vector3; region: Float32Array };
/** Lays the DOM lasso onto the model: each drawn point is cast into the scene, and the loop is kept on the body it hits most. */
function LassoBridge({ api }: { api: React.MutableRefObject<null | ((poly: [number, number][]) => LassoHit | null)> }) {
  const { camera, size, scene } = useThree();
  useEffect(() => {
    api.current = poly => {
      const meshes: Mesh[] = []; scene.traverse(o => { if ((o as Mesh).isMesh && o.userData.cadBody && o.visible) meshes.push(o as Mesh); });
      const caster = new Raycaster(); const hits = new Map<Mesh, Vector3[]>();
      poly.forEach(([x, y]) => { caster.setFromCamera(new Vector2(x / size.width * 2 - 1, -(y / size.height) * 2 + 1), camera); const hit = caster.intersectObjects(meshes, false)[0]; if (hit) { const list = hits.get(hit.object as Mesh) || []; list.push(hit.point.clone()); hits.set(hit.object as Mesh, list); } });
      const best = [...hits.entries()].sort((a, b) => b[1].length - a[1].length)[0];
      if (!best || best[1].length < 4) return null;
      const [mesh, loop] = best;
      const project = (v: Vector3): [number, number] => { const p = v.clone().project(camera); return [(p.x + 1) / 2 * size.width, (1 - p.y) / 2 * size.height]; };
      const inside = circled(mesh.geometry, poly, project, camera.position);
      return { body: mesh.userData.body || 'part', geometry: mesh.geometry, loop, normal: inside ? inside.normal : new Vector3(0, 0, 1), region: inside ? inside.region : new Float32Array() };
    };
    return () => { api.current = null; };
  }, [api, camera, size, scene]);
  return null;
}
type CameraAction = { name: string; sequence: number };
function CameraView({ action }: { action: CameraAction }) {
  const { camera, invalidate, controls, scene, size } = useThree();
  useEffect(() => {
    const orbit = controls as unknown as { target: Vector3; update: () => void } | null;
    if (!orbit) return;
    const target = orbit.target;
    const offset = camera.position.clone().sub(target);
    const positions: Record<string, [number, number, number]> = { Iso: [1,-1,1], Front: [0,-1,0], Top: [0,0,1], Side: [1,0,0] };
    const preset = positions[action.name];
    if (action.name === 'Fit') {
      const box = new Box3();
      scene.traverse(object => {if(object.userData.cadBody && object.visible) box.expandByObject(object);});
      if(box.isEmpty()) return;
      const center = box.getCenter(new Vector3());
      const extent = box.getSize(new Vector3()).length();
      const fov = (camera as PerspectiveCamera).fov * Math.PI / 180;
      const distance = extent / (2*Math.tan(fov/2)) * 1.4 * Math.max(1,size.height/size.width);
      target.copy(center);offset.normalize().multiplyScalar(distance);
      camera.near=Math.max(distance/100,.01);camera.far=distance*100;
    } else if (preset) {
      const distance = offset.length();
      offset.set(...preset).normalize().multiplyScalar(distance);
      camera.up.set(0, action.name === 'Top' ? 1 : 0, action.name === 'Top' ? 0 : 1);
    } else if (action.name === 'Zoom in' || action.name === 'Zoom out') {
      offset.multiplyScalar(action.name === 'Zoom in' ? 0.8 : 1.25);
    } else if (action.name.startsWith('Orbit')) {
      const axis = action.name === 'Orbit left' || action.name === 'Orbit right' ? camera.up.clone().normalize() : new Vector3(1, 0, 0).applyQuaternion(camera.quaternion).normalize();
      const positive = action.name === 'Orbit left' || action.name === 'Orbit up';
      offset.applyAxisAngle(axis, (positive ? 1 : -1) * Math.PI / 12);
    } else if (action.name.startsWith('Pan')) {
      const horizontal = action.name === 'Pan left' || action.name === 'Pan right';
      const axis = new Vector3(horizontal ? 1 : 0, horizontal ? 0 : 1, 0).applyQuaternion(camera.quaternion);
      const positive = action.name === 'Pan right' || action.name === 'Pan up';
      target.addScaledVector(axis, offset.length() * (positive ? 0.08 : -0.08));
    }
    camera.position.copy(target).add(offset);
    camera.lookAt(target);
    camera.updateProjectionMatrix();
    orbit.update();
    invalidate();
  }, [action, camera, controls, invalidate, scene, size.height, size.width]);
  return null;
}
class ModelError extends React.Component<{children: React.ReactNode; onError?: () => void; message?: string}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  componentDidCatch() { this.props.onError?.(); }
  render() { return this.state.failed ? <div className="empty" role="alert">{this.props.message || 'The model could not be loaded. Select another version and return to retry.'}</div> : this.props.children; }
}
function LoadingNotice() { const { active } = useProgress(); return active ? <div className="loading" role="status">Loading model…</div> : null; }
function App() {
  const [printer, setPrinter] = useState<Printer | null>(null); const [savingMaterial, setSavingMaterial] = useState(false); const [materialNotice, setMaterialNotice] = useState(''); const [materialError, setMaterialError] = useState('');
  const [mode, setMode] = useState<Mode>('Studio'); const [details, setDetails] = useState<Details | null>(null); const [detailsError, setDetailsError] = useState('');
  const [viewStyle,setViewStyle] = useState<ViewStyle>({...DEFAULT_VIEW});
  const [navigation,setNavigation] = useState<ToolMode>('orbit');
  const [picks, setPicks] = useState<Pick[]>([]); const pickCount = useRef(0); const [hover, setHover] = useState<Pick | null>(null); const lassoApi = useRef<null | ((poly: [number, number][]) => LassoHit | null)>(null); const [lassoPath, setLassoPath] = useState<[number, number][]>([]); const [noteDraft, setNoteDraft] = useState<string | null>(null); const [measureEdit, setMeasureEdit] = useState<string | null>(null); const downAt = useRef<[number, number] | null>(null);
  const [thread, setThread] = useState<Turn[]>([]); const turnCount = useRef(0);
  const say = (who: Turn['who'], text: string, extra: Partial<Turn> = {}) => setThread(t => [...t, { id: ++turnCount.current, who, text, ...extra }]);
  const [drawer, setDrawer] = useState<null | 'checks' | 'versions' | 'parameters'>(null);
  const [column, setColumn] = useState(storedWidth);
  useEffect(() => { try { localStorage.setItem('studio.column', String(column)); } catch { /* storage unavailable: width resets next visit */ } }, [column]);
  const [runtime, setRuntime] = useState('loading');
  useEffect(() => { json<{agent:string}>('/api/health').then(value => setRuntime(value.agent)).catch(() => setRuntime('unavailable')); }, []);

  const [mobileLayout, setMobileLayout] = useState(() => window.matchMedia('(max-width:760px)').matches);
  useEffect(() => { const media = window.matchMedia('(max-width:760px)'); const update = () => setMobileLayout(media.matches); media.addEventListener('change', update); return () => media.removeEventListener('change', update); }, []);
  const [dark, setDark] = useState(true); const [wireframe, setWireframe] = useState(false); const [hiddenParts, setHiddenParts] = useState<string[]>([]); const [panel, setPanel] = useState('Design'); const [mobileBrowser, setMobileBrowser] = useState(false); const [browserOpen, setBrowserOpen] = useState(true); const [inspectorOpen, setInspectorOpen] = useState(true);
  function showPanel(name: string) { setPanel(name); setInspectorOpen(true); if (name === 'Versions') setDrawer('versions'); if (name === 'Design') setDrawer('parameters'); requestAnimationFrame(() => document.getElementById(name === 'Versions' ? 'version-list' : name === 'Assistant' ? 'request' : 'drawer')?.focus()); }

  const [comparisonSide, setComparisonSide] = useState<'before' | 'after'>('after'); const [previewFailed, setPreviewFailed] = useState(false); const [readySides, setReadySides] = useState<string[]>([]); const previewReady = React.useCallback((side: string) => setReadySides(current => current.includes(side) ? current : [...current, side]), []); const [designs, setDesigns] = useState<string[]>([]); const [design, setDesign] = useState(''); const [sessionId, setSessionId] = useState(''); const [sessionState, setSessionState] = useState(''); const [preparing, setPreparing] = useState(false); const [previewAction, setPreviewAction] = useState<CameraAction>({name:'Iso',sequence:0}); const [message, setMessage] = useState(''); const [proposal, setProposal] = useState<Proposal | null>(null); const [proposalBusy, setProposalBusy] = useState(false); const [opening, setOpening] = useState(false); const [progress, setProgress] = useState<string[]>([]); const [comparison, setComparison] = useState('');
  const [folder, setFolder] = useState(''); const [folderHint, setFolderHint] = useState(false); const [project, setProject] = useState('');
  const [versions, setVersions] = useState<Version[]>([]); const [selected, setSelected] = useState<Version | null>(null); const selectionRef = useRef(''); selectionRef.current = `${project}:${selected?.id || ''}`;
  const [models, setModels] = useState<string[]>([]); const [modelVersion, setModelVersion] = useState(''); const [loading, setLoading] = useState(false); const [action, setAction] = useState<CameraAction>({name: 'Iso', sequence: 0}); const [error, setError] = useState('');
  async function open(e?: React.FormEvent, path?: string) { e?.preventDefault(); if (proposalBusy || savingMaterial || opening) return; const target = (path ?? folder).trim(); if (!target) { setFolderHint(true); document.getElementById('folder')?.focus(); return; } setFolderHint(false); setOpening(true); setError(''); try { const [result, available, printerResult] = await Promise.all([json<{versions: Version[]}>(`/api/projects/versions?project=${encodeURIComponent(target)}`), json<{designs:string[]}>(`/api/projects/designs?project=${encodeURIComponent(target)}`), json<Printer>(`/api/projects/printer?project=${encodeURIComponent(target)}`)]); setPrinter(printerResult); setMaterialNotice(''); setMaterialError(''); setDesigns(available.designs); setDesign(available.designs[0] || ''); setProposal(null); setProgress([]); setComparison(''); setThread([]); setPicks([]); setProject(target); setFolder(target); fetch('/api/workspace/recent', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({project: target})}).catch(() => {}); if (window.matchMedia('(max-width:760px)').matches) setInspectorOpen(false); setVersions(result.versions); setSelected(result.versions.find(v => v.current) || result.versions[0] || null); } catch (err) { setError((err as Error).message); } finally { setOpening(false); } }
  async function post<T>(path:string, body:unknown):Promise<T> { const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); const value = await response.json(); if (!response.ok) throw new Error(value.error || 'Request failed'); return value as T; }
  async function requestProposal(edit?: {name:string;value:number}) { const chosen = edit ? [] : picks; const request = edit ? '' : message.trim() + (chosen.length ? `\n\nSelected on the model: ${chosen.map(describe).join('; ')}.` : ''); say('you', edit ? `Set ${edit.name} to ${edit.value}` : message.trim(), {chips: chosen.map(label)}); if (!edit) { setMessage(''); setPicks([]); } setProposalBusy(true); setPreviewFailed(false); setReadySides([]); setPreparing(true); setSessionId(''); setComparisonSide('after'); setProposal(null); setError(''); setProgress([]); setComparison(''); try { const result = await post<Proposal>('/api/proposals', {project, ...(edit ? {parameter:edit} : {message: request}), selection:{design}}); setSessionId(result.id); setSessionState('running'); const session = new EventSource(`/api/proposals/${result.id}/events`); session.addEventListener('plan', e => { const event = JSON.parse((e as MessageEvent).data); setProgress(p => [...p, event.message]); }); session.addEventListener('preview', e => { const event = JSON.parse((e as MessageEvent).data); setProgress(p => [...p, `Prepared ${event.side} preview`]); }); session.addEventListener('interrupted', () => setSessionState('interrupted')); session.addEventListener('resumed', () => setSessionState('running')); session.addEventListener('ready', async () => { session.close(); try { const ready = await json<Proposal>(`/api/proposals/${result.id}`); setProposal(ready); setSessionState('ready'); say('assistant', ready.changes.length === 1 ? 'I prepared one change. Both previews use the same scale, so compare them on the model before you keep it.' : `I prepared ${ready.changes.length} changes. Compare the previews on the model before you keep them.`); } catch(err) { setError((err as Error).message); say('assistant', (err as Error).message, {tone:'error'}); } finally { setPreparing(false); setProposalBusy(false); } }); session.addEventListener('error', async e => { if (!(e instanceof MessageEvent)) { setProgress(p => [...p, 'Reconnecting to preview updates…']); return; } session.close(); try { const state = await json<{error:string|null}>(`/api/proposals/${result.id}`); setError(state.error || 'Preview updates disconnected.'); say('assistant', state.error || 'Preview updates disconnected.', {tone:'error'}); } catch { setError('Preview updates disconnected.'); } setPreparing(false); setProposalBusy(false); }); } catch(err) { setError((err as Error).message); say('assistant', (err as Error).message, {tone:'error'}); setPreparing(false); setProposalBusy(false); } }
  async function propose(e:React.FormEvent) { e.preventDefault(); if (!message.trim() || proposalBusy || !selected?.current) return; await requestProposal(); }
  async function controlSession(action:'interrupt'|'resume') { try { await post(`/api/proposals/${sessionId}/${action}`, {}); } catch(err) { setError((err as Error).message); } }
  async function reject() { if (!proposal) return; setProposalBusy(true); try { await post(`/api/proposals/${proposal.id}/reject`, {}); setProposal(null); say('assistant', 'Discarded. The project is unchanged.'); if (window.matchMedia('(max-width:760px)').matches) setInspectorOpen(false); } catch(err) { setError((err as Error).message); } finally { setProposalBusy(false); } }
  async function accept() { if (!proposal) return; setProposalBusy(true); setError(''); setProgress([]); const previous = versions.find(v => v.current)?.verdict; try { const result = await post<{run:{id:string}}>(`/api/proposals/${proposal.id}/accept`, {}); setProposal(null); if (window.matchMedia('(max-width:760px)').matches) setInspectorOpen(false); const stream = new EventSource(`/api/runs/${result.run.id}/events`); stream.addEventListener('gate_started', e => { const event = JSON.parse((e as MessageEvent).data); setProgress(p => [...p, `Checking ${event.gate}`]); }); stream.addEventListener('gate_finished', e => { const event = JSON.parse((e as MessageEvent).data); setProgress(p => [...p, `${event.gate}: ${event.status}`]); }); stream.addEventListener('end', async () => { stream.close(); try { const run = await json<{status:string; error:string|null; verdict:{pass:boolean}|null}>(`/api/runs/${result.run.id}`); if (run.status !== 'done' || !run.verdict) throw new Error(run.error || 'Checks failed to finish'); const latest = await json<{versions:Version[]}>(`/api/projects/versions?project=${encodeURIComponent(project)}`); setVersions(latest.versions); setSelected(latest.versions.find(v => v.current) || null); const summary = `Previous: ${previous ? previous.pass ? 'passed' : 'failed' : 'not checked'} · Now: ${run.verdict.pass ? 'passed' : 'failed'}`; setComparison(summary); say('assistant', run.verdict.pass ? `Kept and saved as version ${latest.versions[0]?.number}. The checks passed.` : `Kept and saved as version ${latest.versions[0]?.number}, but a check failed. See the verdict above.`, {chips:[summary]}); } catch(err) { setError((err as Error).message); } finally { setProposalBusy(false); } }); stream.onerror = () => { stream.close(); setError('Live updates disconnected. Reopen the project to see its latest version.'); setProposalBusy(false); }; } catch(err) { setError((err as Error).message); setProposalBusy(false); } }
  async function changeMaterial(material: string) {
    setSavingMaterial(true); setMaterialNotice('Saving material…'); setMaterialError('');
    try {
      const response = await fetch('/api/projects/printer', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({project, material})});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Could not update material');
      setPrinter(result as Printer); setMaterialNotice(`Material set to ${material} for future checks.`);
    } catch (err) { setMaterialNotice(''); setMaterialError((err as Error).message); } finally { setSavingMaterial(false); }
  }
  useEffect(() => { if (!selected || !project) return; let active = true; setError(''); setModels([]); setLoading(true); const query = new URLSearchParams({project, version:selected.id}); json<{models:string[]}>(`/api/projects/version-artifacts?${query}`).then(data => { if (active) { setModels(data.models); setModelVersion(`${project}:${selected.id}`); setLoading(false); } }).catch(err => { if (active) { setError(err.message); setLoading(false); } }); return () => { active = false; }; }, [project, selected]);
  useEffect(() => {
    if (!selected || !project) { setDetails(null); return; }
    let active = true; setDetails(null); setDetailsError('');
    const query = new URLSearchParams({project, version: selected.id});
    json<Details>(`/api/projects/version-details?${query}`).then(data => { if (active) setDetails(data); }).catch(err => { if (active) setDetailsError(err.message); });
    return () => { active = false; };
  }, [project, selected]);
  async function rebuild() { if (!selected) return; const requested = `${project}:${selected.id}`; setLoading(true); setError(''); try { const response = await fetch('/api/projects/version-artifacts', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({project, version:selected.id})}); const result = await response.json(); if (!response.ok) throw new Error(result.error); const query = new URLSearchParams({project, version:selected.id}); const data = await json<{models:string[]}>(`/api/projects/version-artifacts?${query}`); if (selectionRef.current === requested) { setModels(data.models); setModelVersion(requested); } } catch (err) { if (selectionRef.current === requested) setError((err as Error).message); } finally { if (selectionRef.current === requested) setLoading(false); } }
  const shownModels = modelVersion === selectionRef.current ? models : [];
  const url = (path: string) => `/api/projects/version-artifacts?${new URLSearchParams({project, version:selected!.id, path})}`;
  const viewReady = proposal ? readySides.length === 2 && !previewFailed : shownModels.length > 0;
  const cameraCommand = (name:string) => { if (proposal) setPreviewAction(p => ({name,sequence:p.sequence+1})); else setAction(p => ({name,sequence:p.sequence+1})); };
  const focusComposer = () => requestAnimationFrame(() => document.getElementById('request')?.focus());
  const commands:StudioCommand[] = [
    ...['Iso','Front','Top','Side','Fit','Zoom in','Zoom out'].map(name => ({id:'view-'+name,title:name === 'Iso' ? 'Isometric view' : name === 'Fit' ? 'Fit model' : name.startsWith('Zoom') ? name : name+' view',section:'Viewport',icon:(name==='Iso'?'iso':name==='Front'?'front':name==='Top'?'top':name==='Side'?'side':name==='Fit'?'fitModel':name==='Zoom in'?'zoomIn':'zoomOut') as import('./icons').IconName,disabled:!viewReady || (name==='Fit' && !!proposal),action:() => cameraCommand(name)})),
    {id:'assistant',title:`Ask ${ASSISTANT} for a change`,section:'Workspace',icon:'chat',disabled:!selected || !!proposal,action:focusComposer},
    {id:'checks',title:'Show evidence',section:'Workspace',icon:'check',disabled:!selected,action:() => setDrawer('checks')},
    {id:'history',title:'Show versions',section:'Workspace',icon:'history',disabled:!selected,action:() => setDrawer('versions')},
    {id:'inspector',title:'Show settings',section:'Workspace',icon:'parameters',disabled:!selected || !!proposal,action:() => setDrawer('parameters')},
    {id:'theme',title:dark ? 'Use light theme' : 'Use dark theme',section:'Appearance',icon:dark ? 'sun' : 'moon',action:() => setDark(v => !v)}
  ];
  useEffect(() => { setPicks([]); }, [selected?.id, project]);
  const lassoing = navigation === 'lasso';
  useEffect(() => { const key = (e: KeyboardEvent) => { if (e.key !== 'Escape' || (e.target as HTMLElement)?.closest?.('input,textarea')) return; if (lassoing) setNavigation('orbit'); else { setPicks([]); setNoteDraft(null); } }; window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key); }, [lassoing]);
  const [compareSingle, setCompareSingle] = useState(false);
  const makePick = (kind: Pick['kind'], body: string, geometry: BufferGeometry, point: Vector3, faceIndex?: number | null, normal?: Vector3): Pick => {
    const base = { id: `pick-${++pickCount.current}`, kind, body, geometry, point: point.toArray() as Pick['point'] };
    if (kind === 'face' && faceIndex != null) { const r = regionAt(geometry, faceIndex, point); return { ...base, region: r.region, area: r.area, flat: r.flat, normal: r.normal.toArray() as Pick['normal'], centroid: r.centroid.toArray() as Pick['centroid'] }; }
    geometry.computeBoundingBox(); const c = geometry.boundingBox!.getCenter(new Vector3());
    return { ...base, normal: (normal?.toArray() || [0, 0, 1]) as Pick['normal'], centroid: c.toArray() as Pick['centroid'] };
  };
  const add = (next: Pick, extend: boolean) => { setNoteDraft(null); setPicks(current => extend ? [...current.filter(p => !(p.kind === next.kind && p.body === next.body && p.kind === 'body')), next] : [next]); };
  const interact = (body: string) => ({
    pick: (e: ThreeEvent<MouseEvent>, g: BufferGeometry) => { if (lassoing || e.delta > 4) return; e.stopPropagation(); add(makePick('face', body, g, e.point, e.faceIndex), e.shiftKey); },
    body: (e: ThreeEvent<MouseEvent>, g: BufferGeometry) => { if (lassoing) return; e.stopPropagation(); const next = makePick('body', body, g, e.point); setPicks(current => e.shiftKey ? [...current.filter(p => p.body !== body), next] : [next]); },
    hover: (e: ThreeEvent<PointerEvent> | null, g: BufferGeometry) => { if (!e || lassoing || e.buttons) { setHover(null); return; } e.stopPropagation(); if (hover && hover.body === body && e.faceIndex != null && hover.region && regionAt(g, e.faceIndex, e.point).region.length === hover.region.length && hover.geometry === g) return; setHover(makePick('face', body, g, e.point, e.faceIndex)); },
  });
  function finishLasso(path: [number, number][], extend: boolean) {
    setLassoPath([]); if (path.length < 6 || !lassoApi.current) return;
    const hit = lassoApi.current(path);
    if (hit) {
      const centroid = hit.loop.reduce((c, v) => c.add(v), new Vector3()).divideScalar(hit.loop.length);
      const next: Pick = { id: `pick-${++pickCount.current}`, kind: 'area', body: hit.body, geometry: hit.geometry, region: hit.region, loop: new Float32Array(hit.loop.flatMap(v => v.toArray())), area: loopArea(hit.loop), flat: false, point: centroid.toArray() as Pick['point'], centroid: centroid.toArray() as Pick['centroid'], normal: hit.normal.toArray() as Pick['normal'] };
      setPicks(current => extend ? [...current, next] : [next]);
    }
    setNavigation('orbit');
  }
  const anchor = picks[picks.length - 1];
  const measured = picks.length === 2 ? measure(picks[0], picks[1]) : null;
  const updateAnchor = (change: Partial<Pick>) => setPicks(current => current.map(p => p.id === anchor?.id ? { ...p, ...change } : p));
  const bodyName = (path: string, i: number) => path.split('/').pop()?.replace(/\.stl$/i, '') || `Body ${i + 1}`;
  const lastReady = versions.filter(v => v.verdict?.pass).sort((a, b) => b.number - a.number)[0]?.number;
  function startResize(event: React.PointerEvent) {
    const startX = event.clientX, startWidth = column;
    const move = (e: PointerEvent) => setColumn(Math.min(COLUMN.max, Math.max(COLUMN.min, startWidth + e.clientX - startX)));
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); document.body.classList.remove('resizing'); };
    document.body.classList.add('resizing'); window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  }
  const projectName = project ? project.split('/').filter(Boolean).pop() : '';
  const errorInThread = thread.some(t => t.tone === 'error' && t.text === error);
  const focusComposerSoon = () => requestAnimationFrame(() => document.getElementById('request')?.focus());
  return <main className={`app desk${dark ? ' dark' : ''}`} style={{ '--column': `${column}px` } as React.CSSProperties}>
    <header className="app-header">
      <a className="brand" href="#" aria-label="Magic CAD Studio"><BrandMark className="brand-mark" surface={dark ? 'dark' : 'light'}/><Wordmark className="brand-wordmark"/></a>
      {project ? <details className="project-switch"><summary title={project}>{projectName}</summary><form className="project-open compact" noValidate onSubmit={e => { open(e); (e.currentTarget.closest('details') as HTMLDetailsElement | null)?.removeAttribute('open'); }}><label htmlFor="folder">Project folder</label><div className="open-field"><input id="folder" value={folder} onChange={e => { setFolder(e.target.value); setFolderHint(false); }} placeholder="/path/to/project" aria-describedby={folderHint ? 'folder-hint' : undefined} aria-invalid={folderHint || undefined} autoComplete="off" spellCheck={false}/><button className="open-button" aria-label="Open project" disabled={proposalBusy || opening}>{opening ? 'Opening…' : 'Open'}<Icon name="arrow"/></button></div>{folderHint && <p id="folder-hint" className="field-hint">Enter the folder that holds your project.</p>}</form></details> : <span className="project-name">No project open</span>}
      <nav className="mode-nav" aria-label="Workspace modes">{(['Make', 'Studio', 'Mission Control'] as Mode[]).map(name => <button type="button" key={name} aria-current={mode === name ? 'page' : undefined} onClick={() => setMode(name)}>{name}</button>)}</nav>
      <span className="save-state">{proposalBusy ? 'Working…' : project ? 'Saved locally' : 'Local studio'}</span>
      <CommandSearch items={commands}/>
      <button className="theme-button" onClick={() => setDark(v => !v)} aria-label={dark ? 'Use light theme' : 'Use dark theme'}><Icon name={dark ? 'sun' : 'moon'}/></button>
    </header>
    <section className="desk-workspace" hidden={mode !== 'Studio'}>
      <section className="conversation" aria-label={`${ASSISTANT} conversation`}>
        {!project ? <div className="project-open">
          <h1>Open a project</h1>
          <p>{ASSISTANT} works on a project folder on this computer. Nothing leaves it.</p>
          <ProjectPicker busy={opening || proposalBusy} onOpen={path => open(undefined, path)}>
            <form className="type-path-form" onSubmit={open} noValidate><label htmlFor="folder" className="type-path">Or type a project folder path</label>
            <div className="open-field"><input id="folder" value={folder} onChange={e => { setFolder(e.target.value); setFolderHint(false); }} placeholder="/path/to/project" aria-describedby={folderHint ? 'folder-hint' : undefined} aria-invalid={folderHint || undefined} autoComplete="off" spellCheck={false}/><button className="open-button" aria-label="Open project" disabled={proposalBusy || opening}>{opening ? 'Opening…' : 'Open'}<Icon name="arrow"/></button></div>{folderHint && <p id="folder-hint" className="field-hint">Enter the folder that holds your project.</p>}</form>
          </ProjectPicker>
          {error && <p role="alert" className="error">{error}</p>}
        </div> : <>
          {selected && <Verdict number={selected.number} verdict={selected.verdict} assistant={ASSISTANT} lastReady={lastReady !== selected.number ? lastReady : undefined} onFix={text => { setMessage(text); focusComposer(); }} onShowVersion={n => { const v = versions.find(x => x.number === n); if (v) setSelected(v); }} onEvidence={() => setDrawer('checks')}/>}
          <div className="thread">
            <div className="turn assistant"><span className="who">{ASSISTANT}</span><p>{runtime === 'claude' ? 'Tell me what to change, like “make the wall 0.5 mm thicker”. Select part of the model first to be precise. I use your local Claude Code login.' : runtime === 'scripted' ? 'Scripted test runtime: enter a setting and a value, for example “size 24”.' : 'I’m unavailable right now. Check that the local engine is running.'}</p></div>
            {thread.map(turn => <div key={turn.id} className={`turn ${turn.who}${turn.tone ? ' ' + turn.tone : ''}`}>{turn.who === 'assistant' && <span className="who">{ASSISTANT}</span>}<p>{turn.text}</p>{turn.chips && turn.chips.length > 0 && <ul className="turn-chips">{turn.chips.map(c => <li key={c}>{c}</li>)}</ul>}</div>)}
            {preparing && <div className="turn assistant working"><span className="who">{ASSISTANT}</span><div role="status" className="gate-progress">{progress.length ? progress.map((line, i) => <div key={i}>{line}</div>) : <div>{sessionState === 'interrupted' ? 'Preview paused.' : 'Preparing previews…'}</div>}</div><button type="button" className="quiet-button" disabled={!sessionId} onClick={() => controlSession(sessionState === 'interrupted' ? 'resume' : 'interrupt')}>{sessionState === 'interrupted' ? 'Resume' : 'Interrupt'}</button></div>}
            {!preparing && !proposal && progress.length > 0 && <div role="status" className="turn assistant gate-progress quiet">{progress.map((line, i) => <div key={i}>{line}</div>)}</div>}
            {proposal && <section className="turn assistant review" aria-label="Proposed edit">
              <span className="who">{ASSISTANT}</span>
              <h3 role="status">Proposed change ready to review</h3>
              <div className="review-diff"><span className="review-part">{niceName(design)}</span>{proposal.changes.map(c => <strong key={c.parameter}>{c.parameter}: <del>{c.old}</del> <span aria-label="to">→</span> <ins>{c.new}</ins></strong>)}</div>
              <p className="review-note">Previews are unchecked. Keeping the change saves a new version and runs the checks.</p>
              {readySides.length < 2 && !previewFailed && <p role="status" className="review-note">Loading both previews…</p>}
              {previewFailed && <p role="alert">A preview could not be loaded. Discard the change and propose it again to retry.</p>}
              <div className="review-actions">
                <button type="button" className="keep-button" aria-label="Accept change (Keep)" disabled={proposalBusy || previewFailed || readySides.length < 2 || !selected?.current} onClick={accept}><Icon name="check"/>Keep change</button>
                <div className="tray"><button type="button" className="tray-button" aria-label="Reject change (Discard)" disabled={proposalBusy} onClick={reject}>Discard</button><button type="button" className="tray-button" aria-pressed={compareSingle} disabled={readySides.length < 2 || previewFailed} onClick={() => setCompareSingle(v => !v)}>{compareSingle ? 'Side by side' : 'One at a time'}</button></div>
              </div>
              {!selected?.current && <p className="review-note">Select the current version to accept this proposal.</p>}
            </section>}
          </div>
          <form className="composer-form" onSubmit={propose} noValidate>
            {designs.length > 1 && <div className="part-picker"><label htmlFor="design">Part</label><select id="design" value={design} onChange={e => setDesign(e.target.value)} disabled={proposalBusy}>{designs.map(name => <option key={name} value={name}>{niceName(name)}</option>)}</select></div>}
            <label htmlFor="request" className="sr-only">Change request</label>
            <div className="composer">
              {picks.length > 0 && <ul className="pick-chips" aria-label="Selected on the model">{picks.map(p => <li key={p.id}><span>{label(p)}</span><button type="button" aria-label={`Remove ${label(p)}`} onClick={() => setPicks(c => c.filter(x => x.id !== p.id))}><Icon name="close"/></button></li>)}</ul>}
              <textarea id="request" rows={2} value={message} placeholder={picks.length ? 'What should change here?' : runtime === 'claude' ? 'Make the wall 0.5 mm thicker' : 'size 24'} onChange={e => setMessage(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }} disabled={proposalBusy}/>
              <div className="composer-footer"><small aria-hidden="true">{picks.length ? 'Selection rides along as positions and directions' : 'Click the model to point at a part'}</small><ToolHint text="Propose change (Enter)"><button className="composer-send" aria-label="Propose change" disabled={proposalBusy || opening || !selected?.current || !message.trim()}><Icon name="arrow"/></button></ToolHint></div>
            </div>
            {selected && !selected.current && <p className="composer-note">Select the current version to propose a change.</p>}
            {error && !errorInThread && <p role="alert" className="error">{error}</p>}
          </form>
        </>}
      </section>
      <div className="column-resizer" role="separator" aria-orientation="vertical" aria-label="Resize conversation" aria-valuemin={COLUMN.min} aria-valuemax={COLUMN.max} aria-valuenow={column} tabIndex={0} onPointerDown={startResize} onDoubleClick={() => setColumn(COLUMN.initial)} onKeyDown={e => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); setColumn(w => Math.min(COLUMN.max, Math.max(COLUMN.min, w + (e.key === 'ArrowRight' ? 24 : -24)))); } }}/>
      <div className={`stage${lassoing ? ' lassoing' : ''}`} onPointerDown={e => { downAt.current = [e.clientX, e.clientY]; }}>
        {!proposal && shownModels.length > 0 && <ViewportTools ready={shownModels.length > 0} mode={navigation} onMode={setNavigation} onAction={cameraCommand} style={viewStyle} onStyle={setViewStyle} wireframe={wireframe} onWireframe={() => setWireframe(v => !v)}/>}
        <div className="stage-bar">
          {proposal ? <div className="body-chips"><span className="chip-label">Preview bodies</span>{proposal.previews[comparisonSide].map((path, i) => <span key={path} className="body-toggle static">Body {i + 1}</span>)}</div>
            : shownModels.length > 0 && <div className="body-chips" role="group" aria-label="Bodies">{shownModels.map((path, i) => <button key={path} type="button" className="body-toggle" aria-pressed={!hiddenParts.includes(path)} title={hiddenParts.includes(path) ? 'Show body' : 'Hide body'} onClick={() => setHiddenParts(p => p.includes(path) ? p.filter(n => n !== path) : [...p, path])}><Icon name={hiddenParts.includes(path) ? 'eyeOff' : 'eye'}/>{bodyName(path, i)}</button>)}<span className="chip-label">mm · Z up</span></div>}
          {selected && models.length > 0 && !proposal && <div className="stage-actions tray"><button type="button" className="tray-button" aria-pressed={wireframe} onClick={() => setWireframe(v => !v)}><Icon name="wire"/>Wireframe</button><details className="export-menu"><summary><Icon name="download"/>Export STL</summary><div>{models.map(path => <a key={path} href={url(path)} download={path.split('/').pop()}>{path.split('/').pop()}</a>)}</div></details></div>}
        </div>
        {!proposal && shownModels.length > 0 && <p className="select-hint" role="status">{lassoing ? 'Draw around the area you mean. Shift adds to the selection; Escape cancels.' : picks.length ? 'Shift-click adds · double-click selects a whole body · Escape clears' : 'Click a face to point at it · double-click for the whole body'}</p>}
        {lassoing && shownModels.length > 0 && !proposal && <svg className="lasso-layer" role="presentation"
          onPointerDown={e => { (e.currentTarget as Element).setPointerCapture(e.pointerId); const r = e.currentTarget.getBoundingClientRect(); setLassoPath([[e.clientX - r.left, e.clientY - r.top]]); }}
          onPointerMove={e => { if (!lassoPath.length) return; const r = e.currentTarget.getBoundingClientRect(); setLassoPath(p => [...p, [e.clientX - r.left, e.clientY - r.top]]); }}
          onPointerUp={e => finishLasso(lassoPath, e.shiftKey)}>
          {lassoPath.length > 1 && <path d={`M${lassoPath.map(p => p.join(',')).join('L')}Z`}/>}
        </svg>}
        {proposal ? <div className={`comparison-stage${compareSingle ? ' single' : ''}`}><div className="comparison-heading"><div><h2>Change review</h2><p>Inspect the proposed geometry</p></div><span>Unchecked previews · same scale</span></div><div className="mobile-comparison-switch" role="group" aria-label="Preview to show">{(['before','after'] as const).map(side => <button type="button" key={side} aria-pressed={comparisonSide === side} onClick={() => setComparisonSide(side)}>{side === 'before' ? 'Before' : 'After'}</button>)}</div><div className="comparison-models" data-mobile-side={comparisonSide}>{(['before','after'] as const).map(side => <figure key={side}><figcaption>{side === 'before' ? 'Before' : 'After'}</figcaption><div className="comparison-canvas" role="img" aria-label={`${side} preview`}><ModelError message="Preview unavailable. Reject the change and propose it again to retry." onError={() => setPreviewFailed(true)}><LoadingNotice/><Canvas frameloop="demand" camera={{position:[100,-140,110], up:[0,0,1], fov:35}}><StudioEnvironment/><ambientLight intensity={0.45}/><hemisphereLight args={["#fffaf2", "#77716a", 0.7]}/><directionalLight position={[100,-80,160]} intensity={2}/><OrbitControls makeDefault enableZoom={false} enablePan={false} enableRotate={false}/><Suspense fallback={null}><ComparisonModels proposal={proposal} side={side} onReady={previewReady}/></Suspense><CameraView action={previewAction}/></Canvas></ModelError></div><details className="model-measurements"><summary><Icon name="fit"/>Envelope</summary><div>{proposal.preview_dimensions[side].map((dims,i) => <p key={i}><strong>Body {i+1}</strong><span>{dims.map(n => n.toFixed(1)).join(' × ')} mm</span></p>)}</div></details></figure>)}</div><div role="group" aria-label="Preview camera controls" className="comparison-controls">{['Iso','Front','Top','Side'].map(name => <button type="button" key={name} aria-pressed={previewAction.name === name} disabled={readySides.length < 2 || previewFailed} onClick={() => setPreviewAction(p => ({name,sequence:p.sequence+1}))}>{name}</button>)}<details className="comparison-more"><summary>Move camera</summary><div>{['Orbit left','Orbit right','Orbit up','Orbit down','Pan left','Pan right','Pan up','Pan down','Zoom in','Zoom out'].map(name => <button type="button" key={name} aria-pressed={previewAction.name === name} disabled={readySides.length < 2 || previewFailed} onClick={() => setPreviewAction(p => ({name,sequence:p.sequence+1}))}>{name}</button>)}</div></details></div></div> : shownModels.length ? <div className="canvas" aria-label="3D model" role="img"><ModelError key={selectionRef.current}><LoadingNotice/><Canvas camera={{position:[100,-140,110], up:[0,0,1], fov:35}} onPointerMissed={e => { const d = downAt.current; if (!lassoing && d && Math.hypot(e.clientX - d[0], e.clientY - d[1]) < 5) { setPicks([]); setNoteDraft(null); } }}><StudioEnvironment light={viewStyle.light}/><Workplane visible={viewStyle.grid} dark={dark}/><ambientLight intensity={1.5 * viewStyle.light / 100}/><directionalLight position={[100,-80,160]} intensity={2 * viewStyle.light / 100}/><Suspense fallback={null}><Bounds fit clip observe margin={1.4}>{shownModels.map((path, i) => <Model key={url(path)} url={url(path)} name={bodyName(path, i)} visible={!hiddenParts.includes(path)} wireframe={wireframe} style={viewStyle} interact={interact(bodyName(path, i))}/>)}</Bounds>
          {hover && !picks.some(p => p.region && hover.region && p.body === hover.body && p.region.length === hover.region.length) && <Highlight pick={hover} colour="#e57b46" hover/>}
          {picks.map(p => <Highlight key={p.id} pick={p} colour={p.locked ? '#8fbf98' : '#e57b46'}/>)}
          {measured && <group><line><bufferGeometry attach="geometry" onUpdate={g => g.setFromPoints([new Vector3(...measured.from), new Vector3(...measured.to)])}/><lineBasicMaterial attach="material" color="#f0e2c8" depthTest={false}/></line>
            <Html position={measured.from.map((v, k) => (v + measured.to[k]) / 2) as [number, number, number]} center zIndexRange={[20, 10]}>{measureEdit === null ? <button type="button" className="dimension-label" title={`${measured.kind}. Click to change it`} onClick={() => setMeasureEdit(measured.value.toFixed(1))}>{measured.value.toFixed(1)} mm</button> : <form className="dimension-edit" onSubmit={e => { e.preventDefault(); const next = Number(measureEdit); if (next > 0) { setMessage(`Make the ${measured.kind === 'gap between parallel faces' ? 'gap between these two faces' : 'distance between these two selections'} ${next} mm (it is ${measured.value.toFixed(1)} mm now).`); focusComposerSoon(); } setMeasureEdit(null); }}><input autoFocus onFocus={e => e.currentTarget.select()} aria-label="New distance in millimetres" inputMode="decimal" value={measureEdit} onChange={e => setMeasureEdit(e.target.value)} onBlur={() => setMeasureEdit(null)}/><span>mm</span></form>}</Html></group>}
          {anchor && !proposal && <Html position={anchor.kind === 'body' ? anchor.centroid : anchor.point} zIndexRange={[30, 20]} style={{ pointerEvents: 'auto' }}>
            <div className="selection-bar" role="toolbar" aria-label="Selection actions" onPointerDown={e => e.stopPropagation()}>
              {noteDraft === null ? <>
                <span className="selection-name">{picks.length > 1 ? `${picks.length} selected` : label(anchor)}</span>
                <button type="button" onClick={focusComposerSoon}><Icon name="chat"/>Ask</button>
                <button type="button" disabled={!measured} title={measured ? 'Show the distance on the model' : 'Shift-click a second face to measure'} aria-pressed={!!measured} onClick={() => setMeasureEdit(measured ? measured.value.toFixed(1) : null)}><Icon name="fit"/>Measure</button>
                <button type="button" onClick={() => setNoteDraft(anchor.note || '')}><Icon name="pin"/>{anchor.note ? 'Edit note' : 'Note'}</button>
                <button type="button" aria-pressed={!!anchor.locked} onClick={() => updateAnchor({ locked: !anchor.locked })}><Icon name="check"/>Keep as is</button>
                <button type="button" className="selection-clear" aria-label="Clear selection" onClick={() => setPicks([])}><Icon name="close"/></button>
              </> : <form className="note-form" onSubmit={e => { e.preventDefault(); updateAnchor({ note: noteDraft.trim() || undefined }); setNoteDraft(null); }}>
                <input autoFocus aria-label="Note for this selection" placeholder="What about this spot?" value={noteDraft} onChange={e => setNoteDraft(e.target.value)}/>
                <button type="submit">Add note</button>
              </form>}
            </div>
          </Html>}
          <LassoBridge api={lassoApi}/>
        </Suspense><CameraView action={action}/><OrbitControls makeDefault mouseButtons={{LEFT:navigation==='pan'?MOUSE.PAN:MOUSE.ROTATE,MIDDLE:MOUSE.DOLLY,RIGHT:MOUSE.PAN}} touches={{ONE:navigation==='pan'?TOUCH.PAN:TOUCH.ROTATE,TWO:TOUCH.DOLLY_PAN}} /></Canvas></ModelError></div> : <div className="empty" role="status">{selected ? loading ? 'Loading model…' : error ? 'The model could not be loaded.' : <span>No saved model is available for this version. {selected.verdict?.pass === false ? ' Models are exported after checks pass.' : <button type="button" onClick={rebuild}>Rebuild model</button>}</span> : 'Open a project to see your design.'}</div>}
        <div className="views" hidden={!!proposal || !shownModels.length} role="group" aria-label="Camera controls">{['Iso','Front','Top','Side'].map(name => <button key={name} type="button" aria-pressed={action.name === name} disabled={!shownModels.length} onClick={() => setAction(previous => ({name, sequence: previous.sequence + 1}))}><Icon name={name==='Iso'?'iso':name==='Front'?'front':name==='Top'?'top':'side'}/><span>{name}</span></button>)}<details className="camera-more"><summary>Move camera</summary><div className="camera-actions">{['Orbit left','Orbit right','Orbit up','Orbit down','Pan left','Pan right','Pan up','Pan down','Zoom in','Zoom out'].map(name => <button key={name} type="button" aria-pressed={action.name === name} disabled={!shownModels.length} onClick={() => setAction(previous => ({name, sequence: previous.sequence + 1}))}>{name}</button>)}</div></details></div><p className="hint" hidden={!!proposal || !shownModels.length}><span className="desktop-hint">{navigation==='pan' ? 'Drag to pan; scroll to zoom' : 'Drag to orbit; right-drag to pan; scroll to zoom'}</span><span className="touch-hint">{navigation==='pan' ? 'Drag to pan; pinch to zoom' : 'Drag to orbit; pinch to zoom'}</span></p>
      </div>
      <nav className="drawer-rail" aria-label="Details">{([['checks', 'Checks', 'check'], ['versions', 'Versions', 'history'], ['parameters', 'Settings', 'parameters']] as const).map(([key, text, icon]) => <button key={key} type="button" aria-pressed={drawer === key} aria-controls="drawer" disabled={!selected} onClick={() => setDrawer(d => d === key ? null : key)}><Icon name={icon}/><span className="rail-label">{text}</span></button>)}</nav>
      <aside id="drawer" className="drawer" hidden={!drawer || !selected} tabIndex={-1} aria-label={drawer === 'checks' ? 'Evidence' : drawer === 'versions' ? 'Versions' : 'Settings'}>
        <div className="drawer-heading"><h2>{drawer === 'checks' ? 'Evidence' : drawer === 'versions' ? 'Versions' : 'Settings'}</h2><button type="button" className="icon-button" aria-label="Close details" onClick={() => setDrawer(null)}><Icon name="close"/></button></div>
        {selected && drawer === 'checks' && <><p className="drawer-note">Harness checks only, not a design review or a print.</p>{selected.verdict ? <Evidence designs={selected.verdict.designs || []}/> : <p className="drawer-note">This version has not been checked.</p>}</>}
        {selected && drawer === 'versions' && <ol id="version-list" tabIndex={-1}>{versions.map(v => <li key={v.id}><button aria-current={selected.id === v.id ? 'true' : undefined} onClick={() => setSelected(v)}><span>Version {v.number}{v.current ? ' · Current' : ''}<em className={`version-state ${v.verdict ? v.verdict.pass ? 'pass' : 'fail' : 'pending'}`}>{v.verdict ? v.verdict.pass ? 'Ready' : 'Not ready' : 'Not checked'}</em></span><small>{v.message}</small><time>{new Date(v.timestamp).toLocaleString()}</time></button></li>)}</ol>}
        {selected && drawer === 'parameters' && <>{designs.length > 1 && <div className="parameter-design"><label htmlFor="parameter-design">Part</label><select id="parameter-design" value={design} disabled={proposalBusy} onChange={e => setDesign(e.target.value)}>{designs.map(name => <option key={name} value={name}>{niceName(name)}</option>)}</select></div>}<ParameterPanel project={project} design={design} version={selected.id} current={selected.current} busy={proposalBusy || opening} onPropose={(name, value) => requestProposal({name, value})}/>{printer && <section className="printer-settings" aria-labelledby="printer-heading"><h3 id="printer-heading">Printer</h3><p>{printer.profile.name}<br/><small>{printer.profile.build_volume_mm.join(' × ')} mm · {printer.profile.nozzle_mm} mm nozzle</small></p><label htmlFor="material">Material</label><select id="material" aria-describedby="material-help material-error" value={printer.material} disabled={savingMaterial || opening || proposalBusy} onChange={e => changeMaterial(e.target.value)}>{Object.keys(printer.profile.materials).map(material => <option key={material} value={material}>{material}</option>)}</select><p id="material-help" className="printer-note">For future checks; existing version verdicts do not change. Fit clearances are uncalibrated. Save a version to keep this setting in the timeline.</p><p id="material-error" role="alert" className="error">{materialError}</p><p role="status" className="printer-note">{materialNotice}</p></section>}</>}
      </aside>
    </section>
    {mode !== 'Studio' && <section className={mode === 'Mission Control' ? 'expert' : 'make-mode'}><h1>{mode}</h1>{!selected ? <p>Open a project in Studio to get started.</p> : <><p className="version-context">{project} · Version {selected.number}</p>{mode === 'Make' ? <p>Make is not available yet. Return to Studio to inspect your project and its versions.</p> : <>{detailsError && <p role="alert">Could not load this version: {detailsError}</p>}{!details && !detailsError && <p role="status">Loading version details…</p>}{details && <><section><h2>Brief card</h2>{details.briefs.length ? details.briefs.map(file => <div key={file.name}><h3>{file.name}</h3><pre>{file.content}</pre></div>) : <p>No brief card was saved with this version.</p>}</section><section><h2>Gate report</h2>{details.report ? details.report.designs.map(design => <div key={design.design}><h3>{design.design}</h3><ul className="gate-list">{design.gates.map(gate => <li key={gate.name}><strong>{gate.name}</strong><span><i aria-hidden="true" className={`mark ${gate.status === 'PASS' ? 'pass' : gate.status === 'FAIL' || gate.status === 'ERROR' ? 'fail' : 'pending'}`} />{gate.status}</span><p>{gate.detail}</p></li>)}</ul><details><summary>Full report</summary><pre>{JSON.stringify(details.report, null, 2)}</pre></details></div>) : <p>No gate report is saved for this version.</p>}</section><section><h2>Design code</h2>{details.designs.map(file => <div key={file.name}><h3>{file.name.split('/').pop()}</h3><pre><code>{file.content}</code></pre></div>)}</section></>}<PartsList project={project}/><Catalogue project={project}/></>}</>}</section>}
    <footer className="app-status"><span>{project ? 'Engine connected' : 'Ready to open a project'}</span><span>{proposal ? 'Reviewing proposed change' : selected ? `Version ${selected.number} · ${shownModels.length} bodies` : 'Magic CAD Studio'}</span><span>mm · Local workspace</span></footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
