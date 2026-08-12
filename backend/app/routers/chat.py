"""
Chat/RAG router — thin HTTP/SSE layer.

All orchestration (validation, history, embedding, retrieval, prompt
construction, streaming, persistence) lives in services/chat.py. This
router is responsible only for: request validation, HTTP-level repo
gating, rate limiting, and converting the ChatEvent stream from
handle_chat_message() into Server-Sent Events.

Repo check matches routers/repos.py::get_repo() exactly: a single query
filtered by both id and user_id, 404 if nothing matches (no separate 403
branch — repos.py doesn't distinguish "not found" from "not yours," and
chat_messages is user-scoped the same way repos is, so this router
follows repos.py's pattern rather than walkthrough.py's, which has no
user_id filter at all since walkthrough_steps isn't user-scoped).

DEV_USER_ID is the confirmed project-wide dev-bypass pattern — every
router (repos.py, ingest.py, impact.py, heatmap.py) inlines this same
literal constant locally; there is no shared import for it.

SSE headers match routers/ingest.py::stream_progress() — including
X-Accel-Buffering: no, which disables response buffering at an Nginx
reverse-proxy layer (if deployed behind one) so token-level streaming
isn't silently defeated regardless of how correct the backend code is.

Note: services/chat.py performs its own repo validation internally too
(so it's safe to call from any future non-HTTP caller) — this router's
check is intentionally redundant with the service's, same relationship
walkthrough.py has with get_or_generate_walkthrough().
"""



import json
import logging
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.db.supabase import get_supabase_client
from app.services.chat import (
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    TokenEvent,
    handle_chat_message,
)

# Dev bypass — same pattern as repos.py, impact.py, heatmap.py (confirmed
# by inspection: every router inlines this identical literal locally).
DEV_USER_ID = "9a1d390c-f049-4199-8146-503123f4f1f3"

router = APIRouter(prefix="/api/chat", tags=["chat"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    repo_id: UUID
    message: str = Field(..., min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# SSE formatting
# ---------------------------------------------------------------------------

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _event_stream(repo_id: str, user_id: str, message: str):
    """
    Consumes handle_chat_message()'s ChatEvent stream and converts each
    event to one SSE frame. No orchestration logic here — purely a
    type-to-wire-format mapping.

    Wrapped in a defensive try/except: services/chat.py already yields
    ErrorEvent for known failure modes, but this guards against anything
    genuinely unexpected so the SSE connection always ends with a clean
    error frame rather than an abrupt close.
    """
    try:
        async for event in handle_chat_message(repo_id, user_id, message):
            if isinstance(event, SourcesEvent):
                yield _sse("sources", {"sources": [asdict(s) for s in event.sources]})

            elif isinstance(event, TokenEvent):
                yield _sse("token", {"text": event.text})

            elif isinstance(event, ErrorEvent):
                yield _sse("error", {"message": event.message})

            elif isinstance(event, DoneEvent):
                yield _sse("done", {})

    except Exception as exc:
        logger.exception("Unexpected error in chat event stream: %s", exc)
        yield _sse(
            "error",
            {"message": "Sorry, something went wrong. Please try again."},
        )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("")
@limiter.limit(settings.rate_chat)
async def chat(request: Request, body: ChatRequest):
    user_id = DEV_USER_ID
    supabase = get_supabase_client()
    repo_id_str = str(body.repo_id)

    repo_result = (
        supabase.table("repos")
        .select("id,status")
        .eq("id", repo_id_str)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    repo = repo_result.data
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repo["status"] != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Repository is not ready yet (status: {repo['status']})",
        )

    return StreamingResponse(
        _event_stream(repo_id_str, user_id, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

@router.get("/{repo_id}/messages")
@limiter.limit(settings.rate_chat)
async def get_chat_history(
    request: Request,
    repo_id: UUID,
):
    """
    Returns persisted chat history for a repository.

    Thin read endpoint only.

    No orchestration logic lives here—this simply validates repository
    ownership (matching repos.py) and returns persisted chat_messages so
    the frontend can display the same conversation the backend already
    uses as prompt history.
    """

    user_id = DEV_USER_ID
    supabase = get_supabase_client()
    repo_id_str = str(repo_id)

    # Same validation pattern as repos.py / POST endpoint
    repo_result = (
        supabase.table("repos")
        .select("id")
        .eq("id", repo_id_str)
        .eq("user_id", user_id)
        .single()
        .execute()
    )

    if not repo_result.data:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    result = (
        supabase.table("chat_messages")
        .select("id, role, content, created_at")
        .eq("repo_id", repo_id_str)
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )

    return {
        "repo_id": repo_id_str,
        "messages": result.data or [],
    }