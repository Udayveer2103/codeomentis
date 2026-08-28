"""
Chat/RAG router.

Handles authentication, repository ownership validation,
rate limiting, and Server-Sent Events.

All RAG/orchestration logic lives in services/chat.py.
"""

import json
import logging
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.db.supabase import AuthUser, get_supabase_client
from app.dependencies import get_current_user
from app.services.chat import (
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    TokenEvent,
    handle_chat_message,
)

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
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )


# ---------------------------------------------------------------------------
# Chat event stream
# ---------------------------------------------------------------------------

async def _event_stream(
    repo_id: str,
    user_id: str,
    message: str,
):
    """Convert service ChatEvents into SSE frames."""

    try:
        async for event in handle_chat_message(
            repo_id,
            user_id,
            message,
        ):
            if isinstance(event, SourcesEvent):
                yield _sse(
                    "sources",
                    {
                        "sources": [
                            asdict(source)
                            for source in event.sources
                        ]
                    },
                )

            elif isinstance(event, TokenEvent):
                yield _sse(
                    "token",
                    {"text": event.text},
                )

            elif isinstance(event, ErrorEvent):
                yield _sse(
                    "error",
                    {"message": event.message},
                )

            elif isinstance(event, DoneEvent):
                yield _sse("done", {})

    except Exception:
        logger.exception(
            "Unexpected error in chat stream for repo %s",
            repo_id,
        )

        yield _sse(
            "error",
            {
                "message": (
                    "Sorry, something went wrong. "
                    "Please try again."
                )
            },
        )


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------

@router.post("")
@limiter.limit(settings.rate_chat)
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """Start a streaming RAG chat response."""

    user_id = current_user.id
    repo_id_str = str(body.repo_id)

    supabase = get_supabase_client()

    # Verify repository ownership.
    repo_result = (
        supabase.table("repos")
        .select("id, status")
        .eq("id", repo_id_str)
        .eq("user_id", user_id)
        .single()
        .execute()
    )

    repo = repo_result.data

    if not repo:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    if repo["status"] != "ready":
        raise HTTPException(
            status_code=409,
            detail=(
                "Repository is not ready yet "
                f"(status: {repo['status']})"
            ),
        )

    return StreamingResponse(
        _event_stream(
            repo_id_str,
            user_id,
            body.message,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# GET /api/chat/{repo_id}/messages
# ---------------------------------------------------------------------------

@router.get("/{repo_id}/messages")
@limiter.limit(settings.rate_chat)
async def get_chat_history(
    request: Request,
    repo_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
):
    """Return persisted chat history for an owned repository."""

    user_id = current_user.id
    repo_id_str = str(repo_id)

    supabase = get_supabase_client()

    # Verify repository ownership.
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