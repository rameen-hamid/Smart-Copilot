import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from smart_copilot import storage
from smart_copilot.classifier import (
    classify_category,
    classify_sentiment,
    classify_urgency,
    draft_reply,
)
from smart_copilot.page import INDEX_HTML

MAX_MESSAGE_LENGTH = 5000
URGENCY_ORDER = {"high": 0, "medium": 1, "low": 2}

app = FastAPI(title="Smart Customer Support Copilot")


class TicketCreate(BaseModel):
    message: str = Field(max_length=MAX_MESSAGE_LENGTH)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be empty or whitespace only")
        return value


class Ticket(BaseModel):
    id: str
    message: str
    category: str
    urgency: str
    sentiment: str
    draft_reply: str


@app.exception_handler(storage.TicketStoreError)
def store_error_handler(request: Request, exc: storage.TicketStoreError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.post("/tickets", status_code=201, response_model=Ticket)
def create_ticket(body: TicketCreate) -> dict[str, Any]:
    category = classify_category(body.message)
    ticket = {
        "id": str(uuid.uuid4()),
        "message": body.message,
        "category": category,
        "urgency": classify_urgency(body.message),
        "sentiment": classify_sentiment(body.message),
        "draft_reply": draft_reply(category),
    }
    storage.add_ticket(ticket)
    return ticket


@app.get("/tickets", response_model=list[Ticket])
def list_tickets() -> list[dict[str, Any]]:
    tickets = storage.load_tickets()
    return sorted(tickets, key=lambda t: URGENCY_ORDER.get(t.get("urgency"), 3))


@app.delete("/tickets/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: str) -> Response:
    if not storage.delete_ticket(ticket_id):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return Response(status_code=204)
