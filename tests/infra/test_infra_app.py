import json
from pathlib import Path
from typing import Any

import aws_cdk as cdk
import pytest

# The *_fixture imports register pytest fixtures named synthesized, template, resources.
from infra_fixtures import INFRA_DIR, REPO_ROOT, synthesized_fixture  # noqa: F401
from scanners import find_account_ids
from smart_copilot_infra.factory import STACK_ID, create_app


def test_infra_files_exist() -> None:
    for name in ("app.py", "cdk.json", "smart_copilot_infra/stack.py"):
        assert (INFRA_DIR / name).is_file(), f"Requirement 1.1: missing infra/{name}"


def test_synth_has_exactly_one_stack_artifact(synthesized: dict[str, Any]) -> None:
    assert len(synthesized["assembly"].stacks) == 1, "Requirement 1.2"


def test_stack_region_is_us_east_1(synthesized: dict[str, Any]) -> None:
    artifact = synthesized["assembly"].stacks[0]
    assert artifact.environment.region == "us-east-1", "Requirement 1.3"
    assert artifact.environment.account == "unknown-account", "Requirement 1.4"
    assert synthesized["stack"].region == "us-east-1"


def test_stack_account_is_token(synthesized: dict[str, Any]) -> None:
    stack = synthesized["stack"]
    assert cdk.Token.is_unresolved(stack.account), "Requirement 1.4"
    resolved = json.dumps(stack.resolve(stack.account))
    assert "AWS::AccountId" in resolved
    assert find_account_ids(resolved) == []


def test_cli_context_cannot_turn_on_version_reporting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # `cdk synth` passes context to the app. The app must still leave out AWS::CDK::Metadata.
    monkeypatch.setenv("CDK_CONTEXT_JSON", '{"aws:cdk:version-reporting": true}')
    app = create_app(outdir=str(tmp_path))
    template = app.synth().get_stack_by_name(STACK_ID).template
    types = {r["Type"] for r in template["Resources"].values()}
    assert "AWS::CDK::Metadata" not in types, "Requirement 9.5: telemetry off"


def test_cdk_json_settings() -> None:
    config = json.loads((INFRA_DIR / "cdk.json").read_text(encoding="utf-8"))
    assert config["app"] == "uv run python app.py"
    assert config["notices"] is False
    context = config["context"]
    assert context["cli-telemetry"] is False, "Requirement 9.5"
    assert context["@aws-cdk/aws-apigateway:disableCloudWatchRole"] is True
    assert "account" not in context, "Requirement 8.5"
    assert "watch" not in config


def test_gitignore_lists_cdk_out() -> None:
    lines = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "infra/cdk.out/" in lines, "Requirement 9.4"
