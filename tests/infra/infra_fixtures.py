"""Shared fixtures for the infra tests: the CDK stack built in memory once per module.

Not named conftest.py, because tests/conftest.py already uses that module name.
No network or AWS calls.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template
from smart_copilot_infra.factory import STACK_ID, create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA_DIR = REPO_ROOT / "infra"


@pytest.fixture(scope="module", name="synthesized")
def synthesized_fixture(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    outdir = tmp_path_factory.mktemp("cdk.out")
    app = create_app(outdir=str(outdir))
    assembly = app.synth()
    stack = app.node.find_child(STACK_ID)
    assert isinstance(stack, cdk.Stack)
    yield {"app": app, "assembly": assembly, "stack": stack}


@pytest.fixture(scope="module", name="template")
def template_fixture(synthesized: dict[str, Any]) -> Template:
    return Template.from_stack(synthesized["stack"])


@pytest.fixture(scope="module", name="resources")
def resources_fixture(template: Template) -> dict[str, dict[str, Any]]:
    return template.to_json()["Resources"]


def logical_id(resources: dict[str, dict[str, Any]], resource_type: str) -> str:
    """The single logical ID of a resource type. Fails if there is not exactly one."""
    ids = [k for k, v in resources.items() if v["Type"] == resource_type]
    assert len(ids) == 1, f"expected one {resource_type}, found {len(ids)}"
    return ids[0]
