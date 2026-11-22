# Structure

## Layout

```
.
├── .kiro/steering/        Steering rules
├── src/smart_copilot/     Application package (import as `smart_copilot`)
│   ├── __init__.py
│   └── main.py            FastAPI `app` and `/health` route
├── tests/                 pytest tests. Create when the first test is added.
├── data/tickets.json      Synthetic tickets. Create when a spec needs it.
├── pyproject.toml
├── uv.lock
├── .python-version
└── README.md
```

## Rules

- Put application code in `src/smart_copilot/`. Do not create a top-level `app/` package.
- Put tests in `tests/`, named `test_*.py`, mirroring the package layout.
- Read tickets from `data/tickets.json` until a spec says otherwise.
- Create a new subpackage only when a spec calls for it.
- Do not commit `.venv/`, `__pycache__/`, `.pytest_cache/`, or `.ruff_cache/`. Create a `.gitignore` for them when the user asks.
- Branch, commit, and push rules are in `git-workflow.md`.
