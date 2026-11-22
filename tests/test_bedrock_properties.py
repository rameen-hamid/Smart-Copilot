"""Hypothesis property-based tests for the bedrock-analysis feature."""

from __future__ import annotations

from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from smart_copilot.bedrock import (
    ALLOWED_CATEGORIES,
    ALLOWED_SENTIMENTS,
    ALLOWED_URGENCIES,
    BedrockAnalysisError,
    is_valid_analysis,
)
from smart_copilot.main import analyze_or_fallback

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

VALID_DRAFT = st.text(min_size=1).filter(lambda s: s.strip())

valid_analysis_st = st.fixed_dictionaries(
    {
        "category": st.sampled_from(sorted(ALLOWED_CATEGORIES)),
        "urgency": st.sampled_from(sorted(ALLOWED_URGENCIES)),
        "sentiment": st.sampled_from(sorted(ALLOWED_SENTIMENTS)),
        "draft_reply": VALID_DRAFT,
    }
)

# Any dict that violates at least one field
invalid_category_st = st.fixed_dictionaries(
    {
        "category": st.text().filter(lambda s: s not in ALLOWED_CATEGORIES),
        "urgency": st.sampled_from(sorted(ALLOWED_URGENCIES)),
        "sentiment": st.sampled_from(sorted(ALLOWED_SENTIMENTS)),
        "draft_reply": VALID_DRAFT,
    }
)
invalid_urgency_st = st.fixed_dictionaries(
    {
        "category": st.sampled_from(sorted(ALLOWED_CATEGORIES)),
        "urgency": st.text().filter(lambda s: s not in ALLOWED_URGENCIES),
        "sentiment": st.sampled_from(sorted(ALLOWED_SENTIMENTS)),
        "draft_reply": VALID_DRAFT,
    }
)
invalid_sentiment_st = st.fixed_dictionaries(
    {
        "category": st.sampled_from(sorted(ALLOWED_CATEGORIES)),
        "urgency": st.sampled_from(sorted(ALLOWED_URGENCIES)),
        "sentiment": st.text().filter(lambda s: s not in ALLOWED_SENTIMENTS),
        "draft_reply": VALID_DRAFT,
    }
)
blank_draft_st = st.fixed_dictionaries(
    {
        "category": st.sampled_from(sorted(ALLOWED_CATEGORIES)),
        "urgency": st.sampled_from(sorted(ALLOWED_URGENCIES)),
        "sentiment": st.sampled_from(sorted(ALLOWED_SENTIMENTS)),
        "draft_reply": st.text().filter(lambda s: not s.strip()),
    }
)

# Non-dict values
non_dict_st = st.one_of(
    st.none(),
    st.text(),
    st.integers(),
    st.lists(st.text()),
    st.booleans(),
)

# ---------------------------------------------------------------------------
# Property 1: Validation accepts only well-formed, in-enum results
# ---------------------------------------------------------------------------
# Feature: bedrock-analysis, Property 1: Validation accepts only well-formed, in-enum results


@given(result=valid_analysis_st)
@settings(max_examples=100)
def test_is_valid_analysis_accepts_only_well_formed(result: dict[str, Any]) -> None:
    """is_valid_analysis returns True iff all four fields are present and valid."""
    # Requirement 4.6, 5.1, 5.2, 5.3
    assert is_valid_analysis(result) is True


@given(result=st.one_of(invalid_category_st, invalid_urgency_st, invalid_sentiment_st, blank_draft_st))
@settings(max_examples=100)
def test_is_valid_analysis_rejects_out_of_spec_dicts(result: dict[str, Any]) -> None:
    assert is_valid_analysis(result) is False


@given(result=non_dict_st)
@settings(max_examples=100)
def test_is_valid_analysis_rejects_non_dicts(result: Any) -> None:
    assert is_valid_analysis(result) is False


# ---------------------------------------------------------------------------
# Property 2: A Bedrock failure never raises and always falls back to local
# ---------------------------------------------------------------------------
# Feature: bedrock-analysis, Property 2: A Bedrock failure never 500s and always falls back to local


class _RaisingAnalyzer:
    """Raises BedrockAnalysisError on every call."""

    def analyze(self, message: str) -> dict[str, Any]:
        raise BedrockAnalysisError("simulated failure")


class _BadOutputAnalyzer:
    """Returns a bad (non-valid) result on every call."""

    def __init__(self, bad: Any) -> None:
        self._bad = bad

    def analyze(self, message: str) -> Any:
        return self._bad


failing_analyzer_st = st.one_of(
    st.just(_RaisingAnalyzer()),
    st.builds(
        _BadOutputAnalyzer,
        bad=st.one_of(
            non_dict_st,
            invalid_category_st,
            invalid_urgency_st,
            invalid_sentiment_st,
            blank_draft_st,
        ),
    ),
)

non_empty_message_st = st.text(min_size=1).filter(lambda s: s.strip())


@given(message=non_empty_message_st, analyzer=failing_analyzer_st)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_bedrock_failure_always_falls_back_to_local(
    message: str, analyzer: Any
) -> None:
    """Any failing analyzer behavior must result in source='local' — never raises."""
    # Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3
    fields, source = analyze_or_fallback(message, analyzer)
    assert source == "local"
    assert fields["category"] in ALLOWED_CATEGORIES
    assert fields["urgency"] in ALLOWED_URGENCIES
    assert fields["sentiment"] in ALLOWED_SENTIMENTS
    assert isinstance(fields["draft_reply"], str) and fields["draft_reply"].strip()


class _OkAnalyzer:
    """Returns a fixed Valid_Analysis on every call."""

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def analyze(self, message: str) -> dict[str, Any]:
        return self._response


ok_analyzer_st = st.builds(_OkAnalyzer, response=valid_analysis_st)


# ---------------------------------------------------------------------------
# Property 3: Stored enum fields are always within the allowed sets
# ---------------------------------------------------------------------------
# Feature: bedrock-analysis, Property 3: Stored enum fields are always within the allowed sets


@given(
    message=non_empty_message_st,
    analyzer=st.one_of(
        ok_analyzer_st,
        failing_analyzer_st,
        st.just(None),
    ),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_stored_enum_fields_always_within_allowed_sets(
    message: str, analyzer: Any
) -> None:
    """Regardless of analyzer behavior, the returned fields always carry allowed enum values."""
    # Requirement 5.4
    fields, source = analyze_or_fallback(message, analyzer)
    assert fields["category"] in ALLOWED_CATEGORIES
    assert fields["urgency"] in ALLOWED_URGENCIES
    assert fields["sentiment"] in ALLOWED_SENTIMENTS
    assert source in {"bedrock", "local"}
