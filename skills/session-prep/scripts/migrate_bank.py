# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Convert the old Markdown bank (bank/*.md with front matter) to bank/<id>.yaml. Run once.

Usage:
    migrate_bank.py COURSE_DIR [--dry-run]

Maps `type:` to `slot:` (possible-impossible → pi, word-problem / computation → problem),
`topics:` to `tags:`, and splits answers like "False — counterexample ..." into
answer: false + justification. The original .md files move to bank/_migrated_md/.
Anything it can't convert is listed and left in place.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from schemas import BankEntry, dump_yaml  # noqa: E402

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
        "tags": list(meta.get("topics") or []),
        "statement": body,
        "answer": answer,
        "justification": justification,
        "source": meta.get("source", "from scratch"),
        "difficulty": meta.get("difficulty", "medium"),
        "verified": bool(meta.get("verified", False)),
        "last_used": meta.get("last_used"),
        "times_used": 1 if meta.get("last_used") else 0,
    }
    BankEntry.model_validate(entry)
    return {k: v for k, v in entry.items() if v not in ("", None)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("course", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
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
        print(f"{md.name} → {out.name}")
        if not args.dry_run:
            out.write_text(dump_yaml(entry))
            done.mkdir(exist_ok=True)
            md.rename(done / md.name)
    for f in failures:
        print(f"skipped {f}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
