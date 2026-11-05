import { useEffect, useState } from 'react';

type Component = { id: string; name: string; source: string; notes?: string; _catalogue_file?: {path: string; modified: number} | null; dimensions: Record<string, {value: number; unit: string; provenance: string}> };

export function Catalogue({ project }: { project: string }) {
  const [components, setComponents] = useState<Component[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setComponents(null); setError('');
    fetch(`/api/catalogue?${new URLSearchParams({project})}`).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Catalogue unavailable');
      if (active) setComponents(data.components);
    }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [project]);
  return <section><h2>Purchased components</h2><p>Current project catalogue; not tied to the selected version.</p>{error && <p role="alert">Could not load catalogue: {error}</p>}{!components && !error && <p role="status">Loading catalogue…</p>}{components?.map(item => <article key={item.id}><h3>{item.name}</h3>{item.notes && <p>{item.notes}</p>}<p>Catalogue file: {item._catalogue_file?.path || "Unavailable"}{item._catalogue_file && ` · Modified ${new Date(item._catalogue_file.modified * 1000).toLocaleString()}`}</p><p>Source: {item.source.startsWith('https://') ? <a href={item.source}>{item.source}</a> : item.source}</p><ul>{Object.entries(item.dimensions).map(([name, dimension]) => <li key={name}>{name.replaceAll('_', ' ')}: {dimension.value} {dimension.unit} — {dimension.provenance}</li>)}</ul></article>)}</section>;
}
