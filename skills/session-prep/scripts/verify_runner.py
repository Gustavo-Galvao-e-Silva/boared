# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Verify a session: run every check and fail unless every question is covered.

Usage:
    verify_runner.py sessions/2026-09-30              # verify.py + questions.yaml in that folder
    verify_runner.py sessions/2026-09-30/verify.py    # same
    verify_runner.py path/to/verify.py --no-questions # a bare verify.py (no coverage rule)

Checks come from two places:
  - generated questions (with a `generator:` block) are re-checked by their generator,
    from the matrices stored in questions.yaml;
  - verify.py holds the checks for every other question.

Every check label must start with a question ID. The run FAILS if a check fails,
verify.py crashes, a question has no check, a label names an unknown ID, or a
todo() stub is left.

It also FAILS if a question is not teachable yet: a topic in its `uses` is first taught
after the session date (by course.yaml's schedule), a `uses` label isn't in the schedule,
or its text contains a word that course.yaml's `prerequisites:` ties to a later topic.
`preview: true` on a question turns its schedule problems into PREVIEW warnings.

The report is also written to verify.log, stamped with
hashes of questions.yaml and verify.py so later steps can tell it is current:

    verify_runner.py sessions/2026-09-30 --check-log   # exit 0 only if verify.log passed and is current
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import runpy
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_kit  # noqa: E402
from schemas import Course, Question, SchemaError, find_course_dir, load_course, load_questions  # noqa: E402

LOG = "verify.log"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else "-"


def stamp(session: Path) -> str:
    return f"questions.yaml {_sha(session / 'questions.yaml')}  verify.py {_sha(session / 'verify.py')}"


def log_problem(session: Path) -> str | None:
    """None if verify.log exists, passed, and matches the current questions.yaml / verify.py."""
    log = session / LOG
    if not log.exists():
        return f"{log} missing — run verify_runner.py {session}"
    text = log.read_text()
    if f"stamp: {stamp(session)}" not in text:
        return "questions.yaml or verify.py changed since the last verification — re-run verify_runner.py"
    if "\nRESULT: PASS" not in text:
        return f"the last verification failed — see {log}"
    return None


def _text(q: Question) -> str:
    parts = [q.statement, q.justification, q.notes, q.latex or ""]
    if q.answer is not None:
        parts.append(str(q.answer))
    if q.choices:
        parts += q.choices.values()
    return "\n".join(parts).casefold()


def schedule_check(questions: list[Question], course: Course, date: dt.date) -> dict[str, list[str]]:
    """Question ID → topics it relies on that are taught after `date`. `preview: true` excuses these.

    Labels are the course's own `sections` strings, matched by course.resolve_label; boared
    assumes nothing about how a course names its topics.
    """
    known = course.labels()
    found: dict[str, list[str]] = {}
    for q in questions:
        problems = []
        for name in q.uses:
            label = course.resolve_label(name)
            if label is not None and known[label] > date:
                problems.append(f"uses {label!r}, first taught {known[label]}")
        text = _text(q)
        used = {course.resolve_label(n) for n in q.uses}
        for name, words in course.prerequisites.items():
            label = course.resolve_label(name)
            if label is None or label in used or known[label] <= date:
                continue
            hits = [w for w in words if w.casefold() in text]
            if hits:
                problems.append(
                    f"mentions {', '.join(map(repr, hits))}, which belongs to {label!r} (first taught {known[label]})"
                )
        if problems:
            found[q.id] = problems
    return found


def schedule_lines(questions: list[Question], session: Path) -> tuple[list[str], bool]:
    """Report lines for the schedule check and whether it passed."""
    try:
        date = dt.date.fromisoformat(session.name)
    except ValueError:
        return [f"SCHEDULE: skipped — {session.name} is not a session date folder"], True
    course_dir = find_course_dir(session)
    if course_dir is None:
        return ["SCHEDULE: skipped — no course.yaml above the session"], True
    course = load_course(course_dir / "course.yaml")
    found = schedule_check(questions, course, date)
    previews = {q.id for q in questions if q.preview}
    lines, passed = [], True
    topics = ", ".join(course.labels()) or "none"
    unknown = [name for name in course.prerequisites if course.resolve_label(name) is None]
    if unknown:
        lines.append(f"SCHEDULE: course.yaml prerequisites name topics not in the schedule: {', '.join(unknown)}")
        passed = False
    for q in questions:  # a label that matches no topic is a typo or a missing schedule entry; preview can't excuse it
        for name in q.uses:
            if course.resolve_label(name) is None:
                lines.append(f"SCHEDULE: {q.id} uses {name!r}, which is not one topic in course.yaml's schedule ({topics})")
                passed = False
    for qid, problems in found.items():
        for p in problems:
            if qid in previews:
                lines.append(f"PREVIEW: {qid} {p} (preview: true — the leader approves it in plan.md)")
            else:
                lines.append(f"SCHEDULE: {qid} {p}, after this session ({date}). Rewrite it, or set preview: true if deliberate.")
                passed = False
    return lines, passed


def run(script: Path | None, questions_path: Path | None) -> tuple[list[str], bool]:
    """Return (report lines, passed)."""
    verify_kit.RESULTS.clear()
    lines: list[str] = []
    problems: list[str] = []

    questions = []
    if questions_path is not None:
        try:
            questions = load_questions(questions_path)
        except SchemaError as e:
            return [f"questions.yaml is invalid:\n{e}", "", "RESULT: FAIL"], False

    generated = [q for q in questions if q.generator is not None]
    if generated:
        import generators

        for q in generated:
            try:
                generators.run_checks(q)
            except Exception as e:  # report and keep going
                verify_kit.RESULTS.append(verify_kit.Result(f"{q.id} generator check crashed", False, repr(e)))

    crashed = None
    if script is not None and script.exists():
        try:
            runpy.run_path(str(script), run_name="__main__")
        except Exception:
            crashed = traceback.format_exc()
    elif script is not None and any(q.generator is None for q in questions):
        problems.append(f"{script.name} is missing (render_questions.py writes a stub)")

    results = verify_kit.RESULTS
    for r in results:
        lines.append(f"{'ok  ' if r.ok else 'FAIL'} {r.label}")
        if r.detail:
            lines.append(f"    {r.detail}")

    if questions:
        ids = {q.id for q in questions}
        covered = {r.label.split()[0] for r in results if r.label.split()}
        unknown = sorted(covered - ids)
        missing = [q.id for q in questions if q.id not in covered]
        if unknown:
            problems.append(f"check labels name unknown question IDs: {', '.join(unknown)}")
        if missing:
            problems.append(f"questions with no check: {', '.join(missing)}")
        try:
            sched, sched_ok = schedule_lines(questions, questions_path.resolve().parent)
        except SchemaError as e:
            sched, sched_ok = [f"SCHEDULE: course.yaml is invalid:\n{e}"], False

    failed = sum(not r.ok for r in results)
    lines.append(f"\n{len(results) - failed} passed, {failed} failed")
    if crashed:
        lines.append(f"\nverify script crashed before finishing:\n{crashed}")
    if not results and not crashed:
        problems.append("no checks were recorded — verify.py must call check/check_true/check_close")
    lines += [f"COVERAGE: {p}" for p in problems]
    if questions:
        lines += sched
    passed = not (failed or crashed or problems) and (not questions or sched_ok)
    lines.append(f"\nRESULT: {'PASS' if passed else 'FAIL'}")
    return lines, passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", type=Path, help="session folder or verify.py")
    parser.add_argument("--questions", type=Path, help="questions.yaml (default: next to verify.py)")
    parser.add_argument("--no-questions", action="store_true", help="bare verify.py: skip the coverage rule")
    parser.add_argument("--no-log", action="store_true", help="don't write verify.log")
    parser.add_argument("--check-log", action="store_true", help="only report whether verify.log is current and passing")
    args = parser.parse_args()

    target = args.target.resolve()
    session = target if target.is_dir() else target.parent
    script = session / "verify.py" if target.is_dir() else target
    if args.check_log:
        problem = log_problem(session)
        print(problem or "verify.log: PASS and current")
        sys.exit(1 if problem else 0)

    questions = None
    if not args.no_questions:
        questions = args.questions or session / "questions.yaml"
        if not questions.exists():
            if args.questions or target.is_dir():
                sys.exit(f"verify_runner: {questions} not found")
            questions = None  # a bare verify.py without questions.yaml: legacy mode

    lines, passed = run(script, questions)
    report = "\n".join(lines)
    print(report)
    if not args.no_log and questions is not None:
        header = f"# verify_runner {dt.datetime.now().isoformat(timespec='seconds')}\nstamp: {stamp(session)}\n\n"
        (session / LOG).write_text(header + report + "\n")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
