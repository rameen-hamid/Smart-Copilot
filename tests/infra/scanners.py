"""Pure text scanners for account IDs, credentials, and IAM wildcards.

Findings are returned as lists. Callers report where a finding is, never its full value.
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any

ACCOUNT_ID_RE = re.compile(r"(?<![0-9A-Za-z])\d{12}(?![0-9A-Za-z])")
ACCESS_KEY_RE = re.compile(r"(?<![0-9A-Za-z])(?:AKIA|ASIA)[0-9A-Z]{16}")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b\w*(?:password|secret|token)\w*\s*=\s*[\"'][^\"'\n]+[\"']"
)
SECRET_NAME_PARTS = ("PASSWORD", "SECRET", "TOKEN")


def find_account_ids(text: str) -> list[str]:
    return ACCOUNT_ID_RE.findall(text)


def find_access_keys(text: str) -> list[str]:
    return ACCESS_KEY_RE.findall(text)


def find_private_key_headers(text: str) -> list[str]:
    return PRIVATE_KEY_RE.findall(text)


def find_secret_assignments(source: str) -> list[str]:
    return [m.group(0) for m in SECRET_ASSIGNMENT_RE.finditer(source)]


def find_secret_env_names(env: Mapping[str, object]) -> list[str]:
    return [name for name in env if any(p in name.upper() for p in SECRET_NAME_PARTS)]


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def find_policy_wildcards(
    document: Mapping[str, Any], allowed_resources: Sequence[str] = ()
) -> list[str]:
    """Report statements with action `*`, or a `*` resource whose Sid is not allowed."""
    findings: list[str] = []
    for index, statement in enumerate(_as_list(document.get("Statement", []))):
        sid = str(statement.get("Sid", index))
        if "*" in _as_list(statement.get("Action", [])):
            findings.append(f"statement {sid}: action *")
        if "*" in _as_list(statement.get("Resource", [])) and sid not in allowed_resources:
            findings.append(f"statement {sid}: resource *")
    return findings
