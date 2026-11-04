---
name: magic-cad-reviewer
description: "The Magic CAD design-critique gate: judge a finished design the way Impeccable's critique judges a UI, so a harness PASS is never mistaken for good design. Use after any design passes the harness gates, before calling it done, and whenever reviewing, adopting, or comparing candidate designs. Produces a scored verdict with named slop tells and required fixes."
---

# CAD Reviewer — the design verdict gate

The harness proves a design *executes, measures, and prints*. It says nothing about
whether the design is *good*. This skill is the verdict layer, modelled on Impeccable's
critique: scored dimensions, named failure patterns, and a refusal to pass slop.

## When this runs

After `magic.py check` passes, before the design is presented as finished, adopted, or
rolled out to other parts. A design without a reviewer verdict is *unreviewed*, and must
be labelled that way.

## Score these five dimensions (0–4 each, 20 max)

1. **Looks like the thing.** If printed life-size, would it read as the real object —
   structurally and component-wise? Closed paneled forms where the real thing is closed;
   the features a person names first (glass, lights, handles, seams) actually present.
2. **Detail with a reason.** Every detail traces to the brief, the real object, or a
   function. Detail that exists because a default produced it scores zero.
3. **Dimension honesty.** Round numbers are fine *when chosen*. A dimension nobody chose
   (left at a library default, a tutorial value, 3.00 mm because 3 is pretty) is a tell.
   List any dimension you cannot justify in one clause.
4. **Proportion and stance.** Overall proportions vs the brief's intent; no accidental
   toy-like chunkiness, no feature scaled by convenience.
5. **Print-intent coherence.** Orientation is a decision, not an accident: overhang
   strategy, layer direction vs load path, and bed contact are all deliberate and stated.

**Verdict bands:** 17–20 adopt-ready · 13–16 direction approved, refinements named ·
9–12 rework before adoption · ≤8 reject and redesign.

## Slop tells (name them when you see them)

- Default-everything fillets: same radius everywhere, applied because filleting is easy.
- Frame-with-a-shell: open structure dressed up as a closed object.
- Detail-free surfaces on a part whose real counterpart has seams, panels, or texture.
- Library features used unchecked (a boss, hole, or snap whose numbers were never read).
- Renders offered as evidence that the *design* is good — a render shows surfaces, not
  decisions. (And flat QA previews are never product visuals.)
- Symmetry nobody asked for; asymmetry nobody can explain.
- "It passed all gates" offered as a quality claim.

## Output format

```
VERDICT: <band> — <score>/20
Scores: looks-like-the-thing n · detail n · dimensions n · proportion n · print-intent n
Tells found: <named tells, or "none">
Required before adoption: <short list, or "nothing">
What's genuinely good: <one line, specific>
```

## Rules

- Judge against the *brief*, not your taste. Where the brief pins a requirement, the
  brief wins over every tell above.
- Be specific: cite the feature and the dimension, not vibes.
- A high harness score never raises a reviewer score. A low reviewer score blocks
  "done" language even when every gate is green.
- If you cannot see enough to judge a dimension (no render, no section), score it 0 and
  say what you need — do not guess upward.
