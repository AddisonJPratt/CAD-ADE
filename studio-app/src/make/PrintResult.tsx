import React, { useRef, useState } from 'react';
import { Icon } from '../icons';

/* Recording a print (#15): each fit rated in a tap, optional caliper readings of named features
   and an optional photo. The primary fit is required and is the only thing that can move the
   fit gap; readings and the photo are kept as evidence. */

export type Result = 'perfect' | 'too_tight' | 'too_loose' | 'broke';
export const RESULTS: Record<Result, string> = { perfect: 'Perfect', too_tight: 'Too tight', too_loose: 'Too loose', broke: 'It broke' };
export type Fit = { id: string; label: string; primary: boolean };
export type Feature = { id: string; label: string; modelled_mm: number };
export type Measurement = Feature & { measured_mm: number; difference_mm: number };
export type Outcome = { result: Result; adjustment_mm: number; adjustment_reason: string | null; review_needed: boolean; ts: string;
  fits?: (Fit & { result: Result })[]; measurements?: Measurement[]; photo?: string | null };
export type Claim = { claim: string; tier: string; status: string; detail: string };
export type PrintBody = { fits: Record<string, Result>; measurements: Record<string, string>; photo: string | null };

const mm = (value: number) => `${value} mm`;
const signed = (value: number) => `${value > 0 ? '+' : value < 0 ? '−' : '±'}${Math.abs(value)} mm`;
const day = (stamp: string) => new Date(stamp).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
const lower = (label: string) => label.charAt(0).toLowerCase() + label.slice(1);

/** A photo, downsized in the browser to at most 1600 px on its long side, as a JPEG data URL. */
async function shrink(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(bitmap.width * scale)); canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return canvas.toDataURL('image/jpeg', 0.85);
}

/** The evidence tiers for this version, read from its claims: nothing physical is implied until a
    physically tested claim exists. */
export function ProveEvidence({ claims, slicer }: { claims: Claim[]; slicer: string }) {
  const untested = claims.filter(c => c.tier === 'needs physical test');
  const fits = claims.filter(c => c.tier === 'physically tested' && c.claim.startsWith('Physical fit: '));
  const readings = claims.filter(c => c.tier === 'physically tested' && c.claim.startsWith('Measured: '));
  const generic = untested.some(c => c.claim === 'Physical fit and performance');
  const name = (c: Claim, prefix: string) => c.claim.slice(prefix.length);
  return <section className="mk-evidence" aria-label="Evidence">
    <dl className="mk-tiers">
      <div><dt>Computed</dt><dd>All six checks passed: it builds, is one solid piece, fits the bed without supports and exports cleanly.</dd></div>
      <div><dt>Slicer-checked</dt><dd>{slicer}</dd></div>
      {(generic || untested.length > 0 || !fits.length) && <div><dt>Needs a physical test</dt><dd>{generic || !fits.length
        ? 'Fit, grip and strength. Only a real print shows these.'
        : `${untested.map(c => name(c, 'Physical fit: ')).join(', ')}: not rated yet.`}</dd></div>}
      {fits.length > 0 && <div><dt>Physically tested</dt><dd><ul className="mk-tested">
        {fits.map(c => <li key={c.claim}>{name(c, 'Physical fit: ')}: {lower(c.detail.split(' on a real print')[0])}</li>)}
        {readings.map(c => <li key={c.claim}>{name(c, 'Measured: ')} measured with calipers</li>)}
      </ul></dd></div>}
    </dl>
  </section>;
}

export function PrintForm({ fits, features, busy, onSave }: { fits: Fit[]; features: Feature[]; busy: boolean; onSave: (body: PrintBody) => void }) {
  const [rated, setRated] = useState<Record<string, Result>>({});
  const [readings, setReadings] = useState<Record<string, string>>({});
  const [photo, setPhoto] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState('');
  const [reading, setReading] = useState(false);
  const [invalid, setInvalid] = useState<{ id: string; message: string } | null>(null);
  const addPhoto = useRef<HTMLInputElement>(null);
  const primary = fits.find(f => f.primary);
  const choice = primary ? rated[primary.id] : undefined;
  const rate = (fit: Fit, result: Result) => setRated(r => {
    if (r[fit.id] !== result) return { ...r, [fit.id]: result };
    if (fit.primary) return r; // the required fit stays answered; tap another result to change it
    const { [fit.id]: _, ...rest } = r; return rest;
  });
  async function attach(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = '';
    if (!file) return;
    setPhotoError(''); setReading(true);
    try { setPhoto(await shrink(file)); } catch { setPhoto(null); setPhotoError('That photo could not be read. Try a JPEG or PNG.'); } finally { setReading(false); }
  }
  function removePhoto() { setPhoto(null); requestAnimationFrame(() => addPhoto.current?.focus()); }
  function save() {
    // The engine checks these too; checking here keeps the message beside the field it is about.
    for (const f of features) {
      const text = (readings[f.id] || '').trim(); const value = Number(text);
      if (text && (!Number.isFinite(value) || value <= 0 || value > 1000)) {
        setInvalid({ id: f.id, message: `Enter the ${f.label.toLowerCase()} in millimetres, up to 1000.` });
        const details = document.getElementById(`mk-measure-${f.id}`)?.closest('details'); if (details) details.open = true;
        document.getElementById(`mk-measure-${f.id}`)?.focus();
        return;
      }
    }
    setInvalid(null);
    onSave({ fits: rated, measurements: readings, photo });
  }
  return <>
    <p className="mk-quiet">Tap how each fit felt. The first is needed; skip the screws if it isn’t on the wall yet.</p>
    <div className="mk-fits">{fits.map(fit => <div className="mk-fit" key={fit.id}>
      <span className="mk-fit-name"><span id={`mk-fit-${fit.id}`}>{fit.label}</span><small id={`mk-fit-${fit.id}-need`}> {fit.primary ? 'Required' : 'Optional'}</small></span>
      <div className="mk-choices" role="group" aria-labelledby={`mk-fit-${fit.id}`} aria-describedby={`mk-fit-${fit.id}-need`}>{(Object.keys(RESULTS) as Result[]).map(r =>
        <button type="button" key={r} aria-pressed={rated[fit.id] === r} disabled={busy} onClick={() => rate(fit, r)}>{rated[fit.id] === r && <Icon name="check" />}{RESULTS[r]}</button>)}</div>
    </div>)}</div>
    <p className="mk-quiet">{choice === 'too_tight' || choice === 'too_loose' ? 'Saving this moves the fit gap for your next holder by 0.2 mm. It can’t be undone here.' : 'Your result is kept with this version and can’t be undone here.'}</p>
    <details className="mk-more">
      <summary>Add caliper measurements <small>Optional</small></summary>
      <p className="mk-quiet">Measure the printed part. Readings are kept as evidence with this print; they don’t change the fit gap.</p>
      {features.map(f => <div className="mk-row" key={f.id}>
        <label htmlFor={`mk-measure-${f.id}`}>{f.label}</label>
        <span className="mk-number"><input id={`mk-measure-${f.id}`} type="text" inputMode="decimal" autoComplete="off" value={readings[f.id] ?? ''}
          aria-invalid={invalid?.id === f.id || undefined} aria-describedby={[`mk-measure-${f.id}-model`, invalid?.id === f.id ? `mk-measure-${f.id}-error` : ''].filter(Boolean).join(' ')}
          onChange={e => { setReadings(v => ({ ...v, [f.id]: e.target.value })); if (invalid?.id === f.id) setInvalid(null); }} /><span aria-hidden="true">mm</span></span>
        <small id={`mk-measure-${f.id}-model`}>Modelled {mm(f.modelled_mm)}</small>
        {invalid?.id === f.id && <p id={`mk-measure-${f.id}-error`} className="mk-error mk-field-error" role="alert">{invalid.message}</p>}
      </div>)}
    </details>
    <div className="mk-photo">
      {photo ? <figure><img src={photo} alt="Your photo of this print" /><figcaption><button type="button" className="mk-link" disabled={busy} onClick={removePhoto}>Remove photo</button></figcaption></figure>
        : <label className="mk-secondary"><input ref={addPhoto} type="file" accept="image/jpeg,image/png,image/webp" onChange={attach} disabled={busy || reading} />{reading ? 'Reading the photo…' : 'Add a photo'} <small>Optional</small></label>}
      {photoError && <p className="mk-error" role="alert">{photoError}</p>}
    </div>
    <button type="button" className={choice ? 'mk-primary' : 'mk-secondary'} disabled={!choice || busy || reading} onClick={save}>Save result</button>
    {!choice && <p className="mk-quiet">Rate the {fits.find(f => f.primary)?.label.toLowerCase()} to save.</p>}
  </>;
}

export function PrintRecord({ outcome, photoUrl }: { outcome: Outcome; photoUrl: string }) {
  return <>
    <p>Recorded: <strong>{RESULTS[outcome.result]}</strong>, {day(outcome.ts)}.</p>
    {outcome.measurements && outcome.measurements.length > 0 && <table className="mk-measured" aria-label="Caliper measurements">
      <thead><tr><th scope="col">Feature</th><th scope="col">Modelled</th><th scope="col">Measured</th><th scope="col">Difference</th></tr></thead>
      <tbody>{outcome.measurements.map(m => <tr key={m.id}><th scope="row">{m.label}</th><td>{mm(m.modelled_mm)}</td><td>{mm(m.measured_mm)}</td><td>{signed(m.difference_mm)}</td></tr>)}</tbody>
    </table>}
    {outcome.photo && <img className="mk-print-photo" src={photoUrl} alt="Photo recorded with this print" />}
  </>;
}
