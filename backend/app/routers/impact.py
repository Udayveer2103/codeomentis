"""
impact.py — CodeoMentis Week 3
GET /api/impact/{repo_id}?function=file.py::my_func

Loads the call graph from Supabase Storage, reverses it,
runs BFS from the queried node to find callers (blast radius),
and returns structured JSON ready for D3 force-graph rendering.

Milestone 4: added optional force_refresh param, passed straight
through to run_impact_analysis(). No other change to this file's
behavior — request validation, error handling, and the /functions
autocomplete endpoint are all unchanged.
"""

from fastapi import APIRouter, HTTPException, Query

from app.db.supabase import get_supabase_client
from app.services.impact import run_impact_analysis

router = APIRouter(
    prefix="/api/impact",
    tags=["impact"],
)


@router.get("/{repo_id}")
async def get_impact(
    repo_id: str,
    function: str = Query(
        ...,
        description="Qualified function name: file_path::func_name",
    ),
    max_depth: int = Query(
        5,
        ge=1,
        le=10,
    ),
    force_refresh: bool = Query(
        False,
        description=(
            "If true, bypass the cached AI reasoning result and "
            "regenerate it. Does not affect graph loading, BFS, or "
            "any deterministic fact computation — only the AI "
            "reasoning cache."
        ),
    ),
):
    """
    Returns the blast-radius graph for a given function node.
    """

    supabase = get_supabase_client()

    try:
        repo_res = (
            supabase.table("repos")
            .select("id,status")
            .eq("id", repo_id)
            .single()
            .execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate repository: {str(e)}",
        )

    if not repo_res.data:
        raise HTTPException(
            status_code=404,
            detail="Repo not found",
        )

    status = repo_res.data.get("status")

    if status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Repo not ready (status: {status})",
        )

    try:
        result = await run_impact_analysis(
            supabase=supabase,
            repo_id=repo_id,
            query_node=function,
            max_depth=max_depth,
            force_refresh=force_refresh,
        )

        return result

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Impact analysis failed: {str(e)}",
        )


@router.get("/{repo_id}/functions")
async def list_functions(
    repo_id: str,
    search: str = Query(
        "",
        description="Optional substring filter",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
    ),
):
    """
    Returns a flat list of all known function nodes for autocomplete.

    Search filtering is intentionally performed in Python instead
    of PostgREST because Supabase Worker 1101 errors can occur when
    using ilike() on some projects.
    """

    supabase = get_supabase_client()

    try:
        res = (
            supabase.table("code_chunks")
            .select("file_path,function_name")
            .eq("repo_id", repo_id)
            .eq("chunk_type", "function")
            .limit(1000)
            .execute()
        )

        rows = res.data or []

        if search and search.strip():
            search_lower = search.strip().lower()

            rows = [
                row
                for row in rows
                if row.get("function_name")
                and search_lower in row["function_name"].lower()
            ]

        rows.sort(
            key=lambda row: (
                row.get("function_name") or ""
            ).lower()
        )

        functions = [
            {
                "id": f"{row['file_path']}::{row['function_name']}",
                "file_path": row["file_path"],
                "function_name": row["function_name"],
            }
            for row in rows[:limit]
            if row.get("function_name")
        ]

        return {
            "functions": functions
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load functions: {str(e)}",
        )