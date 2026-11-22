"""Run the pre-review checks: ruff, gitleaks, semgrep.

Usage: uv run python scripts/check.py

Runs every check, prints each command, and exits non-zero if any check fails.
Telemetry is turned off for semgrep.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_PATHS = ["src", "tests", "scripts", "docs", "README.md", "pyproject.toml"]
CODE_PATHS = ["src", "tests", "scripts"]


def _existing(paths: list[str]) -> list[str]:
    return [p for p in paths if (ROOT / p).exists()]


def _commands() -> list[tuple[str, list[str]]]:
    return [
        ("ruff", ["ruff", "check", *_existing(CODE_PATHS)]),
        (
            "gitleaks",
            [
                "gitleaks",
                "dir",
                "--no-banner",
                "--redact",
                *_existing(SCAN_PATHS),
            ],
        ),
        (
            "semgrep",
            [
                "semgrep",
                "scan",
                "--config",
                "p/python",
                "--metrics=off",
                "--disable-version-check",
                "--error",
                *_existing(CODE_PATHS),
            ],
        ),
    ]


def main() -> int:
    env = os.environ.copy()
    env["SEMGREP_SEND_METRICS"] = "off"
    env["DO_NOT_TRACK"] = "1"

    failed: list[str] = []
    missing: list[str] = []
    for name, cmd in _commands():
        print(f"\n== {name}: {' '.join(cmd)}", flush=True)
        exe = shutil.which(cmd[0])
        if exe is None:
            print(f"{name}: '{cmd[0]}' is not installed or not on PATH", file=sys.stderr)
            missing.append(name)
            continue
        try:
            result = subprocess.run([exe, *cmd[1:]], cwd=ROOT, env=env, check=False)
        except OSError as exc:
            print(f"{name}: could not run: {exc}", file=sys.stderr)
            missing.append(name)
            continue
        if result.returncode != 0:
            failed.append(name)

    print()
    if missing:
        print(f"NOT RUN (tool missing): {', '.join(missing)}")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
    if missing or failed:
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
