"""Span / linear independence: choose the rank, take that many independent integer
vectors, and form the rest as integer combinations of them. Tag: span.

params:
    dim (3)       vectors live in R^dim
    k (3)         number of vectors
    rank          dimension of the span (default: k if k <= dim, else dim)
"""

from __future__ import annotations

import random

from generators import PROFILES, Candidate, exact, latex_matrix, replay_problems, to_plain, unimodular

OPS = {"easy": (2, 3), "medium": (3, 4), "hard": (4, 5)}


def generate(rng: random.Random, difficulty: str, **params) -> Candidate:
    dim, k = int(params.get("dim", 3)), int(params.get("k", 3))
    rank = int(params.get("rank", min(k, dim)))
    if not 1 <= rank <= min(k, dim):
        raise ValueError(f"rank {rank} impossible for {k} vectors in R^{dim}")
    basis = unimodular(rng, dim, rng.randint(*OPS[difficulty])).T.to_list()[:rank]
    vectors, relation = list(basis), None
    for _ in range(k - rank):
        coeffs = [rng.choice([-2, -1, 0, 1, 2]) for _ in range(rank)]
        if sum(c != 0 for c in coeffs) < min(2, rank):
            coeffs[rng.randrange(rank)] = rng.choice([-1, 1])
            coeffs[rng.randrange(rank)] = rng.choice([-2, 2])
        vectors.append([sum(c * b[j] for c, b in zip(coeffs, basis)) for j in range(dim)])
        if relation is None:  # v_new - Σ c_j b_j = 0
            relation = [-c for c in coeffs] + [0] * (len(vectors) - 1 - rank) + [1]
    order = list(range(k))
    rng.shuffle(order)
    shuffled = [vectors[i] for i in order]
    answer: dict = {"independent": rank == k, "dim_span": rank}
    if relation is not None:
        relation += [0] * (k - len(relation))
        answer["relation"] = [relation[i] for i in order]
    return Candidate("span", "", difficulty, params, {"vectors": to_plain(shuffled)}, answer)


def _column_matrix(vectors):
    return exact([list(row) for row in zip(*vectors)])


def validate(c: Candidate) -> list[str]:
    import panchi as pan
    from panchi.algorithms import rref

    vs = c.data["vectors"]
    M = _column_matrix(vs)
    problems = []
    if pan.rank(M) != c.answer["dim_span"]:
        problems.append("stated dimension is wrong")
    if (pan.rank(M) == len(vs)) != c.answer["independent"]:
        problems.append("independence is wrong")
    rel = c.answer.get("relation")
    if rel is not None:
        combo = [sum(r * v[j] for r, v in zip(rel, vs)) for j in range(len(vs[0]))]
        if any(combo) or not any(rel):
            problems.append("stated dependence relation is wrong")
    cap = PROFILES[c.difficulty]["cap"]
    if any(abs(x) > cap for v in vs for x in v):
        problems.append(f"entry above {cap}")
    if any(not any(v) for v in vs):
        problems.append("zero vector")
    if len({tuple(v) for v in vs}) < len(vs):
        problems.append("repeated vector")
    problems += [p for p in replay_problems(rref(M), c.difficulty) if "row operations" not in p]
    return problems


def to_question(c: Candidate, qid: str) -> dict:
    vs = c.data["vectors"]
    names = ", ".join(f"v{i + 1}" for i in range(len(vs)))
    if c.answer["independent"]:
        justification = f"The matrix [{names}] has a pivot in every column."
    else:
        terms = " + ".join(f"({r})v{i + 1}" for i, r in enumerate(c.answer["relation"]) if r)
        justification = f"Rank {c.answer['dim_span']} < {len(vs)}; e.g. {terms} = 0."
    latex = r",\quad ".join(f"v_{{{i + 1}}} = " + latex_matrix([[x] for x in v]) for i, v in enumerate(vs))
    return {
        "id": qid,
        "slot": "problem",
        "tags": ["span", "independence"],
        "statement": f"Are {names} linearly independent? What is the dimension of their span?",
        "answer": c.answer,
        "justification": justification,
        "minutes": {"easy": 4, "medium": 6, "hard": 8}[c.difficulty],
        "latex": latex,
        "data": c.data,
    }


def checks(q) -> None:
    import panchi as pan

    from verify_kit import check, check_true

    vs = q.data["vectors"]
    M = _column_matrix(vs)
    check(f"{q.id} dimension of span", pan.rank(M), q.answer["dim_span"])
    check(f"{q.id} independent", pan.rank(M) == len(vs), q.answer["independent"])
    rel = q.answer.get("relation")
    if rel is not None:
        combo = [sum(r * v[j] for r, v in zip(rel, vs)) for j in range(len(vs[0]))]
        check_true(f"{q.id} dependence relation", any(rel) and not any(combo), f"Σ r_i v_i = {combo}")
    c = Candidate("span", "", q.difficulty, dict(q.generator.params), q.data, q.answer)
    problems = [p for p in validate(c) if "wrong" not in p]
    check_true(f"{q.id} nice numbers ({q.difficulty})", not problems, "; ".join(problems))
