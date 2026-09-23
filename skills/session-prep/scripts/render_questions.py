# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Generate everything that repeats a question from questions.yaml, the single source.

Usage:
    render_questions.py sessions/2026-09-24               # plan.md sections + verify.py stub + deck.yaml
    render_questions.py sessions/2026-09-24 --only plan   # plan | verify | deck (repeatable)

Writes, in the session folder:
  plan.md    the "Timeline" and "Questions" sections, between boared markers. Text you
             write outside the markers (goals, rationale, what feedback changed) is kept.
             Warns when the total minutes differ from course.yaml session.length_min by > 5.
  verify.py  a stub with one todo("<id>") per hand-written question that has no check yet.
             Existing checks are never touched; stubs for removed questions are reported.
  deck.yaml  one slide group per run of same-slot questions, laid out by the template map's
             `slots:` section (kind, questions per slide, text field or table, answer slide
             with marks). Answers and justifications go into speaker notes. Questions with
             `latex:` are rendered to math/<id>.png first.

The course folder (course.yaml, template-map.yaml) is found by walking up from the session.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from schemas import (  # noqa: E402
    Question,
    SchemaError,
    SlotLayout,
    TemplateMap,
    dump_yaml,
    load_course,
    load_questions,
    load_template_map,
)

SLOT_TITLES = {
    "warmup": "Warm-up",
    "tf": "True or False?",
    "pi": "Possible or Impossible?",
    "problem": "Problem",
    "proof": "Closing",
}
START, END = "<!-- boared:{name}:start -->", "<!-- boared:{name}:end -->"


def find_course_dir(session: Path) -> Path | None:
    for d in [session, *session.parents]:
        if (d / "course.yaml").exists():
            return d
    return None


# --- plan.md ----------------------------------------------------------------------


def _fmt_answer(q: Question) -> str:
    a = q.answer
    if q.slot == "tf":
        return "True" if a else "False"
    if q.slot == "pi":
        return a.capitalize()
    if isinstance(a, list):
        return ", ".join(map(str, a))
    if isinstance(a, dict):
        parts = []
        for k, v in a.items():
            parts.append(f"{k}: {v}")
        return "; ".join(parts)
    return str(a)


def timeline(questions: list[Question], length: int | None) -> tuple[str, str | None]:
    rows, t, warning = ["| Start | Min | Block | Questions |", "|---|---|---|---|"], 0.0, None
    for slot, group in _runs(questions):
        minutes = sum(q.minutes for q in group)
        rows.append(f"| {int(t)}' | {minutes:g} | {SLOT_TITLES[slot]} | {', '.join(q.id for q in group)} |")
        t += minutes
    rows.append(f"| {int(t)}' | | **Total {t:g} min** | |")
    if length is not None and abs(t - length) > 5:
        warning = f"planned {t:g} min but the session is {length} min"
        rows.append(f"\n> ⚠ {warning}.")
    return "\n".join(rows), warning


def questions_md(questions: list[Question]) -> str:
    out = []
    for q in questions:
        out.append(f"### {q.id} · {SLOT_TITLES[q.slot]} · {q.difficulty} · {q.minutes:g} min")
        out.append("")
        out.append(q.statement.strip())
        if q.choices:
            out += [f"- ({k}) {v}" for k, v in q.choices.items()]
        if q.image or q.latex:
            out.append(f"\n![{q.id}](math/{q.id}.png)" if q.latex else f"\n![{q.id}]({q.image})")
        out.append("")
        out.append(f"**Answer:** {_fmt_answer(q)}  ")
        if q.justification:
            out.append(f"**Why:** {q.justification}  ")
        out.append(f"*Source: {q.source}{' · tags: ' + ', '.join(q.tags) if q.tags else ''}*")
        out.append("")
    return "\n".join(out).rstrip()


def replace_section(text: str, name: str, heading: str, body: str) -> str:
    start, end = START.format(name=name), END.format(name=name)
    block = f"{start}\n{body}\n{end}"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if pattern.search(text):
        return pattern.sub(lambda _: block, text)
    return text.rstrip() + f"\n\n## {heading}\n\n{block}\n"


def write_plan(session: Path, questions: list[Question], length: int | None) -> list[str]:
    plan = session / "plan.md"
    text = plan.read_text() if plan.exists() else f"# Plan — {session.name}\n"
    tl, warning = timeline(questions, length)
    text = replace_section(text, "timeline", "Timeline", tl)
    text = replace_section(text, "questions", "Questions", questions_md(questions))
    plan.write_text(text)
    return [warning] if warning else []


# --- verify.py -----------------------------------------------------------------------

VERIFY_HEADER = '''"""Checks for {date}. Every label starts with a question ID from questions.yaml.

Generated questions are checked by their generator; everything else is checked here.
Run: verify_runner.py {session}
"""

import panchi as pan
from panchi.algorithms import rref  # noqa: F401
from verify_kit import check, check_close, check_true, lu_no_pivot, todo  # noqa: F401
'''


def write_verify(session: Path, questions: list[Question]) -> list[str]:
    path = session / "verify.py"
    text = path.read_text() if path.exists() else VERIFY_HEADER.format(date=session.name, session=session)
    mentioned = set(re.findall(r"""(?:check\w*|todo)\(\s*(?:f?["'])([a-z][a-z0-9_-]*)""", text))
    ids = {q.id for q in questions}
    added = []
    for q in questions:
        if q.generator is None and q.id not in mentioned:
            claim = f"{q.statement.strip().splitlines()[0][:90]}"
            text += f"\n\n# {q.id} — {claim}\n# answer: {_fmt_answer(q)[:100]}\ntodo({q.id!r})\n"
            added.append(q.id)
    path.write_text(text)
    notes = [f"verify.py: added todo() stubs for {', '.join(added)}"] if added else []
    stale = sorted(mentioned - ids)
    if stale:
        notes.append(f"verify.py mentions IDs no longer in questions.yaml: {', '.join(stale)} — remove those checks")
    return notes


# --- deck.yaml -------------------------------------------------------------------------


def _runs(questions: list[Question]):
    """Consecutive questions of the same slot, in order."""
    group: list[Question] = []
    for q in questions:
        if group and q.slot != group[0].slot:
            yield group[0].slot, group
            group = []
        group.append(q)
    if group:
        yield group[0].slot, group


def _chunks(items: list, size: int):
    for i in range(0, len(items), max(size, 1)):
        yield items[i : i + size]


def _notes(qs: list[Question], number_from: int) -> str:
    out = []
    for i, q in enumerate(qs, start=number_from):
        line = f"{i}. {q.id}: {_fmt_answer(q)}"
        if q.justification:
            line += f" — {q.justification}"
        out.append(line)
        if q.notes:
            out.append(f"   {q.notes}")
    return "\n".join(out)


def _statement(q: Question) -> str:
    text = q.statement.strip()
    if q.choices:
        text += "\n" + "\n".join(f"({k}) {v}" for k, v in q.choices.items())
    return text


def _mark_state(q: Question):
    if q.slot == "tf":
        return "on" if q.answer else "off"
    if q.slot == "pi":
        return "on" if q.answer == "possible" else "off"
    return None


def _image_for(session: Path, q: Question, render_math: bool) -> str | None:
    if q.latex:
        out = session / "math" / f"{q.id}.png"
        if render_math:
            from render_math import render

            render(q.latex, out)
        return f"math/{q.id}.png"
    return q.image


def deck_slides(
    session: Path,
    questions: list[Question],
    tmap: TemplateMap | None,
    course=None,
    date: dt.date | None = None,
    render_math: bool = True,
) -> tuple[list[dict], list[str]]:
    slides: list[dict] = []
    notes: list[str] = []
    slots = tmap.slots if tmap else {}
    kinds = tmap.kinds if tmap else {}

    if "title" in kinds and course is not None:
        number = course.session_number(date) if date else None
        week = course.week_for(date) if date else None
        subtitle = ", ".join(week.sections) if week else ""
        title = f"Session {number}" if number else course.course
        fields = {"title": title, "subtitle": subtitle}
        slides.append({"kind": "title", "text": {k: v for k, v in fields.items() if k in kinds["title"].fields}})

    slides_in_slot: dict[str, int] = {}
    numbered: dict[str, int] = {}  # questions of each slot emitted so far, for 1., 2., ... numbering
    for slot, group in _runs(questions):
        layout = slots.get(slot) or SlotLayout(kind=slot if slot in kinds else "", per_slide=1)
        for chunk in _chunks(group, layout.per_slide):
            slides_in_slot[slot] = slides_in_slot.get(slot, 0) + 1
            first = numbered.get(slot, 0) + 1
            numbered[slot] = first + len(chunk) - 1
            title = (layout.title or SLOT_TITLES[slot]).format(n=slides_in_slot[slot])
            slide: dict = {"text": {"title": title}, "ids": [q.id for q in chunk], "notes": _notes(chunk, first)}
            if layout.kind:
                slide["kind"] = layout.kind
            if layout.table:
                rows = [[str(i), _statement(q)] for i, q in enumerate(chunk, start=first)]
                slide["tables"] = {layout.table: {"shape": layout.table, "rows": rows}}
            elif layout.field:
                if len(chunk) == 1 and not layout.numbered:
                    body = _statement(chunk[0])
                else:
                    body = "\n".join(f"{i}. {_statement(q)}" for i, q in enumerate(chunk, start=first))
                slide["text"][layout.field] = body
            images = []
            for q in chunk:
                try:
                    img = _image_for(session, q, render_math)
                except RuntimeError as e:  # no TeX, or bad LaTeX: keep going, say so
                    notes.append(f"{q.id}: math not rendered ({str(e).splitlines()[0]}); the slide has no image")
                    continue
                if img:
                    images.append(img)
            if images:
                slide["images"] = [{"path": images[0]}]
                if len(images) > 1:
                    notes.append(
                        f"{', '.join(slide['ids'])}: several questions with math share one slide; only the first image "
                        "is placed. Set per_slide: 1 for this slot or combine the LaTeX into one image."
                    )
            if tmap is not None and layout.kind and "title" not in kinds[layout.kind].fields:
                slide["text"].pop("title")
            slides.append(slide)

            if layout.answers:
                slides.append(_answer_slide(slide, chunk, layout, kinds, title))
    return slides, notes


def _answer_slide(slide: dict, chunk: list[Question], layout: SlotLayout, kinds: dict, title: str) -> dict:
    kind = kinds[layout.answers]
    answer: dict = {"kind": layout.answers, "text": {}, "ids": slide["ids"], "notes": slide["notes"]}
    if "title" in kind.fields:
        answer["text"]["title"] = f"{title} — answers"
    if layout.table and layout.table in kind.tables:
        answer["tables"] = slide["tables"]
    elif layout.field and layout.field in kind.fields:
        answer["text"][layout.field] = slide["text"][layout.field]
    state = kind.states.get(layout.answer_state) if layout.answer_state else None
    if state is not None and isinstance(state.cells, dict):  # multiple choice: highlight the right letters
        chosen = [a for q in chunk for a in (q.answer if isinstance(q.answer, list) else [q.answer])]
        answer["states"] = {layout.answer_state: {"on": [str(a) for a in chosen]}}
    elif state is not None:  # one mark per question: filled for True / Possible
        answer["states"] = {layout.answer_state: [_mark_state(q) or "off" for q in chunk]}
    answer["hidden"] = layout.answers_hidden
    return answer


def write_deck(session: Path, questions: list[Question], tmap: TemplateMap | None, course, date, render_math=True) -> list[str]:
    slides, notes = deck_slides(session, questions, tmap, course, date, render_math)
    header = "# Generated by render_questions.py from questions.yaml. Edit questions.yaml and re-run;\n# hand edits here are overwritten.\n"
    (session / "deck.yaml").write_text(header + dump_yaml({"slides": slides}))
    missing = sorted({s for s, _ in _runs(questions)} - set(tmap.slots)) if tmap else []
    if missing:
        notes.append(f"template-map.yaml has no `slots:` entry for {', '.join(missing)} — using one plain slide per question")
    return notes


# --- main ------------------------------------------------------------------------------


def render_all(session: Path, only: set[str] | None = None, render_math: bool = True) -> list[str]:
    session = session.resolve()
    questions = load_questions(session / "questions.yaml")
    course_dir = find_course_dir(session)
    course = load_course(course_dir / "course.yaml") if course_dir else None
    tmap = None
    if course_dir and (course_dir / "template-map.yaml").exists():
        tmap = load_template_map(course_dir / "template-map.yaml")
    try:
        date = dt.date.fromisoformat(session.name)
    except ValueError:
        date = None

    notes: list[str] = []
    only = only or {"plan", "verify", "deck"}
    if "plan" in only:
        notes += write_plan(session, questions, course.session.length_min if course else None)
    if "verify" in only:
        notes += write_verify(session, questions)
    if "deck" in only:
        notes += write_deck(session, questions, tmap, course, date, render_math)
    return notes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session", type=Path)
    parser.add_argument("--only", action="append", choices=["plan", "verify", "deck"])
    parser.add_argument("--no-math", action="store_true", help="don't render latex: fields to PNG")
    args = parser.parse_args()
    try:
        notes = render_all(args.session, set(args.only) if args.only else None, not args.no_math)
    except SchemaError as e:
        sys.exit(f"render_questions: {e}")
    for n in notes:
        print(f"note: {n}")
    print(f"rendered {args.session}")


if __name__ == "__main__":
    main()
