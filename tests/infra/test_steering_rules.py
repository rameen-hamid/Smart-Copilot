from infra_fixtures import REPO_ROOT

STEERING = REPO_ROOT / ".kiro" / "steering"
CDK_ALLOWED = "A CDK app in `infra/` is allowed for `cdk synth` and template tests only."
FORBIDDEN = (
    "`cdk deploy`, `cdk bootstrap`, `cdk destroy`, `cdk diff` against an account, and every "
    "other command that reads or changes an AWS account stay forbidden without the user's "
    "approval."
)


def _read(name: str) -> str:
    return (STEERING / name).read_text(encoding="utf-8")


def test_cdk_allowed_for_synth_and_template_tests_only() -> None:
    for name in ("tech.md", "verify-first.md"):
        assert CDK_ALLOWED in _read(name), f"12.1: {name}"


def test_account_commands_forbidden() -> None:
    for name in ("tech.md", "verify-first.md"):
        assert FORBIDDEN in _read(name), f"12.2: {name}"


def test_sam_terraform_slides_forbidden() -> None:
    tech, verify = _read("tech.md"), _read("verify-first.md")
    assert "No SAM, Terraform, deploy steps, or slides." in tech, "12.3"
    assert "Do not add SAM, Terraform, deploy steps, or slides." in verify, "12.3"
    assert "No CDK, SAM" not in tech
    assert "Do not add CDK, SAM" not in verify


def test_cognito_allowed_for_infrastructure_definitions_only() -> None:
    for name in ("tech.md", "verify-first.md"):
        assert "Amazon Cognito (infrastructure definitions only)" in _read(name), f"12.4: {name}"
    assert "Cognito is allowed for infrastructure definitions only" in _read("product.md")


def test_structure_lists_infra() -> None:
    lines = _read("structure.md").splitlines()
    assert any(line.startswith("├── infra/") and "CDK app" in line for line in lines), "12.5"


def test_unrelated_rules_unchanged() -> None:
    assert "Bedrock is the only model API" in _read("tech.md"), "12.6"
    assert "Never use Amazon Comprehend, Amazon Kendra, or Amazon Lookout for Metrics." in _read(
        "verify-first.md"
    )
    assert "- Sending email, live chat, payments, user login." in _read("product.md"), "12.6"
