import { useId, type ReactNode } from 'react';
export type IconName = 'orbit'|'pan'|'fitModel'|'display'|'grid'|'shaded'|'front'|'top'|'side'|'iso'|'zoomIn'|'zoomOut'|'reset'|'eyeOff'|'search'|'browser'|'inspector'|'parameters'|'cube'|'folder'|'layers'|'eye'|'chat'|'history'|'download'|'fit'|'wire'|'sun'|'moon'|'check'|'arrow'|'close';
const paths: Record<IconName, ReactNode> = {
 // Original precision-CAD glyphs: cut faces, open corners and calibrated axes.
 orbit:<><ellipse cx="12" cy="12" rx="10" ry="4.5" transform="rotate(-28 12 12)"/><path d="m18 3 1 5-5-1"/><path d="m12 7 4 2.5v5L12 17l-4-2.5v-5L12 7Z" fill="currentColor" fillOpacity=".12"/></>,
 pan:<><path d="M12 2v20M2 12h20m-13-7 3-3 3 3M9 19l3 3 3-3M5 9l-3 3 3 3m14-6 3 3-3 3"/><rect x="9" y="9" width="6" height="6" rx="1" fill="currentColor" fillOpacity=".18"/></>,
 fitModel:<><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/><path d="m12 6 5 3v6l-5 3-5-3V9l5-3Z" fill="currentColor" fillOpacity=".12"/><path d="m7 9 5 3 5-3m-5 3v6"/></>,
 display:<><path d="m12 2 8.5 5v10L12 22l-8.5-5V7L12 2Z"/><path d="M12 2v20m0-20 8.5 5L12 12V2Z" fill="currentColor" fillOpacity=".22"/><path d="m3.5 7 8.5 5 8.5-5M12 12v10"/></>,
 grid:<><path d="m2 13 9-9 11 7-9 9-11-7Z" fill="currentColor" fillOpacity=".08"/><path d="m5 10 11 7M8 7l11 7M6 15.5l9-9m-5.5 11L18.5 8"/></>,
 shaded:<><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4 7.5 8 4.5v9l-8-4.5v-9Z" fill="currentColor" fillOpacity=".24"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></>,
 front:<><path d="m7 7 5-3 8 4.5V17l-5 3H7V7Z"/><path d="M7 7h8v13H7Z" fill="currentColor" fillOpacity=".25"/><path d="m15 7 5 1.5M15 7v13M4 10v10h8"/></>,
 top:<><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m12 3 8 4.5-8 4.5-8-4.5L12 3Z" fill="currentColor" fillOpacity=".3"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></>,
 side:<><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m12 12 8-4.5v9L12 21v-9Z" fill="currentColor" fillOpacity=".3"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></>,
 iso:<><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m12 3 8 4.5-8 4.5-8-4.5L12 3Z" fill="currentColor" fillOpacity=".16"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9M2 20h3m14-17h3"/></>,
 zoomIn:<><circle cx="10" cy="10" r="6.5"/><path d="m15 15 6 6M7 10h6m-3-3v6"/></>,
 zoomOut:<><circle cx="10" cy="10" r="6.5"/><path d="m15 15 6 6M7 10h6"/></>,
 reset:<><path d="M4 9a8 8 0 1 1 0 7M3 3v7h7"/><rect x="9" y="9" width="6" height="6" rx=".5" fill="currentColor" fillOpacity=".16"/></>,
 eyeOff:<><path d="m3 3 18 18M9 5a12 12 0 0 1 13 7 18 18 0 0 1-4 4M6 6a18 18 0 0 0-4 6s4 7 10 7c2 0 3.5-.5 5-1.5M10 10a3 3 0 0 0 4 4"/></>,
 search:<><circle cx="10" cy="10" r="6"/><path d="m14.5 14.5 5.5 5.5"/></>,
 browser:<><path d="M4 4v14h4M4 11h4"/><rect x="9" y="3" width="11" height="4" rx=".5"/><rect x="9" y="9" width="11" height="4" rx=".5"/><rect x="9" y="16" width="11" height="4" rx=".5"/></>,
 inspector:<><rect x="3" y="4" width="18" height="16" rx="1"/><path d="M14 4v16M17 8h1M17 12h1M17 16h1"/></>,
 parameters:<><path d="M4 6h6m4 0h6M4 12h2m4 0h10M4 18h10m4 0h2"/><rect x="10" y="3" width="4" height="6" rx=".5"/><rect x="6" y="9" width="4" height="6" rx=".5"/><rect x="14" y="15" width="4" height="6" rx=".5"/></>,
 cube:<><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></>,
 folder:<path d="M3 7V5h6l2 2h10v12H3V7Z"/>,
 layers:<><path d="m3 8 9-5 9 5-9 5-9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
 eye:<><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,
 chat:<path d="M4 4h16v12H9l-5 4V4Zm4 5h8M8 12h5"/>,
 history:<><path d="M4 8a8 8 0 1 1-1 6M3 3v6h6"/><path d="M12 7v5l3 2"/></>,
 download:<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>,
 fit:<><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/><rect x="8" y="8" width="8" height="8" rx="1"/></>,
 wire:<><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Zm0 0v9m-8 4.5 8-4.5 8 4.5M4 7.5 12 12l8-4.5M12 12v9"/></>,
 sun:<><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/></>,
 moon:<path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z"/>,
 check:<path d="m5 12 4 4L19 6"/>, arrow:<path d="M4 12h16m-6-6 6 6-6 6"/>,close:<path d="m6 6 12 12M18 6 6 18"/>
};
type IconTone = 'sky'|'mint'|'amber'|'violet'|'neutral';
const tones:Partial<Record<IconName,IconTone>> = {
 orbit:'sky',pan:'amber',fitModel:'mint',display:'violet',grid:'mint',shaded:'sky',
 front:'sky',top:'mint',side:'amber',iso:'sky',zoomIn:'sky',zoomOut:'sky',reset:'amber',
 browser:'sky',inspector:'sky',parameters:'amber',cube:'sky',folder:'amber',layers:'violet',
 chat:'violet',history:'sky',download:'mint',fit:'mint',wire:'mint',sun:'amber',moon:'violet',check:'mint'
};
// Filled silhouettes sit behind the precise linework, with a separate refracted edge.
const glass:Partial<Record<IconName,ReactNode>> = {
 orbit:<path d="m12 7 4 2.5v5L12 17l-4-2.5v-5L12 7Z"/>,
 pan:<rect x="8" y="8" width="8" height="8" rx="2"/>,
 fitModel:<path d="m12 6 5 3v6l-5 3-5-3V9l5-3Z"/>,
 display:<path d="m12 2 8.5 5v10L12 22l-8.5-5V7L12 2Z"/>,
 grid:<path d="m2 13 9-9 11 7-9 9-11-7Z"/>,
 shaded:<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/>,
 front:<path d="m7 7 5-3 8 4.5V17l-5 3H7V7Z"/>,
 top:<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/>,
 side:<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/>,
 iso:<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/>,
 zoomIn:<circle cx="10" cy="10" r="6.5"/>,zoomOut:<circle cx="10" cy="10" r="6.5"/>,
 reset:<rect x="8" y="8" width="8" height="8" rx="2"/>,
 browser:<><rect x="9" y="3" width="11" height="4" rx=".5"/><rect x="9" y="9" width="11" height="4" rx=".5"/><rect x="9" y="16" width="11" height="4" rx=".5"/></>,
 inspector:<rect x="3" y="4" width="18" height="16" rx="1"/>,
 parameters:<><rect x="10" y="3" width="4" height="6" rx=".5"/><rect x="6" y="9" width="4" height="6" rx=".5"/><rect x="14" y="15" width="4" height="6" rx=".5"/></>,
 cube:<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/>,
 folder:<path d="M3 7V5h6l2 2h10v12H3V7Z"/>,
 layers:<path d="m3 8 9-5 9 5-9 5-9-5Z"/>,
 chat:<path d="M4 4h16v12H9l-5 4V4Z"/>,
 history:<circle cx="12" cy="12" r="7"/>,download:<path d="M4 16h16v5H4v-5Z"/>,
 fit:<rect x="8" y="8" width="8" height="8" rx="1"/>,
 wire:<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/>,
 sun:<circle cx="12" cy="12" r="4"/>,moon:<path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z"/>
};
export function Icon({name,tone}: {name:IconName;tone?:IconTone|'material'}) {
 const id=useId().replace(/:/g,'');
 const hue=tone || tones[name] || 'neutral';
 if(hue==='material') return <svg className="cad-icon icon-material" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.45" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
 return <svg className={`cad-icon icon-${hue}`} width="20" height="20" viewBox="0 0 24 24" fill="none" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
  <defs>
   <linearGradient id={`${id}-glass`} x1="10%" y1="0%" x2="85%" y2="100%"><stop stopColor="var(--icon-light)" stopOpacity=".85"/><stop offset=".42" stopColor="var(--icon-hue)" stopOpacity=".38"/><stop offset="1" stopColor="var(--icon-deep)" stopOpacity=".72"/></linearGradient>
   <linearGradient id={`${id}-edge`} x1="0%" y1="0%" x2="100%" y2="100%"><stop stopColor="var(--icon-glint)"/><stop offset=".45" stopColor="var(--icon-light)"/><stop offset="1" stopColor="var(--icon-hue)"/></linearGradient>
  </defs>
  {glass[name] && <g className="icon-glass-body" fill={`url(#${id}-glass)`} stroke={`url(#${id}-edge)`} strokeWidth=".7">{glass[name]}</g>}
  <g className="icon-detail" stroke="var(--icon-line)">{paths[name]}</g>
  {glass[name] && <g className="icon-glass-edge" stroke={`url(#${id}-edge)`} strokeWidth=".55" opacity=".9">{glass[name]}</g>}
 </svg>;
}
