# Smart Customer Support Copilot — Hackathon Slides

---

## 1. Problem

A support agent receives customer queries and complaints.
They need to know, for every message:

- What is this ticket about? (category)
- How urgent is it?
- How is the customer feeling?
- What should I say?

Without help, the agent reads each message, decides its urgency manually, and writes a reply from scratch — before they have even decided which ticket to answer first.

> **Speaker notes:**
> The queue problem is real: a negative urgent billing complaint and a neutral low-priority question look the same in the inbox. The agent should spend their time on the customer, not on routing.

---

## 2. Who it is for

**A single support agent** who works the queue and decides what to answer first.

The agent checks every draft before anything is sent. Drafts are suggestions — they are never sent automatically.

**What improves:**
- The agent no longer categorises and prioritises by hand. The queue is already sorted high → medium → low when they open it.
- Each ticket arrives with a draft reply and a recommended solution grounded in past tickets and knowledge-base documents. The agent edits or approves instead of writing from scratch.
- Time spent on routine ticket triage and first-draft writing moves toward zero.

> **Speaker notes:**
> The BRD for the ticket desk (docs/brd-ticket-desk.md) says: "A support agent who pastes in a customer message, checks the result, and works through a list of saved tickets." The queue is sorted by urgency so high-priority items are always at the top.

---

## 3. Features

**Sign-in**
One support agent signs in with a username and password. Every route except `/health` and `/login` requires a valid session. Session cookies are signed, HTTP-only, `SameSite=Lax`, and last 8 hours.

**Ticket queue sorted by urgency**
`GET /tickets` returns tickets sorted high → medium → low, insertion order within each level.

**Classification and sentiment**
Every ticket carries category (`billing`, `technical`, `account`, `other`), urgency (`low`, `medium`, `high`), and sentiment (`negative`, `neutral`, `positive`).

**Bedrock draft reply with local fallback**
Amazon Bedrock generates the category, urgency, sentiment, and draft reply at ticket-creation time. If `BEDROCK_MODEL_ID` is unset, Bedrock is unavailable, or the response is malformed, the local keyword classifier fills in the same fields and the ticket is still created with status 201.

**Recommended solution grounded in past tickets and KB documents**
At creation time the app retrieves the top-3 most relevant snippets from past tickets and knowledge-base `.txt` files by keyword-overlap scoring, then sends the message and snippets to Bedrock for a grounded recommendation. When no snippets are found, or when Bedrock fails, a local fallback string is used.

**Infrastructure as code (CDK)**
A CDK stack in `infra/` defines the Lambda function, API Gateway, DynamoDB table for tickets, S3 bucket for knowledge-base documents, and Cognito user pool — all with least-privilege IAM and secure defaults. The stack synthesises. It has not been deployed.

> **Speaker notes:**
> The five features map to five merged pull requests and five approved specs: ticket-desk, bedrock-analysis, agent-desk, agent-sign-in, and cdk-stack.

---

## 4. Specs in Kiro

Code was written only after a spec was approved.

**Spec folders under `.kiro/specs/`:**
- `ticket-desk` — ticket CRUD, queue sorting, HTML page
- `bedrock-analysis` — Bedrock analysis at creation time, fallback to local classifier
- `agent-desk` — KB document loading, keyword-overlap retrieval, grounded recommendation
- `agent-sign-in` — PBKDF2 password hashing, session cookie, protected routes
- `cdk-stack` — CDK stack definition and CDK assertions tests

**How it worked:**
- **Steering files** (`.kiro/steering/`) set the rules every agent follows: branch names, commit format, allowed AWS services, test requirements, and the `verify-first` rule that bans invented library methods.
- **The spec agent** read existing code, asked questions in one numbered batch with defaults, wrote the BRD and requirements document, and stopped. No code until approval.
- **The build agent** implemented only what the spec said, wrote a pytest with each task, and ran `uv run ruff check` and `uv run pytest` before reporting done. It was denied `git push`, `git merge`, and `git checkout main`.
- **The reviewer agent** runs on `claude-opus-4.8`, reads the diff and runs the checks, and reports findings as Critical / Warnings / Suggestions. It is denied `fs_write` everywhere and cannot approve, merge, or edit code.

> **Speaker notes:**
> The steering files are always-included documents. Every agent sees them on every prompt. The verify-first rule caused the bedrock-analysis build agent to look up the installed boto3 bedrock-runtime SDK and confirm the `converse()` call shape before writing `BedrockAnalyzer.analyze()`. It did not guess the API.

---

## 5. Working demo

# Demo

> **Speaker notes:**
> Attach the demo video here.

---

## 6. Lessons learned

**An empty or ambiguous brief made the agent stop and ask before building.**
The spec agent sent questions in one numbered batch with proposed defaults, waited for answers, and only then wrote the spec. When a requirement was ambiguous (for example, the message character limit for the ticket desk, or the exact fallback behaviour when Bedrock is unavailable), it listed the gap and asked rather than guessing.

**Bedrock runs when a ticket is created and falls back locally when it fails or the model id is unset.**
If `BEDROCK_MODEL_ID` is unset, or Bedrock raises `ClientError` (throttle), returns malformed output, or returns an out-of-enum value, the local keyword classifier produces the category, urgency, sentiment, and draft reply, and `source` is set to `"local"`. The ticket is still created with status 201. The same fallback covers the recommended solution: if there are no snippets, or Bedrock fails, `LOCAL_FALLBACK_RECOMMENDATION` is used.

**The reviewer and the tests state what they could not prove.**
The reviewer's report ends with a "What I could not prove" section. Test files note when a check was verified by assertion and when it was left as a manual concern. For example, `test_bedrock.py` verifies that `recommend()` calls `rate_limiter.wait()` once per call, but cannot prove that two simultaneous requests would not exceed one Bedrock call per second in a multi-threaded deployment.

**A push fails when the GitHub account has no write access.**
The git-workflow steering bans `git push` from agents. When a collaborator without repository write access tried to push a branch, GitHub returned a 403. The exact command to push was printed for the repository owner to run. No agent forced or bypassed the check.
