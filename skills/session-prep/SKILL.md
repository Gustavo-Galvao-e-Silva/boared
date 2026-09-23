---
name: session-prep
description: Prepare a math study session (PLUS / Supplemental Instruction / recitation) — session plan, verified practice questions, and a .pptx deck built from the leader's own template. Use when the user wants to prep, plan, or make slides for an upcoming study/PLUS/SI session or asks for practice questions for a course week. Linear algebra is verified with panchi.
---

# Session prep

Turn "prep next session" into: a session plan → verified questions → a deck copied from the leader's template. The leader should only need to review, not re-explain the course.

Scripts live in `scripts/` next to this file. Run them with uv so dependencies resolve anywhere:

```
uv run --with panchi --with python-pptx --with pyyaml python <this-skill-dir>/scripts/<script>.py ...
```

## 0. Find the course folder

Look for `course.yaml` in the current directory, then in `courses/*/course.yaml`. If several match, ask which course. If none exists, offer to create one from `examples/course-template/` in the plugin repo and fill `course.yaml` with the user from their syllabus/schedule — do not proceed without a schedule.

Course folder layout (see `references/course-folder.md` for the schemas):

```
course.yaml            schedule, session format, subject, optional Drive folder
template.pptx          the leader's slide template (optional)
template-map.yaml      template slide → kind mapping (generated once, step 3)
notes/  exams/  bank/  lecture notes, practice exams, question bank
lessons.md             what past sessions taught (maintained by the session-feedback skill)
sessions/YYYY-MM-DD/   one folder per session: plan.md, verify.py, verify.log, deck.yaml, math/,
                       deck.generated.pptx (last build, written only by the skill),
                       deck.pptx (the user's working copy), feedback.md
```

Every run is kept in its session folder. Nothing in an older session folder is overwritten except its `feedback.md`.

## 1. Locate the session

- Session date = the user's argument, else the next session date after today.
- From `course.yaml` → `schedule`, take the week containing that date: its sections, goals, and whether an exam is near.
- Read `lessons.md` **in full** and follow it. It is the leader's accumulated preferences and what worked with these students; it outranks the defaults in `references/`.
- Read the **2–3 most recent** `sessions/*/feedback.md` and `plan.md` for recent detail (what students struggled with last time, what to revisit). If the latest past session has no post-session feedback yet, mention once that the `session-feedback` skill can log it.
- Tell the user in one or two lines what you found ("Week 6: 2.2–2.3, inverses + IMT; last time T/F ran long") and continue unless something is off.

## 2. Sync materials (optional)

If `course.yaml` has `drive_folder` and the Google Drive connector is available, list that folder and pull anything newer than the local copies (recent decks into `sessions/`, notes/exams into their folders). Skip silently if no connector. Never upload without asking.

## 3. Template

- `template.pptx` present, `template-map.yaml` missing → run `scripts/inspect_template.py template.pptx --draft-map template-map.yaml`, read the dump, rename entries to kinds (`title`, `warmup`, `word-problem`, `tf`, `possible-impossible`, `closing`, ... whatever the template actually has), keep only the text fields that matter, set `math_area` where a slide has an empty box for math. Show the map to the user and get a one-time confirmation.
- Both present → use them. If the user says a template slide changed, re-inspect.
- No template → plain fallback deck (build_deck.py without `--template`). Mention once that adding `template.pptx` improves results.

## 4. Choose question sources

Ask only if the user didn't say. Options (mix freely) — details in `references/question-sourcing.md`:
- **bank** — `bank/*.md` filtered by the week's topics, skipping anything used in the last 3 sessions.
- **exams as inspiration** — model style/difficulty on `exams/`, never copy verbatim.
- **from scratch** — new problems built around "nice" matrices.
- **web research** — search for problems/applications; cite sources in plan.md.

## 5. Draft `plan.md` — checkpoint

Follow the session structure in `course.yaml` (defaults in `references/session-structure.md`: warm-up → ~40 min main block of word problems, T/F and possible/impossible → challenging closing activity such as completing a proof). The format is collaborative: students reach conclusions themselves; questions should provoke reasoning, not re-lecture.

plan.md contains: timeline with minutes, every question with its **answer and justification**, the slide kind each will use, and what the feedback from past sessions changed. Think critically: if the week's topics, the requested structure, or a user instruction would make a weak session, say so and propose better — don't just comply.

**Stop and let the user review plan.md.** Apply their edits before continuing, and log them (step 9).

## 6. Verify — nothing ships unverified

Write `sessions/<date>/verify.py` per `references/verification.md` and run:

```
uv run --with panchi python <this-skill-dir>/scripts/verify_runner.py sessions/<date>/verify.py
```

Every numeric answer and every T/F / possible-impossible claim gets a check (an exact computation, a witness, or a counterexample). On any FAIL: fix the question or the answer in plan.md, rerun, and tell the user what was wrong. Subjects without an engine yet: verify with sympy and say so.

## 7. Render math

For each matrix/derivation shown on a slide, get LaTeX from panchi (`_repr_latex_()` on Matrix, Vector, and result objects from `rref`, `inverse`, `solve`, `eigen`, `qr_decomposition`) or write it by hand, then:

```
uv run --with panchi python <this-skill-dir>/scripts/render_math.py sessions/<date>/math/q3.png --file - <<'EOF'
<latex>
EOF
```

Row labels are shifted to 1-based (R_1...) automatically. Plots of 2D/3D transformations: `panchi.visualizations.Animator2D/3D` with `save_path`. See `references/slide-building.md` for sizing rules.

## 8. Build the deck

Write `sessions/<date>/deck.yaml` (schema in `scripts/build_deck.py` docstring) and run:

```
uv run --with panchi --with python-pptx --with pyyaml python <this-skill-dir>/scripts/build_deck.py \
  sessions/<date>/deck.yaml --template template.pptx --map template-map.yaml -o sessions/<date>/deck.pptx
```

Only copy template slides and replace text — never invent layouts, colors, or fonts. Put answers in speaker `notes`, not on the slide. If a build error names a shape, re-check the map rather than guessing.

## 9. Deliver

- Copy `deck.pptx` to `deck.generated.pptx` after every build. Only the skill writes that copy, and the user edits `deck.pptx` freely. The `session-feedback` skill diffs the two to see what the user changed by hand. Save the verify_runner output to `verify.log`.
- `open sessions/<date>/deck.pptx` so the user can look it over; summarise in a few lines (questions, what was verified, anything you pushed back on).
- If `drive_folder` is set, **ask** before uploading the deck there.
- Write `sessions/<date>/feedback.md` from the template in `references/course-folder.md`, filling the **Prep review** section now: every change the user asked for at the plan checkpoint and after seeing the deck, in their words where possible, plus anything you pushed back on and how it resolved. These are the most direct signal of their preferences. If they ask for more changes later in the conversation, append them, rebuild, and refresh `deck.generated.pptx`. If `deck.pptx` has hand edits newer than `deck.generated.pptx`, ask before rebuilding over them.
- If bank questions were used, update their `last_used`. Offer to add new verified questions to `bank/`.
