import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from smart_copilot.classifier import draft_reply
from smart_copilot.main import app


def _create(client: TestClient, message: str) -> dict:
    response = client.post("/tickets", json={"message": message})
    assert response.status_code == 201
    return response.json()


# Requirement 1: submit a message


def test_create_returns_201_and_full_ticket(client: TestClient) -> None:
    response = client.post("/tickets", json={"message": "Urgent refund, I am furious"})
    assert response.status_code == 201
    ticket = response.json()
    assert set(ticket) == {
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
    assert str(uuid.UUID(ticket["id"], version=4)) == ticket["id"]
    assert ticket["message"] == "Urgent refund, I am furious"
    assert ticket["category"] == "billing"
    assert ticket["urgency"] == "high"
    assert ticket["sentiment"] == "negative"
    assert ticket["draft_reply"] == draft_reply("billing")
    # BEDROCK_MODEL_ID is unset in tests → local classifier (Requirement 6.1)
    assert ticket["source"] == "local"
    # Empty KB fixture → no snippets; fallback recommendation (agent-desk Req 3.1, 3.2)
    assert ticket["source_snippets"] == []
    assert isinstance(ticket["recommended_solution"], str)
    assert len(ticket["recommended_solution"]) > 0


def test_message_is_stored_unchanged(client: TestClient, tickets_file: Path) -> None:
    message = "  padded message with spaces  \n"
    ticket = _create(client, message)
    assert ticket["message"] == message
    assert json.loads(tickets_file.read_text())[0]["message"] == message


def test_draft_reply_does_not_use_customer_text(client: TestClient) -> None:
    ticket = _create(client, "zzqx-unique-marker refund")
    assert "zzqx-unique-marker" not in ticket["draft_reply"]


# Requirement 2: validate message length


def test_empty_message_is_rejected(client: TestClient, tickets_file: Path) -> None:
    assert client.post("/tickets", json={"message": ""}).status_code == 422
    assert not tickets_file.exists()


def test_whitespace_only_message_is_rejected(client: TestClient, tickets_file: Path) -> None:
    assert client.post("/tickets", json={"message": "  \n\t "}).status_code == 422
    assert not tickets_file.exists()


def test_missing_message_field_is_rejected(client: TestClient) -> None:
    assert client.post("/tickets", json={}).status_code == 422


def test_message_over_5000_characters_is_rejected(client: TestClient, tickets_file: Path) -> None:
    response = client.post("/tickets", json={"message": "a" * 5001})
    assert response.status_code == 422
    assert not tickets_file.exists()


def test_message_of_exactly_5000_characters_is_accepted(client: TestClient) -> None:
    response = client.post("/tickets", json={"message": "a" * 5000})
    assert response.status_code == 201


# Requirement 3: list tickets


def test_list_is_empty_when_no_tickets(client: TestClient) -> None:
    response = client.get("/tickets")
    assert response.status_code == 200
    assert response.json() == []


def test_list_returns_created_tickets(client: TestClient) -> None:
    created = _create(client, "Hello there")
    assert client.get("/tickets").json() == [created]


def test_list_orders_high_then_medium_then_low_keeping_insertion_order(
    client: TestClient,
) -> None:
    low1 = _create(client, "Hello one")
    high1 = _create(client, "Urgent one")
    medium1 = _create(client, "Problem one")
    high2 = _create(client, "Emergency two")
    low2 = _create(client, "Hello two")
    medium2 = _create(client, "Delay two")
    listed = client.get("/tickets").json()
    assert [t["id"] for t in listed] == [
        high1["id"],
        high2["id"],
        medium1["id"],
        medium2["id"],
        low1["id"],
        low2["id"],
    ]


# Requirement 4: delete a ticket


def test_delete_existing_ticket_returns_204_and_removes_it(client: TestClient) -> None:
    keep = _create(client, "Hello keep")
    drop = _create(client, "Hello drop")
    response = client.delete(f"/tickets/{drop['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/tickets").json() == [keep]


def test_delete_unknown_id_returns_404_and_changes_nothing(
    client: TestClient, tickets_file: Path
) -> None:
    created = _create(client, "Hello there")
    before = tickets_file.read_text()
    response = client.delete(f"/tickets/{uuid.uuid4()}")
    assert response.status_code == 404
    assert tickets_file.read_text() == before
    assert client.get("/tickets").json() == [created]


# Requirement 5: persist across refresh


def test_create_writes_ticket_to_file(client: TestClient, tickets_file: Path) -> None:
    created = _create(client, "Hello there")
    assert json.loads(tickets_file.read_text()) == [created]


def test_delete_removes_ticket_from_file(client: TestClient, tickets_file: Path) -> None:
    created = _create(client, "Hello there")
    client.delete(f"/tickets/{created['id']}")
    assert json.loads(tickets_file.read_text()) == []


def test_new_app_instance_lists_same_tickets(client: TestClient) -> None:
    created = _create(client, "Hello there")
    with TestClient(app) as second_client:
        assert second_client.get("/tickets").json() == [created]


def test_missing_file_is_an_empty_list(client: TestClient, tickets_file: Path) -> None:
    assert not tickets_file.exists()
    assert client.get("/tickets").json() == []


def test_invalid_json_returns_500_on_list(client: TestClient, tickets_file: Path) -> None:
    tickets_file.write_text("{not json")
    assert client.get("/tickets").status_code == 500
    assert tickets_file.read_text() == "{not json"


def test_invalid_json_returns_500_on_create_and_is_not_overwritten(
    client: TestClient, tickets_file: Path
) -> None:
    tickets_file.write_text("{not json")
    assert client.post("/tickets", json={"message": "Hello"}).status_code == 500
    assert tickets_file.read_text() == "{not json"


def test_invalid_json_returns_500_on_delete_and_is_not_overwritten(
    client: TestClient, tickets_file: Path
) -> None:
    tickets_file.write_text("{not json")
    assert client.delete(f"/tickets/{uuid.uuid4()}").status_code == 500
    assert tickets_file.read_text() == "{not json"


def test_non_list_json_returns_500_and_is_not_overwritten(
    client: TestClient, tickets_file: Path
) -> None:
    tickets_file.write_text('{"a": 1}')
    assert client.get("/tickets").status_code == 500
    assert tickets_file.read_text() == '{"a": 1}'
