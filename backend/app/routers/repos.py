from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.db.supabase import get_supabase_client
from app.config import settings

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/repos", tags=["repos"])

# Dev bypass — same pattern as impact.py, heatmap.py
DEV_USER_ID = "9a1d390c-f049-4199-8146-503123f4f1f3"


@router.get("")
@limiter.limit(settings.rate_heatmap)   # reuse same rate config; add rate_repos to config if you want separate tuning
async def list_repos(request: Request):
    user_id = DEV_USER_ID
    supabase = get_supabase_client()

    result = (
        supabase.table("repos")
        .select("id, owner, name, status, error_message, file_count, architecture_pattern, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    if result.data is None:
        raise HTTPException(status_code=500, detail="Failed to fetch repositories")

    return {"repos": result.data}
@router.get("/{repo_id}")
@limiter.limit(settings.rate_heatmap)
async def get_repo(request: Request, repo_id: str):
    user_id = DEV_USER_ID
    supabase = get_supabase_client()

    result = (
        supabase.table("repos")
        .select(
            "id, owner, name, status, error_message, file_count, architecture_pattern, created_at"
        )
        .eq("id", repo_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Repository not found")

    return result.data