import { useId } from 'react';

// The Magic CAD brand (owner-approved, 7 November 2026). Static copies live in public/brand/.
// Mark: the Magic box, a graphite box in true isometric (30° edges) whose lid floats just above the
// base, with warm light spilling out of the gap. The glow is the brand's one non-action use of orange.

export type BrandSurface = 'light' | 'dark';

const BASE_LEFT = 'M29.36 59 64 79v28L29.36 87Z';
const BASE_RIGHT = 'M64 79l34.64-20v28L64 107Z';
const GAP = 'M29.36 53.4 64 73.4l34.64-20v5.6L64 79 29.36 59Z';
const LID_LEFT = 'M29.36 44.6 64 64.6v8.8L29.36 53.4Z';
const LID_RIGHT = 'M64 64.6l34.64-20v8.8L64 73.4Z';
const LID_TOP = 'M64 24.6l34.64 20L64 64.6 29.36 44.6Z';
// Edges: the lid's top silhouette, its front edges, the two edges lit by the gap, and the base outline.
const RIM_TOP = 'M29.36 44.6 64 24.6l34.64 20';
const RIM_LID = 'M29.36 44.6 64 64.6l34.64-20M64 64.6v8.8M29.36 44.6v8.8M98.64 44.6v8.8';
const RIM_GLOW = 'M29.36 53.4 64 73.4l34.64-20M29.36 59 64 79l34.64-20';
const RIM_BASE = 'M29.36 59v28l34.64 20 34.64-20V59M64 79v28';

type Finish = { top: [string, string]; left: [string, string]; right: [string, string]; rim: string; rimTop: [number, number]; rimLid: [number, number]; rimBase: [number, number]; glow: number };
// Light surfaces show the graphite box as approved. Dark surfaces lift the graphite and brighten the
// rims so the outline still holds against the graphite header. Each rim is [opacity, width].
const FINISH: Record<BrandSurface, Finish> = {
  light: { top: ['#4f493f', '#3b362f'], left: ['#312d27', '#25221e'], right: ['#221f1c', '#171614'], rim: '#f3e7d3', rimTop: [.6, .9], rimLid: [.38, .85], rimBase: [.2, .9], glow: .9 },
  dark: { top: ['#6a6256', '#524b41'], left: ['#433d35', '#36312b'], right: ['#312c27', '#26231f'], rim: '#f6ecdc', rimTop: [.85, 1], rimLid: [.55, .9], rimBase: [.38, .9], glow: .95 },
};

/** The Magic box. Decorative: the surrounding link or heading carries the accessible name. */
export function BrandMark({ surface, className }: { surface: BrandSurface; className?: string }) {
  const id = useId().replace(/[^\w-]/g, '');
  const f = FINISH[surface];
  const url = (part: string) => `url(#${id}-${part})`;
  return <svg className={className} viewBox="19 21 90 90" data-surface={surface} aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id={`${id}-top`} x1="40" y1="30" x2="88" y2="60" gradientUnits="userSpaceOnUse"><stop stopColor={f.top[0]}/><stop offset="1" stopColor={f.top[1]}/></linearGradient>
      <linearGradient id={`${id}-left`} x1="0" y1="46" x2="0" y2="106" gradientUnits="userSpaceOnUse"><stop stopColor={f.left[0]}/><stop offset="1" stopColor={f.left[1]}/></linearGradient>
      <linearGradient id={`${id}-right`} x1="0" y1="46" x2="0" y2="106" gradientUnits="userSpaceOnUse"><stop stopColor={f.right[0]}/><stop offset="1" stopColor={f.right[1]}/></linearGradient>
      <linearGradient id={`${id}-gap`} x1="0" y1="53" x2="0" y2="79" gradientUnits="userSpaceOnUse"><stop stopColor="#ffc47c"/><stop offset=".45" stopColor="#fff6e6"/><stop offset="1" stopColor="#ff9a52"/></linearGradient>
      <linearGradient id={`${id}-lid-spill`} x1="0" y1="73" x2="0" y2="46" gradientUnits="userSpaceOnUse"><stop stopColor="#ff9a52" stopOpacity=".6"/><stop offset="1" stopColor="#ff9a52" stopOpacity="0"/></linearGradient>
      <linearGradient id={`${id}-base-spill`} x1="0" y1="59" x2="0" y2="96" gradientUnits="userSpaceOnUse"><stop stopColor="#ff9a52" stopOpacity=".5"/><stop offset="1" stopColor="#ff9a52" stopOpacity="0"/></linearGradient>
      <filter id={`${id}-bloom`} x="-.5" y="-1.5" width="2" height="4"><feGaussianBlur stdDeviation="4"/></filter>
    </defs>
    <path d={BASE_LEFT} fill={url('left')}/>
    <path d={BASE_RIGHT} fill={url('right')}/>
    <path d={BASE_LEFT + BASE_RIGHT} fill={url('base-spill')}/>
    <path d={GAP} fill="#ff9450" filter={url('bloom')} opacity=".9"/>
    <path d={GAP} fill={url('gap')}/>
    <path d={LID_LEFT} fill={url('left')}/>
    <path d={LID_RIGHT} fill={url('right')}/>
    <path d={LID_LEFT + LID_RIGHT} fill={url('lid-spill')}/>
    <path d={LID_TOP} fill={url('top')}/>
    <g fill="none" strokeLinejoin="round">
      <path d={RIM_TOP} stroke={f.rim} strokeOpacity={f.rimTop[0]} strokeWidth={f.rimTop[1]}/>
      <path d={RIM_LID} stroke={f.rim} strokeOpacity={f.rimLid[0]} strokeWidth={f.rimLid[1]}/>
      <path d={RIM_GLOW} stroke="#ffe3b5" strokeOpacity={f.glow} strokeWidth=".9"/>
      <path d={RIM_BASE} stroke={f.rim} strokeOpacity={f.rimBase[0]} strokeWidth={f.rimBase[1]}/>
    </g>
  </svg>;
}

// MAGIC CAD outlined from Archivo (SIL Open Font License 1.1) at width 125 and weight 700 with
// +0.03em tracking, so the app never loads the font. Font units, baseline at 0; it takes the text colour.
const WORDMARK_VIEWBOX = '91 -700 7508 712';
const WORDMARK_PATH = 'M92 0V-687.2H361L502.4 -356.2Q509.6 -339.1 520.3 -310.8Q531.1 -282.5 542.5 -251.9Q553.9 -221.3 562.8 -196.6H569.8Q578 -218.7 589 -247.8Q600 -277 611.2 -305.8Q622.5 -334.7 630.5 -354.6L771.8 -687.2H1034.3V0H861.7V-393.9Q861.7 -412.7 862.2 -435.6Q862.7 -458.6 863.7 -480.9Q864.7 -503.3 865.5 -519.6H857.5Q852 -502.8 843.7 -479.8Q835.4 -456.7 827.1 -433.8Q818.7 -411 811.5 -393.9L641.7 0H478.3L307.7 -393.9Q298.2 -416.5 289.3 -440.2Q280.3 -463.9 273.5 -484.9Q266.7 -505.9 261.7 -519.6H253.7Q254.7 -506.7 255.2 -485.7Q255.7 -464.7 256.2 -441Q256.7 -417.3 256.7 -393.9V0ZM1176.5 0 1518.1 -687.2H1711.9L2053.5 0H1865.2L1805.4 -123.9H1413.6L1354 0ZM1476.9 -257.3H1742.1L1669.1 -414Q1664.5 -424.3 1656 -444.1Q1647.5 -463.9 1638.7 -485.2Q1630 -506.5 1622.9 -523.1Q1615.9 -539.7 1614 -543.5H1606.2Q1597.9 -524.2 1587.1 -499Q1576.4 -473.9 1566.5 -450.6Q1556.7 -427.2 1549.9 -413.2ZM2542.9 12Q2334.7 12 2230.4 -76Q2126.2 -164 2126.2 -343.2Q2126.2 -460.4 2179.8 -539.8Q2233.3 -619.2 2334.8 -659.2Q2436.3 -699.2 2578 -699.2Q2668.3 -699.2 2743.9 -683.5Q2819.4 -667.8 2875 -636.1Q2930.6 -604.3 2961 -556.1Q2991.3 -507.9 2991.3 -442.9H2823.3Q2823.3 -475.7 2803.9 -498.9Q2784.4 -522.2 2750.8 -536Q2717.2 -549.9 2674.6 -556.3Q2632 -562.7 2585.1 -562.7Q2522.6 -562.7 2470.7 -550.4Q2418.8 -538.1 2381.3 -512.5Q2343.8 -486.8 2323.6 -447.8Q2303.3 -408.7 2303.3 -356V-332Q2303.3 -258.1 2335 -212.6Q2366.7 -167 2425.9 -145.8Q2485 -124.6 2567 -124.6Q2651.6 -124.6 2708.5 -139.8Q2765.4 -155.1 2794.3 -184.2Q2823.1 -213.2 2823.1 -252.5V-259.7H2560.1V-384H2992.3V0H2888.3L2871 -87Q2833.4 -52.5 2782.7 -30.5Q2731.9 -8.6 2671.4 1.7Q2610.9 12 2542.9 12ZM3199 0V-687.2H3371.7V0ZM3981.8 12Q3840.6 12 3745.7 -28.5Q3650.9 -69 3603.5 -148.4Q3556.2 -227.8 3556.2 -344Q3556.2 -514.2 3665.3 -606.7Q3774.4 -699.2 3981.4 -699.2Q4098.3 -699.2 4187.3 -665.2Q4276.4 -631.3 4326.3 -568.3Q4376.3 -505.3 4376.3 -417.5H4207.5Q4207.5 -464.5 4178.7 -496.8Q4149.8 -529.1 4098.5 -545.9Q4047.2 -562.7 3978.2 -562.7Q3901.7 -562.7 3846.9 -537.7Q3792.1 -512.7 3762.8 -466.7Q3733.5 -420.7 3733.5 -357V-332Q3733.5 -268 3762.8 -221.5Q3792.1 -174.9 3847 -149.7Q3901.8 -124.6 3977.9 -124.6Q4050.6 -124.6 4102.8 -140.7Q4155 -156.9 4183.6 -189Q4212.1 -221.1 4212.1 -267.3H4377Q4377 -181.7 4328.2 -118.8Q4279.3 -56 4190.6 -22Q4102 12 3981.8 12ZM5298.8 12Q5157.6 12 5062.7 -28.5Q4967.9 -69 4920.5 -148.4Q4873.2 -227.8 4873.2 -344Q4873.2 -514.2 4982.3 -606.7Q5091.4 -699.2 5298.4 -699.2Q5415.3 -699.2 5504.3 -665.2Q5593.4 -631.3 5643.3 -568.3Q5693.3 -505.3 5693.3 -417.5H5524.5Q5524.5 -464.5 5495.7 -496.8Q5466.8 -529.1 5415.5 -545.9Q5364.2 -562.7 5295.2 -562.7Q5218.7 -562.7 5163.9 -537.7Q5109.1 -512.7 5079.8 -466.7Q5050.5 -420.7 5050.5 -357V-332Q5050.5 -268 5079.8 -221.5Q5109.1 -174.9 5164 -149.7Q5218.8 -124.6 5294.9 -124.6Q5367.6 -124.6 5419.8 -140.7Q5472 -156.9 5500.6 -189Q5529.1 -221.1 5529.1 -267.3H5694Q5694 -181.7 5645.2 -118.8Q5596.3 -56 5507.6 -22Q5419 12 5298.8 12ZM5798.5 0 6140.1 -687.2H6333.9L6675.5 0H6487.2L6427.4 -123.9H6035.6L5976 0ZM6098.9 -257.3H6364.1L6291.1 -414Q6286.5 -424.3 6278 -444.1Q6269.5 -463.9 6260.7 -485.2Q6252 -506.5 6244.9 -523.1Q6237.9 -539.7 6236 -543.5H6228.2Q6219.9 -524.2 6209.1 -499Q6198.4 -473.9 6188.5 -450.6Q6178.7 -427.2 6171.9 -413.2ZM6818 0V-687.2H7191.4Q7317.8 -687.2 7408.9 -647.6Q7499.9 -608 7548.7 -531.4Q7597.6 -454.8 7597.6 -343.2Q7597.6 -232.4 7548.7 -155.8Q7499.9 -79.2 7408.9 -39.6Q7317.8 0 7191.4 0ZM6990.7 -136.6H7181.9Q7233.8 -136.6 7277.2 -149.3Q7320.5 -162.1 7352.5 -186.8Q7384.5 -211.4 7402 -247.9Q7419.5 -284.5 7419.5 -332.2V-355.4Q7419.5 -403.2 7402 -439.6Q7384.5 -476 7352.5 -500.7Q7320.5 -525.3 7277.2 -538Q7233.8 -550.7 7181.9 -550.7H6990.7Z';

export function Wordmark({ className }: { className?: string }) {
  return <svg className={className} viewBox={WORDMARK_VIEWBOX} aria-hidden="true" focusable="false"><path fill="currentColor" d={WORDMARK_PATH}/></svg>;
}
