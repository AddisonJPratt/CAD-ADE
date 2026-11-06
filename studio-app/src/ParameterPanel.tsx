import { useEffect, useState } from 'react';
import { Icon } from './icons';

type Parameter = {name:string; value:number; min:number; max:number; unit:string|null; intent:string; integer:boolean};
type Props = {project:string; design:string; version:string; current:boolean; busy:boolean; onPropose:(name:string,value:number)=>Promise<void>};

export function ParameterPanel({project, design, version, current, busy, onPropose}: Props) {
  const [parameters, setParameters] = useState<Parameter[]>([]);
  const [drafts, setDrafts] = useState<Record<string,string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!current || !design) return;
    let active = true;
    setLoading(true); setError(''); setParameters([]);
    const query = new URLSearchParams({project, design});
    fetch(`/api/projects/parameters?${query}`).then(async response => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Parameters could not be loaded');
      if (!active) return;
      setParameters(result.parameters);
      setDrafts(Object.fromEntries(result.parameters.map((p:Parameter) => [p.name, String(p.value)])));
    }).catch(err => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [project, design, version, current, retry]);

  return <section className="parameter-panel" aria-label="Design parameters">
    <div className="parameter-heading"><Icon name="parameters"/><h2>Parameters</h2><span>Review before applying</span></div>
    {!current ? <p>Select the current version to edit its parameters.</p> : loading ? <p role="status">Loading parameters…</p> : error ? <div role="alert"><p>{error}</p><button type="button" onClick={() => setRetry(n => n+1)}>Retry parameters</button></div> : !parameters.length ? <p>This design has no exposed parameters.</p> : parameters.map(parameter => {
      const value = drafts[parameter.name] ?? '';
      const changed = value !== '' && Number(value) !== parameter.value;
      const id = `parameter-${parameter.name}`;
      return <form key={parameter.name} onSubmit={event => { event.preventDefault(); if (!busy && changed) void onPropose(parameter.name, Number(value)); }}>
        <div className="parameter-label"><label htmlFor={id}>{parameter.name}</label></div>
        {parameter.intent && <p className="parameter-intent">{parameter.intent}</p>}
        <div className="parameter-control"><input id={id} type="number" required min={parameter.min} max={parameter.max} step={parameter.integer ? 1 : 'any'} value={value} disabled={busy} aria-describedby={`${id}-range`} onChange={event => setDrafts(previous => ({...previous, [parameter.name]: event.target.value}))}/>{parameter.unit && <span className="parameter-unit" aria-hidden="true">{parameter.unit}</span>}<button type="submit" aria-label={`Review ${parameter.name}`} title="Preview this edit" disabled={busy || !changed}><Icon name="arrow"/></button></div>
        <small id={`${id}-range`}>{parameter.min} to {parameter.max}{parameter.unit ? ` ${parameter.unit}` : ' / unit not declared'}{parameter.integer ? ' / whole numbers' : ''}</small>
      </form>;
    })}
  </section>;
}
