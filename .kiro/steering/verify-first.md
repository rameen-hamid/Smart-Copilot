# Verify first

Never guess. Check, then write.

## Libraries

- Before calling any library function, class, or method, read the installed source or docs in `.venv/lib/python3.12/site-packages/`, or run `uv run python -c "help(...)"`.
- Never invent a method, parameter, or import. If you cannot find it, say so and ask.
- Check the installed version in `uv.lock` before relying on version-specific behavior.

## AWS and Bedrock

- Before calling an AWS API, read its documentation or the installed `boto3` service model for the exact operation name, parameters, and response shape.
- Never guess a Bedrock model ID, request body, or response field. Look them up. Take the model ID from configuration, not a hard-coded guess.
- Use an AWS service only when a spec names it. Allowed: Bedrock, Lambda, API Gateway, DynamoDB, S3. Region `us-east-1`.
- Bedrock is the only model API. Use it for classification, urgency, sentiment, and draft replies.
- Never use Amazon Comprehend, Amazon Kendra, or Amazon Lookout for Metrics.
- Do not make AWS calls that create, change, or delete resources, or that cost money, without the user's approval. Confirm the account and region first.
- Keep Bedrock calls under 1 request per second. The workshop account is limited. Add a delay or rate limiter. Never loop over many tickets without one.

## Project facts

- Read commands from `pyproject.toml` and the steering files. Do not invent commands.
- Before editing a file, read it. Before creating a file, check that it does not already exist.
- Tickets live in `data/tickets.json` until a spec says otherwise. Do not invent S3 retrieval.
- Do not add CDK, SAM, Terraform, deploy steps, or slides.
- Use synthetic tickets only. If data looks like real personal, financial, or health data, stop and ask.
- If a requirement is ambiguous or the files do not match what the user described, stop and ask. Do not fill the gap with an assumption.
