// How Studio shows an assembly: the tree rows and each instance's display state.
// Positions and explode offsets come from the manifest (see manifest.ts); nothing here
// computes geometry, so the view cannot drift from the CAD.
import type { AssemblyManifest, Instance } from './manifest';

/** The parts list's own words for each kind, so the tree and the parts list agree. */
export const KIND_LABEL: Record<Instance['kind'], string> = { printed: 'Printed part', hardware: 'Hardware', component: 'Purchased component' };

export interface TreeRow { id: string; name: string; kind: Instance['kind']; kindLabel: string; depth: number }

/** Every instance, depth first under its parent, siblings in manifest order. An unknown parent counts as a root. */
export function assemblyRows(manifest: AssemblyManifest): TreeRow[] {
  const ids = new Set(manifest.instances.map(i => i.id));
  const rows: TreeRow[] = []; const seen = new Set<string>();
  const visit = (instance: Instance, depth: number) => {
    if (seen.has(instance.id)) return;
    seen.add(instance.id);
    rows.push({ id: instance.id, name: instance.name, kind: instance.kind, kindLabel: KIND_LABEL[instance.kind], depth });
    manifest.instances.filter(child => child.parent === instance.id).forEach(child => visit(child, depth + 1));
  };
  manifest.instances.filter(i => i.parent === null || !ids.has(i.parent)).forEach(root => visit(root, 0));
  manifest.instances.forEach(i => visit(i, 0)); // a cycle the engine let through still lists every instance once
  return rows;
}

export type Display = 'shown' | 'hidden' | 'ghost';
export interface AssemblyViewState { hidden: string[]; ghosted: string[]; isolated: string | null; selected: string | null; explode: number }
export const INITIAL_VIEW: AssemblyViewState = { hidden: [], ghosted: [], isolated: null, selected: null, explode: 0 };

export type ViewAction =
  | { type: 'select'; id: string | null }
  | { type: 'toggleHidden' | 'toggleGhost' | 'toggleIsolate'; id: string }
  | { type: 'showAll' }
  | { type: 'explode'; amount: number };

const toggle = (list: string[], id: string) => list.includes(id) ? list.filter(x => x !== id) : [...list, id];

export function viewReducer(state: AssemblyViewState, action: ViewAction): AssemblyViewState {
  switch (action.type) {
    case 'select': return { ...state, selected: action.id };
    case 'toggleHidden': return { ...state, hidden: toggle(state.hidden, action.id) };
    case 'toggleGhost': return { ...state, ghosted: toggle(state.ghosted, action.id) };
    case 'toggleIsolate': return { ...state, isolated: state.isolated === action.id ? null : action.id };
    case 'showAll': return { ...state, hidden: [], ghosted: [], isolated: null };
    case 'explode': return { ...state, explode: Math.min(1, Math.max(0, action.amount)) };
  }
}

/** Isolation wins over the per-instance choices, which come back when it ends. */
export function displayOf(state: AssemblyViewState, id: string): Display {
  if (state.isolated !== null && state.isolated !== id) return 'hidden';
  if (state.isolated === null && state.hidden.includes(id)) return 'hidden';
  return state.ghosted.includes(id) ? 'ghost' : 'shown';
}
