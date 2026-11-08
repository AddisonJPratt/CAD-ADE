// Watermelon ButtonGroup 3/12 and Popover 9 patterns (MIT); see NOTICE.md.
// Real local viewport controls replace the catalog's illustrative actions/filters.
import { useId } from 'react';
import { Icon } from '../icons';
import { ToolHint } from './ToolHint';

export type ToolMode = 'orbit'|'pan'|'lasso'|'pin'|'measure';
export type ViewStyle = { material:'alloy'|'porcelain'|'graphite'; light:number; grid:boolean };
export const DEFAULT_VIEW:ViewStyle = {material:'alloy',light:100,grid:true};
export const MATERIALS = {
  alloy:{label:'Satin alloy',color:'#b9c2c7',metalness:.3,roughness:.36},
  porcelain:{label:'Porcelain',color:'#e4ddd0',metalness:.04,roughness:.5},
  graphite:{label:'Graphite',color:'#586575',metalness:.38,roughness:.32}
} as const;
export function ViewportTools({ready,mode,onMode,onAction,style,onStyle,wireframe,onWireframe}:{
  ready:boolean;mode:ToolMode;onMode:(mode:ToolMode)=>void;onAction:(name:string)=>void;
  style:ViewStyle;onStyle:(value:ViewStyle)=>void;wireframe:boolean;onWireframe:()=>void
}) {
  const id = useId();
  return <div className="viewport-tools">
    <div className="viewport-rail" role="group" aria-label="Viewport tools">
      <ToolHint text="Orbit the model with a drag"><button aria-label="Orbit navigation" aria-pressed={mode==='orbit'} disabled={!ready} onClick={()=>onMode('orbit')}><Icon name="orbit"/></button></ToolHint>
      <ToolHint text="Pan the model with a drag"><button aria-label="Pan navigation" aria-pressed={mode==='pan'} disabled={!ready} onClick={()=>onMode('pan')}><Icon name="pan"/></button></ToolHint>
      <ToolHint text="Circle an area of the model to select it"><button aria-label="Circle an area" aria-pressed={mode==='lasso'} disabled={!ready} onClick={()=>onMode(mode==='lasso'?'orbit':'lasso')}><Icon name="lasso"/></button></ToolHint>
      <ToolHint text="Pin a note to a spot on the model; notes stay with this version"><button aria-label="Pin a note" aria-pressed={mode==='pin'} disabled={!ready} onClick={()=>onMode(mode==='pin'?'orbit':'pin')}><Icon name="pin"/></button></ToolHint>
      <ToolHint text="Measure distance and angle between two faces"><button aria-label="Measure distance and angle" aria-pressed={mode==='measure'} disabled={!ready} onClick={()=>onMode(mode==='measure'?'orbit':'measure')}><Icon name="measure"/></button></ToolHint>
      <span className="rail-divider"/>
      <ToolHint text="Fit all visible bodies in the viewport"><button aria-label="Fit model" disabled={!ready} onClick={()=>onAction('Fit')}><Icon name="fitModel"/></button></ToolHint>
      <ToolHint text="Materials, lighting and workplane"><button aria-label="Viewport display settings" popoverTarget={id}><Icon name="display"/></button></ToolHint>
    </div>
    <section popover="auto" id={id} className="viewport-display" aria-label="Viewport display">
      <div className="display-heading"><Icon name="display"/><h2>Viewport display</h2><button type="button" popoverTarget={id} popoverTargetAction="hide" aria-label="Close display settings"><Icon name="close"/></button></div>
      <fieldset><legend>Surface finish</legend><div className="material-options">{Object.entries(MATERIALS).map(([key,value])=><button key={key} type="button" aria-label={value.label} aria-pressed={style.material===key} onClick={()=>onStyle({...style,material:key as ViewStyle['material']})}><span className={`material-swatch swatch-${key}`}><Icon name="shaded" tone="material"/></span><span>{value.label}</span>{style.material===key && <Icon name="check"/>}</button>)}</div></fieldset>
      <div className="light-control"><label htmlFor={`${id}-light`}>Studio lighting <output>{style.light}%</output></label><div><Icon name="sun"/><input id={`${id}-light`} type="range" min="40" max="160" step="5" value={style.light} onChange={event=>onStyle({...style,light:Number(event.target.value)})}/></div></div>
      <fieldset><legend>Drawing aids</legend><div className="display-toggles"><label><Icon name="grid"/><span>Workplane grid</span><input type="checkbox" checked={style.grid} onChange={event=>onStyle({...style,grid:event.target.checked})}/></label><label><Icon name="wire"/><span>Mesh edges</span><input type="checkbox" checked={wireframe} disabled={!ready} onChange={onWireframe}/></label></div></fieldset>
      <div className="display-footer"><span>Viewport appearance only</span><button type="button" onClick={()=>{onStyle({...DEFAULT_VIEW});if(wireframe)onWireframe();}}><Icon name="reset"/>Reset</button></div>
    </section>
  </div>;
}
