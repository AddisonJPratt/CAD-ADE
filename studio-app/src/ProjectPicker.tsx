// Find or start a project without typing a path (#66). A browser cannot read a real
// folder path from the native picker, so the engine lists folders and projects.
import React, { useEffect, useRef, useState } from 'react';
import { Icon } from './icons';

type Project = { name: string; path: string; in_home: boolean; opened: string | null; modified: string };
type Starter = { id: string; label: string; summary: string };
type Listing = { path: string; parent: string | null; project: boolean; entries: { name: string; path: string; project: boolean }[] };
type View = 'list' | 'new' | 'browse';

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url); const body = await r.json();
  if (!r.ok) throw new Error(body.error || r.statusText); return body;
}

function ago(iso: string) {
  const s = (Date.now() - Date.parse(iso)) / 1000;
  if (s < 60) return 'just now';
  const [n, unit] = s < 3600 ? [s / 60, 'minute'] : s < 86400 ? [s / 3600, 'hour'] : s < 86400 * 30 ? [s / 86400, 'day'] : [0, ''];
  if (!unit) return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  const k = Math.floor(n); return `${k} ${unit}${k === 1 ? '' : 's'} ago`;
}

export function ProjectPicker({ onOpen, busy }: { onOpen: (path: string) => void; busy: boolean }) {
  const [view, setView] = useState<View>('list');
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [home, setHome] = useState(''); const [userHome, setUserHome] = useState('');
  const [starters, setStarters] = useState<Starter[]>([]);
  const [name, setName] = useState(''); const [starter, setStarter] = useState('wall_bracket');
  const [creating, setCreating] = useState(false);
  const [listing, setListing] = useState<Listing | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [finder, setFinder] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);
  const tilde = (p: string) => userHome && p.startsWith(userHome) ? '~' + p.slice(userHome.length) : p;

  useEffect(() => {
    get<{ home: string; user_home: string; projects: Project[] }>('/api/workspace/projects')
      .then(r => { setProjects(r.projects); setHome(r.home); setUserHome(r.user_home); })
      .catch(() => setProjects([]));
  }, []);

  async function chooseInFinder() {
    if (finder) return;
    setFinder(true); setError(''); setNotice('');
    try {
      const r = await fetch('/api/workspace/choose-folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const body = await r.json();
      if (!r.ok) { setView('browse'); await browse(''); setNotice(body.error || 'Finder is not available here. Browse instead.'); return; }
      if (!body.path) return;  // cancelled in Finder
      if (body.project) { onOpen(body.path); return; }
      setView('browse'); await browse(body.path);
      setNotice('That folder is not a project. Open a project inside it, or start a new project.');
    } catch (e) { setError((e as Error).message); } finally { setFinder(false); }
  }

  const starterList = useRef<HTMLDivElement>(null);
  useEffect(() => {  // keep the chosen starter visible when the list first appears
    if (view === 'new') starterList.current?.querySelector('input:checked')?.closest('label')?.scrollIntoView({ block: 'nearest' });
  }, [view, starters]);

  function show(next: View) {
    setError(''); setNotice(''); setView(next);
    if (next === 'new') {
      if (!starters.length) get<{ starters: Starter[] }>('/api/workspace/starters').then(r => setStarters(r.starters)).catch(e => setError(e.message));
      setTimeout(() => nameRef.current?.focus());
    }
    if (next === 'browse' && !listing) browse('');
  }

  async function browse(path: string) {
    setError('');
    try { setListing(await get<Listing>('/api/workspace/browse' + (path ? `?path=${encodeURIComponent(path)}` : ''))); }
    catch (e) { setError((e as Error).message); }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault(); if (creating) return;
    if (!name.trim()) { setError('Give the project a name.'); nameRef.current?.focus(); return; }
    setCreating(true); setError('');
    try {
      const r = await fetch('/api/workspace/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name.trim(), starter }) });
      const body = await r.json(); if (!r.ok) throw new Error(body.error || r.statusText);
      onOpen(body.project);
    } catch (err) { setError((err as Error).message); } finally { setCreating(false); }
  }

  return <div className="picker">
    <button type="button" className="finder-button" onClick={chooseInFinder} disabled={finder || busy}>
      <Icon name="folder" /><span>{finder ? 'Waiting for Finder…' : 'Choose a folder in Finder…'}</span>
    </button>
    <div className="picker-tabs" role="group" aria-label="Find a project">
      {(['list', 'new', 'browse'] as View[]).map(v => <button key={v} type="button" aria-pressed={view === v} className="picker-tab" onClick={() => show(v)}>
        {v === 'list' ? 'Your projects' : v === 'new' ? 'New project' : 'Browse here'}</button>)}
    </div>

    {view === 'list' && <section aria-label="Your projects">
      {projects === null ? <p className="picker-note" role="status">Looking for projects…</p>
        : projects.length ? <ul className="picker-list">{projects.map(p => <li key={p.path}>
          <button type="button" className="picker-row" disabled={busy} onClick={() => onOpen(p.path)} title={p.path}>
            <Icon name="cube" /><span className="picker-name">{p.name}</span>
            <span className="picker-meta">{p.in_home ? '' : tilde(p.path.slice(0, p.path.length - p.name.length - 1)) + ' · '}{ago(p.opened && p.opened > p.modified ? p.opened : p.modified)}</span>
          </button></li>)}</ul>
        : <div className="picker-empty"><p>No projects yet. Start one from a design, or browse to a project folder you already have.</p>
          <button type="button" className="primary-button" onClick={() => show('new')}>New project</button></div>}
      {home && <p className="picker-note">New projects are saved in <span className="path">{tilde(home)}</span></p>}
    </section>}

    {view === 'new' && <form className="picker-new" onSubmit={create} noValidate aria-label="New project">
      <label htmlFor="new-name">Name</label>
      <input id="new-name" ref={nameRef} value={name} onChange={e => { setName(e.target.value); setError(''); }} placeholder="Shelf bracket" autoComplete="off" maxLength={80} />
      <fieldset><legend>Start from</legend>
        <div className="starter-list" ref={starterList}>{starters.map(s => <label key={s.id} className="starter">
          <input type="radio" name="starter" value={s.id} checked={starter === s.id} onChange={() => setStarter(s.id)} />
          <span><b>{s.label}</b>{s.summary && <small>{s.summary}</small>}</span></label>)}</div>
      </fieldset>
      <div className="picker-actions"><button className="primary-button" disabled={creating || busy}>{creating ? 'Creating…' : 'Create project'}</button>
        {home && <span className="picker-note">in <span className="path">{tilde(home)}</span></span>}</div>
    </form>}

    {view === 'browse' && <section aria-label="Browse folders" className="picker-browse">
      {listing && <>
        <div className="crumb"><button type="button" className="quiet-button" disabled={!listing.parent} onClick={() => listing.parent && browse(listing.parent)} aria-label="Up one folder"><span className="up-arrow"><Icon name="arrow" /></span></button>
          <span className="path" title={listing.path}>{tilde(listing.path)}</span></div>
        {listing.project && <button type="button" className="primary-button" onClick={() => onOpen(listing.path)} disabled={busy}>Open this project</button>}
        {listing.entries.length ? <ul className="picker-list">{listing.entries.map(e => <li key={e.path}>
          <button type="button" className={`picker-row ${e.project ? 'is-project' : ''}`} disabled={busy && e.project}
            onClick={() => e.project ? onOpen(e.path) : browse(e.path)}>
            <Icon name={e.project ? 'cube' : 'folder'} /><span className="picker-name">{e.name}</span>
            {e.project && <span className="picker-meta">Open</span>}
          </button></li>)}</ul>
          : <p className="picker-note">No folders here.</p>}
      </>}
      {!listing && !error && <p className="picker-note" role="status">Reading folders…</p>}
    </section>}

    {notice && <p role="status" className="picker-notice">{notice}</p>}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}
