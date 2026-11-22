"""CDK entry point. Run `cdk synth` from infra/. Never deploy from this project."""

from smart_copilot_infra.factory import create_app

create_app().synth()
