// The assembly tree docked on the viewport: every instance, its display controls and the
// exploded-view slider. A treegrid, so each row can hold its own buttons and still be a tree.
import { useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react';
import { Icon } from '../icons';
import { JointList } from './joints';
import type { AssemblyManifest } from './manifest';
import { assemblyRows, displayOf, type AssemblyViewState, type ViewAction } from './view';

export function AssemblyPanel({ manifest, view, dispatch, startOpen = true, onShowChecks }: { manifest: AssemblyManifest; view: AssemblyViewState; dispatch: (action: ViewAction) => void; startOpen?: boolean; onShowChecks: () => void }) {
  const rows = useMemo(() => assemblyRows(manifest), [manifest]);
  const [open, setOpen] = useState(startOpen);
  const [focused, setFocused] = useState(rows[0]?.id ?? '');
  const names = useRef<Record<string, HTMLButtonElement | null>>({});
  // A part picked in the viewport becomes the row the keyboard continues from, and comes into view.
  useEffect(() => { if (view.selected) { setFocused(view.selected); names.current[view.selected]?.scrollIntoView({ block: 'nearest' }); } }, [view.selected]);
  const counts = useMemo(() => rows.reduce<Record<string, number>>((c, r) => ({ ...c, [r.kind]: (c[r.kind] || 0) + 1 }), {}), [rows]);
  const summary = [counts.printed && `${counts.printed} printed`, counts.hardware && `${counts.hardware} hardware`, counts.component && `${counts.component} purchased`].filter(Boolean).join(' · ');
  const isolatedName = rows.find(r => r.id === view.isolated)?.name;
  const changed = view.hidden.length > 0 || view.ghosted.length > 0 || view.isolated !== null;
  const explode = Math.round(view.explode * 100);
  function move(e: KeyboardEvent, id: string) {
    const at = rows.findIndex(r => r.id === id);
    if (e.key === 'ArrowRight' && e.currentTarget === names.current[id]) { e.preventDefault(); (e.currentTarget.closest('[role=row]')?.querySelector('.assembly-actions button') as HTMLElement | null)?.focus(); return; }
    const to = e.key === 'ArrowDown' ? at + 1 : e.key === 'ArrowUp' ? at - 1 : e.key === 'Home' ? 0 : e.key === 'End' ? rows.length - 1 : -1;
    if (to < 0 || to >= rows.length || to === at && e.key !== 'Home' && e.key !== 'End') return;
    e.preventDefault(); setFocused(rows[to].id); names.current[rows[to].id]?.focus();
  }
  const clear = (e: KeyboardEvent) => { if (e.key === 'Escape' && view.selected) { e.stopPropagation(); dispatch({ type: 'select', id: null }); } };
  return <section className={`assembly-panel${open ? '' : ' collapsed'}`} aria-labelledby="assembly-heading">
    <div className="assembly-heading">
      <h2 id="assembly-heading">Assembly</h2>
      <span className="assembly-count">{summary}</span>
      <button type="button" className="assembly-collapse" aria-expanded={open} aria-controls="assembly-body" aria-label={open ? 'Collapse assembly list' : 'Expand assembly list'} onClick={() => setOpen(v => !v)}><Icon name={open ? 'minus' : 'chevron'}/></button>
    </div>
    <div id="assembly-body" hidden={!open}>
      {!manifest.pass && <p className="assembly-warning" role="note">The assembly check failed, so these positions may be wrong. <button type="button" onClick={onShowChecks}>Open Checks</button></p>}
      {isolatedName && <p className="assembly-isolated" role="status">Showing only {isolatedName} <button type="button" onClick={() => dispatch({ type: 'toggleIsolate', id: view.isolated! })}>Show the rest</button></p>}
      <div role="treegrid" aria-label="Assembly" className="assembly-tree" aria-multiselectable="false" onKeyDown={clear}>
        {rows.map(row => {
          const display = displayOf(view, row.id);
          const hidden = view.hidden.includes(row.id), ghosted = view.ghosted.includes(row.id), isolated = view.isolated === row.id;
          const selected = view.selected === row.id;
          const actionTab = focused === row.id ? 0 : -1;
          const outside = isolatedName !== undefined && !isolated; // hidden by isolation: its own choices wait until isolation ends
          const why = outside ? `Hidden while ${isolatedName} is isolated` : undefined;
          return <div key={row.id} role="row" aria-level={row.depth + 1} aria-selected={selected}
            className={`assembly-row${selected ? ' selected' : ''}${display === 'hidden' ? ' is-hidden' : ''}${display === 'ghost' ? ' is-ghost' : ''}`}
            style={{ '--depth': row.depth } as CSSProperties}>
            <span role="gridcell" className="assembly-name-cell">
              <button type="button" ref={el => { names.current[row.id] = el; }} className="assembly-name" aria-current={selected || undefined} tabIndex={focused === row.id ? 0 : -1}
                onFocus={() => setFocused(row.id)} onKeyDown={e => move(e, row.id)}
                onClick={() => dispatch({ type: 'select', id: row.id })}>
                <span className="assembly-label">{row.name}</span>
                <small>{row.kindLabel}</small>
              </button>
            </span>
            <span role="gridcell" className="assembly-actions" onKeyDown={e => {
              const buttons = [...e.currentTarget.querySelectorAll('button')]; const at = buttons.indexOf(e.target as HTMLButtonElement);
              if (e.key === 'ArrowRight' && at < buttons.length - 1) { e.preventDefault(); buttons[at + 1].focus(); }
              if (e.key === 'ArrowLeft') { e.preventDefault(); (at > 0 ? buttons[at - 1] : names.current[row.id])?.focus(); }
            }}>
              <button type="button" tabIndex={actionTab} className="assembly-eye" disabled={outside} aria-label={`Hide ${row.name}`} aria-pressed={hidden} title={why ?? (hidden ? 'Hidden. Click to show' : 'Hide')} onClick={() => dispatch({ type: 'toggleHidden', id: row.id })}><Icon name={hidden ? 'eyeOff' : 'eye'}/></button>
              <button type="button" tabIndex={actionTab} disabled={outside} aria-label={`Ghost ${row.name}`} aria-pressed={ghosted} title={why ?? (ghosted ? 'See-through. Click to make solid' : 'Make see-through')} onClick={() => dispatch({ type: 'toggleGhost', id: row.id })}><Icon name="ghost"/></button>
              <button type="button" tabIndex={actionTab} aria-label={`Isolate ${row.name}`} aria-pressed={isolated} title={isolated ? 'Showing only this. Click to show the rest' : 'Show only this'} onClick={() => dispatch({ type: 'toggleIsolate', id: row.id })}><Icon name="isolate"/></button>
            </span>
          </div>;
        })}
      </div>
      <div className="assembly-explode">
        <label htmlFor="assembly-explode">Explode</label>
        <input id="assembly-explode" type="range" min={0} max={100} step={1} value={explode} aria-valuetext={`${explode}%`}
          onChange={e => dispatch({ type: 'explode', amount: Number(e.target.value) / 100 })}/>
        <output htmlFor="assembly-explode">{explode}%</output>
      </div>
      <JointList manifest={manifest}/>
      <div className="assembly-foot">
        <p>Parts move along their joints. Not a collision check.</p>
        <button type="button" className="quiet-button" disabled={!changed} onClick={() => dispatch({ type: 'showAll' })}>Show all</button>
      </div>
    </div>
  </section>;
}
