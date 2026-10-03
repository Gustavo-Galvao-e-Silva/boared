# Changelog

All notable changes to boared. Versions follow `.claude-plugin/plugin.json`. Bump it with every change.

## 0.4.0 — 2026-10-02

### Kahoot export (optional)
- `kahoot.py payload <session>` turns the verified questions into arguments for the Kahoot MCP's `create_or_update_kahoot`: `tf` → True/False, `pi` → Possible/Impossible, `choices` → quiz with the correct letter(s) marked. Markup is removed and Kahoot's limits are checked (120 characters per question, 75 per choice, 6 choices). It refuses a stale or failed `verify.log`, and lists every skipped question with the reason.
- An optional per-question `kahoot:` block: a short plain-text `question` (needed when the math is in `latex:`/`image:`), shorter `choices`, `time`, or `include: false`. A question with the block must export.
- `kahoot.py record` writes `sessions/<date>/kahoot.yaml` (uuid, editor link, question ids), so a re-export replaces the same Kahoot. Bank entries gain `kahoot_uses`, set by `bank.py add` and counted by `record` for `bank:` questions. `bank.py find --kahoot` lists entries that export as they are.
- `course.yaml` gains `kahoot: {folder, language}`. An empty `folder` saves to the account's default workspace: Kahoot refused a workspace id from `get_workspaces` as a `folderId`. session-prep step 10 asks before creating a Kahoot.

### Ready for Anthropic's plugin directory
- Logo (`boared.png`), and `displayName`, `homepage`, `repository`, `documentationUrl`, `supportUrl` and `icon` in `plugin.json`. The marketplace has a description. `claude plugin validate --strict` passes.
- The README says what the plugin runs, sends and fetches, and how to install it from the directory. Course folders live outside the plugin: the empty `courses/` placeholder is gone.
- session-feedback proposes skill fixes as a GitHub issue when running from an installed copy, where edits would be lost on update.

## 0.3.0 — 2026-10-01

### Questions must be teachable on the day
- Every question needs `section`, `uses`, `tags`, `answer`, a non-empty `justification`, `difficulty`, `minutes` and `source`. There are no defaults, and an error names the question and the field.
- `verify_runner.py` runs a schedule check. A question fails when a topic in `uses` is first taught after the session, when a `uses` label isn't in the schedule, or when its text contains a word that `course.yaml` `prerequisites:` ties to a later topic. `preview: true` turns a too-early topic into a `PREVIEW:` warning, and `plan.md` asks the leader to approve it.
- Topics are the course's own `sections` labels (full label or an unambiguous prefix). boared ships no topic or keyword map: `prerequisites:` lives in each course's `course.yaml`.
- `generate.py` fills `section`/`uses` from the session's topic, or from `--section`/`--uses`.
- `migrate_bank.py --fill-required` upgrades a course's bank and session files. It fills honest defaults and takes `uses` from the schedule, and lists whatever it can't fill. `bank.py find` skips incomplete entries with a warning.
- session-feedback proposes a `prerequisites:` entry when feedback says students hadn't learned something yet.

### Course schema (upstreams the local patch 0001)
- `schedule[].sessions[]`: `number` is optional (the leader is asked), plus `day`, `sections` and `goals` per session. Added `Course.session_for(date)` and `Course.sections_for(date)`, where a session's own topics override its week's.
- `final_exam` (free text) and `exams: [{name, date}]`.

## 0.2.0 — 2026-09-23

Changes from the first full run (MATH 1554, week 5, §2.5 LU).

### Questions have one identity
- `sessions/<date>/questions.yaml` is the single source for a session's questions. `render_questions.py` generates the plan's Timeline and Questions sections, `verify.py` stubs, and `deck.yaml` from it.
- `verify_runner.py` enforces coverage: it fails if a question has no check, a check label names an unknown ID, or a `todo()` stub is left. It writes `verify.log` stamped with file hashes, and `validate_deck.py` and `bank.py add` refuse a stale or failed log.
- The bank uses the same schema: `bank/<id>.yaml` with `verified`, `last_used` and `times_used`. `bank.py find|use|add` replaces manual copying. `migrate_bank.py` converts the old Markdown bank.
- `schemas.py` (pydantic) validates course.yaml, questions.yaml, bank entries, deck.yaml and template-map.yaml, with errors that name the question.

### Generators
- `generate.py` plus `generators/`: rref, inverse, eigen (distinct, repeated, defective, complex), span and lu. Each is built backwards from a nice answer, filtered by replaying panchi's own row operations (fractions, entry size, step count, degeneracy), reproducible from its seed, and checked from its stored data.
- `verify_kit`: `lu_no_pivot` (Doolittle LU, no row swaps; uses `panchi.lu(A, pivoting="none")` when available), sympy helpers (`check_identity`, `sym_matrix`, `unit_lower`, `upper`), `steps_text`, and `todo`.

### Builder and QA
- Hidden template slides stay hidden when copied, and `hidden:` can override that per slide.
- Rich text in any field or table cell: `**bold**` and `{{colour|text}}`, with colours from the map's `colors:`.
- Tables (data rows copy the first data row's font), per-field geometry overrides (`box`, `anchor`, `font_size`, `line_spacing`), and a text-overflow and image-overlap warning.
- Answer marks and multiple-choice highlights as generic `states:`, which copy exemplar shapes' formatting, including cells that start with no fill.
- `validate_deck.py`: placeholders, hidden flags, images, leftover template slides, orphan media, verification status. `render.py`: PDF and PNG previews via LibreOffice, or Keynote on macOS.
- `inspect_template.py`: compact dump (only shapes that matter), notes, tables, hidden flags, question/answer pair detection, a draft of `states:` and `slots:`, and a `--thumbs` grid.

### Sessions and feedback
- `course.yaml` schedule entries list `sessions: [{date, number}]`. Session numbers are never inferred.
- `new_session.py` scaffolds the session folder, including an absolute-path `build.sh` that won't overwrite hand edits, and seeds `lessons.md`'s header.
- Confidence slips: a `## Confidence` section in feedback.md and `confidence.py summary|history`. session-feedback adds confidence lessons only when a pattern repeats, and runs a keep/drop review after 4–6 sessions. session-prep flags a low or split room.
- `doctor.py` checks tools once per run. `search_exams.py` confirms exam coverage. `deliver.py` gets the deck into Drive (local copy, reveal, or base64 for small decks), with OS guards.

### Project
- Scripts declare dependencies inline (PEP 723): `uv run <script>` from anywhere.
- Tests: builder golden tests on a TeX-free fixture template, the pipeline, schemas, the coverage rule, and 1000-seed generator property tests. GitHub Actions runs pytest and ruff on every push.

## 0.1.0 — 2026-09-23

First version: session-prep and session-feedback skills, template-based deck builder, panchi verification.
