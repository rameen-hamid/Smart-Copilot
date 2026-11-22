# BRD: Agent Sign-In

## Why

The ticket desk shows customer messages and draft replies to anyone who can reach the server. Only the support agent should see the queue or change tickets. This version adds a simple sign-in for one support agent, with no cloud services.

## Who it is for

One support agent who signs in with a username and password, then works the existing ticket desk.

## In scope

- A login page at `GET /login` with a username field, a password field, and a sign-in button.
- Checking the submitted username and password against one configured agent account.
- A correct sign-in opens the existing ticket desk at `GET /`: the ticket queue, with each ticket's category, urgency, sentiment, and draft reply.
- A wrong username or password keeps the visitor on the login page with an error message.
- A visitor who is not signed in and opens the desk (`GET /`) or calls the ticket API (`GET /tickets`, `POST /tickets`, `DELETE /tickets/{id}`) is sent to the login page.
- The desk page sends the browser to the login page if an API call is redirected there.

## Out of scope

- More than one agent, sign-up, roles, or user management.
- Sign-out, password reset, password change, and account lockout.
- Rate limiting of sign-in attempts.
- Amazon Cognito, DynamoDB, S3, Bedrock, Lambda, API Gateway, and CDK.
- Any change to the classifier (`src/smart_copilot/classifier.py`) or to the ticket API's request and response shapes.
- HTTPS setup. The app runs on `http://localhost` in the lab.

## Requirements

1. **Login page.** `GET /login` returns an HTML page with a username field, a password field, and a submit button. It is reachable without signing in.
2. **Correct sign-in.** Submitting the configured username and the correct password to `POST /login` signs the agent in and redirects to `/` with status 303. After that, `GET /` returns the ticket desk and `GET /tickets` returns the queue with category, urgency, sentiment, and draft reply on each ticket.
3. **Wrong sign-in.** A wrong password, an unknown username, or an empty field returns the login page with status 401 and the message "Invalid username or password." No session is created. The message does not say which field was wrong.
4. **Protected desk and API.** Without a valid session, `GET /`, `GET /tickets`, `POST /tickets`, and `DELETE /tickets/{id}` redirect to `/login` with status 303. They do not return ticket data or change `data/tickets.json`.
5. **Public routes.** `GET /health`, `GET /login`, and `POST /login` work without signing in.
6. **Credentials from configuration.** The agent's username and password hash come from environment variables. The password is never stored in plain text in code, config, tests, or logs. If the account is not configured, sign-in fails with status 503 and the message "Sign-in is not configured."
7. **Desk follows the redirect.** If the desk page's API call is redirected to `/login` (for example because the session expired), the page sends the browser to `/login`.

## Success criteria

- Each requirement above has at least one passing pytest test that checks it.
- The existing ticket desk tests still pass when run as a signed-in agent, and none are deleted, skipped, or weakened.
- `uv run pytest`, `uv run ruff check`, and `uv run check` pass.
- Tests use a fake agent account set through environment variables. No test calls Bedrock or any AWS service.
- `src/smart_copilot/classifier.py` is unchanged.

## Constraints

- Python 3.12 and FastAPI. Commands are in `.kiro/steering/tech.md`.
- Synthetic data only. The fake test user is not a real person.
- No secrets in code, tests, fixtures, or logs. Do not log usernames or passwords.

## Decisions to confirm

These are proposed defaults. Change them before implementation if they are wrong.

- **API redirect.** Logged-out API calls get a 303 redirect to `/login`, as asked, not a 401 JSON error. A script calling the API will receive the login page HTML.
- **Wrong sign-in status.** 401 with the login page re-rendered.
- **Session.** A signed, HTTP-only cookie (`SameSite=Lax`) that lasts 8 hours.
- **No sign-out.** Not requested, so it is out of scope. Clearing cookies or waiting 8 hours ends a session.
- **Product steering.** `.kiro/steering/product.md` lists user login as out of scope until an approved spec adds it. This BRD and its spec are that approval request.
