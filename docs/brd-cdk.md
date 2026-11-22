# BRD: Infrastructure as Code (CDK)

## Why

The Smart Customer Support Copilot runs only on a laptop today. Tickets live in a JSON file, knowledge-base documents in a local folder, and sign-in is a local session cookie. Before the app can move to AWS, the team needs its cloud resources described as code that can be reviewed, tested, and synthesized without touching an AWS account. This version defines that infrastructure and proves it synthesizes. It does not deploy anything.

## Who it is for

The developer who will later deploy the app, and the reviewer who checks that the infrastructure is safe before anyone deploys it.

## In scope

- A Python AWS CDK app in a new `infra/` folder, with one stack in `us-east-1`.
- The stack defines:
  - An AWS Lambda function for the app.
  - An Amazon API Gateway REST API in front of the Lambda function.
  - An Amazon DynamoDB table for tickets.
  - An Amazon S3 bucket for knowledge-base documents.
  - An Amazon Cognito user pool, with one app client, for agent sign-in.
- Least-privilege IAM permissions between these resources, granted by the CDK grant methods.
- Secure defaults on every resource (see Requirements).
- pytest tests that check the synthesized CloudFormation template with the CDK assertions library. They do not call live AWS.
- `cdk synth` succeeding from `infra/`.
- Updates to the steering rules so that CDK and Cognito are allowed for this work (see Steering changes).

## Out of scope

- `cdk deploy`, `cdk bootstrap`, `cdk destroy`, `cdk diff` against an account, and any other command that reads or changes an AWS account.
- Secrets of any kind: no passwords, keys, tokens, or session secrets in code, `cdk.json`, context, or tests.
- AWS account IDs: none in code, config, context, or tests. The stack sets only the region.
- Slides.
- Changing the app to read tickets from DynamoDB, documents from S3, or users from Cognito. The app keeps using `data/tickets.json`, the local knowledge-base folder, and its own sign-in until a later spec moves it.
- A Lambda adapter for FastAPI and bundling the app's dependencies into the Lambda package.
- Bedrock permissions, custom domains, WAF, VPCs, alarms, CI/CD pipelines, and multiple environments.
- Any change to `src/smart_copilot/classifier.py` or other app code.

## Requirements

1. **CDK app.** `infra/` holds a Python CDK app: an entry point, `cdk.json`, and a stack module. It creates exactly one stack, whose environment sets region `us-east-1` and no account.
2. **Lambda.** The stack defines one Lambda function on the Python 3.12 runtime, with its code taken from the app's source and a set memory size and timeout. Its environment holds the table name and bucket name, and no secrets.
3. **API Gateway.** The stack defines one REST API whose requests are proxied to the Lambda function. Access logging and throttling limits are set.
4. **DynamoDB tickets table.** The stack defines one table with partition key `id` (string), on-demand billing, point-in-time recovery, and a retain removal policy.
5. **S3 knowledge-base bucket.** The stack defines one bucket with all public access blocked, SSL required, server-side encryption, versioning, and a retain removal policy.
6. **Cognito user pool.** The stack defines one user pool with self sign-up turned off, sign-in by username, a password policy of at least 12 characters, and a retain removal policy. It has one app client with no client secret. The stack creates no users.
7. **Permissions.** The Lambda function can read and write the tickets table and read the knowledge-base bucket, and nothing more. No IAM policy uses a `*` action. A `*` resource is allowed only where AWS supports nothing narrower, and each such case is listed in the design.
8. **No secrets or account IDs.** The synthesized template and the `infra/` source contain no account IDs, access keys, passwords, or tokens.
9. **Synth.** `cdk synth` run from `infra/` succeeds without AWS credentials and writes a template to `infra/cdk.out/`, and `cdk.out/` is ignored by git.
10. **Tests.** pytest tests build the stack in memory and check requirements 1 to 8 against the synthesized template. They run under `uv run pytest`, and they make no network or AWS calls.

## Success criteria

- `cdk synth` from `infra/` exits 0 with no AWS credentials set.
- Each of requirements 1 to 8 has at least one passing pytest test that checks the template.
- `uv run pytest`, `uv run ruff check src tests scripts infra`, and `uv run check` pass.
- No command in this work reads or changes an AWS account.
- The existing app tests still pass, and `src/smart_copilot/` is unchanged.

## Constraints

- Python 3.12, managed with `uv`. CDK libraries are added with `uv add`, never by editing `uv.lock` by hand.
- The CDK CLI is installed on the lab machine (version 2.1148.1).
- Region `us-east-1`.
- Synthetic data only.

## Steering changes

The steering rules currently forbid CDK and do not list Cognito. This BRD asks to change them as follows, and the spec plans the edits:

- `tech.md` and `verify-first.md`: allow a CDK app in `infra/` for synth and template tests only. `cdk deploy`, `cdk bootstrap`, and other commands that touch an account stay forbidden without the user's approval. SAM, Terraform, and slides stay forbidden.
- `tech.md`, `product.md`, and `verify-first.md`: add Amazon Cognito to the allowed services, for infrastructure definitions only.
- `structure.md`: add `infra/` to the layout.

## Decisions to confirm

These are proposed defaults. Change them before implementation if they are wrong.

- **REST API, not HTTP API.** REST API supports access logging, throttling, and a Cognito authorizer through the stable CDK constructs.
- **The API does not use the Cognito authorizer yet.** The app already has its own sign-in. Adding the authorizer would put a second login in front of it, so that belongs in the spec that moves sign-in to Cognito.
- **Lambda code without an adapter.** The function's code is the app's `src/` folder, with a handler path that a later spec will implement. The template synthesizes, but a deployed function would not run yet. This is acceptable only because deploy is out of scope.
- **Retain on delete.** The table, the bucket, and the user pool are kept if the stack is deleted, so a mistaken delete cannot destroy tickets, documents, or users.
- **Dependencies in their own group.** `aws-cdk-lib` and `constructs` go in a `uv` dependency group for infrastructure, so the app's runtime dependencies do not change.
- **CDK CLI telemetry off.** Telemetry is turned off for `cdk synth`, matching the telemetry-off settings in `scripts/check.py`. The exact setting is taken from the installed CLI's documentation.
