"""Row reduction: pick the RREF (pivots, free variables, consistency), then scramble it
with a few integer row operations. Tag: rref.

params:
    rows (3), cols (4)      matrix size, including the augmented column
    rank                    rank of the coefficient part (default: rows, or rows-1 when inconsistent)
    augmented (true)        last column is the right-hand side b
    consistent (true)       false → the RREF has a pivot in the b column
    free                    number of free variables (alternative to rank)
"""

from __future__ import annotations

import random

from generators import Candidate, degenerate_problems, exact, latex_matrix, replay_problems, scramble, to_plain

OPS = {"easy": (2, 3), "medium": (3, 4), "hard": (4, 5)}


def _shape(params) -> tuple[int, int, int, bool, bool]:
    rows, cols = int(params.get("rows", 3)), int(params.get("cols", 4))
    augmented = bool(params.get("augmented", True))
    consistent = bool(params.get("consistent", True))
    n_vars = cols - 1 if augmented else cols
    if "free" in params:
        rank = n_vars - int(params["free"])
    else:
        rank = int(params.get("rank", min(rows, n_vars) - (0 if consistent or not augmented else 1)))
    if not augmented and not consistent:
        raise ValueError("consistent: false needs augmented: true")
    if not 1 <= rank <= min(rows, n_vars) or (not consistent and rank + 1 > rows):
        raise ValueError(f"rank {rank} impossible for a {rows}x{cols} {'augmented ' if augmented else ''}matrix")
    return rows, cols, rank, augmented, consistent


def generate(rng: random.Random, difficulty: str, **params) -> Candidate:
    rows, cols, rank, augmented, consistent = _shape(params)
    n_vars = cols - 1 if augmented else cols
    pivots = [0, *sorted(rng.sample(range(1, n_vars), rank - 1))] if rank > 1 else [0]
    if not consistent:
        pivots.append(cols - 1)
    target = [[0] * cols for _ in range(rows)]
    for k, pc in enumerate(pivots):
        target[k][pc] = 1
        for j in range(pc + 1, cols):
            if j not in pivots:
                target[k][j] = rng.randint(-3, 3)
    A, _ = scramble(rng, exact(target), rng.randint(*OPS[difficulty]))
    free = n_vars - rank
    solutions = "none" if not consistent else ("unique" if free == 0 else "infinite") if augmented else None
    answer = {"rref": to_plain(target), "pivot_columns": [p + 1 for p in pivots]}
    if augmented:
        answer |= {"solutions": solutions, "free_variables": free if consistent else 0}
    return Candidate("rref", "", difficulty, params, {"matrix": to_plain(A.to_list())}, answer)


def validate(c: Candidate) -> list[str]:
    from panchi.algorithms import rref

    A = exact(c.data["matrix"])
    red = rref(A)
    problems = []
    if red.result != exact(c.answer["rref"]):
        problems.append("stated RREF is wrong")
    problems += replay_problems(red, c.difficulty)
    problems += degenerate_problems(A)
    return problems


def to_question(c: Candidate, qid: str) -> dict:
    rows = c.data["matrix"]
    augmented = c.params.get("augmented", True)
    n_vars = len(rows[0]) - 1 if augmented else len(rows[0])
    if augmented:
        statement = "Row reduce the augmented matrix to RREF. How many solutions does the system have?"
        sol = c.answer["solutions"]
        justification = {
            "unique": "Every variable column has a pivot and the b column has none.",
            "infinite": f"No pivot in the b column; {c.answer['free_variables']} free variable(s).",
            "none": "Pivot in the b column: a row reads 0 = 1.",
        }[sol]
    else:
        statement = "Row reduce to RREF. Which columns are pivot columns?"
        justification = f"Pivot columns: {', '.join(map(str, c.answer['pivot_columns']))}."
    return {
        "id": qid,
        "slot": "problem",
        "tags": ["rref"],
        "statement": statement,
        "answer": c.answer,
        "justification": justification,
        "minutes": {"easy": 4, "medium": 6, "hard": 8}[c.difficulty],
        "latex": latex_matrix(rows, augmented=n_vars if augmented else None),
        "data": c.data,
        "notes": "One path (panchi): " + "; ".join(_steps(rows)),
    }


def _steps(rows) -> list[str]:
    from panchi.algorithms import rref

    from verify_kit import steps_text

    return steps_text(rref(exact(rows)))


def checks(q) -> None:
    from panchi.algorithms import rref

    from verify_kit import check, check_true

    A = exact(q.data["matrix"])
    red = rref(A)
    check(f"{q.id} rref", red.result, exact(q.answer["rref"]))
    check(f"{q.id} pivot columns", [p[1] + 1 for p in red.pivots], q.answer["pivot_columns"])
    if "solutions" in q.answer:
        n_vars = A.cols - 1
        pivot_cols = [p[1] for p in red.pivots]
        actual = "none" if n_vars in pivot_cols else ("unique" if len(pivot_cols) == n_vars else "infinite")
        check(f"{q.id} number of solutions", actual, q.answer["solutions"])
    c = Candidate("rref", "", q.difficulty, dict(q.generator.params), q.data, q.answer)
    problems = [p for p in validate(c) if p != "stated RREF is wrong"]
    check_true(f"{q.id} nice numbers ({q.difficulty})", not problems, "; ".join(problems))
