# Requirements Document

## Introduction

This feature adds Amazon Bedrock analysis to the existing ticket desk. Today
`POST /tickets` builds a ticket with category, urgency, sentiment, and a draft
reply from a local keyword classifier (`classifier.py`). This feature makes
Bedrock the primary analyzer for those four fields, computed inside
`POST /tickets` at creation time. On any Bedrock failure, throttle, or
bad/malformed output, the system falls back to the local keyword classifier and
still returns 201. Every ticket records a `source` field of `bedrock` or
`local`. The Bedrock call sends only the ticket message text; grounding on past
tickets or knowledge-base documents is out of scope. The source of truth for
this feature is `docs/brd-bedrock-analysis.md`, and these requirements stay
consistent with it.

## Glossary

- **Ticket_Desk**: The FastAPI application that creates, lists, and deletes
  tickets (`smart_copilot.main:app`).
- **Bedrock_Analyzer**: The injected wrapper around the Amazon Bedrock runtime
  client, exposing one method `analyze(message) -> dict` that returns a dict with
  keys `category`, `urgency`, `sentiment`, and `draft_reply`.
- **Local_Classifier**: The existing deterministic keyword functions in
  `classifier.py` that compute `category`, `urgency`, `sentiment`, and
  `draft_reply`.
- **Rate_Limiter**: The component that keeps Bedrock_Analyzer calls under 1
  request per second.
- **Ticket**: A stored record with fields `id`, `message`, `category`,
  `urgency`, `sentiment`, `draft_reply`, and `source`.
- **Analysis_Fields**: The four fields `category`, `urgency`, `sentiment`, and
  `draft_reply`.
- **Source_Field**: The Ticket field `source`, whose value is `bedrock` or
  `local`.
- **Allowed_Category**: One of `billing`, `technical`, `account`, `other`.
- **Allowed_Urgency**: One of `low`, `medium`, `high`.
- **Allowed_Sentiment**: One of `negative`, `neutral`, `positive`.
- **Valid_Analysis**: A Bedrock_Analyzer result that is a dict containing
  `category` in Allowed_Category, `urgency` in Allowed_Urgency, `sentiment` in
  Allowed_Sentiment, and a string `draft_reply`.
- **Bedrock_Failure**: Any exception raised by Bedrock_Analyzer, including a
  throttle or other `ClientError`, or a result that is not a Valid_Analysis
  (missing keys, wrong type, or an out-of-enum value).
- **BEDROCK_MODEL_ID**: The environment variable naming the Bedrock model id.
- **AWS_REGION**: The environment variable naming the AWS region, defaulting to
  `us-east-1`.

## Requirements

### Requirement 1: Bedrock produces the analysis fields on success

**User Story:** As a support agent, I want Bedrock to classify the ticket, so
that category, urgency, sentiment, and the draft reply reflect a model reading
rather than only keyword matching.

#### Acceptance Criteria

1. WHEN a ticket is created with a non-empty message AND Bedrock_Analyzer returns a Valid_Analysis, THE Ticket_Desk SHALL set the new Ticket Analysis_Fields to the `category`, `urgency`, `sentiment`, and `draft_reply` values from the Bedrock_Analyzer result.
2. WHEN a ticket is created with a non-empty message AND Bedrock_Analyzer returns a Valid_Analysis, THE Ticket_Desk SHALL NOT use the Local_Classifier for the new Ticket Analysis_Fields.

### Requirement 2: Analysis runs inside ticket creation

**User Story:** As a support agent, I want the analysis to happen when I submit
a ticket, so that the result is ready immediately without a second request.

#### Acceptance Criteria

1. WHEN a client sends `POST /tickets` with a non-empty message, THE Ticket_Desk SHALL call Bedrock_Analyzer once with only the ticket message text before saving the Ticket.
2. THE Ticket_Desk SHALL save the Analysis_Fields and the Source_Field on the new Ticket through the existing storage before returning the response.
3. THE Ticket_Desk SHALL expose no `POST /tickets/{id}/analyze` endpoint.

### Requirement 3: Source is bedrock on success

**User Story:** As a support agent, I want to know when a reading came from
Bedrock, so that I can judge how much to trust it.

#### Acceptance Criteria

1. WHEN Bedrock_Analyzer returns a Valid_Analysis for a created ticket, THE Ticket_Desk SHALL set the Source_Field of the new Ticket to `bedrock`.
2. WHEN Bedrock_Analyzer returns a Valid_Analysis for a created ticket, THE Ticket_Desk SHALL respond to `POST /tickets` with HTTP status 201.

### Requirement 4: Fallback to the local classifier on failure

**User Story:** As a support agent, I want a ticket to still be created when
Bedrock fails, so that a model problem never blocks my work.

#### Acceptance Criteria

1. IF a Bedrock_Failure occurs while creating a ticket, THEN THE Ticket_Desk SHALL set the new Ticket Analysis_Fields from the Local_Classifier for the same message.
2. IF a Bedrock_Failure occurs while creating a ticket, THEN THE Ticket_Desk SHALL set the Source_Field of the new Ticket to `local`.
3. IF a Bedrock_Failure occurs while creating a ticket, THEN THE Ticket_Desk SHALL respond to `POST /tickets` with HTTP status 201.
4. IF a Bedrock_Failure occurs while creating a ticket, THEN THE Ticket_Desk SHALL respond with an HTTP status other than 500.
5. WHEN Bedrock_Analyzer raises a throttling `ClientError` while creating a ticket, THE Ticket_Desk SHALL create the Ticket from the Local_Classifier with the Source_Field set to `local` and respond with HTTP status 201.
6. WHEN Bedrock_Analyzer returns output that is not a Valid_Analysis because a required key is missing or a value has the wrong type, THE Ticket_Desk SHALL create the Ticket from the Local_Classifier with the Source_Field set to `local` and respond with HTTP status 201.

### Requirement 5: Out-of-enum value triggers fallback

**User Story:** As a support agent, I want an invalid category, urgency, or
sentiment from Bedrock to be rejected, so that stored tickets only carry known
values.

#### Acceptance Criteria

1. IF Bedrock_Analyzer returns a `category` that is not an Allowed_Category, THEN THE Ticket_Desk SHALL treat the result as a Bedrock_Failure and create the Ticket from the Local_Classifier with the Source_Field set to `local`.
2. IF Bedrock_Analyzer returns an `urgency` that is not an Allowed_Urgency, THEN THE Ticket_Desk SHALL treat the result as a Bedrock_Failure and create the Ticket from the Local_Classifier with the Source_Field set to `local`.
3. IF Bedrock_Analyzer returns a `sentiment` that is not an Allowed_Sentiment, THEN THE Ticket_Desk SHALL treat the result as a Bedrock_Failure and create the Ticket from the Local_Classifier with the Source_Field set to `local`.
4. WHEN the Ticket_Desk creates a Ticket, THE Ticket_Desk SHALL store a `category` in Allowed_Category, an `urgency` in Allowed_Urgency, and a `sentiment` in Allowed_Sentiment regardless of the Source_Field value.

### Requirement 6: Missing model id falls back

**User Story:** As an operator, I want a missing model id to degrade to the
local classifier, so that the desk keeps working before Bedrock is configured.

#### Acceptance Criteria

1. IF the BEDROCK_MODEL_ID environment variable is unset when a ticket is created, THEN THE Ticket_Desk SHALL create the Ticket from the Local_Classifier with the Source_Field set to `local` and respond with HTTP status 201.
2. IF the BEDROCK_MODEL_ID environment variable is unset when a ticket is created, THEN THE Ticket_Desk SHALL NOT respond with HTTP status 503.
3. THE Ticket_Desk SHALL read the Bedrock model id from the BEDROCK_MODEL_ID environment variable rather than a hard-coded value.
4. THE Ticket_Desk SHALL read the AWS region from the AWS_REGION environment variable and SHALL use `us-east-1` when AWS_REGION is unset.

### Requirement 7: Message-only input

**User Story:** As a support agent, I want the analysis to use only the ticket
message, so that no other data is sent to Bedrock.

#### Acceptance Criteria

1. WHEN the Ticket_Desk calls Bedrock_Analyzer, THE Ticket_Desk SHALL pass only the ticket message text.
2. THE Ticket_Desk SHALL NOT read past tickets, knowledge-base documents, or any S3 object when calling Bedrock_Analyzer.

### Requirement 8: Rate limit

**User Story:** As an operator, I want Bedrock calls rate-limited, so that the
workshop account stays under its limit.

#### Acceptance Criteria

1. THE Rate_Limiter SHALL keep Bedrock_Analyzer calls to fewer than 2 requests in any 1-second window across ticket creation.
2. WHEN a single `POST /tickets` request is handled, THE Ticket_Desk SHALL call Bedrock_Analyzer at most once.
3. THE Ticket_Desk SHALL NOT loop Bedrock_Analyzer over multiple tickets in a single request.

### Requirement 9: Injected client wrapper

**User Story:** As a developer, I want the Bedrock client injected through a
wrapper, so that tests run without network access.

#### Acceptance Criteria

1. THE Bedrock_Analyzer SHALL expose a single method `analyze(message)` that accepts the ticket message text and returns a dict with keys `category`, `urgency`, `sentiment`, and `draft_reply`.
2. THE Ticket_Desk SHALL obtain Bedrock_Analyzer through dependency injection so that a test can supply a fake Bedrock_Analyzer.
3. WHEN a test supplies a fake Bedrock_Analyzer, THE Ticket_Desk SHALL make no network call and no live Bedrock call during ticket creation.
4. WHERE a test supplies a fake Bedrock_Analyzer returning a canned Valid_Analysis, THE Ticket_Desk SHALL set the Source_Field to `bedrock`.
5. WHERE a test supplies a fake Bedrock_Analyzer that raises a throttling `ClientError`, THE Ticket_Desk SHALL set the Source_Field to `local`.
6. WHERE a test supplies a fake Bedrock_Analyzer returning malformed output, THE Ticket_Desk SHALL set the Source_Field to `local`.

### Requirement 10: HTML page shows the fields

**User Story:** As a support agent, I want the page to show the analysis fields
for each ticket, so that I can read them without extra steps.

#### Acceptance Criteria

1. WHEN a client requests `GET /`, THE Ticket_Desk SHALL return an HTML page that shows the `category`, `urgency`, `sentiment`, and `draft_reply` for each listed ticket.
2. WHEN a ticket has been created, THE Ticket_Desk SHALL make the created ticket's Analysis_Fields available through `GET /tickets` so the page shows them after a refresh.
