"""Checks the synthesized template against requirements 2 to 8. No AWS calls."""

import json
from pathlib import Path
from typing import Any

from aws_cdk.assertions import Match, Template

# The *_fixture imports register pytest fixtures named synthesized, template, resources.
from infra_fixtures import (  # noqa: F401
    INFRA_DIR,
    logical_id,
    resources_fixture,
    synthesized_fixture,
    template_fixture,
)
from scanners import (
    find_access_keys,
    find_account_ids,
    find_policy_wildcards,
    find_private_key_headers,
    find_secret_assignments,
    find_secret_env_names,
)

Resources = dict[str, dict[str, Any]]
RETAIN = {"DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain"}
# Statements allowed to use a `*` resource (Wildcard_Resource_Exception). Empty by design.
WILDCARD_RESOURCE_EXCEPTIONS: tuple[str, ...] = ()


def _one(resources: Resources, resource_type: str) -> dict[str, Any]:
    return resources[logical_id(resources, resource_type)]


# Requirement 4: DynamoDB tickets table


def test_table_resource_count_and_key_schema(template: Template, resources: Resources) -> None:
    template.resource_count_is("AWS::DynamoDB::Table", 1)
    props = _one(resources, "AWS::DynamoDB::Table")["Properties"]
    assert props["KeySchema"] == [{"AttributeName": "id", "KeyType": "HASH"}], "4.2"
    assert props["AttributeDefinitions"] == [{"AttributeName": "id", "AttributeType": "S"}]


def test_table_billing_and_pitr(resources: Resources) -> None:
    props = _one(resources, "AWS::DynamoDB::Table")["Properties"]
    assert props["BillingMode"] == "PAY_PER_REQUEST", "4.3"
    assert "ProvisionedThroughput" not in props, "4.3"
    assert props["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is True


def test_table_retained(resources: Resources) -> None:
    table = _one(resources, "AWS::DynamoDB::Table")
    assert {k: table.get(k) for k in RETAIN} == RETAIN, "4.5"


# Requirement 5: S3 knowledge-base bucket


def test_bucket_count_and_public_access_block(template: Template, resources: Resources) -> None:
    template.resource_count_is("AWS::S3::Bucket", 1)
    block = _one(resources, "AWS::S3::Bucket")["Properties"]["PublicAccessBlockConfiguration"]
    assert block == {
        "BlockPublicAcls": True,
        "BlockPublicPolicy": True,
        "IgnorePublicAcls": True,
        "RestrictPublicBuckets": True,
    }, "5.2"


def test_bucket_ssl_deny_policy(resources: Resources) -> None:
    bucket_id = logical_id(resources, "AWS::S3::Bucket")
    policy = _one(resources, "AWS::S3::BucketPolicy")["Properties"]
    assert policy["Bucket"] == {"Ref": bucket_id}
    deny = [
        s
        for s in policy["PolicyDocument"]["Statement"]
        if s["Effect"] == "Deny"
        and s["Principal"] == {"AWS": "*"}
        and s.get("Condition") == {"Bool": {"aws:SecureTransport": "false"}}
    ]
    assert len(deny) == 1, "5.3: SSL deny statement"


def test_bucket_encryption_versioning_retain(resources: Resources) -> None:
    bucket = _one(resources, "AWS::S3::Bucket")
    rules = bucket["Properties"]["BucketEncryption"]["ServerSideEncryptionConfiguration"]
    assert rules[0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256", "5.4"
    assert bucket["Properties"]["VersioningConfiguration"] == {"Status": "Enabled"}, "5.5"
    assert {k: bucket.get(k) for k in RETAIN} == RETAIN, "5.6"


# Requirement 6: Cognito


def test_user_pool_count_and_admin_only(template: Template, resources: Resources) -> None:
    template.resource_count_is("AWS::Cognito::UserPool", 1)
    props = _one(resources, "AWS::Cognito::UserPool")["Properties"]
    assert props["AdminCreateUserConfig"]["AllowAdminCreateUserOnly"] is True, "6.2"


def test_user_pool_username_sign_in_and_password_length(resources: Resources) -> None:
    props = _one(resources, "AWS::Cognito::UserPool")["Properties"]
    assert "UsernameAttributes" not in props, "6.3"
    assert "AliasAttributes" not in props, "6.3"
    assert props["Policies"]["PasswordPolicy"]["MinimumLength"] == 12, "6.4"


def test_user_pool_retained(resources: Resources) -> None:
    pool = _one(resources, "AWS::Cognito::UserPool")
    assert {k: pool.get(k) for k in RETAIN} == RETAIN, "6.5"


def test_app_client_attached_without_secret(template: Template, resources: Resources) -> None:
    template.resource_count_is("AWS::Cognito::UserPoolClient", 1)
    pool_id = logical_id(resources, "AWS::Cognito::UserPool")
    client = _one(resources, "AWS::Cognito::UserPoolClient")["Properties"]
    assert client["UserPoolId"] == {"Ref": pool_id}, "6.6"
    assert client.get("GenerateSecret", False) is False, "6.7"
    assert "ALLOW_USER_SRP_AUTH" in client["ExplicitAuthFlows"]
    assert "ALLOW_USER_PASSWORD_AUTH" not in client["ExplicitAuthFlows"]
    assert client.get("AllowedOAuthFlowsUserPoolClient") is not True
    assert "CallbackURLs" not in client


def test_no_user_pool_users(template: Template) -> None:
    template.resource_count_is("AWS::Cognito::UserPoolUser", 0)


# Requirement 2: Lambda


def test_single_lambda_function_no_helpers(template: Template) -> None:
    template.resource_count_is("AWS::Lambda::Function", 1)


def test_lambda_runtime_and_handler(template: Template) -> None:
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"Runtime": "python3.12", "Handler": "smart_copilot.lambda_handler.handler"},
    )


def test_lambda_memory_and_timeout_explicit(resources: Resources) -> None:
    props = _one(resources, "AWS::Lambda::Function")["Properties"]
    assert isinstance(props["MemorySize"], int) and 128 <= props["MemorySize"] <= 10240
    assert isinstance(props["Timeout"], int) and 1 <= props["Timeout"] <= 900
    assert (props["MemorySize"], props["Timeout"]) == (512, 30)


def test_lambda_environment_refs(resources: Resources) -> None:
    variables = _one(resources, "AWS::Lambda::Function")["Properties"]["Environment"][
        "Variables"
    ]
    assert variables == {
        "TICKETS_TABLE": {"Ref": logical_id(resources, "AWS::DynamoDB::Table")},
        "KB_BUCKET": {"Ref": logical_id(resources, "AWS::S3::Bucket")},
    }, "2.5"


def test_lambda_environment_has_no_secret_names(resources: Resources) -> None:
    variables = _one(resources, "AWS::Lambda::Function")["Properties"]["Environment"][
        "Variables"
    ]
    assert find_secret_env_names(variables) == [], "2.6"


def test_lambda_log_group_has_finite_retention(resources: Resources) -> None:
    fn = _one(resources, "AWS::Lambda::Function")["Properties"]
    group_id = fn["LoggingConfig"]["LogGroup"]["Ref"]
    assert resources[group_id]["Properties"]["RetentionInDays"] == 30


# Requirement 3: API Gateway


def test_single_rest_api_and_no_http_api(template: Template) -> None:
    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
    template.resource_count_is("AWS::ApiGatewayV2::Api", 0)


def test_api_proxies_to_lambda(template: Template, resources: Resources) -> None:
    fn_id = logical_id(resources, "AWS::Lambda::Function")
    methods = [v for v in resources.values() if v["Type"] == "AWS::ApiGateway::Method"]
    assert methods, "3.2: no methods"
    for method in methods:
        integration = method["Properties"]["Integration"]
        assert integration["Type"] == "AWS_PROXY"
        assert fn_id in json.dumps(integration["Uri"]), "3.2: Uri must reference the function"
    template.has_resource_properties(
        "AWS::Lambda::Permission",
        {
            "Principal": "apigateway.amazonaws.com",
            "FunctionName": {"Fn::GetAtt": [fn_id, "Arn"]},
            "Action": "lambda:InvokeFunction",
        },
    )


def test_stage_access_log_destination(resources: Resources) -> None:
    stage = _one(resources, "AWS::ApiGateway::Stage")["Properties"]
    destination = stage["AccessLogSetting"]["DestinationArn"]
    group_id = destination["Fn::GetAtt"][0]
    assert resources[group_id]["Type"] == "AWS::Logs::LogGroup", "3.3"
    assert destination["Fn::GetAtt"][1] == "Arn"
    log_format = stage["AccessLogSetting"]["Format"]
    assert "$context.identity.sourceIp" not in log_format, "no client IP in access logs"


def test_stage_throttling_limits(template: Template, resources: Resources) -> None:
    template.has_resource_properties(
        "AWS::ApiGateway::Stage",
        {
            "MethodSettings": Match.array_with(
                [Match.object_like({"ThrottlingRateLimit": 10, "ThrottlingBurstLimit": 20})]
            )
        },
    )
    for setting in _one(resources, "AWS::ApiGateway::Stage")["Properties"]["MethodSettings"]:
        assert setting["ThrottlingRateLimit"] > 0
        assert setting["ThrottlingBurstLimit"] >= setting["ThrottlingRateLimit"], "3.4"


def test_no_authorizer_and_no_api_gateway_account(template: Template) -> None:
    template.resource_count_is("AWS::ApiGateway::Authorizer", 0)
    template.resource_count_is("AWS::ApiGateway::Account", 0)


# Requirement 7: least privilege


def _function_statements(resources: Resources) -> list[dict[str, Any]]:
    policy = _one(resources, "AWS::IAM::Policy")["Properties"]
    role_id = logical_id(resources, "AWS::IAM::Role")
    assert policy["Roles"] == [{"Ref": role_id}]
    return policy["PolicyDocument"]["Statement"]


def _actions(statement: dict[str, Any]) -> list[str]:
    action = statement["Action"]
    return action if isinstance(action, list) else [action]


def _resources_of(statement: dict[str, Any]) -> list[Any]:
    resource = statement["Resource"]
    return resource if isinstance(resource, list) else [resource]


def test_dynamodb_statements_scoped_to_table(resources: Resources) -> None:
    table_arn = {"Fn::GetAtt": [logical_id(resources, "AWS::DynamoDB::Table"), "Arn"]}
    statements = [
        s for s in _function_statements(resources) if _actions(s)[0].startswith("dynamodb:")
    ]
    assert statements, "7.1: no DynamoDB statement"
    actions: set[str] = set()
    for statement in statements:
        assert all(a.startswith("dynamodb:") for a in _actions(statement))
        assert _resources_of(statement) == [table_arn], "7.1: table ARN only"
        actions.update(_actions(statement))
    assert {"dynamodb:GetItem", "dynamodb:PutItem"} <= actions, "7.1: read and write"


def test_s3_statement_read_only_and_scoped(resources: Resources) -> None:
    bucket_arn = {"Fn::GetAtt": [logical_id(resources, "AWS::S3::Bucket"), "Arn"]}
    statements = [s for s in _function_statements(resources) if _actions(s)[0].startswith("s3:")]
    assert len(statements) == 1
    statement = statements[0]
    assert sorted(_actions(statement)) == ["s3:GetBucket*", "s3:GetObject*", "s3:List*"], "7.2"
    assert _resources_of(statement) == [
        bucket_arn,
        {"Fn::Join": ["", [bucket_arn, "/*"]]},
    ], "7.2"


def test_function_role_has_only_expected_policies(
    template: Template, resources: Resources
) -> None:
    for statement in _function_statements(resources):
        assert _actions(statement)[0].split(":")[0] in {"dynamodb", "s3"}, "7.3"
    template.resource_count_is("AWS::IAM::Role", 1)
    template.resource_count_is("AWS::IAM::ManagedPolicy", 0)
    managed = _one(resources, "AWS::IAM::Role")["Properties"]["ManagedPolicyArns"]
    assert len(managed) == 1
    assert json.dumps(managed[0]).endswith('service-role/AWSLambdaBasicExecutionRole"]]}')


def test_no_wildcard_action_or_unlisted_wildcard_resource(resources: Resources) -> None:
    findings: list[str] = []
    for logical, resource in resources.items():
        props = resource.get("Properties", {})
        documents = []
        if resource["Type"] in ("AWS::IAM::Policy", "AWS::IAM::ManagedPolicy"):
            documents.append(props["PolicyDocument"])
        if resource["Type"] == "AWS::IAM::Role":
            documents += [p["PolicyDocument"] for p in props.get("Policies", [])]
        for document in documents:
            findings += [
                f"{logical}: {f}"
                for f in find_policy_wildcards(document, WILDCARD_RESOURCE_EXCEPTIONS)
            ]
    assert findings == [], "7.4/7.5"


# Requirement 8: no account IDs or secrets


def test_template_has_no_account_id(template: Template) -> None:
    assert find_account_ids(json.dumps(template.to_json())) == [], "8.1"


def test_template_has_no_credentials(template: Template) -> None:
    text = json.dumps(template.to_json())
    assert find_access_keys(text) == [], "8.3"
    assert find_private_key_headers(text) == [], "8.3"
    template.resource_count_is("AWS::SecretsManager::Secret", 0)


def _infra_sources() -> list[Path]:
    return [
        p
        for p in INFRA_DIR.rglob("*")
        if p.suffix in {".py", ".json"} and "cdk.out" not in p.parts and "__pycache__" not in p.parts
    ]


def test_infra_sources_have_no_account_id_or_secret() -> None:
    sources = _infra_sources()
    assert len(sources) >= 5
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for scan in (
            find_account_ids,
            find_access_keys,
            find_private_key_headers,
            find_secret_assignments,
        ):
            assert scan(text) == [], f"8.2/8.4: {scan.__name__} found something in {path.name}"


def test_cdk_json_has_no_account_or_secret() -> None:
    text = (INFRA_DIR / "cdk.json").read_text(encoding="utf-8")
    assert find_account_ids(text) == [], "8.5"
    assert find_access_keys(text) == [], "8.5"
    assert "account" not in json.loads(text)["context"], "8.5"


def test_template_has_no_helper_functions_or_metadata(resources: Resources) -> None:
    types = [r["Type"] for r in resources.values()]
    assert types.count("AWS::Lambda::Function") == 1
    assert not [t for t in types if t.startswith("Custom::")]
    assert "AWS::CDK::Metadata" not in types
