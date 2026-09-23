# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Add generated questions to a session's questions.yaml.

Usage:
    generate.py SESSION_DIR NAME [--count N] [--difficulty easy|medium|hard] [--set key=value ...]
    generate.py --list                     # available generators and their parameters

Examples:
    generate.py sessions/2026-09-24 rref --count 2 --set rows=3 --set cols=4 --set free=1
    generate.py sessions/2026-09-24 lu --set exists=false --difficulty easy
    generate.py sessions/2026-09-24 eigen --set kind=defective

Seeds are <date>-<name>-<index>, so every question (and its answer key) can be
regenerated exactly. IDs are <name><index>, unique within questions.yaml. Each
new question is printed so it can be reviewed; its checks run in verify_runner.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

import generators  # noqa: E402
from schemas import SchemaError, dump_yaml, parse_questions  # noqa: E402


def parse_params(pairs: list[str]) -> dict:
    params = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"generate: --set wants key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        params[key.strip()] = yaml.safe_load(value)
    return params


def add(session: Path, name: str, count: int, difficulty: str, params: dict) -> list[dict]:
    path = session / "questions.yaml"
    raw = (yaml.safe_load(path.read_text()) if path.exists() else None) or []
    parse_questions(raw, path.name)  # refuse to append to an invalid file
    ids = {q["id"] for q in raw}
    seeds = {q.get("generator", {}).get("seed") for q in raw if isinstance(q.get("generator"), dict)}
    new, index = [], 1
    while len(new) < count:
        seed = f"{session.name}-{name}-{index:02d}"
        qid = f"{name}{index}"
        index += 1
        if qid in ids or seed in seeds:
            continue
        new.append(generators.make_question(name, seed, difficulty, qid, **params))
    parse_questions(raw + new, path.name)
    path.write_text(dump_yaml(raw + new))
    return new


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session", type=Path, nargs="?")
    parser.add_argument("name", nargs="?")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--difficulty", default="medium", choices=list(generators.PROFILES))
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        for name in generators.names():
            doc = (generators.module(name).__doc__ or "").strip()
            print(f"== {name}\n{doc}\n")
        return
    if not (args.session and args.name):
        parser.error("give SESSION_DIR and NAME (or --list)")
    try:
        new = add(args.session.resolve(), args.name, args.count, args.difficulty, parse_params(args.set))
    except (generators.GenerationError, SchemaError, ValueError) as e:
        sys.exit(f"generate: {e}")
    print(dump_yaml(new))
    print(f"added {', '.join(q['id'] for q in new)} to {args.session / 'questions.yaml'}")


if __name__ == "__main__":
    main()
