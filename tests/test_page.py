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
    for field in ("t.category", "t.urgency", "t.sentiment", "t.draft_reply", "t.source"):
        assert field in html


def test_page_renders_ticket_text_without_html_injection(client: TestClient) -> None:
    html = client.get("/").text
    assert "textContent" in html
    assert "innerHTML" not in html
