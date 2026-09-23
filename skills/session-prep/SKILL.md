---
name: session-prep
description: Prepare a math study session (PLUS / Supplemental Instruction / recitation) — session plan, verified practice questions, and a .pptx deck built from the leader's own template. Use when the user wants to prep, plan, or make slides for an upcoming study/PLUS/SI session or asks for practice questions for a course week. Linear algebra is verified with panchi; generated problems (RREF, inverses, eigenvalues, span, LU) come with their own checks.
---

# Session prep

Turn "prep next session" into: verified questions → a plan the leader reviews → a deck copied from the leader's template. The leader should only need to review, not re-explain the course.

**Every question has one identity.** It has an `id` and lives in one file, `sessions/<date>/questions.yaml`. The plan, the checks, the deck and the bank all refer to that ID. Never copy a question's text into another file by hand. Edit `questions.yaml` and re-render.

## Running scripts

Scripts live in `scripts/` next to this file and declare their own dependencies, so from any directory:

```
uv run <this-skill-dir>/scripts/<script>.py ...
```

Always use absolute paths for the skill dir, the course folder and the session folder. The working directory resets between shell calls, so never rely on `cd`.

## 0. Check tools, find the course

- Run `uv run <this-skill-dir>/scripts/doctor.py` once per run. If something is missing, tell the user once, with the fallback it prints (e.g. no TeX → math as Unicode text), and carry on.
- Find `course.yaml` in the current directory, then in `courses/*/course.yaml`. If several match, ask which course. If none exists, offer to create one from `examples/course-template/` in the plugin repo and fill in `course.yaml` with the user from their syllabus. Don't proceed without a schedule.

Course folder layout (schemas in `references/course-folder.md`):

```
course.yaml            schedule (weeks, and session dates with their numbers), format, subject, Drive
template.pptx          the leader's slide template (optional)
template-map.yaml      template slide → kind, colours, answer marks, slot layouts (made once, step 3)
notes/  exams/         lecture notes, practice exams
bank/<id>.yaml         question bank (same schema as questions.yaml)
lessons.md             what past sessions taught (maintained by session-feedback)
sessions/YYYY-MM-DD/   questions.yaml, plan.md, verify.py, verify.log, deck.yaml, math/, build.sh,
                       deck.generated.pptx (last build, written only by the skill),
                       deck.pptx (the user's working copy), feedback.md, render/
```

Every run stays in its session folder. Nothing in an older session folder is overwritten except its `feedback.md`.

## 1. Locate the session

```
uv run <this-skill-dir>/scripts/new_session.py <course-dir> [--date YYYY-MM-DD]
```

This prints the week, sections, goals, the **session number** and any notes. It also creates the session folder with an empty `questions.yaml`, `feedback.md` and `build.sh`. It never overwrites anything.

- The session number comes only from `course.yaml` (`schedule[].sessions`). If the output says it's missing or disagrees with `sessions/`, ask the leader **once** and record the answer in `course.yaml`. Never guess it.
- Read `lessons.md` **in full** and follow it. It outranks the defaults in `references/`.
- Read the **2–3 most recent** `sessions/*/feedback.md` and `plan.md`. If the latest past session has no post-session feedback yet, mention once that `session-feedback` can log it.
- **Confidence:** `new_session.py` prints `latest_confidence` when the last session has tallies. If its end mean is ≤ 2.5 or the room was split, say so and propose a fix: a warm-up that revisits the topic for a low room, or a pairing activity (strong students with struggling ones) for a split room.
- Tell the user in one or two lines what you found ("Session 10, week 5: 2.5 LU; last session ended split on row reduction") and continue unless something is off.

## 2. Sync materials (optional)

If `course.yaml` has `drive_folder` and the Google Drive connector is available, pull anything newer than the local copies. Skip silently if there's no connector. Never upload without asking.

## 3. Template

- `template.pptx` present, `template-map.yaml` missing → run `inspect_template.py template.pptx --draft-map template-map.yaml --thumbs <session>/render/template`. The dump lists only shapes that matter, notes, tables, hidden slides and answer marks. The draft proposes kind names, answer `states:`, question/answer `pairs:`, and `slots:` (which kind each question slot uses, how many per slide, and which answer slide follows). Show the user the thumbnail grid and the map, and fix the names with them once. Add the template's accent colours under `colors:` so `{{orange|…}}` markup works.
- Both present → use them. If the user says a template slide changed, re-inspect.
- No template → the plain fallback deck. Mention once that adding `template.pptx` improves results.

## 4. Choose question sources

Ask only if the user didn't say. Mix freely; details in `references/question-sourcing.md`:
- **generated**: `generate.py <session> <name> --count N --difficulty D --set key=value`, for rref, inverse, eigen, span and lu. Built backwards from a nice answer and filtered on panchi's own steps. Ask for them by tag and difficulty ("2 rref, medium, one with a free variable").
- **bank**: `bank.py find <course> --tags ... --slot ...` skips anything used in the last 3 sessions; `bank.py use <session> <id>` copies one in.
- **exams as inspiration**: model style and difficulty on `exams/`, never copy verbatim. Before the plan says a topic is on past exams, confirm it with `search_exams.py "<topic>" --course <course-dir>`.
- **from scratch** and **web research**: cite URLs in `source:`.

## 5. Draft `questions.yaml`

Schema and slot rules in `references/questions.md`. Follow the session structure in `course.yaml` (defaults in `references/session-structure.md`). The format is collaborative: questions should make students reason, not re-lecture.

Think critically: if the week's topics, the requested structure, or a user instruction would make a weak session, say so and propose something better. Don't just comply.

## 6. Verify — nothing ships unverified

```
uv run <this-skill-dir>/scripts/render_questions.py <session>        # plan.md sections, verify.py stubs, deck.yaml
uv run <this-skill-dir>/scripts/verify_runner.py <session>           # writes verify.log
```

`render_questions.py` adds a failing `todo("<id>")` stub to `verify.py` for every hand-written question. Replace each stub with a real check (`references/verification.md`). Generated questions are checked by their generator. The runner **fails** if any check fails, any question has no check, a label names an unknown ID, or a stub is left. Fix every FAIL, in the question or its answer, and rerun. Tell the user what was wrong.

## 7. Checkpoint — show `plan.md`

`plan.md` has your hand-written part at the top: goals, how lessons, feedback and confidence shaped the session, and anything you pushed back on. It also has the generated **Timeline** and **Questions** sections between `boared` markers. Timeline warnings (total ≠ session length ± 5 min) must be resolved or explained.

Show it marked **"all answers verified"** with a link to `verify.log`. Only do this when the runner passed. **Stop and let the user review.** Log every change they ask for in `feedback.md` → Prep review.

## 8. Apply edits, re-verify, build

Apply edits in `questions.yaml` (or `verify.py`), then:

```
bash <session>/build.sh
```

This script was generated with absolute paths. It runs verify → `render_questions.py --only deck` → `build_deck.py` → copies `deck.generated.pptx` → `validate_deck.py` → `render.py`. It stops at the first failure. It refuses to overwrite hand edits in `deck.pptx` unless run with `FORCE=1`; **ask** before forcing. The validator fails if `verify.log` is stale or failed, if `[placeholder]` text is left, if hidden flags are wrong, or if template slides or orphan media remain. Rules for slides and markup are in `references/slide-building.md`. If a build error names a shape, fix the map, don't guess.

If the build warns that text may overflow, shorten the text or give the field a `box`/`font_size` override in `template-map.yaml` slots or `deck.yaml`.

## 9. Deliver

- Look at `render/slide-*.png` if the render step produced them. Then `open <session>/deck.pptx` (macOS; otherwise tell the user the path) and summarise in a few lines: questions, what was verified, anything you pushed back on.
- Fill the **Prep review** section of `feedback.md`: every change the user asked for at the checkpoint and after seeing the deck, in their words where possible, plus pushback and how it resolved. If they ask for more changes later, append them and rebuild.
- Drive: run `deliver.py <session>/deck.pptx --course <course-dir> --options` and offer the routes it lists, best first. **Ask before doing any of them.**
- Offer to promote new verified questions: `bank.py add <session> [--ids ...]`. It only marks them verified if `verify.log` passed and is current.
