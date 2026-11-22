from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_copilot.main import app


@pytest.fixture(autouse=True)
def tickets_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "tickets.json"
    monkeypatch.setenv("TICKETS_FILE", str(path))
    return path


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
