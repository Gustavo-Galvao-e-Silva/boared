# Verification

Wrong answers in front of students are the failure that matters. Every answer and every claim in plan.md gets a check in `sessions/<date>/verify.py`, run through `scripts/verify_runner.py`.

## verify.py shape

```python
import panchi as pan
from panchi.algorithms import rref
from verify_kit import check, check_true, check_close

# Q1 — find the inverse
A = pan.exact_matrix([[2, 1], [5, 3]])
check("Q1 inverse", pan.inverse(A).inverse, pan.exact_matrix([[3, -1], [-5, 2]]))

# Q4 — T/F: "If A is 3x3 with two equal columns, A is not invertible." (True)
B = pan.exact_matrix([[1, 1, 2], [0, 0, 1], [3, 3, 4]])
check_true("Q4 instance agrees", not pan.is_invertible(B))

# Q5 — T/F: "If AB = AC then B = C." (False) — counterexample
A5 = pan.exact_matrix([[1, 0], [0, 0]])
B5 = pan.exact_matrix([[1, 2], [3, 4]])
C5 = pan.exact_matrix([[1, 2], [5, 6]])
check_true("Q5 counterexample", A5 @ B5 == A5 @ C5 and B5 != C5)

# Q7 — possible: nonzero 2x2 A with A^2 = 0
N = pan.exact_matrix([[0, 1], [0, 0]])
check_true("Q7 witness", N @ N == pan.zero_matrix(2, 2) and N != pan.zero_matrix(2, 2))
```

Label checks with the question number so a FAIL points straight at plan.md.

## Rules

- **Always** build with `pan.exact_matrix` / `pan.exact_vector` (or string fractions like `"1/3"`). Plain `pan.Matrix` produces floats (`-3.0`) that look wrong on slides.
- `check` = exact equality; `check_true` = a property/witness; `check_close` only for inherently numerical results (`pan.eigen` is iterative and returns floats). For eigen questions prefer an exact check: `check("Q9 eigenpair", A @ v, v * 3)`.
- **True** claims: check at least one concrete instance *and* name the theorem in plan.md — an instance doesn't prove a universal claim, it catches misstatements.
- **False** claims and **possible** items: the counterexample/witness itself is checked.
- **Impossible** items: name the theorem; if there's a finite search that demonstrates it (e.g. rank bound), check it.
- Word problems: check the solution satisfies the original system and makes sense in context (non-negative, integer where required).
- Any computation shown on a slide (RREF steps, an inverse) must come from panchi output, not be typed by hand.

## Nice numbers

Students should spend their time on ideas, not arithmetic:
- Inverses: pick det = ±1 (integer inverse) or det = ±2 at most.
- RREF: integer pivots, ≤ 3 steps per column; avoid fractions unless the point is fractions.
- Eigen: integer eigenvalues with integer eigenvectors (build A = P D P⁻¹ from integer P with det ±1).
- Sizes: 2x2 or 3x3 for hand work; 4x4 only for structure (zeros, repeated columns) questions.

Check the "nice" property too when it matters, e.g. `check("Q1 det", pan.determinant(A), 1)`.

## Other subjects

panchi only covers linear algebra. For calculus / diff-eq / probability, verify with sympy (`uv run --with sympy ...`) using the same `verify_kit` checks, and state in plan.md that verification used sympy.
