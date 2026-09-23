# boared

Claude Code skills for prepping math study sessions (PLUS, Supplemental Instruction, recitations) with **verified** questions and slides built from **your own template**.

Say "prep Thursday's session" and get:

1. **A session plan** built from your course schedule and your notes on how past sessions went, with no re-pasting of the syllabus, lecture notes and exams every week.
2. **Questions that are checked before students see them.** Every answer, T/F counterexample and "possible/impossible" witness is computed with [panchi](https://github.com/Gustavo-Galvao-e-Silva/panchi) in exact arithmetic, or proved symbolically with sympy. A question without a check, or a wrong answer, fails the build.
3. **Generated practice problems** (row reduction, inverses, eigenvalues, span, LU) built backwards from a nice answer, so the arithmetic stays clean. Each one is reproducible from its seed and carries its own checks.
4. **A .pptx deck** made by copying your template's slides and swapping the text: your fonts, colours and layout, with LaTeX-typeset math, answer slides with marks filled in, and answers in the speaker notes.

v1 covers linear algebra. Other subjects can verify with sympy.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- [uv](https://docs.astral.sh/uv/): scripts declare their own dependencies (PEP 723), so there's nothing to install by hand
- Optional: a TeX distribution with `latex` and `dvipng` (math rendering), poppler (`pdftotext`, `pdftoppm`: exam search and previews), LibreOffice or Keynote (slide previews). `doctor.py` reports what's missing and what still works without it.

## Install

As a plugin, from inside Claude Code:

```
/plugin marketplace add Gustavo-Galvao-e-Silva/boared
/plugin install boared@boared
```

The skills are then `boared:session-prep` and `boared:session-feedback`. You can also copy `skills/session-prep/` and `skills/session-feedback/` side by side into your skills folder.

## Set up a course

Copy `examples/course-template/` somewhere private (e.g. `courses/<course>/` in this repo, which is gitignored) and fill in:

```
course.yaml            schedule: weeks → sections, goals, and session dates with their numbers
template.pptx          your slide template (optional, strongly recommended)
notes/  exams/         lecture notes, practice exams
bank/                  your question bank, one YAML file per question
lessons.md             starts empty; filled in by session-feedback
```

The first run inspects `template.pptx`, shows you a thumbnail grid, and asks you once to confirm which slide is the warm-up, the T/F slide, the answer slide with marks, and so on. The answers are saved as `template-map.yaml`.

Course materials stay in your course folder and are never part of this repo.

## Use

From the course folder (or this repo), in Claude Code:

```
prep the next PLUS session
prep 2026-09-30, inverses + IMT, 2 generated rref (one with a free variable), end with a proof hinting at eigenvectors
```

Each session's questions live in one file, `sessions/<date>/questions.yaml`, and each question has an ID. The plan, the checks, the deck and the bank all refer to that ID. The skill:

1. drafts the questions (from the bank, generators, past-exam style, or from scratch);
2. verifies them. `verify_runner.py` fails unless every question has a passing check;
3. stops once for you to review `plan.md`, marked *all answers verified*;
4. builds `sessions/<date>/deck.pptx` with `build.sh` (verify → build → validate → preview) and never overwrites your hand edits.

Edit the deck however you like before presenting.

## It learns from each session

After the session:

```
log feedback for today's session
```

The `session-feedback` skill:
1. diffs the generated deck against the one you actually presented, so your hand edits count as feedback without you writing them down;
2. asks a few quick questions, including the **confidence slips**: an anonymous 1–5 rating of the week's topic at the start and end of the session;
3. updates the course's `lessons.md` (preferences, what these students struggle with, timing), which every future prep reads first. Confidence patterns become lessons only once they repeat;
4. if the feedback shows a problem with the skill itself rather than your course, proposes the fix as a diff for you to approve.

## How it works

```
skills/session-feedback/SKILL.md    post-session debrief → feedback.md + lessons.md
skills/session-prep/
  SKILL.md                          the workflow Claude follows
  references/                       questions.yaml, verification, slides, structure, sourcing, schemas
  scripts/
    doctor.py                       which tools are installed, and the fallback for each
    new_session.py                  locate the session; scaffold questions.yaml, feedback.md, build.sh
    schemas.py                      pydantic models for every YAML file
    generate.py, generators/        rref · inverse · eigen · span · lu, built backwards, filtered on panchi's steps
    bank.py, migrate_bank.py        find / use / add bank questions; convert an old Markdown bank
    search_exams.py                 where a topic appears in past exams (file, page, problem)
    render_questions.py             questions.yaml → plan.md sections, verify.py stubs, deck.yaml
    verify_kit.py, verify_runner.py checks (exact, symbolic, LU without pivoting) and the coverage rule
    render_math.py                  LaTeX → transparent PNG (latex + dvipng)
    build_deck.py                   deck.yaml + template → deck.pptx (text markup, tables, marks, hidden slides)
    validate_deck.py, render.py     post-build checks; PDF/PNG previews via LibreOffice or Keynote
    inspect_template.py             describe a template and draft template-map.yaml
    confidence.py                   confidence-slip summaries and history
    deliver.py                      get the deck into Drive (local copy, reveal, or base64)
    diff_decks.py                   what changed between the generated and the presented deck
```

## Develop

```
uv sync
uv run pytest                 # BOARED_SEEDS=100 for faster generator property tests
uv run ruff check skills tests
```

CI runs both on every push. Please keep the tests green when accepting a skill edit proposed by `session-feedback`.

## License

MIT
