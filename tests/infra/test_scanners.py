import re
import string

from hypothesis import given, settings
from hypothesis import strategies as st
from scanners import (
    find_access_keys,
    find_account_ids,
    find_policy_wildcards,
    find_private_key_headers,
    find_secret_assignments,
    find_secret_env_names,
)

# Synthetic values only. 123456789012 is the placeholder account ID used in AWS docs.
FAKE_ACCOUNT = "123456789012"


def test_account_id_flags_standalone_12_digits() -> None:
    assert find_account_ids(f"arn:aws:iam::{FAKE_ACCOUNT}:root") == [FAKE_ACCOUNT]


def test_account_id_ignores_11_and_13_digit_runs() -> None:
    assert find_account_ids("12345678901") == []
    assert find_account_ids("1234567890123") == []


def test_account_id_ignores_hex_hash_and_pseudo_parameter() -> None:
    assert find_account_ids("a" + "1" * 12 + "b" + "0f" * 25) == []
    assert find_account_ids("{'Ref': 'AWS::AccountId'}") == []


def test_access_key_detected() -> None:
    assert len(find_access_keys("x AKIA" + "A" * 16)) == 1
    assert len(find_access_keys("x ASIA" + "B" * 16)) == 1
    assert find_access_keys("x AKIA" + "A" * 15) == []
    assert find_access_keys("xAKIA" + "A" * 16) == []


def test_private_key_header_detected() -> None:
    # Built at runtime so the source holds no complete key header for gitleaks to flag.
    begin = "-----BEGIN "
    assert find_private_key_headers(begin + "RSA PRIVATE KEY-----")
    assert find_private_key_headers(begin + "PRIVATE KEY-----")
    assert find_private_key_headers("-----BEGIN CERTIFICATE-----") == []


def test_secret_assignment_detected() -> None:
    assert find_secret_assignments('db_password = "abc"')
    assert find_secret_assignments("API_TOKEN = 'x'")
    assert find_secret_assignments('password = os.environ["X"]') == []
    assert find_secret_assignments("secret = make()") == []


def test_secret_env_names() -> None:
    assert find_secret_env_names({"TICKETS_TABLE": "a", "KB_BUCKET": "b"}) == []
    assert find_secret_env_names({"db_password": "x", "My_Token": "y"}) == [
        "db_password",
        "My_Token",
    ]


def test_policy_wildcard_action_flagged() -> None:
    assert find_policy_wildcards({"Statement": [{"Action": "*", "Resource": "arn:x"}]})
    assert find_policy_wildcards({"Statement": [{"Action": ["s3:*"], "Resource": "a"}]}) == []
    assert find_policy_wildcards({"Statement": [{"Action": "dynamodb:Get*"}]}) == []


def test_policy_wildcard_resource_rules() -> None:
    document = {"Statement": [{"Sid": "Logs", "Action": "logs:PutLogEvents", "Resource": "*"}]}
    assert find_policy_wildcards(document) == ["statement Logs: resource *"]
    assert find_policy_wildcards(document, allowed_resources=["Logs"]) == []
    assert find_policy_wildcards({}) == []
    assert find_policy_wildcards({"Statement": [{"Action": "s3:GetObject"}]}) == []


# Property-based tests

ALNUM = string.ascii_letters + string.digits
SEPARATORS = ":/-_. \"'{}[]"
_digit_run = re.compile(r"\d+")


def _expected_account_ids(text: str) -> list[str]:
    found = []
    for match in _digit_run.finditer(text):
        before = text[match.start() - 1] if match.start() else ""
        after = text[match.end()] if match.end() < len(text) else ""
        if len(match.group()) == 12 and not (before.isalpha() or after.isalpha()):
            found.append(match.group())
    return found


# Feature: cdk-stack, Property 1: Standalone 12-digit runs are detected exactly
@settings(max_examples=200)
@given(
    prefix=st.text(alphabet=ALNUM + SEPARATORS, max_size=10),
    left=st.sampled_from(["", *SEPARATORS, "a", "Z"]),
    length=st.integers(min_value=1, max_value=16),
    right=st.sampled_from(["", *SEPARATORS, "b", "Y"]),
    suffix=st.text(alphabet=string.ascii_letters + SEPARATORS, max_size=10),
)
def test_property_account_id_detected_exactly(
    prefix: str, left: str, length: int, right: str, suffix: str
) -> None:
    text = prefix + left + "7" * length + right + suffix
    assert find_account_ids(text) == _expected_account_ids(text)


# Feature: cdk-stack, Property 2: Credential patterns are detected and near-misses are not
@settings(max_examples=200)
@given(
    prefix=st.sampled_from(["AKIA", "ASIA", "AKIB", "ABCD"]),
    body=st.text(alphabet=string.ascii_uppercase + string.digits, min_size=0, max_size=20),
    lead=st.sampled_from([" ", ":", "\"", ""]),
    name=st.sampled_from(["password", "DB_SECRET", "apiToken", "username", "region"]),
    literal=st.booleans(),
)
def test_property_credential_patterns(
    prefix: str, body: str, lead: str, name: str, literal: bool
) -> None:
    key_hits = find_access_keys(lead + prefix + body)
    assert bool(key_hits) == (prefix in ("AKIA", "ASIA") and len(body) >= 16)
    assert find_private_key_headers(f"x -----BEGIN {body[:0]}PRIVATE KEY----- y")
    line = f'{name} = "value-x"' if literal else f"{name} = load()"
    secret_like = any(p in name.lower() for p in ("password", "secret", "token"))
    assert bool(find_secret_assignments(line)) == (secret_like and literal)


# Feature: cdk-stack, Property 3: Secret-like environment variable names are rejected
@settings(max_examples=200)
@given(st.dictionaries(st.text(alphabet=string.ascii_letters + "_", max_size=20), st.text()))
def test_property_secret_env_names(env: dict[str, str]) -> None:
    expected = [
        n for n in env if any(p in n.upper() for p in ("PASSWORD", "SECRET", "TOKEN"))
    ]
    assert find_secret_env_names(env) == expected


_actions = st.one_of(
    st.just("*"), st.sampled_from(["s3:*", "s3:GetObject", "dynamodb:Get*", "logs:*"])
)
_resources = st.one_of(st.just("*"), st.sampled_from(["arn:aws:s3:::b", "arn:aws:s3:::b/*"]))


# Feature: cdk-stack, Property 4: Wildcard actions and unlisted wildcard resources are detected
@settings(max_examples=200)
@given(
    statements=st.lists(
        st.fixed_dictionaries(
            {
                "Action": st.one_of(_actions, st.lists(_actions, max_size=3)),
                "Resource": st.one_of(_resources, st.lists(_resources, max_size=3)),
            }
        ),
        max_size=5,
    ),
    allowed=st.lists(st.sampled_from(["0", "1", "2"]), max_size=3),
)
def test_property_policy_wildcards(statements: list[dict], allowed: list[str]) -> None:
    findings = find_policy_wildcards({"Statement": statements}, allowed_resources=allowed)
    for i, s in enumerate(statements):
        actions = s["Action"] if isinstance(s["Action"], list) else [s["Action"]]
        resources = s["Resource"] if isinstance(s["Resource"], list) else [s["Resource"]]
        assert (f"statement {i}: action *" in findings) == ("*" in actions)
        assert (f"statement {i}: resource *" in findings) == (
            "*" in resources and str(i) not in allowed
        )
