"""Entry point for `uv run check`. Runs scripts/check.py from the repository."""

import runpy
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check.py"


def main() -> int:
    if not SCRIPT.is_file():
        print(f"check: cannot find {SCRIPT}. Run from a source checkout.", file=sys.stderr)
        return 1
    module = runpy.run_path(str(SCRIPT))
    return module["main"]()
