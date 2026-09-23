"""Assertions for a session's verify.py. Run it through verify_runner.py.

    import panchi as pan
    from verify_kit import check, check_true, check_close

    A = pan.exact_matrix([[2, 1], [5, 3]])
    check("Q1 inverse", pan.inverse(A).inverse, pan.exact_matrix([[3, -1], [-5, 2]]))
    check_true("Q3 witness: A^2 = 0 but A != 0", A2 @ A2 == pan.zero_matrix(2, 2) and A2 != pan.zero_matrix(2, 2))
    check_close("Q7 eigenvalue", max(pan.eigen(B).eigenvalues), 3)

Every check records a result instead of stopping, so one run reports every
wrong answer at once.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Result:
    label: str
    ok: bool
    detail: str = ""


RESULTS: list[Result] = []


def check(label: str, actual, expected) -> bool:
    """Exact equality — use with panchi exact_matrix / exact_vector / Fraction."""
    ok = actual == expected
    RESULTS.append(Result(label, ok, "" if ok else f"expected {expected!r}\n    got      {actual!r}"))
    return ok


def check_true(label: str, condition: bool, detail: str = "") -> bool:
    """A property that must hold (T/F justification, possible/impossible witness)."""
    ok = bool(condition)
    RESULTS.append(Result(label, ok, "" if ok else detail or "condition was False"))
    return ok


def check_close(label: str, actual: float, expected: float, tol: float = 1e-9) -> bool:
    """Approximate equality — only for inherently numerical results such as pan.eigen."""
    ok = abs(actual - expected) <= tol
    RESULTS.append(Result(label, ok, "" if ok else f"expected {expected} ± {tol}, got {actual}"))
    return ok
