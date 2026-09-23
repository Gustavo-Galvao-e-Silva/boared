# Course folder schemas

## course.yaml

```yaml
course: MATH 1554 — Linear Algebra
term: Fall 2026
subject: linear-algebra        # linear-algebra (panchi-verified); others verify with sympy
session:
  days: [Tue, Thu]             # used to find "the next session"
  length_min: 50
  structure: default           # or a custom list of blocks, see session-structure.md
drive_folder: ""               # optional Google Drive folder URL/id for decks & materials
schedule:
  - week: 6
    start: 2026-09-21          # Monday of the week
    sections: ["2.2 The inverse of a matrix", "2.3 Characterizations of invertible matrices"]
    goals: ["compute inverses by row reduction", "use the IMT to decide invertibility"]
    notes: "Midterm 2 next week"
```

## bank/<slug>.md

```markdown
---
topics: [inverses, imt]
type: tf                        # tf | possible-impossible | word-problem | computation | proof | warmup
difficulty: medium              # easy | medium | hard
answer: "False — A = [[1,0],[0,0]], B = I, C = [[1,0],[0,2]]"
source: "from scratch"          # or exam/file name, or URL
verified: true
last_used: 2026-09-23
---
If AB = AC and A ≠ 0, then B = C.
```

## sessions/YYYY-MM-DD/feedback.md

Filled in three passes: session-prep writes **Prep review**, and session-feedback writes **Edits after generation**, **Post-session**, and **Lessons extracted**.

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

## Lessons extracted
<!-- session-feedback: what was added/changed in lessons.md because of this session -->
- 
```

## lessons.md

Read first by every session-prep run and maintained by session-feedback. Short, imperative, dated and sourced.

```markdown
# Lessons — MATH 1554, Fall 2026

## Preferences
- Keep T/F statements to one line; the leader shortens longer ones. [2026-09-16, 2026-09-23]
- Closing activity: a guided proof with blanks, not an open proof. [2026-09-23]

## Students
- This group rushes to compute before reading the question; add one "don't compute, decide" item per session. [2026-09-09, 2026-09-16]

## Timing
- Word problems take ~15 min here, not 10; plan at most two. [2026-09-23]

## Revisit
- Row-reduction sign errors with negative pivots (week 5). Put one in the next warm-up. [2026-09-23]
```
