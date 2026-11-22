# BRD: Bedrock Analysis

## Why

The ticket desk currently classifies a customer message with a local keyword
function (`classifier.py`). Keyword matching is brittle: it misses categories,
urgency, and sentiment when the wording does not contain a known keyword, and
the draft reply is a fixed template. A support agent needs a better reading of
each ticket so the agent can decide what to answer first. This feature adds
Amazon Bedrock as the primary analyzer for category, urgency, sentiment, and the
draft reply, while keeping the local classifier as a reliable fallback so the
desk never fails a ticket creation because of a model problem.

## In scope

- Call Amazon Bedrock inside `POST /tickets` at creation time to produce
  category, urgency, sentiment, and the draft reply for the new ticket.
- Save those four fields on the new ticket, plus a new `source` field recording
  whether the values came from Bedrock or the local classifier.
- Fall back to the local keyword classifier on any Bedrock failure, throttle, or
  bad/malformed output, and still return 201.
- Read the model id from the `BEDROCK_MODEL_ID` environment variable and the
  region from `AWS_REGION` (default `us-east-1`).
- Rate-limit Bedrock calls to under 1 request per second.
- Inject the Bedrock client through a small wrapper exposing one
  `analyze(message) -> dict` method, so tests use a fake client with no network.
- Show the four fields on the HTML page immediately, the same as today.

## Out of scope

- Grounding on past tickets or knowledge-base documents. The Bedrock call sends
  only the ticket message text. No S3, no retrieval.
- A separate `POST /tickets/{id}/analyze` endpoint. Analysis happens only inside
  `POST /tickets`.
- CDK, SAM, Terraform, any infrastructure, deploy steps, or slides.
- Any AWS service other than Bedrock: no S3, no DynamoDB, no Lambda, no API
  Gateway for this feature.
- Amazon Comprehend, Amazon Kendra, and Amazon Lookout for Metrics.
- Changing the allowed values for category, urgency, or sentiment.
- Batch analysis or looping Bedrock over many tickets.

## Requirements

1. **Bedrock produces the four analysis fields.** On a successful Bedrock call,
   the new ticket's category, urgency, sentiment, and draft reply come from
   Bedrock, replacing the keyword classifier for those four fields.
2. **Analysis runs inside create.** Bedrock runs inside `POST /tickets` at
   creation time. The four fields are saved on the new ticket. There is no
   `POST /tickets/{id}/analyze` endpoint.
3. **Source field on success.** On a successful Bedrock call, the ticket has a
   `source` field equal to `bedrock` and `POST /tickets` returns 201.
4. **Fallback on failure.** On any Bedrock failure, throttle, or bad/malformed
   output, the ticket is built from the local classifier, the `source` field is
   `local`, and `POST /tickets` returns 201. Bedrock errors never return 500.
5. **Enum validation triggers fallback.** A Bedrock category, urgency, or
   sentiment value outside the allowed enums is a bad response that triggers the
   local-classifier fallback with `source` = `local`.
6. **Model id unset falls back.** When `BEDROCK_MODEL_ID` is unset, the ticket is
   created with the local classifier, `source` = `local`, and the response is
   201. It does not return 503.
7. **Message-only input.** The Bedrock call sends only the ticket message text.
   No past tickets, knowledge-base documents, or other context.
8. **Rate limit.** Bedrock calls stay under 1 request per second. One ticket per
   create, no batch loop.
9. **Injected client wrapper.** The Bedrock client is injected through a wrapper
   exposing one method `analyze(message) -> dict`. Tests inject a fake client
   with no live Bedrock and no network.
10. **HTML page shows fields.** `GET /` shows the category, urgency, sentiment,
    and draft reply for each ticket immediately, the same behavior as today.

## Success criteria

- Each requirement above has at least one passing pytest test that checks it
  alone, with explicit expected values (status code, enum value, `source`
  value, and the fallback trigger).
- Tests cover a canned Bedrock success, a throttle/`ClientError`, and malformed
  Bedrock output. `source` is `bedrock` on success and `local` on each fallback
  path (failure, throttle, malformed output, out-of-enum value, and
  `BEDROCK_MODEL_ID` unset).
- `uv run pytest` and `uv run ruff check` both pass.
- No test makes a network or AWS call. Tests inject the fake Bedrock client.
- No test writes the real `data/tickets.json`. Tests set `TICKETS_FILE` to a
  temp path.

## Decisions

Captured verbatim from the user's approved interview answers:

1. Bedrock produces category, urgency, sentiment, and the draft reply, replacing
   the keyword classifier for those four. The keyword classifier stays as the
   fallback.
2. Run Bedrock INSIDE POST /tickets at creation time and save those four fields
   on the new ticket. Do NOT add POST /tickets/{id}/analyze. The HTML page shows
   the fields immediately, same as today.
3. On any Bedrock failure, throttle, or bad/malformed output: fall back to the
   local classifier, set a new ticket field source="local", and still return
   201. Never return 500 for a Bedrock error. On Bedrock success,
   source="bedrock".
4. Grounding on past tickets and knowledge-base documents is OUT OF SCOPE. The
   call sends only the ticket message text. No S3, no retrieval.
5. Model ID comes from env var BEDROCK_MODEL_ID. Region from AWS_REGION, default
   us-east-1. No hard-coded model ID. If BEDROCK_MODEL_ID is unset, do NOT return
   503: create the ticket with the local classifier, set source="local", return
   201.
6. Allowed values unchanged: category billing|technical|account|other; urgency
   low|medium|high; sentiment negative|neutral|positive. A Bedrock value outside
   these enums is a bad response and triggers fallback.
7. Keep Bedrock under 1 request per second (rate limiter). One ticket per create.
   No batch loop.
8. The Bedrock client is injected through a small wrapper exposing one method
   analyze(message) -> dict. Tests inject a FAKE client (no live Bedrock, no
   network). Tests must cover: a canned success, a throttle/ClientError, and
   malformed output. source must be "bedrock" on success and "local" on each
   fallback path.
9. Scope limits: NO CDK, no infra, no S3, no DynamoDB, no other AWS service.
   boto3 is an approved new dependency the build agent may add. Feature name:
   bedrock-analysis.
