# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Bring a course's questions up to the current schema. Run once per upgrade.

Usage:
    migrate_bank.py COURSE_DIR [--dry-run]                   # old Markdown bank → bank/<id>.yaml
    migrate_bank.py COURSE_DIR --fill-required [--dry-run]   # add the fields 0.3 requires

Markdown bank: maps `type:` to `slot:` (possible-impossible → pi, word-problem /
computation → problem), `topics:` to `tags:`, and splits answers like
"False — counterexample ..." into answer: false + justification. The original .md files
move to bank/_migrated_md/. Anything it can't convert is listed and left in place.

--fill-required: walks bank/*.yaml and sessions/*/questions.yaml. Fills what has an
honest default — difficulty (medium), minutes (3), source (from scratch) — and `uses`
from the topics course.yaml schedules for the session (bank entries: for last_used),
plus `section` when that is a single topic. Everything else (section when the session
had several topics, justification, tags, answer) is listed for you to write, never guessed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from schemas import BankEntry, Question, SchemaError, dump_yaml, load_course  # noqa: E402

DEFAULTS = {"difficulty": "medium", "minutes": 3, "source": "from scratch"}

SLOTS = {
    "tf": "tf",
    "possible-impossible": "pi",
    "word-problem": "problem",
    "computation": "problem",
    "proof": "proof",
    "warmup": "warmup",
}


def split_answer(answer, slot: str):
    """'False — A = [[1,0],[0,0]] ...' → (False, 'A = [[1,0],[0,0]] ...') for tf; same for pi."""
    if not isinstance(answer, str):
        return answer, ""
    m = re.match(r"\s*(true|false|possible|impossible)\b[\s—–:.,-]*(.*)$", answer, re.I | re.S)
    if not m:
        return answer, ""
    word, rest = m.group(1).lower(), m.group(2).strip()
    if slot == "tf" and word in ("true", "false"):
        return word == "true", rest
    if slot == "pi" and word in ("possible", "impossible"):
        return word, rest
    return answer, ""


def convert(path: Path) -> dict:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        raise ValueError("no front matter")
    meta, body = yaml.safe_load(m.group(1)) or {}, m.group(2).strip()
    slot = SLOTS.get(str(meta.get("type", "")).strip())
    if not slot:
        raise ValueError(f"unknown type {meta.get('type')!r}")
    answer, justification = split_answer(meta.get("answer"), slot)
    qid = re.sub(r"[^a-z0-9_-]+", "-", path.stem.lower()).strip("-")
    if not qid[:1].isalpha():
        qid = f"q-{qid}"
    entry = {
        "id": qid,
        "slot": slot,
        "section": meta.get("section"),
        "uses": list(meta.get("uses") or ([meta["section"]] if meta.get("section") else [])),
        "tags": list(meta.get("topics") or []),
        "statement": body,
        "answer": answer,
        "justification": justification,
        "source": meta.get("source", "from scratch"),
        "difficulty": meta.get("difficulty", "medium"),
        "minutes": meta.get("minutes", 3),
        "verified": bool(meta.get("verified", False)),
        "last_used": meta.get("last_used"),
        "times_used": 1 if meta.get("last_used") else 0,
    }
    entry = {k: v for k, v in entry.items() if v not in ("", None, [])}
    if missing(entry, BankEntry) is None:
        raise ValueError("does not match the bank schema")
    return entry


def missing(entry: dict, model=Question) -> list[str] | None:
    """Required fields still absent or empty in `entry`; None if something else is wrong."""
    try:
        model.model_validate(entry)
        return []
    except ValidationError as e:
        fields = []
        for err in e.errors():
            loc = err["loc"]
            if not loc or (err["type"] != "missing" and "empty" not in err["msg"] and "at least one" not in err["msg"]):
                return None
            fields.append(str(loc[0]))
        return sorted(set(fields))


def fill(entry: dict, labels: list[str]) -> list[str]:
    """Fill the honest defaults in place; return the names of the fields filled."""
    filled = [k for k in DEFAULTS if k not in entry]
    for k in filled:
        entry[k] = DEFAULTS[k]
    if not entry.get("uses") and labels:
        entry["uses"] = list(labels)
        filled.append("uses")
    if not entry.get("section"):
        uses = entry.get("uses") or []
        if len(uses) == 1:
            entry["section"] = uses[0]
            filled.append("section")
    return filled


def _reorder(entry: dict) -> dict:
    head = ["id", "slot", "section", "uses", "tags", "statement", "answer", "justification"]
    return {k: entry[k] for k in head if k in entry} | {k: v for k, v in entry.items() if k not in head}


def _date(value) -> dt.date | None:
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        return None


def fill_required(course_dir: Path, dry_run: bool = False) -> tuple[list[str], list[str]]:
    """Return (lines describing what was filled, lines describing what is still missing)."""
    course = load_course(course_dir / "course.yaml")

    def labels_on(date: dt.date | None) -> list[str]:
        return course.sections_for(date)[0] if date else []

    done, todo = [], []

    def handle(entries: list[dict], where: str, date: dt.date | None, model) -> bool:
        changed = False
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            filled = fill(entry, labels_on(date))
            if filled:
                changed = True
                done.append(f"{where}: {entry.get('id', '?')}: filled {', '.join(filled)}")
            gaps = missing(entry, model)
            if gaps is None:
                todo.append(f"{where}: {entry.get('id', '?')}: invalid beyond missing fields — fix by hand")
            elif gaps:
                hint = ""
                if "section" in gaps and entry.get("uses"):
                    hint = f" (pick one of {', '.join(entry['uses'])})"
                elif "uses" in gaps:
                    hint = " (no scheduled topic for its date)"
                todo.append(f"{where}: {entry.get('id', '?')}: write {', '.join(gaps)}{hint}")
        return changed

    for path in sorted((course_dir / "bank").glob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        if isinstance(raw, dict) and handle([raw], f"bank/{path.name}", _date(raw.get("last_used")), BankEntry):
            if not dry_run:
                path.write_text(dump_yaml(_reorder(raw)))
    for path in sorted((course_dir / "sessions").glob("*/questions.yaml")):
        raw = yaml.safe_load(path.read_text()) or []
        where = f"sessions/{path.parent.name}/questions.yaml"
        if isinstance(raw, list) and handle(raw, where, _date(path.parent.name), Question):
            if not dry_run:
                path.write_text(dump_yaml([_reorder(e) if isinstance(e, dict) else e for e in raw]))
    return done, todo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("course", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fill-required", action="store_true", help="add the fields the current schema requires")
    args = parser.parse_args()
    if args.fill_required:
        try:
            done, todo = fill_required(args.course.resolve(), args.dry_run)
        except SchemaError as e:
            sys.exit(f"migrate_bank: {e}")
        for line in done:
            print(line)
        for line in todo:
            print(f"TODO {line}")
        print(f"\n{len(done)} filled, {len(todo)} need you{' (dry run: nothing written)' if args.dry_run else ''}")
        sys.exit(1 if todo else 0)
    bank = args.course / "bank"
    done = bank / "_migrated_md"
    failures = []
    for md in sorted(bank.glob("*.md")):
        try:
            entry = convert(md)
        except (ValueError, ValidationError) as e:
            failures.append(f"{md.name}: {str(e).splitlines()[0]}")
            continue
        out = bank / f"{entry['id']}.yaml"
        if out.exists():
            failures.append(f"{md.name}: {out.name} already exists")
            continue
        gaps = missing(entry, BankEntry)
        print(f"{md.name} → {out.name}{'  (then write ' + ', '.join(gaps) + ')' if gaps else ''}")
        if not args.dry_run:
            out.write_text(dump_yaml(entry))
            done.mkdir(exist_ok=True)
            md.rename(done / md.name)
    for f in failures:
        print(f"skipped {f}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
