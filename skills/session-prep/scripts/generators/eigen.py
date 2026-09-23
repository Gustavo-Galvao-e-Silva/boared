"""Eigenvalues: A = P D P⁻¹ with a unimodular integer P, so A, P and P⁻¹ are integer
matrices and the eigenvectors are P's columns. Tag: eigen.

params:
    n (2)                         size (2 or 3)
    kind ("distinct")             distinct | repeated | defective | complex
        distinct   integer eigenvalues, all different
        repeated   a repeated eigenvalue that still has a full eigenspace (n = 3)
        defective  a Jordan block: repeated eigenvalue, one eigenvector short
        complex    a [[a, -b], [b, a]] block: eigenvalues a ± bi
"""

from __future__ import annotations

import random

from generators import PROFILES, Candidate, exact, latex_matrix, to_plain, unimodular

OPS = {"easy": (1, 2), "medium": (2, 3), "hard": (3, 4)}


def _block(rng: random.Random, n: int, kind: str) -> tuple[list[list[int]], list]:
    """The target matrix D (diagonal / Jordan / rotation-scaling) and its eigenvalues."""
    D = [[0] * n for _ in range(n)]
    if kind == "distinct":
        vals = rng.sample([v for v in range(-4, 6) if v != 0], n)
    elif kind == "repeated":
        if n < 3:
            raise ValueError("kind: repeated needs n = 3 (a 2x2 with a full repeated eigenspace is λI)")
        a, b = rng.sample([v for v in range(-3, 5) if v != 0], 2)
        vals = [a, a, b]
    elif kind == "defective":
        a = rng.choice([v for v in range(-3, 5) if v != 0])
        vals = [a, a] + ([rng.choice([v for v in range(-3, 5) if v not in (0, a)])] if n == 3 else [])
        D[0][1] = 1
    elif kind == "complex":
        a, b = rng.randint(-3, 3), rng.choice([1, 2, 3])
        D[0][0], D[0][1], D[1][0], D[1][1] = a, -b, b, a
        vals = [f"{a}+{b}i", f"{a}-{b}i"]
        if n == 3:
            c = rng.choice([v for v in range(-3, 5) if v != 0])
            D[2][2] = c
            vals.append(c)
        return D, vals
    else:
        raise ValueError(f"kind must be distinct, repeated, defective or complex, not {kind!r}")
    for i, v in enumerate(vals):
        D[i][i] = v
    return D, vals


def generate(rng: random.Random, difficulty: str, **params) -> Candidate:
    import panchi as pan

    n, kind = int(params.get("n", 2)), params.get("kind", "distinct")
    D, vals = _block(rng, n, kind)
    P = unimodular(rng, n, rng.randint(*OPS[difficulty]))
    A = P @ exact(D) @ pan.inverse(P).inverse
    # "diagonalizable" means over the reals, as in the course (complex eigenvalues → not diagonalizable)
    answer: dict = {"eigenvalues": to_plain(vals), "diagonalizable": kind in ("distinct", "repeated")}
    cols = [_positive(col) for col in P.T.to_list()]
    if kind in ("distinct", "repeated"):
        answer["eigenvectors"] = {str(v): [] for v in dict.fromkeys(vals)}
        for v, col in zip(vals, cols):
            answer["eigenvectors"][str(v)].append(to_plain(col))
    elif kind == "defective":
        answer["eigenvectors"] = {str(vals[0]): [to_plain(cols[0])]}
    return Candidate("eigen", "", difficulty, params, {"matrix": to_plain(A.to_list())}, answer, {"P": P})


def _positive(v: list) -> list:
    """Flip an eigenvector so its first non-zero entry is positive."""
    first = next((x for x in v if x != 0), 1)
    return [-x for x in v] if first < 0 else list(v)


def _sympy_eigenvalues(values):
    import sympy as sp

    return sorted((sp.nsimplify(sp.sympify(str(v).replace("i", "*I"))) for v in values), key=sp.default_sort_key)


def validate(c: Candidate) -> list[str]:
    import sympy as sp

    A = c.data["matrix"]
    M = sp.Matrix(A)
    problems = []
    got = sorted((v for v, m in M.eigenvals().items() for _ in range(m)), key=sp.default_sort_key)
    if got != _sympy_eigenvalues(c.answer["eigenvalues"]):
        problems.append(f"eigenvalues are {got}, not {c.answer['eigenvalues']}")
    if M.is_diagonalizable(reals_only=True) != c.answer["diagonalizable"]:
        problems.append("diagonalizability is wrong")
    cap = PROFILES[c.difficulty]["cap"]
    if any(abs(x) > cap for row in A for x in row):
        problems.append(f"entry above {cap}")
    vecs = [x for vs in c.answer.get("eigenvectors", {}).values() for v in vs for x in v]
    if any(abs(sp.Rational(str(x))) > 5 for x in vecs):
        problems.append("eigenvector entry above 5")
    if all(A[i][j] == 0 for i in range(len(A)) for j in range(len(A)) if i != j):
        problems.append("A is diagonal")
    triangular = all(A[i][j] == 0 for i in range(len(A)) for j in range(i)) or all(
        A[i][j] == 0 for i in range(len(A)) for j in range(i + 1, len(A))
    )
    if triangular and c.difficulty != "easy":
        problems.append("A is triangular (eigenvalues can be read off)")
    return problems


def to_question(c: Candidate, qid: str) -> dict:
    kind = c.params.get("kind", "distinct")
    statement = {
        "distinct": "Find the eigenvalues of A and a basis for each eigenspace.",
        "repeated": "Find the eigenvalues of A. Is A diagonalizable?",
        "defective": "Find the eigenvalues of A. Is A diagonalizable?",
        "complex": "Find the eigenvalues of A.",
    }[kind]
    justification = {
        "distinct": "n distinct eigenvalues, so A is diagonalizable.",
        "repeated": "The repeated eigenvalue has a 2-dimensional eigenspace, so A is diagonalizable.",
        "defective": "The repeated eigenvalue has only a 1-dimensional eigenspace, so A is not diagonalizable.",
        "complex": "The characteristic polynomial has negative discriminant, so the eigenvalues are complex.",
    }[kind]
    return {
        "id": qid,
        "slot": "problem",
        "tags": ["eigen"],
        "statement": statement,
        "answer": c.answer,
        "justification": justification,
        "minutes": {"easy": 5, "medium": 7, "hard": 10}[c.difficulty] + (3 if len(c.data["matrix"]) > 2 else 0),
        "latex": "A = " + latex_matrix(c.data["matrix"]),
        "data": c.data,
    }


def checks(q) -> None:
    from fractions import Fraction

    import panchi as pan

    from verify_kit import check, check_true

    A = exact(q.data["matrix"])
    c = Candidate("eigen", "", q.difficulty, dict(q.generator.params), q.data, q.answer)
    problems = validate(c)
    wrong = [p for p in problems if "eigenvalues are" in p or "diagonalizability" in p]
    check_true(f"{q.id} eigenvalues and diagonalizability", not wrong, "; ".join(wrong))
    for value, vectors in q.answer.get("eigenvectors", {}).items():
        lam = Fraction(value)
        for v in vectors:
            x = pan.exact_vector(v)
            check(f"{q.id} eigenvector for {value}: {v}", A @ x, x * lam)
    nice = [p for p in problems if p not in wrong]
    check_true(f"{q.id} nice numbers ({q.difficulty})", not nice, "; ".join(nice))
