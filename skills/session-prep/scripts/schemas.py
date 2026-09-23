"""Schemas for every file the skills read: course.yaml, questions.yaml, bank/<id>.yaml,
deck.yaml and template-map.yaml.

Every script loads through here so a mistake is reported early, with the file and
the question ID, instead of surfacing as a KeyError halfway through a build:

    from schemas import load_questions
    questions = load_questions("sessions/2026-09-24/questions.yaml")

Errors are raised as SchemaError with one line per problem, e.g.
    questions.yaml: tf4: answer must be true/false for slot tf
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any, Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
Slot = Literal["warmup", "tf", "pi", "problem", "proof"]
Difficulty = Literal["easy", "medium", "hard"]


class SchemaError(Exception):
    pass


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- course.yaml -------------------------------------------------------------


class SessionFormat(_Model):
    days: list[str] = ["Tue", "Thu"]
    length_min: int = 50
    structure: Union[str, list[Any]] = "default"


class ScheduledSession(_Model):
    date: dt.date
    number: int  # session number shown on slides; never inferred


class Week(_Model):
    week: int
    start: dt.date
    sections: list[str] = []
    goals: list[str] = []
    notes: str = ""
    sessions: list[ScheduledSession] = []


class Course(_Model):
    course: str
    term: str = ""
    subject: str = "linear-algebra"
    session: SessionFormat = SessionFormat()
    drive_folder: str = ""
    drive_local: str = ""  # optional local path of the synced Drive folder
    schedule: list[Week]

    def week_for(self, date: dt.date) -> Week | None:
        weeks = sorted(self.schedule, key=lambda w: w.start)
        found = None
        for w in weeks:
            if w.start <= date:
                found = w
        return found

    def session_number(self, date: dt.date) -> int | None:
        for w in self.schedule:
            for s in w.sessions:
                if s.date == date:
                    return s.number
        return None


# --- questions.yaml and bank/<id>.yaml ------------------------------------------


class GeneratorRef(_Model):
    name: str
    seed: str
    params: dict[str, Any] = {}


class Question(_Model):
    id: str
    slot: Slot
    tags: list[str] = []
    statement: str
    answer: Any = None
    justification: str = ""
    source: str = "from scratch"  # bank:<id> | exam:<file> | url | generator:<name>
    difficulty: Difficulty = "medium"
    minutes: float = 3
    choices: dict[str, str] | None = None  # multiple choice: letter -> text; answer = letter(s)
    image: str | None = None  # math PNG (relative to the session folder) shown with the statement
    latex: str | None = None  # or: LaTeX that render_questions.py renders to math/<id>.png
    data: dict[str, Any] | None = None  # the objects the question is about (matrices, ...), for checks
    generator: GeneratorRef | None = None
    notes: str = ""  # extra speaker notes (hints, timing)

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"id {v!r} must be lowercase letters, digits, '-' or '_', starting with a letter")
        return v

    @model_validator(mode="after")
    def _answer_matches_slot(self) -> Question:
        if self.slot == "tf" and not isinstance(self.answer, bool):
            raise ValueError("answer must be true/false for slot tf")
        if self.slot == "pi" and self.answer not in ("possible", "impossible"):
            raise ValueError("answer must be 'possible' or 'impossible' for slot pi")
        if self.choices is not None:
            letters = self.answer if isinstance(self.answer, list) else [self.answer]
            unknown = [a for a in letters if a not in self.choices]
            if unknown:
                raise ValueError(f"answer {unknown} is not one of the choices {list(self.choices)}")
        if self.generator is not None and self.generator.name not in self.tags:
            self.tags = [*self.tags, self.generator.name]  # the generator name counts as a tag
        return self


class BankEntry(Question):
    verified: bool = False
    last_used: dt.date | None = None
    times_used: int = 0


# --- template-map.yaml ------------------------------------------------------------


class Exemplar(_Model):
    shape: Union[str, int]
    text_color: str | None = None  # colour name from `colors:` or hex
    bold: bool | None = None


class StateSpec(_Model):
    cells: Union[list[Union[str, int]], dict[str, Union[str, int]]]
    on: Union[str, int, Exemplar]
    off: Union[str, int, Exemplar]


class Kind(_Model):
    slide: int
    description: str = ""
    fields: dict[str, Union[str, int]] = {}
    math_area: Union[str, int, None] = None
    tables: dict[str, Union[str, int]] = {}
    states: dict[str, StateSpec] = {}
    hidden: bool = False


class SlotLayout(_Model):
    """How render_questions lays a slot's questions onto template slides."""

    kind: str
    per_slide: int = 1
    title: str | None = None  # text for the kind's `title` field; {n} = slide number within the slot
    field: str | None = "body"  # text field that receives the statements
    table: str | None = None  # or: table key that receives one row per question
    numbered: bool = True
    answers: str | None = None  # kind of the answer slide that follows (hidden by default)
    answer_state: str | None = None  # state on the answer kind (e.g. mark / choice)
    answers_hidden: bool = True


class TemplateMap(_Model):
    model_config = ConfigDict(extra="allow")  # keep drafts' extra notes
    template: str = ""
    colors: dict[str, str] = {}
    kinds: dict[str, Kind] = {}
    slots: dict[str, SlotLayout] = {}
    pairs: list[list[str]] = []

    @model_validator(mode="after")
    def _references_exist(self) -> TemplateMap:
        for slot, layout in self.slots.items():
            for kind in (layout.kind, layout.answers):
                if kind and kind not in self.kinds:
                    raise ValueError(f"slots.{slot}: unknown kind {kind!r}")
        return self


# --- deck.yaml -----------------------------------------------------------------------


class FieldSpec(_Model):
    text: str = ""
    box: list[float] | None = None  # [left, top, width, height] in inches
    anchor: Literal["t", "ctr", "b"] | None = None
    font_size: float | None = None  # points
    line_spacing: float | None = None  # multiple, e.g. 1.2


class ImageSpec(_Model):
    path: str
    area: Union[str, int, None] = None
    box: list[float] | None = None


class TableSpec(_Model):
    shape: Union[str, int]
    rows: list[list[str]]
    header_rows: int = 1  # template rows kept as-is at the top


class SlideSpec(_Model):
    kind: str | None = None
    from_slide: int | None = None
    math_area: Union[str, int, None] = None
    text: dict[str, Union[str, FieldSpec]] = {}
    images: list[ImageSpec] = []
    tables: dict[str, TableSpec] = {}
    table: TableSpec | None = None
    states: dict[str, Any] = {}
    notes: str = ""
    hidden: bool | None = None  # None = keep the template slide's setting
    ids: list[str] = []  # question IDs shown on this slide

    @model_validator(mode="after")
    def _one_source(self) -> SlideSpec:
        if self.kind is not None and self.from_slide is not None:
            raise ValueError("give either kind or from_slide, not both")
        return self


class Deck(_Model):
    slides: list[SlideSpec] = Field(min_length=1)


# --- loading ---------------------------------------------------------------------------


def _format(e: ValidationError, name: str, ids: list[str] | None = None) -> str:
    lines = []
    for err in e.errors():
        loc = list(err["loc"])
        if ids is not None and loc and isinstance(loc[0], int) and loc[0] < len(ids):
            loc[0] = ids[loc[0]]
        where = ".".join(str(p) for p in loc if not str(p).startswith("function-after"))
        msg = err["msg"].removeprefix("Value error, ")
        lines.append(f"{name}: {where}: {msg}" if where else f"{name}: {msg}")
    return "\n".join(lines)


def _read(path: Path) -> Any:
    try:
        return yaml.safe_load(Path(path).read_text())
    except FileNotFoundError:
        raise SchemaError(f"{path}: file not found") from None
    except yaml.YAMLError as e:
        raise SchemaError(f"{path}: invalid YAML: {e}") from None


def load_course(path) -> Course:
    try:
        return Course.model_validate(_read(path))
    except ValidationError as e:
        raise SchemaError(_format(e, Path(path).name)) from None


def parse_questions(raw: Any, name: str = "questions.yaml", model=Question) -> list:
    if not isinstance(raw, list):
        raise SchemaError(f"{name}: must be a list of questions")
    ids = [q.get("id", f"#{i + 1}") if isinstance(q, dict) else f"#{i + 1}" for i, q in enumerate(raw)]
    try:
        questions = [model.model_validate(q) for q in raw]
    except ValidationError:
        # validate one by one so every error names its question
        problems = []
        for qid, q in zip(ids, raw):
            try:
                model.model_validate(q)
            except ValidationError as e:
                problems.append(_format(e, name).replace(f"{name}: ", f"{name}: {qid}: ", 1))
        raise SchemaError("\n".join(problems)) from None
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise SchemaError(f"{name}: duplicate question ids: {', '.join(dupes)}")
    return questions


def load_questions(path) -> list[Question]:
    return parse_questions(_read(path) or [], Path(path).name)


def load_bank_entry(path) -> BankEntry:
    raw = _read(path)
    try:
        return BankEntry.model_validate(raw)
    except ValidationError as e:
        raise SchemaError(_format(e, Path(path).name)) from None


def load_template_map(path) -> TemplateMap:
    try:
        return TemplateMap.model_validate(_read(path) or {})
    except ValidationError as e:
        raise SchemaError(_format(e, Path(path).name)) from None


def load_deck(path) -> Deck:
    try:
        return Deck.model_validate(_read(path) or {})
    except ValidationError as e:
        raise SchemaError(_format(e, Path(path).name)) from None


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def question_dict(q: Question) -> dict:
    """A question as it should be written back to YAML: defaults and empty fields dropped."""
    rest = q.model_dump(mode="json", exclude_defaults=True, exclude_none=True)
    head = {"id": q.id, "slot": q.slot, "tags": q.tags, "statement": q.statement, "answer": q.answer}
    return head | {k: v for k, v in rest.items() if k not in head}
