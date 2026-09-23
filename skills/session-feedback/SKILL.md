---
name: session-feedback
description: Log how a study session went and learn from it — collect the leader's post-session feedback, diff the generated deck against the one actually presented, and update the course's lessons.md so future session prep improves. Use after a PLUS/SI/recitation session when the user wants to give feedback, debrief, log how it went, or says the session is done.
---

# Session feedback

Close the loop on a session prepared by `session-prep`: capture what happened, turn it into durable lessons, and propose improvements to the skills themselves. Scripts are in `../session-prep/scripts/` (relative to this file). Run them with `uv run --with python-pptx python ...`.

Course folder layout and file schemas: `../session-prep/references/course-folder.md`.

## 1. Pick the session

Default: the most recent `sessions/<date>/` on or before today without a filled **Post-session** section in its `feedback.md`. Confirm the date in one line. Read the session's `plan.md` and the **Prep review** section of `feedback.md` so you know what was planned and what the user already asked to change.

## 2. Find the presented deck

The version shown to students is one of:
- `sessions/<date>/deck.pptx` if the user edited it locally after the build (newer than `deck.generated.pptx`),
- a copy on Google Drive (`course.yaml` → `drive_folder`), which you download to `sessions/<date>/deck.final.pptx` with the Drive connector,
- a file the user gives you.

Ask if unclear. If the user presented the generated deck unchanged, skip step 3.

## 3. Diff what they changed by hand

```
uv run --with python-pptx python <skills-dir>/session-prep/scripts/diff_decks.py \
  sessions/<date>/deck.generated.pptx sessions/<date>/deck.final.pptx
```

Read the diff as feedback the user didn't have to write: reworded questions (tone, length, difficulty), removed slides (too much material, or a format that doesn't work), added slides (something the plan was missing), edited notes. Summarise it in **Edits after generation** in `feedback.md` as interpretations ("shortened every T/F statement to one line", "cut the second word problem"), not a raw dump. If the reason for an edit isn't obvious, ask.

## 4. Collect post-session feedback

Ask briefly, all at once, and accept whatever the user gives. Don't interrogate:
- Attendance, and roughly how long each block took compared with the plan
- What worked, and what fell flat or confused people
- Where students struggled (these seed the next warm-up)
- Anything to do differently next time

Write the answers into the **Post-session** section of `feedback.md` in the user's words.

## 5. Update `lessons.md`

`lessons.md` in the course folder is what `session-prep` reads first on every run, so keep it short, current and actionable. From this session's Prep review, Edits after generation, and Post-session sections:

- Add a lesson only if it should change a future session. Write it as an instruction ("Keep T/F statements to one line; the leader shortens longer ones"), dated and sourced (`[2026-09-23]`).
- **Strengthen, don't duplicate.** If an existing lesson is confirmed again, update its date and add the source. Two or more sources means the lesson is well established.
- **Replace contradicted lessons** instead of keeping both. Mention the change to the user.
- One-off events ("fire drill cut the session short") are not lessons.
- Keep "Students" lessons (misconceptions, what this group finds hard) separate from "Preferences" (how the leader likes material). Move topic-specific struggles to "Revisit" with the topic, and remove them once revisited.
- Keep the whole file under about 60 lines. Merge or drop the weakest lessons when it grows.

Show the user the lesson changes as a short before/after list. Apply them directly: this file is private to the course and meant to evolve.

## 6. Propose skill improvements (never apply silently)

Some feedback isn't about this course. It shows the skill itself is wrong or unclear: a script bug, a default that is bad for any course, an instruction Claude misread, a slide rule that keeps getting hand-fixed. For those:
- Say what's wrong and which file it's in (`session-prep/SKILL.md`, a `references/` file, or a script).
- Show the proposed edit as a diff.
- Apply it only if the user approves. These files are shared by everyone who installs the plugin, so course-specific preferences stay in `lessons.md`.

If nothing generic came up, skip this step without comment.

## 7. Wrap up

Mark the questions used in `bank/` with `last_used` if session-prep didn't. Offer to save any question that worked well, and was hand-improved, back to `bank/` with `verified: true`. End with one line on what the next prep will do differently.
