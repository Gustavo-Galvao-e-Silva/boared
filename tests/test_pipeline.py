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
        "section": "2.5",
        "uses": ["2.5"],
        "tags": ["lu", "inverses"],
        "statement": "If A is invertible and A = LU, then A⁻¹ = L⁻¹U⁻¹.",
        "answer": False,
        "justification": "The order reverses: A⁻¹ = U⁻¹L⁻¹.",
        "source": "from scratch",
        "difficulty": "medium",
        "minutes": 2.5,
    },
    {
        "id": "tf2",
        "slot": "tf",
        "section": "2.5",
        "uses": ["2.5"],
        "tags": ["lu"],
        "statement": "If A = LU with L unit lower triangular, det A = product of the diagonal of U.",
        "answer": True,
        "justification": "det L = 1.",
        "source": "from scratch",
        "difficulty": "easy",
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
        "section": "2.5",
        "uses": ["2.5"],
        "tags": ["lu"],
        "statement": "Which are triangular?",
        "choices": {"A": "L", "B": "U", "C": "A", "D": "P"},
        "answer": ["A", "B"],
        "justification": "L is lower, U is upper triangular.",
        "source": "from scratch",
        "difficulty": "easy",
        "minutes": 2,
    }
    (folder / "questions.yaml").write_text(yaml.safe_dump([q]))
    render_questions.render_all(folder, {"deck"})
    deck = yaml.safe_load((folder / "deck.yaml").read_text())["slides"]
    assert deck[-1]["states"] == {"choice": {"on": ["A", "B"]}}
    assert "(A) L" in deck[-2]["text"]["body"]


# --- schedule check: is each question teachable yet? ---------------------------------


def _add_later_topic(course, prerequisites=None):
    data = yaml.safe_load((course / "course.yaml").read_text())
    data["schedule"].append(
        {
            "week": 6,
            "start": "2026-09-28",
            "sections": ["Determinants", "Cofactor expansion"],
            "sessions": [{"date": "2026-10-01", "number": 11, "sections": ["Cofactor expansion"]}],
        }
    )
    if prerequisites:
        data["prerequisites"] = prerequisites
    (course / "course.yaml").write_text(yaml.safe_dump(data, sort_keys=False))


def _write_checked(folder, questions):
    (folder / "questions.yaml").write_text(yaml.safe_dump(questions, allow_unicode=True))
    (folder / "verify.py").write_text(
        "from verify_kit import check_true\n" + "".join(f"check_true('{q['id']} ok', True)\n" for q in questions)
    )


def test_schedule_fails_a_topic_taught_later(course, session):
    folder, _ = session
    _add_later_topic(course)
    early = dict(TF[1], uses=["2.5", "Determinants"])
    _write_checked(folder, [TF[0], early])
    lines, passed = verify_runner.run(folder / "verify.py", folder / "questions.yaml")
    report = "\n".join(lines)
    assert not passed
    assert "SCHEDULE: tf2 uses 'Determinants', first taught 2026-09-28" in report
    assert "SCHEDULE: tf1" not in report

    # a deliberate preview is a warning the leader approves in plan.md
    _write_checked(folder, [TF[0], dict(early, preview=True)])
    lines, passed = verify_runner.run(folder / "verify.py", folder / "questions.yaml")
    assert passed and any(line.startswith("PREVIEW: tf2 uses 'Determinants'") for line in lines)
    render_questions.render_all(folder, {"plan"})
    assert "Preview — needs the leader's OK:** uses 'Determinants'" in (folder / "plan.md").read_text()


def test_schedule_uses_session_dates_and_labels(course):
    from schemas import load_course

    _add_later_topic(course)
    c = load_course(course / "course.yaml")
    assert c.taught_on("Determinants") == dt.date(2026, 9, 28)  # week start
    assert c.taught_on("cofactor expansion") == dt.date(2026, 10, 1)  # the session that lists it, any case
    assert c.resolve_label("2.5") == "2.5 Matrix factorizations"  # an unambiguous prefix
    assert c.resolve_label("2") is None and c.resolve_label("Eigenvalues") is None


def test_schedule_unknown_topic_and_keyword_backstop(course, session):
    folder, _ = session
    _add_later_topic(course, prerequisites={"Determinants": ["det(", "determinant"]})
    _write_checked(folder, [dict(TF[0], uses=["2.5", "Eigenvalues"]), TF[1]])
    lines, passed = verify_runner.run(folder / "verify.py", folder / "questions.yaml")
    report = "\n".join(lines)
    assert not passed
    assert "SCHEDULE: tf1 uses 'Eigenvalues', which is not one topic" in report
    assert "SCHEDULE: tf2" not in report  # "det A" / "det L" are not the listed keywords
    _write_checked(folder, [dict(TF[0], uses=["2.5", "Eigenvalues"], preview=True)])
    lines, passed = verify_runner.run(folder / "verify.py", folder / "questions.yaml")
    assert not passed  # preview can't excuse an unknown topic
    _write_checked(folder, [TF[0], dict(TF[1], justification="The determinant of L is 1.")])
    lines, passed = verify_runner.run(folder / "verify.py", folder / "questions.yaml")
    assert not passed and "tf2 mentions 'determinant', which belongs to 'Determinants'" in "\n".join(lines)


def test_required_fields(tmp_path):
    for field in ("section", "uses", "tags", "answer", "justification", "source", "difficulty", "minutes"):
        q = {k: v for k, v in TF[0].items() if k != field}
        (tmp_path / "questions.yaml").write_text(yaml.safe_dump([q], allow_unicode=True))
        with pytest.raises(SchemaError, match=f"tf1: {field}: Field required"):
            load_questions(tmp_path / "questions.yaml")
    for field, empty in (("tags", []), ("uses", []), ("justification", " ")):
        (tmp_path / "questions.yaml").write_text(yaml.safe_dump([dict(TF[0], **{field: empty})], allow_unicode=True))
        with pytest.raises(SchemaError, match=f"tf1: {field}:"):
            load_questions(tmp_path / "questions.yaml")
    (tmp_path / "questions.yaml").write_text(yaml.safe_dump([dict(TF[0], uses=["other"])], allow_unicode=True))
    assert load_questions(tmp_path / "questions.yaml")[0].uses == ["2.5", "other"]  # section counts as used


def test_generate_needs_a_section_when_the_session_has_several(course):
    _add_later_topic(course)
    folder = course / "sessions" / "2026-09-29"  # week 6 lists two topics, no session entry
    folder.mkdir()
    with pytest.raises(SchemaError, match="give --section"):
        generate.add(folder, "lu", 1, "easy", {})
    (q,) = generate.add(folder, "lu", 1, "easy", {}, section="Determinants")
    assert q["section"] == "Determinants" and q["uses"] == ["Determinants"]


def test_fill_required_migration(course):
    import migrate_bank

    folder = course / "sessions" / "2026-09-24"
    folder.mkdir()
    old = {"id": "tf1", "slot": "tf", "tags": ["lu"], "statement": "S.", "answer": False, "justification": "J."}
    (folder / "questions.yaml").write_text(yaml.safe_dump([old, {"id": "tf2", "slot": "tf", "statement": "T.", "answer": True}]))
    (course / "bank").mkdir()
    (course / "bank" / "b1.yaml").write_text(yaml.safe_dump(dict(old, id="b1", verified=True)))  # no last_used

    done, todo = migrate_bank.fill_required(course, dry_run=True)
    assert "sessions/2026-09-24/questions.yaml: tf1: filled difficulty, minutes, source, uses, section" in done
    assert yaml.safe_load((folder / "questions.yaml").read_text())[0] == old  # dry run writes nothing

    done, todo = migrate_bank.fill_required(course)
    (tf1, *_rest) = yaml.safe_load((folder / "questions.yaml").read_text())
    assert tf1["section"] == "2.5 Matrix factorizations" and list(tf1)[:4] == ["id", "slot", "section", "uses"]
    assert any("tf2: write justification, tags" in t for t in todo)
    assert any("bank/b1.yaml: b1: write section, uses (no scheduled topic for its date)" in t for t in todo)
