import React, { Suspense, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas, useLoader } from '@react-three/fiber';
import { Bounds, OrbitControls } from '@react-three/drei';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import './style.css';

type Version = { id: string; number: number; message: string; timestamp: string; current: boolean; verdict: null | { pass: boolean } };
async function json<T>(url: string): Promise<T> { const response = await fetch(url); const value = await response.json(); if (!response.ok) throw new Error(value.error || 'Engine request failed'); return value as T; }
function Model({ url }: { url: string }) { const geometry = useLoader(STLLoader, url); return <mesh geometry={geometry}><meshStandardMaterial color="#ccc8bf" roughness={0.56}/></mesh>; }
function App() {
  const [folder, setFolder] = useState(''); const [project, setProject] = useState('');
  const [versions, setVersions] = useState<Version[]>([]); const [selected, setSelected] = useState<Version | null>(null);
  const [models, setModels] = useState<string[]>([]); const [error, setError] = useState('');
  async function open(e: React.FormEvent) { e.preventDefault(); setError(''); try { const result = await json<{versions: Version[]}>(`/api/projects/versions?project=${encodeURIComponent(folder)}`); setProject(folder); setVersions(result.versions); setSelected(result.versions.find(v => v.current) || result.versions[0] || null); } catch (err) { setError((err as Error).message); } }
  useEffect(() => { if (!selected || !project) return; let active = true; setModels([]); const query = new URLSearchParams({project, version:selected.id}); json<{models:string[]}>(`/api/projects/version-artifacts?${query}`).then(data => { if (active) setModels(data.models); }).catch(err => { if (active) setError(err.message); }); return () => { active = false; }; }, [project, selected]);
  const url = (path: string) => `/api/projects/version-artifacts?${new URLSearchParams({project, version:selected!.id, path})}`;
  return <main><header><strong>Magic CAD</strong><span>Studio</span></header><section className="workspace"><div className="stage">{models.length ? <div className="canvas" aria-label="3D model" role="img"><Canvas camera={{position:[100,-140,110], up:[0,0,1], fov:35}}><ambientLight intensity={1.5}/><directionalLight position={[100,-80,160]} intensity={2}/><Suspense fallback={null}><Bounds fit clip observe margin={1.4}>{models.map(path => <Model key={url(path)} url={url(path)}/>)}</Bounds></Suspense><OrbitControls makeDefault /></Canvas></div> : <div className="empty">{selected ? 'No model is available for this version.' : 'Open a project to see your design.'}</div>}<p className="hint">Drag to orbit · Right-drag to pan · Scroll to zoom</p></div><aside><form onSubmit={open}><label htmlFor="folder">Project folder</label><div className="open"><input id="folder" value={folder} onChange={e=>setFolder(e.target.value)} placeholder="/path/to/project" required/><button>Open project</button></div></form>{error && <p role="alert" className="error">{error}</p>}{selected && <><div className="verdict"><h1>Version {selected.number}</h1><p className={selected.verdict?.pass === false ? 'error' : ''}>{selected.verdict ? selected.verdict.pass ? 'All checks passed' : 'Checks failed' : 'Checks not run'}</p><small>Harness checks only, not a design review or a print.</small></div><h2>Versions</h2><ol>{versions.map(v=><li key={v.id}><button aria-current={selected.id===v.id ? 'true' : undefined} onClick={()=>setSelected(v)}><span>Version {v.number}{v.current ? ' · Current' : ''}</span><small>{v.message}</small><time>{new Date(v.timestamp).toLocaleString()}</time></button></li>)}</ol></>}</aside></section></main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
