# BRD: Agent Desk

## Why

The existing ticket desk shows a generic draft reply that does not use past
solutions or knowledge-base documents. A support agent needs a specific,
grounded recommendation backed by similar solved tickets and curated KB articles
so they can respond faster and consistently. This feature adds a recommended
solution and the source snippets that grounded it to every new ticket, and shows
all eight ticket fields on one FastAPI HTML page.

## In scope

- Load knowledge-base documents from a configurable directory (`KB_PATH` env
  var, default `data/kb/`). Each `.txt` file is one document with the filename
  as its title and the file content as its body. A missing or empty directory is
  zero documents, not an error.
- Retrieve the top-3 most relevant snippets from (a) past ticket
  `message+draft_reply` pairs and (b) KB document content, using
  keyword-overlap scoring (case-insensitive word intersection count). Ties
  broken by insertion order. An empty corpus returns an empty list.
- Call Bedrock with the customer message and retrieved snippets to produce a
  `recommended_solution` string. Bedrock is called via the existing
  `BedrockAnalyzer` interface (a new `recommend(message, snippets)` method).
  The rate limiter in `bedrock.py` covers both `analyze` and `recommend` calls.
- Save `recommended_solution` (non-empty string) and `source_snippets` (list of
  strings, may be empty) on every new ticket alongside existing fields.
- Fall back gracefully: when `BEDROCK_MODEL_ID` is unset, or Bedrock raises an
  error or returns a malformed response, `recommended_solution` is a local
  fallback string; `source_snippets` still contains the retrieved snippets
  (or `[]` if none found). Response is still 201.
- When retrieval finds no snippets, `source_snippets` is `[]` and
  `recommended_solution` is a local fallback string even if Bedrock is
  available.
- Show all eight ticket fields on the existing FastAPI HTML page at `GET /`:
  category, urgency, sentiment, customer message, draft reply, source,
  recommended solution, and source snippets. No separate JavaScript app, no CDK.
- Tests use fixture `.txt` files in a temp KB directory (via `KB_PATH` env var)
  and a fake Bedrock client. No live AWS, no network.

## Out of scope

- S3 for KB storage (future spec). KB files are local `.txt` files for this
  version.
- Vector search or semantic retrieval. Keyword overlap only.
- CDK, SAM, Terraform, deploy steps, or slides.
- Any AWS service other than Bedrock.
- Login, email, or any new user authentication.
- Changing or removing existing ticket fields (`id`, `message`, `category`,
  `urgency`, `sentiment`, `draft_reply`, `source`).
- A separate JavaScript frontend or single-page app.
- Amazon Comprehend, Amazon Kendra, Amazon Lookout for Metrics.

## Requirements

1. **KB documents loaded from disk.** The system reads all `.txt` files in
   `KB_PATH` (default `data/kb/`) at ticket-creation time. A missing or empty
   directory is zero documents and is not an error.
2. **Snippet retrieval.** When a ticket is created, the system retrieves the
   top-3 snippets from: (a) every previously saved ticket's
   `message+draft_reply`, and (b) every KB document's content. Scoring is
   case-insensitive word-overlap count. Ties broken by order. Empty corpus
   returns `[]`. Snippets are strings up to 300 characters each (truncated if
   longer).
3. **Recommended solution saved.** Every response to `POST /tickets` includes
   `recommended_solution` (a non-empty string) and `source_snippets` (a list of
   zero or more strings). These are persisted in `data/tickets.json` alongside
   all existing fields.
4. **Bedrock generates the recommendation.** When `BEDROCK_MODEL_ID` is set and
   Bedrock returns valid output, `recommended_solution` comes from Bedrock,
   grounded in the message and snippets. The call must not include any data
   beyond the message and snippets.
5. **Fallback when Bedrock is unavailable or fails.** When `BEDROCK_MODEL_ID` is
   unset, or Bedrock raises any error or returns malformed output,
   `recommended_solution` is a non-empty local fallback string.
   `source_snippets` still contains retrieved snippets (or `[]`). Response is
   201.
6. **Empty snippets.** When retrieval finds no snippets, `source_snippets` is
   `[]` and `recommended_solution` is a local fallback string, even if
   `BEDROCK_MODEL_ID` is set.
7. **HTML page shows all eight fields.** `GET /` renders category, urgency,
   sentiment, customer message, draft reply, source, recommended solution, and
   source snippets for each ticket.

## Success criteria

- Each requirement has at least one passing pytest that asserts it alone with
  explicit expected values.
- Tests set `KB_PATH` to a temp directory containing synthetic `.txt` fixtures.
  Tests inject a fake Bedrock client. No live AWS, no network.
- `uv run pytest` and `uv run ruff check` both pass.
- No test writes the real `data/tickets.json` (`TICKETS_FILE` points to a temp
  path).
