# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""The question bank: bank/<id>.yaml, same schema as questions.yaml plus
verified / last_used / times_used. Reusing or promoting a question is a copy.

Usage:
    bank.py add  SESSION_DIR [--ids tf4,pi2]          # promote session questions into COURSE/bank
    bank.py find COURSE_DIR [--tags lu,inverses] [--slot tf] [--before DATE] [--skip-recent 3]
    bank.py use  SESSION_DIR BANK_ID [--as NEW_ID]    # copy a bank question into questions.yaml

add:  marks questions verified only if the session's verify.log passed and is current.
      A bank ID that already holds a different statement gets the session date appended.
find: lists matching entries, skipping any used in the last N sessions (default 3).
use:  appends the question with source bank:<id>, and updates last_used / times_used.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from schemas import (  # noqa: E402
    BankEntry,
    SchemaError,
    dump_yaml,
    load_bank_entry,
    load_questions,
    parse_questions,
    question_dict,
)

BANK_ONLY = ("verified", "last_used", "times_used")


def _course_dir(session: Path) -> Path:
    for d in session.parents:
        if (d / "course.yaml").exists():
            return d
    raise SchemaError(f"no course.yaml above {session}")


def _date(session: Path) -> dt.date | None:
    try:
        return dt.date.fromisoformat(session.name)
    except ValueError:
        return None


def load_bank(course: Path) -> dict[str, BankEntry]:
    return {p.stem: load_bank_entry(p) for p in sorted((course / "bank").glob("*.yaml"))}


def add(session: Path, ids: list[str] | None) -> list[str]:
    from verify_runner import log_problem

    course = _course_dir(session)
    questions = load_questions(session / "questions.yaml")
    unknown = sorted(set(ids or []) - {q.id for q in questions})
    if unknown:
        raise SchemaError(f"not in questions.yaml: {', '.join(unknown)}")
    problem = log_problem(session)
    bank_dir = course / "bank"
    bank_dir.mkdir(exist_ok=True)
    done = []
    for q in questions:
        if ids and q.id not in ids:
            continue
        if q.source.startswith("bank:"):
            continue  # already in the bank; `use` updated it
        entry = question_dict(q) | {"verified": problem is None, "last_used": session.name, "times_used": 1}
        bank_id = q.id
        path = bank_dir / f"{bank_id}.yaml"
        if path.exists() and load_bank_entry(path).statement.strip() != q.statement.strip():
            bank_id = f"{q.id}-{session.name}"
            path = bank_dir / f"{bank_id}.yaml"
        entry["id"] = bank_id
        BankEntry.model_validate(entry)
        path.write_text(dump_yaml(entry))
        done.append(f"{q.id} → bank/{path.name}{'' if problem is None else ' (unverified: ' + problem + ')'}")
    return done


def find(course: Path, tags: list[str], slot: str | None, before: dt.date, skip_recent: int) -> list[BankEntry]:
    sessions = sorted(p.name for p in (course / "sessions").glob("20*-*-*") if p.name < before.isoformat())
    recent = set(sessions[-skip_recent:]) if skip_recent else set()
    out = []
    for entry in load_bank(course).values():
        if slot and entry.slot != slot:
            continue
        if tags and not set(tags) & set(entry.tags):
            continue
        if entry.last_used and entry.last_used.isoformat() in recent:
            continue
        out.append(entry)
    return sorted(out, key=lambda e: (not e.verified, e.times_used, e.id))


def use(session: Path, bank_id: str, new_id: str | None) -> str:
    course = _course_dir(session)
    path = course / "bank" / f"{bank_id}.yaml"
    entry = load_bank_entry(path)
    qpath = session / "questions.yaml"
    raw = (yaml.safe_load(qpath.read_text()) if qpath.exists() else None) or []
    q = entry.model_dump(mode="json", exclude=set(BANK_ONLY), exclude_defaults=True, exclude_none=True)
    q = {"id": new_id or entry.id, "slot": entry.slot, "statement": entry.statement, "answer": entry.answer} | q
    q["id"] = new_id or entry.id
    q["source"] = f"bank:{bank_id}"
    parse_questions(raw + [q], qpath.name)  # catches an ID clash before writing
    qpath.write_text(dump_yaml(raw + [q]))
    data = yaml.safe_load(path.read_text())
    data["last_used"] = session.name
    data["times_used"] = int(data.get("times_used", 0)) + 1
    path.write_text(dump_yaml(data))
    note = "" if entry.verified else " — not verified yet: it needs a check in verify.py like any new question"
    return f"added {q['id']} from bank/{path.name}{note}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("session", type=Path)
    a.add_argument("--ids")
    f = sub.add_parser("find")
    f.add_argument("course", type=Path)
    f.add_argument("--tags", default="")
    f.add_argument("--slot")
    f.add_argument("--before", type=dt.date.fromisoformat, default=dt.date.today() + dt.timedelta(days=1))
    f.add_argument("--skip-recent", type=int, default=3)
    u = sub.add_parser("use")
    u.add_argument("session", type=Path)
    u.add_argument("bank_id")
    u.add_argument("--as", dest="new_id")
    args = parser.parse_args()

    try:
        if args.cmd == "add":
            ids = [i.strip() for i in args.ids.split(",")] if args.ids else None
            for line in add(args.session.resolve(), ids):
                print(line)
        elif args.cmd == "find":
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            entries = find(args.course.resolve(), tags, args.slot, args.before, args.skip_recent)
            for e in entries:
                flag = "verified" if e.verified else "UNVERIFIED"
                print(f"{e.id:<24} {e.slot:<8} {e.difficulty:<7} {flag:<10} used {e.times_used}×, last {e.last_used or '-'}")
                print(f"    {e.statement.strip().splitlines()[0][:100]}")
            if not entries:
                print("no matching bank questions")
        else:
            print(use(args.session.resolve(), args.bank_id, args.new_id))
    except SchemaError as e:
        sys.exit(f"bank: {e}")


if __name__ == "__main__":
    main()
