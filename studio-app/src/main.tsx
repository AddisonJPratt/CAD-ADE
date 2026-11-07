import React, { Suspense, useEffect, useState, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas, useLoader, useThree } from '@react-three/fiber';
import { Bounds, OrbitControls, useProgress } from '@react-three/drei';
import { Vector3 } from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import './style.css';
import { Evidence, type EvidenceDesign } from './Evidence';
import { Catalogue } from './Catalogue';
import { PartsList } from './PartsList';

type SourceFile = { name: string; content: string };
type Gate = { name: string; status: string; detail: string };
type Details = { briefs: SourceFile[]; designs: SourceFile[]; report: null | { designs: { design: string; gates: Gate[] }[] } };
type Mode = "Make" | "Studio" | "Mission Control";
type Version = { id: string; number: number; message: string; timestamp: string; current: boolean; verdict: null | { pass: boolean; designs?: EvidenceDesign[] } };
async function json<T>(url: string): Promise<T> { const response = await fetch(url); const value = await response.json(); if (!response.ok) throw new Error(value.error || 'Engine request failed'); return value as T; }
function Model({ url }: { url: string }) { const geometry = useLoader(STLLoader, url); return <mesh geometry={geometry}><meshStandardMaterial color="#ccc8bf" roughness={0.56}/></mesh>; }
type CameraAction = { name: string; sequence: number };
function CameraView({ action }: { action: CameraAction }) {
  const { camera, invalidate, controls } = useThree();
  useEffect(() => {
    const orbit = controls as unknown as { target: Vector3; update: () => void } | null;
    if (!orbit) return;
    const target = orbit.target;
    const offset = camera.position.clone().sub(target);
    const positions: Record<string, [number, number, number]> = { Iso: [1,-1,1], Front: [0,-1,0], Top: [0,0,1], Side: [1,0,0] };
    const preset = positions[action.name];
    if (preset) {
      offset.set(...preset).normalize().multiplyScalar(offset.length());
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
  }, [action, camera, controls, invalidate]);
  return null;
}
class ModelError extends React.Component<{children: React.ReactNode}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  render() { return this.state.failed ? <div className="empty" role="alert">The model could not be loaded. Select another version and return to retry.</div> : this.props.children; }
}
function LoadingNotice() { const { active } = useProgress(); return active ? <div className="loading" role="status">Loading model…</div> : null; }
function App() {
  const [mode, setMode] = useState<Mode>('Studio'); const [details, setDetails] = useState<Details | null>(null); const [detailsError, setDetailsError] = useState('');
  const [folder, setFolder] = useState(''); const [project, setProject] = useState('');
  const [versions, setVersions] = useState<Version[]>([]); const [selected, setSelected] = useState<Version | null>(null); const selectionRef = useRef(''); selectionRef.current = `${project}:${selected?.id || ''}`;
  const [models, setModels] = useState<string[]>([]); const [modelVersion, setModelVersion] = useState(''); const [loading, setLoading] = useState(false); const [action, setAction] = useState<CameraAction>({name: 'Iso', sequence: 0}); const [error, setError] = useState('');
  async function open(e: React.FormEvent) { e.preventDefault(); setError(''); try { const result = await json<{versions: Version[]}>(`/api/projects/versions?project=${encodeURIComponent(folder)}`); setProject(folder); setVersions(result.versions); setSelected(result.versions.find(v => v.current) || result.versions[0] || null); } catch (err) { setError((err as Error).message); } }
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
  return <main><header><strong>Magic CAD</strong><nav aria-label="Workspace modes">{(['Make', 'Studio', 'Mission Control'] as Mode[]).map(name => <button type="button" key={name} aria-current={mode === name ? 'page' : undefined} onClick={() => setMode(name)}>{name}</button>)}</nav></header><section className="workspace" hidden={mode !== 'Studio'}><div className="stage">{shownModels.length ? <div className="canvas" aria-label="3D model" role="img"><ModelError key={selectionRef.current}><LoadingNotice/><Canvas camera={{position:[100,-140,110], up:[0,0,1], fov:35}}><ambientLight intensity={1.5}/><directionalLight position={[100,-80,160]} intensity={2}/><Suspense fallback={null}><Bounds fit clip observe margin={1.4}>{shownModels.map(path => <Model key={url(path)} url={url(path)}/>)}</Bounds></Suspense><CameraView action={action}/><OrbitControls makeDefault /></Canvas></ModelError></div> : <div className="empty" role="status">{selected ? loading ? 'Loading model…' : error ? 'The model could not be loaded.' : <span>No saved model is available for this version. {selected.verdict?.pass === false ? ' Models are exported after checks pass.' : <button type="button" onClick={rebuild}>Rebuild model</button>}</span> : 'Open a project to see your design.'}</div>}<div className="views" role="group" aria-label="Camera controls">{['Iso','Front','Top','Side'].map(name => <button key={name} type="button" disabled={!shownModels.length} onClick={() => setAction(previous => ({name, sequence: previous.sequence + 1}))}>{name}</button>)}<details className="camera-more"><summary>Move camera</summary><div className="camera-actions">{['Orbit left','Orbit right','Orbit up','Orbit down','Pan left','Pan right','Pan up','Pan down','Zoom in','Zoom out'].map(name => <button key={name} type="button" disabled={!shownModels.length} onClick={() => setAction(previous => ({name, sequence: previous.sequence + 1}))}>{name}</button>)}</div></details></div><p className="hint"><span className="desktop-hint">Drag to orbit · Right-drag to pan · Scroll to zoom</span><span className="touch-hint">Drag to orbit · Pinch to zoom</span></p></div><aside><form onSubmit={open}><label htmlFor="folder">Project folder</label><div className="open"><input id="folder" value={folder} onChange={e=>setFolder(e.target.value)} placeholder="/path/to/project" aria-describedby="folder-help" required/><button>Open project</button></div><small id="folder-help">Enter the full path to a Magic CAD project folder.</small></form>{error && <p role="alert" className="error">{error}</p>}{selected && <><div className="verdict"><h1>Version {selected.number}</h1><p className={selected.verdict?.pass === false ? 'error' : ''}><span aria-hidden="true" className={selected.verdict ? selected.verdict.pass ? 'mark pass' : 'mark fail' : 'mark pending'} />{selected.verdict ? selected.verdict.pass ? 'All checks passed' : 'Checks failed' : 'Checks not run'}</p><small>Harness checks only, not a design review or a print.</small>{selected.verdict && <Evidence designs={selected.verdict.designs || []}/>}</div><h2>Versions</h2><ol>{versions.map(v=><li key={v.id}><button aria-current={selected.id===v.id ? 'true' : undefined} onClick={()=>setSelected(v)}><span>Version {v.number}{v.current ? ' · Current' : ''}</span><small>{v.message}</small><time>{new Date(v.timestamp).toLocaleString()}</time></button></li>)}</ol></>}</aside></section>{mode !== 'Studio' && <section className={mode === 'Mission Control' ? 'expert' : 'make-mode'}><h1>{mode}</h1>{!selected ? <p>Open a project in Studio to get started.</p> : <><p className="version-context">{project} · Version {selected.number}</p>{mode === 'Make' ? <p>Make is not available yet. Return to Studio to inspect your project and its versions.</p> : <>{detailsError && <p role="alert">Could not load this version: {detailsError}</p>}{!details && !detailsError && <p role="status">Loading version details…</p>}{details && <><section><h2>Brief card</h2>{details.briefs.length ? details.briefs.map(file => <div key={file.name}><h3>{file.name}</h3><pre>{file.content}</pre></div>) : <p>No brief card was saved with this version.</p>}</section><section><h2>Gate report</h2>{details.report ? details.report.designs.map(design => <div key={design.design}><h3>{design.design}</h3><ul className="gate-list">{design.gates.map(gate => <li key={gate.name}><strong>{gate.name}</strong><span><i aria-hidden="true" className={`mark ${gate.status === 'PASS' ? 'pass' : gate.status === 'FAIL' || gate.status === 'ERROR' ? 'fail' : 'pending'}`} />{gate.status}</span><p>{gate.detail}</p></li>)}</ul><details><summary>Full report</summary><pre>{JSON.stringify(details.report, null, 2)}</pre></details></div>) : <p>No gate report is saved for this version.</p>}</section><section><h2>Design code</h2>{details.designs.map(file => <div key={file.name}><h3>{file.name.split('/').pop()}</h3><pre><code>{file.content}</code></pre></div>)}</section></>}<PartsList project={project}/><Catalogue project={project}/></>}</>}</section>}</main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
