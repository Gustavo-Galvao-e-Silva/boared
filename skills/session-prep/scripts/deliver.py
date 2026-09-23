# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Get a deck into the leader's Google Drive folder. The skill asks before any of these.

Usage:
    deliver.py DECK --course COURSE_DIR --options           # which routes work here, best first
    deliver.py DECK --course COURSE_DIR --mode copy [--name "Session 10.pptx"] [--force]
    deliver.py DECK --course COURSE_DIR --mode reveal
    deliver.py DECK --course COURSE_DIR --mode base64       # small decks only

Routes, in order of preference:
  copy    copy into the locally synced Drive folder (course.yaml drive_local, or found
          under ~/Library/CloudStorage on macOS); Drive for desktop uploads it
  reveal  show the deck in the file manager and open the Drive folder in the browser,
          so the leader drags it in (macOS: Finder; Linux: xdg-open; Windows: explorer)
  base64  write DECK.b64 for the Drive connector, which only accepts pasted base64
          (~4/3 of the file size). Refused above --max-kb (default 120 KB); check the
          uploaded file's size afterwards.
"""

from __future__ import annotations

import argparse
import base64
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from schemas import SchemaError, load_course  # noqa: E402

SYSTEM = platform.system()


def drive_roots() -> list[Path]:
    """Locally synced Google Drive roots (macOS only; elsewhere set drive_local)."""
    if SYSTEM != "Darwin":
        return []
    cloud = Path.home() / "Library" / "CloudStorage"
    return sorted(p / "My Drive" for p in cloud.glob("GoogleDrive-*") if (p / "My Drive").is_dir())


def local_folder(course) -> Path | None:
    if course.drive_local:
        p = Path(course.drive_local).expanduser()
        return p if p.is_dir() else None
    return None


def options(deck: Path, course, max_kb: int) -> list[str]:
    out = []
    folder = local_folder(course)
    if folder:
        out.append(f"copy    → {folder}")
    elif drive_roots():
        roots = ", ".join(str(r) for r in drive_roots())
        out.append(f"copy    (unavailable: set drive_local in course.yaml to a folder under {roots})")
    if SYSTEM in ("Darwin", "Linux", "Windows"):
        target = course.drive_folder or "(no drive_folder URL in course.yaml)"
        out.append(f"reveal  → show {deck.name} in the file manager and open {target}")
    kb = deck.stat().st_size / 1024
    if kb <= max_kb:
        out.append(f"base64  → {kb:.0f} KB deck, ~{kb * 4 / 3:.0f}k characters to paste into the Drive connector")
    else:
        out.append(f"base64  (unavailable: {kb:.0f} KB is above {max_kb} KB)")
    return out


def _open(target: str, reveal: bool = False) -> None:
    if SYSTEM == "Darwin":
        subprocess.run(["open", "-R", target] if reveal else ["open", target], check=False)
    elif SYSTEM == "Windows":
        subprocess.run(["explorer", f"/select,{target}"] if reveal else ["explorer", target], check=False)
    elif shutil.which("xdg-open"):
        subprocess.run(["xdg-open", str(Path(target).parent) if reveal else target], check=False)
    else:
        print(f"open this yourself: {target}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("deck", type=Path)
    parser.add_argument("--course", type=Path, required=True)
    parser.add_argument("--options", action="store_true")
    parser.add_argument("--mode", choices=["copy", "reveal", "base64"])
    parser.add_argument("--name", help="file name in Drive (default: <session date> <deck name>)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing file in the Drive folder")
    parser.add_argument("--max-kb", type=int, default=120)
    args = parser.parse_args()
    try:
        course = load_course(args.course / "course.yaml")
    except SchemaError as e:
        sys.exit(f"deliver: {e}")
    deck = args.deck.resolve()
    if not deck.exists():
        sys.exit(f"deliver: {deck} not found")

    if args.options or not args.mode:
        print("\n".join(options(deck, course, args.max_kb)))
        return
    if args.mode == "copy":
        folder = local_folder(course)
        if folder is None:
            sys.exit("deliver: no local Drive folder — set drive_local in course.yaml (see --options)")
        dest = folder / (args.name or f"{deck.parent.name} {deck.name}")
        if dest.exists() and not args.force:
            sys.exit(f"deliver: {dest} exists — pass --force to overwrite")
        shutil.copy2(deck, dest)
        print(f"copied to {dest}; Drive for desktop will upload it")
    elif args.mode == "reveal":
        _open(str(deck), reveal=True)
        if course.drive_folder:
            url = (
                course.drive_folder
                if course.drive_folder.startswith("http")
                else f"https://drive.google.com/drive/folders/{course.drive_folder}"
            )
            _open(url)
        print("drag the deck into the Drive folder")
    else:
        kb = deck.stat().st_size / 1024
        if kb > args.max_kb:
            sys.exit(f"deliver: {kb:.0f} KB is too big to paste as base64 (limit {args.max_kb} KB); use copy or reveal")
        out = deck.with_suffix(deck.suffix + ".b64")
        out.write_text(base64.b64encode(deck.read_bytes()).decode())
        print(f"{out} ({out.stat().st_size} characters); after uploading, confirm the Drive file is {deck.stat().st_size} bytes")


if __name__ == "__main__":
    main()
