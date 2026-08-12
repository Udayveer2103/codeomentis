"""
Ingestion orchestrator — runs the full pipeline for a single repository.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.db.supabase import get_supabase_client
from app.services.ast_walker import ASTWalker, FunctionInfo
from app.services.complexity import score_files
from app.services.embeddings import embed_functions
from app.services.github import GitHubService
from app.services.graph_builder import build_call_graph, serialise_graph
from app.services.tech_detector import detect_architecture_pattern, detect_tech_stack

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_ingestion(repo_id: str, github_url: str, user_id: str) -> None:
    """
    Full ingestion pipeline. Called as a FastAPI BackgroundTask.
    """

    try:
        await _pipeline(repo_id, github_url, user_id)

    except Exception as exc:

        logger.exception(
            "Ingestion failed for repo %s: %s",
            repo_id,
            exc,
        )

        await _mark_error(repo_id, str(exc))


# ---------------------------------------------------------------------------
# Pipeline implementation
# ---------------------------------------------------------------------------

async def _pipeline(repo_id: str, github_url: str, user_id: str) -> None:

    supabase = get_supabase_client()

    # -----------------------------------------------------------------------
    # Stage 1 — GitHub Fetch
    # -----------------------------------------------------------------------

    await _emit(
        repo_id,
        "fetching",
        5,
        "Connecting to GitHub..."
    )

    github_svc = GitHubService()

    repo_meta = await asyncio.to_thread(
        github_svc.fetch_repo,
        github_url,
    )

    await _emit(
        repo_id,
        "fetching",
        20,
        f"Fetched {len(repo_meta.files)} files from "
        f"{repo_meta.owner}/{repo_meta.name}",
    )

    # FIXED: update() instead of upload()
    supabase.table("repos").update({
        "owner": repo_meta.owner,
        "name": repo_meta.name,
        "default_branch": repo_meta.default_branch,
        "file_count": len(repo_meta.files),
        "language_stats": repo_meta.language_stats,
        "status": "indexing",
    }).eq("id", repo_id).execute()

    # Persist the lightweight file tree (path/language/is_config) so
    # architecture analysis can read repo structure at request time
    # without re-fetching from GitHub. Source files and config files
    # share one list here — is_config is the only thing distinguishing
    # them downstream.
    file_tree_rows = [
        {"path": f.path, "language": f.language, "is_config": False}
        for f in repo_meta.files
    ] + [
        {"path": f.path, "language": f.language, "is_config": True}
        for f in repo_meta.config_files
    ]

    if file_tree_rows:
        supabase.rpc(
            "replace_repo_files",
            {"p_repo_id": repo_id, "p_rows": file_tree_rows},
        ).execute()

    # -----------------------------------------------------------------------
    # Stage 2 — AST Parsing
    # -----------------------------------------------------------------------

    await _emit(
        repo_id,
        "parsing",
        25,
        "Parsing source files..."
    )

    walker = ASTWalker()

    all_functions: list[FunctionInfo] = []

    for i, repo_file in enumerate(repo_meta.files):

        funcs = await asyncio.to_thread(
            walker.extract_functions,
            repo_file.path,
            repo_file.content,
            repo_file.language,
        )

        all_functions.extend(funcs)

        if i % 20 == 0 and i > 0:

            progress = 25 + int(
                (i / len(repo_meta.files)) * 15
            )

            await _emit(
                repo_id,
                "parsing",
                progress,
                f"Parsed {i}/{len(repo_meta.files)} files "
                f"({len(all_functions)} functions found)",
            )

    await _emit(
        repo_id,
        "parsing",
        40,
        f"Extracted {len(all_functions)} functions "
        f"from {len(repo_meta.files)} files",
    )

    # -----------------------------------------------------------------------
    # Stage 3 — Graph Building
    # -----------------------------------------------------------------------

    await _emit(
        repo_id,
        "graphing",
        42,
        "Building call graph..."
    )

    graph_bundle = await asyncio.to_thread(
        build_call_graph,
        all_functions,
    )

    arch_pattern = detect_architecture_pattern(repo_meta.files)

    graph_json = serialise_graph(graph_bundle.call_graph)

    storage_path = f"{repo_id}/call_graph.json"

    try:

        logger.info(
            "Uploading graph to storage: %s",
            storage_path,
        )

        # FIXED: proper first-time upload
        supabase.storage.from_("graphs").upload(
            path=storage_path,
            file=graph_json.encode("utf-8"),
            file_options={
                "content-type": "application/json",
            },
        )

        logger.info("Graph upload successful")

    except Exception as upload_error:

        logger.warning(
            "Upload failed, attempting update fallback: %s",
            upload_error,
        )

        try:

            supabase.storage.from_("graphs").update(
                path=storage_path,
                file=graph_json.encode("utf-8"),
                file_options={
                    "content-type": "application/json",
                },
            )

            logger.info("Graph update fallback successful")

        except Exception as update_error:

            logger.exception(
                "Storage upload completely failed: %s",
                update_error,
            )

            raise update_error

    await _emit(
        repo_id,
        "graphing",
        50,
        f"Built call graph: "
        f"{graph_bundle.call_graph.number_of_nodes()} nodes, "
        f"{graph_bundle.call_graph.number_of_edges()} edges",
    )

    # -----------------------------------------------------------------------
    # Stage 4 — Complexity Scoring
    # -----------------------------------------------------------------------

    await _emit(
        repo_id,
        "scoring",
        52,
        "Scoring complexity and tech debt..."
    )

    file_scores = await asyncio.to_thread(
        score_files,
        repo_meta.files,
        all_functions,
        graph_bundle.import_graph,
    )

    score_rows = [
        {
            "repo_id": repo_id,
            "file_path": s.file_path,
            "language": s.language,
            "cc_score": s.cc_score,
            "coupling_score": s.coupling_score,
            "todo_density": s.todo_density,
            "fn_length_score": s.fn_length_score,
            "composite_score": s.composite_score,
            "severity": s.severity,
            "line_count": s.line_count,
            "function_count": s.function_count,
            "todo_count": s.todo_count,
        }
        for s in file_scores
    ]

    for chunk in _chunks(score_rows, 100):

        supabase.table("file_scores").upsert(
            chunk,
            on_conflict="repo_id,file_path",
        ).execute()

    await _emit(
        repo_id,
        "scoring",
        65,
        f"Scored {len(file_scores)} files",
    )

    # -----------------------------------------------------------------------
    # Stage 5 — Embeddings
    # -----------------------------------------------------------------------

    await _emit(
        repo_id,
        "embedding",
        67,
        "Generating code embeddings..."
    )

    chunks = await embed_functions(
        all_functions,
        repo_id,
    )

    await _emit(
        repo_id,
        "embedding",
        85,
        f"Embedding {len(chunks)} code chunks..."
    )

    if chunks:

        supabase.table("code_chunks") \
            .delete() \
            .eq("repo_id", repo_id) \
            .execute()

        chunk_rows = [
            {
                "repo_id": repo_id,
                "file_path": c.file_path,
                "function_name": c.function_name,
                "chunk_type": c.chunk_type,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "content": c.content,
                "embedding": c.embedding,
            }
            for c in chunks
        ]

        for batch in _chunks(chunk_rows, 50):

            supabase.table("code_chunks") \
                .insert(batch) \
                .execute()

    # -----------------------------------------------------------------------
    # Stage 6 — Finalise
    # -----------------------------------------------------------------------

    await _emit(
        repo_id,
        "storing",
        95,
        "Finalising..."
    )

    tech_stack = detect_tech_stack(
        repo_meta.files,
        repo_meta.config_files,
        repo_meta.language_stats,
    )

    supabase.table("repos").update({
        "status": "ready",
        "architecture_pattern": arch_pattern,
        "tech_stack": tech_stack,
        "architecture_summary": None,
        "chunk_count": len(chunks),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "error_message": None,
    }).eq("id", repo_id).execute()

    await _emit(
        repo_id,
        "ready",
        100,
        f"Done! "
        f"{len(repo_meta.files)} files, "
        f"{len(all_functions)} functions, "
        f"{len(chunks)} embeddings",
    )

    logger.info(
        "Ingestion complete for repo %s",
        repo_id,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _emit(
    repo_id: str,
    stage: str,
    progress: int,
    message: str,
) -> None:

    logger.info(
        "[%s] %s (%d%%) — %s",
        repo_id[:8],
        stage,
        progress,
        message,
    )

    supabase = get_supabase_client()

    supabase.table("progress_events").insert({
        "repo_id": repo_id,
        "stage": stage,
        "progress": progress,
        "message": message,
    }).execute()


async def _mark_error(
    repo_id: str,
    error_message: str,
) -> None:

    supabase = get_supabase_client()

    supabase.table("repos").update({
        "status": "error",
        "error_message": error_message[:500],
    }).eq("id", repo_id).execute()

    await _emit(
        repo_id,
        "error",
        0,
        f"Error: {error_message[:200]}",
    )


def _chunks(lst: list, n: int):

    for i in range(0, len(lst), n):
        yield lst[i:i + n]