import { useId, type ReactNode } from 'react';
export type IconName = 'orbit'|'pan'|'fitModel'|'display'|'grid'|'shaded'|'front'|'top'|'side'|'iso'|'zoomIn'|'zoomOut'|'reset'|'eyeOff'|'search'|'browser'|'inspector'|'parameters'|'cube'|'folder'|'layers'|'eye'|'chat'|'history'|'download'|'fit'|'wire'|'sun'|'moon'|'check'|'arrow'|'close'|'selectBody'|'selectFace'|'pin'|'minus'|'lasso'|'measure';

// True isometric cube on the 24-unit grid (30° edges, 9.5-unit sides), shared by every view glyph.
const HEX = 'M12 2.5 20.25 7.25v9.5L12 21.5l-8.25-4.75v-9.5Z';
const TOP = 'M12 2.5 20.25 7.25 12 12 3.75 7.25Z';
const LEFT = 'M3.75 7.25 12 12v9.5l-8.25-4.75Z';
const RIGHT = 'M12 12 20.25 7.25v9.5L12 21.5Z';
const SEAMS = 'M3.75 7.25 12 12l8.25-4.75M12 12v9.5';
// Half-scale cube for glyphs that hold a model inside another device (orbit, fit).
const MINI = 'M12 7.25 16.13 9.63v4.75L12 16.75l-4.13-2.37V9.63Z';
const MINI_TOP = 'M12 7.25 16.13 9.63 12 12 7.87 9.63Z';
const MINI_RIGHT = 'M12 12 16.13 9.63v4.75L12 16.75Z';
const MINI_SEAMS = 'M7.87 9.63 12 12l4.13-2.37M12 12v4.75';
const BRACKETS = 'M3 8V4a1 1 0 0 1 1-1h4m8 0h4a1 1 0 0 1 1 1v4m0 8v4a1 1 0 0 1-1 1h-4m-8 0H4a1 1 0 0 1-1-1v-4';
const LENS = 'M10.5 3.5a7 7 0 1 1 0 14 7 7 0 0 1 0-14Z';
const HANDLE = 'm15.4 17.5 2.1-2.1 4.1 4.1a1.5 1.5 0 0 1-2.1 2.1Z';
const PLANE = 'M12 5 22 11 12 17 2 11Z';
const PAN_HEADS = 'M12 1.75 15.25 5.5h-6.5Zm0 20.5L8.75 18.5h6.5ZM1.75 12 5.5 8.75v6.5Zm20.5 0L18.5 15.25v-6.5Z';
const PAN_HUB = 'M12 9.25a2.75 2.75 0 1 1 0 5.5 2.75 2.75 0 0 1 0-5.5Z';
const BALL = 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z';
const BALL_SHADE = 'M4.6 17.1A9 9 0 0 0 20.4 9a8 8 0 0 1-15.8 8.1Z';
const BUBBLE = 'M5.5 4h13A1.5 1.5 0 0 1 20 5.5v9a1.5 1.5 0 0 1-1.5 1.5H10l-5 4.25V5.5A1.5 1.5 0 0 1 5.5 4Z';
const FOLDER = 'M3 6.5A1.5 1.5 0 0 1 4.5 5h4.6l2 2h8.4A1.5 1.5 0 0 1 21 8.5v9.5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18Z';
const FOLDER_FLAP = 'M3 10.5h18V18a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18Z';
const TREE_NODES = 'M10 4.5h10a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1Zm0 6.25h10a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1Zm0 6.25h10a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1Z';
const KNOBS = 'M9.5 3h3a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Zm-4 6h3a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1Zm9 6h3a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1Z';
const FRAME = 'M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z';
const FRAME_COLUMN = 'M14 4h5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-5Z';
const CLOCK = 'M12 5.25a6.75 6.75 0 1 1 0 13.5 6.75 6.75 0 0 1 0-13.5Z';
const TRAY = 'M3.5 15h17v4.5a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1Z';
const DOWN_ARROW = 'M10.5 2.75h3v7h3.5L12 14.75 7 9.75h3.5Z';
const LAYER_TOP = 'M12 3 21 8l-9 5-9-5Z';
const DISC = 'M12 7.25a4.75 4.75 0 1 1 0 9.5 4.75 4.75 0 0 1 0-9.5Z';
const MOON = 'M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z';
const STAGE_BALL = 'M11 4a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13Z';
const STAGE_SHADE = 'M5.4 13.9A6.5 6.5 0 0 0 17.3 9.2a5.6 5.6 0 0 1-11.9 4.7Z';
const SPARK = 'M19.5 1.5 20.4 3.85 22.75 4.75 20.4 5.65 19.5 8 18.6 5.65 16.25 4.75 18.6 3.85Z';
const STAGE_FLOOR = 'M3 19.5c0-1.4 4-2.5 9-2.5s9 1.1 9 2.5-4 2.5-9 2.5-9-1.1-9-2.5Z';

// Precision linework drawn over the glass. Also the whole glyph for line-only and material icons.
const paths: Record<IconName, ReactNode> = {
 orbit:<><path d={MINI}/><path d={MINI_SEAMS}/><path d="M18.6 6.4c2.6.6 4 1.9 3.3 3.5-1.1 2.6-6.6 5.6-12.3 6.7-5.7 1.1-9.3-.1-8.1-2.7.5-1.1 1.8-2.3 3.7-3.4"/><path d="m16.6 4.4 2.3 2-2.9 1.1"/></>,
 pan:<><path d={PAN_HEADS}/><path d={PAN_HUB}/><path d="M12 5.5v3.75m0 5.5v3.75M5.5 12h3.75m5.5 0h3.75"/></>,
 fitModel:<><path d={BRACKETS}/><path d={MINI}/><path d={MINI_SEAMS}/></>,
 fit:<><path d={BRACKETS}/><rect x="7.5" y="7.5" width="9" height="9" rx="1.5"/></>,
 display:<><path d={STAGE_FLOOR}/><path d={STAGE_BALL}/><path d={SPARK}/></>,
 grid:<><path d={PLANE}/><path d="m15.33 7-10 6m13.34-4-10 6M8.67 7l10 6M5.33 9l10 6"/></>,
 shaded:<><path d={BALL}/><path d={BALL_SHADE} fill="currentColor" fillOpacity=".3"/></>,
 front:<><path d={HEX}/><path d={SEAMS}/></>,
 top:<><path d={HEX}/><path d={SEAMS}/></>,
 side:<><path d={HEX}/><path d={SEAMS}/></>,
 iso:<><path d={HEX}/><path d={SEAMS}/></>,
 cube:<><path d={HEX}/><path d={SEAMS}/></>,
 // Wireframe reads as a tessellated mesh: every face split along its diagonal.
 wire:<><path d={HEX}/><path d={SEAMS}/><path d="M3.75 7.25h16.5M3.75 7.25 12 21.5m0-9.5 8.25 4.75" strokeOpacity=".7"/></>,
 zoomIn:<><path d={LENS}/><path d={HANDLE}/><path d="M7.25 10.5h6.5m-3.25-3.25v6.5"/></>,
 zoomOut:<><path d={LENS}/><path d={HANDLE}/><path d="M7.25 10.5h6.5"/></>,
 reset:<><path d="M4.5 14.5A7.75 7.75 0 1 0 6.6 6.1"/><path d="M3.25 3.75 3.6 8.4l4.6-.5"/><path d={DISC} transform="translate(6 6) scale(.5)"/></>,
 browser:<><path d={TREE_NODES}/><path d="M5 3.5v14.75M5 6h4m-4 6.75h4m-4 5.5h4"/></>,
 inspector:<><path d={FRAME}/><path d="M14 4v16m2.5-11.5h2m-2 3.5h2m-2 3.5h2M6 8.5h5"/></>,
 parameters:<><path d={KNOBS}/><path d="M3 6h5.5m5 0H21M3 12h1.5m5 0H21M3 18h10.5m5 0H21"/></>,
 folder:<><path d={FOLDER}/><path d="M3 10.5h18"/></>,
 layers:<><path d={LAYER_TOP}/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
 chat:<><path d={BUBBLE}/><path d="M8 8.5h8M8 11.75h5"/></>,
 history:<><path d={CLOCK}/><path d="M3.6 9.2A8.9 8.9 0 1 1 3.4 14.6"/><path d="M2.75 4.75v4.75h4.75"/><path d="M12 8.5V12l2.5 1.75"/></>,
 download:<><path d={TRAY}/><path d={DOWN_ARROW}/></>,
 sun:<><path d={DISC}/><path d="M12 1.75v2.5m0 15.5v2.5M1.75 12h2.5m15.5 0h2.5M4.75 4.75l1.75 1.75m11 11 1.75 1.75M4.75 19.25l1.75-1.75m11-11 1.75-1.75"/></>,
 moon:<path d={MOON}/>,
 // Interface chrome stays plain line: glass is reserved for objects and tools.
 eye:<><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,
 eyeOff:<><path d="m3 3 18 18M9 5a12 12 0 0 1 13 7 18 18 0 0 1-4 4M6 6a18 18 0 0 0-4 6s4 7 10 7c2 0 3.5-.5 5-1.5M10 10a3 3 0 0 0 4 4"/></>,
 search:<><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></>,
 check:<path d="m5 12.5 4.5 4.5L19 7"/>,
 arrow:<path d="M4 12h16m-6-6 6 6-6 6"/>,
 close:<path d="m6 6 12 12M18 6 6 18"/>,
 minus:<path d="M7 12h10"/>,
 lasso:<><path d="M12 4.5c4.7 0 8.25 2.2 8.25 5s-3.55 5-8.25 5-8.25-2.2-8.25-5 3.55-5 8.25-5Z" strokeDasharray="2.4 2.2"/><path d="M7.2 14c-.9 1.3-.5 2.7.8 3.2 1.4.5 2 1.6 1.6 3"/><path d="M14.6 13.4 21 15.8l-2.8 1.2-1.2 2.8Z"/></>,
 // Selection tools: what you point at rides into the next request.
 selectBody:<><path d={MINI}/><path d={MINI_SEAMS}/><path d="M4 8V4h4m8 0h4v4M4 16v4h4"/><path d="M14.6 13.4 21 15.8l-2.8 1.2-1.2 2.8Z"/></>,
 selectFace:<><path d={HEX}/><path d={SEAMS}/><path d="M14.6 13.4 21 15.8l-2.8 1.2-1.2 2.8Z"/></>,
 pin:<><path d="M12 21.5s-6.5-6-6.5-11.25a6.5 6.5 0 0 1 13 0C18.5 15.5 12 21.5 12 21.5Z"/><circle cx="12" cy="10.25" r="2.25"/></>,
 // A rule laid across the view, ticks on its measuring edge: distance and angle between two picks.
 measure:<><path d="M3 16.2 16.2 3 21 7.8 7.8 21Z"/><path d="m5.64 13.56 1.41 1.41M8.28 10.92l2.26 2.26M10.92 8.28l1.41 1.41M13.56 5.64l2.26 2.26"/></>
};

// Hue carries meaning: stone = camera views, mint = navigation, violet = display, amber = workspace.
type IconTone = 'sky'|'mint'|'amber'|'violet'|'neutral';
const tones:Partial<Record<IconName,IconTone>> = {
 front:'sky',top:'sky',side:'sky',iso:'sky',cube:'sky',
 lasso:'mint',selectBody:'mint',selectFace:'mint',pin:'mint',measure:'mint',
 orbit:'mint',pan:'mint',zoomIn:'mint',zoomOut:'mint',fit:'mint',fitModel:'mint',check:'mint',
 display:'violet',shaded:'violet',wire:'violet',grid:'violet',reset:'violet',moon:'violet',
 browser:'amber',inspector:'amber',parameters:'amber',folder:'amber',layers:'amber',chat:'amber',history:'amber',download:'amber',sun:'amber'
};

// Faceted glass: `body` is the gem, `hi` the lit facet, `lo` the facet in shadow, `clear` an uncoloured pane.
type Glass = {body?:string; hi?:string; lo?:string; clear?:string};
const glass:Partial<Record<IconName,Glass>> = {
 cube:{body:HEX,hi:TOP,lo:RIGHT},
 iso:{body:HEX,hi:TOP,lo:RIGHT},
 // The named face is the coloured gem; the rest of the cube stays clear glass.
 front:{clear:HEX,body:LEFT},
 top:{clear:HEX,body:TOP},
 side:{clear:HEX,body:RIGHT},
 wire:{clear:HEX},
 shaded:{body:BALL,lo:BALL_SHADE},
 display:{clear:STAGE_FLOOR,body:STAGE_BALL,lo:STAGE_SHADE,hi:SPARK},
 grid:{body:PLANE},
 orbit:{body:MINI,hi:MINI_TOP,lo:MINI_RIGHT},
 fitModel:{body:MINI,hi:MINI_TOP,lo:MINI_RIGHT},
 fit:{body:'M9 7.5h6a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5H9A1.5 1.5 0 0 1 7.5 15V9A1.5 1.5 0 0 1 9 7.5Z'},
 pan:{body:PAN_HEADS+PAN_HUB},
 zoomIn:{body:LENS,lo:HANDLE},zoomOut:{body:LENS,lo:HANDLE},
 reset:{body:'M12 9.6a2.4 2.4 0 1 1 0 4.8 2.4 2.4 0 0 1 0-4.8Z'},
 browser:{body:TREE_NODES},
 inspector:{clear:FRAME,body:FRAME_COLUMN},
 parameters:{body:KNOBS},
 folder:{body:FOLDER,hi:FOLDER_FLAP},
 layers:{body:LAYER_TOP},
 chat:{body:BUBBLE},
 history:{body:CLOCK},
 download:{body:TRAY+DOWN_ARROW},
 sun:{body:DISC},
 moon:{body:MOON},
 selectBody:{body:MINI,hi:MINI_TOP,lo:MINI_RIGHT},
 selectFace:{clear:HEX,hi:TOP},
 lasso:{clear:'M12 4.5c4.7 0 8.25 2.2 8.25 5s-3.55 5-8.25 5-8.25-2.2-8.25-5 3.55-5 8.25-5Z'},
 pin:{body:'M12 21.5s-6.5-6-6.5-11.25a6.5 6.5 0 0 1 13 0C18.5 15.5 12 21.5 12 21.5Z'},
 measure:{body:'M3 16.2 16.2 3 21 7.8 7.8 21Z'}
};

export function Icon({name,tone}: {name:IconName;tone?:IconTone|'material'}) {
 const id=useId().replace(/:/g,'');
 const hue=tone || tones[name] || 'neutral';
 if(hue==='material') return <svg className="cad-icon icon-material" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
 const g=glass[name];
 const url=(part:string)=>`url(#${id}-${part})`;
 return <svg className={`cad-icon icon-${hue}`} width="20" height="20" viewBox="0 0 24 24" fill="none" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
  {g && <defs>
   <linearGradient id={`${id}-body`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="var(--icon-light)" stopOpacity=".95"/><stop offset=".5" stopColor="var(--icon-hue)" stopOpacity=".82"/><stop offset="1" stopColor="var(--icon-deep)" stopOpacity=".95"/></linearGradient>
   <linearGradient id={`${id}-hi`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="var(--icon-glint)" stopOpacity=".95"/><stop offset="1" stopColor="var(--icon-light)" stopOpacity=".55"/></linearGradient>
   <linearGradient id={`${id}-lo`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="var(--icon-hue)" stopOpacity=".25"/><stop offset="1" stopColor="var(--icon-deep)"/></linearGradient>
   {/* A hard-edged reflection band is what makes the fill read as glass rather than paint. */}
   <linearGradient id={`${id}-sheen`} x1="0" y1="0" x2=".6" y2=".75"><stop stopColor="var(--icon-glint)" stopOpacity=".7"/><stop offset=".38" stopColor="var(--icon-glint)" stopOpacity=".14"/><stop offset=".39" stopColor="var(--icon-glint)" stopOpacity="0"/></linearGradient>
  </defs>}
  {g && <g className="icon-glass-body" stroke="none">
   {g.clear && <path className="glass-clear" d={g.clear}/>}
   {g.body && <path className="glass-main" d={g.body} fill={url('body')}/>}
   {g.hi && <path className="glass-hi" d={g.hi} fill={url('hi')}/>}
   {g.lo && <path className="glass-lo" d={g.lo} fill={url('lo')}/>}
   {g.body && <path className="glass-sheen" d={g.body} fill={url('sheen')}/>}
  </g>}
  <g className="icon-detail" stroke="var(--icon-line)">{paths[name]}</g>
 </svg>;
}
