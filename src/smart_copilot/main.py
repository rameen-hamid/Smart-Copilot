import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.sessions import SessionMiddleware

from smart_copilot import storage
from smart_copilot.auth import (
    PUBLIC_PATHS,
    SESSION_KEY,
    SESSION_MAX_AGE,
    AuthNotConfigured,
    check_login,
    is_signed_in,
    session_secret,
)
from smart_copilot.classifier import (
    classify_category,
    classify_sentiment,
    classify_urgency,
    draft_reply,
)
from smart_copilot.page import INDEX_HTML, login_page

MAX_MESSAGE_LENGTH = 5000
URGENCY_ORDER = {"high": 0, "medium": 1, "low": 2}
INVALID_LOGIN = "Invalid username or password."
NOT_CONFIGURED = "Sign-in is not configured."

app = FastAPI(title="Smart Customer Support Copilot")


@app.middleware("http")
async def require_agent(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Deny by default: every path except the public ones needs a signed-in agent."""
    if request.url.path not in PUBLIC_PATHS and not is_signed_in(request.session):
        return RedirectResponse("/login", status_code=303)
    return await call_next(request)


# Added after require_agent, so it is the outer middleware and request.session
# exists when require_agent runs (Starlette puts the last-added middleware outermost).
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=False,
)


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


@app.get("/login", response_class=HTMLResponse)
def login_form() -> str:
    return login_page()


@app.post("/login", response_model=None)
def login(
    request: Request, username: str = Form(""), password: str = Form("")
) -> Response:
    try:
        ok = check_login(username, password)
    except AuthNotConfigured:
        return HTMLResponse(login_page(NOT_CONFIGURED), status_code=503)
    if not ok:
        return HTMLResponse(login_page(INVALID_LOGIN), status_code=401)
    request.session.clear()
    request.session[SESSION_KEY] = username
    return RedirectResponse("/", status_code=303)


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
