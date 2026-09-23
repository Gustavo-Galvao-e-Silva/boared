# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Build a session deck by copying template slides and replacing their text.

Never designs slides: every output slide is a copy of a template slide, with
text swapped into existing shapes (keeping their fonts, colors, bullets), math
images fitted into a designated area, table rows filled from the template's own
rows, and answer marks copied from exemplar shapes declared in the map.

Usage:
    build_deck.py deck.yaml --template template.pptx --map template-map.yaml -o deck.pptx
    build_deck.py deck.yaml -o deck.pptx          # no template: plain 16:9 fallback

deck.yaml (usually written by render_questions.py):
    slides:
      - kind: tf                  # entry in template-map.yaml `kinds`
        # or: from_slide: 4       # copy template slide 4 directly (fields = shape names/ids)
        text:
          title: "True or **False**?"      # **bold** and {{orange|coloured}} markup
          body:                            # or a plain string
            text: "1. ...\\n2. ..."        # one paragraph per line
            box: [0.5, 1.4, 12, 4]         # optional geometry overrides (inches)
            anchor: t                      # t | ctr | b
            font_size: 20
            line_spacing: 1.1
        tables:
          statements: {rows: [["1", "If A is ..."], ["2", "..."]]}   # key from the kind's `tables`
        images:
          - path: math/q3.png     # relative to deck.yaml
            area: math_area       # map key, shape name, or shape id whose box the image fills
            # or box: [left, top, width, height]   (inches)
        states: {mark: [on, off, on, off]}         # or {choice: {on: [A, C]}}
        hidden: true              # default: the template slide's own setting
        notes: "Answers: ..."

template-map.yaml (see inspect_template.py --draft-map and references/course-folder.md):
    colors: {orange: "E87722"}
    kinds:
      tf:
        slide: 4
        fields: {title: "Title 1", body: 7}
        tables: {statements: "Table 3"}
        math_area: "Rectangle 9"  # optional default image area (removed from output)
      tf-answers:
        slide: 5
        states:
          mark: {cells: ["Oval 12", "Oval 14"], on: "Oval 12", off: "Oval 14"}
"""

from __future__ import annotations

import argparse
import copy
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pptx import Presentation  # noqa: E402
from pptx.opc.constants import RELATIONSHIP_TYPE as RT  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

from pptx_common import find_shape  # noqa: E402
from schemas import (  # noqa: E402
    Exemplar,
    FieldSpec,
    SchemaError,
    SlideSpec,
    TemplateMap,
    load_deck,
    load_template_map,
)

_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_FILLS = ("a:noFill", "a:solidFill", "a:gradFill", "a:blipFill", "a:pattFill", "a:grpFill")


class DeckError(Exception):
    pass


# --- slide copying -----------------------------------------------------------


def duplicate_slide(prs, source):
    """Append a copy of ``source`` (same layout, shapes, background, images, hidden flag)."""
    dest = prs.slides.add_slide(source.slide_layout)
    for shape in list(dest.shapes):  # drop layout placeholders; we copy the source's own
        shape._element.getparent().remove(shape._element)

    rid_map = {}
    for rel in source.part.rels.values():
        if rel.reltype in (RT.NOTES_SLIDE, RT.SLIDE_LAYOUT):
            continue
        if rel.is_external:
            rid_map[rel.rId] = dest.part.relate_to(rel.target_ref, rel.reltype, is_external=True)
        else:
            rid_map[rel.rId] = dest.part.relate_to(rel.target_part, rel.reltype)

    src_tree = source.shapes._spTree
    dest_tree = dest.shapes._spTree
    for el in src_tree:
        if el.tag in (qn("p:nvGrpSpPr"), qn("p:grpSpPr")):
            continue
        dest_tree.append(copy.deepcopy(el))

    src_bg = source._element.cSld.find(qn("p:bg"))
    if src_bg is not None:
        dest._element.cSld.insert(0, copy.deepcopy(src_bg))

    if is_hidden(source):
        set_hidden(dest, True)

    for el in dest._element.iter():
        for attr, value in list(el.attrib.items()):
            if attr.startswith(f"{{{_R_NS}}}") and value in rid_map:
                el.set(attr, rid_map[value])
    return dest


def is_hidden(slide) -> bool:
    return slide._element.get("show") in ("0", "false")


def set_hidden(slide, hidden: bool) -> None:
    if hidden:
        slide._element.set("show", "0")
    elif "show" in slide._element.attrib:
        del slide._element.attrib["show"]


def delete_slide(prs, slide):
    sld_ids = prs.slides._sldIdLst
    for sld_id in list(sld_ids):
        if prs.part.related_part(sld_id.rId) is slide.part:
            prs.part.drop_rel(sld_id.rId)
            sld_ids.remove(sld_id)
            return


# --- rich text -----------------------------------------------------------------

_MARKUP = re.compile(r"\*\*(?P<bold>.+?)\*\*|\{\{(?P<color>[A-Za-z0-9#_-]+)\|(?P<colored>.+?)\}\}")


def parse_markup(line: str, bold: bool = False, color: str | None = None) -> list[tuple[str, bool, str | None]]:
    """Split a line into (text, bold, colour) segments. ``**b**`` and ``{{name|text}}`` nest."""
    segments, pos = [], 0
    for m in _MARKUP.finditer(line):
        if m.start() > pos:
            segments.append((line[pos : m.start()], bold, color))
        if m.group("bold") is not None:
            segments += parse_markup(m.group("bold"), True, color)
        else:
            segments += parse_markup(m.group("colored"), bold, m.group("color"))
        pos = m.end()
    if pos < len(line):
        segments.append((line[pos:], bold, color))
    return segments


def resolve_color(name: str, colors: dict[str, str]) -> str:
    if name in colors:
        return colors[name].lstrip("#").upper()
    hex_ = name.lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", hex_):
        return hex_.upper()
    known = ", ".join(colors) or "none defined"
    raise DeckError(f"unknown colour {name!r} (template-map.yaml colors: {known})")


def _set_run_fill(rpr, hex_: str) -> None:
    for tag in _FILLS:
        for el in rpr.findall(qn(tag)):
            rpr.remove(el)
    fill = rpr.makeelement(qn("a:solidFill"), {})
    fill.append(fill.makeelement(qn("a:srgbClr"), {"val": hex_}))
    ln = rpr.find(qn("a:ln"))
    rpr.insert(list(rpr).index(ln) + 1 if ln is not None else 0, fill)


def _make_run(p, rpr_template, text: str, bold: bool, color: str | None):
    r = p.makeelement(qn("a:r"), {})
    rpr = copy.deepcopy(rpr_template) if rpr_template is not None else r.makeelement(qn("a:rPr"), {})
    rpr.tag = qn("a:rPr")
    if bold:
        rpr.set("b", "1")
    if color:
        _set_run_fill(rpr, color)
    r.append(rpr)
    t = r.makeelement(qn("a:t"), {})
    t.text = text
    r.append(t)
    return r


def fill_txbody(txBody, value: str, colors: dict[str, str] | None = None) -> None:
    """Replace text, one paragraph per line, cloning the template paragraphs' formatting.

    Each line may use ``**bold**`` and ``{{colour|text}}``; every segment gets a copy of
    the template paragraph's first run formatting with the markup overlaid.
    """
    colors = colors or {}
    originals = txBody.findall(qn("a:p"))
    lines = str(value).rstrip("\n").split("\n")

    for i, line in enumerate(lines):
        p = copy.deepcopy(originals[min(i, len(originals) - 1)])
        runs = p.findall(qn("a:r"))
        end = p.find(qn("a:endParaRPr"))
        if runs and runs[0].find(qn("a:rPr")) is not None:
            rpr_template = runs[0].find(qn("a:rPr"))
        else:
            rpr_template = end
        rpr_template = copy.deepcopy(rpr_template) if rpr_template is not None else None
        for extra in p.findall(qn("a:fld")) + p.findall(qn("a:br")) + runs:
            p.remove(extra)
        segments = [(text, bold, resolve_color(c, colors) if c else None) for text, bold, c in parse_markup(line)]
        insert_at = list(p).index(end) if end is not None else len(p)
        for text, bold, color in segments or [("", False, None)]:
            p.insert(insert_at, _make_run(p, rpr_template, text, bold, color))
            insert_at += 1
        txBody.append(p)

    for p in originals:
        txBody.remove(p)


def set_text(shape, value: str, colors: dict[str, str] | None = None) -> None:
    if not shape.has_text_frame:
        raise DeckError(f"Shape {shape.name!r} has no text frame")
    fill_txbody(shape.text_frame._txBody, value, colors)


def apply_geometry(shape, spec: FieldSpec) -> None:
    if spec.box:
        shape.left, shape.top, shape.width, shape.height = (int(Inches(v)) for v in spec.box)
    txBody = shape.text_frame._txBody
    if spec.anchor:
        txBody.find(qn("a:bodyPr")).set("anchor", spec.anchor)
    for p in txBody.findall(qn("a:p")):
        if spec.font_size:
            for rpr in [*p.iter(qn("a:rPr")), *p.iter(qn("a:endParaRPr"))]:
                rpr.set("sz", str(int(spec.font_size * 100)))
        if spec.line_spacing:
            ppr = p.find(qn("a:pPr"))
            if ppr is None:
                ppr = p.makeelement(qn("a:pPr"), {})
                p.insert(0, ppr)
            for old in ppr.findall(qn("a:lnSpc")):
                ppr.remove(old)
            ln = ppr.makeelement(qn("a:lnSpc"), {})
            ln.append(ln.makeelement(qn("a:spcPct"), {"val": str(int(spec.line_spacing * 100000))}))
            ppr.insert(0, ln)


# --- tables ---------------------------------------------------------------------


def fill_table(shape, rows: list[list[str]], header_rows: int = 1, colors: dict | None = None) -> None:
    """Replace a table's data rows. Every new row copies the first data row's formatting,
    since template header rows often use a different font."""
    if not getattr(shape, "has_table", False):
        raise DeckError(f"Shape {shape.name!r} is not a table")
    tbl = shape.table._tbl
    trs = tbl.findall(qn("a:tr"))
    if not trs:
        raise DeckError(f"Table {shape.name!r} has no rows")
    header_rows = min(header_rows, len(trs) - 1) if len(trs) > 1 else 0
    exemplar = copy.deepcopy(trs[header_rows])
    n_cols = len(exemplar.findall(qn("a:tc")))
    for tr in trs[header_rows:]:
        tbl.remove(tr)
    for r, values in enumerate(rows, start=1):
        if len(values) != n_cols:
            raise DeckError(f"table {shape.name!r} row {r} has {len(values)} cells; the table has {n_cols} columns")
        tr = copy.deepcopy(exemplar)
        for tc, value in zip(tr.findall(qn("a:tc")), values):
            fill_txbody(tc.find(qn("a:txBody")), value, colors)
        tbl.append(tr)
    shape.height = sum(int(tr.get("h", 0)) for tr in tbl.findall(qn("a:tr"))) or shape.height


# --- states (answer marks, highlighted choices) --------------------------------------


def _snapshot(slide, exemplar, colors) -> dict:
    """Formatting of an exemplar shape: fill, line, style and first-run text properties."""
    spec = exemplar if isinstance(exemplar, Exemplar) else Exemplar(shape=exemplar)
    shape = find_shape(slide, spec.shape)
    sppr = shape._element.find(qn("p:spPr"))
    fills = [copy.deepcopy(el) for tag in _FILLS for el in sppr.findall(qn(tag))] if sppr is not None else []
    ln = sppr.find(qn("a:ln")) if sppr is not None else None
    style = shape._element.find(qn("p:style"))
    rpr = None
    if shape.has_text_frame:
        rpr = next(shape.text_frame._txBody.iter(qn("a:rPr")), None)
    return {
        "fills": fills,
        "ln": copy.deepcopy(ln) if ln is not None else None,
        "style": copy.deepcopy(style) if style is not None else None,
        "rpr": copy.deepcopy(rpr) if rpr is not None else None,
        "color": resolve_color(spec.text_color, colors) if spec.text_color else None,
        "bold": spec.bold,
    }


def _apply_format(shape, fmt: dict) -> None:
    el = shape._element
    sppr = el.find(qn("p:spPr"))
    if sppr is None:
        raise DeckError(f"Shape {shape.name!r} cannot take a fill")
    for tag in (*_FILLS, "a:ln"):
        for old in sppr.findall(qn(tag)):
            sppr.remove(old)
    geom = [c for c in sppr if c.tag in (qn("a:xfrm"), qn("a:prstGeom"), qn("a:custGeom"))]
    at = list(sppr).index(geom[-1]) + 1 if geom else 0
    for new in [*fmt["fills"], *([fmt["ln"]] if fmt["ln"] is not None else [])]:
        sppr.insert(at, copy.deepcopy(new))
        at += 1
    old_style = el.find(qn("p:style"))
    if old_style is not None:
        el.remove(old_style)
    if fmt["style"] is not None:
        el.insert(list(el).index(sppr) + 1, copy.deepcopy(fmt["style"]))
    if shape.has_text_frame:
        for r in shape.text_frame._txBody.iter(qn("a:r")):
            rpr = r.find(qn("a:rPr"))
            if fmt["rpr"] is not None:
                if rpr is not None:
                    r.remove(rpr)
                rpr = copy.deepcopy(fmt["rpr"])
                r.insert(0, rpr)
            elif rpr is None:
                rpr = r.makeelement(qn("a:rPr"), {})
                r.insert(0, rpr)
            if fmt["bold"] is not None:
                rpr.set("b", "1" if fmt["bold"] else "0")
            if fmt["color"]:
                _set_run_fill(rpr, fmt["color"])


def apply_states(slide, kind_states: dict, wanted: dict, colors: dict) -> None:
    for name, value in wanted.items():
        if name not in kind_states:
            raise DeckError(f"unknown state {name!r}; the kind declares: {', '.join(kind_states) or 'none'}")
        spec = kind_states[name]
        on, off = _snapshot(slide, spec.on, colors), _snapshot(slide, spec.off, colors)
        if isinstance(spec.cells, list):
            if not isinstance(value, list) or len(value) > len(spec.cells):
                raise DeckError(f"state {name!r}: give a list of on/off for up to {len(spec.cells)} cells")
            plan = [(spec.cells[i], v) for i, v in enumerate(value)]
            plan += [(cell, None) for cell in spec.cells[len(value) :]]  # unused cells are removed
        else:
            chosen = value.get("on", []) if isinstance(value, dict) else value
            chosen = [chosen] if isinstance(chosen, str) else list(chosen)
            unknown = [c for c in chosen if c not in spec.cells]
            if unknown:
                raise DeckError(f"state {name!r}: unknown cells {unknown}; known: {list(spec.cells)}")
            plan = [(ref, "on" if key in chosen else "off") for key, ref in spec.cells.items()]
        for ref, v in plan:
            shape = find_shape(slide, ref)
            if v is None:
                shape._element.getparent().remove(shape._element)
            elif v in ("on", True):
                _apply_format(shape, on)
            elif v in ("off", False):
                _apply_format(shape, off)
            else:
                raise DeckError(f"state {name!r}: {v!r} must be on or off")


# --- images -----------------------------------------------------------------------


def place_image(slide, image: Path, box: tuple[int, int, int, int]):
    """Add ``image`` fitted (aspect preserved) and centered inside ``box`` (EMU)."""
    left, top, width, height = box
    pic = slide.shapes.add_picture(str(image), left, top)
    scale = min(width / pic.width, height / pic.height)
    pic.width, pic.height = int(pic.width * scale), int(pic.height * scale)
    pic.left = left + (width - pic.width) // 2
    pic.top = top + (height - pic.height) // 2
    return pic


def default_box(prs) -> tuple[int, int, int, int]:
    """Lower 60% of the slide, with margins — used when no area is given."""
    w, h = prs.slide_width, prs.slide_height
    return (int(w * 0.08), int(h * 0.35), int(w * 0.84), int(h * 0.58))


# --- fit check ----------------------------------------------------------------------


def estimate_text_height(shape) -> int:
    """Rough rendered height of a shape's text in EMU (average glyph ≈ 0.5 em, line ≈ 1.2 em)."""
    tf = shape.text_frame
    body = tf._txBody.find(qn("a:bodyPr"))
    inset_lr = sum(int(body.get(k, 91440)) for k in ("lIns", "rIns"))
    inset_tb = sum(int(body.get(k, 45720)) for k in ("tIns", "bIns"))
    width = max((shape.width or 0) - inset_lr, 1)
    total = inset_tb
    for p in tf.paragraphs:
        sizes = [r.font.size for r in p.runs if r.font.size] or [Pt(18)]
        size = max(sizes)
        spacing = 1.2
        ln = p._p.find(f"{qn('a:pPr')}/{qn('a:lnSpc')}/{qn('a:spcPct')}")
        if ln is not None:
            spacing *= int(ln.get("val")) / 100000
        chars = max(len(p.text), 1)
        lines = math.ceil(chars * size * 0.5 / width)
        total += int(lines * size * spacing)
    return total


def fit_warnings(slide, where: str, images: list) -> list[str]:
    warnings = []
    for shape in slide.shapes:
        if not shape.has_text_frame or not shape.text_frame.text.strip() or not shape.height:
            continue
        need = estimate_text_height(shape)
        if need > shape.height * 1.05:
            warnings.append(
                f"{where}: text in {shape.name!r} may overflow (~{Emu(need).inches:.1f} in needed, box is {Emu(shape.height).inches:.1f} in)"
            )
        text_bottom = shape.top + min(need, shape.height)
        for pic in images:
            overlaps_x = pic.left < shape.left + shape.width and shape.left < pic.left + pic.width
            if overlaps_x and shape.top < pic.top < text_bottom:
                warnings.append(
                    f"{where}: image overlaps the text in {shape.name!r}; shorten the text or give the image a lower box"
                )
    return warnings


# --- build -------------------------------------------------------------------


def resolve_source(spec: SlideSpec, template_map: TemplateMap):
    """Return (1-based template slide number, kind or None) for a deck slide."""
    if spec.from_slide is not None:
        return spec.from_slide, None
    kinds = template_map.kinds
    if spec.kind not in kinds:
        raise DeckError(f"Unknown kind {spec.kind!r}. Known kinds: {', '.join(kinds) or '(none — no template map)'}")
    kind = kinds[spec.kind]
    return kind.slide, kind


def expected_hidden(spec: SlideSpec, kind, template_slide) -> bool:
    if spec.hidden is not None:
        return spec.hidden
    return is_hidden(template_slide) or bool(kind and kind.hidden)


def build(deck_path: Path, out: Path, template: Path | None, map_path: Path | None, warnings: list | None = None) -> Path:
    try:
        deck = load_deck(deck_path)
        template_map = load_template_map(map_path) if map_path else TemplateMap()
    except SchemaError as e:
        raise DeckError(str(e)) from None
    warnings = warnings if warnings is not None else []
    base = deck_path.parent

    if template is None:
        return build_plain(deck.slides, base, out)

    colors = template_map.colors
    prs = Presentation(str(template))
    originals = list(prs.slides)

    for n, spec in enumerate(deck.slides, start=1):
        where = f"deck slide {n}"
        try:
            number, kind = resolve_source(spec, template_map)
            if not 1 <= number <= len(originals):
                raise DeckError(f"template slide {number} does not exist (template has {len(originals)})")
            slide = duplicate_slide(prs, originals[number - 1])
            set_hidden(slide, expected_hidden(spec, kind, originals[number - 1]))
            fields = kind.fields if kind else {}

            for field, value in spec.text.items():
                shape = find_shape(slide, fields.get(field, field))
                if isinstance(value, FieldSpec):
                    set_text(shape, value.text, colors)
                    apply_geometry(shape, value)
                else:
                    set_text(shape, value, colors)

            tables = dict(spec.tables)
            if spec.table is not None:
                tables[str(spec.table.shape)] = spec.table
            for key, table in tables.items():
                ref = (kind.tables.get(key) if kind else None) or table.shape
                ref = int(ref) if isinstance(ref, str) and ref.isdigit() else ref
                fill_table(find_shape(slide, ref), table.rows, table.header_rows, colors)

            if spec.states:
                apply_states(slide, kind.states if kind else {}, spec.states, colors)

            math_area = spec.math_area if spec.math_area is not None else (kind.math_area if kind else None)
            area_shapes, pictures = {}, []
            for img in spec.images:
                path = (base / img.path).resolve()
                if not path.exists():
                    raise DeckError(f"image not found: {path}")
                if img.box:
                    box = tuple(int(Inches(v)) for v in img.box)
                else:
                    area_ref = img.area if img.area is not None else math_area
                    if area_ref is None:
                        box = default_box(prs)
                    else:
                        area = find_shape(slide, fields.get(area_ref, area_ref) if isinstance(area_ref, str) else area_ref)
                        box = (area.left, area.top, area.width, area.height)
                        area_shapes[area.shape_id] = area
                pictures.append(place_image(slide, path, box))
            for area in area_shapes.values():  # the area is a placeholder rectangle, not content
                if not (area.has_text_frame and area.text_frame.text.strip()):
                    area._element.getparent().remove(area._element)

            if spec.notes:
                slide.notes_slide.notes_text_frame.text = str(spec.notes)
            warnings += fit_warnings(slide, where, pictures)
        except (DeckError, KeyError) as e:
            raise DeckError(f"{where}: {e}") from e

    for slide in originals:
        delete_slide(prs, slide)

    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


def build_plain(slides_spec: list[SlideSpec], base: Path, out: Path) -> Path:
    """Fallback when there is no template: title + body + images on a blank 16:9 deck."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    layout = prs.slide_layouts[1]  # Title and Content
    for spec in slides_spec:
        slide = prs.slides.add_slide(layout)
        text = {k: (v.text if isinstance(v, FieldSpec) else v) for k, v in spec.text.items()}
        slide.shapes.title.text = re.sub(r"\*\*|\{\{[^|}]+\||\}\}", "", str(text.get("title", "")))
        body = slide.placeholders[1]
        body_text = "\n".join(str(v) for k, v in text.items() if k != "title")
        for table in [*spec.tables.values(), *([spec.table] if spec.table else [])]:
            body_text += "".join("\n" + " | ".join(row) for row in table.rows)
        body.left, body.top, body.width = Inches(0.8), Inches(1.6), Inches(11.7)
        body.height = Inches(1.8) if spec.images else Inches(5.4)
        if body_text.strip():
            set_text(body, body_text.strip("\n"))
        else:
            body._element.getparent().remove(body._element)
        for img in spec.images:
            box = tuple(int(Inches(v)) for v in img.box) if img.box else default_box(prs)
            place_image(slide, (base / img.path).resolve(), box)
        if spec.hidden:
            set_hidden(slide, True)
        if spec.notes:
            slide.notes_slide.notes_text_frame.text = str(spec.notes)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("deck", type=Path)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--map", type=Path, dest="map_path")
    parser.add_argument("-o", "--out", type=Path, required=True)
    args = parser.parse_args()
    if args.map_path and not args.template:
        parser.error("--map requires --template")
    warnings: list[str] = []
    try:
        print(build(args.deck, args.out, args.template, args.map_path, warnings))
    except DeckError as e:
        sys.exit(f"build_deck: {e}")
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
