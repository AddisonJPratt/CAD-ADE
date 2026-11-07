import { useEffect, useState } from 'react';

type Row = { category: string; item: string; quantity: number; specification: string; source: string; instances: string[] };
type PartsListDocument = { assembly: string; source_sha256: string | null; rows: Row[] };
type State = { status: 'loading' } | { status: 'none' } | { status: 'error'; message: string } | { status: 'ready'; list: PartsListDocument };

const NO_ASSEMBLY = /^no assembly\.py in /;
const HEADINGS: Record<string, string> = { 'Printed part': 'Printed parts', Hardware: 'Hardware', 'Purchased component': 'Purchased components' };

export function PartsList({ project }: { project: string }) {
  const [state, setState] = useState<State>({ status: 'loading' });
  useEffect(() => {
    let active = true;
    setState({ status: 'loading' });
    fetch(`/api/projects/parts-list?${new URLSearchParams({ project })}`).then(async response => {
      const data = await response.json();
      if (!active) return;
      if (response.ok) setState({ status: 'ready', list: data });
      else if (NO_ASSEMBLY.test(data.error || '')) setState({ status: 'none' });
      else setState({ status: 'error', message: data.error || 'The engine did not answer.' });
    }).catch(err => { if (active) setState({ status: 'error', message: err.message }); });
    return () => { active = false; };
  }, [project]);

  const csv = `/api/projects/parts-list?${new URLSearchParams({ project, format: 'csv' })}`;
  const categories = state.status === 'ready' ? [...new Set(state.list.rows.map(row => row.category))] : [];
  return <section className="parts-list" aria-labelledby="parts-list-heading">
    <div className="parts-list-head">
      <h2 id="parts-list-heading">Parts list</h2>
      {state.status === 'ready' && <a className="download" href={csv} download="parts_list.csv">Download CSV</a>}
    </div>
    <p>Built from the project's current assembly file, not the selected version. Change the assembly to change this list.</p>
    {state.status === 'loading' && <p role="status">Reading the assembly…</p>}
    {state.status === 'none' && <p>This project has no assembly file. Add <code>assembly.py</code> to list its printed parts, hardware and purchased components.</p>}
    {state.status === 'error' && <p role="alert">Could not build the parts list: {state.message}</p>}
    {state.status === 'ready' && <table role="table">
      <thead role="rowgroup"><tr role="row"><th role="columnheader" scope="col" className="qty">Qty</th><th role="columnheader" scope="col">Item</th><th role="columnheader" scope="col">Source</th></tr></thead>
      {categories.map(category => <tbody key={category} role="rowgroup">
        <tr className="group" role="row"><th role="rowheader" scope="rowgroup" colSpan={3}>{HEADINGS[category] || category}</th></tr>
        {state.list.rows.filter(row => row.category === category).map(row => <tr key={row.item} role="row">
          <td role="cell" className="qty">{row.quantity}</td>
          <td role="cell"><span className="item">{row.item}</span><span className="spec">{row.specification}</span></td>
          <td role="cell" className="source">{row.source.startsWith('https://') ? <a href={row.source}>Datasheet</a> : <code>{row.source}</code>}</td>
        </tr>)}
      </tbody>)}
    </table>}
  </section>;
}
