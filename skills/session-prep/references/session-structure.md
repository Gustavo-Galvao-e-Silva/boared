# Session structure

Default format (from a PLUS linear algebra leader). `course.yaml` → `session.structure` overrides it.

## Principles

- **Collaborative, not a lecture.** Students arrive at conclusions and solutions themselves. The leader asks, redirects, and summarises; slides pose problems, they don't explain them.
- Every slide should give students something to *do*: decide, compute, justify, find a counterexample, or explain to a partner.
- Put answers and hints in speaker notes, never on the slide face.

## Blocks

Each block maps to a `slot` in `questions.yaml`: warm-up → `warmup`, word problems → `problem`, true/false → `tf`, possible/impossible → `pi`, closing → `proof`.

0. **Confidence slip (1 min, start and end)**: one anonymous slip with two columns, *start* and *end*. Ask a specific question: "How confident are you on *<this week's topic>*, 1–5?" A vague "how did today go?" invites politeness. Collect both columns at the end. The tallies go into `feedback.md` → Confidence. Mention the slip in the plan's timeline and in the first slide's notes.
1. **Warm-up (short)** — low-stakes entry: quick recall questions, a brain dump ("write everything you know about invertible matrices"), a one-step computation. Goal: activate the week's vocabulary and let everyone succeed once.
2. **Main session (~40 min)** — the core. Mix of:
   - **Word problems** — a context (networks, mixing, graphics, economics) that must be translated into a system or matrix before solving.
   - **True / False** — each needs a justification: a theorem for True, a concrete counterexample for False. Target the misconceptions the week invites (e.g. "AB = AC ⇒ B = C").
   - **Possible / Impossible** — "give an example of … or explain why none exists." Possible ⇒ a verified witness; Impossible ⇒ the theorem that forbids it.
   Order from accessible to harder; alternate formats to keep energy.
3. **Closing activity (challenging)** — e.g. completing a guided proof, a conceptual stretch question, or a teaser of the next topic (hinting at eigenvectors while doing inverses). It's fine if not everyone finishes.

## Calibrating

- Roughly 1 T/F or possible/impossible item ≈ 3–5 min in groups; a word problem ≈ 8–12 min. Fit the main block to ~40 min.
- Before an exam: bias toward exam-style questions from `exams/`.
- Use past `feedback.md`: repeat formats that worked, shrink what ran long, revisit what students struggled with in the warm-up.
- Use the last session's confidence: a low end mean (≤ 2.5) calls for revisiting the topic in the warm-up. A *split* room (many 1–2s and many 4–5s) calls for pairing strong students with struggling ones, not for re-teaching everyone.
