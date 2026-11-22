from fastapi.testclient import TestClient


def test_index_returns_html_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_page_has_message_box_submit_and_ticket_list(client: TestClient) -> None:
    html = client.get("/").text
    assert '<textarea id="message"' in html
    assert '<button type="submit">Submit</button>' in html
    assert 'id="tickets"' in html


def test_page_loads_tickets_from_api_and_has_delete_button(client: TestClient) -> None:
    html = client.get("/").text
    assert 'fetch("/tickets")' in html
    assert 'method: "DELETE"' in html
    assert 'del.textContent = "Delete"' in html


def test_page_shows_category_urgency_sentiment_and_draft(client: TestClient) -> None:
    html = client.get("/").text
    for field in ("t.category", "t.urgency", "t.sentiment", "t.draft_reply"):
        assert field in html


def test_page_renders_ticket_text_without_html_injection(client: TestClient) -> None:
    html = client.get("/").text
    assert "textContent" in html
    assert "innerHTML" not in html


# Agent sign-in: login page


def test_login_page_has_one_username_one_password_one_submit() -> None:
    from smart_copilot.page import login_page

    page = login_page()
    assert page.count('name="username"') == 1
    assert page.count('type="password"') == 1
    assert page.count('type="submit"') == 1
    assert '<form method="post" action="/login">' in page


def test_login_page_error_message_and_empty_fields() -> None:
    from smart_copilot.page import login_page

    page = login_page("Invalid username or password.")
    assert "Invalid username or password." in page
    assert "value=" not in page


def test_login_page_escapes_error() -> None:
    from smart_copilot.page import login_page

    page = login_page("<script>x</script>")
    assert "<script>x</script>" not in page
    assert "&lt;script&gt;x&lt;/script&gt;" in page


def test_login_page_no_error_by_default() -> None:
    from smart_copilot.page import login_page

    assert "Invalid username or password." not in login_page()
    assert "__ERROR__" not in login_page()


# Agent sign-in: desk follows the redirect to /login.
# Limit: these read the page source only. pytest runs no browser, so they do not
# prove the redirect happens in a browser (manual Playwright check, task 7.3).


def _fetch_sections() -> list[str]:
    """Each fetch call with the code that follows it, up to the next fetch."""
    from smart_copilot.page import INDEX_HTML

    script = INDEX_HTML.split("<script>", 1)[1]
    return script.split("await fetch(")[1:]


def test_index_defines_redirect_helper() -> None:
    from smart_copilot.page import INDEX_HTML

    assert "function toLoginIfRedirected(res)" in INDEX_HTML
    assert "res.redirected" in INDEX_HTML
    assert 'new URL(res.url).pathname === "/login"' in INDEX_HTML
    assert 'window.location = "/login"' in INDEX_HTML


def test_index_calls_helper_after_each_fetch() -> None:
    sections = _fetch_sections()
    assert [s.split(")", 1)[0].split(",", 1)[0] for s in sections] == [
        '"/tickets"',
        '"/tickets/" + encodeURIComponent(t.id',
        '"/tickets"',
    ]
    for section in sections:
        guard = section.find("if (toLoginIfRedirected(")
        assert guard != -1
        for later in (".json()", ".text()", "errorBox.textContent", "line(list"):
            position = section.find(later)
            assert position == -1 or guard < position


def test_index_keeps_existing_error_messages() -> None:
    from smart_copilot.page import INDEX_HTML

    assert "Could not load tickets (" in INDEX_HTML
    assert "Could not delete (" in INDEX_HTML
    assert "Could not save ticket (" in INDEX_HTML
    assert "Message must be 1 to 5000 characters and not blank." in INDEX_HTML


def test_get_root_signed_in_serves_script(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "toLoginIfRedirected" in response.text
