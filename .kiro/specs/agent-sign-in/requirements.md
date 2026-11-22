# Requirements Document

Source: `docs/brd-agent-sign-in.md`.

## Introduction

Add a username and password sign-in for one support agent. Signing in opens the existing ticket desk. Visitors who are not signed in are sent to the login page from the desk and from the ticket API. The classifier, the ticket API's request and response shapes, and the storage file do not change. No AWS service is used.

## Glossary

- **Agent**: the one configured support agent account.
- **Session**: a signed cookie that marks the browser as signed in as the agent.
- **Protected route**: any route except `GET /health`, `GET /login`, and `POST /login`.
- **Ticket desk**: the HTML page at `GET /` and the ticket API at `/tickets`.

## Requirements

### Requirement 1: Login page

**User Story:** As the agent, I want a login page, so that I can sign in before working tickets.

#### Acceptance Criteria

1. WHEN a visitor sends `GET /login`, THE system SHALL return status 200 and an HTML page containing exactly one username field, exactly one password field of type `password`, and exactly one submit button that posts to `/login`.
2. WHEN a visitor without a session sends `GET /login`, THE system SHALL return the login page with status 200 and without redirecting.
3. WHEN a visitor with a valid session sends `GET /login`, THE system SHALL return the login page with status 200 and without redirecting.
4. WHEN the system renders the login page after a failed sign-in, THE system SHALL show the message "Invalid username or password." and SHALL leave the username field and the password field empty.
5. WHEN a visitor sends `GET /login` while the agent account is not configured, THE system SHALL return the login page with status 200.

### Requirement 2: Correct sign-in

**User Story:** As the agent, I want my correct username and password to open the ticket desk, so that I can see the queue.

#### Acceptance Criteria

1. WHEN `POST /login` receives the configured username and the matching password, THE system SHALL create a session and return status 303 with `Location: /`.
2. WHEN the agent has a valid session, THE system SHALL return status 200 and the existing ticket desk page for `GET /`.
3. WHEN the agent has a valid session, THE system SHALL return status 200 and the ticket queue for `GET /tickets`, each ticket with `category`, `urgency`, `sentiment`, and `draft_reply`, ordered high urgency first, then medium, then low, with tickets of the same urgency in insertion order.
4. WHEN the agent has a valid session and `GET /tickets` is called while no tickets are saved, THE system SHALL return status 200 and an empty list.
5. WHEN the agent has a valid session, THE system SHALL handle `POST /tickets` and `DELETE /tickets/{id}` exactly as described in `docs/brd-ticket-desk.md`, including the 201, 204, 404, and 422 responses and the persistence of changes to the tickets file.
6. WHEN `POST /login` creates a session, THE system SHALL set the session cookie as HTTP-only, with `SameSite=Lax`, and with an expiry of 8 hours (28,800 seconds) from creation.
7. IF a session cookie is older than 8 hours, THEN THE system SHALL treat the request as having no valid session and SHALL redirect it to `/login` with status 303 without returning ticket data.

### Requirement 3: Wrong sign-in

**User Story:** As the agent, I want a wrong password to keep me on the login page, so that I can try again.

#### Acceptance Criteria

1. WHEN `POST /login` receives the configured username with a wrong password, THE system SHALL return status 401 and the login page containing the message "Invalid username or password."
2. WHEN `POST /login` receives a username that is not the configured username, THE system SHALL return the same status, the same message, and the same login page as for a wrong password, so that the response does not reveal which field was wrong.
3. WHEN `POST /login` receives a username or password that is empty, consists only of whitespace, or is missing from the request, THE system SHALL return the same status, the same message, and the same login page as for a wrong password.
4. WHEN sign-in fails, THE system SHALL NOT set a session cookie, and a following `GET /tickets` without a valid session SHALL redirect to `/login` with status 303 and return no ticket data.
5. WHEN sign-in fails, THE system SHALL omit the submitted username and the submitted password from the response body, the response headers, and the re-rendered username and password fields.
6. WHEN sign-in fails, THE system SHALL NOT write the submitted username or password to logs.
7. IF the agent account is not configured, THEN THE system SHALL return status 503 and the message "Sign-in is not configured." instead of the 401 response, and SHALL create no session.
8. WHEN a sign-in attempt fails and the agent then submits the configured username and the correct password, THE system SHALL sign the agent in and redirect to `/` with status 303.

### Requirement 4: Protected desk and API

**User Story:** As the agent, I want the desk and the ticket API closed to visitors who are not signed in, so that customer messages stay private.

#### Acceptance Criteria

1. WHEN a visitor without a valid session sends `GET /`, THE system SHALL return status 303 with `Location: /login` and a response body that contains no ticket data.
2. WHEN a visitor without a valid session sends `GET /tickets`, `POST /tickets`, or `DELETE /tickets/{id}`, THE system SHALL return status 303 with `Location: /login`, regardless of the request body, the ticket id, or whether the ticket exists.
3. WHEN a protected request is redirected, THE system SHALL return no ticket data, SHALL NOT read the tickets file, and SHALL leave the tickets file byte-for-byte unchanged.
4. IF the session cookie is missing, has been modified after signing, was signed with a different secret, or is older than 8 hours, THEN THE system SHALL treat the visitor as not signed in and apply criteria 1 to 3.
5. WHEN a visitor with a valid session sends `GET /`, `GET /tickets`, `POST /tickets`, or `DELETE /tickets/{id}`, THE system SHALL process the request normally and SHALL NOT redirect it to `/login`.
6. WHEN a route is added to the application, THE system SHALL require a valid session for it, unless the route is on the public list. The public list contains only `GET /health`, `GET /login`, and `POST /login`.
7. IF a request without a valid session is sent to a path or method that matches no route and is not on the public list, THEN THE system SHALL return status 303 with `Location: /login` and no ticket data.

### Requirement 5: Public routes

**User Story:** As an operator, I want health and login to work without a session, so that I can check the app and sign in.

#### Acceptance Criteria

1. WHEN a visitor without a session sends `GET /health`, THE system SHALL return status 200 and `{"status": "ok"}`.
2. WHEN a visitor without a session sends `GET /login`, THE system SHALL return the login page with status 200 and SHALL NOT redirect the visitor.
3. WHEN a visitor without a session sends `POST /login`, THE system SHALL process the submitted credentials as described in Requirements 2, 3, and 6 and SHALL NOT redirect the visitor to `/login` because no session exists.
4. WHEN a visitor with an expired, malformed, or tampered session cookie sends `GET /health`, `GET /login`, or `POST /login`, THE system SHALL respond as it does for a visitor without a session.
5. WHEN a visitor without a session sends `GET /health`, `GET /login`, or `POST /login`, THE system SHALL leave `data/tickets.json` unchanged and SHALL NOT include any ticket data in the response.

### Requirement 6: Credentials from configuration

**User Story:** As an operator, I want the agent's credentials outside the code, so that no secret is committed.

#### Acceptance Criteria

1. THE system SHALL read the agent username from the `AGENT_USERNAME` environment variable and a PBKDF2-SHA256 password hash from the `AGENT_PASSWORD_HASH` environment variable.
2. WHEN `POST /login` receives a password, THE system SHALL verify it against the PBKDF2-SHA256 hash in `AGENT_PASSWORD_HASH` using a constant-time comparison.
3. WHEN `POST /login` receives a username, THE system SHALL compare it with `AGENT_USERNAME` using a constant-time comparison.
4. IF `AGENT_USERNAME` or `AGENT_PASSWORD_HASH` is unset, is an empty string, or is not a well-formed PBKDF2-SHA256 hash, THEN THE system SHALL return status 503 and the message "Sign-in is not configured." for `POST /login`, create no session, and keep the application running.
5. THE system SHALL read the session signing key from the `SESSION_SECRET` environment variable.
6. WHERE `SESSION_SECRET` is unset or an empty string, THE system SHALL generate a random signing key at process start and use it until the process ends, so that every session issued before a restart is rejected after the restart.
7. THE system SHALL omit usernames, passwords, password hashes, and the session secret from all log output, including log output for failed sign-in attempts and configuration errors.
8. WHEN an operator runs the project's password-hash command, THE system SHALL read the password from a hidden prompt that does not echo the typed characters, SHALL accept no password as a command-line argument, and SHALL print a PBKDF2-SHA256 hash that `AGENT_PASSWORD_HASH` accepts.
9. IF the operator enters an empty password at the hidden prompt of the password-hash command, THEN THE system SHALL print an error indicating that the password is empty, print no hash, and exit with a non-zero exit code.

### Requirement 7: Desk follows the redirect

**User Story:** As the agent, I want the desk to take me to the login page when my session ends, so that I am not left on a broken page.

#### Acceptance Criteria

1. WHEN a fetch call to load tickets (`GET /tickets`) from the ticket desk page follows a redirect and the final response URL path is `/login`, THE ticket desk page SHALL set `window.location` to `/login`.
2. WHEN a fetch call to create a ticket (`POST /tickets`) from the ticket desk page follows a redirect and the final response URL path is `/login`, THE ticket desk page SHALL set `window.location` to `/login`.
3. WHEN a fetch call to delete a ticket (`DELETE /tickets/{id}`) from the ticket desk page follows a redirect and the final response URL path is `/login`, THE ticket desk page SHALL set `window.location` to `/login`.
4. IF a fetch call from the ticket desk page ends at `/login` after a redirect, THEN THE ticket desk page SHALL NOT display a "Could not load tickets", "Could not delete", or other ticket error message, and SHALL NOT render ticket rows from the login page response.
5. IF a fetch call from the ticket desk page does not end at `/login`, THEN THE ticket desk page SHALL keep its existing behavior for that call, including showing the status-based error message when the response is not successful.

### Requirement 8: Test and scope constraints

**User Story:** As a maintainer, I want the change to stay inside its scope, so that existing behavior and tests remain intact.

#### Acceptance Criteria

1. THE test suite SHALL configure the agent account through environment variables holding a fake username and the hash of a fake test-only password. The fake password SHALL appear only in test code, SHALL be clearly marked as a test value, and SHALL NOT be a real credential.
2. THE test suite SHALL make zero calls to Bedrock or any other AWS service, and SHALL run to completion with no AWS credentials present in the environment.
3. THE test suite SHALL contain at least one passing pytest test for each of Requirements 1 to 7, using FastAPI's `TestClient`.
4. THE system SHALL leave `src/smart_copilot/classifier.py` byte-for-byte identical to its content before this change.
5. THE system SHALL keep the request and response shapes of `GET /tickets`, `POST /tickets`, and `DELETE /tickets/{id}` identical to their shapes before this change.
6. THE existing ticket desk tests SHALL keep every assertion unchanged, SHALL NOT be deleted, skipped, or weakened, and SHALL run as the signed-in agent.
7. WHEN `uv run pytest`, `uv run ruff check`, and `uv run check` are each run, THE system SHALL complete each command with exit code 0.
8. IF the tests need a tickets file, THEN THE test suite SHALL point `TICKETS_FILE` at a temporary file so that `data/tickets.json` is not modified.
