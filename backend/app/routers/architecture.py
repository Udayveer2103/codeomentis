"""
Architecture Analyzer router — thin HTTP layer.

All architecture analysis, config/folder parsing, and summary
generation lives in services/architecture_service.py (module-level
functions, matching services/walkthrough.py's convention); graph
reshaping lives in services/graph_adapter.py. This router is
responsible only for: auth/status gating (repo exists, repo is
ready), delegating to those functions, and shaping the JSON
response.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.db.supabase import get_supabase_client
from app.services.architecture_service import (
    get_config_analysis,
    get_folder_analysis,
    get_overview,
    get_summary,
)
from app.services.graph_adapter import GraphNotFoundError, get_architecture_graph

router = APIRouter(prefix="/api/architecture", tags=["architecture"])
limiter = Limiter(key_func=get_remote_address)


def _require_ready_repo(repo_id: str) -> None:
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


@router.get("/{repo_id}/overview")
@limiter.limit(settings.rate_heatmap)
async def get_overview_route(request: Request, repo_id: str):
    _require_ready_repo(repo_id)

    try:
        return get_overview(repo_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{repo_id}/config")
@limiter.limit(settings.rate_heatmap)
async def get_config_route(request: Request, repo_id: str):
    _require_ready_repo(repo_id)

    return {
        "repo_id": repo_id,
        "config_files": get_config_analysis(repo_id),
    }


@router.get("/{repo_id}/folders")
@limiter.limit(settings.rate_heatmap)
async def get_folders_route(request: Request, repo_id: str):
    _require_ready_repo(repo_id)

    return {
        "repo_id": repo_id,
        "folders": get_folder_analysis(repo_id),
    }


@router.get("/{repo_id}/graph")
@limiter.limit(settings.rate_heatmap)
async def get_graph_route(request: Request, repo_id: str, view: str = "module"):
    _require_ready_repo(repo_id)

    try:
        return get_architecture_graph(repo_id, view=view)
    except GraphNotFoundError:
        raise HTTPException(
            status_code=404, detail="No call graph found for this repo"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{repo_id}/summary")
@limiter.limit(settings.rate_heatmap)
async def get_summary_route(request: Request, repo_id: str):
    _require_ready_repo(repo_id)

    result = await get_summary(repo_id)

    return {"repo_id": repo_id, **result}