"""Run a session's verify.py and report every check. Exit 1 if anything failed.

Usage:
    verify_runner.py sessions/2026-09-30/verify.py
"""

from __future__ import annotations

import runpy
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_kit  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    script = Path(sys.argv[1]).resolve()

    crashed = None
    try:
        runpy.run_path(str(script), run_name="__main__")
    except Exception:
        crashed = traceback.format_exc()

    results = verify_kit.RESULTS
    for r in results:
        print(f"{'ok  ' if r.ok else 'FAIL'} {r.label}")
        if r.detail:
            print(f"    {r.detail}")

    failed = sum(not r.ok for r in results)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    if crashed:
        print(f"\nverify script crashed before finishing:\n{crashed}")
    if not results and not crashed:
        print("No checks were recorded — verify.py must call check/check_true/check_close.")
    sys.exit(1 if failed or crashed or not results else 0)


if __name__ == "__main__":
    main()
