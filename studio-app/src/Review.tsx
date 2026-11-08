// The reviewer agent's verdict (#28) and the session meter. The reviewer is independent of the
// designer: it scores the kept design with the magic-cad-reviewer rubric after the gates pass.
import React, { useEffect, useState } from 'react';

export type Fix = { rank: number; text: string; parameter?: string; value?: number };
export type Review = { scores: Record<string, number>; total: number; band: string; pass: boolean; tells: string[]; fixes: Fix[]; good: string };
export type Usage = { started: number | null; tokens: number; cost: number; reported: boolean };

const DIMENSIONS: [string, string][] = [['looks_like_the_thing', 'Looks like the thing'], ['detail', 'Detail with a reason'],
  ['dimensions', 'Dimension honesty'], ['proportion', 'Proportion and stance'], ['print_intent', 'Print intent']];

export function ReviewCard({ review }: { review: Review }) {
  return <section className={`review-card ${review.pass ? 'pass' : 'fail'}`} aria-label="Design review">
    <header>
      <h3>Design review</h3>
      <p className="review-score"><b>{review.total}</b>/20 · {review.band}</p>
    </header>
    <p className="review-lede">{review.pass
      ? 'An independent reviewer judged the kept design against its brief. A review is not a print.'
      : 'An independent reviewer judged the kept design against its brief and wants changes before you call it done.'}</p>
    <dl className="review-scores">{DIMENSIONS.map(([key, label]) => <div key={key}>
      <dt>{label}</dt>
      <dd><span className="review-pips" aria-hidden="true">{[0, 1, 2, 3].map(i => <i key={i} className={i < (review.scores[key] ?? 0) ? 'on' : ''} />)}</span><span className="review-num">{review.scores[key] ?? 0}/4</span></dd>
    </div>)}</dl>
    {review.fixes.length > 0 && <><h4>Fixes, most important first</h4>
      <ol className="review-fixes">{review.fixes.map(f => <li key={f.rank}>{f.text}{f.parameter && <span className="review-param">{f.parameter} → {f.value}</span>}</li>)}</ol></>}
    {review.tells.length > 0 && <p className="review-tells"><b>Tells:</b> {review.tells.join('; ')}</p>}
    {review.good && <p className="review-good"><b>Good:</b> {review.good}</p>}
  </section>;
}

const clock = (ms: number) => { const s = Math.floor(ms / 1000); return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`; };
const thousands = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n);

export function SessionMeter({ usage, busy }: { usage: Usage; busy: boolean }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (!busy || !usage.started) return; const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, [busy, usage.started]);
  useEffect(() => { setNow(Date.now()); }, [busy]);
  if (!usage.started) return null;
  const parts = [`Session ${clock(Math.max(0, now - usage.started))}`];
  if (usage.reported) parts.push(`${thousands(usage.tokens)} tokens`, `$${usage.cost.toFixed(usage.cost < 1 ? 3 : 2)}`);
  return <span className="session-meter" title="Time since your first request on this project, and the usage Claude Code reported for the designer and reviewer">{parts.join(' · ')} · </span>;
}
