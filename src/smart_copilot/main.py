import uuid
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from smart_copilot import storage
from smart_copilot.bedrock import (
    BedrockAnalysisError,
    BedrockAnalyzer,
    get_analyzer,
    is_valid_analysis,
)
from smart_copilot.classifier import (
    classify_category,
    classify_sentiment,
    classify_urgency,
    draft_reply,
)
from smart_copilot.kb import get_kb_path, load_kb_documents
from smart_copilot.page import INDEX_HTML
from smart_copilot.retriever import retrieve_snippets

MAX_MESSAGE_LENGTH = 5000
URGENCY_ORDER = {"high": 0, "medium": 1, "low": 2}

LOCAL_FALLBACK_RECOMMENDATION: str = (
    "Please review the ticket manually and consult your team's knowledge base "
    "for the most appropriate resolution."
)

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
    source: str
    recommended_solution: str
    source_snippets: list[str]


def _local_fields(message: str) -> dict[str, Any]:
    category = classify_category(message)
    return {
        "category": category,
        "urgency": classify_urgency(message),
        "sentiment": classify_sentiment(message),
        "draft_reply": draft_reply(category),
    }


def analyze_or_fallback(
    message: str,
    analyzer: BedrockAnalyzer | None,
) -> tuple[dict[str, Any], str]:
    """Return (analysis_fields, source). Falls back to local on any Bedrock problem."""
    if analyzer is not None:
        try:
            result = analyzer.analyze(message)
            if is_valid_analysis(result):
                return {
                    "category": result["category"],
                    "urgency": result["urgency"],
                    "sentiment": result["sentiment"],
                    "draft_reply": result["draft_reply"],
                }, "bedrock"
        except BedrockAnalysisError:
            pass
    return _local_fields(message), "local"


def recommend_or_fallback(
    message: str,
    snippets: list[str],
    analyzer: BedrockAnalyzer | None,
) -> str:
    """Return Bedrock recommendation or LOCAL_FALLBACK_RECOMMENDATION.

    Returns LOCAL_FALLBACK_RECOMMENDATION when:
    - analyzer is None (BEDROCK_MODEL_ID unset)
    - snippets is empty (no context to ground the recommendation)
    - analyzer.recommend() raises BedrockAnalysisError
    - analyzer.recommend() returns an empty/blank string (defensive)
    """
    if analyzer is None or not snippets:
        return LOCAL_FALLBACK_RECOMMENDATION
    try:
        result = analyzer.recommend(message, snippets)
        return result if result and result.strip() else LOCAL_FALLBACK_RECOMMENDATION
    except BedrockAnalysisError:
        return LOCAL_FALLBACK_RECOMMENDATION


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
def create_ticket(
    body: TicketCreate,
    analyzer: Annotated[BedrockAnalyzer | None, Depends(get_analyzer)],
) -> dict[str, Any]:
    fields, source = analyze_or_fallback(body.message, analyzer)
    # Load past tickets BEFORE add_ticket so the new ticket is not in the corpus
    past_tickets = storage.load_tickets()
    kb_docs = load_kb_documents(get_kb_path())
    snippets = retrieve_snippets(body.message, past_tickets, kb_docs)
    recommended = recommend_or_fallback(body.message, snippets, analyzer)
    ticket: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "message": body.message,
        **fields,
        "source": source,
        "recommended_solution": recommended,
        "source_snippets": snippets,
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
