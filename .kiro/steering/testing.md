# Testing

## Definition of done

- A task is done only when `uv run pytest` passes.
- Also run `uv run ruff check` and fix what it reports before reporting done.
- Report the actual pass/fail output. Never claim a pass you did not run.
- Pytest exit code 5 means no tests ran. That is not a pass. Add a test or say that none exist.
- If a check cannot run, say so and why. Do not report the task as done.

## Writing tests

- Add or update a test for every behavior you change. Each test asserts the requirement's own expected values.
- Put tests in `tests/`, named `test_*.py`, mirroring `src/smart_copilot/`.
- Use FastAPI's `TestClient` for routes.
- Never call real AWS or Bedrock in tests. Mock the client or use a fake.
- Use synthetic data only. Fixtures must not contain real personal, financial, or health data.
- Do not delete, skip, or weaken a failing test to make the suite pass. Fix the code or ask.
