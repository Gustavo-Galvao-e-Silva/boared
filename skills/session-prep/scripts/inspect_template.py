# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Describe a .pptx template so its slides can be mapped to session slide kinds.

Usage:
    inspect_template.py template.pptx                 # compact dump
    inspect_template.py template.pptx --draft-map OUT # also write a draft template-map.yaml
    inspect_template.py template.pptx --thumbs DIR    # also render a labelled grid.png of all slides
    inspect_template.py template.pptx --all-shapes    # include decorative shapes in the dump

The dump lists, per slide: number, layout, hidden flag, speaker notes, and only the
shapes that matter — shapes with text, [bracket] placeholders, tables (rows × cols and
header), empty boxes that could hold math, and mark shapes (ovals) on answer slides.

The draft map proposes kind names from slide text and notes (warmup, tf,
possible-impossible, word-problem, closing, …), a `title` field, math areas, tables,
answer-mark `states:`, question/answer `pairs:`, and `slots:` for render_questions.py.
The skill then corrects it with the leader.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE, PP_PLACEHOLDER  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Emu  # noqa: E402

from pptx_common import iter_shapes  # noqa: E402

PLACEHOLDER = re.compile(r"\[[^\]\n]{3,}\]")
KIND_WORDS = [  # (pattern in slide text or notes, kind)
    (r"warm[\s-]?up|brain\s*dump|ice\s*breaker", "warmup"),
    (r"true\s*(or|/|&)\s*false|\bt\s*/\s*f\b", "tf"),
    (r"possible\s*(or|/)\s*impossible", "possible-impossible"),
    (r"word\s*problem|application", "word-problem"),
    (r"multiple\s*choice|mcq", "mcq"),
    (r"proof|closing|challenge|wrap[\s-]?up", "closing"),
    (r"agenda|today|outline", "agenda"),
]
SLOT_FOR_KIND = {
    "warmup": "warmup",
    "mcq": "warmup",
    "tf": "tf",
    "possible-impossible": "pi",
    "word-problem": "problem",
    "closing": "proof",
}


def _inches(v: int | None) -> float | None:
    return None if v is None else round(Emu(v).inches, 2)


def _is_mark(shape) -> bool:
    try:
        return shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and shape.auto_shape_type in (
            MSO_SHAPE.OVAL,
            MSO_SHAPE.FLOWCHART_CONNECTOR,
        )
    except (NotImplementedError, ValueError):
        return False


def _has_fill(shape) -> bool:
    sppr = shape._element.find(qn("p:spPr"))
    if sppr is not None and sppr.find(qn("a:noFill")) is not None:
        return False
    if sppr is not None and sppr.find(qn("a:solidFill")) is not None:
        return True
    return shape._element.find(qn("p:style")) is not None  # theme fill


def _is_title(shape) -> bool:
    return shape.is_placeholder and shape.placeholder_format.type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)


def describe(path: Path, all_shapes: bool = False) -> list[dict]:
    prs = Presentation(str(path))
    area = prs.slide_width * prs.slide_height
    slides = []
    for number, slide in enumerate(prs.slides, start=1):
        shapes = []
        for s in iter_shapes(slide.shapes):
            text = s.text_frame.text.strip() if s.has_text_frame else ""
            entry = {
                "name": s.name,
                "id": s.shape_id,
                "type": str(s.shape_type).split(".")[-1].split(" ")[0] if s.shape_type else "UNKNOWN",
                "box_in": [_inches(s.left), _inches(s.top), _inches(s.width), _inches(s.height)],
                "has_text": s.has_text_frame,
                "text": text,
                "title": _is_title(s),
            }
            if getattr(s, "has_table", False):
                rows = s.table.rows
                entry["table"] = {
                    "rows": len(rows),
                    "cols": len(s.table.columns),
                    "header": [c.text.strip() for c in rows[0].cells],
                }
            if _is_mark(s):
                entry["mark"] = {"filled": _has_fill(s)}
            big_empty = s.has_text_frame and not text and s.width and s.height and s.width * s.height > 0.12 * area
            entry["math_candidate"] = bool(big_empty and s.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE)
            keep = all_shapes or text or "table" in entry or "mark" in entry or entry["math_candidate"]
            if keep:
                shapes.append(entry)
        notes = slide.notes_slide.notes_text_frame.text.strip() if slide.has_notes_slide else ""
        hidden = slide._element.get("show") in ("0", "false")
        slides.append({"number": number, "layout": slide.slide_layout.name, "hidden": hidden, "notes": notes, "shapes": shapes})
    return slides


def propose_kind(sl: dict, first: bool = False) -> str:
    slide_text = " ".join(s["text"] for s in sl["shapes"]).lower()
    haystack = f"{sl['notes'].lower()} {slide_text}"
    # question slides' notes often hold "Answer: …", so only the slide itself, or notes that say so, mark an answer slide
    answers = bool(
        re.search(r"\banswers?\b|\bsolutions?\b", slide_text)
        or re.search(r"answer\s*(slide|key)|reveal", sl["notes"].lower())
        or (sl["hidden"] and any(s.get("mark", {}).get("filled") for s in sl["shapes"]))
    )
    for pattern, kind in KIND_WORDS:
        if re.search(pattern, haystack):
            return f"{kind}-answers" if answers else kind
    if first:
        return "title"
    return f"slide{sl['number']}"


def find_pairs(slides: list[dict]) -> list[tuple[int, int]]:
    """Consecutive slides with the same layout and text shapes, where the second adds or fills marks
    or is hidden: a question slide and its answer slide."""
    pairs = []
    for a, b in zip(slides, slides[1:]):
        if a["layout"] != b["layout"]:
            continue
        names_a = {s["name"] for s in a["shapes"] if s["has_text"]}
        names_b = {s["name"] for s in b["shapes"] if s["has_text"]}
        if not names_a or len(names_a & names_b) < max(1, len(names_a) // 2):
            continue
        marks_a = sum(1 for s in a["shapes"] if s.get("mark", {}).get("filled"))
        marks_b = sum(1 for s in b["shapes"] if s.get("mark", {}).get("filled"))
        if marks_b > marks_a or (b["hidden"] and not a["hidden"]):
            pairs.append((a["number"], b["number"]))
    return pairs


def print_dump(path: Path, slides: list[dict]) -> None:
    prs = Presentation(str(path))
    print(f"{path}  —  {len(slides)} slides, {_inches(prs.slide_width)}x{_inches(prs.slide_height)} in\n")
    for sl in slides:
        flags = " HIDDEN" if sl["hidden"] else ""
        print(f"Slide {sl['number']}  [layout: {sl['layout']}]{flags}  → proposed kind: {propose_kind(sl, sl['number'] == 1)}")
        if sl["notes"]:
            notes = sl["notes"].replace("\n", " / ")
            print(f"  notes: {notes[:120]}{'...' if len(notes) > 120 else ''}")
        for s in sl["shapes"]:
            preview = s["text"].replace("\n", " / ")
            if len(preview) > 80:
                preview = preview[:77] + "..."
            tags = []
            if s["title"]:
                tags.append("title")
            if PLACEHOLDER.search(s["text"]):
                tags.append("[placeholder]")
            if "table" in s:
                t = s["table"]
                tags.append(f"table {t['rows']}x{t['cols']} header={t['header']}")
            if "mark" in s:
                tags.append("mark filled" if s["mark"]["filled"] else "mark empty")
            if s["math_candidate"]:
                tags.append("empty box: math area?")
            tag = f" <{'; '.join(tags)}>" if tags else ""
            print(f"  - {s['name']!r} (id {s['id']}){tag}" + (f": {preview}" if preview else ""))
        print()


def draft_map(template: Path, slides: list[dict]) -> dict:
    kinds: dict[str, dict] = {}
    by_number: dict[int, str] = {}
    for sl in slides:
        name = propose_kind(sl, sl["number"] == 1)
        base, i = name, 2
        while name in kinds:
            name, i = f"{base}-{i}", i + 1
        by_number[sl["number"]] = name
        fields, tables, math_area = {}, {}, None
        text_shapes = [s for s in sl["shapes"] if s["has_text"] and s["text"] and "mark" not in s]
        title = next((s for s in text_shapes if s["title"]), None)
        if title is None and text_shapes:
            title = min(text_shapes, key=lambda s: s["box_in"][1] or 0)
        for s in text_shapes:
            key = "title" if s is title else re.sub(r"[^a-z0-9]+", "_", s["name"].lower()).strip("_")
            fields[key] = s["id"]
        for s in sl["shapes"]:
            if "table" in s:
                tables[re.sub(r"[^a-z0-9]+", "_", s["name"].lower()).strip("_")] = s["id"]
            if s["math_candidate"] and math_area is None:
                math_area = s["id"]
        kind: dict = {"slide": sl["number"], "description": (title["text"][:60] if title else "")}
        if sl["hidden"]:
            kind["hidden"] = True
        kind["fields"] = fields
        if tables:
            kind["tables"] = tables
        if math_area is not None:
            kind["math_area"] = math_area
        marks = [s for s in sl["shapes"] if "mark" in s]
        on = next((s["id"] for s in marks if s["mark"]["filled"]), None)
        off = next((s["id"] for s in marks if not s["mark"]["filled"]), None)
        if marks and on is not None and off is not None:
            kind["states"] = {
                "mark": {
                    "cells": [s["id"] for s in sorted(marks, key=lambda s: (s["box_in"][1], s["box_in"][0]))],
                    "on": on,
                    "off": off,
                }
            }
        kinds[name] = kind

    pairs = [[by_number[a], by_number[b]] for a, b in find_pairs(slides)]
    answers_for = {q: a for q, a in pairs}
    slots = {}
    for name, kind in kinds.items():
        slot = SLOT_FOR_KIND.get(name)
        if slot and slot not in slots:
            layout: dict = {"kind": name, "per_slide": 1 if slot in ("problem", "proof") else 3}
            if kind.get("tables"):
                layout["table"] = next(iter(kind["tables"]))
                layout["field"] = None
            elif len(kind["fields"]) > 1:
                layout["field"] = next(k for k in kind["fields"] if k != "title")
            if name in answers_for:
                layout["answers"] = answers_for[name]
                if "states" in kinds[answers_for[name]]:
                    layout["answer_state"] = "mark"
                    layout["per_slide"] = len(kinds[answers_for[name]]["states"]["mark"]["cells"])
            slots[slot] = layout
    return {"template": template.name, "colors": {}, "kinds": kinds, "pairs": pairs, "slots": slots}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("template", type=Path)
    parser.add_argument("--draft-map", type=Path)
    parser.add_argument("--thumbs", type=Path, metavar="DIR")
    parser.add_argument("--all-shapes", action="store_true")
    args = parser.parse_args()

    slides = describe(args.template, args.all_shapes)
    print_dump(args.template, slides)
    if args.draft_map:
        args.draft_map.write_text(yaml.safe_dump(draft_map(args.template, slides), sort_keys=False, allow_unicode=True))
        print(f"Draft map written to {args.draft_map}")
    if args.thumbs:
        from render import RenderError, render

        labels = [f"{sl['number']}: {propose_kind(sl, sl['number'] == 1)}{' (hidden)' if sl['hidden'] else ''}" for sl in slides]
        try:
            render(args.template, args.thumbs, dpi=50, make_grid=True, labels=labels)
            print(f"Thumbnail grid written to {args.thumbs / 'grid.png'}")
        except RenderError as e:
            print(f"thumbnails skipped: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
