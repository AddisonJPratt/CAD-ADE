import { useEffect, useRef, useState } from 'react';
import { Icon } from './icons';

type Parameter = {name:string; value:number; min:number; max:number; unit:string|null; intent:string; integer:boolean};
type Props = {project:string; design:string; version:string; current:boolean; busy:boolean; onPropose:(name:string,value:number)=>Promise<void>};

/** Why a draft cannot be proposed, or '' when it can. The engine re-checks every bound. */
function draftProblem(parameter: Parameter, draft: string) {
  const unit = parameter.unit ? ` ${parameter.unit}` : '';
  const value = Number(draft);
  if (draft.trim() === '' || !Number.isFinite(value) || value < parameter.min || value > parameter.max)
    return `Enter a value from ${parameter.min} to ${parameter.max}${unit}.`;
  if (parameter.integer && !Number.isInteger(value)) return `Enter a whole number from ${parameter.min} to ${parameter.max}${unit}.`;
  return '';
}

/** Arrow-key step: whole numbers for counts, else the finest precision the design itself declares. */
function stepOf(parameter: Parameter) {
  if (parameter.integer) return 1;
  const places = Math.max(...[parameter.value, parameter.min, parameter.max].map(n => (String(n).split('.')[1] ?? '').length));
  return 10 ** -places;
}

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
  // A proposal that ends without a new version (rejected or failed) leaves the saved values in force.
  const wasBusy = useRef(busy);
  useEffect(() => {
    if (wasBusy.current && !busy) setDrafts(Object.fromEntries(parameters.map(p => [p.name, String(p.value)])));
    wasBusy.current = busy;
  }, [busy, parameters]);

  return <section className="parameter-panel" aria-label="Design parameters">
    <div className="parameter-heading"><Icon name="parameters"/><h2>Parameters</h2><span>Review before applying</span></div>
    {!current ? <p>Select the current version to edit its parameters.</p> : loading ? <p role="status">Loading parameters…</p> : error ? <div role="alert"><p>{error}</p><button type="button" onClick={() => setRetry(n => n+1)}>Retry parameters</button></div> : !parameters.length ? <p>This design has no exposed parameters.</p> : parameters.map(parameter => {
      const value = drafts[parameter.name] ?? '';
      const problem = draftProblem(parameter, value);
      // An empty field is mid-edit: it cannot be submitted, but it is not yet an error.
      const shownProblem = value.trim() === '' ? '' : problem;
      const changed = !problem && Number(value) !== parameter.value;
      const dirty = value !== String(parameter.value);
      const id = `parameter-${parameter.name}`;
      const describedBy = [parameter.intent && `${id}-intent`, `${id}-range`, shownProblem && `${id}-problem`].filter(Boolean).join(' ');
      return <form key={parameter.name} noValidate data-dirty={dirty || undefined} onSubmit={event => { event.preventDefault(); if (!busy && changed) void onPropose(parameter.name, Number(value)); }}>
        <div className="parameter-label"><label htmlFor={id}>{parameter.name}</label></div>
        {parameter.intent && <p className="parameter-intent" id={`${id}-intent`}>{parameter.intent}</p>}
        <div className="parameter-control"><input id={id} type="number" required min={parameter.min} max={parameter.max} step={stepOf(parameter)} value={value} disabled={busy} aria-invalid={shownProblem ? true : undefined} aria-describedby={describedBy} onChange={event => setDrafts(previous => ({...previous, [parameter.name]: event.target.value}))}/>{parameter.unit && <span className="parameter-unit" aria-hidden="true">{parameter.unit}</span>}<button type="submit" aria-label={`Review ${parameter.name}`} title={problem || 'Preview this edit'} disabled={busy || !changed}><Icon name="arrow"/></button></div>
        <small id={`${id}-range`}>{parameter.min} to {parameter.max}{parameter.unit ? ` ${parameter.unit}` : ' / unit not declared'}{parameter.integer ? ' / whole numbers' : ''}</small>
        <div className="parameter-feedback"><small className="parameter-problem error" id={`${id}-problem`} aria-live="polite">{shownProblem}</small>{dirty && !busy && <button type="button" className="parameter-revert" onClick={() => setDrafts(previous => ({...previous, [parameter.name]: String(parameter.value)}))}>Revert to {parameter.value}{parameter.unit ? ` ${parameter.unit}` : ''}</button>}</div>
      </form>;
    })}
  </section>;
}
