# Course folder schemas

Every file here is validated by `scripts/schemas.py` when a script loads it.

## course.yaml

```yaml
course: MATH 1554 — Linear Algebra
term: Fall 2026
subject: linear-algebra        # linear-algebra (panchi-verified); others verify with sympy
session:
  days: [Tue, Thu]             # used to find "the next session" when no dates are listed
  length_min: 50               # the plan's Timeline must total this ± 5 min
  structure: default           # or a custom list of blocks, see session-structure.md
drive_folder: ""               # optional Google Drive folder URL/id (for "reveal" delivery and syncing)
drive_local: ""                # optional local path of that folder, synced by Drive for desktop ("copy" delivery)
schedule:
  - week: 5
    start: 2026-09-21          # Monday of the week
    sections: ["2.5 Matrix factorizations"]
    goals: ["compute an LU factorization", "use LU to solve Ax = b"]
    notes: "Midterm 2 next week"
    sessions:                  # the session number shown on slides. Never inferred
      - {date: 2026-09-22, number: 9}
      - {date: 2026-09-24, number: 10}
```

The session number is always read from `sessions:`. If a date is missing, or the numbers disagree with the folders in `sessions/`, the skill asks once and writes the answer here.

## sessions/YYYY-MM-DD/questions.yaml

The session's questions: see `questions.md`.

## bank/<id>.yaml

The same schema as a `questions.yaml` entry, plus bank bookkeeping. Reusing a bank question or promoting a session question is a copy (`scripts/bank.py`).

```yaml
id: tf-cancellation
slot: tf
tags: [matrix-multiplication, inverses]
statement: "If AB = AC and A ≠ 0, then B = C."
answer: false
justification: "A = [[1,0],[0,0]], B = I, C = [[1,0],[0,2]] gives AB = AC with B ≠ C. True if A is invertible."
source: from scratch
difficulty: medium
verified: true                  # set by `bank.py add` only when the session's verify.log passed and was current
last_used: 2026-09-23
times_used: 1
```

An old Markdown bank (`bank/*.md` with front matter) is converted once with `scripts/migrate_bank.py <course-dir>`.

## template-map.yaml

Kinds, colours, answer-mark states, question/answer pairs and slot layouts: see `slide-building.md`. Drafted by `inspect_template.py --draft-map` and confirmed with the leader once.

## sessions/YYYY-MM-DD/feedback.md

Written by `new_session.py`, then filled in over three passes. session-prep writes **Prep review**. session-feedback writes **Edits after generation**, **Post-session**, **Confidence** and **Lessons extracted**.

```markdown
# Feedback — YYYY-MM-DD

## Prep review
<!-- session-prep: changes the leader asked for at the plan checkpoint and after seeing the deck; pushback and how it resolved -->
-

## Edits after generation
<!-- session-feedback: interpreted diff of deck.generated.pptx vs the presented deck -->
-

## Post-session
Attendance:
Timing vs plan:
What worked:
What fell flat / confused people:
Where students struggled:
For next time:

## Confidence
Topic asked:
Start: 1×_ 2×_ 3×_ 4×_ 5×_   (n = _)
End:   1×_ 2×_ 3×_ 4×_ 5×_   (n = _)

## Lessons extracted
<!-- session-feedback: what was added/changed in lessons.md because of this session -->
-
```

The Confidence section holds the paper-slip tallies: how many students answered 1, 2, 3, 4 and 5. `scripts/confidence.py summary` writes the section, adding a line with the mean start, mean end, shift, and whether the room was split. `confidence.py history <course>` reads every session's section back.

## lessons.md

Read first by every session-prep run and maintained by session-feedback. Short, imperative, dated and sourced. `new_session.py` seeds its header from `course.yaml` on first use.

```markdown
# Lessons — MATH 1554, Fall 2026

## Preferences
- Keep T/F statements to one line; the leader shortens longer ones. [2026-09-16, 2026-09-23]
- Closing activity: a guided proof with blanks, not an open proof. [2026-09-23]

## Students
- This group rushes to compute before reading the question; add one "don't compute, decide" item per session. [2026-09-09, 2026-09-16]
- LU sessions end with low confidence; open the next session with an LU warm-up. [2026-09-24, 2026-10-01]

## Timing
- Word problems take ~15 min here, not 10; plan at most two. [2026-09-23]

## Revisit
- Row-reduction sign errors with negative pivots (week 5). Put one in the next warm-up. [2026-09-23]
```
