# Question sourcing

Sources can be mixed within one session. Every question records its origin in `source:` (`bank:<id>`, `exam:<file>`, a URL, `generator:<name>`, or `from scratch`).

## Generated (`scripts/generate.py`)

The fastest source for computational problems, and each one comes with its own checks. Ask by tag and difficulty, e.g. "2 rref, medium, one with a free variable":

```
uv run <skill>/scripts/generate.py <session> rref --count 1 --difficulty medium
uv run <skill>/scripts/generate.py <session> rref --count 1 --difficulty medium --set free=1
```

Generators: `rref`, `inverse`, `eigen`, `span`, `lu`. See `questions.md` for their parameters. Review each generated statement and reword it to fit the session. The data and answer stay tied to the seed.

## Bank (`bank/<id>.yaml`)

```
uv run <skill>/scripts/bank.py find <course> --tags lu,inverses --slot tf     # skips anything used in the last 3 sessions
uv run <skill>/scripts/bank.py use <session> tf-cancellation [--as tf3]      # copy into questions.yaml
```

`use` sets `source: bank:<id>` and updates `last_used` / `times_used`. Prefer `verified: true` entries; unverified ones need a check like any new question.

## Exams as inspiration (`exams/`)

Read practice and past exams for the week's topics to match the **style, difficulty and phrasing** students will face. Write new questions in that style: change the matrices, the context, or flip the claim. Never paste exam questions verbatim onto slides; course materials aren't ours to redistribute, and students may have already seen them.

Before `plan.md` claims a topic "appears on past exams", confirm it:

```
uv run <skill>/scripts/search_exams.py "LU" "PA = LU" --course <course>
```

It reports the file, page and problem each hit is in. Cite them ("Midterm 2 Fall 2025, problem 4(b)").

## From scratch

Start from the misconception or skill the week targets, then build the problem around a hand-picked "nice" matrix (see `verification.md`). Patterns that work:
- T/F: take a true theorem and drop one hypothesis.
- Possible/impossible: ask for an object at the edge of a theorem (rank bounds, invertibility, dimension counts, LU without swaps).
- Word problems: a small real system with integer data whose solution has meaning (non-negative, integer).

## Web research

Use web search for applications, historical context, or problem ideas (e.g. open textbooks like Hefferon, or *Interactive Linear Algebra* by Margalit & Rabinoff, GT's own). Paraphrase, adapt the numbers, and cite the URL in `source:`. Treat anything found online as unverified until it has a passing check.

## Adding to the bank

After a session, offer `bank.py add <session> [--ids tf4,pi2]`. It copies the questions with `verified: true` only if the session's `verify.log` passed and is current. The bank is private course material: it lives in the course folder, not the public plugin repo.
