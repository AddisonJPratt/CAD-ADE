// Adapted from Watermelon UI Command Search (MIT). Source and license: NOTICE.md.
// Native dialog and Studio actions replace demo content and animation dependencies.
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Icon, type IconName } from '../icons';

export type StudioCommand = {id:string; title:string; section:string; icon:IconName; description?:string; disabled?:boolean; action:()=>void};

export function CommandSearch({items}:{items:StudioCommand[]}) {
  const [open,setOpen] = useState(false);
  const [query,setQuery] = useState('');
  const [activeIndex,setActiveIndex] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const id = useId();
  const shortcut = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘ K' : 'Ctrl K';
  const filtered = useMemo(() => items.filter(item => `${item.title} ${item.section} ${item.description || ''}`.toLowerCase().includes(query.trim().toLowerCase())), [items,query]);
  const groups = [...new Set(filtered.map(item => item.section))];
  function show() { setQuery(''); setActiveIndex(0); setOpen(true); }
  function run(item:StudioCommand) { if (item.disabled) return; setOpen(false); requestAnimationFrame(item.action); }
  useEffect(() => {
    if (open) { if (!dialog.current?.open) dialog.current?.showModal(); input.current?.focus(); }
    else if (dialog.current?.open) dialog.current.close();
  }, [open]);
  useEffect(() => {
    const handle = (event:KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k' && !event.repeat && !event.isComposing) {
        event.preventDefault();
        if (open) setOpen(false); else show();
      }
    };
    window.addEventListener('keydown',handle);
    return () => window.removeEventListener('keydown',handle);
  },[open]);
  useEffect(() => { document.getElementById(`${id}-option-${activeIndex}`)?.scrollIntoView({block:'nearest'}); },[activeIndex,id]);
  return <><button type="button" className="command-trigger" aria-label="Open command menu" aria-haspopup="dialog" onClick={show}><Icon name="search"/><span>Commands</span><kbd>{shortcut}</kbd></button>
    <dialog ref={dialog} className="studio-command" aria-labelledby={`${id}-title`} onClose={() => setOpen(false)} onClick={event => {if (event.target === event.currentTarget) setOpen(false);}}>
      <div className="command-heading"><Icon name="search"/><h2 id={`${id}-title`}>Studio commands</h2><button type="button" aria-label="Close commands" onClick={() => setOpen(false)}><Icon name="close"/></button></div>
      <input ref={input} type="search" role="combobox" aria-label="Search commands" aria-expanded={open} aria-controls={`${id}-results`} aria-activedescendant={filtered[activeIndex] ? `${id}-option-${activeIndex}` : undefined} autoComplete="off" placeholder="Find a tool, view or panel…" value={query} onChange={event => {setQuery(event.target.value);setActiveIndex(0);}} onKeyDown={event => {
        if (event.key === 'Escape') { event.preventDefault(); setOpen(false); }
        else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          if (!filtered.length) return;
          const direction = event.key === 'ArrowDown' ? 1 : -1;
          for (let step=1;step<=filtered.length;step++) { const next = (activeIndex + direction*step + filtered.length) % filtered.length; if (!filtered[next].disabled) {setActiveIndex(next);break;} }
        } else if (event.key === 'Enter') { event.preventDefault(); if (filtered[activeIndex]) run(filtered[activeIndex]); }
      }}/>
      <div className="command-results" id={`${id}-results`} role="listbox" aria-label="Available commands">
        {!filtered.length ? <p className="command-empty">No matching commands</p> : groups.map(group => <div role="group" aria-label={group} key={group}><div className="command-section">{group}</div>{filtered.filter(item => item.section === group).map(item => { const index = filtered.indexOf(item); return <button type="button" role="option" id={`${id}-option-${index}`} key={item.id} tabIndex={-1} disabled={item.disabled} aria-selected={index === activeIndex && !item.disabled} onPointerEnter={() => setActiveIndex(index)} onClick={() => run(item)}><Icon name={item.icon}/><span><strong>{item.title}</strong>{item.description && <small>{item.description}</small>}</span><Icon name="arrow"/></button>; })}</div>)}
      </div>
      <div className="command-footer"><span>Arrow keys to navigate</span><span>Enter to run</span><kbd>Esc to close</kbd></div>
    </dialog></>;
}
