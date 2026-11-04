# Magic CAD: Product Vision & UX Spec

Nov 3, 2026 · @Addison

## North star

**From a problem in your hand to a part that fits, with no CAD in between.** The user never sees a sketch, a feature tree or a parameter name. They show the app a problem, choose between outcomes, and get an object that works on the first print.

The promise has three parts, and the product is judged on all three:

- **It fits.** Dimensions come from the real world (camera, reference object, calipers), not from the user typing numbers.
- **It works.** Snap-fits snap, hinges swing, brackets hold. Confidence is earned from real prints, not geometry rules alone.
- **It's yours.** Every part stays parametric and editable. Change the phone, the shelf or the screw size, and the part regenerates.

The one-line pitch: *"Point at the problem. Print the fix."*

What this is not: a prettier CAD program, a chat window bolted onto a 3D viewer, or a mesh generator. Competitors already sell chat-to-parametric models with sliders. The difference here is the closed loop with physical reality, and that loop is the whole product.

## Look and feel

**It should feel like a calm, brilliant workshop partner, not engineering software.** Think the confidence of a camera app crossed with the warmth of a good maker's bench. The object is always the hero; chrome stays out of the way.

### Visual language

- **The object owns the screen.** The 3D part fills 70 to 80% of the view at all times. Controls float over it, translucent, and fade while you rotate.
- **Material, not wireframe.** Parts render as the filament they'll be printed in: matte PETG, slightly glossy PLA, visible layer lines on close zoom. The user should feel they're already holding it.
- **Warm neutral canvas.** A soft off-white workbench in light mode, a deep graphite in dark mode. No blueprint blue, no engineering grids.
- **One accent colour** reserved for "this is the thing that changed" and for the primary action. Everything else is quiet.
- **Type:** one humanist sans, large and generous. Numbers appear only when they matter ("fits a 32 mm pipe"), never as a wall of dimensions.

### Motion and feedback

- **Morph, don't swap.** When a variant or a nudge changes the part, the geometry morphs smoothly from old to new over about 400 ms. The user sees *what* changed.
- **Physical cues.** Snap-fits show a tiny click animation when previewed. A bracket under load shows a subtle flex. Clearances glow briefly where two parts meet.
- **Thinking is visible but calm.** While Claude designs, the part assembles itself feature by feature (base, walls, holes, fillets) rather than a spinner. It doubles as a progress bar and a trust signal.
- **Haptics on mobile** for the moments that matter: capture locked, variant chosen, print sent, "it fit".

### Tone of voice

- Talks about function, never features: "Holds up to about 5 kg" not "6 mm wall, 3 mm fillet".
- Honest about uncertainty: "I'm less sure about this hinge. It's the first one printed on your setup."
- Short. One sentence where a dialog box would normally be.

### Design principles

1. **Show, then ask.** Propose a design first; ask questions only where a wrong guess would cost a print.
2. **Outcomes over parameters.** Every control maps to a result the user cares about.
3. **Reality is the source of truth.** Camera beats typing; a confirmed print beats a passed gate.
4. **Nothing is a dead end.** Every part can be remixed, resized or combined.
5. **Expert mode is one tap away, never in the way.** Parameters, code and gate reports exist for those who want them.

## The flow, screen by screen

**Six moments take a user from problem to proven part, and the last one feeds the first.** Running example: *"I need something to hold my bike pump on the garage wall."*

&#91;embedded content: the core loop · 6 moments\]

The Prove step is the product's moat: its answers flow back into every future design's fit and confidence.

### 1. Capture: "Show me the problem"

The app opens straight to the camera, like a camera app, not a dashboard. A single line of text floats at the bottom: *"Point at what this needs to fit, hold or attach to."*

- **Camera + depth:** the user scans the pump. On phones with depth sensors, the app measures directly; otherwise it asks for a reference object in frame (a credit card, a coin, a printed calibration tag).
- **Live measurement overlay:** key dimensions appear as soft labels on the object as they lock in. A ring around each one fills as confidence rises.
- **Other inputs, same screen:** speak or type ("bike pump, wall mount"), drop a photo, paste a link to the product, or enter caliper readings. Typing is the fallback, not the default.
- **Done state:** a gentle haptic and the captured object turns into a clean grey 3D proxy floating in space.

### 2. Understand: "Here's what I think you need"

The proxy sits on screen with a one-sentence interpretation: *"A wall clip that holds a 38 mm pump barrel, screwed to drywall, easy to pull out one-handed."*

- **At most two or three questions**, each as tappable chips, only where a wrong guess costs a print: "Screws or adhesive?", "Indoor or outdoor?".
- **Assumptions are visible and editable** as small chips under the sentence ("PETG", "your Bambu P1S", "M4 screws"). Tap one to change it.
- The brief card is written silently in the background from all of this. Experts can open it.

### 3. Explore: "Pick the one that feels right"

Three or four variants appear as cards in a horizontal carousel, each a live 3D part already morphing into shape.

- **Each card leads with its trade-off**, not its dimensions: *Minimal · Sturdy · Hidden screws · Fastest print*.
- **Under each:** print time, filament cost and a fit-confidence badge ("High: 41 similar clips worked").
- **Refine by talking or touching:** "a bit wider", or tap a face and drag it. Outcome sliders appear contextually: *stiffer ↔ lighter*, *snug ↔ easy release*. Each slider maps to several parameters underneath.
- **Compare mode:** overlay two variants as ghosts to see exactly what differs.

### 4. Preview in place: "See it in your world"

AR places the chosen part at true scale on the real wall, with the real pump in it.

- **Fit check:** clearances glow green, tight spots amber. Tap to see "1.2 mm clearance, slides in easily".
- **Load check:** a quick tap shows how it behaves with the pump's weight. Simple, visual, no stress plots.
- **Mount guidance:** where the screws go, drawn on the actual wall.
- This is the "holy crap" moment, and the one users screen-record and share.

### 5. Make: "Print it"

One big button. The app already knows the printer, material and slicer profile.

- **Sends directly** to a connected printer, or exports a ready-to-print file. Print-on-demand is offered for users without a printer.
- **Pre-flight in plain language:** "No supports needed. 47 minutes. 12 g of PETG."
- **Live status** from the printer, with a camera snapshot when it finishes.

### 6. Prove: "Did it fit?"

When the print finishes, the app asks one question with three big answers: *Perfect · Too tight · Too loose* (or *Broke*).

- **Optional photo:** snap it installed. This photo becomes the design's thumbnail and its proof.
- **Every answer recalibrates** that user's printer profile and the shared model for that joint type.
- **"Too tight" never ends the flow.** It offers a corrected version immediately: *"Opened the clip 0.3 mm. Reprint?"*
- The part saves to the user's **Shelf** with its proof photo, ready to remix.

## Capabilities

**The product needs nine capabilities in four layers; the moat lives in the reality layer.** Everything above it can be copied; the print-outcome data cannot.

### Perceive: understanding the real world

1. **Measure from camera.** Depth or photogrammetry with a reference object gives key dimensions to roughly ±0.5 mm. That is enough when the design adds compliant clearance.
2. **Recognise known objects.** "That's an iPhone 16 Pro" or "that's a 1-inch PVC pipe" pulls exact manufacturer dimensions from the parts library instead of measuring.
3. **Understand intent.** Turns "hold my pump on the wall" into function, loads, mounting and constraints, asking only what matters.

### Design: generating parts that work

4. **Generate parametric variants.** Several genuinely different designs per request, each built from code, each passing every gate before the user sees it.
5. **Functional features as building blocks.** A verified library of snap-fits, living hinges, press-fits, threads, cable channels and screw bosses, each with calibrated tolerances. Claude composes parts from proven joints instead of inventing them each time.
6. **Composable parts.** Every part declares its mating interfaces (hole patterns, tabs, rails). "Add a hook to this" or "make a lid for that box" just works, across parts and across users.

### Verify: knowing it works before printing

7. **Fit, print and load checks.** Today's gates (dimensions, watertight, overhangs, parameter sweep) plus a real slicer check and lightweight load estimates. Results are shown as plain-language confidence, never as a test report.

### Reality: closing the loop

8. **Printer and material profiles.** Each user's printer, nozzle and filament get a calibrated tolerance profile, built from a one-time test print and refined by every "did it fit?" answer.
9. **Collective print memory.** Every confirmed outcome (fit, too tight, broke) is stored against the joint type, material and printer. Confidence badges are computed from this, and new designs start from what has already worked.

### Around the core

- **Shelf:** a personal library of every part, with its proof photo, its brief and its full history of versions.
- **Remix and share:** fork anyone's proven part and adapt it to your object; the lineage is kept.
- **Kits and catalogs:** one design becomes a family of verified variants (sizes, models, scales) in one request. This is the bridge to selling kits.
- **Expert mode:** open the brief card, the code, the gate report and the parameter sweep for any part.

## Engine room: what already exists underneath

**About half the engine is built; the missing half is perception and the reality loop.** Today's studio pages (Overview, Evals, Library, gates) become an internal mission-control view, not the customer UI.

| Capability | What exists today | What's missing |
| --- | --- | --- |
| Understand intent | Brief card format (YAML: function, dimensions, measurement, ranges) | Writing briefs automatically from conversation and capture |
| Generate variants | Claude + build123d MCP, parametric code, no hard-coded numbers | Several distinct variants per request; trade-off labels |
| Verify fit and print | Five gates: execute, geometry ±0.1 mm, printability, renders, sweep | Real slicer, load estimates, plain-language confidence |
| Functional features | Kernel-pitfalls skill, CAD reviewer, standard-parts lookup | Verified snap-fit, hinge and press-fit library with calibrated tolerances |
| Composable parts | Clearance measurement between parts in the magic-cad MCP | Declared mating interfaces on every part |
| Printer profiles | Print-log skill (prints into clearances) | A tolerance test coupon and a per-printer profile store |
| Collective print memory | Nothing yet | Outcome database: joint type × material × printer × result |
| Measure from camera | Nothing yet | Phone capture with reference object; object recognition |
| Track progress | Eval runner: pass rate and coverage, reported separately | Headline metric switched to fit-first-print rate |

The principle stays the same: **Claude proposes, the harness disposes.** The UI never shows a design that hasn't passed the gates, and never claims confidence it hasn't earned from prints.

## Build sequence

**Build the plainest version of the whole loop first, then make it beautiful.** A polished UI over an unproven loop is the trap to avoid, and it is where the current studio build sits.

&#91;embedded content: build sequence · 4 phases, 3 gates\]

Each phase starts only when the gate above it is met; the magic in phase 3 is worthless until phases 1 and 2 prove parts actually fit.

### The first proof: "make a holder for this"

1. Photograph an object next to a credit card, or enter three caliper readings.
2. Claude writes the brief, generates one holder, and the harness gates it.
3. A plain page shows the part with one button: export for printing.
4. After printing, answer *Perfect · Too tight · Too loose*. The answer adjusts the clearance and is logged.
5. Repeat on five different everyday objects.

**Success:** 3 of 5 fit on the first print, and every miss is fixed on the second.

**Deferred until the gate is met:** AR, the variant carousel, morph animations, accounts and sharing.

The same joint library and printer calibration power the snap-fit car kits, so the first real users can be kit buyers.
