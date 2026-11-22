"""Knowledge-base document loader."""

from __future__ import annotations

import os
from pathlib import Path

from smart_copilot.storage import TicketStoreError

DEFAULT_KB_PATH = "data/kb/"


def get_kb_path() -> Path:
    """Return the KB directory from KB_PATH env var, defaulting to data/kb/."""
    return Path(os.environ.get("KB_PATH", DEFAULT_KB_PATH))


def load_kb_documents(kb_path: Path) -> list[dict[str, str]]:
    """Read all .txt files from kb_path and return KB documents.

    Each document is a dict with:
    - 'title': filename stem (without .txt extension)
    - 'content': file text with leading/trailing whitespace stripped

    Returns [] when kb_path does not exist or is empty.
    Non-.txt files are silently ignored.
    Raises TicketStoreError if the directory cannot be listed or a file read fails.
    """
    if not kb_path.exists():
        return []

    try:
        entries = sorted(kb_path.iterdir())
    except OSError as exc:
        raise TicketStoreError(f"Cannot list KB directory {kb_path}: {exc}") from exc

    docs: list[dict[str, str]] = []
    for entry in entries:
        if not entry.is_file() or entry.suffix != ".txt":
            continue
        try:
            content = entry.read_text(encoding="utf-8")
        except OSError as exc:
            raise TicketStoreError(f"Cannot read KB file {entry}: {exc}") from exc
        docs.append({"title": entry.stem, "content": content.strip()})

    return docs
