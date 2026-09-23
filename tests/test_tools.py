"""Confidence, bank, exam search, template inspection, validation, delivery, doctor, diff."""

import datetime as dt
import subprocess
import sys

import pytest
import yaml
from pptx import Presentation

import bank
import build_deck
import confidence
import inspect_template
import migrate_bank
import new_session
import search_exams
import validate_deck
from conftest import SCRIPTS, TEMPLATE_MAP
from schemas import load_bank_entry, load_questions


def run_script(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], capture_output=True, text=True)


# --- confidence ---------------------------------------------------------------------


def test_confidence_summary():
    start, end = confidence.parse_counts("0,2,5,3,1"), confidence.parse_counts("3 1 0 1 4")
    assert start.n == 11 and round(start.mean, 2) == 3.27
    assert end.split and not start.split
    text = confidence.section(start, end, "LU")
    assert "Start: 1×0 2×2 3×5 4×3 5×1   (n = 11)" in text
    assert "Mean start 3.27 → end 3.22 (shift -0.05)" in text
    assert "split room" in text


def test_confidence_low_flag():
    assert confidence.verdict(confidence.Tally([0, 0, 0, 0, 0]), confidence.Tally([4, 4, 1, 0, 0])) == "low end confidence"
    with pytest.raises(ValueError):
        confidence.parse_counts("1,2,3")


def test_confidence_history_from_feedback(course):
    for date, end in (("2026-09-22", "1×3 2×4 3×1 4×0 5×0"), ("2026-09-24", "1×_ 2×_ 3×_ 4×_ 5×_")):
        folder = course / "sessions" / date
        folder.mkdir(parents=True)
        (folder / "feedback.md").write_text(
            f"## Confidence\nTopic asked: LU\nStart: 1×1 2×2 3×3 4×2 5×0   (n = 8)\nEnd:   {end}   (n = 8)\n\n## Lessons extracted\n"
        )
    rows = confidence.history(course)
    assert len(rows) == 1  # the unfilled template is ignored
    assert rows[0]["flag"] == "low end confidence" and rows[0]["topic"] == "LU"
    info = new_session.setup(course, dt.date(2026, 9, 29))
    assert info["latest_confidence"]["date"] == "2026-09-22"


# --- bank ------------------------------------------------------------------------------


def _session_with_questions(course, date="2026-09-24"):
    folder = course / "sessions" / date
    folder.mkdir(parents=True, exist_ok=True)
    q = {"id": "tf1", "slot": "tf", "tags": ["lu"], "statement": "Every square matrix has an LU factorization.", "answer": False}
    (folder / "questions.yaml").write_text(yaml.safe_dump([q]))
    (folder / "verify.py").write_text(
        "import panchi as pan\nfrom verify_kit import check_true, lu_no_pivot, NoLU\n"
        "try:\n    lu_no_pivot(pan.exact_matrix([[0, 1], [1, 0]]))\n    ok = False\nexcept NoLU:\n    ok = True\n"
        "check_true('tf1 counterexample', ok)\n"
    )
    return folder


def test_bank_add_find_use(course):
    folder = _session_with_questions(course)
    # not verified yet → promoted as unverified
    (line,) = bank.add(folder, None)
    assert "unverified" in line
    assert load_bank_entry(course / "bank" / "tf1.yaml").verified is False

    assert run_script("verify_runner.py", folder).returncode == 0
    bank.add(folder, None)
    entry = load_bank_entry(course / "bank" / "tf1.yaml")
    assert entry.verified and entry.last_used == dt.date(2026, 9, 24) and entry.answer is False

    assert [e.id for e in bank.find(course, ["lu"], "tf", dt.date(2026, 12, 1), 0)] == ["tf1"]
    assert bank.find(course, ["lu"], "tf", dt.date(2026, 12, 1), 3) == []  # used in a recent session
    assert bank.find(course, ["eigen"], None, dt.date(2026, 12, 1), 0) == []

    later = course / "sessions" / "2026-10-01"
    later.mkdir()
    (later / "questions.yaml").write_text("[]\n")
    assert "added tf7 from bank/tf1.yaml" in bank.use(later, "tf1", "tf7")
    (q,) = load_questions(later / "questions.yaml")
    assert q.id == "tf7" and q.source == "bank:tf1" and q.answer is False
    entry = load_bank_entry(course / "bank" / "tf1.yaml")
    assert entry.times_used == 2 and entry.last_used == dt.date(2026, 10, 1)


def test_bank_id_clash_gets_date(course):
    folder = _session_with_questions(course)
    bank.add(folder, None)
    other = _session_with_questions(course, "2026-10-01")
    (other / "questions.yaml").write_text(
        yaml.safe_dump([{"id": "tf1", "slot": "tf", "statement": "Different.", "answer": True}])
    )
    (line,) = bank.add(other, None)
    assert "bank/tf1-2026-10-01.yaml" in line


def test_migrate_bank(tmp_path):
    (tmp_path / "bank").mkdir()
    (tmp_path / "bank" / "example-tf-cancellation.md").write_text(
        '---\ntopics: [inverses]\ntype: tf\nanswer: "False — A = [[1,0],[0,0]] gives AB = AC."\n'
        "verified: true\nlast_used: 2026-09-23\n---\nIf AB = AC and A ≠ 0, then B = C.\n"
    )
    (tmp_path / "bank" / "broken.md").write_text("no front matter")
    result = run_script("migrate_bank.py", tmp_path)
    assert "example-tf-cancellation.md → example-tf-cancellation.yaml" in result.stdout
    assert "skipped broken.md" in result.stdout and result.returncode == 1
    entry = load_bank_entry(tmp_path / "bank" / "example-tf-cancellation.yaml")
    assert entry.answer is False and entry.justification.startswith("A = [[1,0],[0,0]]")
    assert (tmp_path / "bank" / "_migrated_md" / "example-tf-cancellation.md").exists()


def test_split_answer():
    assert migrate_bank.split_answer("Possible: [[0,1],[0,0]]", "pi") == ("possible", "[[0,1],[0,0]]")
    assert migrate_bank.split_answer("True", "tf") == (True, "")
    assert migrate_bank.split_answer("x = 3", "problem") == ("x = 3", "")


# --- exams -------------------------------------------------------------------------------


def test_search_exams(tmp_path):
    (tmp_path / "exams").mkdir()
    (tmp_path / "exams" / "midterm1.txt").write_text(
        "1. Compute the inverse of A.\n\n2. (a) Find an LU factorization of A.\n   (b) Use it to solve Ax = b.\nProblem 3 Show that PA = LU.\n"
    )
    hits = search_exams.search(["LU"], sorted((tmp_path / "exams").glob("*")))
    assert [h.heading for h in hits] == ["2. (a) Find an LU factorization of A.", "Problem 3 Show that PA = LU."]
    assert search_exams.search(["eigen"], sorted((tmp_path / "exams").glob("*"))) == []


# --- template inspection ---------------------------------------------------------------------


def test_inspect_template_draft(template):
    slides = inspect_template.describe(template)
    assert [s["number"] for s in slides] == [1, 2, 3, 4, 5, 6]
    assert slides[3]["hidden"] and slides[5]["hidden"]
    assert slides[1]["notes"] == "Warm-up: brain dump"
    tf = next(s for s in slides[2]["shapes"] if "table" in s)
    assert tf["table"] == {"rows": 3, "cols": 2, "header": ["#", "Statement"]}
    assert not any(s["name"] == "Picture 4" for s in slides[1]["shapes"])  # decorative logo skipped

    draft = inspect_template.draft_map(template, slides)
    kinds = draft["kinds"]
    assert {"title", "warmup", "tf", "tf-answers"} <= set(kinds)
    assert kinds["warmup"]["fields"]["title"] and kinds["warmup"]["math_area"]
    assert kinds["tf-answers"]["hidden"] is True
    assert set(kinds["tf-answers"]["states"]["mark"]) == {"cells", "on", "off"}
    assert ["tf", "tf-answers"] in draft["pairs"]
    assert draft["slots"]["tf"]["answers"] == "tf-answers" and draft["slots"]["tf"]["table"] == "statements"


# --- validation --------------------------------------------------------------------------------


def test_validate_deck_catches_problems(tmp_path, template):
    (tmp_path / "template-map.yaml").write_text(yaml.safe_dump(TEMPLATE_MAP))
    (tmp_path / "deck.yaml").write_text(yaml.safe_dump({"slides": [{"kind": "tf"}, {"kind": "facilitator"}]}))
    out = build_deck.build(tmp_path / "deck.yaml", tmp_path / "deck.pptx", template, tmp_path / "template-map.yaml")
    problems = validate_deck.validate(out, tmp_path / "deck.yaml", template, tmp_path / "template-map.yaml")
    assert any("placeholder text '[Statement 1]'" in p for p in problems)

    prs = Presentation(str(out))
    build_deck.set_hidden(prs.slides[1], False)
    prs.save(str(out))
    problems = validate_deck.validate(out, tmp_path / "deck.yaml", template, tmp_path / "template-map.yaml")
    assert any("slide 2: hidden is False, spec says True" in p for p in problems)

    (tmp_path / "deck.yaml").write_text(yaml.safe_dump({"slides": [{"kind": "tf"}]}))
    problems = validate_deck.validate(out, tmp_path / "deck.yaml")
    assert any("2 slides but deck.yaml has 1" in p for p in problems)


def test_placeholder_pattern():
    assert validate_deck.PLACEHOLDER.search("[Insert statement]")
    assert not validate_deck.PLACEHOLDER.search("v = [1, 2]")
    assert not validate_deck.PLACEHOLDER.search("[A | b]")


# --- delivery and doctor ---------------------------------------------------------------------------


def test_deliver_options_and_base64(course, tmp_path):
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"x" * 2048)
    result = run_script("deliver.py", deck, "--course", course, "--options")
    assert "base64  → 2 KB deck" in result.stdout
    assert run_script("deliver.py", deck, "--course", course, "--mode", "base64").returncode == 0
    assert (tmp_path / "deck.pptx.b64").exists()
    big = run_script("deliver.py", deck, "--course", course, "--mode", "base64", "--max-kb", "1")
    assert big.returncode != 0 and "too big" in big.stderr
    no_local = run_script("deliver.py", deck, "--course", course, "--mode", "copy")
    assert "set drive_local" in no_local.stderr


def test_deliver_copy(course, tmp_path):
    drive = tmp_path / "Drive" / "PLUS"
    drive.mkdir(parents=True)
    data = yaml.safe_load((course / "course.yaml").read_text())
    data["drive_local"] = str(drive)
    (course / "course.yaml").write_text(yaml.safe_dump(data))
    deck = course / "sessions" / "2026-09-24" / "deck.pptx"
    deck.parent.mkdir(parents=True)
    deck.write_bytes(b"deck")
    assert run_script("deliver.py", deck, "--course", course, "--mode", "copy").returncode == 0
    assert (drive / "2026-09-24 deck.pptx").read_bytes() == b"deck"
    again = run_script("deliver.py", deck, "--course", course, "--mode", "copy")
    assert again.returncode != 0 and "--force" in again.stderr


def test_doctor_runs():
    result = run_script("doctor.py")
    assert result.returncode == 0 and "uv" in result.stdout


# --- diff ----------------------------------------------------------------------------------------------


def test_diff_decks(tmp_path):
    import diff_decks

    def deck(name, slides):
        (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump({"slides": slides}))
        return build_deck.build(tmp_path / f"{name}.yaml", tmp_path / f"{name}.pptx", None, None)

    warm = {"text": {"title": "Warm-up", "body": "Brain dump: invertible matrices"}}
    tf = {"text": {"title": "True or False", "body": "AB = AC implies B = C\nA^2 = 0 implies A = 0"}}
    close = {"text": {"title": "Closing", "body": "Prove the IMT direction (a) => (d)"}}
    new_slide = {"text": {"title": "Quick poll", "body": "Which step was hardest?"}}
    tf_edited = {"text": {"title": "True or False", "body": "AB = AC implies B = C\nIf A is invertible, so is A^T"}}

    generated = deck("generated", [warm, tf, close])
    assert "No changes" in diff_decks.diff(generated, generated)

    final = deck("final", [warm, new_slide, tf_edited])
    report = diff_decks.diff(generated, final)
    assert "## Added slide 2: Quick poll" in report
    assert "## Slide 2 → 3: True or False" in report
    assert "-A^2 = 0 implies A = 0" in report and "+If A is invertible, so is A^T" in report
    assert "## Removed slide 3: Closing" in report
    assert "Warm-up" not in report.split("presented slides.")[1]


def test_examples_match_the_schemas():
    from schemas import load_course

    example = SCRIPTS.parents[2] / "examples" / "course-template"
    assert load_course(example / "course.yaml").session_number(dt.date(2026, 8, 20)) == 2
    for entry in (example / "bank").glob("*.yaml"):
        assert load_bank_entry(entry).id == entry.stem
    assert not list((example / "bank").glob("*.md"))  # the bank is YAML now
