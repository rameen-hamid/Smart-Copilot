# Code style

- Python 3.12. Follow `ruff`. Run `uv run ruff check` after edits.
- Put type hints on every public function: parameters and return type.
- Wrap all I/O in error handling: file reads, network calls, and every AWS call. Catch specific exceptions, not bare `except`. Return or raise a clear error. Do not swallow it.
- Never put secrets in code, tests, fixtures, logs, or config files. No access keys, tokens, or passwords. Read config from environment variables or the default AWS credential chain.
- Do not log ticket text, customer names, or emails.
- Keep modules small and single-purpose. Put application code under `src/smart_copilot/`.
- Do not add dependencies unless the task needs them. Add them with `uv add` (runtime) or `uv add --dev` (dev). Never edit `uv.lock` by hand.
- Do not add features, files, or refactors the task did not ask for.
