---
name: code-review
description: Reviews a Python (.py) file in this project (Smart Customer Support Copilot) for type hints on public functions, error handling on I/O and AWS calls, secrets in source, and tests that assert real behavior. Applies to reviews of .py files in this project, under src/smart_copilot/, tests/ or scripts/. Use whenever the user asks to review, audit, check, or give feedback on a Python file, module, or change here, even if they don't say "code review". Produces a summary with Critical, Warnings, Suggestions, and Passed sections.
---

# Code review

Review one Python file in this project and report findings in a fixed format. This skill only reads. Do not edit the file under review, and do not stage or commit anything.

## Steps

1. **Identify the file.** If the user did not name one, ask. If the path is outside this repository, say so and stop.
2. **Read it fully** with a file-read tool. Never review from memory or from the file name alone.
3. **Find its tests.** Source files in `src/smart_copilot/<name>.py` are tested by `tests/test_<name>.py`. Read that file if it exists. If the file under review is itself a test, review it directly and read the source it covers.
4. **Run the automated checks only when asked or when the result matters.** `uv run ruff check <file>` is cheap and can be included. Do not run `uv run pytest` unless the user wants it. Never call real AWS or Bedrock.
5. **Apply the four checks below**, then write the summary.

## Checks

### 1. Type hints on public functions
Public means the name does not start with `_`, including methods on public classes and FastAPI route handlers.
- Every parameter and the return type must be annotated. `self` and `cls` are exempt.
- Missing return annotation or parameter annotation: **Warning**. `Any` used where a concrete type is obvious: **Suggestion**.

### 2. Error handling on I/O and AWS calls
I/O means file reads and writes, network calls, and every AWS or boto3 call (Bedrock, S3, DynamoDB, Lambda).
- Each call must sit inside error handling that catches specific exceptions (for example `OSError`, `json.JSONDecodeError`, `botocore.exceptions.ClientError`).
- Bare `except:` or `except Exception:` that swallows the error: **Critical** when it hides an I/O or AWS failure, otherwise **Warning**.
- An unguarded I/O or AWS call: **Critical** for AWS calls and writes, **Warning** for reads.
- Errors must be raised or returned clearly, not silently dropped.
- Bedrock calls inside a loop need a delay or rate limiter (limit is under 1 request per second). Missing limiter: **Critical**.
- Logging that includes ticket text, customer names, or emails: **Critical**.

### 3. No secrets in source
Look for access keys, tokens, passwords, API keys, private keys, connection strings with credentials, and hard-coded bearer headers. Check string literals, defaults, comments, and test fixtures.
- Any real-looking secret: **Critical**. Report the line and the kind of secret, never print the value.
- Config must come from environment variables or the default AWS credential chain. A hard-coded Bedrock model ID: **Warning** (it should come from configuration).
- Real-looking personal, financial, or health data in fixtures: **Critical**. Only synthetic data is allowed.
- If the project script exists, `uv run python scripts/check.py` runs gitleaks and Semgrep and can back up this check.

### 4. Tests that assert the behavior
For each public function or route in the file, look for a test that checks the expected result, not just that the code runs.
- No test for a public function or route: **Warning** (**Critical** if it does I/O or AWS calls).
- A test with no assertion, or one that only asserts `is not None`, a status code without checking the body, or `True`: **Warning**.
- Tests that call real AWS or Bedrock instead of a mock or fake: **Critical**.
- Tests that do not set `TICKETS_FILE` to a temp file when touching ticket storage: **Warning**.
- Skipped, deleted, or weakened tests: **Critical**.
- Missing edge or error cases (empty input, missing file, AWS `ClientError`): **Suggestion**.

## Output format

Always produce exactly these four sections, in this order. Write "None." under a section with no findings. Cite `file:line` for every finding and give a one-line fix.

```
## Code review: <path>

### Critical
- <file:line> <what is wrong>. Fix: <one-line fix>.

### Warnings
- <file:line> <what is wrong>. Fix: <one-line fix>.

### Suggestions
- <file:line> <improvement>.

### Passed
- <check that passed, with the evidence, e.g. "All 4 public functions have full type hints">.
```

Rules for the summary:
- A check with no findings goes under **Passed**, naming what was checked. Do not leave a check out of the summary: each of the four checks appears in a finding or in Passed.
- Do not report style issues that `ruff` already covers unless the user asked.
- If the file has nothing to check for a category (for example no I/O), put it under Passed as "not applicable" with the reason.
- Be specific. Do not pad with generic advice, and do not claim tests pass unless you ran them.
