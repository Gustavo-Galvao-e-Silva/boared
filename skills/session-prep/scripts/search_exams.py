"""Find where a topic appears in past exams, and which problem each hit is in.

Usage:
    python3 search_exams.py "LU" --course COURSE_DIR          # searches COURSE_DIR/exams
    python3 search_exams.py "LU factori[sz]ation" "PA = LU" --course . --regex

Reads PDFs with pdftotext (page by page) and .txt / .md files directly. Each hit
reports the file, the page, the problem heading it falls under (the nearest
preceding line like "3.", "Problem 3", "Question 3(b)", "Part II"), and the line.
Standard library only.

The plan must confirm a topic appears on past exams with this before claiming it does.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HEADING = re.compile(
    r"^\s*(?:(?:Problem|Question|Exercise|Part|Section)\s+[\dIVX]+[a-z]?(?:\s*\([a-z]\))?|\(?\d{1,2}[.)]\s|\([a-z]\)\s)",
    re.I,
)


@dataclass
class Hit:
    file: str
    page: int
    heading: str
    line: str


def pages(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        if shutil.which("pdftotext") is None:
            raise RuntimeError("pdftotext not found — install poppler (brew install poppler / apt install poppler-utils)")
        run = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True)
        if run.returncode != 0:
            raise RuntimeError(f"pdftotext failed on {path.name}: {run.stderr.strip()}")
        return run.stdout.split("\f")
    return [path.read_text(errors="replace")]


def search(patterns: list[str], files: list[Path], regex: bool = False) -> list[Hit]:
    compiled = [re.compile(p if regex else re.escape(p), re.I) for p in patterns]
    hits = []
    for f in files:
        heading = ""
        for page_no, text in enumerate(pages(f), start=1):
            for line in text.splitlines():
                if HEADING.match(line):
                    heading = line.strip()[:60]
                if any(c.search(line) for c in compiled):
                    hits.append(Hit(f.name, page_no, heading or "(before the first problem)", " ".join(line.split())[:120]))
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("patterns", nargs="+")
    parser.add_argument("--course", type=Path, default=Path("."))
    parser.add_argument("--regex", action="store_true")
    args = parser.parse_args()

    exams = args.course / "exams"
    files = sorted(p for p in exams.rglob("*") if p.suffix.lower() in (".pdf", ".txt", ".md"))
    if not files:
        sys.exit(f"search_exams: no .pdf/.txt/.md files in {exams}")
    try:
        hits = search(args.patterns, files, args.regex)
    except RuntimeError as e:
        sys.exit(f"search_exams: {e}")

    if not hits:
        print(f"No matches for {', '.join(map(repr, args.patterns))} in {len(files)} exam file(s).")
        return
    by_file: dict[str, list[Hit]] = {}
    for h in hits:
        by_file.setdefault(h.file, []).append(h)
    for name, hs in by_file.items():
        problems = sorted({h.heading for h in hs})
        print(f"## {name} — {len(hs)} hit(s) in {len(problems)} problem(s)")
        for h in hs:
            print(f"  p.{h.page}  [{h.heading}]  {h.line}")
        print()


if __name__ == "__main__":
    main()
