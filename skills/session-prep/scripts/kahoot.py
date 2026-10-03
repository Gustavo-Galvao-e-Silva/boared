# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Turn a session's verified questions into a Kahoot, through the Kahoot MCP tools.

Usage:
    kahoot.py payload SESSION_DIR [--title T] [--new]    # writes kahoot.payload.json
    kahoot.py record  SESSION_DIR --uuid UUID [--url URL] # after create_or_update_kahoot

payload: refuses unless verify.log passed and is current. Writes the arguments for the
         Kahoot `create_or_update_kahoot` tool to SESSION_DIR/kahoot.payload.json: title,
         description, language and folderId (course.yaml `kahoot:`), and the questions.
         If kahoot.yaml exists, its uuid is included so the same Kahoot is replaced
         (--new starts a fresh one). Prints what was included and why anything was skipped.
record:  writes SESSION_DIR/kahoot.yaml (uuid, url, date, question ids) and adds one to
         kahoot_uses on the bank entries of questions that came from the bank.

What exports:
  slot tf                  → True/False
  slot pi                  → quiz with Possible / Impossible
  any question with choices → quiz (≤ 6 choices), the answer letter(s) marked correct
  anything else            → skipped
Kahoot shows plain text only (≤ 120 characters per question, ≤ 75 per choice): **bold** and
{{colour|…}} markup is removed, and a question whose math is in `latex:`/`image:` needs a
short `kahoot.question`. A question with a `kahoot:` block must export, or payload fails;
`kahoot: {include: false}` leaves it out.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from build_deck import parse_markup  # noqa: E402
from schemas import (  # noqa: E402
    KAHOOT_CHOICE_MAX,
    KAHOOT_CHOICES_MAX,
    KAHOOT_QUESTION_MAX,
    Question,
    SchemaError,
    dump_yaml,
    find_course_dir,
    load_course,
    load_questions,
)

PAYLOAD = "kahoot.payload.json"
RECORD = "kahoot.yaml"
DEFAULT_TIME = {"easy": 20, "medium": 30, "hard": 60}  # seconds


def plain(text: str) -> str:
    """Text without deck markup, on one line."""
    lines = ("".join(seg for seg, _, _ in parse_markup(line)) for line in text.splitlines())
    return " ".join(" ".join(lines).split())


def _question_text(q: Question) -> str:
    return q.kahoot.question if q.kahoot and q.kahoot.question else plain(q.statement)


def _choice_texts(q: Question) -> dict[str, str]:
    short = (q.kahoot.choices if q.kahoot else None) or {}
    return {k: short.get(k, plain(v)) for k, v in (q.choices or {}).items()}


def blocker(q: Question) -> str | None:
    """Why `q` can't go into a Kahoot, or None if it can."""
    if q.kahoot and not q.kahoot.include:
        return "kahoot.include is false"
    if q.slot not in ("tf", "pi") and not q.choices:
        return f"slot {q.slot} without choices has no Kahoot question type"
    if q.slot not in ("tf", "pi") and len(q.choices) > KAHOOT_CHOICES_MAX:
        return f"{len(q.choices)} choices (Kahoot allows {KAHOOT_CHOICES_MAX})"
    if (q.latex or q.image) and not (q.kahoot and q.kahoot.question):
        return "its math is in latex/image, which Kahoot can't show: add kahoot.question"
    text = _question_text(q)
    if len(text) > KAHOOT_QUESTION_MAX:
        return f"question is {len(text)} characters (Kahoot allows {KAHOOT_QUESTION_MAX}): add kahoot.question"
    if q.slot not in ("tf", "pi"):
        long = [k for k, v in _choice_texts(q).items() if len(v) > KAHOOT_CHOICE_MAX]
        if long:
            return f"choices {long} are over {KAHOOT_CHOICE_MAX} characters: add kahoot.choices"
    return None


def item(q: Question) -> dict:
    """One entry of the tool's `questions` array. Call only when blocker(q) is None."""
    time = (q.kahoot.time if q.kahoot else None) or DEFAULT_TIME[q.difficulty]
    out: dict = {"question": _question_text(q), "time": time * 1000}
    if q.slot == "tf":
        return {"type": "true_false", **out, "correct": q.answer}
    if q.slot == "pi":
        choices = [{"answer": a.capitalize(), "correct": q.answer == a} for a in ("possible", "impossible")]
    else:
        correct = set(q.answer if isinstance(q.answer, list) else [q.answer])
        choices = [{"answer": text, "correct": k in correct} for k, text in _choice_texts(q).items()]
    return {"type": "quiz", **out, "choices": choices}


def build(session: Path, title: str | None = None, new: bool = False) -> tuple[dict, list[str], list[str]]:
    """(tool arguments, included ids, skipped lines). Raises SchemaError when nothing can be exported
    or a question with a `kahoot:` block can't be."""
    from verify_runner import log_problem

    problem = log_problem(session)
    if problem:
        raise SchemaError(f"not exporting unverified questions: {problem}")
    course_dir = find_course_dir(session)
    if course_dir is None:
        raise SchemaError(f"no course.yaml above {session}")
    course = load_course(course_dir / "course.yaml")
    questions = load_questions(session / "questions.yaml")

    items, included, skipped, errors = [], [], [], []
    for q in questions:
        reason = blocker(q)
        if reason is None:
            items.append(item(q))
            included.append(q.id)
        elif q.kahoot and q.kahoot.include:
            errors.append(f"{q.id}: has a kahoot: block but can't be exported: {reason}")
        else:
            skipped.append(f"{q.id}: {reason}")
    if errors:
        raise SchemaError("\n".join(errors))
    if not items:
        raise SchemaError("no question can go into a Kahoot (only tf, pi and multiple choice can)")

    try:
        date = dt.date.fromisoformat(session.name)
    except ValueError:
        date = None
    number = course.session_number(date) if date else None
    when = f"Session {number}" if number else session.name
    payload: dict = {
        "title": title or f"{course.course} — {when}",
        "description": f"{course.course}, {when}. {len(items)} questions, every answer verified by boared."[:500],
        "language": course.kahoot.language,
        "questions": items,
    }
    if course.kahoot.folder:
        payload["folderId"] = course.kahoot.folder
    record = session / RECORD
    if record.exists() and not new:
        payload["uuid"] = (yaml.safe_load(record.read_text()) or {})["uuid"]
    return payload, included, skipped


def write_payload(session: Path, title: str | None = None, new: bool = False) -> list[str]:
    payload, included, skipped = build(session, title, new)
    (session / PAYLOAD).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    action = f"replaces {payload['uuid']}" if "uuid" in payload else "creates a new Kahoot"
    lines = [f"wrote {session / PAYLOAD} ({len(included)} questions, {action})", f"included: {', '.join(included)}"]
    return lines + [f"skipped {line}" for line in skipped]


def record(session: Path, uuid: str, url: str = "") -> list[str]:
    """Write kahoot.yaml and count the use on bank entries. Re-recording the same Kahoot counts
    only the questions it didn't have before."""
    payload_path = session / PAYLOAD
    if not payload_path.exists():
        raise SchemaError(f"{payload_path} missing — run kahoot.py payload first")
    payload, included, _ = build(session, json.loads(payload_path.read_text())["title"])
    saved = json.loads(payload_path.read_text())
    if saved["questions"] != payload["questions"]:
        raise SchemaError("questions.yaml changed since kahoot.payload.json — run payload again and re-upload")

    path = session / RECORD
    old = (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}
    before = set(old.get("questions", [])) if old.get("uuid") == uuid else set()
    data = {"uuid": uuid, "url": url or old.get("url", ""), "exported": dt.date.today().isoformat(), "questions": included}
    path.write_text(dump_yaml(data))
    lines = [f"wrote {path}"]

    course_dir = find_course_dir(session)
    by_id = {q.id: q for q in load_questions(session / "questions.yaml")}
    for qid in included:
        source = by_id[qid].source
        if qid in before or not source.startswith("bank:"):
            continue
        bank_path = course_dir / "bank" / f"{source.removeprefix('bank:')}.yaml"
        if not bank_path.exists():
            continue
        entry = yaml.safe_load(bank_path.read_text())
        entry["kahoot_uses"] = int(entry.get("kahoot_uses", 0)) + 1
        bank_path.write_text(dump_yaml(entry))
        lines.append(f"bank/{bank_path.name}: kahoot_uses {entry['kahoot_uses']}")
    return lines


def recorded_ids(session: Path) -> set[str]:
    """Question ids in the session's Kahoot, if it has one."""
    path = session / RECORD
    return set((yaml.safe_load(path.read_text()) or {}).get("questions", [])) if path.exists() else set()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("payload")
    p.add_argument("session", type=Path)
    p.add_argument("--title")
    p.add_argument("--new", action="store_true", help="ignore kahoot.yaml and create a new Kahoot")
    r = sub.add_parser("record")
    r.add_argument("session", type=Path)
    r.add_argument("--uuid", required=True)
    r.add_argument("--url", default="")
    args = parser.parse_args()

    try:
        if args.cmd == "payload":
            lines = write_payload(args.session.resolve(), args.title, args.new)
        else:
            lines = record(args.session.resolve(), args.uuid, args.url)
    except SchemaError as e:
        sys.exit(f"kahoot: {e}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
