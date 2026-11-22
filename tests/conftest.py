from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_copilot.bedrock import get_analyzer
from smart_copilot.main import app


@pytest.fixture(autouse=True)
def tickets_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "tickets.json"
    monkeypatch.setenv("TICKETS_FILE", str(path))
    return path


@pytest.fixture(autouse=True)
def kb_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KB_PATH at a fresh empty temp directory for every test."""
    path = tmp_path / "kb"
    path.mkdir()
    monkeypatch.setenv("KB_PATH", str(path))
    return path


@pytest.fixture(autouse=True)
def reset_analyzer_override() -> Iterator[None]:
    """Ensure no get_analyzer override leaks between tests."""
    yield
    app.dependency_overrides.pop(get_analyzer, None)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
