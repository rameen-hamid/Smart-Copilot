# Implementation Plan: Bedrock Analysis

## Overview

This plan converts the approved design into incremental, test-driven coding
tasks. Work proceeds from pure functions (enum constants, `is_valid_analysis`,
`RateLimiter`) to the `BedrockAnalyzer` wrapper (built only after the installed
`boto3` `bedrock-runtime` API is confirmed), then the `get_analyzer`
dependency, then the `main.py` model and create-flow change, then the `page.py`
display, then the Hypothesis property tests, and finally a full-suite run. Every
implementation task names the pytest test(s) it adds or updates and the single
requirement/acceptance criterion each test asserts with its exact expected value.

All work happens on branch `feat/bedrock-analysis` with exactly one commit per
task (per git-workflow steering). Tests inject a fake analyzer through
`app.dependency_overrides[get_analyzer]`, cleared after each test; the autouse
`tickets_file` fixture in `conftest.py` already points `TICKETS_FILE` at a temp
path, so no test writes the real `data/tickets.json` and no test makes a network
or live AWS call.

## Tasks

- [ ] 1. Add dependencies and prepare the branch
  - Run `git branch --show-current`; if not already on `feat/bedrock-analysis`, create it with `git switch -c feat/bedrock-analysis` before editing.
  - Add the runtime dependency with `uv add boto3`.
  - Add the dev dependency with `uv add --dev hypothesis`.
  - Confirm `uv run pytest` still passes on the unchanged suite as a baseline before any code change.
  - Commit: `Add boto3 and hypothesis dependencies`.
  - _Requirements: 9.1_

- [ ] 2. Create pure validation core in `bedrock.py` (enums + `is_valid_analysis`)
  - [ ] 2.1 Implement allowed-enum constants and `is_valid_analysis`
    - Create `src/smart_copilot/bedrock.py` with frozen sets `ALLOWED_CATEGORIES = {"billing", "technical", "account", "other"}`, `ALLOWED_URGENCIES = {"low", "medium", "high"}`, `ALLOWED_SENTIMENTS = {"negative", "neutral", "positive"}`.
    - Implement `is_valid_analysis(result: Any) -> bool` returning `True` only when `result` is a dict whose `category`/`urgency`/`sentiment` are in the allowed sets and `draft_reply` is a non-empty (non-blank) string; `False` for non-dict, missing key, wrong-typed value, out-of-enum value, or empty/blank `draft_reply`.
    - _Requirements: 4.6, 5.1, 5.2, 5.3_

  - [ ] 2.2 Write unit tests for `is_valid_analysis`
    - Add `tests/test_bedrock.py::test_is_valid_analysis_accepts_well_formed_result` asserting `is_valid_analysis({"category": "billing", "urgency": "high", "sentiment": "negative", "draft_reply": "hi"})` returns exactly `True` (Requirement 4.6).
    - Add `tests/test_bedrock.py::test_is_valid_analysis_rejects_out_of_enum_category` asserting a result with `category="unknown"` returns exactly `False` (Requirement 5.1).
    - Add `tests/test_bedrock.py::test_is_valid_analysis_rejects_out_of_enum_urgency` asserting `urgency="soon"` returns exactly `False` (Requirement 5.2).
    - Add `tests/test_bedrock.py::test_is_valid_analysis_rejects_out_of_enum_sentiment` asserting `sentiment="mad"` returns exactly `False` (Requirement 5.3).
    - Add `tests/test_bedrock.py::test_is_valid_analysis_rejects_missing_key_and_non_dict` asserting a dict missing `draft_reply` returns `False` and a non-dict input (e.g. `"x"`, `None`) returns `False` (Requirement 4.6).
    - _Requirements: 4.6, 5.1, 5.2, 5.3_

- [ ] 3. Implement the `RateLimiter`
  - [ ] 3.1 Implement `RateLimiter` with a monotonic clock
    - Add `RateLimiter` to `bedrock.py` with `__init__(self, min_interval_seconds: float = 1.0)` and `wait(self) -> None` that blocks until at least `min_interval_seconds` have elapsed since the previous call, using `time.monotonic` and a lock, recording the last-call time.
    - Allow an injectable clock/sleep (or module-level `time` reference) so tests can assert interval behavior without real sleeping.
    - _Requirements: 8.1, 8.3_

  - [ ]* 3.2 Write unit test for `RateLimiter` interval
    - Add `tests/test_bedrock.py::test_rate_limiter_enforces_min_interval` using a controlled/fake clock to assert two consecutive `wait()` calls cannot both start within the same 1.0s window (the second waits for the remaining interval) (Requirement 8.1).
    - _Requirements: 8.1_

- [ ] 4. Implement `BedrockAnalyzer.analyze` against the verified boto3 API
  - [ ] 4.1 Confirm the installed boto3 bedrock-runtime API, then implement `analyze`
    - BEFORE writing `analyze`, confirm from the INSTALLED SDK (e.g. `uv run python -c "import boto3; c = boto3.client('bedrock-runtime', region_name='us-east-1'); print([m for m in dir(c) if 'invoke' in m.lower()])"` and inspecting the operation's input/output shape) the exact invoke operation name, the request body structure, and the response field path to the model's generated text. Do not invent the API.
    - Implement `class BedrockAnalyzer` with `__init__(self, client, model_id, rate_limiter)` and `analyze(self, message: str) -> dict`: call `rate_limiter.wait()`, invoke the confirmed operation on `client` for `model_id` passing ONLY the message text, read the model text from the confirmed response path, and parse it as JSON into a dict with keys `category`, `urgency`, `sentiment`, `draft_reply`.
    - Wrap AWS/JSON operations in `try`/`except` catching SPECIFIC exceptions (`botocore.exceptions.ClientError`, `botocore.exceptions.BotoCoreError`, `json.JSONDecodeError`, `KeyError`, `TypeError`); never a bare `except`. Raise on failure; do not read past tickets, storage, or any S3 object; do not log message text, model id, or credentials.
    - _Requirements: 7.1, 7.2, 8.2, 9.1_

  - [ ] 4.2 Write unit tests for `analyze` using a fake boto3 client
    - Add `tests/test_bedrock.py::test_analyze_passes_only_message_and_returns_dict` with a fake client returning canned model text; assert `analyze("just this message")` returns a dict with the four keys and that the fake client received only the message text (no extra context) (Requirement 9.1, 7.1).
    - Add `tests/test_bedrock.py::test_analyze_calls_rate_limiter_once_per_call` asserting `analyze` invokes the (fake/spy) rate limiter's `wait` and the fake client exactly once per call (Requirement 8.2).
    - _Requirements: 7.1, 8.2, 9.1_

- [ ] 5. Implement the `get_analyzer` dependency
  - [ ] 5.1 Implement `get_analyzer`
    - Add `get_analyzer() -> BedrockAnalyzer | None` to `bedrock.py`: read `BEDROCK_MODEL_ID`; when unset or empty, return `None` (never raise, never 503). When set, read `AWS_REGION` defaulting to `us-east-1`, construct the `bedrock-runtime` client, and return a `BedrockAnalyzer` wrapping the client, a shared `RateLimiter`, and the model id.
    - _Requirements: 6.3, 6.4_

  - [ ]* 5.2 Write unit tests for `get_analyzer` env handling
    - Add `tests/test_bedrock.py::test_get_analyzer_returns_none_when_model_id_unset` using `monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)` asserting the return is exactly `None` (Requirement 6.3).
    - Add `tests/test_bedrock.py::test_get_analyzer_uses_default_region_when_unset` setting `BEDROCK_MODEL_ID` and unsetting `AWS_REGION`, asserting the constructed client/region resolves to `us-east-1` (patch the client constructor to capture `region_name`) (Requirement 6.4).
    - _Requirements: 6.3, 6.4_

- [ ] 6. Add `source` to the Ticket model and wire the create flow in `main.py`
  - [ ] 6.1 Add `source` field and `analyze_or_fallback`, inject the analyzer
    - Add `source: str` to the `Ticket` pydantic model in `main.py`.
    - Implement `analyze_or_fallback(message, analyzer)`: if `analyzer is None`, return local-classifier fields with `source="local"`; otherwise call `analyzer.analyze(message)` inside `try`; if it raises a caught specific exception OR `is_valid_analysis(result)` is `False`, return local fields with `source="local"`; on a valid result return its four fields with `source="bedrock"`.
    - Change `create_ticket` to `analyzer: BedrockAnalyzer | None = Depends(get_analyzer)`, build the ticket dict from `analyze_or_fallback`, and keep `storage.add_ticket` and the 422 `TicketCreate` validation unchanged. A Bedrock problem must never return 500.
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 4.1, 4.2, 4.3, 4.4, 5.4, 6.1, 6.2, 9.2_

  - [ ] 6.2 Update the existing full-ticket key-set test
    - Update `tests/test_tickets_api.py::test_create_returns_201_and_full_ticket` so the expected key set includes `"source"` (the Ticket model change otherwise breaks it); assert the local-path ticket has `source == "local"` when no analyzer override is supplied and `BEDROCK_MODEL_ID` is unset (Requirement 6.1).
    - _Requirements: 6.1_

  - [ ] 6.3 Write success-path tests with a fake analyzer (source=bedrock)
    - Add a reusable fake-analyzer helper and override `app.dependency_overrides[get_analyzer]`, clearing it after each test (a fixture in `tests/test_bedrock_api.py` or `conftest.py`).
    - Add `tests/test_bedrock_api.py::test_valid_analysis_sets_bedrock_source_and_fields` asserting a canned Valid_Analysis yields `source == "bedrock"`, the four fields equal the canned values, and status `201` (Requirements 1.1, 3.1, 3.2, 9.4).
    - Add `tests/test_bedrock_api.py::test_valid_analysis_does_not_use_local_classifier` asserting the stored fields differ from the local-classifier output for a message whose keywords would classify differently, proving local was not used (Requirement 1.2).
    - Add `tests/test_bedrock_api.py::test_analyzer_called_once_with_message_only` using a spy fake asserting `analyze` is called exactly once with only the message text per `POST /tickets` (Requirements 2.1, 8.2).
    - Add `tests/test_bedrock_api.py::test_created_ticket_fields_and_source_persisted` asserting `GET /tickets` returns the created ticket with its analysis fields and `source` (Requirements 2.2, 10.2).
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 8.2, 9.4, 10.2_

  - [ ] 6.4 Write fallback-path tests with a fake analyzer (source=local)
    - Add `tests/test_bedrock_api.py::test_throttle_client_error_falls_back_to_local` where the fake raises a throttling `botocore.exceptions.ClientError`; assert status `201`, `source == "local"`, and the four fields equal the local-classifier output for that message (Requirements 4.5, 9.5).
    - Add `tests/test_bedrock_api.py::test_malformed_output_falls_back_to_local` where the fake returns a dict missing a key or with a wrong-typed value; assert status `201` and `source == "local"` (Requirements 4.6, 9.6).
    - Add `tests/test_bedrock_api.py::test_out_of_enum_output_falls_back_to_local` where the fake returns `category="unknown"`; assert status `201` and `source == "local"` (Requirements 5.1).
    - Add `tests/test_bedrock_api.py::test_bedrock_failure_never_returns_500` asserting the fallback response status is not 500 (Requirement 4.4).
    - Add `tests/test_bedrock_api.py::test_model_id_unset_creates_local_ticket` (override `get_analyzer` to return `None`, or unset `BEDROCK_MODEL_ID`) asserting status `201`, `source == "local"`, and not 503 (Requirements 6.1, 6.2).
    - Add `tests/test_bedrock_api.py::test_no_analyze_endpoint` asserting `POST /tickets/{id}/analyze` returns 404/405 (no such endpoint) (Requirement 2.3).
    - Add `tests/test_bedrock_api.py::test_fake_analyzer_makes_no_network_call` asserting that with a fake supplied, `get_analyzer` is not invoked and no real client is constructed (Requirement 9.3).
    - _Requirements: 2.3, 4.4, 4.5, 4.6, 5.1, 6.1, 6.2, 9.3, 9.5, 9.6_

- [ ] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Show `source` on the HTML page
  - [ ] 8.1 Render `source` per ticket in `page.py`
    - Add one rendered line per ticket showing `source` alongside the existing `category`, `urgency`, `sentiment`, and `draft_reply` meta lines.
    - _Requirements: 10.1_

  - [ ]* 8.2 Write a test asserting the page markup shows the fields
    - Add `tests/test_page.py::test_index_shows_analysis_fields_and_source` asserting `GET /` returns HTML whose markup renders the four analysis fields and `source` for each listed ticket (Requirement 10.1).
    - _Requirements: 10.1_

- [ ] 9. Add Hypothesis property-based tests
  - [ ]* 9.1 Property test for `is_valid_analysis` (Property 1)
    - Add `tests/test_bedrock_properties.py::test_is_valid_analysis_accepts_only_well_formed` generating dicts and non-dicts with valid or deliberately violated fields (missing key, wrong type, out-of-enum, blank `draft_reply`); assert `is_valid_analysis` matches the contract (`True` iff all four fields valid). Min 100 iterations.
    - Tag: `# Feature: bedrock-analysis, Property 1: Validation accepts only well-formed, in-enum results`.
    - **Property 1: Validation accepts only well-formed, in-enum results**
    - **Validates: Requirements 4.6, 5.1, 5.2, 5.3**

  - [ ]* 9.2 Property test for route-level fallback (Property 2)
    - Add `tests/test_bedrock_properties.py::test_bedrock_failure_always_local_never_500` generating failing analyzer behaviors (raising `ClientError`/other exceptions, non-dict, missing key, wrong type, out-of-enum) via the fake; assert `POST /tickets` returns `201`, `source == "local"`, fields equal the local classifier, and status is never 500. Min 100 iterations.
    - Tag: `# Feature: bedrock-analysis, Property 2: A Bedrock failure never 500s and always falls back to local`.
    - **Property 2: A Bedrock failure never 500s and always falls back to local**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3**

  - [ ]* 9.3 Property test for the stored-enum invariant (Property 3)
    - Add `tests/test_bedrock_properties.py::test_stored_enum_fields_always_within_allowed_sets` generating messages and analyzer behaviors (valid, invalid, raising) with `BEDROCK_MODEL_ID` set and unset; assert the stored `category`/`urgency`/`sentiment` are within their allowed sets and `source` is exactly `"bedrock"` or `"local"`. Min 100 iterations.
    - Tag: `# Feature: bedrock-analysis, Property 3: Stored enum fields are always within the allowed sets`.
    - **Property 3: Stored enum fields are always within the allowed sets**
    - **Validates: Requirements 5.4**

- [ ] 10. Final checkpoint - Run the full suite and lint
  - Run `uv run ruff check` and fix anything it reports.
  - Run `uv run pytest` and confirm the whole suite passes (exit code 0, not exit code 5).
  - Report the actual pass/fail output. If a push or merge is needed, STOP and print the exact command for the user to run; do not push or merge.
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1, 9.1, 10.1_

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a
  faster MVP; core implementation sub-tasks are never marked optional.
- Each task references the specific requirement/acceptance-criterion IDs it
  implements, and every implementation task names the pytest test(s) it adds or
  updates with the exact expected value asserted (status code, enum value,
  `source` value, call count).
- The `boto3` `bedrock-runtime` invoke operation name, request body, and
  response field path MUST be confirmed from the installed SDK in task 4.1
  before implementing `analyze`; the API is not invented in this plan.
- Checkpoints ensure incremental validation. Property tests validate the three
  universal correctness properties; unit and example tests validate specific
  requirements and edge cases.
- All work stays on branch `feat/bedrock-analysis` with one commit per task; no
  pushing or merging is performed by the build agent.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "3.1"] },
    { "id": 1, "tasks": ["2.2", "3.2", "4.1"] },
    { "id": 2, "tasks": ["4.2", "5.1"] },
    { "id": 3, "tasks": ["5.2", "6.1"] },
    { "id": 4, "tasks": ["6.2", "6.3", "6.4", "8.1"] },
    { "id": 5, "tasks": ["8.2", "9.1", "9.2", "9.3"] }
  ]
}
```
