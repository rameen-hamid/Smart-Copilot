from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_copilot.auth import hash_password
from smart_copilot.bedrock import get_analyzer
from smart_copilot.main import app

# Test-only value, not a real credential.
FAKE_PASSWORD = "fake-password-for-tests"
FAKE_USERNAME = "test-agent"
FAKE_HASH = hash_password(FAKE_PASSWORD, iterations=1000)


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


@pytest.fixture(autouse=True)
def fake_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_USERNAME", FAKE_USERNAME)
    monkeypatch.setenv("AGENT_PASSWORD_HASH", FAKE_HASH)
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")


def sign_in(test_client: TestClient) -> None:
    response = test_client.post(
        "/login",
        data={"username": FAKE_USERNAME, "password": FAKE_PASSWORD},
        follow_redirects=False,
    )
    # Login now returns 200 + JS navigation (instead of 303) so it works
    # correctly behind proxy/preview environments like Kiro's built-in browser.
    assert response.status_code == 200


@pytest.fixture
def anon_client() -> Iterator[TestClient]:
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        sign_in(test_client)
        yield test_client
