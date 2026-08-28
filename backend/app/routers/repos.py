import logging

from fastapi import APIRouter, Request, HTTPException, Response, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.db.supabase import AuthUser, get_supabase_client
from app.dependencies import get_current_user
from app.config import settings

logger = logging.getLogger(__name__)
supabase = get_supabase_client()
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/repos", tags=["repos"])

# Dev bypass — same pattern as impact.py, heatmap.py



@router.get("")
@limiter.limit(settings.rate_heatmap)  # reuse same rate config; add rate_repos to config if you want separate tuning
async def list_repos(
    request: Request,
    current_user: AuthUser = Depends(get_current_user),
):
    user_id = current_user.id

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
async def get_repo(
    request: Request,
    repo_id: str,
    current_user: AuthUser = Depends(get_current_user),
):
    user_id = current_user.id

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


@router.get("/{repo_id}/progress")
@limiter.limit(settings.rate_heatmap)
async def get_repo_progress(
    request: Request,
    repo_id: str,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Returns the single latest progress_events row for this repository —
    a plain polled GET, distinct from the existing SSE stream at
    GET /api/ingest/{repo_id}/progress (which the frontend doesn't
    currently use). Ownership is checked the same way as get_repo()
    before touching progress_events, so this can't be used to probe
    another user's repo_id.
    """
    user_id = current_user.id
    supabase = get_supabase_client()

    repo = (
        supabase.table("repos")
        .select("id")
        .eq("id", repo_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )

    if not repo.data:
        raise HTTPException(status_code=404, detail="Repository not found")

    result = (
        supabase.table("progress_events")
        .select(
            "stage, progress, message, files_processed, total_files, "
            "functions_extracted, chunks_created, total_chunks, "
            "graph_nodes, graph_edges, created_at"
        )
        .eq("repo_id", repo_id)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        # Ingestion hasn't emitted anything yet (e.g. very first moment
        # after the repo row was created) — not an error, just nothing
        # to report yet.
        return None

    return result.data[0]


@router.delete("/{repo_id}", status_code=204)
@limiter.limit(settings.rate_heatmap)
async def delete_repo(
    request: Request,
    repo_id: str,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Removes a repository from RepoMind — never touches the actual GitHub
    repository. Deleting the `repos` row cascades (ON DELETE CASCADE) to
    every dependent table that references repo_id: file_scores,
    code_chunks, chat_messages, walkthrough_steps, impact_ai_cache
    (per supabase/migrations/*). The call graph JSON in the "graphs"
    Storage bucket is NOT covered by Postgres FK cascades, so it's
    removed explicitly below.
    """
    user_id = current_user.id
    supabase = get_supabase_client()

    # The service-role key bypasses RLS, so this explicit user_id filter
    # is what actually enforces ownership here — same pattern as
    # list_repos/get_repo above. A repo_id that exists but belongs to
    # another user matches zero rows, same as a repo_id that doesn't
    # exist at all — both return 404, never leaking existence.
    result = (
        supabase.table("repos")
        .delete()
        .eq("id", repo_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Best-effort: the row (and its cascaded RepoMind data) is already
    # gone at this point regardless of whether this succeeds.
    try:
        supabase.storage.from_("graphs").remove([f"{repo_id}/call_graph.json"])
    except Exception:
        logger.warning(
            "Failed to remove graph storage object for repo %s",
            repo_id,
            exc_info=True,
        )

    return Response(status_code=204)