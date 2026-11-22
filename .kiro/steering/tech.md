# Tech

## Stack

- Python 3.12 managed with `uv`. Dependencies are in `pyproject.toml` and `uv.lock`.
- FastAPI served by uvicorn. Tests use pytest. Lint uses ruff.
- App entry point: `smart_copilot.main:app`.

## Commands

- Run: `uv run uvicorn smart_copilot.main:app --port 8000`
- Test: `uv run pytest`
- Lint: `uv run ruff check`
- Add a runtime dependency: `uv add <pkg>`. Add a dev dependency: `uv add --dev <pkg>`.
- Pre-review checks (ruff, gitleaks, semgrep): `uv run check`. Same as `uv run python scripts/check.py`.
- `pyproject.toml` defines only the `check` command alias. Do not invent others.

## Data

- Tickets live in `data/tickets.json` until a spec says otherwise. The `TICKETS_FILE` environment variable overrides the path. Tests MUST set it.
- Do not invent S3 retrieval or any other storage.
- Synthetic tickets only. No real personal, financial, or health data.

## AWS

- Use AWS only when a spec asks for it. Allowed: Bedrock, Lambda, API Gateway, DynamoDB, S3. Region `us-east-1`.
- Bedrock is the only model API. It does classification, urgency, sentiment, and draft replies.
- Never use Amazon Comprehend, Amazon Kendra, or Amazon Lookout for Metrics.
- Keep Bedrock under 1 request per second in the workshop account.

## Not in scope

- No CDK, SAM, Terraform, deploy steps, or slides.

See `verify-first.md`, `code-style.md`, `testing.md`, and `git-workflow.md` for the rules that apply to every change.
