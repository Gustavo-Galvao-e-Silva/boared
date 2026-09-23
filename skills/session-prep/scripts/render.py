# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Render a deck to PDF and one PNG per slide, to look at before presenting.

Usage:
    render.py deck.pptx [--out DIR] [--dpi 80] [--grid]

Uses LibreOffice (soffice) when available, else Keynote on macOS. PNGs come from
pdftoppm. --grid also writes grid.png: every slide as a labelled thumbnail.
Exits 2 with a clear message when no renderer is available.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from doctor import keynote_available, soffice_path  # noqa: E402


class RenderError(RuntimeError):
    pass


def to_pdf(deck: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / f"{deck.stem}.pdf"
    office = soffice_path()
    if office:
        with tempfile.TemporaryDirectory() as profile:  # own profile: works while LibreOffice is open
            run = subprocess.run(
                [
                    office,
                    f"-env:UserInstallation=file://{profile}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(out_dir),
                    str(deck),
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
        if run.returncode != 0 or not pdf.exists():
            raise RenderError(f"soffice failed: {run.stderr.strip() or run.stdout.strip()}")
        return pdf
    if keynote_available():
        # `open` on a .pptx often returns no reference while Keynote imports it, so wait for the document.
        # An import dialog blocks scripting; the timeout turns that into an error instead of a hang.
        script = f'''
            with timeout of 90 seconds
                tell application "Keynote"
                    set docsBefore to count of documents
                    open (POSIX file "{deck.resolve()}" as alias)
                    repeat 30 times
                        if (count of documents) > docsBefore then exit repeat
                        delay 1
                    end repeat
                    if (count of documents) = docsBefore then error "Keynote did not open the deck"
                    set d to front document
                    export d to POSIX file "{pdf.resolve()}" as PDF
                    close d saving no
                end tell
            end timeout'''
        try:
            run = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=150)
        except subprocess.TimeoutExpired:
            raise RenderError(
                "Keynote did not respond — check it for an open dialog; installing LibreOffice gives reliable previews"
            ) from None
        if run.returncode != 0 or not pdf.exists():
            raise RenderError(
                f"Keynote export failed ({run.stderr.strip()}). Check Keynote for an import dialog; "
                "installing LibreOffice (soffice) gives reliable previews"
            )
        return pdf
    system = "macOS" if platform.system() == "Darwin" else platform.system()
    raise RenderError(f"no renderer on {system}: install LibreOffice (soffice){' or Keynote' if system == 'macOS' else ''}")


def to_pngs(pdf: Path, out_dir: Path, dpi: int = 80) -> list[Path]:
    if shutil.which("pdftoppm") is None:
        raise RenderError("pdftoppm not found — install poppler to get PNG previews (the PDF is ready)")
    for old in out_dir.glob("slide-*.png"):
        old.unlink()
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(out_dir / "slide")], check=True)
    return sorted(out_dir.glob("slide-*.png"))


def grid(pngs: list[Path], out: Path, columns: int = 4, labels: list[str] | None = None) -> Path:
    from PIL import Image, ImageDraw

    thumbs = [Image.open(p).convert("RGB") for p in pngs]
    w = 320
    h = int(thumbs[0].height * w / thumbs[0].width)
    pad, label_h = 12, 22
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * (w + pad) + pad, rows * (h + label_h + pad) + pad), "white")
    draw = ImageDraw.Draw(sheet)
    for i, im in enumerate(thumbs):
        x, y = pad + (i % columns) * (w + pad), pad + (i // columns) * (h + label_h + pad)
        sheet.paste(im.resize((w, h)), (x, y + label_h))
        draw.rectangle([x, y + label_h, x + w - 1, y + label_h + h - 1], outline="#999999")
        draw.text((x, y + 4), labels[i] if labels else f"Slide {i + 1}", fill="black")
    sheet.save(out)
    return out


def render(deck: Path, out_dir: Path, dpi: int = 80, make_grid: bool = False, labels: list[str] | None = None) -> list[Path]:
    pdf = to_pdf(deck, out_dir)
    pngs = to_pngs(pdf, out_dir, dpi)
    if make_grid and pngs:
        grid(pngs, out_dir / "grid.png", labels=labels)
    return pngs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("deck", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--dpi", type=int, default=80)
    parser.add_argument("--grid", action="store_true")
    args = parser.parse_args()
    out = args.out or args.deck.parent / "render"
    try:
        pngs = render(args.deck, out, args.dpi, args.grid)
    except RenderError as e:
        print(f"render: {e}", file=sys.stderr)
        sys.exit(2)
    print(f"{len(pngs)} slides → {out}")


if __name__ == "__main__":
    main()
