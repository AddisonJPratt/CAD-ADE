// Live agent and gate progress. "Checking X" and "X: STATUS" collapse into one row per
// check; the step still running shimmers, finished steps take their verdict colour.
type Row = { text: string; status?: string; pending: boolean };

const STARTED = /^Checking (.+)$/;
const FINISHED = /^(.+): ([A-Z]+)$/;

export function rowsOf(lines: string[]): Row[] {
  const rows: Row[] = [];
  const open = new Map<string, number>();
  for (const line of lines) {
    const started = STARTED.exec(line);
    const finished = FINISHED.exec(line);
    if (started) {
      open.set(started[1], rows.length);
      rows.push({ text: started[1], pending: true });
    } else if (finished && open.has(finished[1])) {
      rows[open.get(finished[1])!] = { text: finished[1], status: finished[2], pending: false };
      open.delete(finished[1]);
    } else {
      rows.push({ text: line, pending: false });
    }
  }
  return rows;
}

const tone = (status?: string) => status === 'PASS' ? 'pass' : status === 'FAIL' || status === 'ERROR' ? 'fail' : status ? 'other' : '';

export function ProgressLines({ lines, active, idle }: { lines: string[]; active: boolean; idle?: string }) {
  const rows = rowsOf(lines);
  if (!rows.length) return idle ? <div className={active ? 'progress-row live' : 'progress-row'}><span className="shimmer-text">{idle}</span></div> : null;
  const last = rows.length - 1;
  return <>{rows.map((row, i) => {
    const live = active && (row.pending || (i === last && !row.status));
    const kind = row.status ? 'check' : row.pending ? 'check' : 'note';
    return <div key={i} className={`progress-row ${kind} ${tone(row.status)} ${live ? 'live' : ''} ${i < last && !row.status && !row.pending ? 'done' : ''}`}>
      {kind === 'check' && <i aria-hidden="true" className="progress-mark" />}
      <span className="shimmer-text">{row.text}{row.pending && live ? '…' : ''}</span>
      {row.status && <b className="progress-status">{row.status}</b>}
    </div>;
  })}</>;
}
