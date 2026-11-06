// Watermelon Tooltip 8 keyboard-hint pattern, adapted to local tokens/custom icons.
// Source and MIT license: NOTICE.md. Portalled to escape scrolling toolbar clips.
import { cloneElement, useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type ReactElement } from 'react';
import { createPortal } from 'react-dom';

export function ToolHint({children,text}:{children:ReactElement<ButtonHTMLAttributes<HTMLButtonElement>>;text:string}) {
  const [rect,setRect] = useState<DOMRect|null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>|null>(null);
  const id = useId();
  function clear() { if (timer.current) clearTimeout(timer.current); }
  function show(element:HTMLButtonElement,delay=0) { clear(); const bounds = element.getBoundingClientRect(); if (delay) timer.current=setTimeout(() => setRect(bounds),delay); else setRect(bounds); }
  function hide() { clear();setRect(null); }
  useEffect(() => () => clear(), []);
  return <>{cloneElement(children,{
    title:undefined,
    'aria-describedby':rect ? id : children.props['aria-describedby'],
    onPointerEnter:event => {children.props.onPointerEnter?.(event);show(event.currentTarget,180);},
    onPointerLeave:event => {children.props.onPointerLeave?.(event);if (!event.currentTarget.matches(':focus-visible')) hide();},
    onFocus:event => {children.props.onFocus?.(event);show(event.currentTarget);},
    onBlur:event => {children.props.onBlur?.(event);hide();},
    onKeyDown:event => {children.props.onKeyDown?.(event);if(event.key === 'Escape') hide();}
  })}{rect && createPortal(<div id={id} role="tooltip" className="studio-tooltip" style={{top:Math.min(rect.bottom+8,window.innerHeight-60),left:Math.max(8,Math.min(rect.left,window.innerWidth-248))}}>{text}</div>,document.querySelector('.app') || document.body)}</>;
}
