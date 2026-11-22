import pytest

from smart_copilot.classifier import (
    classify_category,
    classify_sentiment,
    classify_urgency,
    draft_reply,
)

BILLING = ["refund", "charge", "charged", "invoice", "payment", "billing", "subscription", "price"]
TECHNICAL = ["error", "crash", "crashes", "bug", "broken", "slow", "freezes", "fails"]
ACCOUNT = ["password", "login", "account", "username", "locked", "access"]
HIGH = ["urgent", "immediately", "asap", "emergency", "critical", "outage"]
MEDIUM = ["issue", "problem", "waiting", "delay", "delayed"]
NEGATIVE = [
    "angry",
    "terrible",
    "awful",
    "worst",
    "unacceptable",
    "frustrated",
    "disappointed",
    "furious",
    "ridiculous",
]
POSITIVE = ["thanks", "thank", "great", "love", "appreciate", "awesome", "excellent", "happy"]


@pytest.mark.parametrize("word", BILLING)
def test_billing_keywords(word: str) -> None:
    assert classify_category(f"About my {word} today") == "billing"


@pytest.mark.parametrize("word", TECHNICAL)
def test_technical_keywords(word: str) -> None:
    assert classify_category(f"The app {word} today") == "technical"


@pytest.mark.parametrize("word", ACCOUNT)
def test_account_keywords(word: str) -> None:
    assert classify_category(f"About my {word} today") == "account"


def test_category_other_when_no_keyword() -> None:
    assert classify_category("Hello there") == "other"


def test_category_order_billing_before_technical_before_account() -> None:
    assert classify_category("refund error password") == "billing"
    assert classify_category("error password") == "technical"
    assert classify_category("password") == "account"


def test_keyword_matches_whole_word_and_ignores_case() -> None:
    assert classify_category("REFUND please") == "billing"
    assert classify_category("refunds please") == "other"
    assert classify_category("Refund, please.") == "billing"


@pytest.mark.parametrize("word", HIGH)
def test_high_urgency_keywords(word: str) -> None:
    assert classify_urgency(f"This is {word}") == "high"


@pytest.mark.parametrize("word", MEDIUM)
def test_medium_urgency_keywords(word: str) -> None:
    assert classify_urgency(f"There is an {word}") == "medium"


def test_urgency_low_when_no_keyword() -> None:
    assert classify_urgency("Hello there") == "low"


def test_high_urgency_beats_medium() -> None:
    assert classify_urgency("urgent problem") == "high"


@pytest.mark.parametrize("word", NEGATIVE)
def test_negative_keywords(word: str) -> None:
    assert classify_sentiment(f"I am {word}") == "negative"


@pytest.mark.parametrize("word", POSITIVE)
def test_positive_keywords(word: str) -> None:
    assert classify_sentiment(f"I say {word}") == "positive"


def test_sentiment_neutral_when_no_keyword() -> None:
    assert classify_sentiment("Hello there") == "neutral"


def test_negative_wins_over_positive() -> None:
    assert classify_sentiment("thanks but this is terrible") == "negative"


def test_classifier_is_deterministic() -> None:
    message = "Urgent refund, I am furious"
    assert classify_category(message) == classify_category(message)
    assert classify_urgency(message) == classify_urgency(message)
    assert classify_sentiment(message) == classify_sentiment(message)


@pytest.mark.parametrize("category", ["billing", "technical", "account", "other"])
def test_draft_reply_is_fixed_template_per_category(category: str) -> None:
    reply = draft_reply(category)
    assert reply
    assert reply == draft_reply(category)


def test_draft_replies_differ_by_category() -> None:
    replies = {draft_reply(c) for c in ["billing", "technical", "account", "other"]}
    assert len(replies) == 4
