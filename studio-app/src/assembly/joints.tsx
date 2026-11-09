// Joints between printed parts (#54): how Studio names them in the assembly panel and in a
// proposed change. The engine derives every value (fit class, clearance from the printer
// profile, the measured gap, the evidence tier); Studio only words them.
import type { AssemblyManifest, Joint, JointFit } from './manifest';

const LABELS: Record<string, string> = {
  snap_fit: 'Snap-fit', press_fit: 'Press fit', dovetail: 'Dovetail',
  print_in_place_hinge: 'Print-in-place hinge', living_hinge: 'Living hinge', screw_insert: 'Screw + heat-set insert',
};
const FITS: Record<string, string> = { sliding: 'sliding', press: 'press', print_in_place: 'print-in-place' };

export const jointLabel = (kind: string) => LABELS[kind] ?? kind.replace(/_/g, ' ');

export function fitText(fit: { class: string; material: string; clearance_mm: number }) {
  return `${fit.material} ${FITS[fit.class] ?? fit.class} fit, ${fit.clearance_mm}\u00a0mm per side`;
}

/** A proposed joint: the change an assembly.py edit makes, before it is kept. */
export type JointChange = { kind: 'joint'; joint: string; parts: [string, string]; fit: string; material: string; clearance: number };

export function JointChangeSummary({ change }: { change: JointChange }) {
  const [a, b] = change.parts;
  return <>
    <span className="review-part">Assembly</span>
    <strong>Add a {jointLabel(change.joint).toLowerCase()}: <ins>{a}</ins> to <ins>{b}</ins></strong>
    <small className="joint-fit">{fitText({ class: change.fit, material: change.material, clearance_mm: change.clearance })}. Needs a physical test until a print result is recorded.</small>
  </>;
}

type FittedJoint = Joint & { fit: JointFit };

/** The part-to-part joints of an assembly, each with its fit and how far it is proven. */
export function JointList({ manifest }: { manifest: AssemblyManifest }) {
  const joints = manifest.joints.filter((j): j is FittedJoint => !!j.fit);
  if (!joints.length) return null;
  const name = (id: string) => manifest.instances.find(i => i.id === id)?.name ?? id;
  return <section className="assembly-joints" aria-labelledby="assembly-joints-heading">
    <h3 id="assembly-joints-heading">Joints</h3>
    <ul>
      {joints.map(j => <li key={j.id}>
        <span className="joint-name">{jointLabel(j.role)}</span>
        <span className="joint-parts">{name(j.child)} to {name(j.parent)}</span>
        <small>{fitText(j.fit)}{j.fit.measured_mm !== null ? `; measured ${j.fit.measured_mm.toFixed(2)}\u00a0mm` : ''}</small>
        <span className={`joint-tier${j.fit.tier === 'physically tested' ? ' tested' : ''}`}>{j.fit.tier === 'physically tested' ? 'Physically tested' : 'Needs physical test'}</span>
      </li>)}
    </ul>
  </section>;
}
