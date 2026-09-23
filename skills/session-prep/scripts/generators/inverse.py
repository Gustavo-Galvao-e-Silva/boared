"""Inverses: multiply integer elementary matrices so det = ±1 and the inverse is an
integer matrix. Tag: inverse.

params:
    n (2)                 size
    invertible (true)     false → a rank n-1 matrix; the answer is "not invertible"
"""

from __future__ import annotations

import random

from generators import (
    Candidate,
    degenerate_problems,
    entries,
    exact,
    latex_matrix,
    replay_problems,
    scramble,
    to_plain,
    unimodular,
)

OPS = {"easy": (2, 3), "medium": (3, 5), "hard": (4, 6)}


def generate(rng: random.Random, difficulty: str, **params) -> Candidate:
    import panchi as pan

    n = int(params.get("n", 2))
    invertible = bool(params.get("invertible", True))
    if invertible:
        A = unimodular(rng, n, rng.randint(*OPS[difficulty]))
        answer = {"invertible": True, "inverse": to_plain(pan.inverse(A).inverse.to_list())}
    else:
        # rank n-1: an invertible matrix with one row replaced by a combination of the others
        B = unimodular(rng, n, rng.randint(*OPS[difficulty])).to_list()
        k = rng.randrange(n)
        others = [r for i, r in enumerate(B) if i != k]
        coeffs = [rng.choice([-2, -1, 1, 2]) for _ in others]
        B[k] = [sum(c * r[j] for c, r in zip(coeffs, others)) for j in range(n)]
        A, _ = scramble(rng, exact(B), 1)
        answer = {"invertible": False}
    return Candidate("inverse", "", difficulty, params, {"matrix": to_plain(A.to_list())}, answer)


def validate(c: Candidate) -> list[str]:
    import panchi as pan
    from panchi.algorithms import rref

    from generators import PROFILES

    A = exact(c.data["matrix"])
    problems = []
    if pan.is_invertible(A) != c.answer["invertible"]:
        problems.append("invertibility is wrong")
        return problems
    cap = PROFILES[c.difficulty]["cap"]
    if c.answer["invertible"]:
        inv = exact(c.answer["inverse"])
        if A @ inv != pan.identity(A.rows):
            problems.append("stated inverse is wrong")
        if any(abs(x) > cap for x in entries(inv)):
            problems.append(f"inverse has an entry above {cap}")
    # a singular matrix reduces in a step or two, so only its invertible cousin gets a step-count range
    problems += replay_problems(rref(A), c.difficulty, steps=None if c.answer["invertible"] else (1, 99))
    problems += degenerate_problems(A)
    if pan.identity(A.rows) == A:
        problems.append("identity matrix")
    return problems


def to_question(c: Candidate, qid: str) -> dict:
    rows = c.data["matrix"]
    if c.answer["invertible"]:
        justification = "Row reduce [A | I] to [I | A⁻¹]; check A·A⁻¹ = I."
    else:
        justification = "A has rank < n (a row is a combination of the others), so det A = 0 and A has no inverse."
    return {
        "id": qid,
        "slot": "problem",
        "tags": ["inverse"],
        "statement": "Find A⁻¹, or explain why A is not invertible.",
        "answer": c.answer,
        "justification": justification,
        "minutes": {"easy": 4, "medium": 6, "hard": 8}[c.difficulty] + (2 if len(rows) > 2 else 0),
        "latex": "A = " + latex_matrix(rows),
        "data": c.data,
    }


def checks(q) -> None:
    import panchi as pan

    from verify_kit import check, check_true

    A = exact(q.data["matrix"])
    check(f"{q.id} invertible", pan.is_invertible(A), q.answer["invertible"])
    if q.answer["invertible"]:
        check(f"{q.id} inverse", pan.inverse(A).inverse, exact(q.answer["inverse"]))
    c = Candidate("inverse", "", q.difficulty, dict(q.generator.params), q.data, q.answer)
    problems = [p for p in validate(c) if "wrong" not in p]
    check_true(f"{q.id} nice numbers ({q.difficulty})", not problems, "; ".join(problems))
