# Implementation Plan: cdk-stack

## Overview

This plan builds the Python CDK app in `infra/` in small steps. It starts with dependencies and a re-check of the design's open items, then the test helpers (scanners), the app skeleton, one stack resource group at a time, the secret and account-ID checks, the steering edits, and a final checkpoint. All work stays on the current branch `feat/cdk-stack`. Nothing is committed unless the user asks.

**Safety rules for every task**

- Never run `cdk deploy`, `cdk bootstrap`, `cdk destroy`, `cdk diff`, `cdk import`, `cdk doctor`, or any command that reads or changes an AWS account. The only CDK CLI command allowed is the offline `cdk synth` in the final checkpoint.
- Add dependencies only with `uv add --group infra aws-cdk-lib constructs`. Never edit `uv.lock` by hand.
- Tests use `aws_cdk.assertions`, make no network or AWS call, and use synthetic data only.
- Do not change anything under `src/smart_copilot/`.
- Do not delete, skip, or weaken an existing test.

**Task completion commands.** Every task ends by running both of these and reporting the real output:

- `uv run pytest`
- `uv run ruff check src tests scripts infra`

Test file names in `tests/infra/` must stay unique across `tests/` (no `__init__.py`, default import mode). `tests/test_dependencies.py` already exists, so the new dependency test is named `test_infra_dependencies.py`.

## Tasks

- [x] 1. Add the CDK dependencies and re-verify the design's open items
  - [x] 1.1 Add the infra dependency group and pytest wiring
    - Run `uv add --group infra aws-cdk-lib constructs`. Do not edit `uv.lock` by hand.
    - In `pyproject.toml` add `[tool.uv] default-groups = ["dev", "infra"]` and `[tool.pytest.ini_options] pythonpath = ["infra"]` (merge with any existing pytest section; read the file first). Do not change the runtime `dependencies` list.
    - Create `tests/infra/test_infra_dependencies.py` (read `pyproject.toml` with `tomllib`) with these tests:
      - `test_cdk_libs_only_in_infra_group`: `aws-cdk-lib` and `constructs` appear in `dependency-groups.infra` and in no other list (not in `project.dependencies`, not in `dev`). Requirement 11.1.
      - `test_runtime_dependencies_unchanged`: the names in `project.dependencies` are exactly `boto3`, `fastapi`, `itsdangerous`, `python-multipart`, `uvicorn` (the design's list). Requirement 11.2.
      - `test_infra_group_installed_by_default`: `tool.uv.default-groups` contains `infra` and `dev`, and `tool.pytest.ini_options.pythonpath` contains `infra`.
      - `test_cdk_importable`: `import aws_cdk` and `import constructs` succeed (needs Node; no AWS call).
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.
    - _Requirements: 11.1, 11.2, 11.3, 10.3_

  - [x] 1.2 Re-verify the "Still to check" items against the installed library and update the design
    - Check each of the six items in the design section "Still to check against the installed `aws-cdk-lib` once `uv add` has run" against `.venv/lib/python3.12/site-packages/aws_cdk/` and `uv run python -c "help(...)"`. Record the installed `aws-cdk-lib` version from `uv.lock`.
      1. `lambda_.Function` has a `log_group` parameter and what it accepts.
      2. `cloud_watch_role=False` with the `disableCloudWatchRole` flag leaves no `AWS::ApiGateway::Account` (use an in-memory synth in a throwaway script outside the repo, for example in `/tmp`; no CLI, no AWS call).
      3. Each flag in the planned `cdk.json` context exists in the installed library. Take the flag list from `cdk init app --language python --generate-only` run in `/tmp`, minus `watch`.
      4. Whether `"notices": false` in `cdk.json` is honored (use `cdk synth` only, offline, with `CDK_DISABLE_CLI_TELEMETRY=true`).
      5. `uv run python app.py` started from `infra/` finds the root `pyproject.toml` and the `infra` group.
      6. Defer the "no standalone 12-digit run and no helper Lambda" check to task 5.1 and note that in the design.
    - Also confirm `cdk.App(outdir=...)`, `app.synth()`, the `aws_cdk.assertions` names (`Template.from_stack`, `has_resource_properties`, `resource_count_is`, `find_resources`, `Match.object_like`, `Match.array_with`, `Match.absent`, `Match.any_value`), and the pytest `pythonpath` key, as the design lists.
    - Update `.kiro/specs/cdk-stack/design.md` with every difference found, replace the "Still to check" list with the verified results, then run `validate_spec_format` on it. If nothing differs, add the confirmed version numbers only.
    - No test file. Verification output is reported in the task result. Run `uv run pytest` and `uv run ruff check src tests scripts infra`.
    - _Requirements: 9.1, 9.5, 10.1_

- [x] 2. Build the pure scanner helpers
  - [x] 2.1 Create `tests/infra/scanners.py` and `tests/infra/test_scanners.py` (example tests)
    - `scanners.py` holds pure functions with type hints, using the patterns in the design's Data Models section. Proposed names (implementer may adjust and keep the tests consistent):
      - `find_account_ids(text: str) -> list[str]`: regex `(?<![0-9A-Za-z])\d{12}(?![0-9A-Za-z])`.
      - `find_access_keys(text: str) -> list[str]`: `(?<![0-9A-Za-z])(AKIA|ASIA)[0-9A-Z]{16}` (left boundary only, as the design says).
      - `find_private_key_headers(text: str) -> list[str]`.
      - `find_secret_assignments(source: str) -> list[str]`: literal-string assignments to names containing `password`, `secret`, or `token`, case-insensitive.
      - `find_secret_env_names(env: Mapping[str, object]) -> list[str]`: names containing `PASSWORD`, `SECRET`, or `TOKEN`, case-insensitive.
      - `find_policy_wildcards(document: Mapping, allowed_resources: Sequence[str] = ()) -> list[str]`: statements whose `Action` list contains exactly `*`, or whose `Resource` is `*` and not in the allow list.
    - `test_scanners.py` example tests (synthetic strings only):
      - `test_account_id_flags_standalone_12_digits`: `"arn:aws:iam::123456789012:root"` gives one finding `123456789012`.
      - `test_account_id_ignores_11_and_13_digit_runs`: `"12345678901"` and `"1234567890123"` give no finding.
      - `test_account_id_ignores_hex_hash_and_pseudo_parameter`: a 64-character hex string and `"AWS::AccountId"` give no finding.
      - `test_access_key_detected`: `"x AKIA" + "A"*16` and the `ASIA` form give one finding each. `"AKIA" + "A"*15` gives none.
      - `test_private_key_header_detected`: `"-----BEGIN RSA PRIVATE KEY-----"` gives a finding. `"-----BEGIN CERTIFICATE-----"` gives none.
      - `test_secret_assignment_detected`: `db_password = "abc"` and `API_TOKEN = 'x'` give findings. `password = os.environ["X"]` and `secret = make()` give none.
      - `test_secret_env_names`: `{"TICKETS_TABLE": "a", "KB_BUCKET": "b"}` gives `[]`. `{"db_password": "x", "My_Token": "y"}` gives both names.
      - `test_policy_wildcard_action_flagged`: a statement with `Action: "*"` is reported. `s3:*` and `dynamodb:Get*` are not.
      - `test_policy_wildcard_resource_rules`: `Resource: "*"` is reported when the allow list is empty and not reported when it names that statement. A document with no statements, or no wildcard, gives `[]`.
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.
    - _Requirements: 2.6, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x]* 2.2 Write property test for the account-ID scanner
    - In `tests/infra/test_scanners.py`, add `test_property_account_id_detected_exactly` with Hypothesis (`max_examples=100` or more) and the comment `# Feature: cdk-stack, Property 1: Standalone 12-digit runs are detected exactly`.
    - Build strings from text segments and a digit run of generated length `n` placed between characters from alphanumeric and non-alphanumeric sets. Assert a finding exists if and only if a maximal digit run of exactly 12 has non-alphanumeric neighbors (or string edges). Runs of 11 or 13 digits and 12-digit runs touching a letter or digit give no finding. Strings with no digits give none.
    - **Property 1: Standalone 12-digit runs are detected exactly**
    - **Validates: Requirements 8.1, 8.2, 8.5**
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.

  - [x]* 2.3 Write property test for credential patterns
    - Add `test_property_credential_patterns` with the comment `# Feature: cdk-stack, Property 2: Credential patterns are detected and near-misses are not`.
    - Assert: `AKIA` or `ASIA` plus 16 uppercase letters or digits, preceded by a non-alphanumeric character, is reported. The same prefixes with 15 or fewer characters, or any other four-letter prefix, are not reported as keys. Any text with `-----BEGIN ... PRIVATE KEY` is reported. A line assigning a non-empty string literal to a name containing `password`, `secret`, or `token` (any case) is reported, and assigning a call or name is not.
    - **Property 2: Credential patterns are detected and near-misses are not**
    - **Validates: Requirements 8.3, 8.4, 8.5**
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.

  - [x]* 2.4 Write property test for secret-like environment variable names
    - Add `test_property_secret_env_names` with the comment `# Feature: cdk-stack, Property 3: Secret-like environment variable names are rejected`.
    - Assert: for any generated name, it is flagged if and only if it contains `PASSWORD`, `SECRET`, or `TOKEN` in any letter case. For any generated mapping, the result is exactly the flagged names.
    - **Property 3: Secret-like environment variable names are rejected**
    - **Validates: Requirements 2.6, 8.3**
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.

  - [x]* 2.5 Write property test for the IAM wildcard checker
    - Add `test_property_policy_wildcards` with the comment `# Feature: cdk-stack, Property 4: Wildcard actions and unlisted wildcard resources are detected`.
    - Generate policy documents (statements with arbitrary action lists and resource values, either possibly `*`) and allow lists. Assert every statement with the exact action `*` is reported, every statement whose `Resource` is `*` (alone or in a list) and not allowed is reported, nothing is reported for documents without these, and `s3:*` or `dynamodb:Get*` are not reported by the action check.
    - **Property 4: Wildcard actions and unlisted wildcard resources are detected**
    - **Validates: Requirements 7.4, 7.5**
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.

- [x] 3. Create the CDK app skeleton
  - [x] 3.1 Add `infra/` entry point, factory, empty stack, `cdk.json`, `.gitignore` entry, and fixtures
    - Read each existing file before editing. Create `infra/app.py` (calls `create_app().synth()`, no exception handling), `infra/cdk.json` (`app` is `uv run python app.py`, `"notices": false`, `context` with `"cli-telemetry": false`, `"@aws-cdk/aws-apigateway:disableCloudWatchRole": true`, and the other flags from `cdk init`, no `account`, no `watch`), `infra/smart_copilot_infra/__init__.py`, `factory.py` (`create_app(outdir: str | None = None) -> cdk.App`, builds `SmartCopilotStack(app, "SmartCopilotStack", env=cdk.Environment(region="us-east-1"))`), and `stack.py` with an empty `SmartCopilotStack(cdk.Stack)` and its `__init__` type hints.
    - Append `infra/cdk.out/` to `.gitignore`.
    - Create `tests/infra/conftest.py` with a module-scoped fixture that calls `create_app(outdir=<tmp dir>)`, and returns the stack and `Template.from_stack(stack)`. Confirm the two `conftest.py` files (root `tests/` and `tests/infra/`) coexist under the default import mode.
    - Create `tests/infra/test_infra_app.py` with these tests:
      - `test_infra_files_exist`: `infra/app.py`, `infra/cdk.json`, and `infra/smart_copilot_infra/stack.py` exist. Requirement 1.1.
      - `test_synth_has_exactly_one_stack_artifact`: the cloud assembly from `app.synth()` has exactly 1 stack artifact. Requirement 1.2.
      - `test_stack_region_is_us_east_1`: the stack artifact environment is `aws://unknown-account/us-east-1` and `stack.region == "us-east-1"`. Requirement 1.3.
      - `test_stack_account_is_token`: `stack.account` is unresolved, and the resolved value contains `AWS::AccountId` and is not 12 digits. Requirement 1.4.
      - `test_cdk_json_settings`: `infra/cdk.json` parses, `app == "uv run python app.py"`, `notices is False`, `context["cli-telemetry"] is False`, `context["@aws-cdk/aws-apigateway:disableCloudWatchRole"] is True`, and no context key is named `account`. Requirements 9.5, 8.5.
      - `test_gitignore_lists_cdk_out`: `.gitignore` has a line `infra/cdk.out/`. Requirement 9.4.
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 8.5, 9.4, 9.5, 10.1_

- [x] 4. Define the stack resources
  - [x] 4.1 Add the DynamoDB table and S3 bucket to `stack.py`
    - Use `dynamodb.Table` (not `TableV2`) with construct id `TicketsTable`: partition key `id` string, `PAY_PER_REQUEST`, `point_in_time_recovery_specification=PointInTimeRecoverySpecification(point_in_time_recovery_enabled=True)`, `RemovalPolicy.RETAIN`, no `table_name`.
    - Use `s3.Bucket` with id `KnowledgeBaseBucket`: `BlockPublicAccess.BLOCK_ALL`, `enforce_ssl=True`, `S3_MANAGED` encryption, `versioned=True`, `RETAIN`, no `bucket_name`, no `auto_delete_objects`.
    - Create `tests/infra/test_stack.py` with:
      - `test_table_resource_count_and_key_schema`: `resource_count_is("AWS::DynamoDB::Table", 1)`, `KeySchema == [{"AttributeName": "id", "KeyType": "HASH"}]`, and `AttributeDefinitions` holds `id` with type `S`. Requirements 4.1, 4.2.
      - `test_table_billing_and_pitr`: `BillingMode == "PAY_PER_REQUEST"`, `ProvisionedThroughput` absent, and `PointInTimeRecoverySpecification.PointInTimeRecoveryEnabled is True`. Requirements 4.3, 4.4.
      - `test_table_retained`: `DeletionPolicy == "Retain"` and `UpdateReplacePolicy == "Retain"`. Requirement 4.5.
      - `test_bucket_count_and_public_access_block`: one `AWS::S3::Bucket`, with `BlockPublicAcls`, `BlockPublicPolicy`, `IgnorePublicAcls`, and `RestrictPublicBuckets` all `True`. Requirements 5.1, 5.2.
      - `test_bucket_ssl_deny_policy`: an `AWS::S3::BucketPolicy` has a statement with `Effect == "Deny"`, `Principal == {"AWS": "*"}` (how CloudFormation spells the anonymous principal, per the design), and `Condition == {"Bool": {"aws:SecureTransport": "false"}}`. Requirement 5.3.
      - `test_bucket_encryption_versioning_retain`: at least one `ServerSideEncryptionByDefault.SSEAlgorithm` (`AES256`), `VersioningConfiguration.Status == "Enabled"`, and `Retain` on both policy attributes. Requirements 5.4, 5.5, 5.6.
      - Each assertion message names its requirement.
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 4.2 Add the Cognito user pool and app client to `stack.py`
    - `cognito.UserPool` id `UserPool`: `self_sign_up_enabled=False`, `sign_in_aliases=SignInAliases(username=True)`, password policy min length 12 with lowercase, uppercase, digits, symbols, `RETAIN`. Add the client with `user_pool.add_client("AppClient", generate_secret=False, auth_flows=cognito.AuthFlow(user_srp=True), disable_o_auth=True)`. No user, no group, no domain.
    - Add to `tests/infra/test_stack.py`:
      - `test_user_pool_count_and_admin_only`: one `AWS::Cognito::UserPool` and `AdminCreateUserConfig.AllowAdminCreateUserOnly is True`. Requirements 6.1, 6.2.
      - `test_user_pool_username_sign_in_and_password_length`: `UsernameAttributes` and `AliasAttributes` absent, `Policies.PasswordPolicy.MinimumLength == 12`. Requirements 6.3, 6.4.
      - `test_user_pool_retained`: both policy attributes `Retain`. Requirement 6.5.
      - `test_app_client_attached_without_secret`: one `AWS::Cognito::UserPoolClient`, `UserPoolId` is a `Ref` to the pool's logical ID, `GenerateSecret` is `False` or absent, `ExplicitAuthFlows` contains `ALLOW_USER_SRP_AUTH` and not `ALLOW_USER_PASSWORD_AUTH`, and `AllowedOAuthFlowsUserPoolClient` is not `True`. Requirements 6.6, 6.7.
      - `test_no_user_pool_users`: `resource_count_is("AWS::Cognito::UserPoolUser", 0)`. Requirement 6.8.
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [x] 4.3 Add the Lambda function and its log group to `stack.py`
    - `aws_lambda.Function` id `AppFunction`: `Runtime.PYTHON_3_12`, `Code.from_asset(str(SRC_DIR), exclude=["**/__pycache__", "**/*.pyc"])` with `SRC_DIR = Path(__file__).resolve().parents[2] / "src"`, `handler="smart_copilot.lambda_handler.handler"` (the module does not exist and must not be added), `memory_size=512`, `timeout=Duration.seconds(30)`, `environment` of exactly `TICKETS_TABLE` and `KB_BUCKET`, and an explicit `logs.LogGroup` id `AppFunctionLogGroup` (`ONE_MONTH`, `DESTROY`) passed as `log_group` (use the form confirmed in task 1.2). No `logRetention`, no helper function.
    - Add to `tests/infra/test_stack.py`:
      - `test_single_lambda_function_no_helpers`: `resource_count_is("AWS::Lambda::Function", 1)`. Requirement 2.1.
      - `test_lambda_runtime_and_handler`: `Runtime == "python3.12"`, `Handler == "smart_copilot.lambda_handler.handler"`. Requirements 2.2, 2.3.
      - `test_lambda_memory_and_timeout_explicit`: `MemorySize` is an int in 128..10240 and `Timeout` an int in 1..900 (design values 512 and 30). Requirement 2.4.
      - `test_lambda_environment_refs`: `Environment.Variables` keys are exactly `{"TICKETS_TABLE", "KB_BUCKET"}`, with `TICKETS_TABLE == {"Ref": <table logical ID>}` and `KB_BUCKET == {"Ref": <bucket logical ID>}`, where the IDs are found by type through `find_resources`. Requirement 2.5.
      - `test_lambda_environment_has_no_secret_names`: `find_secret_env_names` on the variables returns `[]`. Requirement 2.6.
      - `test_lambda_log_group_has_finite_retention`: an `AWS::Logs::LogGroup` with `RetentionInDays == 30` exists. Design, Lambda section.
      - Do not pin the asset hash.
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 4.4 Add the REST API with access logs and throttling to `stack.py`
    - `apigateway.LambdaRestApi` id `Api` with `handler=fn`, `cloud_watch_role=False`, and `StageOptions`: `access_log_destination=LogGroupLogDestination(api_log_group)`, `access_log_format=AccessLogFormat.json_with_standard_fields(caller=False, http_method=True, ip=False, protocol=True, request_time=True, resource_path=True, response_length=True, status=True, user=False)`, `throttling_rate_limit=10`, `throttling_burst_limit=20`. Log group id `ApiAccessLogs` (`ONE_MONTH`, `DESTROY`). No authorizer.
    - Add to `tests/infra/test_stack.py`:
      - `test_single_rest_api_and_no_http_api`: `resource_count_is("AWS::ApiGateway::RestApi", 1)` and `resource_count_is("AWS::ApiGatewayV2::Api", 0)`. Requirement 3.1.
      - `test_api_proxies_to_lambda`: a `AWS::ApiGateway::Method` has `Integration.Type == "AWS_PROXY"` with a `Uri` that references the function's logical ID, and an `AWS::Lambda::Permission` has `Principal == "apigateway.amazonaws.com"` for the function. Requirement 3.2.
      - `test_stage_access_log_destination`: the `AWS::ApiGateway::Stage` `AccessLogSetting.DestinationArn` is an `Fn::GetAtt` on the logical ID of an existing `AWS::Logs::LogGroup`. Requirement 3.3.
      - `test_stage_throttling_limits`: `MethodSettings` has `ThrottlingRateLimit == 10` and `ThrottlingBurstLimit == 20`, both greater than 0, burst at least rate. Requirement 3.4.
      - `test_no_authorizer_and_no_api_gateway_account`: zero `AWS::ApiGateway::Authorizer` and zero `AWS::ApiGateway::Account`. Requirement 7.3 and the BRD decision.
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 7.3_

  - [x] 4.5 Add the least-privilege grants to `stack.py`
    - Call `table.grant_read_write_data(fn)` and `bucket.grant_read(fn)` only. No `add_to_role_policy`, no `initial_policy`.
    - Add to `tests/infra/test_stack.py`:
      - `test_dynamodb_statements_scoped_to_table`: collect the DynamoDB statements of the `AWS::IAM::Policy` for the function role (accept one or more, per the design). Every action starts with `dynamodb:`, every resource is the table's `Fn::GetAtt` Arn (or an `/index/*` `Fn::Join` on it), and the combined actions include a read action (`dynamodb:GetItem`) and a write action (`dynamodb:PutItem`). Requirement 7.1.
      - `test_s3_statement_read_only_and_scoped`: the S3 statement actions are exactly `s3:GetObject*`, `s3:GetBucket*`, `s3:List*`, with no `s3:Put*`, `s3:Delete*`, or `s3:*`, and resources are the bucket ARN and the bucket ARN joined with `/*`. Requirement 7.2.
      - `test_function_role_has_only_expected_policies`: the function's policy has no statements besides the two groups above. The role's `ManagedPolicyArns` has one entry ending in `AWSLambdaBasicExecutionRole`. There is exactly one `AWS::IAM::Role` and no `AWS::IAM::ManagedPolicy`. Requirement 7.3.
      - `test_no_wildcard_action_or_unlisted_wildcard_resource`: `find_policy_wildcards` over every `AWS::IAM::Policy`, `AWS::IAM::ManagedPolicy`, and `AWS::IAM::Role` policy document returns `[]`, with an empty exception list (the design's Wildcard_Resource_Exception list is empty). Requirements 7.4, 7.5.
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 5. Check the template and sources for account IDs and secrets
  - [x] 5.1 Add the account-ID and secret tests
    - Add to `tests/infra/test_stack.py` (using `scanners.py`):
      - `test_template_has_no_account_id`: `find_account_ids(json.dumps(template.to_json()))` is `[]`. Requirement 8.1.
      - `test_template_has_no_credentials`: `find_access_keys` and `find_private_key_headers` on the dumped template are `[]`, and `resource_count_is("AWS::SecretsManager::Secret", 0)`. Requirement 8.3.
      - `test_infra_sources_have_no_account_id_or_secret`: for every `.py` and `.json` file under `infra/` (skipping `cdk.out/`), `find_account_ids`, `find_access_keys`, `find_private_key_headers`, and `find_secret_assignments` return `[]`. The message names the file. Requirements 8.2, 8.4.
      - `test_cdk_json_has_no_account_or_secret`: the same scanners return `[]` on `infra/cdk.json`, and there is no context key named `account`. Requirement 8.5.
      - `test_template_has_no_helper_functions_or_metadata`: exactly one `AWS::Lambda::Function`, zero `Custom::*` resources, and no `AWS::CDK::Metadata` resource in the in-memory template. This closes item 6 of the design's "Still to check" list; update `design.md` if the result differs.
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 10.4, 10.5_

- [x] 6. Update the steering rules
  - [x] 6.1 Edit the four steering files and add the steering test
    - Read each file first. Make only the edits listed in the design's "Steering Rule Updates" section: `.kiro/steering/tech.md` (3 edits), `.kiro/steering/verify-first.md` (3 edits), `.kiro/steering/product.md` (1 edit), `.kiro/steering/structure.md` (add the `infra/` layout line). Leave every other line unchanged.
    - Create `tests/infra/test_steering_rules.py`, reading the files from `.kiro/steering/` (synthetic text only, no AWS):
      - `test_cdk_allowed_for_synth_and_template_tests_only`: `tech.md` and `verify-first.md` each contain the phrase `A CDK app in \`infra/\` is allowed for \`cdk synth\` and template tests only`. Requirement 12.1.
      - `test_account_commands_forbidden`: `tech.md` and `verify-first.md` each contain `cdk deploy`, `cdk bootstrap`, `cdk destroy`, and `cdk diff` against an account, together with the words `stay forbidden without the user's approval`. Requirement 12.2.
      - `test_sam_terraform_slides_forbidden`: `tech.md` contains `No SAM, Terraform, deploy steps, or slides.` and `verify-first.md` contains `Do not add SAM, Terraform, deploy steps, or slides.` Neither still contains the old text `No CDK, SAM` or `Do not add CDK, SAM`. Requirement 12.3.
      - `test_cognito_allowed_for_infrastructure_definitions_only`: `tech.md` and `verify-first.md` contain `Amazon Cognito (infrastructure definitions only)`. `product.md` contains `Cognito is allowed for infrastructure definitions only`. Requirement 12.4.
      - `test_structure_lists_infra`: `structure.md` contains a layout line starting with `├── infra/` and mentioning `CDK app`. Requirement 12.5.
      - `test_unrelated_rules_unchanged`: key unchanged lines still exist, for example `Bedrock is the only model API` in `tech.md`, and the `user login` bullet in `product.md`. Requirement 12.6.
    - Run `uv run pytest` and `uv run ruff check src tests scripts infra`.
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

- [x] 7. Final checkpoint - Verify everything and prove the app is unchanged
  - Run each command below and report the real output. If any command fails or cannot run, do not report the work as done; state the failing command and its output (Requirement 13.5).
    - `uv run pytest` (exit code 0, not 5)
    - `uv run ruff check src tests scripts infra`
    - `uv run check` (runs ruff, gitleaks, and semgrep; if a tool is missing, report it as not run)
    - From `infra/`: `CDK_DISABLE_CLI_TELEMETRY=true cdk synth --no-version-reporting --no-notices` (exit code 0, one template file in `infra/cdk.out/`, and no AWS credentials needed)
    - `git status --short` shows nothing under `infra/cdk.out/`.
    - `git diff --exit-code main -- src/smart_copilot/` (exit code 0, which shows the app is unchanged)
  - Confirm no existing test was deleted, skipped, or weakened, and that no Account_Command was run.
  - Do not commit. Tell the user the work is ready for review on `feat/cdk-stack`.
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 10.3, 13.1, 13.2, 13.3, 13.4, 13.5_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP.
- Each task references specific requirements for traceability.
- Property tests cover only the pure scanners (Properties 1 to 4). The template checks are example tests, as the design states.
- Tasks 4.1 to 4.5 and 5.1 all edit `tests/infra/test_stack.py`, and 4.1 to 4.5 all edit `stack.py`, so they run in separate waves.
- This workflow only creates the plan. To run it, open `tasks.md` and click "Start task" next to a task item.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "3.1", "6.1"] },
    { "id": 3, "tasks": ["2.2", "4.1"] },
    { "id": 4, "tasks": ["2.3", "4.2"] },
    { "id": 5, "tasks": ["2.4", "4.3"] },
    { "id": 6, "tasks": ["2.5", "4.4"] },
    { "id": 7, "tasks": ["4.5"] },
    { "id": 8, "tasks": ["5.1"] }
  ]
}
```
