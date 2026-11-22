"""Hypothesis property-based tests for the agent-desk feature."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from smart_copilot.bedrock import BedrockAnalysisError
from smart_copilot.kb import load_kb_documents
from smart_copilot.main import recommend_or_fallback
from smart_copilot.retriever import keyword_overlap, retrieve_snippets

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

alpha_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    min_size=1,
    max_size=20,
)
corpus_text = st.text(alphabet="abcde ", min_size=0, max_size=100)
non_empty_message = st.text(min_size=1, max_size=200).filter(str.strip)


# ---------------------------------------------------------------------------
# Property 1: KB loader returns exactly the .txt files with correct metadata
# Feature: agent-desk, Property 1: KB loader returns exactly the .txt files with correct metadata
# ---------------------------------------------------------------------------


@given(
    pairs=st.lists(
        st.tuples(alpha_text, st.sampled_from([".txt", ".md", ".json", ".csv"])),
        min_size=0,
        max_size=8,
        unique_by=lambda p: p[0],
    )
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property1_kb_loader_txt_filter(
    kb_path: Path, pairs: list[tuple[str, str]]
) -> None:
    """KB loader returns exactly the .txt files with correct title and content."""
    # Clear previous Hypothesis example state
    for f in list(kb_path.iterdir()):
        f.unlink()

    expected_titles: set[str] = set()
    for stem, ext in pairs:
        content = f"content of {stem}"
        (kb_path / f"{stem}{ext}").write_text(content)
        if ext == ".txt":
            expected_titles.add(stem)

    result = load_kb_documents(kb_path)
    assert {d["title"] for d in result} == expected_titles
    for doc in result:
        assert doc["content"] == f"content of {doc['title']}"


# ---------------------------------------------------------------------------
# Property 2: Retriever returns only positive-scored snippets in score order
# Feature: agent-desk, Property 2: Retriever returns only positive-scored snippets in score order
# ---------------------------------------------------------------------------


@given(
    query=st.text(alphabet="abcde ", min_size=1, max_size=50),
    items=st.lists(corpus_text, min_size=0, max_size=10),
)
@settings(max_examples=100)
def test_property2_retriever_positive_score_ordering(
    query: str, items: list[str]
) -> None:
    """All returned snippets have score > 0 and are in non-increasing score order."""
    kb_docs = [{"title": f"doc{i}", "content": item} for i, item in enumerate(items)]
    result = retrieve_snippets(query, [], kb_docs)

    # Every returned snippet must have score > 0
    for snippet in result:
        assert keyword_overlap(query, snippet) > 0

    # Scores must be non-increasing
    scores = [keyword_overlap(query, s) for s in result]
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1]


# ---------------------------------------------------------------------------
# Property 3: Snippet length invariant
# Feature: agent-desk, Property 3: Snippet length invariant
# ---------------------------------------------------------------------------


@given(item=st.text(min_size=0, max_size=600))
@settings(max_examples=100)
def test_property3_snippet_length_invariant(item: str) -> None:
    """Each snippet length equals min(len(original), 300)."""
    # Force a match by using a word that appears in the item (or just a common char)
    # Use "a" as the query, and ensure "a" is in the item
    if not item:
        return  # skip empty items — keyword_overlap will be 0, snippet won't be returned
    # Inject one matching word into the item so it always has score > 0
    item_with_match = "a " + item
    kb_docs = [{"title": "doc", "content": item_with_match}]
    result = retrieve_snippets("a", [], kb_docs)
    if result:
        assert len(result[0]) == min(len(item_with_match), 300)


# ---------------------------------------------------------------------------
# Property 4: Keyword overlap is case-invariant
# Feature: agent-desk, Property 4: Keyword overlap is case-invariant
# ---------------------------------------------------------------------------


@given(
    query=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
        min_size=0,
        max_size=50,
    ),
    text=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
        min_size=0,
        max_size=50,
    ),
)
@settings(max_examples=100)
def test_property4_keyword_overlap_case_invariant(query: str, text: str) -> None:
    """keyword_overlap is unaffected by letter case."""
    base = keyword_overlap(query, text)
    assert keyword_overlap(query.upper(), text) == base
    assert keyword_overlap(query, text.lower()) == base
    assert keyword_overlap(query.upper(), text.lower()) == base


# ---------------------------------------------------------------------------
# Property 5: recommend_or_fallback always returns a non-empty string
# Feature: agent-desk, Property 5: recommend_or_fallback always returns a non-empty string
# ---------------------------------------------------------------------------


class _OkFake:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def recommend(self, message: str, snippets: list[str]) -> str:
        return self._reply


class _RaisingFake:
    def recommend(self, message: str, snippets: list[str]) -> str:
        raise BedrockAnalysisError("simulated")


@given(
    message=non_empty_message,
    snippets=st.lists(st.text(min_size=1), min_size=0, max_size=5),
    reply=st.text(min_size=0, max_size=200),
)
@settings(max_examples=100)
def test_property5_recommend_or_fallback_always_non_empty(
    message: str, snippets: list[str], reply: str
) -> None:
    """recommend_or_fallback always returns a non-empty string for any input."""
    for analyzer in [None, _RaisingFake(), _OkFake(reply)]:
        result = recommend_or_fallback(message, snippets, analyzer)  # type: ignore[arg-type]
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Property 6: Ticket persistence preserves all nine fields
# Feature: agent-desk, Property 6: Ticket persistence preserves all nine fields
# ---------------------------------------------------------------------------


@given(message=st.text(min_size=1, max_size=100).filter(str.strip))
@settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property6_ticket_persistence_round_trip(
    message: str,
    client: TestClient,
    tickets_file: Path,
) -> None:
    """POST then GET returns a ticket with all nine fields and correct types."""
    # Clear between Hypothesis examples to avoid cross-contamination
    if tickets_file.exists():
        tickets_file.unlink()

    response = client.post("/tickets", json={"message": message})
    assert response.status_code == 201
    created = response.json()

    # All nine fields present
    expected_keys = {
        "id", "message", "category", "urgency", "sentiment",
        "draft_reply", "source", "recommended_solution", "source_snippets",
    }
    assert set(created.keys()) == expected_keys

    # New fields have correct types
    assert isinstance(created["recommended_solution"], str)
    assert len(created["recommended_solution"]) > 0
    assert isinstance(created["source_snippets"], list)

    # Round-trip: GET /tickets contains the same ticket
    listed = client.get("/tickets").json()
    matching = [t for t in listed if t["id"] == created["id"]]
    assert len(matching) == 1
    ticket = matching[0]

    # Pre-existing fields must match the POST response exactly
    for field in ["id", "message", "category", "urgency", "sentiment", "draft_reply", "source"]:
        assert ticket[field] == created[field]
