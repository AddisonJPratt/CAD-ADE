import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { Icon } from '../icons';
import { GATES } from '../Verdict';
import { PrintForm, PrintRecord, ProveEvidence, RESULTS, type Claim, type Feature, type Fit, type Outcome, type PrintBody } from './PrintResult';
import './make.css';

const PartView = lazy(() => import('./PartView'));

/* Make mode (#14): the guided Ask → Make → Prove → Shelf flow over the engine's /make endpoints.
   Every make is an ordinary project, so Studio and Mission Control open the same folder. */

type Field = { name: string; min: number; max: number; default: number; sizes: boolean };
type Shape = 'round' | 'rectangular';
type FormSpec = { shapes: Record<Shape, { template: string; fields: Field[]; clearance_mm: number; calibrated: boolean }>; materials: string[]; printer: string };
type Ask = { object: string; shape: Shape; material: string; readings: Record<string, number>; clearance_used_mm: number };
type Version = { id: string; number: number; message: string; timestamp: string; current: boolean; verdict: null | { pass: boolean }; outcome?: Outcome | null };
type Proof = { project: string; version: Version; make: Ask | null; checked: boolean; proven: boolean; stl: string | null; render: string | null; failure: string | null; gates: { name: string; status: string; detail: string }[]; outcome: Outcome | null; next_clearance_mm: number | null; can_remake: boolean; claims: Claim[]; fits: Fit[]; features: Feature[] };
type ShelfItem = { name: string; path: string; modified: string; make: Ask | null; versions: Version[] };
type Step = 'ask' | 'make' | 'prove' | 'shelf';
type GateState = { name: string; status: string; detail: string };

const STEPS: { id: Step; label: string }[] = [{ id: 'ask', label: 'Ask' }, { id: 'make', label: 'Make' }, { id: 'prove', label: 'Prove' }, { id: 'shelf', label: 'Shelf' }];
const ORDER = ['1 Execute', '2 Geometry', '3 Printability', '4 Renders', 'Sweep', '5 Exports'];
const FIELD_LABEL: Record<string, string> = { diameter: 'Diameter', length: 'Length', width: 'Width', depth: 'Depth', height: 'Height' };

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const value = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(value.error || 'The engine did not answer. Check that it is running.');
  return value as T;
}
const gateText = (name: string, status: string) => {
  const gate = GATES.find(g => name.endsWith(g.key));
  return gate ? (status === 'FAIL' || status === 'ERROR' ? gate.fail : gate.pass) : name;
};
const artifact = (project: string, version: string, path: string) => `/api/projects/version-artifacts?${new URLSearchParams({ project, version, path })}`;
export const sizedFor = (ask: Ask) => ask.shape === 'round' ? `${ask.readings.diameter} mm diameter` : `${ask.readings.width} × ${ask.readings.depth} × ${ask.readings.height} mm`;
const day = (stamp: string) => new Date(stamp).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

function Mark({ status }: { status: string }) {
  if (status === 'PASS') return <span className="mk-state ok"><Icon name="check" />Passed</span>;
  if (status === 'FAIL' || status === 'ERROR') return <span className="mk-state bad"><Icon name="close" />Failed</span>;
  if (status === 'running') return <span className="mk-state wait">Checking…</span>;
  if (status === 'NOT RUN') return <span className="mk-state wait">Not run</span>;
  return <span className="mk-state idle">Waiting</span>;
}

type Props = { project: string; version: string; onOpen: (path: string, studio: boolean) => void; onNewProject: () => void };

export function MakeMode({ project, version, onOpen, onNewProject }: Props) {
  const [step, setStep] = useState<Step>('ask');
  const [spec, setSpec] = useState<FormSpec | null>(null);
  const [specError, setSpecError] = useState('');
  const [proof, setProof] = useState<Proof | null>(null);
  const [making, setMaking] = useState<null | { project: string; version: string; run: string; object: string }>(null);
  const [gates, setGates] = useState<GateState[]>([]);
  const [runError, setRunError] = useState('');
  const [prefill, setPrefill] = useState<Ask | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const stream = useRef<EventSource | null>(null);
  const lastAsk = useRef<Ask | null>(null);
  useEffect(() => () => stream.current?.close(), []);

  useEffect(() => { api<FormSpec>('/make/form').then(setSpec).catch(err => setSpecError(err.message)); }, []);
  // The project open in Studio, when it was made here, opens on its proof: modes share one project.
  useEffect(() => {
    if (!project || !version || making) return;
    let active = true;
    api<Proof>(`/make/proof?${new URLSearchParams({ project, version })}`).then(value => { if (active && value.make) { setProof(value); setStep(s => s === 'ask' ? 'prove' : s); } }).catch(() => {});
    return () => { active = false; };
  }, [project, version]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { heading.current?.focus(); }, [step]);

  async function loadProof(path: string, ref: string) {
    const value = await api<Proof>(`/make/proof?${new URLSearchParams({ project: path, version: ref })}`);
    setProof(value); setStep('prove'); return value;
  }
  function follow(run: { project: string; version: string; run: string; object: string }) {
    setMaking(run); setRunError(''); setStep('make');
    setGates(ORDER.map(name => ({ name, status: 'waiting', detail: '' })));
    stream.current?.close();
    const source = new EventSource(`/api/runs/${run.run}/events`); stream.current = source;
    const current = () => stream.current === source;
    const update = (name: string, status: string, detail = '') => setGates(list => list.some(g => g.name === name) ? list.map(g => g.name === name ? { name, status, detail } : g) : [...list, { name, status, detail }]);
    source.addEventListener('gate_started', e => update(JSON.parse((e as MessageEvent).data).gate, 'running'));
    source.addEventListener('gate_finished', e => { const event = JSON.parse((e as MessageEvent).data); update(event.gate, event.status, event.detail); });
    let failed = false;
    source.addEventListener('error', e => {
      const data = (e as MessageEvent).data;
      if (data) { failed = true; setRunError(JSON.parse(data).error || 'The check stopped with an error.'); }
      else if (source.readyState === EventSource.CLOSED && current()) setRunError('Lost contact with the engine. The holder is on the Shelf; check it again from there once the engine is running.');
    });
    source.addEventListener('end', async () => {
      source.close();
      if (!current()) return; // the maker went back; the run still finishes and lands on the Shelf
      stream.current = null;
      onOpen(run.project, false);
      if (failed) return; // stay on Make with the error; Back returns to Ask
      try { await loadProof(run.project, run.version); setMaking(null); } catch (err) { setRunError((err as Error).message); }
    });
  }
  async function start(form: Record<string, string>) {
    const made = await api<{ project: string; version: { id: string }; run: { id: string } }>('/make', form);
    lastAsk.current = { object: form.object, shape: form.shape as Shape, material: form.material, readings: Object.fromEntries(Object.entries(form).filter(([k]) => k in FIELD_LABEL).map(([k, v]) => [k, Number(v)])), clearance_used_mm: 0 };
    follow({ project: made.project, version: made.version.id, run: made.run.id, object: form.object });
  }
  async function remake() {
    if (!proof) return;
    const made = await api<{ project: string; version: { id: string }; run: { id: string } }>('/make', { project: proof.project });
    follow({ project: made.project, version: made.version.id, run: made.run.id, object: proof.make?.object || '' });
  }
  async function check() {
    if (!proof) return;
    const run = await api<{ id: string }>('/runs', { project: proof.project });
    follow({ project: proof.project, version: proof.version.id, run: run.id, object: proof.make?.object || '' });
  }

  const reachable: Record<Step, boolean> = { ask: !making, make: !!making, prove: !!proof && !making, shelf: true };
  return <section className="make-mode mk" aria-labelledby="make-heading">
    <nav className="mk-steps" aria-label="Make steps">
      <ol>{STEPS.map(s => <li key={s.id}><button type="button" aria-current={step === s.id ? 'step' : undefined} disabled={!reachable[s.id]} title={reachable[s.id] ? undefined : s.id === 'make' ? 'Shows progress while a holder is being made' : s.id === 'prove' ? 'Available once a holder has been made or opened from the Shelf' : 'Available when nothing is being made'} onClick={() => setStep(s.id)}>{s.label}</button></li>)}</ol>
    </nav>
    {step === 'ask' && project && proof?.project !== project && <p className="mk-note mk-open">{project.split('/').filter(Boolean).pop()} stays open in Studio. Making a holder starts a new project beside it.</p>}
    {step === 'ask' && <AskStep key={prefill ? prefill.object + prefill.clearance_used_mm : "new"} spec={spec} specError={specError} prefill={prefill} heading={heading} onSubmit={start} onNewProject={onNewProject} />}
    {step === 'make' && making && <MakeStep object={making.object} gates={gates} error={runError} heading={heading} onBack={() => { stream.current?.close(); stream.current = null; setMaking(null); setPrefill(lastAsk.current); setStep('ask'); }} />}
    {step === 'prove' && proof && <ProveStep key={proof.project + proof.version.id + (proof.outcome ? "r" : "")} proof={proof} heading={heading} onRecorded={setProof} onRemake={remake} onCheck={check}
      onLatest={async () => { const list = await api<{ versions: Version[] }>(`/projects/versions?${new URLSearchParams({ project: proof.project })}`); const latest = list.versions.find(v => v.current); if (latest) await loadProof(proof.project, latest.id); }}
      onChange={() => { setPrefill(proof.make); setStep('ask'); }} onOpen={() => onOpen(proof.project, true)} />}
    {step === 'shelf' && <ShelfStep heading={heading} onProve={async (path, ref) => { await loadProof(path, ref); }} onOpen={path => onOpen(path, true)} onAsk={() => { setPrefill(null); setStep('ask'); }} />}
  </section>;
}

function AskStep({ spec, specError, prefill, heading, onSubmit, onNewProject }: { spec: FormSpec | null; specError: string; prefill: Ask | null; heading: React.RefObject<HTMLHeadingElement | null>; onSubmit: (form: Record<string, string>) => Promise<void>; onNewProject: () => void }) {
  const [shape, setShape] = useState<Shape>(prefill?.shape || 'round');
  const [object, setObject] = useState(prefill?.object || '');
  const [material, setMaterial] = useState(prefill?.material || 'PLA');
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(Object.entries(prefill?.readings || {}).map(([k, v]) => [k, String(v)])));
  const [error, setError] = useState('');
  const [invalid, setInvalid] = useState('');
  const [busy, setBusy] = useState(false);
  const fields = spec?.shapes[shape].fields || [];
  const fail = (field: string, message: string) => { setError(message); setInvalid(field); document.getElementById(`mk-${field}`)?.focus(); };
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!object.trim()) return fail('object', 'Enter an object name, up to 100 characters.');
    for (const field of fields) {
      const text = (values[field.name] || '').trim(); const value = Number(text); const label = FIELD_LABEL[field.name] || field.name;
      if (!text || !Number.isFinite(value)) return fail(field.name, `Enter the ${label.toLowerCase()} in millimetres.`);
      if (value < field.min || value > field.max) return fail(field.name, `${label} must be between ${field.min} and ${field.max} mm.`);
    }
    setBusy(true); setError(''); setInvalid('');
    const readings = Object.fromEntries(fields.map(f => [f.name, values[f.name].trim()]));
    try { await onSubmit({ object, shape, material, mount: 'screws', ...readings }); } catch (err) {
      const message = (err as Error).message; const field = fields.find(f => message.startsWith(FIELD_LABEL[f.name] || f.name));
      setError(message); setInvalid(field ? field.name : ''); setBusy(false);
    }
  }
  const described = (field: string, own?: string) => [own, invalid === field ? 'mk-form-error' : ''].filter(Boolean).join(' ') || undefined;
  return <div className="mk-columns">
    <div className="mk-intro">
      <h1 id="make-heading" ref={heading} tabIndex={-1}>Make a wall holder</h1>
      <p>Measure the object you want to hang with calipers, and Make sizes a screw-mounted holder to it, then checks the design before you print.</p>
      <p className="mk-quiet">Make only does wall holders for now: a clip for round things, a cradle for boxes. Holders mount with two M3 screws and fit a limited range of sizes.</p>
      <p className="mk-quiet mk-elsewhere">Making something else? Start a <button type="button" className="mk-link" onClick={onNewProject}>New project</button> in Studio from a starter design, then shape it in chat.</p>
      {spec && spec.shapes[shape].calibrated && <p className="mk-quiet">Your past prints set this holder’s fit gap to {spec.shapes[shape].clearance_mm} mm per side.</p>}
    </div>
    {specError ? <p className="mk-error" role="alert">{specError}</p> : !spec ? <p role="status">Loading the holder templates…</p> :
    <form className="mk-form" noValidate onSubmit={submit}>
      <label htmlFor="mk-object">Object name</label>
      <input id="mk-object" value={object} maxLength={100} placeholder="Bike pump" autoComplete="off" onChange={e => { setObject(e.target.value); setError(''); setInvalid(''); }} aria-invalid={invalid === 'object' || undefined} aria-describedby={described('object')} />
      <fieldset className="mk-shape">
        <legend>Shape</legend>
        {(['round', 'rectangular'] as Shape[]).map(option => <label key={option} className={shape === option ? 'chosen' : undefined}>
          <input type="radio" name="shape" value={option} checked={shape === option} onChange={() => { setShape(option); setError(''); setInvalid(''); }} />
          <span>{option === 'round' ? 'Round' : 'Rectangular'}</span>
          <small>{option === 'round' ? 'A clip around a tube or handle' : 'A cradle that holds a box from below'}</small>
        </label>)}
      </fieldset>
      <fieldset className="mk-measure">
        <legend>Measurements</legend>
        {fields.map(field => <div className="mk-row" key={shape + field.name}>
          <label htmlFor={`mk-${field.name}`}>{FIELD_LABEL[field.name] || field.name}</label>
          <span className="mk-number"><input id={`mk-${field.name}`} type="number" inputMode="decimal" step="any" min={field.min} max={field.max} value={values[field.name] ?? ''} placeholder={`e.g. ${field.default}`} onChange={e => { setValues(v => ({ ...v, [field.name]: e.target.value })); setError(''); setInvalid(''); }} aria-invalid={invalid === field.name || undefined} aria-describedby={described(field.name, `mk-${field.name}-range`)} /><span aria-hidden="true">mm</span></span>
          <small id={`mk-${field.name}-range`}>{field.sizes ? `${field.min}–${field.max} mm` : 'Saved for reference; it does not change this clip yet'}</small>
        </div>)}
      </fieldset>
      <div className="mk-material">
        <label htmlFor="mk-material">Material</label>
        <select id="mk-material" value={material} onChange={e => setMaterial(e.target.value)}>{spec.materials.map(m => <option key={m}>{m}</option>)}</select>
      </div>
      <p id="mk-form-error" className="mk-error" role="alert">{error}</p>
      <button className="mk-primary" disabled={busy}>{busy ? 'Starting…' : 'Make my holder'}<Icon name="arrow" /></button>
      <p className="mk-quiet">Printer: {spec.printer}. {spec.shapes[shape].calibrated ? 'The fit gap comes from your recorded prints.' : 'Fit gaps are starting values until you record a print.'}</p>
    </form>}
  </div>;
}

function MakeStep({ object, gates, error, heading, onBack }: { object: string; gates: GateState[]; error: string; heading: React.RefObject<HTMLHeadingElement | null>; onBack: () => void }) {
  const done = gates.filter(g => g.status !== 'waiting' && g.status !== 'running').length;
  return <div className="mk-single">
    <h1 id="make-heading" ref={heading} tabIndex={-1}>Making the {object} holder</h1>
    <p>Sizing the design to your measurements and running every check on it. This usually takes under a minute; you can leave this page and find it on the Shelf.</p>
    <p className="mk-progress" role="status" aria-live="polite">{error ? 'The check stopped.' : `${done} of ${gates.length} checks finished`}</p>
    <ul className="mk-gates">{gates.map(g => <li key={g.name}><span>{gateText(g.name, g.status)}</span><Mark status={g.status} />{g.detail && (g.status === 'FAIL' || g.status === 'ERROR') && <p>{g.detail}</p>}</li>)}</ul>
    {error && <><p className="mk-error" role="alert">{error}</p><button type="button" className="mk-secondary" onClick={onBack}>Back to Ask</button></>}
  </div>;
}

function ProveStep({ proof, heading, onRecorded, onRemake, onCheck, onChange, onOpen, onLatest }: { proof: Proof; heading: React.RefObject<HTMLHeadingElement | null>; onRecorded: (p: Proof) => void; onRemake: () => Promise<void>; onCheck: () => Promise<void>; onChange: () => void; onOpen: () => void; onLatest: () => Promise<void> }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const ask = proof.make;
  const name = ask ? `${ask.object} holder` : proof.project.split('/').pop();
  async function act(fn: () => Promise<unknown>) { setBusy(true); setError(''); try { await fn(); } catch (err) { setError((err as Error).message); } finally { setBusy(false); } }
  const record = (body: PrintBody) => act(async () => onRecorded(await api<Proof>('/make/print', { project: proof.project, version: proof.version.id, ...body })));
  const photo = `/api/make/photo?${new URLSearchParams({ project: proof.project, version: proof.version.id })}`;
  return <div className="mk-columns prove">
    <figure className="mk-render">
      {proof.stl ? <Suspense fallback={<div className="mk-norender">Loading the part…</div>}>
        <PartView url={artifact(proof.project, proof.version.id, proof.stl)} label={`The checked ${name}, in its print orientation. Drag to turn it.`} fallback={<div className="mk-norender">The part could not be shown here; the print file is still available.</div>} />
      </Suspense> : <div className="mk-norender">{proof.checked ? 'No print file for this version' : 'Not checked yet'}</div>}
      <figcaption>Version {proof.version.number} · {proof.version.message}{proof.stl && ' · drag to turn'}</figcaption>
      {proof.render && <details className="mk-qa"><summary>Engineering render</summary><img src={artifact(proof.project, proof.version.id, proof.render)} alt={`Harness check render of the ${name}`} /></details>}
    </figure>
    <div className="mk-verdict">
      <h1 id="make-heading" ref={heading} tabIndex={-1}>{name}</h1>
      {ask && <p className="mk-lede">Sized for {sizedFor(ask)} · {ask.material} · fit gap {ask.clearance_used_mm} mm per side · screws to the wall</p>}
      {!proof.version.current && <p className="mk-note">This is version {proof.version.number}, not the latest. <button type="button" className="mk-link" onClick={() => act(onLatest)}>See the latest version</button></p>}
      {!proof.checked ? <section aria-label="Verdict"><h2>Not checked yet</h2><p>This version has no finished check, so there is no print file yet.</p>
        {proof.version.current && <button type="button" className="mk-primary" disabled={busy} onClick={() => act(onCheck)}>Check this version<Icon name="arrow" /></button>}</section>
      : proof.proven ? <section aria-label="Verdict">
        <h2>Ready to print</h2>
        <ProveEvidence claims={proof.claims} slicer="Not run. Printability comes from geometry checks, not a slicer." />
        {proof.stl && <a className={proof.outcome || !proof.version.current ? "mk-secondary" : "mk-primary"} href={artifact(proof.project, proof.version.id, proof.stl)} download={`${name}.stl`}><Icon name="download" />Download print file (STL)</a>}
      </section>
      : <section aria-label="Verdict"><h2>Not ready to print</h2><p>We couldn’t verify this holder. {proof.failure}</p>
        <ul className="mk-gates compact">{proof.gates.map(g => <li key={g.name}><span>{gateText(g.name, g.status)}</span><Mark status={g.status} /></li>)}</ul>
        <button type="button" className="mk-secondary" onClick={onChange}>Change the measurements</button></section>}
      {proof.proven && ask && <section className="mk-print" aria-labelledby="mk-print-heading">
        <h2 id="mk-print-heading">{proof.outcome ? 'Your print' : 'Printed it? How did it fit?'}</h2>
        {proof.outcome ? <>
          <PrintRecord outcome={proof.outcome} photoUrl={photo} />
          {proof.outcome.adjustment_reason ? <p>{proof.outcome.adjustment_reason} Your result is saved for review.</p>
            : proof.outcome.adjustment_mm ? <p>The fit gap for the next holder moves {proof.outcome.adjustment_mm > 0 ? 'up' : 'down'} by {Math.abs(proof.outcome.adjustment_mm)} mm, to {proof.next_clearance_mm} mm per side.</p>
            : proof.outcome.result === 'broke' ? <p>Saved for review. The fit gap is unchanged.</p> : null}
          {proof.can_remake && <button type="button" className="mk-primary" disabled={busy} onClick={() => act(onRemake)}>Make an adjusted version<Icon name="arrow" /></button>}
        </> : <PrintForm fits={proof.fits} features={proof.features} busy={busy} onSave={record} />}
      </section>}
      <p className="mk-error" role="alert">{error}</p>
      <p className="mk-links"><button type="button" className="mk-link" onClick={onOpen}>Open in Studio</button></p>
    </div>
  </div>;
}

function ShelfStep({ heading, onProve, onOpen, onAsk }: { heading: React.RefObject<HTMLHeadingElement | null>; onProve: (path: string, version: string) => Promise<void>; onOpen: (path: string) => void; onAsk: () => void }) {
  const [items, setItems] = useState<ShelfItem[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { api<{ projects: ShelfItem[] }>('/make/shelf').then(v => setItems(v.projects)).catch(err => setError(err.message)); }, []);
  const status = (v: Version) => v.verdict === null ? 'Not checked' : v.verdict.pass ? 'Ready to print' : 'Not ready';
  return <div className="mk-single wide">
    <h1 id="make-heading" ref={heading} tabIndex={-1}>Shelf</h1>
    <p>Everything you have made, with every version, its check and how its print went.</p>
    {error && <p className="mk-error" role="alert">{error}</p>}
    {!items && !error && <p role="status">Loading the shelf…</p>}
    {items && !items.length && <div className="mk-empty"><p>Nothing on the shelf yet.</p><button type="button" className="mk-primary" onClick={onAsk}>Make your first holder<Icon name="arrow" /></button></div>}
    {items && items.length > 0 && <ul className="mk-shelf">{items.map(item => {
      const latest = item.versions[0]; const printed = item.versions.find(v => v.outcome);
      return <li key={item.path}>
        <div className="mk-shelf-head">
          <div><h2>{item.name}</h2><p>{item.make ? `${item.make.object} · ${sizedFor(item.make)}` : 'Made in Studio'}{latest ? ` · ${status(latest)}` : ''}{printed?.outcome ? ` · Last print: ${RESULTS[printed.outcome.result]} (version ${printed.number})` : ''}</p></div>
          <button type="button" className="mk-secondary" onClick={() => onOpen(item.path)} aria-label={`Open in Studio: ${item.name}`}>Open in Studio</button>
        </div>
        {item.versions.length > 0 && <details><summary>{item.versions.length === 1 ? '1 version' : `${item.versions.length} versions`}</summary>
          <ol className="mk-history">{item.versions.map(v => <li key={v.id}>
            <span className="mk-num">Version {v.number}</span>
            <span className="mk-msg">{v.message}<small>{day(v.timestamp)}</small></span>
            <span className="mk-check">{status(v)}{v.outcome ? ` · Printed: ${RESULTS[v.outcome.result]}` : ''}</span>
            {item.make && (v.verdict !== null || v.current) && <button type="button" className="mk-link" onClick={() => onProve(item.path, v.id).catch(err => setError((err as Error).message))} aria-label={`Proof: ${item.name} version ${v.number}`}>Proof</button>}
          </li>)}</ol>
        </details>}
      </li>;
    })}</ul>}
  </div>;
}
