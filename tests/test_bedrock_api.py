"""Route-level integration tests for the Bedrock analysis feature."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smart_copilot.bedrock import BedrockAnalysisError, get_analyzer
from smart_copilot.classifier import (
    classify_category,
    classify_sentiment,
    classify_urgency,
    draft_reply,
)
from smart_copilot.main import app

# ---------------------------------------------------------------------------
# Fake analyzer helpers
# ---------------------------------------------------------------------------


class FakeAnalyzer:
    """Returns a canned Valid_Analysis dict on every analyze() call."""

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.calls: list[str] = []

    def analyze(self, message: str) -> dict[str, Any]:
        self.calls.append(message)
        return self._response

    def recommend(self, message: str, snippets: list[str]) -> str:
        return "stub recommendation"


class FakeThrottleAnalyzer:
    """Simulates a throttle by raising BedrockAnalysisError (same as the real analyzer does)."""

    def analyze(self, message: str) -> dict[str, Any]:
        raise BedrockAnalysisError("simulated throttle")

    def recommend(self, message: str, snippets: list[str]) -> str:
        return "stub recommendation"


class FakeMalformedAnalyzer:
    """Returns a dict missing required keys."""

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def analyze(self, message: str) -> dict[str, Any]:
        return self._response

    def recommend(self, message: str, snippets: list[str]) -> str:
        return "stub recommendation"


CANNED_VALID: dict[str, Any] = {
    "category": "account",
    "urgency": "medium",
    "sentiment": "positive",
    "draft_reply": "Thank you for reaching out about your account.",
}

# A message whose local-classifier result differs from CANNED_VALID
# Local: category=billing (refund keyword), urgency=low, sentiment=neutral
DIFF_MESSAGE = "I need a refund"


def _override(fake: Any) -> None:
    app.dependency_overrides[get_analyzer] = lambda: fake


# ---------------------------------------------------------------------------
# Task 6.3 – success path: source=bedrock
# ---------------------------------------------------------------------------


def test_valid_analysis_sets_bedrock_source_and_fields(client: TestClient) -> None:
    # Requirements 1.1, 3.1, 3.2, 9.4
    _override(FakeAnalyzer(CANNED_VALID))
    response = client.post("/tickets", json={"message": DIFF_MESSAGE})
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["source"] == "bedrock"
    assert ticket["category"] == "account"
    assert ticket["urgency"] == "medium"
    assert ticket["sentiment"] == "positive"
    assert ticket["draft_reply"] == "Thank you for reaching out about your account."


def test_valid_analysis_does_not_use_local_classifier(client: TestClient) -> None:
    # Requirement 1.2: local classifier is NOT used when Bedrock succeeds
    _override(FakeAnalyzer(CANNED_VALID))
    ticket = client.post("/tickets", json={"message": DIFF_MESSAGE}).json()
    # local would give category=billing, Bedrock gives category=account
    assert ticket["category"] != classify_category(DIFF_MESSAGE)


def test_analyzer_called_once_with_message_only(client: TestClient) -> None:
    # Requirements 2.1, 8.2: exactly one call, only the message passed
    fake = FakeAnalyzer(CANNED_VALID)
    _override(fake)
    client.post("/tickets", json={"message": DIFF_MESSAGE})
    assert len(fake.calls) == 1
    assert fake.calls[0] == DIFF_MESSAGE


def test_created_ticket_fields_and_source_persisted(
    client: TestClient, tickets_file: Any
) -> None:
    # Requirements 2.2, 10.2
    _override(FakeAnalyzer(CANNED_VALID))
    created = client.post("/tickets", json={"message": DIFF_MESSAGE}).json()
    assert created["source"] == "bedrock"

    listed = client.get("/tickets").json()
    assert any(t["id"] == created["id"] and t["source"] == "bedrock" for t in listed)

    stored = json.loads(tickets_file.read_text())
    assert any(t["id"] == created["id"] and t["source"] == "bedrock" for t in stored)


# ---------------------------------------------------------------------------
# Task 6.4 – fallback paths: source=local
# ---------------------------------------------------------------------------


def _local_fields_for(message: str) -> dict[str, Any]:
    cat = classify_category(message)
    return {
        "category": cat,
        "urgency": classify_urgency(message),
        "sentiment": classify_sentiment(message),
        "draft_reply": draft_reply(cat),
    }


def test_throttle_client_error_falls_back_to_local(client: TestClient) -> None:
    # Requirements 4.5, 9.5
    _override(FakeThrottleAnalyzer())
    response = client.post("/tickets", json={"message": DIFF_MESSAGE})
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["source"] == "local"
    local = _local_fields_for(DIFF_MESSAGE)
    assert ticket["category"] == local["category"]
    assert ticket["urgency"] == local["urgency"]
    assert ticket["sentiment"] == local["sentiment"]


def test_malformed_output_missing_key_falls_back_to_local(client: TestClient) -> None:
    # Requirement 4.6, 9.6: missing key in Bedrock response → fallback
    bad = {"category": "billing", "urgency": "high"}  # missing sentiment and draft_reply
    _override(FakeMalformedAnalyzer(bad))
    response = client.post("/tickets", json={"message": DIFF_MESSAGE})
    assert response.status_code == 201
    assert response.json()["source"] == "local"


def test_out_of_enum_category_falls_back_to_local(client: TestClient) -> None:
    # Requirement 5.1: out-of-enum category → fallback
    bad = {**CANNED_VALID, "category": "unknown-category"}
    _override(FakeMalformedAnalyzer(bad))
    response = client.post("/tickets", json={"message": DIFF_MESSAGE})
    assert response.status_code == 201
    assert response.json()["source"] == "local"


def test_out_of_enum_urgency_falls_back_to_local(client: TestClient) -> None:
    # Requirement 5.2
    bad = {**CANNED_VALID, "urgency": "immediately"}
    _override(FakeMalformedAnalyzer(bad))
    response = client.post("/tickets", json={"message": DIFF_MESSAGE})
    assert response.status_code == 201
    assert response.json()["source"] == "local"


def test_out_of_enum_sentiment_falls_back_to_local(client: TestClient) -> None:
    # Requirement 5.3
    bad = {**CANNED_VALID, "sentiment": "enraged"}
    _override(FakeMalformedAnalyzer(bad))
    response = client.post("/tickets", json={"message": DIFF_MESSAGE})
    assert response.status_code == 201
    assert response.json()["source"] == "local"


def test_non_dict_bedrock_response_falls_back_to_local(client: TestClient) -> None:
    # Requirement 4.6: non-dict result → fallback
    class NonDictAnalyzer:
        def analyze(self, message: str) -> Any:
            return ["billing", "high", "negative", "reply"]

    _override(NonDictAnalyzer())
    response = client.post("/tickets", json={"message": DIFF_MESSAGE})
    assert response.status_code == 201
    assert response.json()["source"] == "local"


def test_bedrock_failure_never_returns_500(client: TestClient) -> None:
    # Requirement 4.4: Bedrock errors must never produce 500
    _override(FakeThrottleAnalyzer())
    response = client.post("/tickets", json={"message": DIFF_MESSAGE})
    assert response.status_code != 500
    assert response.status_code == 201


def test_model_id_unset_creates_local_ticket(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Requirements 6.1, 6.2: unset BEDROCK_MODEL_ID → local, 201, never 503
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    # No dependency override — real get_analyzer() runs and returns None
    response = client.post("/tickets", json={"message": DIFF_MESSAGE})
    assert response.status_code == 201
    assert response.status_code != 503
    assert response.json()["source"] == "local"


def test_no_analyze_endpoint(client: TestClient) -> None:
    # Requirement 2.3: no POST /tickets/{id}/analyze endpoint
    fake_id = str(uuid.uuid4())
    response = client.post(f"/tickets/{fake_id}/analyze", json={})
    assert response.status_code in (404, 405)


def test_stored_enums_always_within_allowed_sets_on_local_fallback(
    client: TestClient, tickets_file: Any
) -> None:
    # Requirement 5.4: stored values always in allowed enums (local path)
    _override(FakeMalformedAnalyzer({"category": "bad", "urgency": "bad", "sentiment": "bad", "draft_reply": "x"}))
    client.post("/tickets", json={"message": DIFF_MESSAGE})
    stored = json.loads(tickets_file.read_text())
    for ticket in stored:
        assert ticket["category"] in {"billing", "technical", "account", "other"}
        assert ticket["urgency"] in {"low", "medium", "high"}
        assert ticket["sentiment"] in {"negative", "neutral", "positive"}
        assert ticket["source"] in {"bedrock", "local"}


def test_stored_enums_always_within_allowed_sets_on_bedrock_success(
    client: TestClient, tickets_file: Any
) -> None:
    # Requirement 5.4: stored values always in allowed enums (bedrock path)
    _override(FakeAnalyzer(CANNED_VALID))
    client.post("/tickets", json={"message": DIFF_MESSAGE})
    stored = json.loads(tickets_file.read_text())
    for ticket in stored:
        assert ticket["category"] in {"billing", "technical", "account", "other"}
        assert ticket["urgency"] in {"low", "medium", "high"}
        assert ticket["sentiment"] in {"negative", "neutral", "positive"}
        assert ticket["source"] in {"bedrock", "local"}


def test_invalid_message_does_not_call_analyzer(client: TestClient) -> None:
    # 422 must be returned before Bedrock is called
    fake = FakeAnalyzer(CANNED_VALID)
    _override(fake)
    response = client.post("/tickets", json={"message": ""})
    assert response.status_code == 422
    assert len(fake.calls) == 0
