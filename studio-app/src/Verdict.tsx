import type { EvidenceDesign } from './Evidence';
import { Icon } from './icons';

// Plain-language reading of the harness gates for makers who do not read gate reports.
// Each entry says what passing proves; `fail` says what went wrong when it does not.
export const GATES: { key: string; pass: string; fail: string }[] = [
  { key: 'Execute', pass: 'The design builds from its own settings', fail: 'The design does not build from its settings' },
  { key: 'Geometry', pass: 'Every part is one solid piece at the intended size', fail: 'A part is not one solid piece at the intended size' },
  { key: 'Printability', pass: 'It fits your print bed and needs no supports', fail: 'It may not print cleanly on your bed' },
  { key: 'Renders', pass: 'The saved model reloads and renders correctly', fail: 'The saved model did not reload cleanly' },
  { key: 'Sweep', pass: 'It still holds together at its smallest and largest settings', fail: 'It breaks at some of its allowed settings' },
  { key: 'Exports', pass: 'Print files (STL) and CAD files (STEP) are ready', fail: 'The print files could not be written' },
];

export type Reading = { key: string; status: 'pass' | 'fail' | 'skipped'; text: string; detail: string };

export function readVerdict(designs: EvidenceDesign[]): Reading[] {
  const claims = designs.flatMap(d => d.claims || []);
  return GATES.flatMap(gate => {
    const found = claims.filter(c => c.tier === 'computed' && new RegExp(`^(\\d+ )?${gate.key}$`).test(c.claim));
    if (!found.length) return [];
    const status = found.some(c => c.status === 'FAIL' || c.status === 'ERROR') ? 'fail' : found.every(c => c.status === 'PASS') ? 'pass' : 'skipped';
    const detail = found.find(c => c.status === 'FAIL' || c.status === 'ERROR')?.detail || '';
    return [{ key: gate.key, status, text: status === 'fail' ? gate.fail : gate.pass, detail }];
  });
}

/** Translate the most common gate failure details into maker language. */
export function explain(detail: string) {
  const literal = detail.match(/line (\d+): literal ([\d.]+)/);
  if (literal) return `Line ${literal[1]} uses a fixed ${literal[2]} instead of one of the part's settings.`;
  return detail;
}

type Props = {
  number: number;
  verdict: null | { pass: boolean; designs?: EvidenceDesign[] };
  review?: null | { total: number; band: string; pass: boolean };  // the reviewer agent's verdict (#28)
  assistant: string;
  lastReady?: number;
  onFix: (text: string) => void;
  onShowVersion: (number: number) => void;
  onEvidence: () => void;
};

export function Verdict({ number, verdict, review, assistant, lastReady, onFix, onShowVersion, onEvidence }: Props) {
  const readings = verdict ? readVerdict(verdict.designs || []) : [];
  // A recorded print (#15) turns the fit claims physically tested; until then nothing physical is implied.
  const printed = (verdict?.designs || []).flatMap(d => d.claims || []).filter(c => c.tier === 'physically tested' && c.claim.startsWith('Physical fit: '));
  const perfect = printed.filter(c => c.status === 'PASS').length;
  // A tight or loose fit is calibration, not a failed check; only a broken part reads as a failure.
  const broke = printed.some(c => c.detail.startsWith('It broke'));
  const physical = printed.length ? `Real print: ${perfect} of ${printed.length} rated fits perfect` : 'Real print: fit and strength not tested';
  const failed = readings.find(r => r.status === 'fail');
  const passed = readings.filter(r => r.status === 'pass').length;
  // A failing design review blocks "done" language even when every gate is green.
  const state = !verdict ? 'pending' : !verdict.pass ? 'blocked' : review && !review.pass ? 'rework' : 'ready';
  return <section className={`verdict-card ${state}`} aria-labelledby="verdict-title">
    <h1 id="verdict-title"><span className="verdict-version">Version {number}</span>
      <span className="verdict-headline">{state === 'ready' ? 'Ready to print' : state === 'rework' ? 'Prints, but needs rework' : state === 'blocked' ? 'Not ready to print' : 'Not checked yet'}</span></h1>
    {state === 'ready' && <p>All {readings.length} computer checks passed. {review ? `The design review scored it ${review.total}/20 (${review.band}).` : 'The design has not been reviewed.'} {printed.length ? `A real print was recorded: ${perfect} of ${printed.length} rated fits were perfect. The full evidence has each one.` : 'Nobody has printed it yet, so real-world fit and strength are untested.'}</p>}
    {state === 'rework' && review && <p>All {readings.length} computer checks passed, but the independent design review scored it {review.total}/20 ({review.band}). Its fixes are in the conversation.</p>}
    {state === 'blocked' && failed && <p>{failed.text}. {explain(failed.detail)}</p>}
    {state === 'blocked' && !failed && <p>A check failed. Open the evidence to see which one.</p>}
    {state === 'pending' && <p>This version has not been through the checks.</p>}
    {readings.length > 0 && <details className="verdict-checks" open={state === 'blocked'}>
      <summary>What was checked<span className="tick-count">{passed} of {readings.length} passed</span></summary>
      <ul>{readings.map(r => <li key={r.key} className={r.status}>
        <span className="glyph" aria-hidden="true"><Icon name={r.status === 'pass' ? 'check' : r.status === 'fail' ? 'close' : 'minus'}/></span>
        <span>{r.status === 'skipped' ? `${r.text} (not reached)` : r.text}</span></li>)}
        <li className={!printed.length ? 'untested' : perfect === printed.length ? 'pass' : broke ? 'fail' : 'untested'}><span className="glyph" aria-hidden="true"><Icon name={!printed.length ? 'minus' : perfect === printed.length ? 'check' : broke ? 'close' : 'minus'}/></span><span>{physical}</span></li>
      </ul>
    </details>}
    <div className="verdict-actions">
      {state === 'blocked' && failed && <button type="button" className="quiet-button strong" onClick={() => onFix(`Fix the failed check: ${explain(failed.detail) || failed.text}`)}><Icon name="chat"/>Ask {assistant} to fix this</button>}
      {state === 'blocked' && lastReady && <button type="button" className="quiet-button" onClick={() => onShowVersion(lastReady)}>Show version {lastReady}</button>}
      <button type="button" className="quiet-button" onClick={onEvidence}>Full evidence</button>
    </div>
  </section>;
}
