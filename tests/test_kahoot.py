"""Kahoot export: question mapping, blockers, payload, record, and bank bookkeeping."""

import datetime as dt
import json

import pytest
import yaml

import bank
import kahoot
from conftest import SCRIPTS
from schemas import Question, SchemaError, load_bank_entry, load_course, parse_questions
from test_tools import run_script

BASE = {
    "section": "2.5",
    "uses": ["2.5"],
    "tags": ["lu"],
    "justification": "Because.",
    "source": "from scratch",
    "difficulty": "medium",
    "minutes": 2,
}


def q(**fields) -> dict:
    return BASE | fields


def tf(qid="tf1", **fields):
    return q(
        **{"id": qid, "slot": "tf", "statement": "Every square matrix has an **LU** factorization.", "answer": False} | fields
    )


def pi(qid="pi1", **fields):
    return q(**{"id": qid, "slot": "pi", "statement": "A 3×3 matrix with LU = A and det(U) = 0.", "answer": "possible"} | fields)


def mcq(qid="w1", **fields):
    defaults = {"statement": "Which are triangular?", "choices": {"A": "L", "B": "U", "C": "A"}, "answer": ["A", "B"]}
    return q(**{"id": qid, "slot": "warmup"} | defaults | fields)


def problem(qid="p1", **fields):
    return q(**{"id": qid, "slot": "problem", "statement": "Find an LU factorization of A.", "answer": "see notes"} | fields)


def question(raw: dict) -> Question:
    (parsed,) = parse_questions([raw])
    return parsed


def make_session(course, questions, date="2026-09-24", verify=True):
    folder = course / "sessions" / date
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "questions.yaml").write_text(yaml.safe_dump(questions, allow_unicode=True))
    checks = "".join(f"check_true('{x['id']} ok', True)\n" for x in questions)
    (folder / "verify.py").write_text("from verify_kit import check_true\n" + checks)
    if verify:
        assert run_script("verify_runner.py", folder).returncode == 0
    return folder


# --- mapping ---------------------------------------------------------------------------


def test_item_shapes():
    assert kahoot.item(question(tf())) == {
        "type": "true_false",
        "question": "Every square matrix has an LU factorization.",  # markup removed
        "time": 30000,
        "correct": False,
    }
    assert kahoot.item(question(pi(difficulty="easy")))["choices"] == [
        {"answer": "Possible", "correct": True},
        {"answer": "Impossible", "correct": False},
    ]
    item = kahoot.item(question(mcq(kahoot={"time": 45, "choices": {"C": "A itself"}})))
    assert item["type"] == "quiz" and item["time"] == 45000
    assert item["choices"] == [
        {"answer": "L", "correct": True},
        {"answer": "U", "correct": True},
        {"answer": "A itself", "correct": False},
    ]


def test_plain_text():
    assert kahoot.plain("If **A** is {{orange|invertible}}\n  then   A⁻¹ exists.") == "If A is invertible then A⁻¹ exists."


@pytest.mark.parametrize(
    "raw, reason",
    [
        (problem(), "slot problem without choices"),
        (tf(latex="A = I"), "add kahoot.question"),
        (tf(statement="x" * 121), "121 characters"),
        (mcq(choices={k: k for k in "ABCDEFG"}, answer="A"), "7 choices"),
        (mcq(choices={"A": "y" * 76, "B": "U"}, answer="A"), "add kahoot.choices"),
        (tf(kahoot={"include": False}), "include is false"),
    ],
)
def test_blockers(raw, reason):
    assert reason in kahoot.blocker(question(raw))


def test_overrides_unblock():
    assert kahoot.blocker(question(tf(latex="A = I", kahoot={"question": "A = I is invertible."}))) is None
    assert kahoot.blocker(question(tf(statement="x" * 121, kahoot={"question": "Short."}))) is None
    assert kahoot.blocker(question(mcq(choices={"A": "y" * 76, "B": "U"}, answer="A", kahoot={"choices": {"A": "y"}}))) is None
    assert kahoot.blocker(question(problem(choices={"A": "1", "B": "2"}, answer="A"))) is None


def test_schema_rejects_bad_kahoot_fields():
    for raw, msg in [
        (tf(kahoot={"time": 25}), "time must be one of"),
        (tf(kahoot={"question": "x" * 121}), "at most 120"),
        (mcq(kahoot={"choices": {"Z": "nope"}}), "not among the question's choices"),
        (mcq(kahoot={"choices": {"A": "y" * 76}}), "longer than 75"),
    ]:
        with pytest.raises(SchemaError, match=msg):
            parse_questions([raw])


# --- payload and record -----------------------------------------------------------------


def test_payload(course):
    folder = make_session(course, [tf(), pi(), mcq(), problem()])
    lines = kahoot.write_payload(folder)
    assert "3 questions, creates a new Kahoot" in lines[0]
    assert lines[1] == "included: tf1, pi1, w1"
    assert lines[2].startswith("skipped p1: slot problem")
    payload = json.loads((folder / kahoot.PAYLOAD).read_text())
    assert payload["title"] == "MATH 1554 — Linear Algebra — Session 10"
    assert payload["language"] == "English" and "folderId" not in payload and "uuid" not in payload
    assert [x.get("type") for x in payload["questions"]] == ["true_false", "quiz", "quiz"]


def test_payload_uses_course_settings(course):
    data = yaml.safe_load((course / "course.yaml").read_text())
    data["kahoot"] = {"folder": "ws-1", "language": "Português"}
    (course / "course.yaml").write_text(yaml.safe_dump(data, allow_unicode=True))
    assert load_course(course / "course.yaml").kahoot.folder == "ws-1"
    payload, _, _ = kahoot.build(make_session(course, [tf()]))
    assert payload["folderId"] == "ws-1" and payload["language"] == "Português"


def test_payload_refuses_unverified(course):
    folder = make_session(course, [tf()], verify=False)
    with pytest.raises(SchemaError, match="unverified"):
        kahoot.build(folder)
    assert run_script("verify_runner.py", folder).returncode == 0
    (folder / "questions.yaml").write_text(yaml.safe_dump([tf(answer=True)]))
    with pytest.raises(SchemaError, match="changed since the last verification"):
        kahoot.build(folder)


def test_explicit_block_must_export(course):
    folder = make_session(course, [tf(), problem(kahoot={"time": 30})])
    with pytest.raises(SchemaError, match="p1: has a kahoot: block"):
        kahoot.build(folder)
    folder = make_session(course, [problem()], date="2026-09-22")
    with pytest.raises(SchemaError, match="no question can go into a Kahoot"):
        kahoot.build(folder)


def test_record_and_update(course):
    folder = make_session(course, [tf(), pi()])
    kahoot.write_payload(folder)
    assert kahoot.record(folder, "u-1", "https://create.kahoot.it/edit/u-1") == [f"wrote {folder / 'kahoot.yaml'}"]
    data = yaml.safe_load((folder / "kahoot.yaml").read_text())
    assert data["uuid"] == "u-1" and data["questions"] == ["tf1", "pi1"]
    assert data["exported"] == dt.date.today().isoformat()

    kahoot.write_payload(folder)  # a re-export replaces the same Kahoot
    assert json.loads((folder / kahoot.PAYLOAD).read_text())["uuid"] == "u-1"
    kahoot.write_payload(folder, new=True)
    assert "uuid" not in json.loads((folder / kahoot.PAYLOAD).read_text())


def test_record_refuses_stale_payload(course):
    folder = make_session(course, [tf()])
    kahoot.write_payload(folder)
    make_session(course, [tf(statement="Changed.")])
    with pytest.raises(SchemaError, match="changed since kahoot.payload.json"):
        kahoot.record(folder, "u-1")


def test_bank_kahoot_uses(course):
    first = make_session(course, [tf(), problem()], date="2026-09-22")
    kahoot.write_payload(first)
    kahoot.record(first, "u-1")
    bank.add(first, None)
    assert load_bank_entry(course / "bank" / "tf1.yaml").kahoot_uses == 1
    assert load_bank_entry(course / "bank" / "p1.yaml").kahoot_uses == 0

    found = bank.find(course, ["lu"], None, dt.date(2026, 12, 1), 0, kahoot=True)
    assert [e.id for e in found] == ["tf1"]

    later = course / "sessions" / "2026-09-24"
    later.mkdir()
    (later / "questions.yaml").write_text("[]\n")
    bank.use(later, "tf1", "tf9")
    raw = yaml.safe_load((later / "questions.yaml").read_text())
    assert "kahoot_uses" not in raw[0]  # bank bookkeeping stays in the bank
    make_session(course, raw, date="2026-09-24")
    kahoot.write_payload(later)
    assert "bank/tf1.yaml: kahoot_uses 2" in kahoot.record(later, "u-2")
    kahoot.record(later, "u-2")  # recording the same Kahoot again doesn't count twice
    assert load_bank_entry(course / "bank" / "tf1.yaml").kahoot_uses == 2


def test_cli(course):
    folder = make_session(course, [tf()])
    out = run_script("kahoot.py", "payload", folder)
    assert out.returncode == 0 and "included: tf1" in out.stdout
    out = run_script("kahoot.py", "record", folder, "--uuid", "u-1")
    assert out.returncode == 0 and (folder / "kahoot.yaml").exists()
    assert (SCRIPTS / "kahoot.py").exists()
