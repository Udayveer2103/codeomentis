"""
Architecture analysis — overview, config, folders, and summary
generation for the Architecture Analyzer feature.

Follows the same module-level-functions convention as
services/walkthrough.py: no service class, each function opens its
own Supabase client. Reads what ingestion already computed
(repo_files, repos.tech_stack, repos.architecture_pattern) rather
than recomputing anything.

Config and folder analysis are deterministic, filename/path-pattern
based, kept as private module functions here per the locked
architecture — extract to a standalone module only if this file
grows significantly.
"""

from __future__ import annotations

import logging

from app.db.supabase import get_supabase_client
from app.services.graph_adapter import GraphNotFoundError, get_architecture_graph
from app.services.summarizer import generate_architecture_summary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Known config file purposes (deterministic — filename/path pattern based)
# ---------------------------------------------------------------------------

_CONFIG_PURPOSES: dict[str, tuple[str, str]] = {
    "package.json": ("Node.js package manifest — dependencies and scripts", "dependency"),
    "requirements.txt": ("Python dependency list", "dependency"),
    "pyproject.toml": ("Python project manifest — dependencies and build config", "dependency"),
    "Pipfile": ("Python dependency manifest (pipenv)", "dependency"),
    "tsconfig.json": ("TypeScript compiler configuration", "build"),
    "next.config.js": ("Next.js build/runtime configuration", "build"),
    "next.config.ts": ("Next.js build/runtime configuration", "build"),
    "next.config.mjs": ("Next.js build/runtime configuration", "build"),
    "vite.config.ts": ("Vite build configuration", "build"),
    "vite.config.js": ("Vite build configuration", "build"),
    "tailwind.config.ts": ("Tailwind CSS configuration", "styling"),
    "tailwind.config.js": ("Tailwind CSS configuration", "styling"),
    "Dockerfile": ("Container image definition", "deployment"),
    "docker-compose.yml": ("Multi-container local/deploy orchestration", "deployment"),
    "docker-compose.yaml": ("Multi-container local/deploy orchestration", "deployment"),
    "railway.json": ("Railway deployment configuration", "deployment"),
    "vercel.json": ("Vercel deployment configuration", "deployment"),
    "render.yaml": ("Render deployment configuration", "deployment"),
    "fly.toml": ("Fly.io deployment configuration", "deployment"),
    "prisma.schema": ("Prisma database schema", "database"),
    "schema.prisma": ("Prisma database schema", "database"),
    "drizzle.config.ts": ("Drizzle ORM configuration", "database"),
    "drizzle.config.js": ("Drizzle ORM configuration", "database"),
}

_WORKFLOW_PREFIX = ".github/workflows/"
_WORKFLOW_PURPOSE = ("GitHub Actions CI/CD workflow", "deployment")

_FOLDER_RESPONSIBILITIES: dict[str, str] = {
    "components": "Reusable UI components",
    "pages": "Route-level page components",
    "app": "Application routes/pages (app router convention)",
    "routers": "API route definitions",
    "routes": "API route definitions",
    "services": "Business logic, isolated from route handlers",
    "models": "Data models / schema definitions",
    "hooks": "Reusable stateful logic (React hooks)",
    "middleware": "Request/response pipeline middleware",
    "utils": "Shared utility functions",
    "lib": "Shared library code",
    "db": "Database access/configuration",
    "tests": "Automated tests",
    "test": "Automated tests",
    "config": "Application configuration",
    "public": "Static assets",
    "static": "Static assets",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_overview(repo_id: str) -> dict:
    """
    Combines what ingestion already computed (tech_stack,
    architecture_pattern) with lightweight counts derived from
    repo_files. Does not recompute tech detection.
    """

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("repos")
            .select(
                "owner,name,language_stats,file_count,"
                "architecture_pattern,tech_stack"
            )
            .eq("id", repo_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise ValueError(f"Repo not found: {repo_id}") from exc

    repo_row = result.data

    files = _get_repo_files(repo_id)
    config_files = [f for f in files if f["is_config"]]

    return {
        "repository": f"{repo_row['owner']}/{repo_row['name']}",
        "architecture_pattern": repo_row.get("architecture_pattern"),
        "tech_stack": repo_row.get("tech_stack"),
        "language_stats": repo_row.get("language_stats"),
        "file_count": repo_row.get("file_count"),
        "config_file_count": len(config_files),
    }


def get_config_analysis(repo_id: str) -> list[dict]:
    return _analyze_config(repo_id)


def get_folder_analysis(repo_id: str) -> list[dict]:
    return _analyze_folders(repo_id)


async def get_summary(repo_id: str) -> dict:
    """
    Returns {"summary": str | None, "cached": bool}.

    Cache check: if repos.architecture_summary is already set, it's
    returned as-is with no LLM call. Invalidated automatically on
    re-ingestion, which clears this column to NULL — see
    ingestion.py Stage 6.
    """

    supabase = get_supabase_client()

    repo_result = (
        supabase.table("repos")
        .select("architecture_summary")
        .eq("id", repo_id)
        .single()
        .execute()
    )

    existing = (
        repo_result.data.get("architecture_summary")
        if repo_result.data else None
    )

    if existing:
        return {"summary": existing, "cached": True}

    overview = get_overview(repo_id)
    config_files = _analyze_config(repo_id)
    folders = _analyze_folders(repo_id)

    try:
        graph = get_architecture_graph(repo_id, view="module")
        graph_summary = {
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
        }
    except GraphNotFoundError:
        graph_summary = None

    architecture_data = {
        "repository": overview["repository"],
        "architecture_pattern": overview["architecture_pattern"],
        "tech_stack": overview["tech_stack"],
        "config_files": config_files,
        "folders": folders,
        "graph_summary": graph_summary,
    }

    summary = await generate_architecture_summary(architecture_data)

    if summary:
        supabase.table("repos").update(
            {"architecture_summary": summary}
        ).eq("id", repo_id).execute()

    return {"summary": summary, "cached": False}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _analyze_config(repo_id: str) -> list[dict]:
    """
    Explains each detected config file's purpose. Deterministic,
    filename-pattern based — no raw content is available at request
    time by design (nothing intermediate was persisted), so this
    works from path alone.
    """

    files = _get_repo_files(repo_id)
    config_files = [f for f in files if f["is_config"]]

    results = []

    for f in config_files:
        purpose, category = _lookup_config_purpose(f["path"])

        results.append({
            "path": f["path"],
            "purpose": purpose,
            "category": category,
        })

    return results


def _lookup_config_purpose(path: str) -> tuple[str, str]:
    if path.startswith(_WORKFLOW_PREFIX):
        return _WORKFLOW_PURPOSE

    filename = path.rsplit("/", 1)[-1]

    if filename in _CONFIG_PURPOSES:
        return _CONFIG_PURPOSES[filename]

    return ("Configuration file", "other")


def _analyze_folders(repo_id: str) -> list[dict]:
    """
    Groups source files by top-level folder and attaches a known
    responsibility where the folder name matches a common
    convention. Folders with no known convention are still listed,
    just without a responsibility label.
    """

    files = _get_repo_files(repo_id)
    source_files = [f for f in files if not f["is_config"]]

    folder_counts: dict[str, int] = {}

    for f in source_files:
        top_folder = _top_level_folder(f["path"])
        folder_counts[top_folder] = folder_counts.get(top_folder, 0) + 1

    return [
        {
            "folder": folder,
            "file_count": count,
            "responsibility": _FOLDER_RESPONSIBILITIES.get(folder.lower()),
        }
        for folder, count in sorted(folder_counts.items())
    ]


def _top_level_folder(path: str) -> str:
    if "/" not in path:
        return "(root)"

    return path.split("/", 1)[0]


def _get_repo_files(repo_id: str) -> list[dict]:
    supabase = get_supabase_client()

    response = (
        supabase.table("repo_files")
        .select("path,language,is_config")
        .eq("repo_id", repo_id)
        .execute()
    )

    return response.data or []