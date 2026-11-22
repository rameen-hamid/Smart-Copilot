import logging
import os
import re
import subprocess
import sys

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from smart_copilot import auth
from smart_copilot.auth import (
    AuthNotConfigured,
    agent_credentials,
    check_login,
    hash_password,
    is_signed_in,
    session_secret,
    verify_password,
)

# Test-only value, not a real credential. Matches the fake agent in conftest.py.
FAKE_PASSWORD = "fake-password-for-tests"
FAKE_HASH = hash_password(FAKE_PASSWORD, iterations=1000)
HASH_RE = re.compile(r"^pbkdf2_sha256\$\d+\$[0-9a-f]+\$[0-9a-f]+$")


# The fake agent (AGENT_USERNAME, AGENT_PASSWORD_HASH, SESSION_SECRET) is set by
# the autouse `fake_agent` fixture in tests/conftest.py.


def test_hash_password_format() -> None:
    encoded = hash_password("x", iterations=1000)
    assert encoded.startswith("pbkdf2_sha256$1000$")
    assert len(encoded.split("$")) == 4
    assert HASH_RE.match(encoded)


def test_hash_password_uses_random_salt() -> None:
    assert hash_password("x", iterations=1000) != hash_password("x", iterations=1000)


def test_verify_password_correct_and_wrong() -> None:
    assert verify_password(FAKE_PASSWORD, FAKE_HASH) is True
    assert verify_password("other", FAKE_HASH) is False


@pytest.mark.parametrize(
    "encoded",
    [
        "",
        "abc",
        "md5$1$aa$bb",
        "pbkdf2_sha256$0$aa$bb",
        "pbkdf2_sha256$x$aa$bb",
        "pbkdf2_sha256$1000$zz$bb",
        "pbkdf2_sha256$1000$$",
    ],
)
def test_verify_password_malformed_raises(encoded: str) -> None:
    with pytest.raises(AuthNotConfigured):
        verify_password(FAKE_PASSWORD, encoded)


@pytest.mark.parametrize("name", ["AGENT_USERNAME", "AGENT_PASSWORD_HASH"])
@pytest.mark.parametrize("mode", ["unset", "empty"])
def test_agent_credentials_not_configured(
    monkeypatch: pytest.MonkeyPatch, name: str, mode: str
) -> None:
    if mode == "unset":
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, "")
    with pytest.raises(AuthNotConfigured):
        agent_credentials()


def test_agent_credentials_read_from_env() -> None:
    username, password_hash = agent_credentials()
    assert username == "test-agent"
    assert password_hash == os.environ["AGENT_PASSWORD_HASH"]
    assert verify_password(FAKE_PASSWORD, password_hash)


@pytest.mark.parametrize(
    ("username", "password", "expected"),
    [
        ("test-agent", FAKE_PASSWORD, True),
        ("test-agent", "wrong-password", False),
        ("someone-else", FAKE_PASSWORD, False),
        ("", "", False),
        ("test-agent", "", False),
        ("   ", "   ", False),
        ("tëst-agent", FAKE_PASSWORD, False),
    ],
)
def test_check_login(username: str, password: str, expected: bool) -> None:
    assert check_login(username, password) is expected


def test_check_login_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_PASSWORD_HASH")
    with pytest.raises(AuthNotConfigured):
        check_login("test-agent", FAKE_PASSWORD)


def test_session_secret_env_and_random(monkeypatch: pytest.MonkeyPatch) -> None:
    assert session_secret() == "test-session-secret"
    monkeypatch.delenv("SESSION_SECRET")
    first = session_secret()
    assert first
    assert first != "test-session-secret"
    assert session_secret() == first
    monkeypatch.setenv("SESSION_SECRET", "")
    assert session_secret() == first


def test_session_secret_differs_between_processes() -> None:
    env = {k: v for k, v in os.environ.items() if k != "SESSION_SECRET"}
    code = "from smart_copilot.auth import session_secret; print(session_secret())"
    values = [
        subprocess.run(
            [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
        ).stdout.strip()
        for _ in range(2)
    ]
    assert values[0] and values[1]
    assert values[0] != values[1]


def test_is_signed_in(monkeypatch: pytest.MonkeyPatch) -> None:
    assert is_signed_in({"agent": "test-agent"}) is True
    assert is_signed_in({}) is False
    assert is_signed_in({"agent": "someone-else"}) is False
    assert is_signed_in({"agent": 123}) is False
    monkeypatch.delenv("AGENT_USERNAME")
    assert is_signed_in({"agent": "test-agent"}) is False


def _fake_getpass(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> None:
    replies = iter(answers)
    monkeypatch.setattr(auth.getpass, "getpass", lambda prompt="": next(replies))


def test_hash_command_matching_passwords(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _fake_getpass(monkeypatch, ["pw-for-test", "pw-for-test"])
    assert auth.main() == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert HASH_RE.match(lines[0])
    assert verify_password("pw-for-test", lines[0])


def test_hash_command_empty_password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _fake_getpass(monkeypatch, ["", ""])
    assert auth.main() != 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "empty" in captured.err


def test_hash_command_mismatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _fake_getpass(monkeypatch, ["pw-one", "pw-two"])
    assert auth.main() != 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "match" in captured.err


def test_hash_command_takes_no_password_argument(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["smart_copilot.auth", "argv-password"])
    _fake_getpass(monkeypatch, ["prompt-password", "prompt-password"])
    assert auth.main() == 0
    printed = capsys.readouterr().out.strip()
    assert verify_password("prompt-password", printed)
    assert not verify_password("argv-password", printed)


def test_no_logging(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        check_login("test-agent", "wrong-password")
        check_login("test-agent", FAKE_PASSWORD)
    text = caplog.text
    fake_hash = os.environ["AGENT_PASSWORD_HASH"]
    for secret in ("test-agent", FAKE_PASSWORD, "wrong-password", fake_hash):
        assert secret not in text


# Feature: agent-sign-in, Property 1: Password verification matches equality
@settings(max_examples=100, deadline=None)
@given(st.text(), st.text())
def test_property_verify_password_matches_equality(p: str, q: str) -> None:
    encoded = hash_password(p, iterations=1000)
    assert HASH_RE.match(encoded)
    assert verify_password(q, encoded) == (p == q)
    assert verify_password(p, encoded) is True
