# Requirements Document

## Introduction

This feature extends the ticket desk with a grounded recommended solution on
every new ticket. Today `POST /tickets` stores category, urgency, sentiment,
draft reply, and source but offers no recommendation backed by real evidence.
This feature adds two new fields to every ticket: `recommended_solution` (a
non-empty string) and `source_snippets` (a list of up to three relevant text
snippets). Snippets are retrieved at creation time by keyword-overlap scoring
across past tickets and local knowledge-base `.txt` files. When
`BEDROCK_MODEL_ID` is set and Bedrock returns valid output, `recommended_solution`
comes from Bedrock grounded on the message and snippets; otherwise a local
fallback string is used. The HTML page at `GET /` is updated to show all eight
ticket fields. The source of truth for this feature is
`docs/brd-agent-desk.md`, and these requirements stay consistent with it.

## Glossary

- **Ticket_Desk**: The FastAPI application that creates, lists, and deletes
  tickets (`smart_copilot.main:app`).
- **KB_Loader**: The component in `smart_copilot.kb` that reads `.txt` files
  from the `KB_PATH` directory and returns a list of KB_Documents.
- **KB_Document**: A dict with keys `title` (filename without extension) and
  `content` (file text, stripped). Produced by KB_Loader.
- **KB_PATH**: The environment variable that overrides the KB directory path.
  When unset, the default is `data/kb/`. A missing or empty directory yields
  zero KB_Documents and is not an error.
- **Retriever**: The component in `smart_copilot.retriever` that scores and
  returns the top-N Snippets from a corpus of past tickets and KB_Documents.
- **Corpus**: The combined set of text strings available to the Retriever: each
  past ticket contributes one string of `message + " " + draft_reply`, and each
  KB_Document contributes its `content`. An empty Corpus returns no Snippets.
- **Snippet**: A string of up to 300 characters drawn from a Corpus item. If
  the source string is longer than 300 characters it is truncated to 300.
- **Keyword_Overlap_Score**: The count of distinct lowercase words that appear
  in both the query message and a Corpus item, used to rank Corpus items.
  Case-insensitive; ties broken by insertion order in the Corpus.
- **Recommendation_Engine**: The logic in `smart_copilot.main` that calls the
  Retriever, then either calls Bedrock_Recommender or falls back to
  Local_Fallback_Recommendation.
- **Bedrock_Recommender**: The `recommend(message, snippets)` method added to
  `BedrockAnalyzer` in `smart_copilot.bedrock`. It calls the Bedrock Converse
  API with the message and snippets and returns a non-empty string.
- **Bedrock_Recommend_Failure**: Any exception raised by Bedrock_Recommender,
  including `BedrockAnalysisError`, or a response that is not a non-empty
  string.
- **Local_Fallback_Recommendation**: A statically defined non-empty string
  returned by the Recommendation_Engine when Bedrock_Recommender is unavailable
  or raises a Bedrock_Recommend_Failure.
- **recommended_solution**: A new Ticket field: a non-empty string holding the
  recommended solution, from Bedrock_Recommender or Local_Fallback_Recommendation.
- **source_snippets**: A new Ticket field: a list of zero or more Snippets that
  were passed to Bedrock_Recommender (or would have been, had it been called).
- **BEDROCK_MODEL_ID**: The environment variable naming the Bedrock model id,
  shared with the existing analysis feature.
- **Rate_Limiter**: The existing component in `bedrock.py` that keeps all
  Bedrock calls under 1 request per second; it covers both `analyze` and
  `recommend` calls.
- **Ticket**: A stored record with fields `id`, `message`, `category`,
  `urgency`, `sentiment`, `draft_reply`, `source`, `recommended_solution`, and
  `source_snippets`.

## Requirements

### Requirement 1: KB documents loaded from disk

**User Story:** As a support agent, I want knowledge-base articles loaded
automatically, so that my recommended solutions draw on curated guidance without
any manual wiring.

#### Acceptance Criteria

1. WHEN a ticket is created, THE KB_Loader SHALL read every `.txt` file in the directory specified by KB_PATH and return one KB_Document per file, with `title` set to the filename without its `.txt` extension and `content` set to the file text stripped of leading and trailing whitespace.
2. IF the KB_PATH directory does not exist when a ticket is created, THEN THE KB_Loader SHALL return an empty list of KB_Documents and SHALL NOT raise an error.
3. IF the KB_PATH directory is empty when a ticket is created, THEN THE KB_Loader SHALL return an empty list of KB_Documents and SHALL NOT raise an error.
4. THE KB_Loader SHALL read the KB directory path from the KB_PATH environment variable and SHALL use `data/kb/` when KB_PATH is unset.
5. THE KB_Loader SHALL ignore files that do not have the `.txt` extension.

### Requirement 2: Snippet retrieval by keyword overlap

**User Story:** As a support agent, I want the most relevant past solutions and
KB articles surfaced for my ticket, so that my recommendation is grounded in
real evidence.

#### Acceptance Criteria

1. WHEN a ticket is created, THE Retriever SHALL score every Corpus item by its Keyword_Overlap_Score with the new ticket message and return the top-3 Snippets in descending score order, ties broken by insertion order in the Corpus.
2. WHEN the Corpus is empty, THE Retriever SHALL return an empty list.
3. WHEN the Corpus has fewer than three items, THE Retriever SHALL return all items that have a Keyword_Overlap_Score greater than zero, up to the number of items available.
4. THE Retriever SHALL build the Corpus from past tickets first (each contributing `message + " " + draft_reply`) followed by KB_Documents (each contributing `content`).
5. WHEN a Corpus item string is longer than 300 characters, THE Retriever SHALL truncate the Snippet to exactly 300 characters.
6. WHEN a Corpus item string is 300 characters or fewer, THE Retriever SHALL return the full string as the Snippet without truncation.
7. THE Retriever SHALL perform all word matching case-insensitively.
8. WHEN all Corpus items have a Keyword_Overlap_Score of zero with the query message, THE Retriever SHALL return an empty list.

### Requirement 3: Recommended solution and source snippets saved on every ticket

**User Story:** As a support agent, I want every new ticket to carry a
recommended solution and its supporting snippets, so that I always have
something to act on.

#### Acceptance Criteria

1. WHEN `POST /tickets` creates a ticket, THE Ticket_Desk SHALL include `recommended_solution` as a non-empty string in the response body.
2. WHEN `POST /tickets` creates a ticket, THE Ticket_Desk SHALL include `source_snippets` as a list of zero or more strings in the response body.
3. THE Ticket_Desk SHALL persist `recommended_solution` and `source_snippets` in `data/tickets.json` alongside all existing Ticket fields.
4. THE Ticket_Desk SHALL NOT remove or modify the existing Ticket fields `id`, `message`, `category`, `urgency`, `sentiment`, `draft_reply`, or `source` when saving the new fields.
5. WHEN `POST /tickets` creates a ticket, THE Ticket_Desk SHALL respond with HTTP status 201.

### Requirement 4: Bedrock generates the recommended solution

**User Story:** As a support agent, I want Bedrock to write the recommended
solution grounded in my retrieved snippets, so that the recommendation is
specific and evidence-backed rather than generic.

#### Acceptance Criteria

1. WHEN `BEDROCK_MODEL_ID` is set AND Bedrock_Recommender returns a non-empty string, THE Recommendation_Engine SHALL set `recommended_solution` to that string.
2. WHEN the Recommendation_Engine calls Bedrock_Recommender, THE Recommendation_Engine SHALL pass only the ticket message and the retrieved Snippets.
3. THE Recommendation_Engine SHALL NOT include any data other than the ticket message and retrieved Snippets in the Bedrock_Recommender call.
4. THE Rate_Limiter SHALL govern calls to Bedrock_Recommender at the same rate as calls to `BedrockAnalyzer.analyze`, keeping total Bedrock calls under 1 request per second.

### Requirement 5: Fallback when Bedrock is unavailable or fails

**User Story:** As a support agent, I want a recommended solution on every
ticket even when Bedrock is unreachable, so that a model problem never blocks
my work.

#### Acceptance Criteria

1. IF `BEDROCK_MODEL_ID` is unset when a ticket is created, THEN THE Recommendation_Engine SHALL set `recommended_solution` to Local_Fallback_Recommendation and SHALL NOT call Bedrock_Recommender.
2. IF a Bedrock_Recommend_Failure occurs, THEN THE Recommendation_Engine SHALL set `recommended_solution` to Local_Fallback_Recommendation.
3. IF a Bedrock_Recommend_Failure occurs, THEN THE Recommendation_Engine SHALL set `source_snippets` to the Snippets retrieved before the failure (or `[]` if no Snippets were retrieved).
4. IF a Bedrock_Recommend_Failure occurs, THEN THE Ticket_Desk SHALL respond to `POST /tickets` with HTTP status 201.
5. IF a Bedrock_Recommend_Failure occurs, THEN THE Ticket_Desk SHALL NOT respond with HTTP status 500.
6. THE Local_Fallback_Recommendation SHALL be a non-empty string defined statically in the application.

### Requirement 6: Empty snippets trigger local fallback recommendation

**User Story:** As a support agent, I want a sensible recommendation even when
no relevant past tickets or KB articles exist, so that new ticket types are
handled gracefully from day one.

#### Acceptance Criteria

1. WHEN the Retriever returns an empty list of Snippets, THE Recommendation_Engine SHALL set `source_snippets` to `[]`.
2. WHEN the Retriever returns an empty list of Snippets, THE Recommendation_Engine SHALL set `recommended_solution` to Local_Fallback_Recommendation regardless of whether `BEDROCK_MODEL_ID` is set.
3. WHEN the Retriever returns an empty list of Snippets, THE Recommendation_Engine SHALL NOT call Bedrock_Recommender.

### Requirement 7: HTML page shows all eight ticket fields

**User Story:** As a support agent, I want to see the recommended solution and
supporting snippets on the ticket page, so that I can read the full context
without navigating elsewhere.

#### Acceptance Criteria

1. WHEN a client requests `GET /`, THE Ticket_Desk SHALL return an HTML page that shows `category`, `urgency`, `sentiment`, `message`, `draft_reply`, `source`, `recommended_solution`, and `source_snippets` for each listed ticket.
2. WHEN `source_snippets` for a ticket contains one or more strings, THE Ticket_Desk SHALL render each snippet as a distinct visible element on the HTML page.
3. WHEN `source_snippets` for a ticket is `[]`, THE Ticket_Desk SHALL render an indication that no source snippets are available on the HTML page.
4. THE Ticket_Desk SHALL NOT require a separate JavaScript frontend or single-page app to display the eight fields; all rendering SHALL be part of the existing `GET /` HTML page.
