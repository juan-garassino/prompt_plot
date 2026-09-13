# Design Studio Rubric — the bar every collection piece must pass

Two-role adversarial loop: a DESIGNER (edits generator code/params, renders) and a
CRITIC (sees ONLY the rendered png, fresh eyes). A piece ships when the critic
scores **avg ≥ 8/10 with no dimension below 7** (all seven dimensions; a declared-flat piece is scored on how well the flatness serves it), over at most 5 rounds.

## The six dimensions (1–10 each)

1. **Hierarchy** — one element dominates at 3 meters; a clear second and third read
   at 1 meter; details reward 30 cm. If everything is mid-sized, score ≤ 4.
2. **Grid & alignment** — type, furniture and subject share axes/edges. Nothing
   floats "roughly in a corner". Margins are exact and consistent.
3. **Tension & asymmetry** — off-center balance, working diagonals, elements that
   crop at the frame or overlap with intent. Centered-symmetric = student work, ≤ 4.
4. **Negative space** — emptiness is shaped, not leftover. At least one generous
   quiet zone that makes the dense zone read louder.
5. **Craft for pen** — line weight built from 1–3 passes with purpose; fills solid
   without flooding; no muddy ink-on-ink collisions; density plottable (≥0.8 mm
   spacing); ≤ 3–4 pen swaps.
6. **Concept legibility** — the physics/ML idea lands in one glance without reading
   the caption. The caption confirms, never explains.
7. **Depth & dimensionality** — the default is NOT flat: use occlusion/overlap,
   projected 3D forms (spheres, tubes, perspective), line-weight or dash-density
   falling off with distance, tone gradients that turn planes into volumes.
   Flatness is permitted ONLY as a conscious, declared decision — either the
   assigned style canon is flat by nature (Swiss, Pop Ben-Day, classic Bauhaus)
   and the designer says so in the report, or the concept demands it. Undeclared
   flatness scores ≤ 4.

## Known failure modes of this codebase (critic: check these first)

- Subject floating dead-center with even margins on all sides.
- Furniture checklist: swatch bar + plus marks + footer placed in corners without
  a shared grid line.
- All elements at similar scale (no dominant mass).
- Colors used as mere categories instead of compositional weights (the accent pen
  should be scarce and loud).
- Type blocks colliding with, or ignoring, the subject's geometry.
- Elements politely avoiding each other — masters overlap.

## Designer's obligations per round

- Address every mandatory change from the critic, or argue (in the report) why not.
- Move whole compositions, not just parameters: reposition, rescale, crop at the
  frame, merge/delete furniture. Rewrite layout code freely.
- Keep: seeded determinism, margins, paper safety, tests green.

## Critic's obligations per round

- Judge ONLY the png (no code reading), against this rubric plus the piece brief.
- Score all six dimensions, name the single biggest weakness, give exactly 3
  mandatory changes (concrete, visual — "move the type block onto the bar's left
  edge", not "improve balance").
- PASS/FAIL verdict. No politeness. A pass means it could hang in a gallery.
