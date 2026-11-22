# Structure

## Layout

```
.
├── .kiro/steering/        Steering rules
├── src/smart_copilot/     Application package (import as `smart_copilot`)
│   ├── __init__.py
│   ├── main.py            FastAPI `app`, routes
│   ├── classifier.py      Keyword classifier and draft reply templates
│   ├── storage.py         Read and write the tickets JSON file
│   └── page.py            HTML page served at `GET /`
├── tests/                 pytest tests. `conftest.py` points `TICKETS_FILE` at a temp file.
├── docs/                  BRD and other specs
├── infra/                 CDK app (synth and template tests only). Not deployed.
├── data/tickets.json      Synthetic tickets. Created by the app at runtime.
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
