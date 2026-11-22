# BRD: Ticket Desk

## Why

A support agent needs to see how urgent a customer message is and have a draft reply ready before deciding what to answer first. This first version proves that flow end to end with no cloud dependencies.

## Who it is for

A support agent who pastes in a customer message, checks the result, and works through a list of saved tickets.

## In scope

- Paste a customer message, through a JSON API or a simple HTML page at `GET /`.
- Show its category, urgency, sentiment, and a draft reply.
- List saved tickets.
- Delete a ticket.
- Keep tickets in `data/tickets.json` so they survive a page refresh.

## Out of scope

- Bedrock, DynamoDB, S3, Lambda, API Gateway, and CDK.
- Email, login, and slides.
- The first version uses a local classifier function, so tests never call AWS.

## Requirements

1. **Submit a message.** `POST /tickets` with a non-empty message returns 201 and a ticket with an id, the message, a category, an urgency, a sentiment, and a draft reply.
2. **Validate message length.** An empty or whitespace-only message is rejected with a 422 error. A message over 5,000 characters is rejected with a 422 error. A message of exactly 5,000 characters is accepted. A rejected message creates no ticket.
3. **List tickets.** `GET /tickets` returns all saved tickets, high urgency first, then medium, then low. Within one urgency, tickets keep insertion order. When none exist, it returns an empty list, not an error.
4. **Delete a ticket.** `DELETE /tickets/{id}` on an existing id removes that ticket and returns 204. An unknown id returns 404 and changes nothing.
5. **Persist across refresh.** After a ticket is created or deleted, `data/tickets.json` reflects it. A new app instance reading the same file lists the same tickets. A missing file is an empty list. Invalid JSON in the file returns 500 and the file is not overwritten.
6. **HTML page.** `GET /` returns an HTML page with a message box, a submit button, the ticket list, and a delete button on each ticket. Each ticket shows its category, urgency, sentiment, and draft reply. The page reads tickets from the API, so a refresh shows what is in `data/tickets.json`.

## Success criteria

- Each requirement above has at least one passing pytest test that checks it alone.
- `uv run pytest` and `uv run ruff check` both pass.
- No test makes a network or AWS call.
- No test writes the real `data/tickets.json`.

## Constraints

- Python 3.12 and FastAPI. Run commands are in `.kiro/steering/tech.md`.
- Synthetic tickets only. No real personal, financial, or health data.
- The classifier is a local, deterministic function. The same message always gives the same result.

## Decisions

- **Values.** Category: `billing`, `technical`, `account`, `other`. Urgency: `low`, `medium`, `high`. Sentiment: `negative`, `neutral`, `positive`.
- **Ids and message.** The id is a UUID4 string. The message is counted and stored unchanged.
- **Storage path.** The file is `data/tickets.json`, or the path in the `TICKETS_FILE` environment variable. Tests set `TICKETS_FILE`.
- **Draft reply.** A fixed template per category. It does not use the customer text and does not call Bedrock.
- **Matching.** The message is lowercased and split into words made of letters and apostrophes. A keyword matches only a whole word. There is no stemming, so `charged` and `charge` are separate keywords.
- **Category keywords.** Checked in this order, first match wins, otherwise `other`:
  1. `billing`: refund, charge, charged, invoice, payment, billing, subscription, price
  2. `technical`: error, crash, crashes, bug, broken, slow, freezes, fails
  3. `account`: password, login, account, username, locked, access
- **Urgency keywords.** `high` if any of: urgent, immediately, asap, emergency, critical, outage. Otherwise `medium` if any of: issue, problem, waiting, delay, delayed. Otherwise `low`.
- **Sentiment keywords.** `negative` if any of: angry, terrible, awful, worst, unacceptable, frustrated, disappointed, furious, ridiculous. Otherwise `positive` if any of: thanks, thank, great, love, appreciate, awesome, excellent, happy. Otherwise `neutral`. Negative wins when both match.
- **Delete response.** A successful delete returns 204 with no body.
