---
target: "#26 outline, note pin and measure tools"
total_score: 19
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 4
target_identity: "file:/Users/addisonjpratt/Documents/Repositories/CAD-ADE/.claude/worktrees/26-outline-pin-measure-e9bd52/studio-app/src/main.tsx"
target_fingerprint: "sha256:3c0ecafbfa29cbac6e149803d175a0c61f9cff714c01e9fe226b4ce73533d07e"
target_path: /Users/addisonjpratt/Documents/Repositories/CAD-ADE/.claude/worktrees/26-outline-pin-measure-e9bd52/studio-app/src/main.tsx
timestamp: 2026-11-08T18-14-24Z
slug: studio-app-src-main-tsx
---
Method: dual-agent (A: design review sub-agent · B: detector + browser sub-agent)

Target: Studio viewport tools for #26 (lasso catch, note pins, measure), `studio-app/src/main.tsx` and friends, on the stepped_blocks demo project.

## Design Health Score (Assessment A, before fixes)

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | No feedback on pin delete; missed lasso silently returned to orbit |
| 2 | Match System / Real World | 2 | "0 corners", centroid distance between perpendicular faces |
| 3 | User Control and Freedom | 1 | Delete instant with no undo; measuring replaced the selection |
| 4 | Consistency and Standards | 1 | Two note systems and two measure entry points with different glyphs |
| 5 | Error Prevention | 2 | Delete unguarded beside Edit |
| 6 | Recognition Rather Than Recall | 2 | No list of pins; can't see which notes go with a request |
| 7 | Flexibility and Efficiency | 1 | No shortcuts; no keyboard way to place a pin or pick faces |
| 8 | Aesthetic and Minimalist Design | 3 | Restrained markers; invisible dimension line |
| 9 | Error Recovery | 2 | No "try again" path for a missed lasso |
| 10 | Help and Documentation | 3 | Clear tooltips and per-mode hints |
| **Total** | | **19/40** | **Needs work** |

## Design Specificity Verdict
LLM: static visuals on-brief (ink markers, warm graphite, glass rail glyphs, no glowing dots); the interaction layer collided with the existing selection bar and clipped at the stage edge.
Deterministic scan: `impeccable detect` on the changed TSX: 0 findings (exit 0). Live overlay injected: 2 findings, `tiny-text` on the older `.composer-footer small` (now carrying pin-count copy) and `cream-palette` on the established light bench (false positive).

## Priority Issues (before fixes) and what this PR did
- [P0] Pin draft autoFocus scrolled the canvas wrapper and the form overflowed the stage. FIXED: focus({preventScroll}), overflow:clip on the canvas wrapper, draft and card flip to the marker's left near the right edge, draft docks along the stage bottom on phones.
- [P1] Two note systems and two measure entry points. FIXED: the selection bar's "Note" now pins a version note at the selection ("Pin note"); its "Measure" enters the measure tool and uses the rule glyph.
- [P1] Measure output hard to read. FIXED: dimension line in the ink token with end dots; one decimal everywhere; parallel faces read "Gap between parallel faces 13.5 mm", others "Faces at 90.0° · centres 12.9 mm apart".
- [P1] Orange on measure picks; pin hover mixed in accent. FIXED: measure picks highlight in stone while measuring; marker hover is an ink ring. Kept: the measured pair stays the selection after leaving the tool, so the measurement rides with the next request.
- [P1] (B) Pins inside role=img. FIXED: role=img wraps only the canvas; pins, the dimension and the selection bar portal into a sibling overlay.
- [P2] Lasso feedback. FIXED: a loop that catches nothing says so and stays in the tool; the chip omits "0 corners"; the pick belongs to the body the loop caught most of.
- [P2] (B) Focus lost after closing a card or deleting. FIXED: Escape returns focus to the marker; delete shows "Note deleted · Undo" with focus on Undo; saving focuses the pin.
- [P2] (B) Card labelled dialog but acts as disclosure. FIXED: role=group with aria-controls from the marker.
- [P3] (B) 22 px marker, literal font stack, dimension under the pin draft. FIXED: 24 px, var(--font-1), dimension hidden while pinning. Dark theme markers are graphite in a cream ring (A: cream marker on a near-white model).

## Remaining (follow-ups)
- No keyboard path to place a pin on an arbitrary spot or pick faces (selection itself is pointer-only since #25).
- No pin list / per-request opt-out of pins.
- Lasso loop and highlight draw through occluding bodies in iso.
- Clicking Top while drei Bounds' opening fit animates leaves the camera oblique (pre-existing).
- Mobile: long hint overlaps "mm · Z up"; header "Mission Control" clipped (pre-existing).

## Persona Red Flags (A, before fixes)
First-time maker: two "note" concepts, "0 corners", unexplained centroid distances, irreversible delete. Keyboard user: no shortcuts; focus dropped to body. Low-vision: cream marker on light model, invisible measure line.
