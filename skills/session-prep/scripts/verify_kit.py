"""Assertions for a session's verify.py. Run it through verify_runner.py.

    import panchi as pan
    from verify_kit import check, check_true, check_close, todo

    A = pan.exact_matrix([[2, 1], [5, 3]])
    check("inv1 inverse", pan.inverse(A).inverse, pan.exact_matrix([[3, -1], [-5, 2]]))
    check_true("pi2 witness: A^2 = 0 but A != 0", A2 @ A2 == pan.zero_matrix(2, 2) and A2 != pan.zero_matrix(2, 2))
    check_close("eig3 eigenvalue", max(pan.eigen(B).eigenvalues), 3)
    todo("tf4")                          # stub written by render_questions.py: fails until replaced

Every label starts with the question ID from questions.yaml. verify_runner.py
fails the run if a question has no check or a label names an unknown ID.

Every check records a result instead of stopping, so one run reports every
wrong answer at once.

Helpers:
    lu_no_pivot(A)            Doolittle LU (unit lower L, no row swaps) or raises NoLU
    check_identity(label, lhs, rhs)   symbolic identity with sympy (matrices or scalars)
    sym_matrix("a", 3), unit_lower(3), upper(3)   generic symbolic matrices for such claims
    steps_text(reduction)     panchi's row operations as 1-based text for speaker notes
"""

from __future__ import annotations

import re
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


def todo(qid: str, what: str = "") -> bool:
    """Placeholder for a question whose check hasn't been written. Always fails."""
    RESULTS.append(Result(f"{qid} TODO", False, what or "no check written yet — replace todo() with a real check"))
    return False


# --- LU without pivoting ---------------------------------------------------------------


class NoLU(ValueError):
    """The matrix has no LU factorisation without row swaps."""


def lu_no_pivot(A):
    """Doolittle LU as taught: L unit lower-triangular, U echelon, no row swaps.

    Returns (L, U) with L @ U == A, or raises NoLU when elimination meets a zero
    pivot with a non-zero entry below it. Uses panchi's ``lu(A, pivoting="none")``
    when available.
    """
    import panchi as pan

    if hasattr(pan, "lu"):
        try:
            d = pan.lu(A, pivoting="none")
            return d.lower, d.upper
        except TypeError:
            pass  # older panchi without the pivoting argument
        except ValueError as e:
            raise NoLU(str(e)) from None
    from panchi.algorithms.decompositions import lu
    from panchi.algorithms.row_operations import RowSwap

    d = lu(A)  # panchi only swaps when it meets a zero pivot
    swaps = [s for s in d.steps if isinstance(s, RowSwap)]
    if swaps:
        raise NoLU(f"elimination needs a row swap ({swaps[0]}), so A has no LU factorisation without pivoting")
    return d.lower, d.upper


# --- symbolic checks (sympy) --------------------------------------------------------------


def sym_matrix(name: str, n: int, m: int | None = None):
    """A generic n×m sympy matrix with entries name_ij."""
    import sympy as sp

    return sp.Matrix(n, m or n, lambda i, j: sp.Symbol(f"{name}_{i + 1}{j + 1}"))


def unit_lower(n: int, name: str = "l"):
    import sympy as sp

    return sp.Matrix(n, n, lambda i, j: 1 if i == j else (sp.Symbol(f"{name}_{i + 1}{j + 1}") if i > j else 0))


def upper(n: int, name: str = "u"):
    import sympy as sp

    return sp.Matrix(n, n, lambda i, j: sp.Symbol(f"{name}_{i + 1}{j + 1}") if i <= j else 0)


def check_identity(label: str, lhs, rhs) -> bool:
    """Symbolic identity, e.g. check_identity("lu3 det", (L*U).det(), prod(U.diagonal()))."""
    import sympy as sp

    diff = sp.simplify(sp.Matrix(lhs) - sp.Matrix(rhs)) if hasattr(lhs, "shape") else sp.simplify(lhs - rhs)
    ok = diff.is_zero_matrix if hasattr(diff, "is_zero_matrix") else diff == 0
    RESULTS.append(Result(label, bool(ok), "" if ok else f"lhs - rhs simplifies to {diff}"))
    return bool(ok)


# --- working for solution slides --------------------------------------------------------------

_ROW = re.compile(r"R(\d+)")


def steps_text(reduction) -> list[str]:
    """panchi's row operations with 1-based labels, e.g. 'R2 -> R2 + (-2) * R1'."""
    return [_ROW.sub(lambda m: f"R{int(m.group(1)) + 1}", str(step)) for step in reduction.steps]
