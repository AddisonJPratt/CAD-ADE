// Find or start a project without typing a path (#66). A browser cannot read a real
// folder path from the native picker, so the engine lists folders and projects.
import React, { useEffect, useRef, useState } from 'react';
import { Icon } from './icons';

type Project = { name: string; path: string; in_home: boolean; opened: string | null; modified: string };
type Starter = { id: string; label: string; summary: string };
type Listing = { path: string; parent: string | null; project: boolean; entries: { name: string; path: string; project: boolean }[] };
type View = 'list' | 'new' | 'browse';

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `The engine did not answer (${r.status})`); return body;
}

function ago(iso: string) {
  const s = (Date.now() - Date.parse(iso)) / 1000;
  if (s < 60) return 'just now';
  const [n, unit] = s < 3600 ? [s / 60, 'minute'] : s < 86400 ? [s / 3600, 'hour'] : s < 86400 * 30 ? [s / 86400, 'day'] : [0, ''];
  if (!unit) return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  const k = Math.floor(n); return `${k} ${unit}${k === 1 ? '' : 's'} ago`;
}

const dirname = (path: string) => path.slice(0, Math.max(0, path.lastIndexOf('/'))) || '/';

// children: the typed-path fallback, shown with the list and browse views but not while naming a new project.
export function ProjectPicker({ onOpen, busy, children }: { onOpen: (path: string) => void; busy: boolean; children?: React.ReactNode }) {
  const [view, setView] = useState<View>('list');
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [home, setHome] = useState(''); const [userHome, setUserHome] = useState('');
  const [starters, setStarters] = useState<Starter[]>([]);
  const [name, setName] = useState(''); const [starter, setStarter] = useState('');
  const [nameError, setNameError] = useState('');
  const [creating, setCreating] = useState(false);
  const [listing, setListing] = useState<Listing | null>(null);
  const [reading, setReading] = useState(false); const request = useRef(0); // only the newest listing may land
  const [engineDown, setEngineDown] = useState(false);
  const [error, setError] = useState('');
  const nameRef = useRef<HTMLInputElement>(null);
  const tilde = (p: string) => userHome && p.startsWith(userHome) ? '~' + p.slice(userHome.length) : p;

  useEffect(() => {
    get<{ home: string; user_home: string; projects: Project[] }>('/api/workspace/projects')
      .then(r => { setProjects(r.projects); setHome(r.home); setUserHome(r.user_home); })
      .catch(() => { setProjects([]); setEngineDown(true); });
  }, []);

  function show(next: View) {
    setError(''); setView(next);
    if (next === 'new') {
      if (!starters.length) get<{ starters: Starter[] }>('/api/workspace/starters').then(r => { setStarters(r.starters); setStarter(current => r.starters.some(s => s.id === current) ? current : r.starters[0]?.id || ''); }).catch(e => setError(e.message));
      setTimeout(() => nameRef.current?.focus());
    }
    if (next === 'browse' && !listing) browse('');
  }

  async function browse(path: string) {
    const ticket = ++request.current;
    setError(''); setReading(true);
    try {
      const result = await get<Listing>('/api/workspace/browse' + (path ? `?path=${encodeURIComponent(path)}` : ''));
      if (ticket === request.current) setListing(result);
    } catch (e) { if (ticket === request.current) setError((e as Error).message); }
    finally { if (ticket === request.current) setReading(false); }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault(); if (creating) return;
    if (!name.trim()) { setNameError('Give the project a name.'); nameRef.current?.focus(); return; }
    setCreating(true); setError(''); setNameError('');
    try {
      const r = await fetch('/api/workspace/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name.trim(), starter }) });
      const body = await r.json(); if (!r.ok) throw new Error(body.error || r.statusText);
      onOpen(body.project);
    } catch (err) {
      // A refused name belongs beside the field; anything else is an engine error.
      const message = (err as Error).message;
      if (/name|already exists/i.test(message)) { setNameError(message); nameRef.current?.focus(); } else setError(message);
    } finally { setCreating(false); }
  }

  const row = (p: Project) => <button type="button" className="picker-row" disabled={busy} onClick={() => onOpen(p.path)} title={p.path}>
    <Icon name="cube" /><span className="picker-name">{p.name}</span>
    <span className="picker-meta">{!p.in_home && <><span className="path">{tilde(dirname(p.path))}</span> · </>}{ago(p.opened && p.opened > p.modified ? p.opened : p.modified)}</span>
  </button>;

  return <div className="picker">
    <div className="picker-tabs" role="group" aria-label="Find a project">
      {(['list', 'new', 'browse'] as View[]).map(v => <button key={v} type="button" aria-pressed={view === v} className="picker-tab" onClick={() => show(v)}>
        {v === 'list' ? 'Your projects' : v === 'new' ? 'New project' : 'Browse'}</button>)}
    </div>

    {view === 'list' && <section aria-label="Your projects">
      {projects === null ? <p className="picker-note" role="status">Looking for projects…</p>
        : engineDown ? <p role="alert" className="error">The local engine is not answering, so your projects cannot be listed. Start it and reload this page.</p>
        : projects.length ? <ul className="picker-list">{projects.map(p => <li key={p.path}>{row(p)}</li>)}</ul>
        : <div className="picker-empty"><p>No projects yet. Start one from a design, or browse to a project folder you already have.</p>
          <button type="button" className="primary-button" onClick={() => show('new')}>New project</button></div>}
      {home && <p className="picker-note">New projects are saved in <span className="path">{tilde(home)}</span></p>}
    </section>}

    {view === 'new' && <form className="picker-new" onSubmit={create} noValidate aria-label="New project">
      <label htmlFor="new-name">Name</label>
      <input id="new-name" ref={nameRef} value={name} onChange={e => { setName(e.target.value); setNameError(''); }} placeholder="Shelf bracket" autoComplete="off" maxLength={80} aria-invalid={nameError ? true : undefined} aria-describedby={nameError ? 'new-name-hint' : undefined} />
      {nameError && <p id="new-name-hint" className="field-hint">{nameError}</p>}
      <fieldset><legend>Start from</legend>
        <div className="starter-list">{starters.map(s => <label key={s.id} className="starter">
          <input type="radio" name="starter" value={s.id} checked={starter === s.id} onChange={() => setStarter(s.id)} aria-label={s.label} aria-describedby={s.summary ? `starter-${s.id}` : undefined} />
          <span><b>{s.label}</b>{s.summary && <small id={`starter-${s.id}`}>{s.summary}</small>}</span></label>)}</div>
      </fieldset>
      <div className="picker-actions"><button className="primary-button" disabled={creating || busy}>{creating ? 'Creating…' : 'Create project'}</button>
        {home && <span className="picker-note">in <span className="path">{tilde(home)}</span></span>}</div>
    </form>}

    {view === 'browse' && <section aria-label="Browse folders" className="picker-browse">
      {listing && <>
        <div className="crumb"><button type="button" className="quiet-button" disabled={!listing.parent} onClick={() => listing.parent && browse(listing.parent)} aria-label="Up one folder"><span className="up-arrow"><Icon name="arrow" /></span></button>
          <span className="path" title={listing.path}>{tilde(listing.path)}</span>
          {home && listing.path !== home && <button type="button" className="quiet-button crumb-home" onClick={() => browse(home)}>Projects home</button>}</div>
        {listing.project && <button type="button" className="primary-button" onClick={() => onOpen(listing.path)} disabled={busy}>Open this project</button>}
        {listing.entries.length ? <ul className="picker-list">{listing.entries.map(e => <li key={e.path}>
          <button type="button" className={`picker-row ${e.project ? 'is-project' : ''}`} disabled={busy || reading}
            onClick={() => e.project ? onOpen(e.path) : browse(e.path)}>
            <Icon name={e.project ? 'cube' : 'folder'} /><span className="picker-name">{e.name}</span>
            {e.project && <span className="picker-meta">Open</span>}
          </button></li>)}</ul>
          : <p className="picker-note">No folders here.</p>}
      </>}
      {reading && !error && <p className="picker-note" role="status">Reading folders…</p>}
    </section>}

    {error && <p role="alert" className="error">{error}</p>}
    {view !== 'new' && children}
  </div>;
}
