# BRD: Ticket Desk

## Why

A support agent needs to see how urgent a customer message is and have a draft reply ready before deciding what to answer first. This first version proves that flow end to end with no cloud dependencies.

## Who it is for

A support agent who pastes in a customer message, checks the result, and works through a list of saved tickets.

## In scope

- Paste a customer message.
- Show its classification, urgency, sentiment, and a draft reply.
- List saved tickets.
- Delete a ticket.
- Keep tickets in `data/tickets.json` so they survive a page refresh.

## Out of scope

- Bedrock, DynamoDB, S3, Lambda, API Gateway, and CDK.
- Email, login, and slides.
- The first version uses a local classifier function, so tests never call AWS.

## Requirements

1. **Submit a message.** Submitting a non-empty message creates a ticket with an id, the message, a category, an urgency, a sentiment, and a draft reply.
2. **Validate message length.** An empty or whitespace-only message is rejected with a 422 error. A message over 5,000 characters is rejected with a 422 error. A message of exactly 5,000 characters is accepted. A rejected message creates no ticket.
3. **List tickets.** Listing returns all saved tickets. When none exist, it returns an empty list, not an error.
4. **Delete a ticket.** Deleting an existing id removes that ticket. Deleting an unknown id returns 404 and changes nothing.
5. **Persist across refresh.** After a ticket is created or deleted, `data/tickets.json` reflects it. A new app instance reading the same file lists the same tickets.

## Success criteria

- Each requirement above has at least one passing pytest test that checks it alone.
- `uv run pytest` and `uv run ruff check` both pass.
- No test makes a network or AWS call.

## Constraints

- Python 3.12 and FastAPI. Run commands are in `.kiro/steering/tech.md`.
- Synthetic tickets only. No real personal, financial, or health data.
- The classifier is a local, deterministic function. The same message always gives the same result.
