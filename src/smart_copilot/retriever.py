"""Keyword-overlap snippet retriever."""

from __future__ import annotations

import re
from typing import Any

SNIPPET_MAX_LEN = 300


def keyword_overlap(query: str, text: str) -> int:
    """Count of distinct lowercase words appearing in both query and text."""
    query_words = set(re.findall(r"[a-z']+", query.lower()))
    text_words = set(re.findall(r"[a-z']+", text.lower()))
    return len(query_words & text_words)


def retrieve_snippets(
    message: str,
    past_tickets: list[dict[str, Any]],
    kb_docs: list[dict[str, str]],
    top_n: int = 3,
) -> list[str]:
    """Return up to top_n snippets most relevant to message by keyword overlap.

    Corpus construction (insertion order determines tie-breaking):
    1. Each past ticket contributes: ticket["message"] + " " + ticket["draft_reply"]
    2. Each KB document contributes: doc["content"]

    Returns snippets with score > 0, sorted descending by score (ties broken by
    insertion order). Each snippet is truncated to SNIPPET_MAX_LEN characters.
    Returns [] when the corpus is empty or all scores are zero.
    """
    corpus: list[str] = []
    for ticket in past_tickets:
        msg = ticket.get("message", "")
        draft = ticket.get("draft_reply", "")
        corpus.append(f"{msg} {draft}")
    for doc in kb_docs:
        corpus.append(doc.get("content", ""))

    if not corpus:
        return []

    scored: list[tuple[int, int, str]] = [
        (keyword_overlap(message, item), idx, item)
        for idx, item in enumerate(corpus)
    ]

    # Keep positive scores only; sort descending by score, ties by insertion order
    positive = [(score, idx, item) for score, idx, item in scored if score > 0]
    positive.sort(key=lambda x: (-x[0], x[1]))

    return [item[:SNIPPET_MAX_LEN] for _, _, item in positive[:top_n]]
