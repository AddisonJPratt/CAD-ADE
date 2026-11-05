export type Claim = { claim: string; tier: string; status: string; detail: string };
export type EvidenceDesign = { design: string; claims?: Claim[] };

const groups = [
  ['computed', 'Computed checks'],
  ['slicer-checked', 'Checked by a slicer'],
  ['needs physical test', 'Needs a physical test'],
  ['physically tested', 'Physically tested'],
] as const;

export function Evidence({ designs }: { designs: EvidenceDesign[] }) {
  const claims = designs.flatMap(design => (design.claims || []).map(claim => ({...claim, design: design.design})));
  if (!claims.length) return <p>Evidence details are unavailable for this older verdict. Run the checks again to see them.</p>;
  return <div className="evidence">{groups.map(([tier, label]) => {
    const entries = claims.filter(claim => claim.tier === tier);
    return entries.length > 0 && <section key={tier} aria-label={label}><h2>{label}</h2><ul>{entries.map((claim, index) => <li key={`${claim.design}-${index}`}><strong>{claim.claim}</strong> <span>— {claim.status}</span><br/><small>{designs.length > 1 ? `${claim.design}: ` : ''}{claim.detail}</small></li>)}</ul></section>;
  })}</div>;
}
