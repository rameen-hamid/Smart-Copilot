import importlib
import re
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _config() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _names(entries: list[str]) -> set[str]:
    return {re.split(r"[<>=!~\[ ;]", e, maxsplit=1)[0] for e in entries}


def test_cdk_libs_only_in_infra_group() -> None:
    config = _config()
    groups = config["dependency-groups"]
    assert {"aws-cdk-lib", "constructs"} <= _names(groups["infra"]), "Requirement 11.1"
    for name, entries in [("project", config["project"]["dependencies"])] + [
        (g, e) for g, e in groups.items() if g != "infra"
    ]:
        assert not {"aws-cdk-lib", "constructs"} & _names(entries), f"11.1: found in {name}"


def test_runtime_dependencies_unchanged() -> None:
    assert _names(_config()["project"]["dependencies"]) == {
        "boto3",
        "fastapi",
        "itsdangerous",
        "python-multipart",
        "uvicorn",
    }, "Requirement 11.2"


def test_infra_group_installed_by_default() -> None:
    config = _config()
    assert {"dev", "infra"} <= set(config["tool"]["uv"]["default-groups"])
    assert "infra" in config["tool"]["pytest"]["ini_options"]["pythonpath"]


def test_cdk_importable() -> None:
    assert importlib.import_module("aws_cdk")
    assert importlib.import_module("constructs")
