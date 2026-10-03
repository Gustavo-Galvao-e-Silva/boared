# questions.yaml

`sessions/<date>/questions.yaml` is the single source for a session's questions. Everything else is generated from it or refers to it by `id`: the plan's Timeline and Questions sections, the `verify.py` stubs, and every slide, table row, answer mark and speaker note in `deck.yaml`. Bank entries (`bank/<id>.yaml`) use the same schema.

Validated by `scripts/schemas.py`. Errors name the question, e.g. `tf4: answer must be true/false for slot tf`.

```yaml
- id: tf4                        # lowercase letters, digits, - or _; unique in the file
  slot: tf                       # warmup | tf | pi | problem | proof
  section: "2.5"                 # the topic it practises: a course.yaml `sections` label (or unambiguous prefix)
  uses: ["2.5", "2.2"]           # every topic the question AND its justification rely on (section is added)
  tags: [lu, inverses]           # skill tags, at least one; a generator's name is added automatically
  statement: "If A is invertible and A = LU, then **A⁻¹ = L⁻¹U⁻¹**."
  answer: false
  justification: "The order reverses: A⁻¹ = U⁻¹L⁻¹."
  source: from scratch           # bank:<id> | exam:<file> | <url> | generator:<name>
  difficulty: medium             # easy | medium | hard
  minutes: 2.5
  notes: "Hint: try 2x2 with L = [[1,0],[1,1]]."   # optional extra speaker notes
  kahoot:                        # optional: how it goes into a Kahoot (kahoot.py)
    question: "A invertible, A = LU ⇒ A⁻¹ = L⁻¹U⁻¹"   # plain text, ≤ 120 characters
    time: 30                     # seconds: 5 10 15 20 30 45 60 90 120 180 240

- id: w1
  slot: warmup
  section: "2.5"
  uses: ["2.5"]
  tags: [lu]
  statement: "Which of these are triangular?"
  choices: {A: "L", B: "U", C: "A", D: "P"}   # multiple choice: answer is one letter or a list
  answer: [A, B]
  justification: "L is lower triangular, U upper; A and P in general are neither."
  source: from scratch
  difficulty: easy
  minutes: 2

- id: lam1
  slot: proof
  section: "2.5"
  uses: ["2.5", "5.1"]           # 5.1 is taught next week...
  preview: true                  # ...on purpose: verify_runner warns instead of failing, plan.md asks the leader
  # (other required fields as above)

- id: lu1                        # written by generate.py; don't hand-edit the generator block
  slot: problem
  section: "2.5"                 # generate.py: the session's topic, or --section / --uses
  statement: "Find an LU factorization of A, or explain why none exists without row swaps."
  latex: 'A = \begin{bmatrix} 0 & 2 \\ 1 & 3 \end{bmatrix}'   # rendered to math/lu1.png for the slide
  data: {matrix: [[0, 2], [1, 3]]}   # what the checks recompute from
  answer: {exists: false}
  generator: {name: lu, seed: 2026-09-24-lu-01, params: {exists: false}}
```

## Answers by slot

| slot | `answer` | checked by |
|---|---|---|
| `tf` | `true` / `false` | a theorem instance (True) or a counterexample (False) |
| `pi` | `possible` / `impossible` | a witness (Possible) or the theorem plus any finite demonstration (Impossible) |
| `warmup` with `choices` | a letter or list of letters | the computation behind the right choice |
| `problem`, `proof`, `warmup` | anything (number, matrix, dict, text) | exact computation of the answer |

## Rules

- **Every field above is required** except `choices`, `image`/`latex`, `data`, `generator`, `notes`, `preview` and `kahoot`. A missing one is an error naming the question.
- **Teachable yet?** `verify_runner.py` fails a question when a topic in `uses` is first taught after the session date, when a `uses` label matches no topic in the schedule, or when its statement, justification, answer or notes contain a word that `course.yaml` `prerequisites:` ties to a later topic. Before writing a question, list the concepts it and its justification need. The usual miss is a slick justification that leans on a later tool. When the check fails, rewrite the question by default; in the plan, name the item, the topic and the date it is taught. Use `preview: true` only for a deliberate preview, and the leader approves it in `plan.md`.
- **IDs are permanent within a session.** Reordering questions is fine; renaming an ID means renaming its checks too (the runner flags orphans).
- Statements use the deck markup: `**bold**` and `{{colour|text}}`, with colours from `template-map.yaml`. Short math as Unicode (A⁻¹, ℝ³); matrices go in `latex:` or a prepared `image:`.
- `minutes` drives the Timeline. The total must be within 5 minutes of `session.length_min`.
- Order is the session order. Consecutive questions with the same slot share slides according to the template map's `slots:` (e.g. 3 T/F per slide, then a hidden answer slide with marks).

## Kahoot

`kahoot.py payload <session>` exports the verified questions that have a Kahoot equivalent:

| question | Kahoot |
|---|---|
| slot `tf` | True/False |
| slot `pi` | quiz: Possible / Impossible |
| any slot with `choices` (≤ 6) | quiz, with the answer letter(s) correct |
| `problem`, `proof`, `warmup` without choices | skipped |

Kahoot shows plain text only: markup is removed, questions are at most 120 characters and choices at most 75. The time defaults to 20/30/60 s for easy/medium/hard.

The optional `kahoot:` block:
- **left out**: the question is exported when it fits, and skipped (with the reason) when it doesn't;
- `question:` a short plain-text statement. Required when the math is in `latex:`/`image:` or the statement is too long;
- `choices:` shorter texts for some choice letters, e.g. `{C: "A itself"}`;
- `time:` seconds to answer;
- `include: false` leaves the question out.

A question with a `kahoot:` block (and `include` not false) **must** export, or `payload` fails. Use the block to say "this one belongs in the Kahoot".

## Generated questions

```
uv run <skill>/scripts/generate.py <session> <name> [--count N] [--difficulty easy|medium|hard] [--set key=value ...]
uv run <skill>/scripts/generate.py --list        # generators and their parameters
```

| name | builds | useful params |
|---|---|---|
| `rref` | a target RREF (pivots, free variables, consistency) scrambled by 2–5 integer row operations | `rows`, `cols`, `free` or `rank`, `augmented`, `consistent` |
| `inverse` | a product of integer elementary matrices (det ±1, integer inverse), or a rank-deficient matrix | `n`, `invertible` |
| `eigen` | A = PDP⁻¹ with unimodular P: distinct, repeated, defective (Jordan) or complex (`[[a,-b],[b,a]]`) | `n`, `kind` |
| `span` | independent integer vectors plus integer combinations of them | `dim`, `k`, `rank` |
| `lu` | A = LU (Doolittle, no swaps), or a matrix that needs a row swap | `n`, `exists` |

Difficulty is tuned by filtering, not construction. A candidate is replayed through panchi's own steps and rejected if an intermediate entry is a fraction (easy/medium), exceeds the size cap (|x| ≤ 9, or 12 for hard), or the step count is out of range, or if it has structure the question didn't ask for (duplicate rows, zero columns).

The seed `<date>-<name>-<index>` regenerates the question exactly. Its checks recompute the answer from `data`, so a hand-edited matrix is re-checked, not trusted. They also re-check the nice-number filter for the stated difficulty. If you make a generated problem harder by hand, raise its `difficulty`.
