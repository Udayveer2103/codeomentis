from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.db.supabase import AuthUser, get_supabase_client
from app.dependencies import get_current_user
from app.services.ingestion import run_ingestion

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ingest"])

# Simple GitHub URL pattern
GITHUB_URL_RE = re.compile(
    r"^https://github\.com/[\w\-\.]+/[\w\-\.]+/?$"
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    github_url: str

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")

        if not GITHUB_URL_RE.match(v):
            raise ValueError(
                "Must be a valid public GitHub URL: https://github.com/owner/repo"
            )

        if len(v) > 200:
            raise ValueError("URL must be under 200 characters")

        return v


class IngestResponse(BaseModel):
    repo_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# POST /api/ingest
# ---------------------------------------------------------------------------

@router.post("", response_model=IngestResponse)
# or @router.post("/")
async def start_ingestion(
    body: IngestRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Create a repo record and kick off the background ingestion pipeline.
    """


    user_id = current_user.id

    supabase = get_supabase_client()

    # Check if repo already exists
    existing = (
        supabase.table("repos")
        .select("id, status")
        .eq("user_id", user_id)
        .eq("github_url", body.github_url)
        .execute()
    )

    existing_data = existing.data[0] if existing.data else None

    if existing_data:
        existing_status = existing_data["status"]

        if existing_status == "indexing":
            raise HTTPException(
                status_code=409,
                detail="This repository is already being indexed",
            )

        repo_id = existing_data["id"]

        supabase.table("repos").update({
            "status": "indexing",
            "error_message": None,
        }).eq("id", repo_id).execute()

    else:
        repo_id = str(uuid.uuid4())

        supabase.table("repos").insert({
            "id": repo_id,
            "user_id": user_id,
            "github_url": body.github_url,
            "owner": "",
            "name": "",
            "status": "indexing",
        }).execute()

    # Spawn background task
    background_tasks.add_task(
        run_ingestion,
        repo_id=repo_id,
        github_url=body.github_url,
        user_id=user_id,
    )

    logger.info(
        "Ingestion started: repo_id=%s url=%s",
        repo_id,
        body.github_url,
    )

    return IngestResponse(
        repo_id=repo_id,
        status="indexing",
        message="Repository ingestion started. Stream progress at /api/ingest/{repo_id}/progress",
    )


# ---------------------------------------------------------------------------
# GET /api/ingest/{repo_id}/progress
# ---------------------------------------------------------------------------

@router.get("/{repo_id}/progress")
async def stream_progress(
    repo_id: str,
    request: Request,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Server-Sent Events stream for ingestion progress.
    """

    user_id = current_user.id

    supabase = get_supabase_client()

    repo = (
        supabase.table("repos")
        .select("id, user_id")
        .eq("id", repo_id)
        .eq("user_id", user_id)
        .execute()
    )

    repo_data = repo.data[0] if repo.data else None

    if not repo_data:
        raise HTTPException(status_code=404, detail="Repository not found")

    return StreamingResponse(
        _event_generator(repo_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _event_generator(
    repo_id: str,
    request: Request,
) -> AsyncGenerator[str, None]:

    supabase = get_supabase_client()

    last_id = 0
    terminal_stages = {"ready", "error"}

    poll_interval = 1.0
    keepalive_every = 15
    elapsed_since_keepalive = 0

    while True:

        if await request.is_disconnected():
            logger.debug("SSE client disconnected for repo %s", repo_id)
            break

        result = (
            supabase.table("progress_events")
            .select("id, stage, progress, message")
            .eq("repo_id", repo_id)
            .gt("id", last_id)
            .order("id", desc=False)
            .limit(20)
            .execute()
        )

        events = result.data or []

        for event in events:
            last_id = event["id"]

            payload = json.dumps({
                "stage": event["stage"],
                "progress": event["progress"],
                "message": event["message"],
            })

            yield f"data: {payload}\n\n"

            if event["stage"] in terminal_stages:
                return

        elapsed_since_keepalive += poll_interval

        if elapsed_since_keepalive >= keepalive_every:
            yield ": keepalive\n\n"
            elapsed_since_keepalive = 0

        await asyncio.sleep(poll_interval)
