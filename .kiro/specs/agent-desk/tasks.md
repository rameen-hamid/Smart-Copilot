# Implementation Plan: Agent Desk

## Overview

Extends the ticket desk with a grounded recommended solution on every new
ticket. The plan adds `kb.py` (KB loader), `retriever.py` (keyword-overlap
scoring), a `recommend()` method on `BedrockAnalyzer`, and wires everything
into `main.py`. `page.py` is updated to show all eight ticket fields. All new
pure functions are covered by unit and property-based tests using pytest and
Hypothesis. No existing endpoint, field, or storage behaviour changes.

## Tasks

- [ ] 1. Prepare test infrastructure and update assertions for new ticket fields
  - [ ] 1.1 Add `kb_path` autouse fixture to `tests/conftest.py`
    - Add after the existing `tickets_file` fixture:
      ```python
      @pytest.fixture(autouse=True)
      def kb_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
          path = tmp_path / "kb"
          path.mkdir()
          monkeypatch.setenv("KB_PATH", str(path))
          return path
      ```
    - Import `Path` from `pathlib` is already present; no new imports needed
    - **Validates:** `tests/test_kb.py::test_kb_path_reads_from_env_var` asserts
      `get_kb_path() == Path(os.environ["KB_PATH"])` — the fixture must set
      `KB_PATH` so that `get_kb_path()` returns the temp path, not `data/kb/`
    - _Requirements: 1.4_

  - [ ] 1.2 Update `test_create_returns_201_and_full_ticket` in `tests/test_tickets_api.py`
    - Replace the existing `set(ticket) == {"id", "message", ...}` assertion with:
      ```python
      assert set(ticket) == {
          "id", "message", "category", "urgency", "sentiment",
          "draft_reply", "source", "recommended_solution", "source_snippets",
      }
      ```
    - Add after the `source` assertion:
      ```python
      assert isinstance(ticket["recommended_solution"], str)
      assert len(ticket["recommended_solution"]) > 0
      assert ticket["source_snippets"] == []  # empty KB → no snippets
      ```
    - **Validates (intentionally red until Task 5.1):**
      `tests/test_tickets_api.py::test_create_returns_201_and_full_ticket`
      asserts `set(ticket) == {..., "recommended_solution", "source_snippets"}`,
      `ticket["source_snippets"] == []`, and
      `len(ticket["recommended_solution"]) > 0`
    - _Requirements: 3.1, 3.2_

- [ ] 2. Create KB loader (`src/smart_copilot/kb.py`)
  - [ ] 2.1 Create `src/smart_copilot/kb.py` with `get_kb_path()` and `load_kb_documents()`
    - `get_kb_path() -> Path`: reads `KB_PATH` env var; defaults to `Path("data/kb/")` when unset
    - `load_kb_documents(kb_path: Path) -> list[dict[str, str]]`:
      - Returns `[]` without raising when `kb_path` does not exist
      - Returns `[]` without raising when `kb_path` is an empty directory
      - For each `.txt` file found: returns `{"title": stem, "content": file_text.strip()}`
      - Silently ignores files without the `.txt` extension
      - Raises `TicketStoreError` (import from `smart_copilot.storage`) with context on `OSError` reading a specific file
    - **Validates:**
      `tests/test_kb.py::test_missing_directory_returns_empty_list` asserts
      `load_kb_documents(tmp_path / "no_dir") == []`;
      `tests/test_kb.py::test_loads_txt_files_with_correct_title_and_content`
      asserts `result[0]["title"] == "billing"` and
      `result[0]["content"] == "hello world"` after writing `"hello world"` to
      `kb_path / "billing.txt"`;
      `tests/test_kb.py::test_ignores_non_txt_files` asserts `result == []`
      after writing only `.md` and `.json` files
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 2.2 Write `tests/test_kb.py`
    - `test_missing_directory_returns_empty_list`:
      `assert load_kb_documents(tmp_path / "no_dir") == []`
    - `test_empty_directory_returns_empty_list`:
      `assert load_kb_documents(tmp_path / "empty") == []`
    - `test_loads_txt_files_with_correct_title_and_content`:
      write `"hello world"` to `kb_path / "billing.txt"`;
      `assert result[0]["title"] == "billing"` and
      `result[0]["content"] == "hello world"`
    - `test_strips_whitespace_from_content`:
      write `"  hello  \n"` to a `.txt` file;
      `assert result[0]["content"] == "hello"`
    - `test_ignores_non_txt_files`:
      write `kb_path / "readme.md"` and `kb_path / "data.json"`;
      `assert result == []`
    - `test_mixed_txt_and_non_txt_returns_only_txt`:
      write `"content"` to `kb_path / "a.txt"` and `kb_path / "b.md"`;
      `assert len(result) == 1` and `result[0]["title"] == "a"`
    - `test_kb_path_reads_from_env_var`:
      `monkeypatch.setenv("KB_PATH", str(tmp_path))`;
      `assert get_kb_path() == tmp_path`
    - `test_kb_path_defaults_to_data_kb`:
      `monkeypatch.delenv("KB_PATH", raising=False)`;
      `assert get_kb_path() == Path("data/kb/")`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 3. Create snippet retriever (`src/smart_copilot/retriever.py`)
  - [ ] 3.1 Create `src/smart_copilot/retriever.py` with `keyword_overlap()` and `retrieve_snippets()`
    - `keyword_overlap(query: str, text: str) -> int`:
      count of distinct lowercase words in both; use
      `re.findall(r"[a-z']+", text.lower())` for tokenisation (same pattern as
      `classifier.py`)
    - `retrieve_snippets(message: str, past_tickets: list[dict[str, Any]], kb_docs: list[dict[str, str]], top_n: int = 3) -> list[str]`:
      - Builds corpus in order: `ticket["message"] + " " + ticket["draft_reply"]`
        for each past ticket, then `doc["content"]` for each KB document
      - Scores every corpus item with `keyword_overlap(message, item)`
      - Returns the top `top_n` items with score > 0, sorted descending by score
        (ties broken by earlier insertion order)
      - Truncates each returned snippet to at most 300 characters
      - Returns `[]` for an empty corpus or when all scores are zero
    - **Validates:**
      `tests/test_retriever.py::test_empty_corpus_returns_empty_list` asserts
      `retrieve_snippets("hello", [], []) == []`;
      `tests/test_retriever.py::test_truncation_at_300_chars` asserts
      `len(result[0]) == 300` for a 400-character corpus item;
      `tests/test_retriever.py::test_keyword_overlap_counts_distinct_words`
      asserts `keyword_overlap("billing billing billing", "billing") == 1`;
      `tests/test_retriever.py::test_past_ticket_beats_kb_doc_on_tie` asserts
      the past-ticket snippet appears before the KB-doc snippet when both have
      equal score
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]* 3.2 Write `tests/test_retriever.py`
    - `test_empty_corpus_returns_empty_list`:
      `assert retrieve_snippets("hello", [], []) == []`
    - `test_all_zero_scores_returns_empty_list`:
      query `"xyz"` vs corpus `["abc def"]`; `assert result == []`
    - `test_top_3_selection_by_score`:
      5 KB docs with content words overlapping the query 5, 3, 1, 4, 2 times
      respectively; `assert len(result) == 3` and score of each is > score of
      items ranked 4th and 5th
    - `test_truncation_at_300_chars`:
      one KB doc with `"billing " * 60` (480 chars); query `"billing"`;
      `assert len(result[0]) == 300`
    - `test_no_truncation_at_exactly_300_chars`:
      `"a" * 300`; `assert len(result[0]) == 300`
    - `test_no_truncation_below_300_chars`:
      `"billing short"` (13 chars); `assert len(result[0]) == 13`
    - `test_case_insensitive_matching`:
      `assert keyword_overlap("BILLING", "billing expense") == 1`
    - `test_past_ticket_beats_kb_doc_on_tie`:
      one past ticket and one KB doc, both containing exactly the query word;
      `assert result[0]` starts with the past-ticket corpus string (truncated)
    - `test_keyword_overlap_counts_distinct_words`:
      `assert keyword_overlap("billing billing billing", "billing") == 1`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

- [ ] 4. Add `recommend()` to `BedrockAnalyzer` in `src/smart_copilot/bedrock.py`
  - [ ] 4.1 Add `RECOMMEND_SYSTEM_PROMPT` constant and `recommend()` method to `BedrockAnalyzer`
    - Add module-level constant:
      ```python
      RECOMMEND_SYSTEM_PROMPT = (
          "You are a customer support assistant. "
          "Using only the provided context snippets, write a specific, actionable "
          "recommended solution for the customer's issue. "
          "Return only the recommendation text with no markdown, no code blocks, "
          "and no explanation."
      )
      ```
    - Add method `recommend(self, message: str, snippets: list[str]) -> str`:
      - Calls `self._rate_limiter.wait()` before the Converse call (shared
        singleton; keeps total Bedrock calls under 1 req/sec alongside `analyze`)
      - Builds user content:
        `f"Customer message: {message}\n\nContext:\n" + "\n---\n".join(snippets)`
      - Converse call shape mirrors `analyze()`:
        `response["output"]["message"]["content"][0]["text"]`
      - Raises `BedrockAnalysisError` if `text.strip()` is empty
      - Raises `BedrockAnalysisError` on `ClientError`, `BotoCoreError`,
        `KeyError`, `TypeError`, `IndexError` (same pattern as `analyze()`)
    - **Validates:**
      `tests/test_bedrock.py::test_recommend_returns_string_from_converse`
      asserts `analyzer.recommend("broken item", ["past fix"]) == "Use our refund process"`;
      `tests/test_bedrock.py::test_recommend_raises_on_empty_response`
      asserts `pytest.raises(BedrockAnalysisError)` when fake client returns `""`;
      `tests/test_bedrock.py::test_recommend_calls_rate_limiter_once`
      asserts `wait_count == 1` after a single `recommend()` call
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 4.2 Extend `tests/test_bedrock.py` with `recommend()` unit tests
    - Reuse the existing `FakeConverseClient`, `FakeThrottleClient`, and
      `NoSleepLimiter` helpers already defined in that file
    - `test_recommend_returns_string_from_converse`:
      `FakeConverseClient("Use our refund process")`; call
      `analyzer.recommend("broken item", ["past fix"])`;
      `assert result == "Use our refund process"`
    - `test_recommend_calls_rate_limiter_once`:
      counting limiter (`wait_count` incremented in `wait()`);
      `assert wait_count == 1` after one `recommend()` call
    - `test_recommend_raises_on_throttle`:
      `FakeThrottleClient`; `pytest.raises(BedrockAnalysisError)`
    - `test_recommend_raises_on_empty_response`:
      `FakeConverseClient("")`; `pytest.raises(BedrockAnalysisError)`
    - `test_recommend_passes_message_and_snippets`:
      spy records `kwargs`; after `recommend("test msg", ["s1", "s2"])`,
      assert `"Customer message: test msg" in kwargs["messages"][0]["content"][0]["text"]`
      and `"s1" in kwargs["messages"][0]["content"][0]["text"]`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 5. Wire recommendation logic into `main.py`
  - [ ] 5.1 Update `src/smart_copilot/main.py`
    - Extend `Ticket` Pydantic model — add two new required fields:
      ```python
      recommended_solution: str
      source_snippets: list[str]
      ```
    - Add module-level constant (non-empty statically defined string):
      ```python
      LOCAL_FALLBACK_RECOMMENDATION: str = (
          "Please review the ticket manually and consult your team's knowledge base "
          "for the most appropriate resolution."
      )
      ```
    - Add new helper:
      ```python
      def recommend_or_fallback(
          message: str,
          snippets: list[str],
          analyzer: BedrockAnalyzer | None,
      ) -> str:
      ```
      Returns `LOCAL_FALLBACK_RECOMMENDATION` when `analyzer is None` or
      `snippets` is empty; otherwise calls `analyzer.recommend(message, snippets)`,
      catching `BedrockAnalysisError` and returning `LOCAL_FALLBACK_RECOMMENDATION`
    - Add imports:
      ```python
      from smart_copilot.kb import get_kb_path, load_kb_documents
      from smart_copilot.retriever import retrieve_snippets
      ```
    - Update `create_ticket` route: call `storage.load_tickets()` to get
      `past_tickets` **before** `storage.add_ticket()`; call
      `load_kb_documents(get_kb_path())`; call
      `retrieve_snippets(body.message, past_tickets, kb_docs)`; call
      `recommend_or_fallback(body.message, snippets, analyzer)`; include both
      new fields in the ticket dict passed to `storage.add_ticket()`
    - **Validates:**
      `tests/test_tickets_api.py::test_create_returns_201_and_full_ticket`
      asserts `set(ticket) == {..., "recommended_solution", "source_snippets"}` and
      `ticket["source_snippets"] == []` (empty KB fixture) and
      `len(ticket["recommended_solution"]) > 0`;
      `tests/test_agent_desk_api.py::test_bedrock_recommend_success_sets_recommended_solution`
      asserts `ticket["recommended_solution"] == "Specific fix"`;
      `tests/test_agent_desk_api.py::test_empty_corpus_gives_fallback_and_empty_snippets`
      asserts `ticket["source_snippets"] == []` and
      `ticket["recommended_solution"] == LOCAL_FALLBACK_RECOMMENDATION`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3_

  - [ ] 5.2 Add `recommend()` stub to every fake analyzer in `tests/test_bedrock_api.py`
    - `FakeAnalyzer`: add `def recommend(self, message: str, snippets: list[str]) -> str: return "stub recommendation"`
    - `FakeThrottleAnalyzer`: add `def recommend(self, message: str, snippets: list[str]) -> str: return "stub recommendation"`
    - `FakeMalformedAnalyzer`: add `def recommend(self, message: str, snippets: list[str]) -> str: return "stub recommendation"`
    - Add `list` import to the annotation (`snippets: list[str]`) if needed; `from __future__ import annotations` is already present
    - **Validates:**
      `tests/test_bedrock_api.py::test_valid_analysis_sets_bedrock_source_and_fields`
      asserts `ticket["source"] == "bedrock"` and `response.status_code == 201`
      (no `AttributeError` crash on missing `recommend()`);
      `tests/test_bedrock_api.py::test_throttle_client_error_falls_back_to_local`
      asserts `ticket["source"] == "local"` and `response.status_code == 201`
    - _Requirements: 3.5_

  - [ ]* 5.3 Create `tests/test_agent_desk_api.py`
    - Define `FakeAnalyzer` with both `analyze()` returning `CANNED_VALID` and
      a configurable `recommend()` (default returns `"Specific fix"`)
    - `test_bedrock_recommend_success_sets_recommended_solution`:
      fake `recommend` returns `"Specific fix"`;
      `assert ticket["recommended_solution"] == "Specific fix"` and
      `isinstance(ticket["source_snippets"], list)`
    - `test_bedrock_recommend_failure_falls_back`:
      fake `recommend` raises `BedrockAnalysisError`;
      `assert ticket["recommended_solution"] == LOCAL_FALLBACK_RECOMMENDATION`
      and `response.status_code == 201`
    - `test_model_id_unset_gives_fallback_recommendation`:
      no dependency override; `monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)`;
      `assert ticket["recommended_solution"] == LOCAL_FALLBACK_RECOMMENDATION`
      and `response.status_code == 201`
    - `test_empty_corpus_gives_fallback_and_empty_snippets`:
      no past tickets; `kb_path` fixture dir is empty (default);
      `assert ticket["source_snippets"] == []` and
      `ticket["recommended_solution"] == LOCAL_FALLBACK_RECOMMENDATION`
    - `test_recommend_called_with_message_and_snippets`:
      write a KB file containing the same word as the POST message; spy captures
      `(message, snippets)` passed to `recommend`; assert
      `spy_args[0] == message` and `len(spy_args[1]) > 0`
    - `test_past_tickets_not_included_in_own_corpus`:
      POST ticket A, then POST ticket B; assert that ticket B's
      `source_snippets` does not contain ticket B's own `message` text
    - `test_new_ticket_has_recommended_solution_and_snippets_persisted`:
      read `tickets_file` after POST; `assert stored[0]["recommended_solution"]`
      is a non-empty string and `isinstance(stored[0]["source_snippets"], list)`
    - `test_bedrock_failure_still_returns_201`:
      fake `recommend` raises `BedrockAnalysisError`;
      `assert response.status_code == 201`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3_

- [ ] 6. Update HTML page to render all eight ticket fields
  - [ ] 6.1 Update `INDEX_HTML` in `src/smart_copilot/page.py`
    - In the `for (const t of tickets)` loop, after the existing `line(box, "draft", ...)` call, add:
      - A `line(box, "recommendation", "Recommendation: " + t.recommended_solution)` call using `textContent` (never `innerHTML`)
      - A conditional block: if `t.source_snippets.length > 0`, iterate and
        call `line(box, "snippet", s)` per snippet; else append a single
        `<em>No source snippets available.</em>` element
    - **Validates:**
      `tests/test_page.py::test_index_shows_recommended_solution_field`
      asserts `"t.recommended_solution" in client.get("/").text`;
      `tests/test_page.py::test_index_shows_source_snippets_field`
      asserts `"t.source_snippets" in client.get("/").text`;
      `tests/test_page.py::test_index_shows_no_snippets_message`
      asserts `"No source snippets" in client.get("/").text`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 6.2 Extend `tests/test_page.py`
    - `test_index_shows_recommended_solution_field`:
      `assert "t.recommended_solution" in client.get("/").text`
    - `test_index_shows_source_snippets_field`:
      `assert "t.source_snippets" in client.get("/").text`
    - `test_index_shows_no_snippets_message`:
      `assert "No source snippets" in client.get("/").text`
    - _Requirements: 7.1, 7.3_

- [ ] 7. Add Hypothesis property tests (`tests/test_agent_desk_properties.py`)
  - [ ]* 7.1 Property 1 — KB loader `.txt` filter
    - Create `tests/test_agent_desk_properties.py`; add:
      `@given(st.lists(st.tuples(st.text(min_size=1, alphabet=st.characters(whitelist_categories=("Lu","Ll","Nd"))), st.sampled_from([".txt", ".md", ".json", ".csv"])), min_size=0, max_size=10))`
    - Write each file to `kb_path`; call `load_kb_documents(kb_path)`; assert:
      `{d["title"] for d in result} == {stem for stem, ext in pairs if ext == ".txt"}`
      and each `content` equals the written text stripped
    - **Property 1: KB loader returns exactly the .txt files with correct metadata**
    - _Requirements: 1.1, 1.5_

  - [ ]* 7.2 Property 2 — Retriever positive-score ordering
    - `@given(st.text(min_size=1, alphabet="abcde "), st.lists(st.text(alphabet="abcde "), min_size=0, max_size=10))`
    - Build a corpus from KB docs only; call `retrieve_snippets`; assert:
      all returned snippets have `keyword_overlap(message, s) > 0` and that
      scores are non-increasing (each `keyword_overlap(msg, result[i]) >= keyword_overlap(msg, result[i+1])`)
    - **Property 2: Retriever returns only positive-scored snippets in score order**
    - _Requirements: 2.1, 2.3, 2.4, 2.8_

  - [ ]* 7.3 Property 3 — Snippet length invariant
    - `@given(st.text(min_size=0, max_size=600))` as corpus item text; force
      one-word overlap with the query; assert
      `len(result[0]) == min(len(original), 300)`
    - **Property 3: Snippet length invariant**
    - _Requirements: 2.5, 2.6_

  - [ ]* 7.4 Property 4 — Keyword overlap case-invariance
    - `@given(st.text(alphabet=st.characters(whitelist_categories=("Lu","Ll"," "))), st.text(alphabet=st.characters(whitelist_categories=("Lu","Ll"," "))))`
    - Assert `keyword_overlap(q, t) == keyword_overlap(q.upper(), t.lower()) == keyword_overlap(q.lower(), t.upper())`
    - **Property 4: Keyword overlap is case-invariant**
    - _Requirements: 2.7_

  - [ ]* 7.5 Property 5 — `recommend_or_fallback` always returns a non-empty string
    - `@given(st.text(min_size=1).filter(str.strip), st.lists(st.text(min_size=0), min_size=0, max_size=5))`
    - Run once per analyzer variant: `None`, a fake that raises
      `BedrockAnalysisError`, a fake that returns a non-empty string, a fake
      that returns `""`
    - Assert `len(recommend_or_fallback(msg, snippets, analyzer)) > 0`
    - **Property 5: recommend_or_fallback always returns a non-empty string**
    - _Requirements: 3.1, 5.2_

  - [ ]* 7.6 Property 6 — Ticket persistence round-trip
    - `@given(st.text(min_size=1, max_size=5000).filter(str.strip))`
    - POST the generated message via `TestClient`; call `GET /tickets`; find
      the matching ticket by `id`; assert:
      `stored["recommended_solution"]` is a non-empty string;
      `isinstance(stored["source_snippets"], list)`;
      all seven pre-existing fields (`id`, `message`, `category`, `urgency`,
      `sentiment`, `draft_reply`, `source`) match the POST response body
    - **Property 6: Ticket persistence preserves all nine fields**
    - _Requirements: 3.2, 3.3, 3.4_

- [ ] 8. Final checkpoint — `ruff check` and `pytest` both exit 0
  - Run `uv run ruff check` and fix every reported issue before proceeding
  - Run `uv run pytest` and confirm exit code 0 (exit code 5 means no tests ran — that is a failure)
  - Report the actual terminal output (pass count, any failures)
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Sub-tasks marked with `*` are optional and can be skipped for faster MVP
- Every non-optional sub-task names the specific pytest function(s) and exact
  assertion(s) that define "done" for that task; the implementation is complete
  when those assertions pass
- Sub-task 1.2 is intentionally red until 5.1 makes it green — this is TDD
- Sub-task 5.2 must be completed alongside 5.1 to prevent `AttributeError`
  crashes in existing `test_bedrock_api.py` tests (the route now calls
  `analyzer.recommend()`, which fake analyzers must expose)
- Hypothesis property tests each run a minimum of 100 iterations (default
  `@given` settings)
- All API tests inject a fake analyzer via `app.dependency_overrides[get_analyzer]`; no real Bedrock calls are made
- The `kb_path` autouse fixture in `conftest.py` isolates every test from
  `data/kb/`; tests that need KB files write `.txt` files into the returned
  `tmp_path / "kb"` directory; tests that need an empty KB leave that directory
  empty (the default)
- `TicketStoreError` is imported from `smart_copilot.storage` for use in
  `kb.py`'s error handling

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "4.2"] },
    { "id": 3, "tasks": ["5.1"] },
    { "id": 4, "tasks": ["5.2", "5.3", "6.1"] },
    { "id": 5, "tasks": ["6.2"] },
    { "id": 6, "tasks": ["7.1"] },
    { "id": 7, "tasks": ["7.2"] },
    { "id": 8, "tasks": ["7.3"] },
    { "id": 9, "tasks": ["7.4"] },
    { "id": 10, "tasks": ["7.5"] },
    { "id": 11, "tasks": ["7.6"] }
  ]
}
```
