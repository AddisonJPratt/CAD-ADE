# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
FDM makers without CAD skills, working locally on their own computer next to their printer
(owner's printer: Elegoo Centauri Carbon 2, PLA first, then PETG). Their job is to get a part
that fits and prints, by describing what they want and approving changes, not by modelling.
Engineering detail (checks, parameters, code, evidence) must stay one tap away for when they,
or an expert, want to look.

## Product Purpose
Magic CAD turns a conversation into verified, printable parametric parts. Parametric build123d
code is the source of truth; edits happen through the agent and through bounded parameters.
Success is a part the harness has checked and the user has accepted, with honest labels for
what is computed, slicer-checked, or still needs a physical test.

## Positioning
The agent never just edits geometry: every change is previewed as a before/after diff, accepted
by the user, then re-checked by the harness gates and saved as a version. A harness pass is never
presented as a design review or a print.

## Operating Context
- One app with three modes: Make (Ask, Make, Prove, Shelf), Studio (3D model plus the agent), and
  Mission Control (the expert view).
- Runs locally with no account. The agent runs through an adapter; Claude Code (the user's own
  login) comes first, and a scripted agent backs tests.
- Versions are git commits underneath, shown as a timeline.
- Agent activity streams live and can be interrupted.

## Capabilities and Constraints
- Units are millimetres, Z up. FDM only, plus STEP export.
- Verdicts use three tiers: computed, slicer-checked, needs physical test. A recorded print
  upgrades a claim.
- Never send a print job; printer actions always need the user's confirmation.
- No weapon or firearm components; original designs only.
- Every exposed control must operate a supported function. Assembly, motion, selection tools and
  sketching are roadmap capabilities and must not appear as working tools until they exist.
- Undecided: the selection tools (part, surface, lasso, note pin, measure) are planned but not built.

## Evidence on Hand
- Real test fixtures: `tests/fixtures/good_two_parts.py` (two blocks) and the curved cable-clip
  proposal used in Playwright. These prove interactions; they are not finished product visuals.
- No testimonials, customers, or print photos exist yet; do not fabricate them.

## Product Principles
1. The agent is the main way in; it does the work and explains it in plain language.
2. Show the verdict and the next step first; evidence on demand.
3. Never let a check pass read as a design review or a print.
4. The user approves every change before it lands.
5. Nothing on screen pretends to work.
