"""
Onboarding Walkthrough router — thin HTTP layer.

All cache validation, generation, and persistence logic lives in
services/walkthrough.py. This router is responsible only for: auth/status
gating (repo exists, repo is ready), delegating to the service, and
shaping the JSON response.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.db.supabase import get_supabase_client
from app.services.walkthrough import get_or_generate_walkthrough

router = APIRouter(prefix="/api/walkthrough", tags=["walkthrough"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/{repo_id}")
@limiter.limit(settings.rate_heatmap)
async def get_walkthrough(request: Request, repo_id: str):
    supabase = get_supabase_client()

    repo_result = (
        supabase.table("repos")
        .select("id,status")
        .eq("id", repo_id)
        .single()
        .execute()
    )
    repo = repo_result.data
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")

    if repo["status"] != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Repo is not ready yet (status: {repo['status']})",
        )

    result = await get_or_generate_walkthrough(repo_id)

    return {"repo_id": repo_id, "steps": result.steps, "cached": result.cached}