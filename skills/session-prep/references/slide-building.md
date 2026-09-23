# Slide building

The leader's rule: **don't waste time on new slide designs. Reuse what's in the template and just edit the text.** build_deck.py enforces this: every output slide is a copy of a template slide, and every format (colour, bold, mark fill, table font) is copied from something already in the template.

## deck.yaml is generated

`render_questions.py` writes `deck.yaml` from `questions.yaml` and the map's `slots:`. It adds a title slide (if the map has a `title` kind), then for each run of same-slot questions:
- one slide per `per_slide` questions, statements numbered into the slot's text `field` or one row each into its `table`;
- if the slot names `answers:`, an answer slide right after, hidden by default, with the same statements and the `answer_state` marks set: filled for True/Possible, or the right letters highlighted for multiple choice;
- answers and justifications in speaker notes as `1. tf4: False — …`;
- the question's `latex:` rendered to `math/<id>.png` and fitted into the kind's `math_area`.

Don't hand-edit `deck.yaml`; it's overwritten. Change `questions.yaml` or the map. For a one-off slide, add a slot layout or use `from_slide` in a hand-kept deck.

## template-map.yaml

```yaml
colors: {orange: "E87722", navy: "1F2A44"}   # names usable in {{orange|…}} markup
kinds:
  tf:
    slide: 4
    fields: {title: "Title 1"}
    tables: {statements: "Table 3"}
  tf-answers:
    slide: 5
    hidden: true
    fields: {title: "Title 1"}
    tables: {statements: "Table 3"}
    states:
      mark:
        cells: ["Oval 12", "Oval 14", "Oval 16", "Oval 18"]   # one per row
        on:  "Oval 12"      # formatting source for a filled mark
        off: "Oval 14"      # formatting source for an empty mark
  warmup-mcq-answer:
    slide: 3
    states:
      choice:
        cells: {A: "Oval 5", B: "Oval 6", C: "Oval 7", D: "Oval 8"}
        on:  {shape: "Oval 5", text_color: orange, bold: true}
        off: "Oval 6"
pairs: [[tf, tf-answers]]
slots:
  tf: {kind: tf, per_slide: 4, table: statements, field: null, answers: tf-answers, answer_state: mark}
  pi: {kind: possible-impossible, per_slide: 3}
  problem: {kind: word-problem, per_slide: 1, title: "Problem {n}", numbered: false}
```

A state copies the exemplar's fill, outline, theme style and text formatting onto each cell, so cells that start with no fill work too. Cells beyond the number of questions are removed.

## Text

- Multi-line values become one paragraph per line, each cloned from the corresponding template paragraph (bullets, size, colour).
- `**bold**` and `{{colour|text}}` work in any text field and table cell, and nest (`**{{orange|key}}**`). Colours come from `colors:` or a 6-digit hex. The builder never invents a colour.
- Fields you don't set keep the template's text. `validate_deck.py` fails on leftover `[bracket]` placeholders.
- Per-field overrides when the template box doesn't fit: `text: {body: {text: "…", box: [l, t, w, h], anchor: t, font_size: 20, line_spacing: 1.1}}`.
- Tables: every data row copies the template's first data row, since header rows often use another font. Header rows are kept.

## Math on slides

- Short inline math in text is fine as Unicode: A⁻¹, Ax = b, det(A) ≠ 0, ℝ³, λ.
- Matrices, derivations and systems go in `latex:` on the question, or through render_math.py by hand.
- An image fills the slide's `math_area` (or the given `area`/`box`), keeping its aspect ratio. One image per slide from render_questions. Several questions with math on one slide means `per_slide: 1` for that slot, or combine them into one LaTeX expression.
- Long RREF chains render tiny. Show at most ~3 steps, or only `A \sim \dots \sim \text{RREF}`, and leave the steps to the students.
- For questions students solve, show the *problem*, not panchi's derivation. The derivation belongs in notes or on an answer slide.

## Checks before delivering

`build.sh` runs these; read their output:
- **Build warnings**: estimated text overflow per shape, and images overlapping text. Fix with shorter text or a field override.
- **validate_deck.py**: hidden flags match the spec, no `[placeholder]` text, every image present, no template-original slides, no orphan media, `verify.log` current.
- **render.py**: PNG per slide in `render/` (LibreOffice, or Keynote on macOS). Look at them for overflow and tiny math. With no renderer, open the deck instead.

The `pptx` skill, if installed, may be used as an extra check, never as a required step.
