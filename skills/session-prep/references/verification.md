# Verification

Wrong answers in front of students are the failure that matters. Every question in `questions.yaml` must have at least one check, and `verify_runner.py` enforces that. It fails when:
- a check fails, or `verify.py` crashes;
- a question has no check;
- a check label starts with an ID that isn't in `questions.yaml`;
- a `todo("<id>")` stub is left.

It writes `verify.log`, stamped with hashes of `questions.yaml` and `verify.py`. `validate_deck.py`, `bank.py add` and the checkpoint all require a log that **passed and is current**. Editing a question after verifying makes the build fail until you re-verify.

## Where checks live

- **Generated questions** (with a `generator:` block): checked by their generator, from the question's stored `data`. Nothing to write.
- **Everything else**: `sessions/<date>/verify.py`. `render_questions.py` appends a failing `todo("<id>")` stub for each new hand-written question, with the claim and answer as comments. Replace the stub with real checks. Existing checks are never touched.

## verify.py shape

Every label **starts with the question ID**, then says what it checks.

```python
import panchi as pan
from panchi.algorithms import rref
from verify_kit import check, check_true, check_close, check_identity, lu_no_pivot, NoLU, unit_lower, upper

# inv1 — find the inverse
A = pan.exact_matrix([[2, 1], [5, 3]])
check("inv1 inverse", pan.inverse(A).inverse, pan.exact_matrix([[3, -1], [-5, 2]]))

# tf4 — "If A is invertible and A = LU, then A⁻¹ = L⁻¹U⁻¹." (False) — counterexample
L = pan.exact_matrix([[1, 0], [2, 1]])
U = pan.exact_matrix([[1, 1], [0, 1]])
check_true("tf4 counterexample", pan.inverse(L @ U).inverse != pan.inverse(L).inverse @ pan.inverse(U).inverse)

# tf5 — "det(LU) is the product of U's diagonal" (True) — symbolic, for every 3x3
import sympy as sp

check_identity("tf5 det(LU) = prod diag(U)", (unit_lower(3) * upper(3)).det(), sp.prod(upper(3).diagonal()))

# pi2 — possible: a nonzero 2x2 A with A^2 = 0
N = pan.exact_matrix([[0, 1], [0, 0]])
check_true("pi2 witness", N @ N == pan.zero_matrix(2, 2) and N != pan.zero_matrix(2, 2))

# pi3 — impossible: an LU factorization (no swaps) of [[0,1],[1,1]]
try:
    lu_no_pivot(pan.exact_matrix([[0, 1], [1, 1]]))
    check_true("pi3 no LU without swaps", False)
except NoLU:
    check_true("pi3 no LU without swaps", True)
```

## Rules

- **Always** build with `pan.exact_matrix` / `pan.exact_vector` (or string fractions like `"1/3"`). Plain `pan.Matrix` produces floats (`-3.0`) that look wrong on slides.
- `check` = exact equality; `check_true` = a property/witness; `check_close` only for inherently numerical results (`pan.eigen` is iterative). For eigen questions prefer exact: `check("eig3 eigenpair", A @ v, v * 3)`.
- `check_identity` (sympy) proves a symbolic identity for *all* matrices of a size. Use `sym_matrix("a", 3)`, `unit_lower(3)` and `upper(3)` for generic matrices. Prefer it over one instance when a True claim is an algebraic identity.
- **True** claims: check an instance *and* name the theorem in `justification`, or prove the identity symbolically. An instance doesn't prove a universal claim, but it catches misstatements.
- **False** claims and **possible** items: check the counterexample or witness itself.
- **Impossible** items: name the theorem; if a finite demonstration exists (a rank bound, `NoLU`), check it.
- LU follows the course's convention: **no row swaps, L unit lower-triangular** (`lu_no_pivot`). "No LU exists" means elimination needs a swap.
- Word problems: check the solution satisfies the original system and makes sense in context (non-negative, integer where required).
- Any computation shown on a slide (RREF steps, an inverse) must come from panchi output, not be typed by hand. `steps_text(rref(A))` gives the row operations with 1-based labels for speaker notes.

## Nice numbers

Students should spend their time on ideas, not arithmetic. Prefer a generator, which enforces these. By hand:
- Inverses: det = ±1 (integer inverse), ±2 at most.
- RREF: integer pivots, no fractions along the way unless fractions are the point.
- Eigen: integer eigenvalues with integer eigenvectors (A = P D P⁻¹, P unimodular).
- Sizes: 2x2 or 3x3 for hand work; 4x4 only for structure questions (zeros, repeated columns).

Check the "nice" property too when it matters, e.g. `check("inv1 det", pan.determinant(A), 1)`.

## Other subjects

panchi only covers linear algebra. For calculus, differential equations or probability, verify with sympy through the same `verify_kit` checks (`check_identity` works for scalars too), and say in `plan.md` that verification used sympy.
