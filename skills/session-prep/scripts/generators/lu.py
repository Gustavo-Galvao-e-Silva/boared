"""LU factorisation without row swaps (Doolittle, as taught): A = LU with L unit
lower-triangular. Tag: lu.

params:
    n (3)             size
    exists (true)     false → elimination meets a zero pivot with a non-zero entry below,
                      so A has no LU factorisation without pivoting (A is still invertible)
"""

from __future__ import annotations

import random

from generators import PROFILES, Candidate, entries, exact, latex_matrix, to_plain

NONZERO = [-3, -2, -1, 1, 2, 3]


def _unit_lower(rng: random.Random, n: int, difficulty: str) -> list[list[int]]:
    pool = [-2, -1, 0, 1, 2] if difficulty == "easy" else [-3, -2, -1, 0, 1, 2, 3]
    return [[1 if i == j else (rng.choice(pool) if i > j else 0) for j in range(n)] for i in range(n)]


def _upper(rng: random.Random, n: int, difficulty: str) -> list[list[int]]:
    pivots = [-2, -1, 1, 2] if difficulty != "hard" else [-3, -2, -1, 1, 2, 3]
    return [[(rng.choice(pivots) if i == j else rng.randint(-3, 3)) if j >= i else 0 for j in range(n)] for i in range(n)]


def generate(rng: random.Random, difficulty: str, **params) -> Candidate:
    n = int(params.get("n", 3))
    exists = bool(params.get("exists", True))
    L = _unit_lower(rng, n, difficulty)
    U = _upper(rng, n, difficulty)
    if not exists:
        # B is upper-triangular except that a zero pivot at (k, k) has a non-zero entry below it
        k = 0 if difficulty == "easy" or n == 2 else rng.randrange(0, n - 1)
        U[k][k] = 0
        U[k + 1][k] = rng.choice(NONZERO)
        for j in range(k + 1, n):
            U[k][j] = rng.choice(NONZERO) if j == k + 1 else rng.randint(-3, 3)
    A = exact(L) @ exact(U)
    answer = {"exists": True, "L": L, "U": U} if exists else {"exists": False}
    return Candidate("lu", "", difficulty, params, {"matrix": to_plain(A.to_list())}, answer)


def validate(c: Candidate) -> list[str]:
    import panchi as pan

    from verify_kit import NoLU, lu_no_pivot

    A = exact(c.data["matrix"])
    problems = []
    try:
        L, U = lu_no_pivot(A)
        if not c.answer["exists"]:
            problems.append("A has an LU factorisation after all")
        elif (L, U) != (exact(c.answer["L"]), exact(c.answer["U"])):
            problems.append("stated L, U are wrong")
    except NoLU:
        if c.answer["exists"]:
            problems.append("A has no LU factorisation without row swaps")
    if not pan.is_invertible(A):
        problems.append("A is singular")
    cap = PROFILES[c.difficulty]["cap"]
    if any(abs(x) > cap for x in entries(A)):
        problems.append(f"entry above {cap}")
    return problems


def to_question(c: Candidate, qid: str) -> dict:
    if c.answer["exists"]:
        justification = "Eliminate below each pivot without swapping; L holds the multipliers, U the echelon form."
    else:
        justification = (
            "Elimination meets a zero pivot with a non-zero entry below it, so a row swap is needed: PA = LU, but A ≠ LU."
        )
    return {
        "id": qid,
        "slot": "problem",
        "tags": ["lu"],
        "statement": "Find an LU factorization of A (L unit lower triangular), or explain why none exists without row swaps.",
        "answer": c.answer,
        "justification": justification,
        "minutes": {"easy": 5, "medium": 7, "hard": 9}[c.difficulty],
        "latex": "A = " + latex_matrix(c.data["matrix"]),
        "data": c.data,
    }


def checks(q) -> None:
    from verify_kit import NoLU, check, check_true, lu_no_pivot

    A = exact(q.data["matrix"])
    try:
        L, U = lu_no_pivot(A)
        found = True
    except NoLU:
        found = False
    check(f"{q.id} LU exists without swaps", found, q.answer["exists"])
    if found and q.answer["exists"]:
        check(f"{q.id} L", L, exact(q.answer["L"]))
        check(f"{q.id} U", U, exact(q.answer["U"]))
        check(f"{q.id} LU = A", exact(q.answer["L"]) @ exact(q.answer["U"]), A)
    c = Candidate("lu", "", q.difficulty, dict(q.generator.params), q.data, q.answer)
    problems = [p for p in validate(c) if "wrong" not in p and "LU" not in p]
    check_true(f"{q.id} nice numbers ({q.difficulty})", not problems, "; ".join(problems))
