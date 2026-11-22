# Git workflow

## Branches

- Branch names MUST match `^(feat|fix|chore|docs|refactor)/[a-z0-9]+(-[a-z0-9]+)*$`. Example: `feat/ticket-classifier`.
- Before editing files for a task, MUST run `git branch --show-current`.
- If the current branch is `main` or does not match the pattern, MUST create a matching branch with `git switch -c <type>/<slug>` before the first edit.
- NEVER commit on a branch that does not match the pattern.

## Commits

- MUST make exactly one commit per task.
- Message format: `<Verb> <object>`. The verb is imperative and capitalized. Example: `Add health route`.
- Message MUST be under 72 characters, with no trailing period and no type prefix.
- MUST stage files by exact path with `git add <path>`.
- NEVER use `git add -A`, `git add .`, or `git commit -a`.
- NEVER stage `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.env`, or credential files.

## Forbidden

- NEVER commit to `main`.
- NEVER run `git push`, `git merge`, `git rebase`, `git reset --hard`, or `git push --force`.
- NEVER change git config or use `--no-verify`.

## Blocked

- If a task needs a push, a merge, or a commit on `main`, MUST stop and print the exact command for the user to run. NEVER run it.
