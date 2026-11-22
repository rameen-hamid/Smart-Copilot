"""One stack: Lambda, REST API, DynamoDB tickets table, S3 knowledge-base bucket, Cognito.

Synth and template tests only. The handler module does not exist yet, so a deployed
function would fail. Do not deploy this stack.
"""

from pathlib import Path
from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
HANDLER = "smart_copilot.lambda_handler.handler"  # implemented by a later spec


class SmartCopilotStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        table = dynamodb.Table(
            self,
            "TicketsTable",
            partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        bucket = s3.Bucket(
            self,
            "KnowledgeBaseBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        user_pool = cognito.UserPool(
            self,
            "UserPool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        user_pool.add_client(
            "AppClient",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_srp=True),
            disable_o_auth=True,
        )

        function_logs = logs.LogGroup(
            self,
            "AppFunctionLogGroup",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        function = lambda_.Function(
            self,
            "AppFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset(
                str(SRC_DIR), exclude=["**/__pycache__", "**/*.pyc"]
            ),
            handler=HANDLER,
            memory_size=512,
            timeout=cdk.Duration.seconds(30),
            environment={
                "TICKETS_TABLE": table.table_name,
                "KB_BUCKET": bucket.bucket_name,
            },
            log_group=function_logs,
        )

        api_logs = logs.LogGroup(
            self,
            "ApiAccessLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        apigateway.LambdaRestApi(
            self,
            "Api",
            handler=function,
            cloud_watch_role=False,
            deploy_options=apigateway.StageOptions(
                access_log_destination=apigateway.LogGroupLogDestination(api_logs),
                # No caller, IP, or user fields, so access logs hold no personal data.
                access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                    caller=False,
                    http_method=True,
                    ip=False,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=False,
                ),
                throttling_rate_limit=10,
                throttling_burst_limit=20,
            ),
        )

        table.grant_read_write_data(function)
        bucket.grant_read(function)
