"""Show what the leader changed between the generated deck and the one they presented.

Usage:
    diff_decks.py sessions/<date>/deck.generated.pptx sessions/<date>/deck.final.pptx

Prints Markdown: slides added, removed, and per-slide text edits. Slides are
aligned by content, so inserting or deleting a slide doesn't make every later
slide look changed. Image changes are reported as counts (math re-rendered,
pictures added or removed).
"""

from __future__ import annotations

import argparse
import difflib
from dataclasses import dataclass
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx_common import iter_shapes


@dataclass
class SlideText:
    number: int
    lines: list[str]
    pictures: int
    notes: str

    @property
    def title(self) -> str:
        return self.lines[0] if self.lines else "(no text)"


def read_deck(path: Path) -> list[SlideText]:
    slides = []
    for number, slide in enumerate(Presentation(str(path)).slides, start=1):
        lines, pictures = [], 0
        for shape in iter_shapes(slide.shapes):
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                pictures += 1
            if shape.has_text_frame:
                lines += [p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip()]
        notes = slide.notes_slide.notes_text_frame.text.strip() if slide.has_notes_slide else ""
        slides.append(SlideText(number, lines, pictures, notes))
    return slides


def _similar(a: SlideText, b: SlideText) -> float:
    return difflib.SequenceMatcher(None, "\n".join(a.lines), "\n".join(b.lines)).ratio()


def align(old: list[SlideText], new: list[SlideText], threshold: float = 0.4):
    """Yield (old_slide | None, new_slide | None) pairs in order, pairing similar slides."""
    i = j = 0
    while i < len(old) or j < len(new):
        if i == len(old):
            yield None, new[j]
            j += 1
        elif j == len(new):
            yield old[i], None
            i += 1
        elif _similar(old[i], new[j]) >= threshold:
            yield old[i], new[j]
            i += 1
            j += 1
        # not similar: was the old slide deleted, or a new slide inserted?
        elif j + 1 < len(new) and _similar(old[i], new[j + 1]) >= threshold:
            yield None, new[j]
            j += 1
        elif i + 1 < len(old) and _similar(old[i + 1], new[j]) >= threshold:
            yield old[i], None
            i += 1
        else:  # rewritten in place
            yield old[i], new[j]
            i += 1
            j += 1


def diff(old_path: Path, new_path: Path) -> str:
    old, new = read_deck(old_path), read_deck(new_path)
    out = [f"# Deck edits: {old_path.name} → {new_path.name}", ""]
    out.append(f"{len(old)} generated slides → {len(new)} presented slides.")
    changes = 0
    for a, b in align(old, new):
        if a is None:
            changes += 1
            out += ["", f"## Added slide {b.number}: {b.title}", *(f"    {line}" for line in b.lines)]
            continue
        if b is None:
            changes += 1
            out += ["", f"## Removed slide {a.number}: {a.title}", *(f"    {line}" for line in a.lines)]
            continue
        text = [
            line
            for line in difflib.unified_diff(a.lines, b.lines, lineterm="", n=0)
            if not line.startswith(("---", "+++", "@@"))
        ]
        notes_changed = a.notes != b.notes
        pics_changed = a.pictures != b.pictures
        if not (text or notes_changed or pics_changed):
            continue
        changes += 1
        out += ["", f"## Slide {a.number} → {b.number}: {b.title}"]
        out += [f"    {line}" for line in text]
        if pics_changed:
            out.append(f"    images: {a.pictures} → {b.pictures}")
        if notes_changed:
            out.append("    speaker notes edited")
    if not changes:
        out += ["", "No changes — the generated deck was presented as is."]
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("generated", type=Path)
    parser.add_argument("final", type=Path)
    args = parser.parse_args()
    print(diff(args.generated, args.final))


if __name__ == "__main__":
    main()
