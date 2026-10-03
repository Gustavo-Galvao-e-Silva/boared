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
    number: int | None = None  # session number shown on slides; never inferred (None = ask the leader)
    day: str = ""
    sections: list[str] = []  # this session's sections/goals, when they differ from the week's
    goals: list[str] = []


class Exam(_Model):
    name: str
    date: dt.date


class Week(_Model):
    week: int
    start: dt.date
    sections: list[str] = []
    goals: list[str] = []
    notes: str = ""
    sessions: list[ScheduledSession] = []


class KahootSettings(_Model):
    folder: str = ""  # Kahoot folder id the export saves into ("" = the account's default workspace)
    language: str = "English"  # a language name Kahoot accepts


class Course(_Model):
    course: str
    term: str = ""
    subject: str = "linear-algebra"
    session: SessionFormat = SessionFormat()
    drive_folder: str = ""
    drive_local: str = ""  # optional local path of the synced Drive folder
    final_exam: str = ""  # optional, free text (e.g. "2026-12-15 18:00-20:50")
    exams: list[Exam] = []
    # topic label → words that give it away in a question, for the schedule check's backstop.
    # Labels are the course's own `sections` strings (or a prefix that picks out one of them).
    prerequisites: dict[str, list[str]] = {}
    kahoot: KahootSettings = KahootSettings()
    schedule: list[Week]

    def week_for(self, date: dt.date) -> Week | None:
        weeks = sorted(self.schedule, key=lambda w: w.start)
        found = None
        for w in weeks:
            if w.start <= date:
                found = w
        return found

    def session_for(self, date: dt.date) -> ScheduledSession | None:
        for w in self.schedule:
            for s in w.sessions:
                if s.date == date:
                    return s
        return None

    def session_number(self, date: dt.date) -> int | None:
        s = self.session_for(date)
        return s.number if s else None

    def labels(self) -> dict[str, dt.date]:
        """Every topic label in the schedule → the first date it is taught: the earliest session
        that lists it, else the start of the earliest week that lists it."""
        by_session: dict[str, dt.date] = {}
        by_week: dict[str, dt.date] = {}
        for w in self.schedule:
            for label in w.sections:
                by_week[label] = min(by_week.get(label, w.start), w.start)
            for s in w.sessions:
                for label in s.sections:
                    by_session[label] = min(by_session.get(label, s.date), s.date)
        return by_week | by_session

    def resolve_label(self, name: str) -> str | None:
        """The schedule label `name` refers to: an exact match (ignoring case), or the one label
        that starts with `name` followed by a space ("3.1" → "3.1 Determinants")."""
        key = name.strip().casefold()
        known = list(self.labels())
        exact = [lab for lab in known if lab.strip().casefold() == key]
        if exact:
            return exact[0]
        prefixed = [lab for lab in known if lab.strip().casefold().startswith(key + " ")]
        return prefixed[0] if len(prefixed) == 1 else None

    def taught_on(self, name: str) -> dt.date | None:
        label = self.resolve_label(name)
        return self.labels()[label] if label else None

    def sections_for(self, date: dt.date) -> tuple[list[str], list[str]]:
        """(sections, goals) for a session date: the session's own, else its week's."""
        s, w = self.session_for(date), self.week_for(date)
        sections = (s.sections if s else []) or (w.sections if w else [])
        goals = (s.goals if s else []) or (w.goals if w else [])
        return sections, goals


# --- questions.yaml and bank/<id>.yaml ------------------------------------------


# Kahoot's limits (create_or_update_kahoot): question text, choice text, choices per question, time limits
KAHOOT_QUESTION_MAX = 120
KAHOOT_CHOICE_MAX = 75
KAHOOT_CHOICES_MAX = 6
KAHOOT_TIMES = (5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240)


class KahootSpec(_Model):
    """How a question goes into a Kahoot. Without it, kahoot.py exports the question when it fits."""

    include: bool = True
    question: str | None = Field(None, max_length=KAHOOT_QUESTION_MAX)  # plain-text statement for Kahoot
    choices: dict[str, str] | None = None  # shorter choice texts, by letter
    time: int | None = None  # seconds to answer

    @field_validator("choices")
    @classmethod
    def _short_choices(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        long = [k for k, text in (v or {}).items() if len(text) > KAHOOT_CHOICE_MAX]
        if long:
            raise ValueError(f"choices {long} are longer than {KAHOOT_CHOICE_MAX} characters")
        return v

    @field_validator("time")
    @classmethod
    def _allowed_time(cls, v: int | None) -> int | None:
        if v is not None and v not in KAHOOT_TIMES:
            raise ValueError(f"time must be one of {', '.join(map(str, KAHOOT_TIMES))} seconds")
        return v


class GeneratorRef(_Model):
    name: str
    seed: str
    params: dict[str, Any] = {}


class Question(_Model):
    id: str
    slot: Slot
    section: str  # the course topic label (from course.yaml `sections`) this question practises
    uses: list[str]  # every topic label the question AND its justification rely on
    tags: list[str]
    statement: str
    answer: Any
    justification: str
    source: str  # from scratch | bank:<id> | exam:<file> | url | generator:<name>
    difficulty: Difficulty
    minutes: float
    preview: bool = False  # deliberately uses a topic taught later: a schedule warning, not a failure
    choices: dict[str, str] | None = None  # multiple choice: letter -> text; answer = letter(s)
    image: str | None = None  # math PNG (relative to the session folder) shown with the statement
    latex: str | None = None  # or: LaTeX that render_questions.py renders to math/<id>.png
    data: dict[str, Any] | None = None  # the objects the question is about (matrices, ...), for checks
    generator: GeneratorRef | None = None
    notes: str = ""  # extra speaker notes (hints, timing)
    kahoot: KahootSpec | None = None  # Kahoot export: leave out, short text, or time (see kahoot.py)

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"id {v!r} must be lowercase letters, digits, '-' or '_', starting with a letter")
        return v

    @field_validator("tags", "uses")
    @classmethod
    def _not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("needs at least one entry")
        return v

    @field_validator("justification", "section", "source")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
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
        if self.kahoot and self.kahoot.choices:
            unknown = sorted(set(self.kahoot.choices) - set(self.choices or {}))
            if unknown:
                raise ValueError(f"kahoot.choices {unknown} are not among the question's choices {list(self.choices or {})}")
        if self.generator is not None and self.generator.name not in self.tags:
            self.tags = [*self.tags, self.generator.name]  # the generator name counts as a tag
        if self.section not in self.uses:
            self.uses = [self.section, *self.uses]  # a question relies on its own section
        return self


class BankEntry(Question):
    verified: bool = False
    last_used: dt.date | None = None
    times_used: int = 0
    kahoot_uses: int = 0  # sessions whose Kahoot included it


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


def find_course_dir(path: Path) -> Path | None:
    """The nearest folder at or above `path` that holds course.yaml."""
    path = Path(path).resolve()
    for d in [path, *path.parents]:
        if (d / "course.yaml").exists():
            return d
    return None


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
    head = {"id": q.id, "slot": q.slot, "section": q.section, "uses": q.uses, "tags": q.tags}
    head |= {"statement": q.statement, "answer": q.answer}
    return head | {k: v for k, v in rest.items() if k not in head}
