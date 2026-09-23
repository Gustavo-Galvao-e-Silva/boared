---
name: session-feedback
description: Log how a study session went and learn from it — collect the leader's post-session feedback and confidence-slip tallies, diff the generated deck against the one actually presented, and update the course's lessons.md so future session prep improves. Use after a PLUS/SI/recitation session when the user wants to give feedback, debrief, log how it went, or says the session is done.
---

# Session feedback

Close the loop on a session prepared by `session-prep`: capture what happened, turn it into durable lessons, and propose improvements to the skills themselves.

Scripts are in `<this-skill-dir>/../session-prep/scripts/`, called `<scripts>` below. Run them with `uv run <scripts>/<script>.py ...`, always with absolute paths. Course folder layout and file schemas: `<this-skill-dir>/../session-prep/references/course-folder.md`.

## 1. Pick the session

Default: the most recent `sessions/<date>/` on or before today without a filled **Post-session** section in its `feedback.md`. Confirm the date in one line. Read the session's `plan.md`, `questions.yaml`, and the **Prep review** section of `feedback.md` so you know what was planned and what the user already asked to change.

## 2. Find the presented deck

The version shown to students is one of:
- `sessions/<date>/deck.pptx` if the user edited it locally after the build (it differs from `deck.generated.pptx`),
- a copy on Google Drive (`course.yaml` → `drive_folder`), which you download to `sessions/<date>/deck.final.pptx` with the Drive connector,
- a file the user gives you.

Ask if unclear. If the user presented the generated deck unchanged, skip step 3.

## 3. Diff what they changed by hand

```
uv run <scripts>/diff_decks.py sessions/<date>/deck.generated.pptx sessions/<date>/deck.final.pptx
```

Read the diff as feedback the user didn't have to write: reworded questions (tone, length, difficulty), removed slides (too much material, or a format that doesn't work), added slides (something the plan was missing), edited notes. Speaker notes start with question IDs (`1. tf4: …`), so tie each edit to a question in `questions.yaml`. Summarise it in **Edits after generation** as interpretations ("shortened every T/F statement to one line", "cut rref2"), not a raw dump. If the reason for an edit isn't obvious, ask.

## 4. Collect post-session feedback and confidence

Ask briefly, all at once, and accept whatever the user gives. Don't interrogate:
- Attendance, and roughly how long each block took compared with the plan
- What worked, and what fell flat or confused people
- Where students struggled (these seed the next warm-up)
- Anything to do differently next time
- **The confidence slips**: the topic asked, and how many students wrote 1, 2, 3, 4 and 5 at the **start** and at the **end** (e.g. "start 0 2 5 3 1, end 3 1 0 1 4")

Write the answers into **Post-session** in the user's words. For the tallies, run:

```
uv run <scripts>/confidence.py summary --start 0,2,5,3,1 --end 3,1,0,1,4 --topic "LU factorization"
```

Paste its output over the **Confidence** section. It gives the mean start, mean end, the shift, and whether the end distribution is **split** (1–2 and 4–5 each hold at least a quarter of the answers). Say in one line how the shift compares with the user's own read of the session. When they disagree, that's the useful signal.

If there were no slips this time, leave the section blank and don't ask again.

## 5. Update `lessons.md`

`lessons.md` in the course folder is what `session-prep` reads first on every run, so keep it short, current and actionable. From this session's Prep review, Edits after generation, Post-session and Confidence sections:

- Add a lesson only if it should change a future session. Write it as an instruction ("Keep T/F statements to one line; the leader shortens longer ones"), dated and sourced (`[2026-09-23]`).
- **Confidence lessons need a pattern.** Add one only when the same pattern shows up in at least 2 sessions: run `confidence.py history <course>` and look (e.g. "LU sessions end low; add a revisit warm-up" after two low LU sessions). One low session is not a lesson.
- **Strengthen, don't duplicate.** If an existing lesson is confirmed again, update its date and add the source. Two or more sources means the lesson is well established.
- **Replace contradicted lessons** instead of keeping both. Mention the change to the user.
- One-off events ("fire drill cut the session short") are not lessons.
- Keep "Students" lessons (misconceptions, what this group finds hard) separate from "Preferences" (how the leader likes material). Move topic-specific struggles to "Revisit" with the topic, and remove them once revisited.
- Keep the whole file under about 60 lines. Merge or drop the weakest lessons when it grows.

Show the user the lesson changes as a short before/after list. Apply them directly: this file is private to the course and meant to evolve.

## 6. Review the confidence experiment (after 4–6 sessions with tallies)

When `confidence.py history <course>` shows 4 or more sessions and `lessons.md` has no `Confidence review:` line yet, walk through the review with the user once. Confidence slips are worth keeping, and possibly extending to per-question data, if at least one of these holds:
1. The tallies changed a session plan at least once (look for plans that cite confidence).
2. The shift sometimes disagreed with the leader's own read of a session.
3. Low-confidence topics line up with topics students missed on the midterm (ask the leader).

Record the outcome as one line under Preferences: `Confidence review: keep, …` or `Confidence review: drop, …`, dated. If none of the criteria hold, suggest dropping the slips and trying another signal (e.g. timing). If they hold, mention that per-question confidence is the next step in the plugin's roadmap.

## 7. Propose skill improvements (never apply silently)

Some feedback isn't about this course. It shows the skill itself is wrong or unclear: a script bug, a default that is bad for any course, an instruction Claude misread, a slide rule that keeps getting hand-fixed. For those:
- Say what's wrong and which file it's in (`session-prep/SKILL.md`, a `references/` file, or a script).
- Show the proposed edit as a diff.
- Apply it only if the user approves, and run the tests (`uv run pytest` in the plugin repo) before calling it done. These files are shared by everyone who installs the plugin. Course-specific preferences stay in `lessons.md`.

If nothing generic came up, skip this step without comment.

## 8. Wrap up

Offer to save questions that worked well, especially hand-improved ones, to the bank: `uv run <scripts>/bank.py add <session> --ids tf4,pi2`. Copy the leader's improved wording into `questions.yaml` first, then re-verify so they land as `verified: true`. End with one line on what the next prep will do differently.
