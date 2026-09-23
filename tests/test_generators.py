"""Property tests: every accepted candidate passes validate() and its own emitted checks.

BOARED_SEEDS sets how many seeds each case runs (default 1000, as in the plan).
"""

import os

import pytest

import generators
import verify_kit
from schemas import Question

SEEDS = int(os.environ.get("BOARED_SEEDS", "1000"))

CASES = [
    ("rref", "medium", {}),
    ("rref", "easy", {"free": 1}),
    ("rref", "hard", {"consistent": False}),
    ("rref", "medium", {"augmented": False, "rows": 3, "cols": 5, "rank": 2}),
    ("inverse", "medium", {}),
    ("inverse", "hard", {"n": 3}),
    ("inverse", "easy", {"invertible": False}),
    ("eigen", "medium", {}),
    ("eigen", "hard", {"n": 3, "kind": "repeated"}),
    ("eigen", "medium", {"kind": "defective"}),
    ("eigen", "medium", {"kind": "complex"}),
    ("span", "medium", {"k": 4}),
    ("span", "easy", {"k": 2}),
    ("lu", "medium", {}),
    ("lu", "medium", {"exists": False}),
    ("lu", "easy", {"n": 2, "exists": False}),
]

# eigen uses sympy and is ~20x slower per candidate; run it on a tenth of the seeds
SLOW = {"eigen": 10}


@pytest.mark.parametrize(("name", "difficulty", "params"), CASES, ids=[f"{n}-{d}-{p}" for n, d, p in CASES])
def test_accepted_candidates_pass_their_checks(name, difficulty, params):
    for i in range(SEEDS // SLOW.get(name, 1)):
        seed = f"test-{name}-{i}"
        q = Question.model_validate(generators.make_question(name, seed, difficulty, f"{name}{i}", **params))
        c = generators.make_candidate(name, seed, difficulty, **params)
        assert generators.module(name).validate(c) == [], seed
        verify_kit.RESULTS.clear()
        generators.run_checks(q)
        failed = [r for r in verify_kit.RESULTS if not r.ok]
        assert verify_kit.RESULTS and not failed, (seed, [(r.label, r.detail) for r in failed])
        assert all(r.label.startswith(q.id + " ") for r in verify_kit.RESULTS)


def test_seed_reproduces_question():
    a = generators.make_question("rref", "2026-09-24-rref-01", "medium", "rref1", free=1)
    b = generators.make_question("rref", "2026-09-24-rref-01", "medium", "rref1", free=1)
    assert a == b
    assert generators.make_question("rref", "2026-09-24-rref-02", "medium", "rref1")["data"] != a["data"]


def test_checks_catch_a_hand_edited_answer():
    q = generators.make_question("inverse", "s", "medium", "inv1")
    q["answer"]["inverse"][0][0] += 1
    verify_kit.RESULTS.clear()
    generators.run_checks(Question.model_validate(q))
    assert any(r.label == "inv1 inverse" and not r.ok for r in verify_kit.RESULTS)


def test_easy_rref_is_integer_only():
    from fractions import Fraction

    import panchi as pan
    from panchi.algorithms import rref

    for i in range(50):
        q = generators.make_question("rref", f"int-{i}", "easy", "r1")
        red = rref(pan.exact_matrix(q["data"]["matrix"]))
        m = red.original
        for step in red.steps:
            m = step.apply(m)
            assert all(Fraction(x).denominator == 1 for row in m.to_list() for x in row)


def test_bad_params_are_reported():
    with pytest.raises(ValueError, match="rank 5 impossible"):
        generators.make_candidate("rref", "s", "medium", rank=5)
    with pytest.raises(generators.GenerationError, match="no generator 'qr'"):
        generators.make_candidate("qr", "s")


def test_lu_no_pivot():
    import panchi as pan

    L, U = verify_kit.lu_no_pivot(pan.exact_matrix([[2, 1], [4, 3]]))
    assert L == pan.exact_matrix([[1, 0], [2, 1]]) and U == pan.exact_matrix([[2, 1], [0, 1]])
    with pytest.raises(verify_kit.NoLU):
        verify_kit.lu_no_pivot(pan.exact_matrix([[0, 1], [1, 1]]))
    # zero pivot with only zeros below: no swap needed, LU exists
    L, U = verify_kit.lu_no_pivot(pan.exact_matrix([[0, 1], [0, 1]]))
    assert L @ U == pan.exact_matrix([[0, 1], [0, 1]])


def test_symbolic_identity():
    import sympy as sp

    verify_kit.RESULTS.clear()
    L, U = verify_kit.unit_lower(3), verify_kit.upper(3)
    assert verify_kit.check_identity("lu3 det(LU)", (L * U).det(), sp.prod(U.diagonal()))
    assert not verify_kit.check_identity("lu3 wrong", (L * U).det(), U[0, 0])
