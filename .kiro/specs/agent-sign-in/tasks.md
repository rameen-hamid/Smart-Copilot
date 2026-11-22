# Implementation Plan: Agent Sign-In

## Overview

Add a username and password sign-in for one agent: `auth.py` (credentials, hashing, session check), a login page in `page.py`, a deny-by-default middleware plus `GET/POST /login` in `main.py`, a signed-in `client` fixture, and a redirect helper in the desk script. Each task names the pytest file and test functions it adds. No AWS service is used and `classifier.py` is not touched.

Rules for every task:
- Tests use FastAPI `TestClient`, never call Bedrock or AWS, and use only synthetic data.
- Fake agent: `AGENT_USERNAME=test-agent`, `SESSION_SECRET=test-session-secret`, `FAKE_PASSWORD = "fake-password-for-tests"` (test-only value, marked as such), hash built with `iterations=1000`.
- Each task ends by running `uv run pytest` and `uv run ruff check` and reporting the real output. Fix failures; never skip or weaken a test.
- Work on a branch matching `^(feat|fix|chore|docs|refactor)/[a-z0-9]+(-[a-z0-9]+)*$` (for example `feat/agent-sign-in`). Do not commit unless the user asks.

Ordering note: once the middleware lands (task 4), the existing ticket tests fail until `conftest.py` signs the `client` fixture in (task 5). The tests in task 4 therefore use their own fixtures local to `tests/test_login.py`, and the full-suite run is green at the end of task 5. Run `uv run pytest tests/test_auth.py tests/test_login.py` at the end of task 4 and the whole suite at the end of task 5.

## Tasks

- [x] 1. Add dependencies
  - [x] 1.1 Install packages with `uv`
    - Run `uv add itsdangerous`, `uv add python-multipart`, and `uv add --dev hypothesis`. Do not edit `uv.lock` by hand.
    - Check the installed `starlette.middleware.sessions` and `itsdangerous` source in `.venv/lib/python3.12/site-packages/` for the `SessionMiddleware` arguments and the `TimestampSigner` time call before using them.
    - Test: add `tests/test_dependencies.py` with two tests. `test_session_and_form_dependencies_import` asserts that `import itsdangerous`, `import multipart` (the module installed by python-multipart; confirm the import name in `.venv/lib/python3.12/site-packages/` when implementing), and `from starlette.middleware.sessions import SessionMiddleware` succeed. `test_hypothesis_available` asserts that `import hypothesis` succeeds.
    - Finish with `uv run pytest` and `uv run ruff check`.
    - _Requirements: 6.1, 6.5, 8.3, 8.7_

- [x] 2. Implement `auth.py`
  - [x] 2.1 Create `src/smart_copilot/auth.py`
    - Add `SESSION_KEY`, `SESSION_MAX_AGE = 28800`, `PUBLIC_PATHS`, `AuthNotConfigured`, `hash_password`, `verify_password`, `agent_credentials`, `check_login`, `session_secret`, `is_signed_in`, and the `python -m smart_copilot.auth` hash command, as in the design. Type hints on every public function. No logging.
    - `session_secret()` returns `SESSION_SECRET` or a random per-process value; the random value is generated once and cached.
    - The hash command uses `getpass.getpass` twice, prints only the hash, takes no password argument, and on an empty or mismatched password writes an error to stderr, prints no hash, and exits non-zero.
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9_

  - [x] 2.2 Write unit tests in `tests/test_auth.py`
    - `test_hash_password_format`: `hash_password("x", iterations=1000)` starts with `pbkdf2_sha256$1000$` and has four `$`-separated parts (6.1).
    - `test_verify_password_correct_and_wrong`: `verify_password(FAKE_PASSWORD, h)` is `True`; `verify_password("other", h)` is `False` (6.2).
    - `test_verify_password_malformed_raises`: parametrized over `""`, `"abc"`, `"md5$1$aa$bb"`, `"pbkdf2_sha256$0$aa$bb"`, `"pbkdf2_sha256$x$aa$bb"`, `"pbkdf2_sha256$1000$zz$bb"`; each raises `AuthNotConfigured` (6.4).
    - `test_agent_credentials_not_configured`: parametrized over unset and empty `AGENT_USERNAME` and `AGENT_PASSWORD_HASH` (via `monkeypatch`); each raises `AuthNotConfigured` (6.4).
    - `test_check_login`: true for `("test-agent", FAKE_PASSWORD)`; false for wrong password, wrong username, empty strings, whitespace-only strings, and a non-ASCII username (3.1, 3.2, 3.3, 6.3).
    - `test_session_secret_env_and_random`: with `SESSION_SECRET=test-session-secret` it returns that value; with it unset and with it empty it returns a non-empty value that stays the same across two calls in one process (6.5, 6.6).
    - `test_session_secret_differs_between_processes`: run `uv run python -c` style subprocess twice with `SESSION_SECRET` removed; the two printed values differ (6.6).
    - `test_is_signed_in`: `{"agent": "test-agent"}` is true; `{}`, `{"agent": "someone-else"}` are false; with `AGENT_USERNAME` unset it is false (4.4, 4.5).
    - `test_hash_command_matching_passwords`: patch `getpass.getpass` to return the same password twice; running the module's `main` prints exactly one line that `verify_password` accepts, exit code 0 (6.8).
    - `test_hash_command_empty_password`: patch `getpass` to return `""`; stdout is empty, stderr mentions the empty password, exit code non-zero (6.9).
    - `test_hash_command_mismatch`: patch `getpass` to return two different values; stdout empty, exit code non-zero (6.8).
    - `test_hash_command_takes_no_password_argument`: `main` run with an extra command-line argument does not use it as the password (6.8).
    - `test_no_logging`: with `caplog`, `check_login` for a wrong and a correct pair leaves no username, password, or hash in the log records (3.6, 6.7).
    - Finish with `uv run pytest tests/test_auth.py`, `uv run pytest`, and `uv run ruff check`.
    - _Requirements: 3.1, 3.2, 3.3, 3.6, 4.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 8.1, 8.2_

  - [x]* 2.3 Write property test for password verification in `tests/test_auth.py`
    - **Property 1: Password verification matches equality**
    - `test_property_verify_password_matches_equality`: Hypothesis `@given(st.text(), st.text())`, `@settings(max_examples=100)`, hashes with `iterations=1000`; asserts `verify_password(q, hash_password(p, iterations=1000)) == (p == q)` and the hash matches `pbkdf2_sha256$<n>$<hex>$<hex>`. Add the comment `# Feature: agent-sign-in, Property 1: Password verification matches equality`.
    - **Validates: Requirements 6.1, 6.2, 6.8**

- [x] 3. Login page in `page.py`
  - [x] 3.1 Add `LOGIN_HTML` and `login_page(error: str = "") -> str` to `src/smart_copilot/page.py`
    - Form `method="post" action="/login"`, one `name="username"` input (`autocomplete="username"`), one `type="password" name="password"` input (`autocomplete="current-password"`), one submit button, an error slot filled with `html.escape(error)`. No `value` attribute on either input. Do not change `INDEX_HTML` in this task.
    - _Requirements: 1.1, 1.4, 3.5_

  - [x] 3.2 Write unit tests in `tests/test_page.py` (append; keep existing tests unchanged)
    - `test_login_page_has_one_username_one_password_one_submit`: `login_page()` contains exactly one `name="username"`, exactly one `type="password"`, exactly one submit button, and `action="/login"` with `method="post"` (1.1).
    - `test_login_page_error_message_and_empty_fields`: `login_page("Invalid username or password.")` contains that exact text and no `value=` attribute on the inputs (1.4, 3.5).
    - `test_login_page_escapes_error`: `login_page("<script>x</script>")` does not contain the raw `<script>x</script>` (3.5).
    - `test_login_page_no_error_by_default`: `login_page()` does not contain "Invalid username or password." (1.1).
    - Finish with `uv run pytest tests/test_page.py`, `uv run pytest`, and `uv run ruff check`.
    - _Requirements: 1.1, 1.4, 3.5, 8.3_

- [x] 4. Middleware and login routes in `main.py`
  - [x] 4.1 Update `src/smart_copilot/main.py`
    - Add the `require_agent` HTTP middleware (deny-by-default, 303 to `/login` unless the path is in `PUBLIC_PATHS` or `is_signed_in(request.session)`), then `app.add_middleware(SessionMiddleware, secret_key=session_secret(), max_age=SESSION_MAX_AGE, same_site="lax", https_only=False)` so `SessionMiddleware` is outermost.
    - Add `GET /login` (200, `login_page()`) and `POST /login` with `Form("")` fields: `AuthNotConfigured` gives 503 "Sign-in is not configured."; a match runs `session.clear()`, sets `session["agent"]`, returns 303 to `/`; otherwise 401 "Invalid username or password.". No cookie on failure. No logging of credentials.
    - Do not change ticket routes, `GET /health`, `store_error_handler`, or `classifier.py`.
    - _Requirements: 1.2, 1.3, 1.5, 2.1, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.7, 3.8, 4.1, 4.2, 4.3, 4.6, 4.7, 5.1, 5.2, 5.3, 6.4_

  - [x] 4.2 Write route tests in `tests/test_login.py`
    - Local fixtures in this file: `anon_client` (`TestClient(app, follow_redirects=False)`), and the env vars `AGENT_USERNAME`, `AGENT_PASSWORD_HASH`, `SESSION_SECRET` set with `monkeypatch`. `FAKE_PASSWORD` is declared with a "test-only value, not a real credential" comment.
    - `test_get_login_without_session`: status 200, one password field, no redirect (1.1, 1.2, 5.2).
    - `test_get_login_with_session`: after a correct sign-in, `GET /login` is 200 with the login page (1.3).
    - `test_get_login_when_not_configured`: with the env vars unset, `GET /login` is 200 (1.5).
    - `test_correct_login_redirects_and_sets_cookie`: `POST /login` with `test-agent` and `FAKE_PASSWORD` returns 303, `Location: /`, and a `Set-Cookie` containing `httponly`, `samesite=lax`, and `Max-Age=28800` (case-insensitive) (2.1, 2.6).
    - `test_signed_in_desk_and_api_work`: after sign-in, `GET /` is 200, `GET /tickets` is 200 and `[]` on an empty file, a `POST /tickets` with a valid body is 201, `DELETE /tickets/{id}` is 204, and `DELETE` of a missing id is 404, `POST` with an invalid body is 422 (2.2, 2.4, 2.5, 4.5).
    - `test_signed_in_queue_order_and_shape`: add a low, a high, a second high, and a medium ticket; `GET /tickets` returns high, high (insertion order), medium, low, each with `category`, `urgency`, `sentiment`, `draft_reply` (2.3, 8.5).
    - `test_wrong_password_gives_401_message`: status 401, body contains "Invalid username or password.", no `Set-Cookie` header (3.1, 3.4).
    - `test_wrong_username_same_response_as_wrong_password`: status and body equal those of the wrong-password response (3.2).
    - `test_empty_whitespace_and_missing_fields_same_response`: parametrized over empty, whitespace-only, and omitted username or password; each equals the wrong-password response (3.3).
    - `test_failed_login_leaves_no_session`: after a failed sign-in, `GET /tickets` is 303 with `Location: /login` and the body has no ticket data (3.4).
    - `test_failed_login_does_not_echo_input`: submit a marker username and password; neither string appears in the body or headers (3.5).
    - `test_failed_login_does_not_log_input`: with `caplog`, failed and successful sign-ins leave no username or password in the records (3.6, 6.7).
    - `test_login_not_configured_returns_503`: parametrized over unset, empty, and malformed `AGENT_PASSWORD_HASH`, and unset `AGENT_USERNAME`; status 503, body contains "Sign-in is not configured.", no cookie, and the app still answers `GET /health` (3.7, 6.4).
    - `test_retry_after_failure_signs_in`: a wrong attempt then a correct one gives 303 to `/` (3.8).
    - `test_protected_routes_redirect_without_session`: `GET /`, `GET /tickets`, `POST /tickets` (valid and invalid body), `DELETE /tickets/does-not-exist` all return 303 with `Location: /login` and no ticket data (4.1, 4.2).
    - `test_redirect_leaves_tickets_file_unchanged`: seed the temp `TICKETS_FILE` with a synthetic ticket; after the redirected calls, its bytes are unchanged (4.3).
    - `test_redirect_does_not_read_tickets_file`: point `TICKETS_FILE` at a path that holds invalid JSON; `GET /tickets` without a session is still 303, not 500 (4.3).
    - `test_unknown_path_and_method_redirect`: `GET /nope` and `PUT /tickets` without a session return 303 to `/login` (4.7).
    - `test_every_non_public_route_is_protected`: iterate `app.routes`; every route not in `{/health, /login}` returns 303 without a session (4.6).
    - `test_health_is_public`: `GET /health` is 200 `{"status": "ok"}` and the tickets file is unchanged (5.1, 5.5).
    - `test_public_routes_with_bad_cookie`: with a garbage cookie, `GET /health` is 200, `GET /login` is 200, and `POST /login` with correct credentials is 303 to `/` (5.3, 5.4).
    - `test_tampered_cookie_rejected`: change one character of a valid session cookie; `GET /tickets` is 303 (4.4).
    - `test_cookie_signed_with_other_secret_rejected`: sign in against an app built with a different secret (or sign a cookie with `itsdangerous` using another key); `GET /tickets` is 303 (4.4, 6.6).
    - `test_expired_cookie_rejected`: build a cookie whose timestamp is older than 28,800 seconds (use the `TimestampSigner` time call found in task 1.1, or patch time); `GET /tickets` is 303 and returns no ticket data; a cookie at 28,799 seconds is accepted (2.7, 4.4).
    - `test_signed_in_request_not_redirected_proves_middleware_order`: a signed-in `GET /tickets` returns 200, which fails if `SessionMiddleware` is not outermost (4.5).
    - `test_no_aws_credentials_needed`: with `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_PROFILE` removed from the environment, a sign-in and `GET /tickets` still work (8.2).
    - Finish with `uv run pytest tests/test_auth.py tests/test_login.py` and `uv run ruff check`. The full suite is expected to be green only after task 5.
    - _Requirements: 1.2, 1.3, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.2, 5.3, 5.4, 5.5, 6.4, 6.6, 6.7, 8.2, 8.3, 8.5_

  - [x]* 4.3 Write property tests for login and session checks in `tests/test_login.py`
    - **Property 2: Any wrong credentials give one uniform failure**
    - `test_property_wrong_credentials_uniform_failure`: `@given(st.text(), st.text())` filtered to exclude `("test-agent", FAKE_PASSWORD)`; creates its own `TestClient` inside the test; asserts status 401, body equal to the known wrong-password body, no `Set-Cookie`, the submitted strings not in the body or headers (to avoid false matches, the echo check uses only inputs of 4 or more characters that do not already appear in the fixed login page text), and a following `GET /tickets` is 303. Comment: `# Feature: agent-sign-in, Property 2: ...`.
    - **Validates: Requirements 1.4, 3.1, 3.2, 3.3, 3.4, 3.5**
    - **Property 3: Protected routes never serve data without a session**
    - `test_property_protected_routes_redirect_without_session`: `@given` a method and path from the protected set, arbitrary body bytes, and arbitrary ids and unknown paths; resets the tickets file per example with one synthetic ticket; asserts 303, `Location: /login`, a body without the ticket's text, and unchanged file bytes. Comment: `# Feature: agent-sign-in, Property 3: ...`.
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.7**
    - **Property 4: Any invalid session cookie is rejected**
    - `test_property_invalid_cookie_rejected`: `@given` arbitrary text cookie values, a valid cookie with one character changed, and a cookie signed with a different secret; protected routes return 303 to `/login`; `GET /health` is 200 and `GET /login` is 200. Comment: `# Feature: agent-sign-in, Property 4: ...`.
    - **Validates: Requirements 4.4, 5.4**
    - All use `@settings(max_examples=100)` and create the client inside the test (no function-scoped fixture reuse).
    - Finish with `uv run pytest` and `uv run ruff check`.

- [x] 5. Update `conftest.py` so existing tests run as the agent
  - [x] 5.1 Update `tests/conftest.py`
    - Add `FAKE_PASSWORD = "fake-password-for-tests"` with a "test-only value, not a real credential" comment.
    - Add an autouse fixture that sets `AGENT_USERNAME=test-agent`, `AGENT_PASSWORD_HASH=hash_password(FAKE_PASSWORD, iterations=1000)`, and `SESSION_SECRET=test-session-secret` with `monkeypatch`.
    - Add `anon_client` (a `TestClient` with no session, `follow_redirects=False`).
    - Change `client` to sign in through `POST /login` before yielding, keeping its name and ticket behavior, so no assertion in `test_tickets_api.py`, `test_page.py`, `test_health.py`, or `test_classifier.py` changes.
    - Keep the existing `tickets_file` fixture. Move the duplicated env and `FAKE_PASSWORD` setup out of `tests/test_login.py` and `tests/test_auth.py` to use these fixtures where possible, without changing any assertion.
    - Do not edit, delete, skip, or weaken existing tests.
    - _Requirements: 8.1, 8.2, 8.6, 8.8_

  - [x] 5.2 Write a fixture test in `tests/test_login.py`
    - `test_client_fixture_is_signed_in`: using `client`, `GET /tickets` is 200 and `[]`; using `anon_client`, `GET /tickets` is 303 to `/login` (2.2, 8.6).
    - `test_tickets_file_is_temp`: the `tickets_file` path is under `tmp_path`, differs from `data/tickets.json`, and `data/tickets.json` bytes are the same before and after a `POST /tickets` through `client` (8.8).
    - Run the full suite: `uv run pytest` must pass with the existing tests unchanged, then `uv run ruff check`.
    - _Requirements: 2.2, 8.6, 8.8_

- [x] 6. Checkpoint - Ensure all tests pass
  - Run `uv run pytest` and `uv run ruff check`. Ensure all tests pass, ask the user if questions arise.

- [x] 7. Desk follows the redirect to `/login`
  - [x] 7.1 Update `INDEX_HTML` in `src/smart_copilot/page.py`
    - Add `toLoginIfRedirected(res)`: when `res.redirected` is true and `new URL(res.url).pathname === "/login"`, set `window.location = "/login"` and return true. Call it right after each of the three `fetch` calls (`GET /tickets`, `POST /tickets`, `DELETE /tickets/{id}`), before the body is read; the caller returns at once on true, so no error message is shown and no rows render. Other responses keep existing handling, including the status-based error messages.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 7.2 Write page-source tests in `tests/test_page.py` (append; keep existing tests unchanged)
    - Limit: pytest does not run a browser. These tests only read the page source and do not prove the redirect happens in a browser. Task 7.3 covers that.
    - `test_index_defines_redirect_helper`: `INDEX_HTML` contains `toLoginIfRedirected`, `res.redirected`, and `pathname === "/login"` and `window.location` set to `/login` (7.1, 7.2, 7.3).
    - `test_index_calls_helper_after_each_fetch`: the helper is called after each of the three `fetch(` calls (list, create, delete), and before the first `.json()` or `.text()` read in each handler (7.1, 7.2, 7.3, 7.4).
    - `test_index_keeps_existing_error_messages`: `INDEX_HTML` still contains "Could not load tickets" and "Could not delete" in the non-redirect branches (7.5).
    - `test_get_root_signed_in_serves_script`: `client.get("/")` is 200 and includes `toLoginIfRedirected` (2.2, 7.1).
    - Finish with `uv run pytest` and `uv run ruff check`.
    - _Requirements: 2.2, 7.1, 7.2, 7.3, 7.4, 7.5, 8.3_

  - [x]* 7.3 Manual browser check with the Playwright MCP tools
    - Start the app yourself with `uv run uvicorn smart_copilot.main:app --port 8000`, with `AGENT_USERNAME`, `AGENT_PASSWORD_HASH` (from `uv run python -m smart_copilot.auth`), and `SESSION_SECRET` set. Use a synthetic ticket.
    - Sign in, delete the cookie, then load the desk, add a ticket, and delete a ticket. Confirm each lands on `/login` with no "Could not load tickets" or "Could not delete" message and no rows from the login page.
    - This is a manual check and is not part of `uv run pytest`.
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Run `uv run pytest`, `uv run ruff check`, and `uv run check`; report the real output of each. All three must exit 0.
  - Manual scope check, not a pytest test: run `git diff --exit-code src/smart_copilot/classifier.py` and confirm exit code 0.
  - Confirm no AWS, CDK, Cognito, DynamoDB, or S3 code was added and `uv.lock` was changed only by `uv add`. Ask the user if questions arise.
  - _Requirements: 8.2, 8.4, 8.7_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP.
- Requirement 7 has a pytest that checks the page source only; the browser behavior is checked by the optional manual task 7.3.
- Property tests use Hypothesis (`uv add --dev hypothesis`) and validate Properties 1 to 4 of the design.
- Each task lists the requirement numbers it covers.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "4.1"] },
    { "id": 3, "tasks": ["2.3", "4.2"] },
    { "id": 4, "tasks": ["4.3", "5.1"] },
    { "id": 5, "tasks": ["5.2", "7.1"] },
    { "id": 6, "tasks": ["7.2"] },
    { "id": 7, "tasks": ["7.3"] }
  ]
}
```
