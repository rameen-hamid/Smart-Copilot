"""Route-level integration tests for the agent-desk recommendation feature."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smart_copilot.bedrock import BedrockAnalysisError, get_analyzer
from smart_copilot.main import LOCAL_FALLBACK_RECOMMENDATION, app

# ---------------------------------------------------------------------------
# Shared fake helpers
# ---------------------------------------------------------------------------

CANNED_ANALYSIS: dict[str, Any] = {
    "category": "account",
    "urgency": "medium",
    "sentiment": "positive",
    "draft_reply": "Thank you for reaching out about your account.",
}

MESSAGE = "I need help with my account access"


class _FakeAnalyzer:
    """Configurable fake: analyze() returns CANNED_ANALYSIS; recommend() is configurable."""

    def __init__(self, recommendation: str = "Specific fix") -> None:
        self._recommendation = recommendation
        self.recommend_calls: list[tuple[str, list[str]]] = []

    def analyze(self, message: str) -> dict[str, Any]:
        return CANNED_ANALYSIS

    def recommend(self, message: str, snippets: list[str]) -> str:
        self.recommend_calls.append((message, snippets))
        return self._recommendation


class _RaisingRecommender:
    """analyze() succeeds; recommend() raises BedrockAnalysisError."""

    def analyze(self, message: str) -> dict[str, Any]:
        return CANNED_ANALYSIS

    def recommend(self, message: str, snippets: list[str]) -> str:
        raise BedrockAnalysisError("simulated recommend failure")


def _override(fake: Any) -> None:
    app.dependency_overrides[get_analyzer] = lambda: fake


# ---------------------------------------------------------------------------
# Requirement 4: Bedrock generates the recommendation
# ---------------------------------------------------------------------------


def test_bedrock_recommend_success_sets_recommended_solution(
    client: TestClient, kb_path: Path
) -> None:
    # Requirements 3.1, 4.1: Bedrock success → recommended_solution = Bedrock string
    (kb_path / "help.txt").write_text("account access login password")
    fake = _FakeAnalyzer(recommendation="Reset your password via the account portal.")
    _override(fake)
    ticket = client.post("/tickets", json={"message": MESSAGE}).json()
    assert ticket["recommended_solution"] == "Reset your password via the account portal."
    assert isinstance(ticket["source_snippets"], list)


def test_recommend_called_with_message_and_snippets(
    client: TestClient, kb_path: Path
) -> None:
    # Requirements 4.2, 4.3: recommend() called with exactly (message, snippets)
    (kb_path / "kb.txt").write_text("account access help login")
    fake = _FakeAnalyzer()
    _override(fake)
    client.post("/tickets", json={"message": MESSAGE})
    assert len(fake.recommend_calls) == 1
    called_message, called_snippets = fake.recommend_calls[0]
    assert called_message == MESSAGE
    assert len(called_snippets) > 0  # KB file has matching words


def test_bedrock_recommend_success_response_is_201(
    client: TestClient, kb_path: Path
) -> None:
    # Requirement 3.5
    (kb_path / "kb.txt").write_text("account access login")
    _override(_FakeAnalyzer())
    response = client.post("/tickets", json={"message": MESSAGE})
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Requirement 5: Fallback when Bedrock fails
# ---------------------------------------------------------------------------


def test_bedrock_recommend_failure_falls_back(
    client: TestClient, kb_path: Path
) -> None:
    # Requirements 5.2, 5.4: recommend() raises → fallback, 201
    (kb_path / "kb.txt").write_text("account access login help")
    _override(_RaisingRecommender())
    response = client.post("/tickets", json={"message": MESSAGE})
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["recommended_solution"] == LOCAL_FALLBACK_RECOMMENDATION
    assert isinstance(ticket["source_snippets"], list)


def test_bedrock_failure_still_returns_201(
    client: TestClient, kb_path: Path
) -> None:
    # Requirement 5.5: never 500 for a recommend failure
    (kb_path / "kb.txt").write_text("account access login help")
    _override(_RaisingRecommender())
    response = client.post("/tickets", json={"message": MESSAGE})
    assert response.status_code != 500
    assert response.status_code == 201


def test_model_id_unset_gives_fallback_recommendation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Requirements 5.1, 6.2: unset BEDROCK_MODEL_ID → fallback, never 503
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    # No dependency override — real get_analyzer() returns None
    response = client.post("/tickets", json={"message": MESSAGE})
    assert response.status_code == 201
    assert response.status_code != 503
    ticket = response.json()
    assert ticket["recommended_solution"] == LOCAL_FALLBACK_RECOMMENDATION


# ---------------------------------------------------------------------------
# Requirement 6: Empty snippets trigger fallback
# ---------------------------------------------------------------------------


def test_empty_corpus_gives_fallback_and_empty_snippets(
    client: TestClient,
) -> None:
    # Requirements 6.1, 6.2, 6.3: no past tickets, empty KB → [] + fallback
    # kb_path fixture is already empty
    _override(_FakeAnalyzer())
    response = client.post("/tickets", json={"message": MESSAGE})
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["source_snippets"] == []
    assert ticket["recommended_solution"] == LOCAL_FALLBACK_RECOMMENDATION


def test_empty_snippets_does_not_call_recommend(client: TestClient) -> None:
    # Requirement 6.3: recommend() NOT called when snippets is []
    fake = _FakeAnalyzer()
    _override(fake)
    client.post("/tickets", json={"message": MESSAGE})
    # No KB files, no past tickets → snippets = [] → recommend never called
    assert len(fake.recommend_calls) == 0


# ---------------------------------------------------------------------------
# Requirement 3: Fields saved and persisted
# ---------------------------------------------------------------------------


def test_new_ticket_has_recommended_solution_and_snippets_persisted(
    client: TestClient, tickets_file: Path
) -> None:
    # Requirements 3.3, 3.4: persisted to tickets.json
    _override(_FakeAnalyzer())
    client.post("/tickets", json={"message": MESSAGE})
    stored = json.loads(tickets_file.read_text())
    assert len(stored) == 1
    assert isinstance(stored[0]["recommended_solution"], str)
    assert len(stored[0]["recommended_solution"]) > 0
    assert isinstance(stored[0]["source_snippets"], list)


def test_existing_fields_not_removed_when_saving(
    client: TestClient, tickets_file: Path
) -> None:
    # Requirement 3.4: existing fields (id, message, category, etc.) unchanged
    _override(_FakeAnalyzer())
    created = client.post("/tickets", json={"message": MESSAGE}).json()
    stored = json.loads(tickets_file.read_text())[0]
    for field in ["id", "message", "category", "urgency", "sentiment", "draft_reply", "source"]:
        assert stored[field] == created[field]


def test_past_tickets_not_included_in_own_corpus(
    client: TestClient, kb_path: Path
) -> None:
    # Requirement: the new ticket should not appear in its own retrieval corpus
    (kb_path / "kb.txt").write_text("account login access")
    _override(_FakeAnalyzer())

    # Create ticket A
    client.post("/tickets", json={"message": "first account login"})
    # Create ticket B — ticket A may now be in the corpus but ticket B should not
    response = client.post("/tickets", json={"message": "second account login"})
    ticket_b = response.json()

    # ticket B's source_snippets must not contain ticket B's own message
    for snippet in ticket_b["source_snippets"]:
        assert "second account login" not in snippet or ticket_b["message"] not in snippet


# ---------------------------------------------------------------------------
# Requirement 7: source_snippets in GET /tickets response
# ---------------------------------------------------------------------------


def test_source_snippets_returned_in_list_endpoint(
    client: TestClient, kb_path: Path
) -> None:
    # Requirement 3.2: source_snippets is a list[str] in GET /tickets
    _override(_FakeAnalyzer())
    client.post("/tickets", json={"message": MESSAGE})
    listed = client.get("/tickets").json()
    assert len(listed) == 1
    assert isinstance(listed[0]["source_snippets"], list)
    assert isinstance(listed[0]["recommended_solution"], str)
