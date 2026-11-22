import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

DEFAULT_TICKETS_FILE = "data/tickets.json"

_lock = threading.Lock()


class TicketStoreError(Exception):
    """The tickets file could not be read or written."""


def tickets_path() -> Path:
    return Path(os.environ.get("TICKETS_FILE", DEFAULT_TICKETS_FILE))


def _read(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise TicketStoreError(f"Cannot read tickets file: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TicketStoreError("Tickets file is not valid JSON") from exc
    if not isinstance(data, list):
        raise TicketStoreError("Tickets file must contain a JSON list")
    return data


def _write(path: Path, tickets: list[dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(tickets, tmp, indent=2)
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
    except OSError as exc:
        raise TicketStoreError(f"Cannot write tickets file: {exc}") from exc


def load_tickets() -> list[dict[str, Any]]:
    with _lock:
        return _read(tickets_path())


def add_ticket(ticket: dict[str, Any]) -> None:
    with _lock:
        path = tickets_path()
        tickets = _read(path)
        tickets.append(ticket)
        _write(path, tickets)


def delete_ticket(ticket_id: str) -> bool:
    with _lock:
        path = tickets_path()
        tickets = _read(path)
        remaining = [t for t in tickets if t.get("id") != ticket_id]
        if len(remaining) == len(tickets):
            return False
        _write(path, remaining)
        return True
