"""questions.yaml is the spine: new_session → generate → render_questions → verify → build → validate."""

import datetime as dt
import subprocess
import sys

import pytest
import yaml
from pptx import Presentation

import build_deck
import generate
import new_session
import render_questions
import validate_deck
import verify_runner
from conftest import SCRIPTS
from schemas import SchemaError, load_questions

TF = [
    {
        "id": "tf1",
        "slot": "tf",
        "tags": ["lu", "inverses"],
        "statement": "If A is invertible and A = LU, then A⁻¹ = L⁻¹U⁻¹.",
        "answer": False,
        "justification": "The order reverses: A⁻¹ = U⁻¹L⁻¹.",
        "minutes": 2.5,
    },
    {
        "id": "tf2",
        "slot": "tf",
        "tags": ["lu"],
        "statement": "If A = LU with L unit lower triangular, det A = product of the diagonal of U.",
        "answer": True,
        "justification": "det L = 1.",
        "minutes": 2.5,
    },
]

CHECKS = """
L = pan.exact_matrix([[1, 0], [2, 1]])
U = pan.exact_matrix([[1, 1], [0, 1]])
Li, Ui = pan.inverse(L).inverse, pan.inverse(U).inverse
check_true("tf1 counterexample", pan.inverse(L @ U).inverse != Li @ Ui)
check("tf2 instance", pan.determinant(L @ U), U[0][0] * U[1][1])
"""


def run_script(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], capture_output=True, text=True)


@pytest.fixture
def session(course):
    info = new_session.setup(course, dt.date(2026, 9, 24))
    return course / "sessions" / "2026-09-24", info


def test_new_session_scaffold(course, session):
    folder, info = session
    assert info["session_number"] == 10 and info["week"] == 5
    assert set(info["created"]) == {"questions.yaml", "feedback.md", "build.sh"}
    assert "## Confidence" in (folder / "feedback.md").read_text()
    assert (course / "lessons.md").read_text().startswith("# Lessons — MATH 1554, Fall 2026")
    build_sh = (folder / "build.sh").read_text()
    assert str(folder.resolve()) in build_sh and "cd " not in build_sh  # absolute paths, no cd
    assert f'--template "{(course / "template.pptx").resolve()}"' in build_sh
    assert subprocess.run(["bash", "-n", str(folder / "build.sh")]).returncode == 0
    again = new_session.setup(course, dt.date(2026, 9, 24))
    assert again["created"] == []  # never overwrites


def test_session_number_is_never_inferred(course):
    info = new_session.setup(course, dt.date(2026, 10, 1))
    assert info["session_number"] is None
    assert any("no session number" in n for n in info["notes"])


def test_next_session_date(course):
    from schemas import load_course

    c = load_course(course / "course.yaml")
    assert new_session.next_session_date(c, dt.date(2026, 9, 22)) == dt.date(2026, 9, 24)
    assert new_session.next_session_date(c, dt.date(2026, 9, 25)) == dt.date(2026, 9, 29)  # next Tue from days


def test_full_pipeline(course, session, tmp_path):
    folder, _ = session
    (folder / "questions.yaml").write_text(yaml.safe_dump(TF, allow_unicode=True))
    generate.add(folder, "lu", 1, "easy", {"exists": False})
    qs = load_questions(folder / "questions.yaml")
    assert [q.id for q in qs] == ["tf1", "tf2", "lu1"]
    assert qs[2].generator.seed == "2026-09-24-lu-01" and "lu" in qs[2].tags

    notes = render_questions.render_all(folder, render_math=False)
    assert any("todo() stubs for tf1, tf2" in n for n in notes)
    plan = (folder / "plan.md").read_text()
    assert "### tf1 · True or False?" in plan and "**Answer:** False" in plan
    assert "⚠ planned" in plan  # 2.5 + 2.5 + 5 min is far from 50

    # stubs fail until real checks replace them
    lines, passed = verify_runner.run(folder / "verify.py", folder / "questions.yaml")
    assert not passed and "FAIL tf1 TODO" in "\n".join(lines)

    text = (folder / "verify.py").read_text()
    text = text.replace("todo('tf1')", "").replace("todo('tf2')", "") + CHECKS
    (folder / "verify.py").write_text(text)
    result = run_script("verify_runner.py", folder)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok   lu1 LU exists without swaps" in result.stdout
    assert verify_runner.log_problem(folder) is None

    deck = yaml.safe_load((folder / "deck.yaml").read_text())["slides"]
    assert [s.get("kind") for s in deck] == ["title", "tf", "tf-answers", "warmup"]
    assert deck[0]["text"] == {"title": "Session 10", "subtitle": "2.5 Matrix factorizations"}
    assert deck[2]["states"] == {"mark": ["off", "on"]} and deck[2]["hidden"] is True
    assert "1. tf1: False — The order reverses" in deck[1]["notes"]

    from PIL import Image

    (folder / "math").mkdir(exist_ok=True)
    Image.new("RGBA", (300, 100), (0, 0, 0, 255)).save(folder / "math" / "lu1.png")  # render_math=False above
    out = build_deck.build(folder / "deck.yaml", folder / "deck.pptx", course / "template.pptx", course / "template-map.yaml")
    prs = Presentation(str(out))
    assert len(prs.slides) == 4
    assert validate_deck.validate(out, folder / "deck.yaml", course / "template.pptx", course / "template-map.yaml") == []

    # editing a question after verifying makes the deck fail validation until re-verified
    (folder / "questions.yaml").write_text((folder / "questions.yaml").read_text().replace("2.5", "3"))
    problems = validate_deck.validate(out, folder / "deck.yaml", course / "template.pptx", course / "template-map.yaml")
    assert any("changed since the last verification" in p for p in problems)


def test_coverage_rule(course, session):
    folder, _ = session
    (folder / "questions.yaml").write_text(yaml.safe_dump(TF, allow_unicode=True))
    (folder / "verify.py").write_text(
        "import panchi as pan\nfrom verify_kit import check_true\n"
        "check_true('tf1 counterexample', True)\ncheck_true('tf9 stray', True)\n"
    )
    lines, passed = verify_runner.run(folder / "verify.py", folder / "questions.yaml")
    report = "\n".join(lines)
    assert not passed
    assert "questions with no check: tf2" in report
    assert "unknown question IDs: tf9" in report


def test_schema_errors_name_the_question(tmp_path):
    bad = [dict(TF[0], answer="nope"), dict(TF[1], id="Bad ID")]
    (tmp_path / "questions.yaml").write_text(yaml.safe_dump(bad))
    with pytest.raises(SchemaError) as e:
        load_questions(tmp_path / "questions.yaml")
    assert "tf1: answer must be true/false for slot tf" in str(e.value)
    assert "Bad ID" in str(e.value)
    (tmp_path / "questions.yaml").write_text(yaml.safe_dump([TF[0], TF[0]]))
    with pytest.raises(SchemaError, match="duplicate question ids: tf1"):
        load_questions(tmp_path / "questions.yaml")


def test_plan_keeps_hand_written_text(course, session):
    folder, _ = session
    (folder / "questions.yaml").write_text(yaml.safe_dump(TF, allow_unicode=True))
    (folder / "plan.md").write_text("# Plan\n\nGoals: LU.\n")
    render_questions.render_all(folder, {"plan"})
    render_questions.render_all(folder, {"plan"})
    plan = (folder / "plan.md").read_text()
    assert plan.startswith("# Plan\n\nGoals: LU.")
    assert plan.count("<!-- boared:questions:start -->") == 1


def test_mcq_answer_slide(course, session):
    folder, _ = session
    tmap = yaml.safe_load((course / "template-map.yaml").read_text())
    tmap["slots"]["warmup"] = {"kind": "warmup", "answers": "mcq-answer", "answer_state": "choice"}
    (course / "template-map.yaml").write_text(yaml.safe_dump(tmap))
    q = {
        "id": "w1",
        "slot": "warmup",
        "statement": "Which are triangular?",
        "choices": {"A": "L", "B": "U", "C": "A", "D": "P"},
        "answer": ["A", "B"],
    }
    (folder / "questions.yaml").write_text(yaml.safe_dump([q]))
    render_questions.render_all(folder, {"deck"})
    deck = yaml.safe_load((folder / "deck.yaml").read_text())["slides"]
    assert deck[-1]["states"] == {"choice": {"on": ["A", "B"]}}
    assert "(A) L" in deck[-2]["text"]["body"]
