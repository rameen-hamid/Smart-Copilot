import aws_cdk as cdk

from smart_copilot_infra.stack import SmartCopilotStack

STACK_ID = "SmartCopilotStack"
REGION = "us-east-1"


def create_app(outdir: str | None = None) -> cdk.App:
    """Build the app with its one stack. The environment sets the region only, no account.

    analytics_reporting=False keeps the AWS::CDK::Metadata resource (CDK usage analytics)
    out of the template, whatever flags the CLI is run with.
    """
    app = cdk.App(outdir=outdir, analytics_reporting=False)
    SmartCopilotStack(app, STACK_ID, env=cdk.Environment(region=REGION))
    return app
