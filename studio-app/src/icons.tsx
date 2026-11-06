import type { ReactNode } from 'react';
export type IconName = 'search'|'browser'|'inspector'|'parameters'|'cube'|'folder'|'layers'|'eye'|'chat'|'history'|'download'|'fit'|'wire'|'sun'|'moon'|'check'|'arrow'|'close';
const paths: Record<IconName, ReactNode> = {
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
export function Icon({name}: {name: IconName}) {return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.55" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>}
