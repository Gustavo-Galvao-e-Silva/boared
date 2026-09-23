"""Problem generators: build a problem backwards from a nice answer, then filter it
by replaying panchi's own elimination steps.

Each module ``generators/<name>.py`` (one per skill tag) provides:

    generate(rng, difficulty, **params) -> Candidate   # one random attempt
    validate(c) -> list[str]                           # problems; empty = accepted
    to_question(c, qid) -> dict                        # a questions.yaml entry
    checks(q) -> None                                  # verify_kit checks for a stored entry

``make_question(name, seed, difficulty, qid, **params)`` runs generate-then-reject
until a candidate passes (or MAX_ATTEMPTS). The seed fully determines the result,
so any answer key can be regenerated. Seeds follow ``<date>-<tag>-<index>``.

``checks`` re-derives the answer from the question's stored ``data`` — so a
hand-edited matrix is re-checked, not trusted — and re-applies ``validate``.
"""

from __future__ import annotations

import importlib
import pkgutil
import random
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

MAX_ATTEMPTS = 400

# difficulty → filter settings used by every generator (each may add its own)
PROFILES = {
    "easy": {"integer_only": True, "cap": 9, "steps": (1, 6)},
    "medium": {"integer_only": True, "cap": 9, "steps": (3, 10)},
    "hard": {"integer_only": False, "cap": 12, "steps": (5, 16)},
}


class GenerationError(RuntimeError):
    pass


@dataclass
class Candidate:
    name: str
    seed: str
    difficulty: str
    params: dict[str, Any]
    data: dict[str, Any]  # the objects the question is about (lists of ints / fraction strings)
    answer: Any
    extra: dict[str, Any] = field(default_factory=dict)  # construction details, not stored


def names() -> list[str]:
    import generators

    return sorted(m.name for m in pkgutil.iter_modules(generators.__path__) if not m.name.startswith("_"))


def module(name: str):
    if name not in names():
        raise GenerationError(f"no generator {name!r}; available: {', '.join(names())}")
    return importlib.import_module(f"generators.{name}")


def make_candidate(name: str, seed: str, difficulty: str = "medium", **params) -> Candidate:
    if difficulty not in PROFILES:
        raise GenerationError(f"difficulty must be one of {', '.join(PROFILES)}")
    mod = module(name)
    rng = random.Random(seed)
    last: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        c = mod.generate(rng, difficulty, **params)
        c.seed = seed
        last = mod.validate(c)
        if not last:
            return c
    raise GenerationError(
        f"{name}: no candidate passed after {MAX_ATTEMPTS} attempts ({difficulty}, {params}); last problems: {'; '.join(last)}"
    )


def make_question(name: str, seed: str, difficulty: str, qid: str, **params) -> dict:
    c = make_candidate(name, seed, difficulty, **params)
    q = module(name).to_question(c, qid)
    q.setdefault("difficulty", difficulty)
    q["source"] = f"generator:{name}"
    q["generator"] = {"name": name, "seed": seed, "params": params}
    tags = q.setdefault("tags", [])
    if name not in tags:
        tags.append(name)
    return q


def run_checks(q) -> None:
    """Record verify_kit checks for a generated question (a schemas.Question)."""
    module(q.generator.name).checks(q)


# --- helpers shared by generators ----------------------------------------------------------


def to_plain(value):
    """Fractions → int when whole, else 'p/q' strings, recursively (YAML-friendly)."""
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if isinstance(value, Fraction):
        return int(value) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def entries(matrix) -> list:
    return [x for row in matrix.to_list() for x in row]


def replay_problems(reduction, difficulty: str, cap: int | None = None, steps: tuple[int, int] | None = None) -> list[str]:
    """Filter a candidate by the path panchi takes to reduce it.

    Replays ``reduction.steps`` from the original matrix and reports fractions
    (when the difficulty wants integer-only work), entries above the size cap, and
    a step count outside the difficulty's range.
    """
    prof = PROFILES[difficulty]
    cap = cap if cap is not None else prof["cap"]
    lo, hi = steps or prof["steps"]
    problems = []
    n = len(reduction.steps)
    if not lo <= n <= hi:
        problems.append(f"{n} row operations (want {lo}-{hi})")
    m = reduction.original
    for i, step in enumerate(reduction.steps, start=1):
        m = step.apply(m)
        xs = entries(m)
        if prof["integer_only"] and any(Fraction(x).denominator != 1 for x in xs):
            problems.append(f"fraction after step {i}")
            break
        if any(abs(x) > cap for x in xs):
            problems.append(f"entry above {cap} after step {i}")
            break
    return problems


def degenerate_problems(matrix, allow_zero_rows: bool = False, allow_zero_cols: bool = False) -> list[str]:
    rows = matrix.to_list()
    problems = []
    if len({tuple(r) for r in rows}) < len(rows):
        problems.append("duplicate rows")
    if not allow_zero_rows and any(all(x == 0 for x in r) for r in rows):
        problems.append("zero row")
    if not allow_zero_cols and any(all(r[j] == 0 for r in rows) for j in range(len(rows[0]))):
        problems.append("zero column")
    return problems


def scramble(rng: random.Random, matrix, n_ops: int, swaps: bool = True, multipliers=(-3, -2, -1, 1, 2, 3)):
    """Apply ``n_ops`` random integer row operations (adds, swaps, sign flips).

    Returns (scrambled, ops). Every op is invertible over the integers, so the
    scrambled matrix has the same RREF and, if square, det = ±det(matrix).
    """
    from panchi.algorithms.row_operations import RowAdd, RowScale, RowSwap

    n = matrix.rows
    ops = []
    for _ in range(n_ops):
        roll = rng.random()
        a, b = rng.sample(range(n), 2) if n > 1 else (0, 0)
        if n > 1 and (roll < 0.7 or not swaps):
            op = RowAdd(a, b, rng.choice(multipliers))
        elif n > 1 and roll < 0.85:
            op = RowSwap(a, b)
        else:
            op = RowScale(a, -1)
        matrix = op.apply(matrix)
        ops.append(op)
    return matrix, ops


def unimodular(rng: random.Random, n: int, n_ops: int):
    """A random integer matrix with det ±1 (so its inverse is an integer matrix)."""
    import panchi as pan

    return scramble(rng, pan.identity(n), n_ops, multipliers=(-2, -1, 1, 2))[0]


def exact(data):
    import panchi as pan

    return pan.exact_matrix(data)


def latex_matrix(rows, env: str = "bmatrix", augmented: int | None = None) -> str:
    """LaTeX for a matrix given as lists; ``augmented`` = number of columns before the bar."""

    def cell(x):
        s = str(x)
        if "/" in s:
            p, q = s.split("/")
            sign = "-" if p.startswith("-") else ""
            return f"{sign}\\tfrac{{{p.lstrip('-')}}}{{{q}}}"
        return s

    body = r" \\ ".join(" & ".join(cell(x) for x in row) for row in rows)
    if augmented is not None:
        cols = "c" * augmented + "|" + "c" * (len(rows[0]) - augmented)
        return rf"\left[\begin{{array}}{{{cols}}} {body} \end{{array}}\right]"
    return rf"\begin{{{env}}} {body} \end{{{env}}}"
