# /// script
# requires-python = ">=3.10"
# dependencies = ["panchi>=2.0.0", "python-pptx>=1.0", "pyyaml>=6.0", "pydantic>=2.0", "sympy>=1.12", "pillow>=10"]
# ///
"""Render LaTeX math to a transparent PNG for pasting into slides.

Uses the local TeX install (latex + dvipng) so anything amsmath supports —
bmatrix, aligned, xrightarrow — renders exactly as on paper.

Usage:
    render_math.py OUT.png "LATEX"            # LaTeX given inline
    render_math.py OUT.png --file eq.tex      # LaTeX read from a file
    render_math.py OUT.png --file - < eq.tex  # LaTeX read from stdin

Options:
    --dpi N            resolution (default 300)
    --zero-based-rows  keep panchi's R_{0}, R_{1}, ... labels as-is
                       (default: shift to R_{1}, R_{2}, ... as students expect)
    --color HEX        text color, e.g. 1F2937 (default black)

From Python:
    from render_math import render
    render(rref(A)._repr_latex_(), "sessions/.../math/rref.png")
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_ROW_LABEL = re.compile(r"R_\{(\d+)\}")

_DOCUMENT = r"""\documentclass[preview,border=2pt]{standalone}
\usepackage{amsmath,amssymb}
\usepackage{xcolor}
\begin{document}
\color[HTML]{%(color)s}
$\displaystyle %(body)s$
\end{document}
"""


def strip_delimiters(latex: str) -> str:
    """Remove surrounding $...$ / $$...$$ / \\[...\\] so we control math mode."""
    s = latex.strip()
    for left, right in (("$$", "$$"), ("\\[", "\\]"), ("$", "$")):
        if s.startswith(left) and s.endswith(right) and len(s) > len(left) + len(right):
            return s[len(left) : -len(right)].strip()
    return s


def one_based_rows(latex: str) -> str:
    """Shift panchi's 0-based row labels (R_{0}) to 1-based (R_{1})."""
    return _ROW_LABEL.sub(lambda m: f"R_{{{int(m.group(1)) + 1}}}", latex)


def render(
    latex: str,
    out: str | Path,
    dpi: int = 300,
    zero_based_rows: bool = False,
    color: str = "000000",
) -> Path:
    """Render ``latex`` to ``out`` (PNG). Raises RuntimeError with the TeX log on failure."""
    for tool in ("latex", "dvipng"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"'{tool}' not found on PATH. Install a TeX distribution (e.g. MacTeX).")

    body = strip_delimiters(latex)
    if not zero_based_rows:
        body = one_based_rows(body)

    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tex = Path(tmp) / "eq.tex"
        tex.write_text(_DOCUMENT % {"body": body, "color": color.lstrip("#")})
        run = subprocess.run(
            ["latex", "-interaction=nonstopmode", "-halt-on-error", tex.name],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        if run.returncode != 0:
            log = "\n".join(line for line in run.stdout.splitlines() if line.startswith(("!", "l.")))
            raise RuntimeError(f"LaTeX failed for:\n{body}\n\n{log or run.stdout[-2000:]}")
        subprocess.run(
            ["dvipng", "-q", "-D", str(dpi), "-T", "tight", "-bg", "Transparent", "-o", str(out), "eq.dvi"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out")
    parser.add_argument("latex", nargs="?")
    parser.add_argument("--file")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--zero-based-rows", action="store_true")
    parser.add_argument("--color", default="000000")
    args = parser.parse_args()

    if args.file == "-":
        latex = sys.stdin.read()
    elif args.file:
        latex = Path(args.file).read_text()
    elif args.latex:
        latex = args.latex
    else:
        parser.error("give LATEX inline or --file")

    try:
        path = render(latex, args.out, args.dpi, args.zero_based_rows, args.color)
    except RuntimeError as e:
        sys.exit(str(e))
    print(path)


if __name__ == "__main__":
    main()
