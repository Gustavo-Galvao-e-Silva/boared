# Slide building

The leader's rule: **don't waste time on new slide designs — reuse what's in the template, just edit the text.** build_deck.py enforces this: every output slide is a copy of a template slide.

## deck.yaml

- One entry per slide, in order. Use `kind` (from template-map.yaml) whenever possible; `from_slide: N` copies template slide N directly when no kind fits.
- `text` keys are field names from the map (or shape names / ids with `from_slide`). Multi-line values become one paragraph per line with the template's formatting (bullets, size, color) cloned from the corresponding template paragraph.
- Fields you don't set keep the template's placeholder text — set or blank (`""`) every field that shouldn't show template text.
- `notes` = speaker notes: answers, justifications, hints, timing.

## Math on slides

- Short inline math in text is fine as plain Unicode: A⁻¹, Ax = b, det(A) ≠ 0, ℝ³, λ.
- Matrices, derivations, systems → render to PNG with render_math.py and place via `images`.
- An image fills the slide's `math_area` (or the given `area`/`box`) keeping aspect ratio. One image per area; for two side-by-side matrices, either render them in one LaTeX expression (`A = ..., \quad B = ...`) or give explicit `box`es.
- Long RREF chains render tiny. Show at most ~3 steps per slide, or show only the start and the result (`A \sim \dots \sim \text{RREF}`), and leave the steps to the students.
- For questions students solve, show the *problem*, not panchi's worked derivation — the derivation belongs in notes or on an answer slide shown after discussion.

## Checks before delivering

- Build errors name the deck slide and the missing shape — fix the map or deck.yaml, don't work around it.
- Open the deck (`open deck.pptx`) and skim: leftover template text, overflowing text boxes, unreadably small math.
