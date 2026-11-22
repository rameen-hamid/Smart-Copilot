"""Unit tests for retriever.py: keyword_overlap and retrieve_snippets."""

from __future__ import annotations

from typing import Any

from smart_copilot.retriever import keyword_overlap, retrieve_snippets

# ---------------------------------------------------------------------------
# Task 3.2 – keyword_overlap
# ---------------------------------------------------------------------------


def test_keyword_overlap_counts_distinct_words() -> None:
    # Requirement 2.7: distinct word overlap (not occurrence count)
    assert keyword_overlap("billing billing billing", "billing") == 1


def test_keyword_overlap_case_insensitive() -> None:
    # Requirement 2.7: case-insensitive
    assert keyword_overlap("BILLING", "billing expense") == 1


def test_keyword_overlap_no_match() -> None:
    assert keyword_overlap("xyz", "abc def") == 0


def test_keyword_overlap_multiple_matches() -> None:
    assert keyword_overlap("refund billing payment", "billing payment issue") == 2


def test_keyword_overlap_empty_query() -> None:
    assert keyword_overlap("", "billing") == 0


def test_keyword_overlap_empty_text() -> None:
    assert keyword_overlap("billing", "") == 0


# ---------------------------------------------------------------------------
# Task 3.2 – retrieve_snippets
# ---------------------------------------------------------------------------


def _make_ticket(message: str, draft: str = "Thank you.") -> dict[str, Any]:
    return {
        "id": "fake-id",
        "message": message,
        "draft_reply": draft,
        "category": "other",
        "urgency": "low",
        "sentiment": "neutral",
        "source": "local",
        "recommended_solution": "n/a",
        "source_snippets": [],
    }


def _make_kb_doc(content: str, title: str = "doc") -> dict[str, str]:
    return {"title": title, "content": content}


def test_empty_corpus_returns_empty_list() -> None:
    # Requirement 2.2
    assert retrieve_snippets("hello", [], []) == []


def test_all_zero_scores_returns_empty_list() -> None:
    # Requirement 2.8: all-zero scores → []
    kb = [_make_kb_doc("abc def ghi")]
    assert retrieve_snippets("xyz", [], kb) == []


def test_top_3_selection_by_score() -> None:
    # Requirement 2.1: return top 3 by score
    # Scores: doc0=5, doc1=1, doc2=4, doc3=3, doc4=2  →  top3: doc0,doc2,doc3
    query = "a b c d e"
    kb = [
        _make_kb_doc("a b c d e"),   # score 5
        _make_kb_doc("a"),            # score 1
        _make_kb_doc("a b c d"),      # score 4
        _make_kb_doc("a b c"),        # score 3
        _make_kb_doc("a b"),          # score 2
    ]
    result = retrieve_snippets(query, [], kb)
    assert len(result) == 3
    # Top 3 by score: "a b c d e" (5), "a b c d" (4), "a b c" (3)
    assert result[0] == "a b c d e"
    assert result[1] == "a b c d"
    assert result[2] == "a b c"


def test_fewer_than_three_items_returned_when_corpus_small() -> None:
    # Requirement 2.3: returns all items with score > 0 when < top_n
    kb = [_make_kb_doc("billing refund"), _make_kb_doc("payment")]
    result = retrieve_snippets("billing payment", [], kb)
    assert len(result) == 2


def test_truncation_at_300_chars() -> None:
    # Requirement 2.5: items > 300 chars are truncated to exactly 300
    long_content = "billing " * 60  # 480 chars
    kb = [_make_kb_doc(long_content)]
    result = retrieve_snippets("billing", [], kb)
    assert len(result) == 1
    assert len(result[0]) == 300


def test_no_truncation_at_exactly_300_chars() -> None:
    # Requirement 2.6: exactly 300 chars → returned in full
    content = "a " * 150  # 300 chars, space-separated tokens that overlap "a"
    kb = [_make_kb_doc(content)]
    result = retrieve_snippets("a", [], kb)
    assert len(result[0]) == 300


def test_no_truncation_below_300_chars() -> None:
    # Requirement 2.6: short items returned in full
    content = "billing refund"
    kb = [_make_kb_doc(content)]
    result = retrieve_snippets("billing", [], kb)
    assert result[0] == content


def test_past_ticket_beats_kb_doc_on_tie() -> None:
    # Requirement 2.4: past tickets precede KB docs in corpus → win on tie
    ticket = _make_ticket("billing", "Thank you billing.")
    kb_doc = _make_kb_doc("billing account")
    result = retrieve_snippets("billing", [ticket], [kb_doc])
    assert len(result) == 2
    # Past ticket is first in corpus so its snippet should appear first on tie
    # ticket corpus string: "billing Thank you billing."
    # kb_doc string: "billing account"
    # Both have score 1 for query "billing"
    # Past ticket is insertion index 0, kb_doc is index 1 → ticket wins
    assert "billing" in result[0]
    assert result[0].startswith("billing")  # ticket message


def test_past_tickets_included_in_corpus() -> None:
    # Requirement 2.4: past ticket message+draft_reply is in corpus
    ticket = _make_ticket("refund request", "We will process your refund.")
    result = retrieve_snippets("refund", [ticket], [])
    assert len(result) == 1
    assert "refund" in result[0].lower()


def test_only_positive_score_items_returned() -> None:
    # Requirement 2.1: items with score 0 are excluded
    kb = [
        _make_kb_doc("billing payment"),   # score 1 for "billing"
        _make_kb_doc("xyz abc def"),        # score 0 for "billing"
    ]
    result = retrieve_snippets("billing", [], kb)
    assert len(result) == 1
    assert "billing" in result[0]


def test_top_n_parameter_respected() -> None:
    kb = [_make_kb_doc(f"billing {i}") for i in range(10)]
    result = retrieve_snippets("billing", [], kb, top_n=2)
    assert len(result) == 2
