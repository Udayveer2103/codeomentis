"""
heatmap.py  —  RepoMind Week 3
GET /api/heatmap/{repo_id}

Reads pre-computed scores from file_scores (written during ingestion by
complexity.py / ingestion.py Stage 4).  No computation happens here —
this is a pure DB read.

Query params:
  severity  — "all" | "high" | "medium" | "low"   (default: "all")
  sort      — "composite_score" | "cc_score" | "coupling_score"
              | "todo_density" | "fn_length_score" | "file_path"
              (default: "composite_score")
  limit     — 10–500  (default: 200)
"""

from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings
from app.db.supabase import get_supabase_client

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_VALID_SORT = {
    "composite_score",
    "cc_score",
    "coupling_score",
    "todo_density",
    "fn_length_score",
    "file_path",
}

_VALID_SEVERITY = {"all", "high", "medium", "low"}


@router.get("/{repo_id}")
@limiter.limit(settings.rate_heatmap)
async def get_heatmap(
    request: Request,
    repo_id: str,
    severity: str = Query("all"),
    sort: str = Query("composite_score"),
    limit: int = Query(200, ge=10, le=500),
):
    """
    Returns file-level tech debt scores for the given repo.

    Response shape:
    {
      "repo_id": "...",
      "summary": {
        "total_files": 1220,
        "high_count": 0,
        "medium_count": 15,
        "low_count": 1205,
        "avg_composite": 8.17,
        "max_composite": 55.0
      },
      "files": [
        {
          "id": "2c3c28f1-...",
          "file_path": "app/services/ingestion.py",
          "language": "python",
          "composite_score": 55.0,
          "cc_score": 72.1,
          "coupling_score": 40.0,
          "todo_density": 5.0,
          "fn_length_score": 61.3,
          "severity": "medium",
          "line_count": 312,
          "function_count": 18,
          "todo_count": 2
        },
        ...
      ]
    }
    """
    # ── Validate params ───────────────────────────────────────────────────────
    if severity not in _VALID_SEVERITY:
        raise HTTPException(
            status_code=422,
            detail=f"severity must be one of: {', '.join(sorted(_VALID_SEVERITY))}",
        )
    if sort not in _VALID_SORT:
        raise HTTPException(
            status_code=422,
            detail=f"sort must be one of: {', '.join(sorted(_VALID_SORT))}",
        )

    supabase = get_supabase_client()

    # ── Verify repo exists and is ready ──────────────────────────────────────
    repo_res = (
        supabase.table("repos")
        .select("id, status")
        .eq("id", repo_id)
        .single()
        .execute()
    )
    if not repo_res.data:
        raise HTTPException(status_code=404, detail="Repo not found")
    if repo_res.data["status"] != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Repo not ready (status: {repo_res.data['status']})",
        )

    # ── Fetch summary stats (all files, no severity filter) ──────────────────
    # We fetch a lightweight select for the summary so filtering doesn't
    # distort the counts and averages shown in the summary bar.
    summary_res = (
        supabase.table("file_scores")
        .select("composite_score, severity")
        .eq("repo_id", repo_id)
        .execute()
    )

    all_rows = summary_res.data or []
    summary = _compute_summary(all_rows)

    # ── Fetch file rows (with optional severity filter) ───────────────────────
    query = (
        supabase.table("file_scores")
        .select(
            "id, file_path, language, composite_score, cc_score, "
            "coupling_score, todo_density, fn_length_score, severity, "
            "line_count, function_count, todo_count"
        )
        .eq("repo_id", repo_id)
    )

    if severity != "all":
        query = query.eq("severity", severity)

    # Supabase Python client: order() — ascending=False for DESC
    ascending = sort == "file_path"   # only file_path sorts A→Z; scores sort high→low
    query = query.order(sort, desc=not ascending).limit(limit)

    files_res = query.execute()
    files = files_res.data or []

    return {
        "repo_id": repo_id,
        "summary": summary,
        "files": files,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_summary(rows: list[dict]) -> dict:
    if not rows:
        return {
            "total_files": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "avg_composite": 0.0,
            "max_composite": 0.0,
        }

    scores = [r["composite_score"] for r in rows]
    severities = [r["severity"] for r in rows]

    return {
        "total_files": len(rows),
        "high_count": severities.count("high"),
        "medium_count": severities.count("medium"),
        "low_count": severities.count("low"),
        "avg_composite": round(sum(scores) / len(scores), 1),
        "max_composite": round(max(scores), 1),
    }