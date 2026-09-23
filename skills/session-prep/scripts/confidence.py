# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Session confidence from paper slips: start/end tallies on a 1–5 scale.

Usage:
    confidence.py summary --start 0,2,5,3,1 --end 0,1,3,5,2 [--topic "LU factorization"]
        → the ## Confidence section for feedback.md, with mean start, mean end, shift and spread
    confidence.py history COURSE_DIR
        → one row per session that has tallies, for the 4–6 session review

Tallies are counts of 1s, 2s, 3s, 4s, 5s. The shift (end − start) matters more than
either mean. A room is *split* when 1–2 and 4–5 each hold at least a quarter of the
answers: an all-3s room and a room of 1s and 5s need different next sessions.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from dataclasses import dataclass
from pathlib import Path

LOW_MEAN = 2.5
SPLIT_SHARE = 0.25
_TALLY = re.compile(r"1×(\d+)\s+2×(\d+)\s+3×(\d+)\s+4×(\d+)\s+5×(\d+)")


@dataclass
class Tally:
    counts: list[int]

    @property
    def n(self) -> int:
        return sum(self.counts)

    @property
    def mean(self) -> float:
        return sum((i + 1) * c for i, c in enumerate(self.counts)) / self.n if self.n else float("nan")

    @property
    def split(self) -> bool:
        if not self.n:
            return False
        low, high = sum(self.counts[:2]) / self.n, sum(self.counts[3:]) / self.n
        return low >= SPLIT_SHARE and high >= SPLIT_SHARE

    def line(self) -> str:
        return " ".join(f"{i + 1}×{c}" for i, c in enumerate(self.counts)) + f"   (n = {self.n})"


def parse_counts(text: str) -> Tally:
    counts = [int(x) for x in re.split(r"[,\s]+", text.strip()) if x]
    if len(counts) != 5 or any(c < 0 for c in counts):
        raise ValueError(f"need five non-negative counts (1s,2s,3s,4s,5s), got {text!r}")
    return Tally(counts)


def verdict(start: Tally, end: Tally) -> str:
    flags = []
    if end.n and end.mean <= LOW_MEAN:
        flags.append("low end confidence")
    if end.split:
        flags.append("split room")
    return ", ".join(flags) or "ok"


def section(start: Tally, end: Tally, topic: str = "") -> str:
    shift = end.mean - start.mean
    return "\n".join(
        [
            "## Confidence",
            f"Topic asked: {topic}",
            f"Start: {start.line()}",
            f"End:   {end.line()}",
            f"Mean start {start.mean:.2f} → end {end.mean:.2f} (shift {shift:+.2f}); "
            f"end {'split' if end.split else 'not split'}; flag: {verdict(start, end)}",
        ]
    )


def read_feedback(path: Path) -> dict | None:
    text = path.read_text()
    m = re.search(r"## Confidence\n(.*?)(?:\n## |\Z)", text, re.S)
    if not m:
        return None
    body = m.group(1)
    start = re.search(r"Start:\s*" + _TALLY.pattern, body)
    end = re.search(r"End:\s*" + _TALLY.pattern, body)
    if not (start and end):
        return None
    s, e = Tally([int(x) for x in start.groups()]), Tally([int(x) for x in end.groups()])
    if not e.n:
        return None
    topic = re.search(r"Topic asked:\s*(.*)", body)
    return {
        "date": path.parent.name,
        "topic": topic.group(1).strip() if topic else "",
        "start_mean": round(s.mean, 2) if s.n else None,
        "end_mean": round(e.mean, 2),
        "shift": round(e.mean - s.mean, 2) if s.n else None,
        "end_split": e.split,
        "flag": verdict(s, e),
    }


def history(course_dir: Path, before: dt.date | None = None) -> list[dict]:
    rows = []
    for fb in sorted((course_dir / "sessions").glob("*/feedback.md")):
        if before and fb.parent.name >= before.isoformat():
            continue
        row = read_feedback(fb)
        if row:
            rows.append(row)
    return rows


def latest_confidence(course_dir: Path, before: dt.date | None = None) -> dict | None:
    rows = history(course_dir, before)
    return rows[-1] if rows else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary")
    s.add_argument("--start", required=True)
    s.add_argument("--end", required=True)
    s.add_argument("--topic", default="")
    h = sub.add_parser("history")
    h.add_argument("course", type=Path)
    args = parser.parse_args()

    if args.cmd == "summary":
        try:
            print(section(parse_counts(args.start), parse_counts(args.end), args.topic))
        except ValueError as e:
            sys.exit(f"confidence: {e}")
    else:
        rows = history(args.course)
        if not rows:
            print("No sessions with confidence tallies yet.")
            return
        print("| Date | Topic | Start | End | Shift | Split | Flag |\n|---|---|---|---|---|---|---|")
        for r in rows:
            print(
                f"| {r['date']} | {r['topic']} | {r['start_mean'] if r['start_mean'] is not None else '-'} | {r['end_mean']} "
                f"| {r['shift'] if r['shift'] is not None else '-'} | {'yes' if r['end_split'] else 'no'} | {r['flag']} |"
            )


if __name__ == "__main__":
    main()
