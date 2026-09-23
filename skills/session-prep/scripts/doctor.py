"""Check the tools a prep run needs, once, at the start. Standard library only.

Usage:
    python3 doctor.py            # report; exit 0 even if something is missing
    python3 doctor.py --strict   # exit 1 if a required tool is missing

Reports every missing tool at once, with what still works without it.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
from pathlib import Path

TOOLS = [
    # (command, required, what it's for, fallback when missing)
    ("uv", True, "runs every script with its dependencies", "install: https://docs.astral.sh/uv/ — nothing else runs without it"),
    ("latex", False, "math rendering (render_math.py)", "write math as Unicode text on slides; install MacTeX / TeX Live"),
    ("dvipng", False, "math rendering (render_math.py)", "same as latex (ships with TeX distributions)"),
    ("pdftotext", False, "exam search (search_exams.py)", "read exam PDFs directly; install poppler (brew install poppler)"),
    ("pdftoppm", False, "slide previews (render.py)", "skip previews and open the deck instead; install poppler"),
]


def keynote_available() -> bool:
    return platform.system() == "Darwin" and Path("/Applications/Keynote.app").exists()


def soffice_path() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    mac = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    return found or (str(mac) if mac.exists() else None)


def report() -> tuple[list[str], bool]:
    lines, ok = [], True
    for cmd, required, purpose, fallback in TOOLS:
        path = shutil.which(cmd)
        if path:
            lines.append(f"ok       {cmd:<10} {purpose}")
        else:
            ok = ok and not required
            lines.append(f"{'MISSING' if required else 'missing'}  {cmd:<10} {purpose}\n         → {fallback}")
    office = soffice_path()
    if office:
        lines.append(f"ok       {'soffice':<10} deck → PDF for previews ({office})")
    elif keynote_available():
        lines.append(f"ok       {'Keynote':<10} deck → PDF for previews (macOS fallback; soffice not found)")
    else:
        lines.append(
            f"missing  {'soffice':<10} deck → PDF for previews\n"
            "         → install LibreOffice, or skip previews and open the deck to check it"
        )
    return lines, ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    lines, ok = report()
    print("\n".join(lines))
    if args.strict and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
