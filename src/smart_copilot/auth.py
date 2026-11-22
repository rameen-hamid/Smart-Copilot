"""Agent credentials, password hashing, and the session check.

Run `uv run python -m smart_copilot.auth` to create a value for AGENT_PASSWORD_HASH.
This module never logs usernames, passwords, hashes, or the session secret.
"""

import functools
import getpass
import hashlib
import hmac
import os
import secrets
import sys
from collections.abc import Mapping
from typing import Any

SESSION_KEY = "agent"
SESSION_MAX_AGE = 8 * 60 * 60  # 28,800 seconds
PUBLIC_PATHS = frozenset({"/health", "/login"})
DEFAULT_ITERATIONS = 600_000
_ALGORITHM = "pbkdf2_sha256"


class AuthNotConfigured(Exception):
    """The agent account is missing or its password hash is malformed."""


def hash_password(password: str, iterations: int = DEFAULT_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def _parse_hash(encoded: str) -> tuple[int, bytes, bytes]:
    parts = encoded.split("$")
    if len(parts) != 4 or parts[0] != _ALGORITHM:
        raise AuthNotConfigured("Password hash is malformed")
    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        digest = bytes.fromhex(parts[3])
    except ValueError as exc:
        raise AuthNotConfigured("Password hash is malformed") from exc
    if iterations <= 0 or not salt or not digest:
        raise AuthNotConfigured("Password hash is malformed")
    return iterations, salt, digest


def verify_password(password: str, encoded: str) -> bool:
    iterations, salt, expected = _parse_hash(encoded)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def agent_credentials() -> tuple[str, str]:
    username = os.environ.get("AGENT_USERNAME", "")
    password_hash = os.environ.get("AGENT_PASSWORD_HASH", "")
    if not username or not password_hash:
        raise AuthNotConfigured("Sign-in is not configured")
    return username, password_hash


def check_login(username: str, password: str) -> bool:
    expected_username, password_hash = agent_credentials()
    username_ok = hmac.compare_digest(
        username.encode("utf-8"), expected_username.encode("utf-8")
    )
    # Always verify the password so timing does not reveal whether the username exists.
    password_ok = verify_password(password, password_hash)
    return username_ok and password_ok


@functools.cache
def _process_secret() -> str:
    return secrets.token_urlsafe(32)


def session_secret() -> str:
    return os.environ.get("SESSION_SECRET") or _process_secret()


def is_signed_in(session: Mapping[str, Any]) -> bool:
    try:
        expected_username, _ = agent_credentials()
    except AuthNotConfigured:
        return False
    value = session.get(SESSION_KEY)
    if not isinstance(value, str):
        return False
    return hmac.compare_digest(value.encode("utf-8"), expected_username.encode("utf-8"))


def main() -> int:
    """Prompt for a password twice and print its hash. Takes no password argument."""
    try:
        first = getpass.getpass("Agent password: ")
        second = getpass.getpass("Repeat password: ")
    except (EOFError, KeyboardInterrupt):
        print("error: no password entered", file=sys.stderr)
        return 1
    if not first:
        print("error: password is empty", file=sys.stderr)
        return 1
    if first != second:
        print("error: passwords do not match", file=sys.stderr)
        return 1
    print(hash_password(first))
    return 0


if __name__ == "__main__":
    sys.exit(main())
