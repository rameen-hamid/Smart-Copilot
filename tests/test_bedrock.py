"""Unit tests for bedrock.py: is_valid_analysis, RateLimiter, BedrockAnalyzer, get_analyzer."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import botocore.exceptions
import pytest

from smart_copilot.bedrock import (
    ALLOWED_CATEGORIES,
    ALLOWED_SENTIMENTS,
    ALLOWED_URGENCIES,
    BedrockAnalysisError,
    BedrockAnalyzer,
    RateLimiter,
    get_analyzer,
    is_valid_analysis,
)

# ---------------------------------------------------------------------------
# Task 2.2 – is_valid_analysis
# ---------------------------------------------------------------------------

VALID_RESULT: dict[str, Any] = {
    "category": "billing",
    "urgency": "high",
    "sentiment": "negative",
    "draft_reply": "Thank you for contacting us.",
}


def test_is_valid_analysis_accepts_well_formed_result() -> None:
    # Requirement 4.6: a Valid_Analysis is accepted
    assert is_valid_analysis(VALID_RESULT) is True


@pytest.mark.parametrize("category", list(ALLOWED_CATEGORIES))
def test_is_valid_analysis_accepts_all_allowed_categories(category: str) -> None:
    result = {**VALID_RESULT, "category": category}
    assert is_valid_analysis(result) is True


@pytest.mark.parametrize("urgency", list(ALLOWED_URGENCIES))
def test_is_valid_analysis_accepts_all_allowed_urgencies(urgency: str) -> None:
    assert is_valid_analysis({**VALID_RESULT, "urgency": urgency}) is True


@pytest.mark.parametrize("sentiment", list(ALLOWED_SENTIMENTS))
def test_is_valid_analysis_accepts_all_allowed_sentiments(sentiment: str) -> None:
    assert is_valid_analysis({**VALID_RESULT, "sentiment": sentiment}) is True


def test_is_valid_analysis_rejects_out_of_enum_category() -> None:
    # Requirement 5.1
    assert is_valid_analysis({**VALID_RESULT, "category": "unknown"}) is False


def test_is_valid_analysis_rejects_out_of_enum_urgency() -> None:
    # Requirement 5.2
    assert is_valid_analysis({**VALID_RESULT, "urgency": "soon"}) is False


def test_is_valid_analysis_rejects_out_of_enum_sentiment() -> None:
    # Requirement 5.3
    assert is_valid_analysis({**VALID_RESULT, "sentiment": "mad"}) is False


def test_is_valid_analysis_rejects_missing_draft_reply() -> None:
    # Requirement 4.6: missing key → False
    result = {k: v for k, v in VALID_RESULT.items() if k != "draft_reply"}
    assert is_valid_analysis(result) is False


def test_is_valid_analysis_rejects_empty_draft_reply() -> None:
    assert is_valid_analysis({**VALID_RESULT, "draft_reply": ""}) is False


def test_is_valid_analysis_rejects_blank_draft_reply() -> None:
    assert is_valid_analysis({**VALID_RESULT, "draft_reply": "   "}) is False


def test_is_valid_analysis_rejects_non_string_draft_reply() -> None:
    assert is_valid_analysis({**VALID_RESULT, "draft_reply": 42}) is False


def test_is_valid_analysis_rejects_missing_category_key() -> None:
    result = {k: v for k, v in VALID_RESULT.items() if k != "category"}
    assert is_valid_analysis(result) is False


def test_is_valid_analysis_rejects_non_dict_input_string() -> None:
    # Requirement 4.6: non-dict → False
    assert is_valid_analysis("not a dict") is False


def test_is_valid_analysis_rejects_non_dict_input_none() -> None:
    assert is_valid_analysis(None) is False


def test_is_valid_analysis_rejects_non_dict_input_list() -> None:
    assert is_valid_analysis(["billing", "high", "negative", "reply"]) is False


# ---------------------------------------------------------------------------
# Task 3.2 – RateLimiter
# ---------------------------------------------------------------------------


def test_rate_limiter_enforces_min_interval() -> None:
    """Two consecutive wait() calls must span at least min_interval_seconds."""
    # Requirement 8.1: keep Bedrock under 1 req/sec
    fake_time = 0.0

    def fake_monotonic() -> float:
        return fake_time

    sleep_amounts: list[float] = []

    def fake_sleep(secs: float) -> None:
        nonlocal fake_time
        sleep_amounts.append(secs)
        fake_time += secs

    limiter = RateLimiter(min_interval_seconds=1.0, _monotonic=fake_monotonic, _sleep=fake_sleep)

    # First call: no wait needed (last_call starts at 0.0, monotonic starts at 0.0)
    limiter.wait()

    # Second call immediately after (fake_time still 0.0 after first wait updates last_call)
    limiter.wait()

    # The second call must have slept for ~1.0 second
    assert len(sleep_amounts) >= 1
    assert sleep_amounts[-1] == pytest.approx(1.0, abs=0.01)


def test_rate_limiter_does_not_sleep_if_interval_elapsed() -> None:
    """No sleep when enough time has already passed."""
    fake_time = 0.0

    def fake_monotonic() -> float:
        return fake_time

    sleep_amounts: list[float] = []

    def fake_sleep(secs: float) -> None:
        nonlocal fake_time
        sleep_amounts.append(secs)
        fake_time += secs

    limiter = RateLimiter(min_interval_seconds=1.0, _monotonic=fake_monotonic, _sleep=fake_sleep)

    limiter.wait()  # first call at t=0
    fake_time = 2.0  # advance clock by 2 seconds
    limiter.wait()  # second call at t=2 — interval has elapsed

    assert len(sleep_amounts) == 0  # no sleep needed


# ---------------------------------------------------------------------------
# Task 4.2 – BedrockAnalyzer.analyze with fake boto3 client
# ---------------------------------------------------------------------------


def _make_converse_response(text: str) -> dict[str, Any]:
    """Build a minimal Converse API response as returned by boto3."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        },
        "stopReason": "end_turn",
    }


class FakeConverseClient:
    """Records calls and returns a canned response."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return _make_converse_response(self._response_text)


class FakeThrottleClient:
    """Raises a throttling ClientError on every converse call."""

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        raise botocore.exceptions.ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "Converse",
        )


class NoSleepLimiter:
    """Rate limiter stub that never sleeps — prevents real delays in unit tests."""

    def wait(self) -> None:
        pass


def _analyzer_with_client(client: Any) -> BedrockAnalyzer:
    return BedrockAnalyzer(client, "test-model-id", NoSleepLimiter())  # type: ignore[arg-type]


def test_analyze_returns_dict_with_four_keys() -> None:
    # Requirement 9.1: analyze(message) -> dict with the four keys
    canned = json.dumps(
        {"category": "billing", "urgency": "high", "sentiment": "negative", "draft_reply": "Reply"}
    )
    analyzer = _analyzer_with_client(FakeConverseClient(canned))
    result = analyzer.analyze("I need a refund")
    assert set(result.keys()) == {"category", "urgency", "sentiment", "draft_reply"}
    assert result["category"] == "billing"


def test_analyze_passes_only_message_and_returns_dict() -> None:
    # Requirement 7.1: only the message text is sent to the model
    canned = json.dumps(VALID_RESULT)
    fake_client = FakeConverseClient(canned)
    analyzer = _analyzer_with_client(fake_client)

    analyzer.analyze("just this message")

    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    # messages field must contain only the user message
    assert call["messages"] == [{"role": "user", "content": [{"text": "just this message"}]}]
    # no extra fields beyond system prompt, modelId, messages
    assert "modelId" in call


def test_analyze_calls_rate_limiter_once_per_call() -> None:
    # Requirement 8.2: exactly one rate-limiter wait per analyze call
    wait_count = 0

    class CountingLimiter:
        def wait(self) -> None:
            nonlocal wait_count
            wait_count += 1

    canned = json.dumps(VALID_RESULT)
    analyzer = BedrockAnalyzer(FakeConverseClient(canned), "m", CountingLimiter())  # type: ignore[arg-type]
    analyzer.analyze("hello")
    assert wait_count == 1
    analyzer.analyze("hello again")
    assert wait_count == 2


def test_analyze_raises_bedrock_analysis_error_on_throttle() -> None:
    # Requirement 4.5: throttle → BedrockAnalysisError
    analyzer = _analyzer_with_client(FakeThrottleClient())
    with pytest.raises(BedrockAnalysisError):
        analyzer.analyze("message")


def test_analyze_raises_bedrock_analysis_error_on_invalid_json() -> None:
    # Requirement 4.6: unparseable response → BedrockAnalysisError
    analyzer = _analyzer_with_client(FakeConverseClient("not json {{"))
    with pytest.raises(BedrockAnalysisError):
        analyzer.analyze("message")


def test_analyze_raises_bedrock_analysis_error_on_missing_response_key() -> None:
    # Unexpected response shape → BedrockAnalysisError
    class MissingKeyClient:
        def converse(self, **kwargs: Any) -> dict[str, Any]:
            return {}  # missing "output"

    analyzer = _analyzer_with_client(MissingKeyClient())
    with pytest.raises(BedrockAnalysisError):
        analyzer.analyze("message")


# ---------------------------------------------------------------------------
# Task 5.2 – get_analyzer env handling
# ---------------------------------------------------------------------------


def test_get_analyzer_returns_none_when_model_id_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Requirement 6.3: missing model id → None (not 503)
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    assert get_analyzer() is None


def test_get_analyzer_returns_none_when_model_id_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEDROCK_MODEL_ID", "   ")
    assert get_analyzer() is None


def test_get_analyzer_uses_default_region_when_aws_region_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Requirement 6.4: AWS_REGION defaults to us-east-1
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.delenv("AWS_REGION", raising=False)

    captured: dict[str, Any] = {}

    def fake_boto3_client(service: str, region_name: str = "") -> MagicMock:
        captured["region_name"] = region_name
        return MagicMock()

    with patch("smart_copilot.bedrock.boto3.client", side_effect=fake_boto3_client):
        result = get_analyzer()

    assert result is not None
    assert captured["region_name"] == "us-east-1"


def test_get_analyzer_uses_aws_region_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")

    captured: dict[str, Any] = {}

    def fake_boto3_client(service: str, region_name: str = "") -> MagicMock:
        captured["region_name"] = region_name
        return MagicMock()

    with patch("smart_copilot.bedrock.boto3.client", side_effect=fake_boto3_client):
        result = get_analyzer()

    assert result is not None
    assert captured["region_name"] == "eu-west-1"


def test_get_analyzer_returns_bedrock_analyzer_when_model_id_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEDROCK_MODEL_ID", "my-model-id")

    with patch("smart_copilot.bedrock.boto3.client", return_value=MagicMock()):
        result = get_analyzer()

    assert isinstance(result, BedrockAnalyzer)
