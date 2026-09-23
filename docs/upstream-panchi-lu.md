# Upstream change for panchi: `lu(A, pivoting="none")`

Status: **proposed** (plan item 3.5). boared already works without it: `verify_kit.lu_no_pivot` uses `panchi.lu(A, pivoting="none")` when that exists, and otherwise falls back to `panchi.algorithms.decompositions.lu` and rejects any `RowSwap` in its steps.

## Why

The course teaches Doolittle LU: no row swaps, L unit lower-triangular, and "A has no LU factorization" when elimination meets a zero pivot with a non-zero entry below it. panchi's `lu` always returns `P, L, U` with `PA = LU`, so "no LU exists" questions can't be checked directly.

## Two findings in panchi 2.0.0

1. `lu` isn't exported at the top level: `panchi.lu` raises `AttributeError`, and you need `from panchi.algorithms.decompositions import lu`.
2. The `lu` docstring says it uses partial pivoting ("swaps rows … to place the largest available entry in the pivot column"). But `ref` → `_swap_pivot` only swaps when the pivot is exactly zero (or within `tolerance`), and then takes the *first* non-zero row below, not the largest. The behaviour is fine for teaching, but the docstring is wrong. The consequence: `lu(A).permutation == I` exactly when Doolittle LU exists.

## Proposed patch (`panchi/algorithms/decompositions.py`)

```python
def lu(matrix: Matrix, pivoting: str = "zero") -> LUDecomposition:
    """
    Compute an LU decomposition of a square matrix.

    pivoting : {"zero", "none"}
        "zero" (default): swap rows only when a pivot is zero, recording the swaps
        in P so that P @ matrix == L @ U.
        "none": Doolittle LU as usually taught — no row swaps, L unit lower-triangular,
        matrix == L @ U, P = I. Raises ValueError when elimination meets a zero pivot
        with a non-zero entry below it (no LU factorization exists without pivoting).
    """
    if pivoting not in ("zero", "none"):
        raise ValueError(f"pivoting must be 'zero' or 'none', not {pivoting!r}")
    matrix_ref = ref(matrix)
    steps = matrix_ref.steps
    if pivoting == "none":
        swap = next((s for s in steps if isinstance(s, RowSwap)), None)
        if swap is not None:
            raise ValueError(
                f"zero pivot in row {swap.a} with a non-zero entry below it: "
                "no LU factorization without row swaps"
            )
    n = matrix.rows
    return LUDecomposition(matrix, _calculate_l(n, steps), matrix_ref.result, _calculate_p(n, steps), steps)
```

Also: `from panchi.algorithms.decompositions import lu` in `panchi/__init__.py`, add `"lu"` to `__all__`, and fix the docstring to describe zero-pivot swapping. (Also accept `"partial"` as a deprecated alias for `"zero"` if anyone depends on the word.)

## Tests

```python
def test_lu_no_pivoting():
    A = exact_matrix([[2, 1], [4, 3]])
    d = lu(A, pivoting="none")
    assert d.lower @ d.upper == A and d.permutation == identity(2)

def test_lu_no_pivoting_needs_swap():
    with pytest.raises(ValueError, match="no LU factorization"):
        lu(exact_matrix([[0, 1], [1, 1]]), pivoting="none")

def test_lu_zero_pivot_with_zeros_below_is_fine():
    A = exact_matrix([[0, 1], [0, 1]])
    d = lu(A, pivoting="none")
    assert d.lower @ d.upper == A
```

Once released, bump `panchi>=` in `pyproject.toml` and the scripts' PEP 723 headers. `verify_kit.lu_no_pivot` picks it up automatically.
