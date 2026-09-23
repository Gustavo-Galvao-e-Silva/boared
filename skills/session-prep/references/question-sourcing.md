# Question sourcing

Sources can be mixed within one session. Record the source of every question in plan.md.

## Bank (`bank/*.md`)

One problem per file, YAML front-matter + Markdown body (schema in `course-folder.md`). Filter by `topics` matching the week's sections and `type` matching the slot (tf, possible-impossible, word-problem, computation, proof). Skip questions whose `last_used` is within the last 3 sessions. Prefer `verified: true`; unverified ones go through step 6 like new questions.

## Exams as inspiration (`exams/`)

Read practice/past exams for the week's topics to match the **style, difficulty and phrasing** students will face. Write new questions in that style — change the matrices, the context, or flip the claim. Never paste exam questions verbatim onto slides (course materials are not ours to redistribute, and students may have already seen them).

## From scratch

Start from the misconception or skill the week targets, then build the problem around a hand-picked "nice" matrix (see `verification.md`). Good generators:
- T/F: take a true theorem and drop one hypothesis.
- Possible/impossible: ask for an object at the edge of a theorem (rank bounds, invertibility, dimension counts).
- Word problems: a small real system with integer data whose solution has meaning (non-negative, integer).

## Web research

Use web search for applications, historical context, or problem ideas (e.g. open textbooks like Hefferon, Interactive Linear Algebra by Margalit & Rabinoff — GT's own). Paraphrase, adapt the numbers, and cite the URL in plan.md. Treat anything found online as unverified until step 6.

## Adding to the bank

After a session, offer to save new verified questions to `bank/` with `verified: true` and the session date as `last_used`. The bank is private course material — it lives in the course folder, not the public plugin repo.
