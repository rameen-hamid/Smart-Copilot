import json
import logging
import os
import string
import types
import urllib.parse
from base64 import b64encode
from pathlib import Path

import httpx2
import itsdangerous
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from starlette.routing import Route

from smart_copilot.auth import PUBLIC_PATHS
from smart_copilot.main import app

# Test-only value, not a real credential. Matches the fake agent in conftest.py.
FAKE_PASSWORD = "fake-password-for-tests"
INVALID = "Invalid username or password."
NOT_CONFIGURED = "Sign-in is not configured."
SYNTHETIC_TICKET = {
    "id": "00000000-0000-4000-8000-000000000001",
    "message": "Synthetic ticket marker-7731 about a refund",
    "category": "billing",
    "urgency": "low",
    "sentiment": "neutral",
    "draft_reply": "Thank you.",
    "source": "local",
    "recommended_solution": "Review the ticket manually.",
    "source_snippets": [],
}


# AGENT_USERNAME, AGENT_PASSWORD_HASH, SESSION_SECRET, TICKETS_FILE and `anon_client`
# come from tests/conftest.py.


def _sign_in(c: TestClient) -> None:
    response = c.post("/login", data={"username": "test-agent", "password": FAKE_PASSWORD})
    # 200 + JS navigation (proxy-safe; was 303)
    assert response.status_code == 200


@pytest.fixture
def agent_client(anon_client: TestClient) -> TestClient:
    _sign_in(anon_client)
    return anon_client


def _wrong(c: TestClient) -> tuple[int, str]:
    r = c.post("/login", data={"username": "test-agent", "password": "wrong-password"})
    return r.status_code, r.text


def _assert_redirect_to_login(response: httpx2.Response) -> None:
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert SYNTHETIC_TICKET["message"] not in response.text


# Requirement 1: login page


def test_get_login_without_session(anon_client: TestClient) -> None:
    response = anon_client.get("/login")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text.count('type="password"') == 1


def test_get_login_with_session(agent_client: TestClient) -> None:
    response = agent_client.get("/login")
    assert response.status_code == 200
    assert 'action="login"' in response.text


def test_get_login_when_not_configured(
    anon_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AGENT_USERNAME")
    monkeypatch.delenv("AGENT_PASSWORD_HASH")
    assert anon_client.get("/login").status_code == 200


# Requirement 2: correct sign-in


def test_correct_login_redirects_and_sets_cookie(anon_client: TestClient) -> None:
    response = anon_client.post(
        "/login", data={"username": "test-agent", "password": FAKE_PASSWORD}
    )
    # 200 — serves the ticket desk directly (no redirect, works behind any proxy)
    assert response.status_code == 200
    assert '<textarea id="message"' in response.text   # ticket desk is present
    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith("session=")
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=28800" in cookie


def test_signed_in_desk_and_api_work(agent_client: TestClient) -> None:
    page = agent_client.get("/")
    assert page.status_code == 200
    assert '<textarea id="message"' in page.text
    assert agent_client.get("/tickets").json() == []
    created = agent_client.post("/tickets", json={"message": "Hello there"})
    assert created.status_code == 201
    assert agent_client.delete(f"/tickets/{created.json()['id']}").status_code == 204
    assert agent_client.delete("/tickets/does-not-exist").status_code == 404
    assert agent_client.post("/tickets", json={"message": "  "}).status_code == 422


def test_signed_in_queue_order_and_shape(agent_client: TestClient) -> None:
    for message in ["Hello there", "urgent one", "urgent two", "there is a problem"]:
        assert agent_client.post("/tickets", json={"message": message}).status_code == 201
    tickets = agent_client.get("/tickets").json()
    assert [t["message"] for t in tickets] == [
        "urgent one",
        "urgent two",
        "there is a problem",
        "Hello there",
    ]
    assert [t["urgency"] for t in tickets] == ["high", "high", "medium", "low"]
    for t in tickets:
        assert set(t) == {
            "id",
            "message",
            "category",
            "urgency",
            "sentiment",
            "draft_reply",
            "source",
            "recommended_solution",
            "source_snippets",
        }


# Requirement 3: wrong sign-in


def test_wrong_password_gives_401_message(anon_client: TestClient) -> None:
    response = anon_client.post(
        "/login", data={"username": "test-agent", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert INVALID in response.text
    assert 'action="login"' in response.text
    assert "set-cookie" not in response.headers


def test_wrong_username_same_response_as_wrong_password(anon_client: TestClient) -> None:
    response = anon_client.post(
        "/login", data={"username": "someone-else", "password": FAKE_PASSWORD}
    )
    assert (response.status_code, response.text) == _wrong(anon_client)


@pytest.mark.parametrize(
    "data",
    [
        {"username": "", "password": ""},
        {"username": "test-agent", "password": ""},
        {"username": "", "password": FAKE_PASSWORD},
        {"username": "   ", "password": "   "},
        {"password": FAKE_PASSWORD},
        {"username": "test-agent"},
        {},
    ],
)
def test_empty_whitespace_and_missing_fields_same_response(
    anon_client: TestClient, data: dict[str, str]
) -> None:
    response = anon_client.post("/login", data=data)
    assert (response.status_code, response.text) == _wrong(anon_client)
    assert "set-cookie" not in response.headers


def test_failed_login_leaves_no_session(anon_client: TestClient) -> None:
    _wrong(anon_client)
    assert not anon_client.cookies
    _assert_redirect_to_login(anon_client.get("/tickets"))


def test_failed_login_does_not_echo_input(anon_client: TestClient) -> None:
    response = anon_client.post(
        "/login", data={"username": "marker-user-5521", "password": "marker-pass-8843"}
    )
    everything = response.text + str(response.headers)
    assert "marker-user-5521" not in everything
    assert "marker-pass-8843" not in everything


def test_failed_login_does_not_log_input(
    anon_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        anon_client.post("/login", data={"username": "log-user-1", "password": "log-pass-1"})
        _sign_in(anon_client)
    fake_hash = os.environ["AGENT_PASSWORD_HASH"]
    for secret in ("log-user-1", "log-pass-1", FAKE_PASSWORD, fake_hash):
        assert secret not in caplog.text


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("AGENT_PASSWORD_HASH", None),
        ("AGENT_PASSWORD_HASH", ""),
        ("AGENT_PASSWORD_HASH", "not-a-hash"),
        ("AGENT_USERNAME", None),
        ("AGENT_USERNAME", ""),
    ],
)
def test_login_not_configured_returns_503(
    anon_client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, value)
    response = anon_client.post(
        "/login", data={"username": "test-agent", "password": FAKE_PASSWORD}
    )
    assert response.status_code == 503
    assert NOT_CONFIGURED in response.text
    assert "set-cookie" not in response.headers
    assert anon_client.get("/health").json() == {"status": "ok"}


def test_retry_after_failure_signs_in(anon_client: TestClient) -> None:
    assert _wrong(anon_client)[0] == 401
    response = anon_client.post(
        "/login", data={"username": "test-agent", "password": FAKE_PASSWORD}
    )
    assert response.status_code == 200
    assert anon_client.get("/tickets").status_code == 200


# Requirement 4: protected desk and API


def test_protected_routes_redirect_without_session(anon_client: TestClient) -> None:
    _assert_redirect_to_login(anon_client.get("/"))
    _assert_redirect_to_login(anon_client.get("/tickets"))
    _assert_redirect_to_login(anon_client.post("/tickets", json={"message": "Hello"}))
    _assert_redirect_to_login(anon_client.post("/tickets", json={"message": ""}))
    _assert_redirect_to_login(anon_client.post("/tickets", content=b"{not json"))
    _assert_redirect_to_login(anon_client.delete("/tickets/does-not-exist"))
    _assert_redirect_to_login(anon_client.delete(f"/tickets/{SYNTHETIC_TICKET['id']}"))


def test_redirect_leaves_tickets_file_unchanged(
    anon_client: TestClient, tickets_file: Path
) -> None:
    tickets_file.write_text(json.dumps([SYNTHETIC_TICKET]))
    before = tickets_file.read_bytes()
    _assert_redirect_to_login(anon_client.get("/tickets"))
    _assert_redirect_to_login(anon_client.post("/tickets", json={"message": "Hello"}))
    _assert_redirect_to_login(anon_client.delete(f"/tickets/{SYNTHETIC_TICKET['id']}"))
    assert tickets_file.read_bytes() == before


def test_redirect_does_not_read_tickets_file(
    anon_client: TestClient, tickets_file: Path
) -> None:
    tickets_file.write_text("{not json")
    _assert_redirect_to_login(anon_client.get("/tickets"))


def test_unknown_path_and_method_redirect(anon_client: TestClient) -> None:
    _assert_redirect_to_login(anon_client.get("/nope"))
    _assert_redirect_to_login(anon_client.put("/tickets"))
    _assert_redirect_to_login(anon_client.get("/login/"))


def test_every_non_public_route_is_protected(anon_client: TestClient) -> None:
    checked = 0
    for route in app.routes:
        if not isinstance(route, (APIRoute, Route)) or route.path in PUBLIC_PATHS:
            continue
        path = route.path.replace("{ticket_id}", "some-id")
        for method in route.methods or {"GET"}:
            _assert_redirect_to_login(anon_client.request(method, path))
            checked += 1
    assert checked >= 4


def test_signed_in_request_not_redirected_proves_middleware_order(
    agent_client: TestClient,
) -> None:
    response = agent_client.get("/tickets")
    assert response.status_code == 200
    assert response.json() == []


def _session_cookie(c: TestClient) -> str:
    return c.cookies["session"]


def _tamper(value: str) -> str:
    # Change the first character of the signed data; any change breaks the signature.
    first = value[0]
    return ("B" if first != "B" else "C") + value[1:]


def test_tampered_cookie_rejected(agent_client: TestClient) -> None:
    good = _session_cookie(agent_client)
    agent_client.cookies.clear()  # replace the valid cookie, do not send both
    agent_client.cookies.set("session", _tamper(good))
    assert agent_client.cookies["session"] != good
    _assert_redirect_to_login(agent_client.get("/tickets"))


def _cookie_with_secret(secret: str) -> str:
    data = b64encode(json.dumps({"agent": "test-agent"}).encode("utf-8"))
    return itsdangerous.TimestampSigner(secret).sign(data).decode("utf-8")


def test_cookie_signed_with_other_secret_rejected(anon_client: TestClient) -> None:
    anon_client.cookies.set("session", _cookie_with_secret("another-secret-for-tests"))
    _assert_redirect_to_login(anon_client.get("/tickets"))


def _freeze_time(monkeypatch: pytest.MonkeyPatch, now: float) -> None:
    # itsdangerous.timed calls time.time() to stamp and to check cookie age.
    monkeypatch.setattr(itsdangerous.timed, "time", types.SimpleNamespace(time=lambda: now))


def test_expired_cookie_rejected(
    anon_client: TestClient, monkeypatch: pytest.MonkeyPatch, tickets_file: Path
) -> None:
    tickets_file.write_text(json.dumps([SYNTHETIC_TICKET]))
    start = 1_900_000_000.0
    _freeze_time(monkeypatch, start)
    _sign_in(anon_client)
    _freeze_time(monkeypatch, start + 28_799)
    assert anon_client.get("/tickets").status_code == 200
    _freeze_time(monkeypatch, start + 28_801)
    _assert_redirect_to_login(anon_client.get("/tickets"))


# Requirement 5: public routes


def test_health_is_public(anon_client: TestClient, tickets_file: Path) -> None:
    tickets_file.write_text(json.dumps([SYNTHETIC_TICKET]))
    before = tickets_file.read_bytes()
    response = anon_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert tickets_file.read_bytes() == before


def test_public_routes_with_bad_cookie(anon_client: TestClient) -> None:
    anon_client.cookies.set("session", "garbage-cookie-value")
    assert anon_client.get("/health").status_code == 200
    assert anon_client.get("/login").status_code == 200
    response = anon_client.post(
        "/login", data={"username": "test-agent", "password": FAKE_PASSWORD}
    )
    assert response.status_code == 200


# Requirement 8: no AWS


def test_no_aws_credentials_needed(
    anon_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    _sign_in(anon_client)
    assert anon_client.get("/tickets").status_code == 200


# Property-based tests

SAFE_COOKIE_CHARS = string.ascii_letters + string.digits + "-_.="
PROPERTY_SETTINGS = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


# Feature: agent-sign-in, Property 2: Any wrong credentials give one uniform failure
@PROPERTY_SETTINGS
@given(username=st.text(), password=st.text())
def test_property_wrong_credentials_uniform_failure(username: str, password: str) -> None:
    assume((username, password) != ("test-agent", FAKE_PASSWORD))
    with TestClient(app, follow_redirects=False) as c:
        baseline = c.post("/login", data={"username": "x-baseline", "password": "y-baseline"})
        baseline_text = baseline.text + str(baseline.headers)
        response = c.post("/login", data={"username": username, "password": password})
        assert response.status_code == 401
        assert response.text == baseline.text
        assert "set-cookie" not in response.headers
        everything = response.text + str(response.headers)
        for value in (username, password):
            if len(value) >= 4 and value not in baseline_text:
                assert value not in everything
        assert c.get("/tickets").status_code == 303


_PROTECTED_REQUESTS = st.one_of(
    st.just(("GET", "/", b"")),
    st.just(("GET", "/tickets", b"")),
    st.tuples(st.just("POST"), st.just("/tickets"), st.binary(max_size=200)),
    st.tuples(
        st.just("DELETE"),
        st.text(min_size=1, max_size=40).map(
            lambda s: "/tickets/" + urllib.parse.quote(s, safe="")
        ),
        st.just(b""),
    ),
    st.tuples(
        st.sampled_from(["GET", "POST", "PUT", "PATCH", "DELETE"]),
        st.text(min_size=1, max_size=40).map(lambda s: "/" + urllib.parse.quote(s, safe="")),
        st.just(b""),
    ),
)


# Feature: agent-sign-in, Property 3: Protected routes never serve data without a session
@PROPERTY_SETTINGS
@given(request=_PROTECTED_REQUESTS)
def test_property_protected_routes_redirect_without_session(
    request: tuple[str, str, bytes], tickets_file: Path
) -> None:
    method, path, body = request
    assume(path not in PUBLIC_PATHS)
    tickets_file.write_text(json.dumps([SYNTHETIC_TICKET]))
    before = tickets_file.read_bytes()
    with TestClient(app, follow_redirects=False) as c:
        response = c.request(method, path, content=body)
    _assert_redirect_to_login(response)
    assert tickets_file.read_bytes() == before


# Feature: agent-sign-in, Property 4: Any invalid session cookie is rejected
@PROPERTY_SETTINGS
@given(
    kind=st.sampled_from(["arbitrary", "tampered", "other-secret"]),
    text=st.text(alphabet=SAFE_COOKIE_CHARS, min_size=1, max_size=120),
    index=st.integers(min_value=0, max_value=10_000),
    replacement=st.sampled_from(string.ascii_letters + string.digits),
)
def test_property_invalid_cookie_rejected(
    kind: str, text: str, index: int, replacement: str
) -> None:
    with TestClient(app, follow_redirects=False) as c:
        if kind == "arbitrary":
            cookie = text
        elif kind == "other-secret":
            cookie = _cookie_with_secret("other-" + text)
        else:
            _sign_in(c)
            good = _session_cookie(c)
            # Only change the signed data and timestamp, not the base64 signature itself,
            # where the last character can carry unused padding bits.
            limit = good.rindex(".")
            i = index % limit
            assume(good[i] != replacement)
            cookie = good[:i] + replacement + good[i + 1 :]
            c.cookies.clear()
        c.cookies.set("session", cookie)
        _assert_redirect_to_login(c.get("/tickets"))
        _assert_redirect_to_login(c.get("/"))
        assert c.get("/health").status_code == 200
        assert c.get("/login").status_code == 200


# Task 5: shared fixtures


def test_client_fixture_is_signed_in(client: TestClient, anon_client: TestClient) -> None:
    assert client.get("/tickets").status_code == 200
    assert client.get("/tickets").json() == []
    _assert_redirect_to_login(anon_client.get("/tickets"))


def test_tickets_file_is_temp(client: TestClient, tickets_file: Path, tmp_path: Path) -> None:
    real = Path(__file__).resolve().parent.parent / "data" / "tickets.json"
    before = real.read_bytes() if real.exists() else None
    assert tickets_file.parent == tmp_path
    assert tickets_file.resolve() != real
    assert client.post("/tickets", json={"message": "Hello there"}).status_code == 201
    assert tickets_file.exists()
    after = real.read_bytes() if real.exists() else None
    assert after == before
