# boardwork

Claude Code skills for prepping math study sessions — PLUS, Supplemental Instruction, recitations — with **verified** questions and slides built from **your own template**.

Say "prep Thursday's session" and get:

1. **A session plan** built from your course schedule and your notes on how past sessions went — no re-pasting the syllabus, lecture notes and exams every week.
2. **Questions that are checked before students see them.** Every answer, T/F counterexample and "possible/impossible" witness is computed with [panchi](https://github.com/Gustavo-Galvao-e-Silva/panchi) in exact arithmetic. A wrong answer fails the build.
3. **A .pptx deck** made by copying your template's slides and swapping the text — your fonts, colors and layout, with math typeset in LaTeX and answers in the speaker notes.

v1 covers linear algebra. Other subjects can verify with sympy; dedicated engines may come later.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- [uv](https://docs.astral.sh/uv/) (scripts run with `uv run --with ...`, no manual installs)
- A TeX distribution with `latex` and `dvipng` (MacTeX, TeX Live) for math rendering

## Install

As a plugin, from inside Claude Code:

```
/plugin marketplace add Gustavo-Galvao-e-Silva/boardwork
/plugin install boardwork@boardwork
```

Or copy `skills/session-prep/` into `~/.claude/skills/`.

## Set up a course

Copy `examples/course-template/` somewhere private (e.g. `courses/<course>/` in this repo — it's gitignored) and fill in:

```
course.yaml            schedule (week → sections → goals), session days, optional Drive folder
template.pptx          your slide template (optional, strongly recommended)
notes/  exams/         lecture notes, practice exams
bank/                  your question bank, one Markdown file per question
lessons.md             starts empty; filled in by session-feedback
```

The first run inspects `template.pptx` and asks you to confirm which slide is the warm-up, T/F, closing, etc. (saved as `template-map.yaml`).

Course materials stay in your course folder and are never part of this repo.

## Use

From the course folder (or this repo), in Claude Code:

```
prep the next PLUS session
prep 2026-09-30, inverses + IMT, use exam 2 for inspiration, end with a proof hinting at eigenvectors
```

The skill stops once for you to review `plan.md`, then verifies, renders, and builds `sessions/<date>/deck.pptx`. Edit that deck however you like before presenting.

## It learns from each session

Every run stays in `sessions/<date>/`: the plan, the verification log, the deck as generated, and your working copy. After the session:

```
log feedback for today's session
```

The `session-feedback` skill:
1. diffs the generated deck against the one you actually presented, so your hand edits count as feedback without you writing them down;
2. asks a few quick questions about how it went;
3. updates the course's `lessons.md` (preferences, what these students struggle with, timing), which every future prep reads first;
4. if the feedback shows a problem with the skill itself rather than your course, proposes the fix as a diff for you to approve.

`feedback.md` in each session folder keeps the full record: your review comments during prep, your edits after generation, the post-session notes, and which lessons came from it.

## How it works

```
skills/session-feedback/
  SKILL.md                   post-session debrief → feedback.md + lessons.md
skills/session-prep/
  SKILL.md                   the workflow Claude follows
  references/                session structure, question sourcing, verification, slide rules, schemas
  scripts/
    inspect_template.py      describe a .pptx and draft template-map.yaml
    render_math.py           LaTeX → transparent PNG (latex + dvipng); panchi row labels shifted to R_1…
    build_deck.py            deck.yaml + template → deck.pptx by copying slides and replacing text
    verify_kit.py            check / check_true / check_close for verify.py
    verify_runner.py         run a session's verify.py, report every failure, exit 1 on any
    diff_decks.py            what changed between the generated and the presented deck
```

## Develop

```
uv sync
uv run pytest
```

## License

MIT
