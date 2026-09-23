# questions.yaml

`sessions/<date>/questions.yaml` is the single source for a session's questions. Everything else is generated from it or refers to it by `id`: the plan's Timeline and Questions sections, the `verify.py` stubs, and every slide, table row, answer mark and speaker note in `deck.yaml`. Bank entries (`bank/<id>.yaml`) use the same schema.

Validated by `scripts/schemas.py`. Errors name the question, e.g. `tf4: answer must be true/false for slot tf`.

```yaml
- id: tf4                        # lowercase letters, digits, - or _; unique in the file
  slot: tf                       # warmup | tf | pi | problem | proof
  tags: [lu, inverses]           # skill tags; a generator's name is added automatically
  statement: "If A is invertible and A = LU, then **A⁻¹ = L⁻¹U⁻¹**."
  answer: false
  justification: "The order reverses: A⁻¹ = U⁻¹L⁻¹."
  source: from scratch           # bank:<id> | exam:<file> | <url> | generator:<name>
  difficulty: medium             # easy | medium | hard
  minutes: 2.5
  notes: "Hint: try 2x2 with L = [[1,0],[1,1]]."   # optional extra speaker notes

- id: w1
  slot: warmup
  statement: "Which of these are triangular?"
  choices: {A: "L", B: "U", C: "A", D: "P"}   # multiple choice: answer is one letter or a list
  answer: [A, B]

- id: lu1                        # written by generate.py; don't hand-edit the generator block
  slot: problem
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

- **IDs are permanent within a session.** Reordering questions is fine; renaming an ID means renaming its checks too (the runner flags orphans).
- Statements use the deck markup: `**bold**` and `{{colour|text}}`, with colours from `template-map.yaml`. Short math as Unicode (A⁻¹, ℝ³); matrices go in `latex:` or a prepared `image:`.
- `minutes` drives the Timeline. The total must be within 5 minutes of `session.length_min`.
- Order is the session order. Consecutive questions with the same slot share slides according to the template map's `slots:` (e.g. 3 T/F per slide, then a hidden answer slide with marks).

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
