# Requirements Document

## Introduction

The Smart Customer Support Copilot runs only on a laptop. Tickets live in `data/tickets.json`, knowledge-base documents in a local folder, and sign-in is a local session cookie. This feature describes the cloud resources as code in a Python AWS CDK app in `infra/`, so a reviewer can check them, test them, and synthesize them without touching an AWS account. The feature does not deploy anything and does not change the application in `src/smart_copilot/`.

Source: `docs/brd-cdk.md`.

In scope:

- A Python CDK app in `infra/` with one stack in `us-east-1`.
- In the stack: a Lambda function, a REST API Gateway, a DynamoDB tickets table, an S3 knowledge-base bucket, and a Cognito user pool with one app client.
- Least-privilege IAM permissions granted by the CDK grant methods.
- pytest tests on the synthesized CloudFormation template, with no live AWS calls.
- A successful `cdk synth` from `infra/`.
- Steering rule updates that allow CDK (synth and template tests only) and Cognito (infrastructure definitions only).

Out of scope:

- `cdk deploy`, `cdk bootstrap`, `cdk destroy`, `cdk diff` against an account, and any other command that reads or changes an AWS account.
- Secrets of any kind, and AWS account IDs.
- Slides.
- Changing the app to read tickets from DynamoDB, documents from S3, or users from Cognito.
- A Lambda adapter for FastAPI, and bundling the app's dependencies into the Lambda package.
- Bedrock permissions, custom domains, WAF, VPCs, alarms, CI/CD pipelines, and multiple environments.
- Any change to `src/smart_copilot/`, including `classifier.py`.

Decisions taken from the BRD:

- The API is a REST API, not an HTTP API.
- The API does not use a Cognito authorizer yet.
- The Lambda code is the app's `src/` folder with a handler path that a later spec implements, so a deployed function would not run yet.
- The table, the bucket, and the user pool are retained when the stack is deleted.
- `aws-cdk-lib` and `constructs` go in their own `uv` dependency group.
- CDK CLI telemetry is turned off for `cdk synth`, using the setting documented for the installed CLI.

## Glossary

- **CDK_App**: The Python AWS CDK application in the `infra/` folder, made of an entry point, `cdk.json`, and a stack module.
- **Stack**: The single CloudFormation stack that the CDK_App creates.
- **Template**: The CloudFormation template that the CDK_App synthesizes from the Stack.
- **App_Function**: The one AWS Lambda function defined in the Stack.
- **Api**: The one Amazon API Gateway REST API defined in the Stack.
- **Tickets_Table**: The one Amazon DynamoDB table defined in the Stack for tickets.
- **Knowledge_Base_Bucket**: The one Amazon S3 bucket defined in the Stack for knowledge-base documents.
- **User_Pool**: The one Amazon Cognito user pool defined in the Stack for agent sign-in.
- **App_Client**: The one Cognito app client attached to the User_Pool.
- **Infra_Tests**: The pytest tests that build the Stack in memory and check the Template.
- **Steering_Rules**: The rule files `.kiro/steering/tech.md`, `verify-first.md`, `product.md`, and `structure.md`.
- **Account_Command**: Any command that reads or changes an AWS account, including `cdk deploy`, `cdk bootstrap`, `cdk destroy`, and `cdk diff` against an account.
- **Wildcard_Resource_Exception**: A `*` resource in an IAM policy statement for an action where AWS supports no narrower resource, listed in the design document.

## Requirements

### Requirement 1: CDK app and stack

**User Story:** As a developer, I want a CDK app in `infra/` with one stack in `us-east-1`, so that the cloud resources are described as code before any deploy.

#### Acceptance Criteria

1. THE CDK_App SHALL consist of an entry point, a `cdk.json` file, and a stack module, all inside the `infra/` folder.
2. WHEN the CDK_App is synthesized, THE CDK_App SHALL produce a cloud assembly that contains exactly one CloudFormation stack artifact.
3. THE Stack SHALL set its environment region to the literal value `us-east-1`, so that the Stack's `region` property equals `us-east-1` after synthesis.
4. THE Stack SHALL leave its environment account unset, so that the Stack's `account` property resolves to the `AWS::AccountId` pseudo parameter and not to a 12-digit literal.

### Requirement 2: Lambda function

**User Story:** As a developer, I want a Lambda function definition for the app, so that the compute resource is reviewable before deploy.

#### Acceptance Criteria

1. THE Stack SHALL define exactly one App_Function, so that the synthesized template contains exactly one resource of type `AWS::Lambda::Function` that was declared by the app's own code. Helper functions that the CDK adds for custom resources are excluded from this count, and the design lists them if any are present.
2. THE App_Function SHALL set the `Runtime` property to `python3.12`.
3. THE App_Function SHALL take its code from the app's `src/` folder and SHALL set the `Handler` property to a module-and-function path that a later spec implements.
4. THE App_Function SHALL set the `MemorySize` property to an explicit integer from 128 to 10240 MB and the `Timeout` property to an explicit integer from 1 to 900 seconds.
5. THE App_Function SHALL set `Environment.Variables` with exactly two entries. One entry SHALL reference the Tickets_Table through a `Ref` to the `AWS::DynamoDB::Table` resource. The other SHALL reference the Knowledge_Base_Bucket through a `Ref` to the `AWS::S3::Bucket` resource.
6. IF an `Environment.Variables` entry of the App_Function holds a password, an access key, a token, or a session secret, THEN THE CDK_App test suite SHALL fail.

### Requirement 3: API Gateway

**User Story:** As a developer, I want a REST API in front of the Lambda function, so that the app has an HTTP entry point.

#### Acceptance Criteria

1. THE Stack SHALL define exactly one `AWS::ApiGateway::RestApi` resource and no `AWS::ApiGatewayV2::Api` resource.
2. THE Api SHALL proxy every request path and HTTP method to the App_Function. The synthesized template SHALL contain an `AWS::ApiGateway::Method` resource whose `Integration.Type` is `AWS_PROXY` and whose `Integration.Uri` references the App_Function, and an `AWS::Lambda::Permission` resource that allows API Gateway to invoke the App_Function.
3. THE Api SHALL write access logs, so that the `AWS::ApiGateway::Stage` resource sets `AccessLogSetting.DestinationArn` to the ARN of an `AWS::Logs::LogGroup` resource.
4. THE Api SHALL set explicit throttling limits, so that the `AWS::ApiGateway::Stage` resource sets `MethodSettings` with `ThrottlingRateLimit` and `ThrottlingBurstLimit`. Each of these SHALL be a number greater than 0, and the burst limit SHALL be greater than or equal to the rate limit.

### Requirement 4: DynamoDB tickets table

**User Story:** As a developer, I want a tickets table definition, so that ticket storage is protected and ready for a later migration.

#### Acceptance Criteria

1. THE Stack SHALL define exactly one Tickets_Table, so that the synthesized template contains exactly one resource of type `AWS::DynamoDB::Table`.
2. THE Tickets_Table SHALL set `KeySchema` to a single `HASH` key with `AttributeName` equal to `id`, and SHALL set `AttributeDefinitions` so that `id` has `AttributeType` equal to `S`.
3. THE Tickets_Table SHALL set `BillingMode` to `PAY_PER_REQUEST` and SHALL NOT set `ProvisionedThroughput`.
4. THE Tickets_Table SHALL set `PointInTimeRecoverySpecification.PointInTimeRecoveryEnabled` to `true`.
5. THE Tickets_Table SHALL set the resource attributes `DeletionPolicy` and `UpdateReplacePolicy` to `Retain`.

### Requirement 5: S3 knowledge-base bucket

**User Story:** As a developer, I want a knowledge-base bucket definition with secure defaults, so that documents are stored privately and safely.

#### Acceptance Criteria

1. THE Stack SHALL define exactly one Knowledge_Base_Bucket, so that the Template contains exactly one resource of type `AWS::S3::Bucket`.
2. THE Knowledge_Base_Bucket SHALL block all public access, so that its `PublicAccessBlockConfiguration` property has `BlockPublicAcls`, `BlockPublicPolicy`, `IgnorePublicAcls`, and `RestrictPublicBuckets` all set to `true`.
3. THE Knowledge_Base_Bucket SHALL require SSL for every request, so that the Template contains an `AWS::S3::BucketPolicy` for the bucket with a statement whose `Effect` is `Deny`, whose `Principal` is `*`, and whose `Condition` is `aws:SecureTransport` equal to `false`.
4. THE Knowledge_Base_Bucket SHALL have server-side encryption enabled, so that its `BucketEncryption.ServerSideEncryptionConfiguration` property contains at least one rule with a `ServerSideEncryptionByDefault.SSEAlgorithm` value.
5. THE Knowledge_Base_Bucket SHALL have versioning enabled, so that its `VersioningConfiguration.Status` property is `Enabled`.
6. THE Knowledge_Base_Bucket SHALL have a retain removal policy, so that its `DeletionPolicy` and `UpdateReplacePolicy` attributes are both `Retain`.

### Requirement 6: Cognito user pool

**User Story:** As a developer, I want a user pool and app client definition, so that agent sign-in infrastructure exists for a later spec.

#### Acceptance Criteria

1. THE Stack SHALL define exactly one User_Pool, so that the Template contains exactly one resource of type `AWS::Cognito::UserPool`.
2. THE User_Pool SHALL have self sign-up turned off, so that its `AdminCreateUserConfig.AllowAdminCreateUserOnly` property is `true`.
3. THE User_Pool SHALL allow sign-in by username, so that its `UsernameAttributes` and `AliasAttributes` properties are absent, which makes the username the sign-in identifier.
4. THE User_Pool SHALL require passwords of at least 12 characters, so that its `Policies.PasswordPolicy.MinimumLength` property is 12 or greater.
5. THE User_Pool SHALL have a retain removal policy, so that its `DeletionPolicy` and `UpdateReplacePolicy` attributes are both `Retain`.
6. THE Stack SHALL define exactly one App_Client attached to the User_Pool, so that the Template contains exactly one resource of type `AWS::Cognito::UserPoolClient` whose `UserPoolId` property references the User_Pool.
7. THE App_Client SHALL have no client secret, so that its `GenerateSecret` property is `false` or absent.
8. THE Stack SHALL create no user in the User_Pool, so that the Template contains zero resources of type `AWS::Cognito::UserPoolUser`.

### Requirement 7: Least-privilege permissions

**User Story:** As a reviewer, I want the Lambda function to have only the permissions it needs, so that the infrastructure is safe to deploy later.

#### Acceptance Criteria

1. THE Stack SHALL grant the App_Function read and write access to the Tickets_Table through the CDK grant methods, so that an `AWS::IAM::Policy` attached to the App_Function role has a statement whose `Resource` is only the Tickets_Table ARN (and its index ARN pattern) and whose `Action` values are all `dynamodb:` actions covering both read and write.
2. THE Stack SHALL grant the App_Function read access to the Knowledge_Base_Bucket through the CDK grant methods, so that an `AWS::IAM::Policy` attached to the App_Function role has a statement whose `Resource` is only the Knowledge_Base_Bucket ARN and the ARN pattern for objects in it, and whose `Action` values are read-only `s3:` actions (`s3:GetObject*`, `s3:GetBucket*`, `s3:List*`) with no `s3:Put*`, `s3:Delete*`, or `s3:*`.
3. THE Stack SHALL grant the App_Function no permission on any resource other than the Tickets_Table, the Knowledge_Base_Bucket, and the logging and execution permissions that the CDK adds to every Lambda function role, so that the App_Function role has no inline or managed policy other than the Requirement 7.1 and 7.2 statements and the single Lambda basic execution managed policy in its `ManagedPolicyArns` property. A role that the CDK creates for API Gateway to write CloudWatch logs, if the design keeps one, counts as a listed exception and the design SHALL name it. Otherwise the design SHALL turn that role off.
4. THE Template SHALL contain no IAM policy statement whose action is `*`, so that no `Action` value in any `AWS::IAM::Policy`, `AWS::IAM::ManagedPolicy`, or `AWS::IAM::Role` policy document equals `*`.
5. THE Template SHALL contain a `*` resource in an IAM policy statement only for a Wildcard_Resource_Exception, so that every statement whose `Resource` equals `*` matches an entry listed in the design, and a Template with no such statement also passes.

### Requirement 8: No secrets or account IDs

**User Story:** As a reviewer, I want the infrastructure free of secrets and account IDs, so that the code is safe to share and reuse.

#### Acceptance Criteria

1. THE Template SHALL contain no AWS account ID, so that no string value in it contains a standalone run of exactly 12 digits (one not preceded or followed by a letter or digit), and `AWS::AccountId` and `AWS::Partition` pseudo-parameter references that the CDK emits are not counted as account IDs. CDK asset hashes are 64-character hexadecimal strings and are not account IDs.
2. THE `infra/` source SHALL contain no AWS account ID, so that no `.py` or `.json` file in `infra/` (excluding `cdk.out/`) contains a standalone run of exactly 12 digits (one not preceded or followed by a letter or digit), and the stack environment sets only the region `us-east-1`.
3. THE Template SHALL contain no access key, password, or token, so that it has no string value matching an access key ID pattern (`AKIA` or `ASIA` followed by 16 uppercase letters or digits), no private key header, no resource of type `AWS::SecretsManager::Secret`, and no Lambda environment variable whose name contains `PASSWORD`, `SECRET`, or `TOKEN`.
4. THE `infra/` source SHALL contain no access key, password, or token, so that no `.py` or `.json` file in `infra/` (excluding `cdk.out/`) contains an access key ID pattern, a private key header, or an assignment of a literal string to a name containing `password`, `secret`, or `token`.
5. THE `cdk.json` file and the CDK context SHALL contain no secret and no AWS account ID, so that neither contains a standalone run of exactly 12 digits (one not preceded or followed by a letter or digit), an access key ID pattern, or a context key named `account`.

### Requirement 9: Synthesis

**User Story:** As a developer, I want `cdk synth` to succeed offline, so that I can prove the infrastructure is valid without an AWS account.

#### Acceptance Criteria

1. WHEN `cdk synth` runs from `infra/` with no AWS credentials set, and with CDK notices and version checks turned off, THE CDK_App SHALL synthesize the Template for exactly one stack in region `us-east-1` with no account, and exit with code 0.
2. WHEN `cdk synth` exits with code 0, THE CDK_App SHALL have written one Template file for the stack to `infra/cdk.out/`.
3. IF `cdk synth` fails, THEN THE CDK_App SHALL exit with a non-zero code and print an error to standard error that names the failure.
4. THE repository `.gitignore` SHALL list `infra/cdk.out/` so that `git status` shows no file under `infra/cdk.out/` as untracked after `cdk synth`.
5. WHERE the installed CDK CLI (version 2.1148.1) supports a telemetry-off setting, THE CDK_App SHALL turn off CDK CLI telemetry for `cdk synth`, using the setting documented for that CLI version and matching the telemetry-off settings in `scripts/check.py`.

### Requirement 10: Template tests

**User Story:** As a reviewer, I want automated tests on the synthesized template, so that requirements 1 to 8 stay true as the code changes.

#### Acceptance Criteria

1. THE Infra_Tests SHALL build the Stack in memory and check the Template against each of requirements 1 to 8 with at least one test per requirement, using the CDK assertions library.
2. THE Infra_Tests SHALL make no network call and no AWS call, and SHALL pass when no AWS credentials are set.
3. WHEN `uv run pytest` runs, THE Infra_Tests SHALL run and pass together with the existing app tests, and pytest SHALL exit with code 0 and not code 5.
4. IF the Template violates any of requirements 1 to 8, THEN THE Infra_Tests SHALL fail the matching test with an assertion failure that names the violated check.
5. THE Infra_Tests SHALL use synthetic data and contain no secret and no AWS account ID.

### Requirement 11: Dependencies

**User Story:** As a developer, I want the CDK libraries kept separate from the app's runtime dependencies, so that the app's dependencies do not change.

#### Acceptance Criteria

1. THE project SHALL declare `aws-cdk-lib` and `constructs` in one `uv` dependency group for infrastructure, and in no other dependency list.
2. THE project SHALL leave the app's runtime dependency list in `pyproject.toml` with the same entries and version constraints as before this work.
3. THE project SHALL add the CDK libraries with the `uv add` command, so that `uv.lock` is never edited by hand.

### Requirement 12: Steering rule updates

**User Story:** As a developer, I want the steering rules to allow this CDK work and nothing broader, so that agents follow the approved scope.

#### Acceptance Criteria

1. THE Steering_Rules `tech.md` and `verify-first.md` SHALL each state that a CDK app in `infra/` is allowed for synth and template tests only.
2. THE Steering_Rules `tech.md` and `verify-first.md` SHALL each state that `cdk deploy`, `cdk bootstrap`, `cdk destroy`, `cdk diff` against an account, and every other Account_Command remain forbidden without the user's approval.
3. THE Steering_Rules `tech.md` and `verify-first.md` SHALL each state that SAM, Terraform, and slides remain forbidden.
4. THE Steering_Rules `tech.md`, `product.md`, and `verify-first.md` SHALL each list Amazon Cognito as an allowed service for infrastructure definitions only.
5. THE Steering_Rules `structure.md` SHALL list `infra/` in the project layout.
6. THE Steering_Rules SHALL keep every rule not named in criteria 1 to 5 unchanged.

### Requirement 13: Account safety and app isolation

**User Story:** As a reviewer, I want proof that this work touched no AWS account and left the app alone, so that I can trust the change.

#### Acceptance Criteria

1. THE CDK_App work SHALL run no Account_Command.
2. THE CDK_App work SHALL leave every file under `src/smart_copilot/` unchanged, so that `git diff` against the starting commit shows no change under `src/smart_copilot/`.
3. WHEN the work is complete, THE project SHALL pass `uv run pytest`, `uv run ruff check src tests scripts infra`, and `uv run check`, each with exit code 0.
4. WHEN the work is complete, THE existing app tests SHALL pass with no test deleted, skipped, or weakened.
5. IF any of the commands in criterion 3 fails or cannot run, THEN THE project SHALL NOT be reported as complete, and the report SHALL state the failing command and its output.
