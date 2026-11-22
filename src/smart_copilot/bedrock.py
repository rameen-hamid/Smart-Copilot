"""Bedrock analysis wrapper, validation, and FastAPI dependency."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import boto3
import botocore.exceptions

ALLOWED_CATEGORIES: frozenset[str] = frozenset({"billing", "technical", "account", "other"})
ALLOWED_URGENCIES: frozenset[str] = frozenset({"low", "medium", "high"})
ALLOWED_SENTIMENTS: frozenset[str] = frozenset({"negative", "neutral", "positive"})

SYSTEM_PROMPT = (
    "You are a customer support ticket classifier. "
    "For the given customer message, return ONLY a JSON object "
    "(no markdown, no code blocks, no explanation) with exactly these four fields: "
    '"category": one of "billing", "technical", "account", "other"; '
    '"urgency": one of "low", "medium", "high"; '
    '"sentiment": one of "negative", "neutral", "positive"; '
    '"draft_reply": a brief professional reply (do not reference personal details). '
    "Example: "
    '{"category":"billing","urgency":"high","sentiment":"negative",'
    '"draft_reply":"Thank you for contacting us. We are reviewing your account."}'
)


class BedrockAnalysisError(Exception):
    """Raised by BedrockAnalyzer.analyze on any failure."""


def is_valid_analysis(result: Any) -> bool:
    """Return True iff result is a dict with all four fields in their allowed sets."""
    if not isinstance(result, dict):
        return False
    try:
        category = result["category"]
        urgency = result["urgency"]
        sentiment = result["sentiment"]
        draft = result["draft_reply"]
    except KeyError:
        return False
    if category not in ALLOWED_CATEGORIES:
        return False
    if urgency not in ALLOWED_URGENCIES:
        return False
    if sentiment not in ALLOWED_SENTIMENTS:
        return False
    return isinstance(draft, str) and bool(draft.strip())


class RateLimiter:
    """Enforces a minimum interval between calls using a monotonic clock."""

    def __init__(
        self,
        min_interval_seconds: float = 1.0,
        _monotonic: Any = None,
        _sleep: Any = None,
    ) -> None:
        self._min_interval = min_interval_seconds
        self._monotonic = _monotonic if _monotonic is not None else time.monotonic
        self._sleep = _sleep if _sleep is not None else time.sleep
        self._last_call: float = float("-inf")
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Block until at least min_interval_seconds have passed since the last call."""
        with self._lock:
            now = self._monotonic()
            elapsed = now - self._last_call
            if elapsed < self._min_interval:
                self._sleep(self._min_interval - elapsed)
            self._last_call = self._monotonic()


class BedrockAnalyzer:
    """Wraps a boto3 bedrock-runtime client behind a single analyze() method."""

    def __init__(self, client: Any, model_id: str, rate_limiter: RateLimiter) -> None:
        self._client = client
        self._model_id = model_id
        self._rate_limiter = rate_limiter

    def analyze(self, message: str) -> dict[str, Any]:
        """Call the Bedrock Converse API with only the message text.

        Returns a dict with keys category, urgency, sentiment, draft_reply.
        Raises BedrockAnalysisError on any failure.
        """
        self._rate_limiter.wait()
        try:
            response = self._client.converse(
                modelId=self._model_id,
                system=[{"text": SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": [{"text": message}]}],
            )
            text: str = response["output"]["message"]["content"][0]["text"]
            return json.loads(text)
        except botocore.exceptions.ClientError as exc:
            raise BedrockAnalysisError(f"Bedrock client error: {exc}") from exc
        except botocore.exceptions.BotoCoreError as exc:
            raise BedrockAnalysisError(f"Bedrock transport error: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise BedrockAnalysisError("Bedrock response is not valid JSON") from exc
        except (KeyError, TypeError, IndexError) as exc:
            raise BedrockAnalysisError(f"Unexpected Bedrock response shape: {exc}") from exc


# --- Shared rate limiter singleton ---

_shared_rate_limiter: RateLimiter | None = None
_shared_limiter_lock = threading.Lock()


def _get_shared_rate_limiter() -> RateLimiter:
    global _shared_rate_limiter
    with _shared_limiter_lock:
        if _shared_rate_limiter is None:
            _shared_rate_limiter = RateLimiter()
        return _shared_rate_limiter


# --- FastAPI dependency ---

def get_analyzer() -> BedrockAnalyzer | None:
    """Return a configured BedrockAnalyzer, or None when BEDROCK_MODEL_ID is unset."""
    model_id = os.environ.get("BEDROCK_MODEL_ID", "").strip()
    if not model_id:
        return None
    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-runtime", region_name=region)
    return BedrockAnalyzer(client, model_id, _get_shared_rate_limiter())
